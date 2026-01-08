from typing import Dict, Any, Optional, Set, List
from langfuse.langchain import CallbackHandler
from dataclasses import asdict, is_dataclass

class FilteredLangfuseHandler(CallbackHandler):
    """
    Custom Langfuse Handler that filters state inputs and outputs to reduce trace bloat.
    """
    
    EXCLUDE_KEYS = {
        "embeddings", "question_embedding", "vector_results", "lexical_results",
        "raw_documents", "full_context", "image_data", "docs", "conversation_config"
    }
    
    # Whitelist of keys that are critical for specific nodes (optional refinement)
    # If a node is in this map, ONLY these keys are logged for output.
    NODE_OUTPUT_WHITELIST = {
        "check_cache": {"cache_hit", "cache_key", "answer", "confidence"},
        "retrieve": {"doc_ids", "retrieval_score", "docs"}, # docs might be large, handle carefully
        "generation": {"answer", "tokens_used", "confidence"},
        "state_machine": {"dialog_state", "action_recommendation"},
        "routing": {"action"},
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._node_name_map = {}
        # Allow overriding excludes via init
        if "exclude_keys" in kwargs:
            self.EXCLUDE_KEYS.update(kwargs.pop("exclude_keys"))
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], *, run_id: Any, **kwargs: Any) -> Any:
        node_name = self.get_langchain_run_name(serialized, **kwargs)
        self._node_name_map[run_id] = node_name
        
        # Convert dataclass if needed, then filter
        inputs_dict = asdict(inputs) if is_dataclass(inputs) else dict(inputs)
        filtered_inputs = self._filter_dict(inputs_dict)
        
        return super().on_chain_start(serialized, filtered_inputs, run_id=run_id, **kwargs)
    
    def on_chain_end(self, outputs: Dict[str, Any], *, run_id: Any, **kwargs: Any) -> Any:
        node_name = self._node_name_map.get(run_id, "")
        
        # Safely convert outputs to dict
        if isinstance(outputs, dict):
            outputs_dict = outputs
        elif is_dataclass(outputs):
            outputs_dict = asdict(outputs)
        else:
            # Fallback for non-dict outputs (e.g. string or objects)
            # Try to convert if it looks like a sequence of pairs, otherwise wrap it
            try:
                outputs_dict = dict(outputs)
            except (ValueError, TypeError):
                outputs_dict = {"output": str(outputs)}
        
        # If node has specific whitelist, use it. Otherwise use generic exclude list.
        # Note: Whitelist is stricter.
        
        if node_name in self.NODE_OUTPUT_WHITELIST:
             allowed = self.NODE_OUTPUT_WHITELIST[node_name]
             filtered_outputs = {k: v for k, v in outputs_dict.items() if k in allowed}
        else:
             filtered_outputs = self._filter_dict(outputs_dict)
        
        return super().on_chain_end(filtered_outputs, run_id=run_id, **kwargs)

    def _filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove excluded keys and truncate large values."""
        filtered = {}
        for k, v in data.items():
            if k in self.EXCLUDE_KEYS:
                continue
            
            # Additional safety: Truncate very long strings
            if isinstance(v, str) and len(v) > 5000:
                filtered[k] = v[:1000] + "... [truncated because > 5000 chars]"
            elif isinstance(v, list) and len(v) > 20:
                 filtered[k] = f"[{type(v).__name__} with {len(v)} items]"
            else:
                filtered[k] = v
        return filtered

    def get_langchain_run_name(self, serialized: Dict[str, Any], **kwargs: Any) -> str:
        """Helper to extract node name from serialized data or kwargs."""
        if "name" in kwargs:
            return kwargs["name"]
        if serialized and "name" in serialized:
            return serialized["name"]
        return "unknown_node"
