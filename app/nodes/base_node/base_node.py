from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.pipeline.state import State
from app.observability.tracing import observe

class BaseNode(ABC):
    """
    Abstract base class for all nodes in the RAG pipeline.
    Encapsulates common logic like tracing, state management, and configuration.
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__

    ## LangGraph entry point 
    ## with typical langfuse observation annotation for tracing
    # @observe(as_type="span")
    async def __call__(self, state: State) -> Dict[str, Any]:
        """
        The entry point when the node is called by LangGraph.
        """
        return await self.execute(state)

    @abstractmethod
    async def execute(self, state: State) -> Dict[str, Any]:
        """
        Node logic implementation. Should be overridden by subclasses.
        
        Args:
            state: The current graph state
            
        Returns:
            Dict containing state updates
        """
        pass

    def get_config(self, state: State) -> Dict[str, Any]:
        """
        Helper to get node-specific configuration from state or global config.
        """
        return state.get("config", {})
