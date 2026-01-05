# Архитектурная диаграмма и примеры реализации

## 1. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                    │
│  (Web form / API client для загрузки qa.json и редактирования метаданных)   │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
         POST /analyze                  GET /preview
                │                             │
                ▼                             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI ENDPOINTS                                    │
│  ┌────────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐ │
│  │ /analyze           │  │ /review         │  │ /confirm                 │ │
│  │ - Load JSON        │  │ - Accept diffs  │  │ - Save to DB             │ │
│  │ - Extract Q&A      │  │ - Validate      │  │ - Update registry        │ │
│  └────────────────────┘  └─────────────────┘  └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
        QAMetadataGenerator          AnalysisCache (Redis)
                │                             │
    ┌───────────┼───────────┐                 │
    │           │           │                 │
    ▼           ▼           ▼                 ▼
┌──────────┐ ┌───────────────────┐  ┌──────────────────────┐
│ Embed    │ │ MetadataClusterizer │  │ Redis Cache          │
│ Question │ │ - K-means on N cats  │  │ - Store analysis     │
│   via    │ │ - K-means per cat on  │  │ - TTL 1 hour         │
│  Encoder │ │   M intents          │  │ - Fast retrieval     │
│          │ │ - LLM cluster names  │  │                      │
└──────────┘ └───────────────────┘  └──────────────────────┘
    │           │           │
    └───────────┼───────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                       METADATA GENERATION PIPELINE                           │
│                                                                              │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────────┐ │
│  │ Question Embeddings │ │  K-means (N=15)  │   │ Generate Category Names  │ │
│  │  [dim=384]          │ │  Category: 0-14  │   │ (LLM prompt)             │ │
│  └──────────────────┘   └──────────────────┘   └──────────────────────────┘ │
│           │                     │                        │                   │
│           └─────────────────────┼────────────────────────┘                   │
│                                 ▼                                            │
│                  ┌──────────────────────────┐                                │
│                  │ For each Category:       │                                │
│                  │ ┌────────────────────┐   │                                │
│                  │ │ K-means (M=3)      │   │                                │
│                  │ │ Intent: 0-2        │   │                                │
│                  │ └────────────────────┘   │                                │
│                  │         │                │                                │
│                  │         ▼                │                                │
│                  │ Generate Intent Names    │                                │
│                  │ (LLM prompt)             │                                │
│                  └──────────────────────────┘                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
        SemanticClassifier          HandoffDetector
        (existing service)          (new component)
        - Classify each Q&A         - Rule-based check
        - Get confidence scores     - LLM fallback
                │                             │
                └──────────────┬──────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │  MetadataGenerationResult    │
                │  - proposed_categories       │
                │  - proposed_intents          │
                │  - qa_with_metadata          │
                │  - confidence_scores         │
                │  - statistics                │
                └──────────────────────────────┘
                               │
                ┌──────────────┴──────────────────────┐
                │                                     │
         Save to Redis (TTL 1h)              User Review + Corrections
                │                                     │
                │                    ┌────────────────┼────────────────┐
                │                    │                │                │
                │              Rename cats?    Reassign Q&A?    Modify Handoff?
                │                    │                │                │
                │                    └────────────────┼────────────────┘
                │                                     │
                │                    (POST /review with user corrections)
                │                                     │
                │                    ┌────────────────▼────────────────┐
                │                    │  ValidationResult               │
                │                    │  - is_valid: bool               │
                │                    │  - conflicts: List              │
                │                    │  - ready_for_ingestion: bool    │
                │                    └────────────────┬────────────────┘
                │                                     │
                │                                     ▼
                │                     (POST /confirm with analysis_id)
                │                                     │
                │            ┌────────────────────────┼────────────────────────┐
                │            │                        │                        │
                ▼            ▼                        ▼                        ▼
        ┌─────────────┐ ┌──────────────┐  ┌──────────────────────┐  ┌─────────────┐
        │   PostgreSQL │ │ intents_      │  │  Semantic            │  │  Langfuse   │
        │   documents  │ │ registry.yaml │  │  Classifier          │  │  (Tracing)  │
        │   table      │ │  (updated)    │  │  (refresh embeddings)│  │             │
        └──────────────┘ └──────────────┘  └──────────────────────┘  └─────────────┘
