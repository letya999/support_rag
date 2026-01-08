import os
import inspect
import logging
from abc import abstractmethod
from typing import Dict, Any, Optional, List

from app.pipeline.state import State
from app.observability.tracing import observe, langfuse_context
from app.services.config_loader.loader import get_global_param
from app.observability.state_validator import (
    StateValidator,
    InputContract,
    OutputContract,
    ContractViolation,
)
from app.observability.input_state_filter import InputStateFilter
from app.observability.output_state_validator import OutputStateValidator
from app.observability.validation_config import get_validation_config


logger = logging.getLogger(__name__)


class BaseNode(StateValidator):
    """
    Abstract base class for all nodes in the RAG pipeline.
    Encapsulates common logic like tracing, state management, configuration,
    and input/output contract validation.
    
    Nodes can define contracts by setting class variables:
        INPUT_CONTRACT = {
            "required": ["question", "user_id"],
            "optional": ["session_id"]
        }
        OUTPUT_CONTRACT = {
            "guaranteed": ["answer"],
            "conditional": ["confidence", "docs"]
        }
    
    Or by overriding get_input_contract() and get_output_contract() methods.
    """
    
    # Default empty contracts - subclasses should override
    INPUT_CONTRACT: Dict[str, List[str]] = {}
    OUTPUT_CONTRACT: Dict[str, List[str]] = {}
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.timeout_ms = get_global_param("timeout_ms", 5000)
        self.retry_count = get_global_param("retry_count", 3)
        
        # Initialize filters with validation config
        self._init_filters()
    
    def _init_filters(self):
        """Initialize input/output filters based on current config."""
        config = get_validation_config()
        self._validation_enabled = config.enabled
        
        if config.enabled:
            self._input_filter = InputStateFilter(
                self,
                strict_mode=config.strict_required_inputs,
                log_removed=config.log_filtering
            )
            self._output_validator = OutputStateValidator(
                self,
                strict_mode=config.strict_mode,
                log_violations=config.log_violations,
                auto_filter=config.filter_outputs
            )
        else:
            self._input_filter = None
            self._output_validator = None

    # === StateValidator interface implementation ===
    
    def get_input_contract(self) -> InputContract:
        """
        Returns the input contract for this node.
        
        Override this method or set INPUT_CONTRACT class variable.
        """
        return InputContract(
            required=self.INPUT_CONTRACT.get("required", []),
            optional=self.INPUT_CONTRACT.get("optional", [])
        )
    
    def get_output_contract(self) -> OutputContract:
        """
        Returns the output contract for this node.
        
        Override this method or set OUTPUT_CONTRACT class variable.
        """
        return OutputContract(
            guaranteed=self.OUTPUT_CONTRACT.get("guaranteed", []),
            conditional=self.OUTPUT_CONTRACT.get("conditional", [])
        )
    
    # === LangGraph entry point ===
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        The entry point when the node is called by LangGraph.
        Applies input filtering and output validation if enabled.
        
        Refactored to support Langfuse tracing without direct access to langfuse_context.
        We filter inputs BEFORE passing them to the traced function, and validate outputs
        BEFORE returning them, allowing @observe to automatically capture the clean, 
        filtered data.
        """
        
        # Step 1: Prepare Input (Filter if enabled)
        input_to_processed = state
        input_metadata = {}
        
        if self._validation_enabled and self._input_filter:
            contract = self.get_input_contract()
            if contract.required or contract.optional:
                # Calculate stats potentially for logging (optional)
                # original_size = len(str(state))
                try:
                    input_to_processed = self._input_filter.apply(state)
                except ValueError as e:
                    logger.error(f"Input validation failed for node '{self.name}': {e}", exc_info=True)
                    raise
                # filtered_size = len(str(input_to_processed))
                # input_metadata = ... (Cant attach easily without context)
            else:
                input_to_processed = state
        
        # Step 2: Define Traced Wrapper
        # This function receives the FILTERED input, so @observe logs the clean version
        @observe(name=f"node_{self.name}") 
        async def _execute_traced(current_state: Dict[str, Any]) -> Dict[str, Any]:
            
            # Execute node logic
            output = await self.execute(current_state)
            
            # Step 3: Validate/Filter Output
            if self._validation_enabled and self._output_validator:
                contract = self.get_output_contract()
                if contract.guaranteed or contract.conditional:
                    validated_output = self._output_validator.apply(output)
                    return validated_output
            
            return output

        # Step 4: Execute with filtered input
        try:
            return await _execute_traced(input_to_processed)
        except Exception as e:
            logger.error(f"Error in node '{self.name}' execution: {e}", exc_info=True)
            raise

    
    def _safe_serialize_for_log(self, data: Dict[str, Any], max_str_len: int = 500) -> Dict[str, Any]:
        """
        Safely serialize data for logging, truncating long strings.
        
        Args:
            data: Dictionary to serialize
            max_str_len: Maximum string length before truncation
            
        Returns:
            Serializable dictionary suitable for logging
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_str_len:
                result[key] = value[:max_str_len] + f"... [truncated, total {len(value)} chars]"
            elif isinstance(value, (list, tuple)):
                if len(value) > 10:
                    result[key] = f"[{type(value).__name__} with {len(value)} items]"
                else:
                    result[key] = value
            elif isinstance(value, dict):
                if len(str(value)) > max_str_len:
                    result[key] = f"[dict with {len(value)} keys]"
                else:
                    result[key] = value
            elif callable(value):
                result[key] = f"[callable: {value.__name__ if hasattr(value, '__name__') else 'anonymous'}]"
            else:
                result[key] = value
        return result

    @abstractmethod
    async def execute(self, state: State) -> Dict[str, Any]:
        """
        Node logic implementation. Should be overridden by subclasses.
        
        IMPORTANT: Return ONLY the fields that this node produces/modifies.
        Do NOT return the entire state - this causes "State Bloat" in logs.
        
        Args:
            state: The filtered graph state (only contains fields from input contract)
            
        Returns:
            Dict containing ONLY state updates (fields from output contract)
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

