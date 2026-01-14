"""
Input State Filter for Observability.

Filters the state before it's passed to a node's execute method,
keeping only the fields declared in the node's input contract.

This solves the "State Pollution" problem where nodes receive 
the entire state (18KB-30KB) instead of just what they need.
"""

from typing import Dict, Any, Optional, Set, List
import logging

from app.observability.state_validator import InputContract, StateValidator
from app.utils.size_estimator import estimate_size

logger = logging.getLogger(__name__)


class InputStateFilter:
    """
    Filters state to only include fields in a node's input contract.
    
    Usage:
        filter = InputStateFilter(node)
        filtered_state = filter.apply(full_state)
    """
    
    def __init__(
        self, 
        validator: StateValidator,
        strict_mode: bool = False,
        log_removed: bool = True
    ):
        """
        Initialize the input filter.
        
        Args:
            validator: The node implementing StateValidator interface
            strict_mode: If True, raise error on missing required inputs
            log_removed: If True, log which fields were removed (DEBUG level)
        """
        self.validator = validator
        self.strict_mode = strict_mode
        self.log_removed = log_removed
        self.node_name = getattr(validator, 'name', validator.__class__.__name__)
    
    def apply(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply the input filter to the state.
        
        Args:
            state: The full state dictionary
            
        Returns:
            Filtered state containing only allowed input fields
            
        Raises:
            ValueError: In strict_mode if required inputs are missing
        """
        contract = self.validator.get_input_contract()
        
        # If no fields defined (empty contract), pass through everything
        # This maintains backward compatibility with nodes that don't define contracts
        if not contract.required and not contract.optional:
            return state
        
        allowed_fields = contract.all_fields
        
        # Validate required inputs
        if self.strict_mode:
            missing = [f for f in contract.required if f not in state or state[f] is None]
            if missing:
                raise ValueError(
                    f"Node '{self.node_name}' missing required inputs: {missing}"
                )
        
        # Filter the state
        filtered = {}
        removed_fields = []
        
        for key, value in state.items():
            if key in allowed_fields:
                filtered[key] = value
            else:
                removed_fields.append(key)
        
        # Log what was removed (DEBUG level to avoid noise in production)
        if self.log_removed and removed_fields:
            logger.debug(
                f"[{self.node_name}] Input filter removed {len(removed_fields)} fields: "
                f"{removed_fields[:10]}{'...' if len(removed_fields) > 10 else ''}"
            )
        
        return filtered
    
    def get_stats(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about what would be filtered.
        
        Useful for debugging and observability dashboards.
        
        Args:
            state: The full state dictionary
            
        Returns:
            Dict with statistics about filtering
        """
        contract = self.validator.get_input_contract()
        allowed_fields = contract.all_fields
        
        all_keys = set(state.keys())
        kept_keys = all_keys & allowed_fields
        removed_keys = all_keys - allowed_fields
        missing_required = set(contract.required) - all_keys
        
        # Calculate size reduction (approximate)
        # Calculate size reduction (approximate)
        original_size = estimate_size({k: state[k] for k in all_keys})
        filtered_size = estimate_size({k: state[k] for k in kept_keys})
        
        return {
            "node_name": self.node_name,
            "original_field_count": len(all_keys),
            "filtered_field_count": len(kept_keys),
            "removed_field_count": len(removed_keys),
            "removed_fields": list(removed_keys),
            "missing_required": list(missing_required),
            "original_size_bytes": original_size,
            "filtered_size_bytes": filtered_size,
            "size_reduction_pct": round((1 - filtered_size / original_size) * 100, 1) if original_size > 0 else 0
        }