```

---

## 2. Data Flow Sequence Diagram

```
User            Browser         FastAPI          Generator        SemanticCls    Redis
 │                │               │                 │                │           │
 │─ Upload QA ────>              │                 │                │           │
 │                │               │                 │                │           │
 │                │─ POST /analyze─>                │                │           │
 │                │               │                 │                │           │
 │                │               │─ Load JSON ─────>                │           │
 │                │               │ Parse Q&A pairs │                │           │
 │                │               │<────────────────│                │           │
 │                │               │                 │                │           │
 │                │               │─ Embed questions────────────────>│           │
 │                │               │                 │    embeddings  │           │
 │                │               │                 │<───────────────│           │
 │                │               │                 │                │           │
 │                │               │─ K-means clustering (N=15)       │           │
 │                │               │ K-means per cat (M=3)            │           │
 │                │               │ LLM cluster names                │           │
 │                │               │<────────────────┤                │           │
 │                │               │                 │                │           │
 │                │               │─ For each Q&A:────────────────> │           │
 │                │               │   classify + handoff detection   │           │
 │                │               │<───────────────────────────────< │           │
 │                │               │                 │                │           │
 │                │               │─ Build MetadataGenerationResult  │           │
 │                │               │                 │                │           │
 │                │               │─ Save to Redis──────────────────────────────>│
 │                │               │<──────────────────────────────────────────────│
 │                │               │ (analysis_id)  │                │           │
 │                │<─ 200 OK ──────│ (proposed      │                │           │
 │                │ (analysis_id)  │  categories/   │                │           │
 │                │ (proposals)    │  intents/QA)   │                │           │
 │                │                │                │                │           │
 │<─ Show JSON ────│                │                │                │           │
 │ with proposals  │                │                │                │           │
 │                 │                │                │                │           │
 │─ Edit & submit ─>               │                │                │           │
 │                 │                │                │                │           │
 │                 │─POST /review ─>│                │                │           │
 │                 │                │ Validate       │                │           │
 │                 │                │ corrections    │                │           │
 │                 │                │ (category      │                │           │
 │                 │                │  renames,      │                │           │
 │                 │                │  reassigns)    │                │           │
 │                 │                │                │                │           │
 │                 │<─ 200 OK ──────│ (conflicts OK) │                │           │
 │                 │ (validation OK) │                │                │           │
 │                 │                │                │                │           │
 │─ Confirm ───────>               │                │                │           │
 │                 │                │                │                │           │
 │                 │ POST /confirm ─>│                │                │           │
 │                 │                │ Save to DB     │                │           │
 │                 │                │ + update       │                │           │
 │                 │                │   registry     │                │           │
 │                 │                │─ ingestion ───────────────────>│           │
 │                 │                │<──────────────────────────────< │           │
 │                 │                │ (ingestion OK) │                │           │
 │                 │                │                │                │           │
 │                 │                │ (refresh       │                │           │
 │                 │                │  intents)      │                │           │
 │                 │                │                │                │           │
 │                 │<─ 200 OK ──────│ (10 items OK)  │                │           │
 │                 │ (success)      │ (registry upd.)│                │           │
 │<─ Show Success ─│                │                │                │           │
```

---

## 3. File Structure

```
app/
├── services/
│   └── metadata_generation/          # NEW MODULE
│       ├── __init__.py
│       ├── generator.py              # Main QAMetadataGenerator class
│       ├── clustering.py             # MetadataClusterizer
│       ├── handoff_detector.py       # HandoffDetector
│       ├── models.py                 # Pydantic models
│       ├── storage.py                # AnalysisCache (Redis)
│       └── config.py                 # Configuration loader
│
│   ├── ingestion.py                  # Existing, extend for metadata
│   └── ...
│
├── api/
│   └── routes.py                     # Add new endpoints (3 new routes)
│
├── nodes/
│   └── easy_classification/
│       └── semantic_classifier.py    # Existing, already available
│
├── nodes/
│   └── _shared_config/
│       ├── intent_registry.py        # Existing
│       └── intents_registry.yaml     # Existing (will be updated)
│
├── integrations/
│   └── embeddings.py                 # Existing get_embedding()
│
└── settings.py                       # Extend with metadata config

