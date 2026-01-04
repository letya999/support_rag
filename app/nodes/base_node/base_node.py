import os
import inspect
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.pipeline.state import State
from app.observability.tracing import observe
from app.services.config_loader.loader import get_global_param

class BaseNode(ABC):
    """
    Abstract base class for all nodes in the RAG pipeline.
    Encapsulates common logic like tracing, state management, and configuration.
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.timeout_ms = get_global_param("timeout_ms", 5000)
        self.retry_count = get_global_param("retry_count", 3)

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

    def _load_prompt(self, filename: str) -> str:
        """
        Utility to load a prompt from a text file located in the same directory 
        as the node's implementation file.
        
        Args:
            filename: Name of the prompt file (e.g., "prompt_qa.txt")
            
        Returns:
            str: Content of the prompt file
        """
        # Get the file path of the class that inherited BaseNode
        node_file = inspect.getfile(self.__class__)
        node_dir = os.path.dirname(node_file)
        path = os.path.join(node_dir, filename)
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt file not found: {path}")
            
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
