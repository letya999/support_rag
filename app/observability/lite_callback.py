"""
Кастомный Langfuse CallbackHandler который создаёт spans БЕЗ inputs/outputs.

Этот handler создаёт только структуру трейса (spans для узлов),
а BaseNode заполняет inputs/outputs отфильтрованными данными через langfuse_context.
"""

from typing import Any, Dict, List, Optional
from langfuse.langchain import CallbackHandler


class LiteCallbackHandler(CallbackHandler):
    """
    Облегчённый CallbackHandler который НЕ логирует inputs/outputs автоматически.
    
    Используется для LangGraph чтобы:
    1. Создать spans для узлов (структура трейса)
    2. НЕ логировать full state автоматически
    3. Позволить BaseNode заполнить inputs/outputs отфильтрованными данными
    """
    
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Override: НЕ логируем inputs при старте chain.
        Создаём span с пустым input.
        """
        # Вызываем parent метод но с пустым input
        super().on_chain_start(
            serialized=serialized,
            inputs={},  # ❗ Пустой вместо full state
            run_id=run_id,
            parent_run_id=parent_run_id,
            tags=tags,
            metadata=metadata,
            **kwargs,
        )
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Override: НЕ логируем outputs при завершении chain.
        Завершаем span с пустым output.
        """
        # Вызываем parent метод но с пустым output
        super().on_chain_end(
            outputs={},  # ❗ Пустой вместо full state
            run_id=run_id,
            parent_run_id=parent_run_id,
            **kwargs,
        )


def get_lite_langfuse_callback_handler() -> LiteCallbackHandler:
    """
    Создаёт облегчённый callback handler для LangGraph.
    
    Returns:
        LiteCallbackHandler который создаёт spans БЕЗ автоматических inputs/outputs
    """
    return LiteCallbackHandler()