config/
└── metadata_generation.yaml          # NEW CONFIG FILE

scripts/
├── refresh_intents.py                # Existing
└── auto_metadata_migration.py        # NEW (optional, for bulk migration)

tests/
└── services/
    └── metadata_generation/          # NEW TEST MODULE
        ├── test_generator.py
        ├── test_clustering.py
        ├── test_handoff_detector.py
        └── fixtures/
            └── qa_samples.py
```

---

## 4. Key Classes - Pseudo Code

### 4.1 QAMetadataGenerator

```python
# app/services/metadata_generation/generator.py

import asyncio
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel
from app.services.metadata_generation.clustering import MetadataClusterizer
from app.services.metadata_generation.handoff_detector import HandoffDetector
from app.services.metadata_generation.models import (
    MetadataGenerationResult,
    QAPairWithMetadata,
    MetadataGenConfig,
)
from app.nodes.easy_classification.semantic_classifier import SemanticClassificationService
from app.integrations.embeddings import get_embedding


class QAMetadataGenerator:
    """
    Автоматическое генерирование метаданных (категории, интенты, handoff)
    для неразмеченных Q&A документов.
    """

    def __init__(self):
        self.clusterizer = MetadataClusterizer()
        self.handoff_detector = HandoffDetector()
        self.classifier = SemanticClassificationService()

    async def generate_metadata_batch(
        self,
        qa_pairs: List[Dict[str, str]],
        config: Optional[MetadataGenConfig] = None,
    ) -> MetadataGenerationResult:
        """
        Генерирует метаданные для всех Q&A пар.

        Args:
            qa_pairs: Список {'question': str, 'answer': str}
            config: Конфигурация (дефолт: 15 категорий, 3 интента)

        Returns:
            MetadataGenerationResult с предложенными метаданными
        """
        if config is None:
            config = MetadataGenConfig()

        # Step 1: Получить embeddings вопросов
        questions = [pair["question"] for pair in qa_pairs]
        embeddings = await self._get_embeddings_batch(questions)

        # Step 2: Кластеризация на категории и интенты
        clustering_result = await self.clusterizer.cluster_questions(
            questions=questions,
            embeddings=embeddings,
            num_categories=config.num_categories,
            num_intents_per_category=config.num_intents_per_category,
        )

        # Step 3: Для каждого Q&A — классификация + handoff детекция
        qa_with_metadata = []
        for idx, pair in enumerate(qa_pairs):
            question = pair["question"]
            answer = pair["answer"]

            # Classify
            classification = await self.classifier.classify(question)
            category = classification.category if classification else "Uncategorized"
            intent = classification.intent if classification else "unknown"

            # Handoff detection
            requires_handoff = await self.handoff_detector.detect(
                question=question,
                answer=answer,
                category=category,
                intent=intent,
            )

            # Get confidence scores
            cat_confidence = (
                classification.category_confidence if classification else 0.0
            )
            intent_confidence = (
                classification.intent_confidence if classification else 0.0
            )
            handoff_confidence = requires_handoff.get("confidence", 0.5)

            metadata = {
                "category": category,
                "intent": intent,
                "requires_handoff": requires_handoff.get("decision", False),
                "confidence": {
                    "category": cat_confidence,
                    "intent": intent_confidence,
                    "handoff": handoff_confidence,
                },
            }

            qa_with_metadata.append(
                QAPairWithMetadata(
                    question=question,
                    answer=answer,
                    metadata=metadata,
                    **pair,
                )
            )

        # Step 4: Build result
        return MetadataGenerationResult(
            proposed_categories=clustering_result.categories,
            proposed_intents=clustering_result.intents,
            qa_with_metadata=qa_with_metadata,
            statistics={
                "total_pairs": len(qa_pairs),
                "total_categories": len(clustering_result.categories),
                "total_intents": sum(
                    len(cat.intents) for cat in clustering_result.categories
                ),
                "avg_category_confidence": sum(
                    m.metadata["confidence"]["category"]
                    for m in qa_with_metadata
                ) / len(qa_with_metadata),
            },
        )

    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Получить embeddings для списка текстов"""
        embeddings = []
        for text in texts:
            emb = await get_embedding(text)
            embeddings.append(emb)
        return embeddings


# Usage
async def main():
    generator = QAMetadataGenerator()

    qa_pairs = [
        {
            "question": "How do I reset my password?",
            "answer": "You can reset via the forgot password link.",
        },
        # ... more pairs
    ]

    result = await generator.generate_metadata_batch(
        qa_pairs,
        config=MetadataGenConfig(
            num_categories=15,
            num_intents_per_category=3,
        ),
    )

    print(f"Generated {len(result.qa_with_metadata)} items with metadata")
    print(f"Categories: {[c.name for c in result.proposed_categories]}")

    # Save to Redis for later review
    from app.services.metadata_generation.storage import AnalysisCache
    cache = AnalysisCache()
    analysis_id = await cache.save_analysis(result)
    print(f"Analysis saved with ID: {analysis_id}")
```

### 4.2 MetadataClusterizer

```python
# app/services/metadata_generation/clustering.py

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np
from typing import List, Dict, Optional
from app.services.metadata_generation.models import CategoryProposal


class MetadataClusterizer:
    """
    K-means кластеризация вопросов в категории и интенты.
    Генерирует человекочитаемые названия кластеров через LLM.
    """

    async def cluster_questions(
        self,
        questions: List[str],
        embeddings: List[List[float]],
        num_categories: int = 15,
        num_intents_per_category: int = 3,
    ) -> "ClusteringResult":
        """
        Кластеризует вопросы на иерархическую структуру.
        """

        # Convert to numpy
        X = np.array(embeddings, dtype=np.float32)

        # Step 1: K-means для категорий
        kmeans_cat = KMeans(
            n_clusters=num_categories,
            random_state=42,
            n_init=10,
            max_iter=300,
        )
        category_labels = kmeans_cat.fit_predict(X)

        # Step 2: Для каждой категории — K-means для интентов
        category_intents = {}
        for cat_id in range(num_categories):
            cat_mask = category_labels == cat_id
            cat_questions = [q for q, m in zip(questions, cat_mask) if m]
            cat_embeddings = X[cat_mask]

            if len(cat_questions) < num_intents_per_category:
                # Если вопросов меньше чем интентов, просто используем вопросы как интенты
                intents = cat_questions
            else:
                kmeans_intent = KMeans(
                    n_clusters=num_intents_per_category,
                    random_state=42,
                    n_init=10,
                )
                intent_labels = kmeans_intent.fit_predict(cat_embeddings)
                intents = self._aggregate_intent_names(
                    cat_questions, intent_labels, num_intents_per_category
                )

            category_intents[cat_id] = intents

        # Step 3: Генерирование названий кластеров через LLM
        category_names = await self._generate_category_names(
            questions, category_labels, num_categories
        )

        # Step 4: Build CategoryProposal objects
        categories = []
        for cat_id in range(num_categories):
            categories.append(
                CategoryProposal(
                    id=f"cat_{cat_id}",
                    name=category_names.get(cat_id, f"Category {cat_id}"),
                    description=f"Questions about {category_names.get(cat_id, f'category {cat_id}')}",
                    suggested_intents=category_intents.get(cat_id, []),
                    question_count=sum(1 for l in category_labels if l == cat_id),
                )
            )

        return ClusteringResult(
            categories=categories,
            category_labels=category_labels,
            category_intents=category_intents,
        )

    async def _generate_category_names(
        self,
        questions: List[str],
        labels: List[int],
        num_categories: int,
    ) -> Dict[int, str]:
        """Генерирует названия кластеров через LLM"""
        from app.integrations.llm import get_llm

        names = {}
        for cat_id in range(num_categories):
            # Выбрать top 3 вопроса в этой категории
            cat_questions = [
                q for q, label in zip(questions, labels) if label == cat_id
            ]

            if not cat_questions:
                names[cat_id] = f"Category {cat_id}"
                continue

            top_questions = cat_questions[:3]

            prompt = f"""
            Based on these support questions from the same category:
            {chr(10).join(f'- {q}' for q in top_questions)}

            Generate a concise 1-2 word category name that describes them.
            Examples: "Account Access", "Order Management", "Returns & Refunds"

            Category name:"""

            llm = get_llm()
            name = await llm.agenerate(prompt)
            names[cat_id] = name.strip()

        return names

    def _aggregate_intent_names(
        self, questions: List[str], labels: List[int], num_intents: int
    ) -> List[str]:
        """
        Агрегирует названия интентов.
        Простой подход: берем вопрос, наиболее близкий к центру каждого кластера.
        """
        intent_names = []
        for intent_id in range(num_intents):
            intent_questions = [
                q for q, label in zip(questions, labels) if label == intent_id
            ]
            # Берем первый вопрос как представителя
            representative = (
                intent_questions[0]
                if intent_questions
                else f"Intent {intent_id}"
            )
            # Преобразуем в slug
            slug = (
                representative.lower()
                .replace(" ", "_")
                .replace("?", "")[:30]
            )
            intent_names.append(slug)

        return intent_names


class ClusteringResult:
    """Результат кластеризации"""

    def __init__(
        self,
        categories: List[CategoryProposal],
        category_labels: np.ndarray,
        category_intents: Dict[int, List[str]],
    ):
        self.categories = categories
        self.category_labels = category_labels
        self.category_intents = category_intents
```

### 4.3 HandoffDetector

```python
# app/services/metadata_generation/handoff_detector.py

from typing import Dict, Tuple


class HandoffDetector:
    """
    Определяет, требуется ли передача пользователя оператору.
    """

    HANDOFF_KEYWORDS = [
        "operator",
        "human",
        "agent",
        "call",
        "phone",
        "representative",
        "escalate",
        "contact support",
        "customer service",
        "live chat",
    ]

    async def detect(
        self,
        question: str,
        answer: str,
        category: str,
        intent: str,
    ) -> Dict[str, object]:
        """
        Детектирует требуется ли handoff.

        Returns:
            {
                "decision": bool,
                "confidence": float,
                "method": "rule" | "llm",
                "reason": str
            }
        """

        # Step 1: Rule-based detection (быстро)
        rule_result = self._detect_rule_based(question, answer)

        if rule_result["confidence"] > 0.7:
            return rule_result

        # Step 2: LLM-based detection (для неясных случаев)
        llm_result = await self._detect_llm_based(
            question, answer, category, intent
        )

        return llm_result

    def _detect_rule_based(self, question: str, answer: str) -> Dict:
        """Правило-базированная детекция"""
        score = 0.0
        reason_parts = []

        combined_text = f"{question} {answer}".lower()

        keyword_count = sum(
            1 for kw in self.HANDOFF_KEYWORDS if kw in combined_text
        )

        if keyword_count > 0:
            score += keyword_count * 0.3
            reason_parts.append(f"Found {keyword_count} handoff keywords")

        # Проверить длину ответа (очень короткие ответы могут означать, что нужен оператор)
        if len(answer) < 50:
            score += 0.2
            reason_parts.append("Short answer (< 50 chars)")

        return {
            "decision": score > 0.5,
            "confidence": min(score, 1.0),
            "method": "rule",
            "reason": " + ".join(reason_parts) if reason_parts else "Low confidence",
        }

    async def _detect_llm_based(
        self,
        question: str,
        answer: str,
        category: str,
        intent: str,
    ) -> Dict:
        """LLM-based детекция для сложных случаев"""
        from app.integrations.llm import get_llm

        prompt = f"""
        Given a support question and answer, determine if human operator escalation is needed.

        Question: {question}
        Answer: {answer}
        Category: {category}
        Intent: {intent}

        Respond with JSON: {{"requires_handoff": true/false, "confidence": 0.0-1.0, "reason": "..."}}
        """

        llm = get_llm()
        response = await llm.agenerate(prompt)

        import json

        try:
            parsed = json.loads(response)
            return {
                "decision": parsed.get("requires_handoff", False),
                "confidence": parsed.get("confidence", 0.5),
                "method": "llm",
                "reason": parsed.get("reason", ""),
            }
        except:
            return {
                "decision": False,
                "confidence": 0.3,
                "method": "llm_fallback",
                "reason": "LLM parsing failed",
            }
```

### 4.4 API Endpoints

```python
# Add to app/api/routes.py

from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.metadata_generation.generator import QAMetadataGenerator
from app.services.metadata_generation.storage import AnalysisCache
import json
import uuid

router = APIRouter()

metadata_generator = QAMetadataGenerator()
analysis_cache = AnalysisCache()


@router.post("/documents/metadata-generation/analyze")
async def analyze_qa_file(file: UploadFile = File(...)):
    """
    Анализирует загруженный qa.json и генерирует предложенные метаданные.
    """
    try:
        # 1. Прочитать JSON файл
        content = await file.read()
        qa_pairs = json.loads(content.decode("utf-8"))

        if not isinstance(qa_pairs, list):
            raise ValueError("JSON must be a list of Q&A pairs")

        # 2. Генерировать метаданные
        result = await metadata_generator.generate_metadata_batch(
            qa_pairs,
            config={
                "num_categories": 15,
                "num_intents_per_category": 3,
            },
        )

        # 3. Сохранить в кэш
        analysis_id = str(uuid.uuid4())
        await analysis_cache.save_analysis(analysis_id, result)

        # 4. Вернуть результат
        return {
            "status": "success",
            "analysis_id": analysis_id,
            "proposed_structure": {
                "categories": [
                    {
                        "id": cat.id,
                        "name": cat.name,
                        "description": cat.description,
                        "suggested_intents": cat.suggested_intents,
                    }
                    for cat in result.proposed_categories
                ],
                "qa_pairs": [
                    {
                        "id": idx,
                        "question": qa.question,
                        "answer": qa.answer,
                        "suggested_category": qa.metadata.get("category"),
                        "suggested_intent": qa.metadata.get("intent"),
                        "suggested_requires_handoff": qa.metadata.get(
                            "requires_handoff"
                        ),
                        "confidence": qa.metadata.get("confidence"),
                    }
                    for idx, qa in enumerate(result.qa_with_metadata)
                ],
                "statistics": result.statistics,
            },
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analyzing file: {str(e)}"
        )


@router.post("/documents/metadata-generation/review")
async def review_metadata(request: dict):
    """
    Пользователь редактирует предложенные метаданные.
    """
    analysis_id = request.get("analysis_id")
    user_corrections = request.get("user_corrections", [])

    try:
        # 1. Загрузить из кэша
        result = await analysis_cache.get_analysis(analysis_id)

        # 2. Применить коррекции пользователя
        for correction in user_corrections:
            qa_index = correction.get("qa_index")
            if 0 <= qa_index < len(result.qa_with_metadata):
                qa = result.qa_with_metadata[qa_index]
                qa.metadata["category"] = correction.get(
                    "corrected_category", qa.metadata["category"]
                )
                qa.metadata["intent"] = correction.get(
                    "corrected_intent", qa.metadata["intent"]
                )
                qa.metadata["requires_handoff"] = correction.get(
                    "corrected_requires_handoff",
                    qa.metadata["requires_handoff"],
                )

        # 3. Валидировать
        # (проверить что все категории/интенты существуют)

        # 4. Сохранить обновленный результат
        await analysis_cache.save_analysis(analysis_id, result)

        return {
            "status": "review_accepted",
            "validated": True,
            "conflicts": [],
            "ready_for_ingestion": True,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reviewing metadata: {str(e)}"
        )


@router.post("/documents/metadata-generation/confirm")
async def confirm_metadata(request: dict):
    """
    Финализирует и сохраняет метаданные в БД.
    """
    analysis_id = request.get("analysis_id")

    try:
        # 1. Загрузить финальный результат
        result = await analysis_cache.get_analysis(analysis_id)

        # 2. Сохранить в БД
        from app.services.ingestion import DocumentIngestionService

        ingestion_service = DocumentIngestionService()
        ingested_count = await ingestion_service.ingest_pairs_with_metadata(
            result.qa_with_metadata
        )

        # 3. Обновить intent registry
        import subprocess

        subprocess.run(["python", "scripts/refresh_intents.py"], check=True)

        # 4. Рефрешить классификатор
        classifier = SemanticClassificationService()
        await classifier.refresh_embeddings()

        # 5. Удалить из кэша
        await analysis_cache.delete_analysis(analysis_id)

        return {
            "status": "success",
            "ingested_count": ingested_count,
            "registry_updated": True,
            "message": f"Successfully ingested {ingested_count} Q&A pairs",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error confirming metadata: {str(e)}"
        )
```

---

## 5. Configuration Example

```yaml
# config/metadata_generation.yaml

metadata_generation:
  clustering:
    algorithm: "kmeans"
    random_state: 42
    n_init: 10
    max_iter: 300

  defaults:
    num_categories: 15
    num_intents_per_category: 3
    min_confidence_threshold: 0.6
    language: "en"

  handoff_detection:
    use_rules: true
    use_llm: true
    rule_threshold: 0.7
    llm_threshold: 0.5

  cache:
    backend: "redis"
    ttl_seconds: 3600
    prefix: "metadata_analysis:"

  llm:
    model: "gpt-4"
    temperature: 0.7
    max_tokens: 100
```

---

## 6. Example Usage Flow

### Step 1: Load and Analyze

```bash
# User uploads qa.json
curl -X POST http://localhost:8000/documents/metadata-generation/analyze \
  -F "file=@qa.json"

# Response includes analysis_id and proposals
# analysis_id: "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6"
```

### Step 2: Review and Edit

User sees in UI:
```json
{
  "categories": [
    {
      "name": "Account Access",
      "intents": ["reset_password", "account_recovery", "login_help"]
    },
    ...
  ],
  "qa_pairs": [
    {
      "question": "How do I reset my password?",
      "suggested_category": "Account Access",
      "suggested_intent": "reset_password"
    },
    ...
  ]
}
```

User makes corrections (e.g., rename category, reassign Q&A).

### Step 3: Confirm

```bash
curl -X POST http://localhost:8000/documents/metadata-generation/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_id": "a1b2c3d4-...",
    "action": "save_with_metadata"
  }'

# Response:
# {
#   "status": "success",
#   "ingested_count": 10,
#   "registry_updated": true
# }
```

---

## 7. Testing Strategy

```python
# tests/services/metadata_generation/test_generator.py

import pytest
from app.services.metadata_generation.generator import QAMetadataGenerator


@pytest.fixture
def sample_qa_pairs():
    return [
        {
            "question": "How do I reset my password?",
            "answer": "Click forgot password on login page.",
        },
        {
            "question": "Where is my order?",
            "answer": "Check tracking email for updates.",
        },
        # ... more pairs
    ]


@pytest.mark.asyncio
async def test_generate_metadata_batch(sample_qa_pairs):
    generator = QAMetadataGenerator()
    result = await generator.generate_metadata_batch(sample_qa_pairs)

    assert len(result.qa_with_metadata) == len(sample_qa_pairs)
    assert len(result.proposed_categories) == 15
    assert result.statistics["total_pairs"] == len(sample_qa_pairs)

    # Check metadata structure
    for qa in result.qa_with_metadata:
        assert qa.metadata["category"] is not None
        assert qa.metadata["intent"] is not None
        assert "confidence" in qa.metadata


@pytest.mark.asyncio
async def test_handoff_detection():
    detector = HandoffDetector()

    result = await detector.detect(
        question="Can I speak to a human?",
        answer="Please call our support team.",
        category="Support",
        intent="contact_support",
    )

    assert result["decision"] == True
    assert result["confidence"] > 0.5
```

