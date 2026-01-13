"""
LLMValidator - Validates low-confidence predictions using LLM with context.

Sends minimal information to LLM (question + examples) for validation.
"""

import json
import asyncio
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from app.logging_config import logger
from .models import (
    LLMValidationRequest,
    LLMValidationResult,
    CategoryContext,
    MetadataConfig
)


class LLMValidator:
    """
    Validates classification predictions using LLM with context.

    Sends low-confidence predictions to GPT-3.5-turbo with examples
    for validation and correction.
    """

    def __init__(self, config: Optional[MetadataConfig] = None):
        """Initialize LLM validator."""
        self.config = config or MetadataConfig()
        self.client = AsyncOpenAI()
        self.model = "gpt-3.5-turbo"

    async def validate_category(
        self,
        question: str,
        predicted_category: str,
        confidence: float,
        context: CategoryContext
    ) -> Dict:
        """
        Validate predicted category with context examples.

        Args:
            question: The question to validate
            predicted_category: ML-predicted category
            confidence: Confidence score from embedding classifier
            context: CategoryContext with examples

        Returns:
            Dict with validation result:
                - is_correct: bool
                - suggested_category: str (may differ from predicted)
                - confidence: float
                - reasoning: str (optional)
        """
        prompt = self._build_category_prompt(
            question,
            predicted_category,
            confidence,
            context
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a support ticket category validator. "
                            "You receive a question and verify if it belongs to the suggested category. "
                            "Look at the example questions to understand what this category covers. "
                            "Respond with JSON only."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Low temperature for consistency
                max_tokens=200
            )

            response_text = response.choices[0].message.content
            result = self._parse_llm_response(response_text)

            return {
                "is_correct": result.get("is_correct", True),
                "suggested_category": result.get("suggested_category", predicted_category),
                "confidence": result.get("confidence", confidence),
                "reasoning": result.get("reasoning")
            }

        except Exception as e:
            logger.error("LLM validation error", extra={"category": predicted_category, "error": str(e)})
            # Fallback: trust the prediction
            return {
                "is_correct": True,
                "suggested_category": predicted_category,
                "confidence": confidence,
                "reasoning": f"LLM validation failed, using ML prediction. Error: {str(e)}"
            }

    async def validate_intent(
        self,
        question: str,
        category: str,
        predicted_intent: str,
        confidence: float,
        context: CategoryContext
    ) -> Dict:
        """
        Validate predicted intent within a category.

        Args:
            question: The question to validate
            category: Parent category
            predicted_intent: ML-predicted intent
            confidence: Confidence score from embedding classifier
            context: CategoryContext with examples

        Returns:
            Dict with validation result
        """
        prompt = self._build_intent_prompt(
            question,
            category,
            predicted_intent,
            confidence,
            context
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are an intent classifier for the '{category}' support category. "
                            "You receive a question and verify if it matches the suggested intent. "
                            "Look at the example questions to understand what this intent covers. "
                            "The intent must be within the same category. "
                            "Respond with JSON only."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=200
            )

            response_text = response.choices[0].message.content
            result = self._parse_llm_response(response_text)

            return {
                "is_correct": result.get("is_correct", True),
                "suggested_intent": result.get("suggested_intent", predicted_intent),
                "confidence": result.get("confidence", confidence),
                "reasoning": result.get("reasoning")
            }

        except Exception as e:
            logger.error("LLM validation error", extra={"intent": predicted_intent, "error": str(e)})
            return {
                "is_correct": True,
                "suggested_intent": predicted_intent,
                "confidence": confidence,
                "reasoning": f"LLM validation failed, using ML prediction. Error: {str(e)}"
            }

    async def validate_batch(
        self,
        validation_requests: List[Dict],
        batch_size: Optional[int] = None
    ) -> List[Dict]:
        """
        Validate multiple items in parallel batches.

        Args:
            validation_requests: List of validation request dicts
            batch_size: Number of items per batch (uses config default if None)

        Returns:
            List of validation results
        """
        if batch_size is None:
            batch_size = self.config.llm_batch_size

        # Split into batches
        batches = [
            validation_requests[i:i+batch_size]
            for i in range(0, len(validation_requests), batch_size)
        ]

        results = []

        # Process batches with max parallel limit
        for batch_idx in range(0, len(batches), self.config.max_parallel_batches):
            parallel_batches = batches[batch_idx:batch_idx + self.config.max_parallel_batches]

            # Process these batches in parallel
            tasks = [
                self._process_batch(batch)
                for batch in parallel_batches
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for batch_result in batch_results:
                if isinstance(batch_result, Exception):
                    logger.error("Error processing LLM batch", extra={"error": str(batch_result)})
                    continue
                results.extend(batch_result)

        return results

    async def _process_batch(self, batch: List[Dict]) -> List[Dict]:
        """Process a single batch of validation requests."""
        results = []

        for request in batch:
            if request["type"] == "category":
                result = await self.validate_category(
                    request["question"],
                    request["predicted_category"],
                    request["confidence"],
                    request["context"]
                )
            elif request["type"] == "intent":
                result = await self.validate_intent(
                    request["question"],
                    request["category"],
                    request["predicted_intent"],
                    request["confidence"],
                    request["context"]
                )
            else:
                continue

            result["qa_index"] = request.get("qa_index")
            results.append(result)

        return results

    def _build_category_prompt(
        self,
        question: str,
        predicted_category: str,
        confidence: float,
        context: CategoryContext
    ) -> str:
        """Build prompt for category validation."""
        examples = "\n".join([
            f"- {example.content[:100]}..."
            for example in context.examples
        ])

        prompt = f"""Question: "{question}"

Predicted category: "{predicted_category}"
ML confidence: {confidence:.2f}

Examples of questions in this category:
{examples if examples else "(No examples available)"}

Task: Validate if this question belongs to "{predicted_category}".
If not, suggest the correct category.

Respond with JSON (no markdown, just JSON):
{{"is_correct": true/false, "suggested_category": "...", "confidence": 0.0-1.0, "reasoning": "..."}}
"""
        return prompt

    def _build_intent_prompt(
        self,
        question: str,
        category: str,
        predicted_intent: str,
        confidence: float,
        context: CategoryContext
    ) -> str:
        """Build prompt for intent validation."""
        examples = "\n".join([
            f"- {example.content[:100]}..."
            for example in context.examples
        ])

        prompt = f"""Question: "{question}"

Category: "{category}"
Predicted intent: "{predicted_intent}"
ML confidence: {confidence:.2f}

Examples of questions with this intent:
{examples if examples else "(No examples available)"}

Task: Validate if this question has intent "{predicted_intent}" within {category} category.
If not, suggest the correct intent (must be within {category}).

Respond with JSON (no markdown, just JSON):
{{"is_correct": true/false, "suggested_intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}}
"""
        return prompt

    def _parse_llm_response(self, response_text: str) -> Dict:
        """
        Parse JSON response from LLM.

        Handles various formats and malformed responses.
        """
        try:
            # Remove markdown if present
            text = response_text.strip()
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            return result

        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response", extra={"response_snippet": response_text[:200]})
            # Return safe defaults
            return {
                "is_correct": True,
                "confidence": 0.5,
                "reasoning": "Failed to parse response"
            }
