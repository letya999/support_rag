from typing import Dict, Any, List, Optional
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.services.config_loader.loader import get_node_config
import logging

logger = logging.getLogger(__name__)

class ClarificationQuestionsNode(BaseNode):
    """
    Handles multi-turn clarification dialogue.
    Acts as a Logic Controller for the Clarification Loop.
    
    Modes:
    1. Initialization: Entered from Search/Router when doc has questions. Sets up context.
    2. Loop: Entered from Router when context.active=True. Parses answer, asks next question or exits.
    """
    
    INPUT_CONTRACT = {
        "required": ["conversation_history"],
        "optional": [
            "best_doc_metadata", 
            "clarification_task", 
            "clarification_context", 
            "detected_language",
            "last_user_message",
            "dialog_state"
        ]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["answer", "clarification_context"],
        "conditional": ["dialog_state"]
    }
    
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute clarification logic: either initialize a new loop or process the current step.
        """
        context = state.get("clarification_context", {})
        
        # Check if we are already in an active loop
        if context and context.get("active"):
            return await self._handle_loop(state, context)
        else:
            return await self._handle_initialization(state)

    async def _handle_initialization(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start the clarification loop.
        Triggered when HybridSearch finds a document with clarifying_questions.
        """
        # 1. Identify Source
        clarification_task = state.get("clarification_task", {})
        best_doc = state.get("best_doc_metadata", {})
        
        source = clarification_task if clarification_task else best_doc
        questions = source.get("clarifying_questions", [])
        
        if not questions:
            # Fallback: No questions found, exit immediately
            logger.warning("ClarificationNode triggered but no questions found.")
            return {
                "dialog_state": "ANSWER_PROVIDED",
                "clarification_context": {"active": False},
                "answer": ""
            }

        # 2. logical check: External Override (e.g. State Machine wanted Escalation)
        current_state = state.get("dialog_state")
        if current_state and current_state not in ["NEEDS_CLARIFICATION", "INITIAL"]:
             # If something else set the state (like Blocked), bail out.
             return {
                 "dialog_state": current_state,
                 "answer": "",
                 "clarification_context": {"active": False}
             }

        # 3. Create Context
        context = {
            "active": True,
            "questions": questions,
            "current_index": 0,
            "answers": {},
            "original_doc_id": best_doc.get("id"),
            "original_doc_content": best_doc.get("content"),
            "requires_handoff": best_doc.get("requires_handoff", False),
            "target_language": state.get("detected_language", "en")
        }
        
        logger.info(f"Starting Clarification Loop with {len(questions)} questions.")

        # 4. Ask First Question
        question_text = questions[0]
        final_question = await self._translate_question(question_text, context["target_language"])
        
        return {
            "answer": final_question, 
            "clarification_context": context,
            "dialog_state": "NEEDS_CLARIFICATION"
        }

    async def _handle_loop(self, state: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user answer and advance lock.
        """
        questions = context.get("questions", [])
        current_index = context.get("current_index", 0)
        
        # 1. Capture User Answer
        # We assume the user's last message is the answer to questions[current_index]
        user_message = self._get_last_user_message(state)
        
        if current_index < len(questions):
            current_q = questions[current_index]
            context["answers"][current_q] = user_message
            logger.info(f"Collected answer for '{current_q}': '{user_message}'")
        
        # 2. Advance
        current_index += 1
        context["current_index"] = current_index
        
        # 3. Check Completion
        if current_index >= len(questions):
            # All done!
            logger.info("Clarification Loop Complete.")
            context["active"] = False
            
            # Helper: Add collected Q&A to state for PromptRouting to see?
            # It's already in 'clarification_context', PromptRouting should look there.
            
            # Transition to Generation (via Routing)
            # We return empty answer so the Router sees we are done and moves to Generating.
            # We set dialog_state to ANSWER_PROVIDED to signal searching is done.
            return {
                "answer": "", 
                "clarification_context": context,
                "dialog_state": "ANSWER_PROVIDED" 
            }
        else:
            # 4. Ask Next Question
            next_q = questions[current_index]
            final_question = await self._translate_question(next_q, context.get("target_language", "en"))
            
            return {
                "answer": final_question,
                "clarification_context": context,
                "dialog_state": "NEEDS_CLARIFICATION"
            }

    def _get_last_user_message(self, state: Dict[str, Any]) -> str:
        """Helper to get the actual text of the user's latest input."""
        # Optimized: If graph passes 'question' or 'last_user_message' specifically
        if state.get("question"):
             return state.get("question")
             
        history = state.get("conversation_history", [])
        if history:
            last = history[-1]
            if isinstance(last, dict):
                content = last.get("content", "")
                if last.get("role") == "user":
                    return content
            # Add other object type checks if needed
        return ""

    async def _translate_question(self, question: str, target_lang: str) -> str:
        """
        Translate the clarification question to the user's language.
        If target is english or unknown, return as is.
        """
        if not target_lang or target_lang.lower() in ["en", "english", "unknown"]:
            return question
            
        try:
            from app.integrations.llm import get_llm
            from langchain_core.prompts import ChatPromptTemplate
            
            llm = get_llm(temperature=0)
            prompt = ChatPromptTemplate.from_template(
                "Translate the following support question into {language}. "
                "Keep the tone professional and friendly. "
                "Do not add any preamble or quotes.\n\n"
                "Question: {question}"
            )
            chain = prompt | llm
            res = await chain.ainvoke({"language": target_lang, "question": question})
            return res.content.strip()
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return question

clarification_questions_node = ClarificationQuestionsNode()
