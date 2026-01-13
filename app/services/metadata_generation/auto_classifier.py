"""
AutoClassificationPipeline - Intelligent Q&A classification with minimal LLM usage.

Architecture:
1. EmbeddingGenerator - sentence-transformers for question embeddings
2. CategoryDiscovery - clustering + TF-IDF keyword extraction → category names  
3. IntentExtractor - semantic patterns + rules → intent names
4. LLMValidator - ONLY for low-confidence cases (редкие вызовы)

All heavy lifting on CPU. LLM called sparingly.
"""

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from app.logging_config import logger

from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class CategoryInfo:
    """Discovered category information."""
    name: str
    keywords: List[str]
    member_indices: List[int]
    centroid: np.ndarray = field(default=None, repr=False)
    
    
@dataclass
class ClassificationResult:
    """Classification result for a single Q&A pair."""
    category: str
    intent: str
    category_confidence: float
    intent_confidence: float
    needs_llm_validation: bool = False
    validation_reason: Optional[str] = None


class AutoClassificationPipeline:
    """
    CPU-first auto-classification pipeline.
    
    Uses sentence-transformers + sklearn for 95% of work.
    LLM only for validation of uncertain cases.
    """
    
    # Category name templates based on common support topics
    # Order matters: more specific patterns first
    CATEGORY_TEMPLATES = {
        # Account Access (login/password related)
        'password': 'Account Access',
        'login': 'Account Access',
        'sign in': 'Account Access',
        'forgot': 'Account Access',
        'reset': 'Account Access',
        
        # Order Management
        'order history': 'Order Management',
        'order': 'Order Management',
        'history': 'Order Management',
        'purchase': 'Order Management',
        
        # Shipping & Delivery
        'track': 'Shipping',
        'package': 'Shipping',
        'ship': 'Shipping',  
        'shipping': 'Shipping',
        'delivery': 'Shipping',
        'address': 'Shipping',
        'international': 'Shipping',
        
        # Returns & Refunds
        'return': 'Returns & Refunds',
        'refund': 'Returns & Refunds',
        'policy': 'Returns & Refunds',
        
        # Billing & Payments
        'payment': 'Billing',
        'pay': 'Billing',
        'billing': 'Billing',
        'card': 'Billing',
        'visa': 'Billing',
        'mastercard': 'Billing',
        'paypal': 'Billing',
        
        # Account Management (profile/settings)
        'subscription': 'Account Management',
        'cancel': 'Account Management',
        'account': 'Account Management',
        'profile': 'Account Management',
        'settings': 'Account Management',
        
        # Support
        'support': 'Support',
        'help': 'Support',
        'contact': 'Support',
        
        # General Info
        'company': 'General Info',
        'about': 'General Info',
        'located': 'General Info',
        'headquarters': 'General Info',
    }
    
    # Intent extraction patterns (action -> intent)
    # Ordered by specificity - more specific patterns first
    INTENT_PATTERNS = [
        # Account Access intents
        (r'reset.*password|forgot.*password|change.*password', 'reset_password'),
        
        # Order Management intents  
        (r'order.*history|my.*orders|past.*orders|find.*order|view.*order', 'view_history'),
        
        # Shipping intents
        (r'track.*order|track.*package|where.*package|order.*status|package.*status', 'track_order'),
        (r'change.*address|update.*address|shipping.*address|modify.*address', 'change_address'),
        (r'international.*ship|ship.*country|deliver.*international|offer.*ship', 'check_shipping_availability'),
        
        # Returns & Refunds intents
        (r'return.*policy|refund.*policy|what.*return|return.*item', 'check_policy'),
        
        # Billing intents
        (r'payment.*method|pay.*with|accept.*card|payment.*accept', 'check_payment_methods'),
        
        # Account Management intents
        (r'cancel.*subscription|stop.*subscription|end.*subscription', 'cancel_subscription'),
        
        # Support intents
        (r'contact.*support|reach.*support|call.*support|email.*support|how.*contact', 'contact_support'),
        
        # General Info intents
        (r'company.*locat|where.*locat|headquarters|about.*company|company.*address', 'company_info'),
    ]
    
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        min_cluster_samples: int = 1,
        distance_threshold: float = 0.8,
        confidence_threshold: float = 0.65,
        llm_validation_threshold: float = 0.5
    ):
        """
        Initialize pipeline.
        
        Args:
            embedding_model: Sentence-transformer model name
            min_cluster_samples: Minimum samples per cluster
            distance_threshold: Clustering distance threshold (lower = more clusters)
            confidence_threshold: Below this, mark as needs_validation
            llm_validation_threshold: Below this, actually call LLM
        """
        self.embedding_model = embedding_model
        self.min_cluster_samples = min_cluster_samples
        self.distance_threshold = distance_threshold
        self.confidence_threshold = confidence_threshold
        self.llm_validation_threshold = llm_validation_threshold
        
        self._encoder: Optional[SentenceTransformer] = None
        self._tfidf: Optional[TfidfVectorizer] = None
        self._categories: List[CategoryInfo] = []
        self._embeddings: Optional[np.ndarray] = None
        self._is_initialized: bool = False
        
    async def initialize(self):
        """
        Load models (CPU-only).
        
        This method initializes the SentenceTransformer and TfidfVectorizer.
        It is idempotent and will return immediately if already initialized.
        """
        if self._is_initialized:
            return
            
        logger.info("Loading embedding model", extra={"model": self.embedding_model})
        loop = asyncio.get_running_loop()
        self._encoder = await loop.run_in_executor(
            None, SentenceTransformer, self.embedding_model
        )
        
        # TF-IDF for keyword extraction
        self._tfidf = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        self._is_initialized = True
        logger.info("AutoClassifier ready")
        
    async def classify_batch(
        self,
        qa_pairs: List[Dict[str, str]],
        use_llm_validation: bool = True
    ) -> Tuple[List[ClassificationResult], List[CategoryInfo]]:
        """
        Classify a batch of Q&A pairs.
        
        Args:
            qa_pairs: List of {"question": "...", "answer": "..."} 
            use_llm_validation: Whether to call LLM for uncertain cases
            
        Returns:
            Tuple of (results, discovered_categories)
        """
        if not qa_pairs:
            return [], []
            
        await self.initialize()
        
        questions = [qa["question"] for qa in qa_pairs]
        
        # Step 1: Generate embeddings (CPU)
        logger.info("AutoClassifier Step 1: Embedding questions", extra={"count": len(questions)})
        loop = asyncio.get_running_loop()
        self._embeddings = await loop.run_in_executor(
            None, self._encoder.encode, questions
        )
        
        # Step 2: Cluster questions (CPU)
        logger.info("AutoClassifier Step 2: Clustering")
        cluster_labels = await self._cluster_questions()
        
        # Step 3: Discover category names using TF-IDF (CPU)
        logger.info("AutoClassifier Step 3: Discovering categories via TF-IDF")
        self._categories = self._discover_categories(questions, cluster_labels)
        
        # Step 4: Classify each Q&A pair (CPU)
        logger.info("AutoClassifier Step 4: Generating classifications")
        results = self._generate_classifications(qa_pairs, cluster_labels)
        
        # Step 5: LLM validation for uncertain cases (optional, minimal)
        if use_llm_validation:
            uncertain_count = sum(1 for r in results if r.needs_llm_validation)
            if uncertain_count > 0:
                logger.info("AutoClassifier Step 5: LLM validation", extra={"uncertain_count": uncertain_count})
                results = await self._validate_uncertain(qa_pairs, results)
        
        logger.info("AutoClassifier completed", extra={"categories_discovered": len(self._categories)})
        return results, self._categories
        
    async def _cluster_questions(self) -> np.ndarray:
        """Cluster question embeddings using Agglomerative Clustering."""
        n = len(self._embeddings)
        
        if n <= 1:
            return np.array([0] * n)
        
        if n <= 3:
            # Too few samples, put each in own cluster or simple grouping
            return np.arange(n)
            
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric='cosine',
            linkage='average'
        )
        
        loop = asyncio.get_running_loop()
        labels = await loop.run_in_executor(
            None, clustering.fit_predict, self._embeddings
        )
        
        logger.debug("Clustering completed", extra={"cluster_count": len(set(labels))})
        return labels
        
    def _discover_categories(
        self,
        questions: List[str],
        cluster_labels: np.ndarray
    ) -> List[CategoryInfo]:
        """
        Discover category names using TF-IDF keyword extraction.
        
        For each cluster:
        1. Extract top TF-IDF keywords
        2. Match keywords to known category templates
        3. If no match, create category from keywords
        """
        categories = []
        unique_clusters = sorted(set(cluster_labels))
        
        for cluster_id in unique_clusters:
            # Get questions in this cluster
            member_indices = [
                i for i, label in enumerate(cluster_labels) 
                if label == cluster_id
            ]
            cluster_questions = [questions[i] for i in member_indices]
            
            # Calculate centroid
            cluster_embeddings = self._embeddings[member_indices]
            centroid = np.mean(cluster_embeddings, axis=0)
            
            # Extract keywords using TF-IDF
            keywords = self._extract_keywords(cluster_questions)
            
            # Map keywords to category name
            category_name = self._keywords_to_category(keywords, cluster_questions)
            
            categories.append(CategoryInfo(
                name=category_name,
                keywords=keywords,
                member_indices=member_indices,
                centroid=centroid
            ))
            
        return categories
        
    def _extract_keywords(self, texts: List[str], top_n: int = 5) -> List[str]:
        """Extract top keywords from texts using TF-IDF."""
        if not texts:
            return []
            
        # Fit TF-IDF on cluster texts
        try:
            tfidf_matrix = self._tfidf.fit_transform(texts)
            feature_names = self._tfidf.get_feature_names_out()
            
            # Sum TF-IDF scores across documents
            scores = np.array(tfidf_matrix.sum(axis=0)).flatten()
            
            # Get top keywords
            top_indices = scores.argsort()[-top_n:][::-1]
            keywords = [feature_names[i] for i in top_indices if scores[i] > 0]
            
            return keywords
        except Exception:
            # Fallback: simple word frequency
            all_words = ' '.join(texts).lower().split()
            word_counts = Counter(all_words)
            # Remove common words
            stopwords = {'how', 'do', 'i', 'can', 'what', 'is', 'the', 'a', 'an', 'my', 'your', 'to', 'you', 'for', 'it', 'of'}
            keywords = [w for w, _ in word_counts.most_common(top_n * 2) if w not in stopwords]
            return keywords[:top_n]
            
    def _keywords_to_category(
        self,
        keywords: List[str],
        questions: List[str]
    ) -> str:
        """Map keywords to a category name."""
        # Check keywords against templates
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for template_key, category_name in self.CATEGORY_TEMPLATES.items():
                if template_key in keyword_lower:
                    return category_name
                    
        # Check full questions against templates
        combined_text = ' '.join(questions).lower()
        for template_key, category_name in self.CATEGORY_TEMPLATES.items():
            if template_key in combined_text:
                return category_name
                
        # Fallback: Create category from top keyword
        if keywords:
            # Capitalize and clean up
            main_keyword = keywords[0].replace('_', ' ').title()
            return f"{main_keyword} Related"
            
        return "General Inquiry"
        
    def _generate_classifications(
        self,
        qa_pairs: List[Dict[str, str]],
        cluster_labels: np.ndarray
    ) -> List[ClassificationResult]:
        """Generate classification for each Q&A pair."""
        results = []
        
        # Build cluster -> category mapping
        cluster_to_category = {}
        for cat in self._categories:
            if cat.member_indices:
                cluster_id = cluster_labels[cat.member_indices[0]]
                cluster_to_category[cluster_id] = cat
                
        for i, (qa, label) in enumerate(zip(qa_pairs, cluster_labels)):
            question = qa["question"]
            
            # FIRST: Try to get category directly from question (more accurate)
            direct_category = self._get_category_from_question(question)
            
            # Get cluster category as fallback
            category_info = cluster_to_category.get(label)
            cluster_category = category_info.name if category_info else "Unknown"
            
            # Use direct category if found, otherwise use cluster
            if direct_category:
                category = direct_category
                category_confidence = 0.9  # High confidence for direct match
            else:
                category = cluster_category
                # Calculate confidence (similarity to centroid)
                if category_info is not None and category_info.centroid is not None:
                    similarity = cosine_similarity(
                        [self._embeddings[i]], 
                        [category_info.centroid]
                    )[0][0]
                    category_confidence = float(max(0, min(1, similarity)))
                else:
                    category_confidence = 0.5
                
            # Extract intent
            intent, intent_confidence = self._extract_intent(question)
            
            # Determine if needs validation
            needs_validation = (
                category_confidence < self.confidence_threshold or
                intent_confidence < self.confidence_threshold
            )
            
            validation_reason = None
            if needs_validation:
                if category_confidence < self.confidence_threshold:
                    validation_reason = f"Low category confidence: {category_confidence:.2f}"
                else:
                    validation_reason = f"Low intent confidence: {intent_confidence:.2f}"
            
            results.append(ClassificationResult(
                category=category,
                intent=intent,
                category_confidence=category_confidence,
                intent_confidence=intent_confidence,
                needs_llm_validation=needs_validation,
                validation_reason=validation_reason
            ))
            
        return results
    
    def _get_category_from_question(self, question: str) -> Optional[str]:
        """
        Try to extract category directly from question text.
        
        Returns category name if found, None otherwise.
        """
        question_lower = question.lower()
        
        # Check question against templates (order matters - more specific first)
        # We need to check more specific patterns before generic ones
        priority_patterns = [
            # Very specific patterns first
            ('reset password', 'Account Access'),
            ('forgot password', 'Account Access'),
            ('order history', 'Order Management'),
            ('my orders', 'Order Management'),
            ('payment method', 'Billing'),
            ('accept card', 'Billing'),
            ('accept visa', 'Billing'),
            ('track package', 'Shipping'),
            ('track order', 'Shipping'),
            ('shipping address', 'Shipping'),
            ('return policy', 'Returns & Refunds'),
            ('cancel subscription', 'Account Management'),
            ('contact support', 'Support'),
            ('company located', 'General Info'),
        ]
        
        for pattern, category in priority_patterns:
            if pattern in question_lower:
                return category
        
        # Then check CATEGORY_TEMPLATES for single-word matches
        for template_key, category_name in self.CATEGORY_TEMPLATES.items():
            if template_key in question_lower:
                return category_name
                
        return None
        
    def _extract_intent(self, question: str) -> Tuple[str, float]:
        """
        Extract intent from question text.
        
        Returns (intent_name, confidence)
        """
        question_lower = question.lower()
        
        # Try pattern matching first (high confidence)
        for pattern, intent in self.INTENT_PATTERNS:
            if re.search(pattern, question_lower):
                return intent, 0.9
                
        # Fallback: Generate intent from key words
        # Remove question words and common words
        cleaned = re.sub(r'[^\w\s]', '', question_lower)
        words = cleaned.split()
        
        stopwords = {
            'how', 'do', 'i', 'can', 'what', 'is', 'the', 'a', 'an', 
            'my', 'your', 'to', 'you', 'for', 'it', 'of', 'are', 
            'where', 'when', 'why', 'will', 'would', 'could', 'should',
            'does', 'did', 'have', 'has', 'be', 'been', 'being'
        }
        
        key_words = [w for w in words if w not in stopwords and len(w) > 2]
        
        if len(key_words) >= 2:
            intent = '_'.join(key_words[:2])
            return intent, 0.7
        elif key_words:
            return key_words[0], 0.6
            
        return 'general_inquiry', 0.5
        
    async def _validate_uncertain(
        self,
        qa_pairs: List[Dict[str, str]],
        results: List[ClassificationResult]
    ) -> List[ClassificationResult]:
        """
        Validate uncertain classifications using LLM.
        
        Only calls LLM for cases below llm_validation_threshold.
        """
        from openai import AsyncOpenAI
        import json
        
        client = AsyncOpenAI()
        
        # Get available categories for context
        category_names = [cat.name for cat in self._categories]
        
        updated_results = []
        llm_calls = 0
        
        for i, (qa, result) in enumerate(zip(qa_pairs, results)):
            # Only validate if really uncertain
            if not result.needs_llm_validation:
                updated_results.append(result)
                continue
                
            # Check if confidence is below LLM threshold
            min_confidence = min(result.category_confidence, result.intent_confidence)
            if min_confidence >= self.llm_validation_threshold:
                # Not uncertain enough for LLM
                updated_results.append(result)
                continue
                
            # Call LLM
            llm_calls += 1
            try:
                validation = await self._call_llm_validator(
                    client,
                    qa["question"],
                    result.category,
                    result.intent,
                    category_names
                )
                
                # Update result with LLM feedback
                updated_result = ClassificationResult(
                    category=validation.get("category", result.category),
                    intent=validation.get("intent", result.intent),
                    category_confidence=validation.get("category_confidence", result.category_confidence),
                    intent_confidence=validation.get("intent_confidence", result.intent_confidence),
                    needs_llm_validation=False,
                    validation_reason=f"LLM validated: {validation.get('reasoning', 'OK')}"
                )
                updated_results.append(updated_result)
                
            except Exception as e:
                logger.error("LLM validation failed", extra={"index": i, "error": str(e)})
                updated_results.append(result)
                
        if llm_calls > 0:
            logger.info("LLM validation completed", extra={"llm_calls": llm_calls})
            
        return updated_results
        
    async def _call_llm_validator(
        self,
        client,
        question: str,
        predicted_category: str,
        predicted_intent: str,
        available_categories: List[str]
    ) -> Dict:
        """Call LLM to validate/correct classification."""
        import json
        
        categories_str = ", ".join(available_categories)
        
        prompt = f"""You are a support ticket classifier validator.

Question: "{question}"
Predicted Category: "{predicted_category}"
Predicted Intent: "{predicted_intent}"

Available categories: {categories_str}

Task: Validate or correct the classification.
- Category should match one of the available categories if possible
- Intent should be a snake_case action verb (e.g., reset_password, track_order)

Respond with JSON only:
{{"category": "...", "intent": "...", "category_confidence": 0.0-1.0, "intent_confidence": 0.0-1.0, "reasoning": "..."}}"""

        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You validate support ticket classifications. JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=150
        )
        
        text = response.choices[0].message.content.strip()
        
        # Parse JSON
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            
        return json.loads(text)
        
    def get_category_summary(self) -> List[Dict]:
        """Get summary of discovered categories."""
        return [
            {
                "name": cat.name,
                "keywords": cat.keywords,
                "question_count": len(cat.member_indices)
            }
            for cat in self._categories
        ]
