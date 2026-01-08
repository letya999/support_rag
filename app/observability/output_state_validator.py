"""
Output State Validator for Observability.

Validates and filters the output from a node's execute method,
ensuring only declared fields are returned.

This solves the "State Bloat" problem where nodes return 
the entire state (53+ fields) instead of just their changes.
"""

from typing import Dict, Any, List, Optional
import logging

from app.observability.state_validator import OutputContract, ContractViolation, StateValidator

logger = logging.getLogger(__name__)


class OutputStateValidator:
    """
    Validates and optionally filters node outputs against their contracts.
    
    Usage:
        validator = OutputStateValidator(node, strict_mode=True)
        validated_output = validator.apply(raw_output)
    """
    
    def __init__(
        self,
        validator: StateValidator,
        strict_mode: bool = True,
        log_violations: bool = True,
        auto_filter: bool = True
    ):
        """
        Initialize the output validator.
        
        Args:
            validator: The node implementing StateValidator interface
            strict_mode: If True, remove undeclared fields from output
            log_violations: If True, log contract violations
            auto_filter: If True, automatically filter out undeclared fields
        """
        self.validator = validator
        self.strict_mode = strict_mode
        self.log_violations = log_violations
        self.auto_filter = auto_filter
        self.node_name = getattr(validator, 'name', validator.__class__.__name__)
    
    def apply(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and optionally filter the output.
        
        Args:
            output: The raw output dictionary from node's execute method
            
        Returns:
            Validated (and optionally filtered) output dictionary
        """
        contract = self.validator.get_output_contract()
        
        # If no fields defined (empty contract), pass through everything
        # This maintains backward compatibility with nodes that don't define contracts
        if not contract.guaranteed and not contract.conditional:
            return output
        
        allowed_fields = contract.all_fields
        violations = []
        filtered_output = {}
        removed_fields = []
        
        for key, value in output.items():
            if key in allowed_fields:
                filtered_output[key] = value
            else:
                removed_fields.append(key)
                violations.append(ContractViolation(
                    node_name=self.node_name,
                    violation_type='unexpected_output',
                    field_name=key,
                    message=f"Output field '{key}' not in contract"
                ))
        
        # Log violations
        if self.log_violations and violations:
            for v in violations:
                logger.warning(
                    f"[{v.node_name}] Contract violation: {v.message}"
                )
        
        # Return filtered or original based on settings
        if self.auto_filter:
            if removed_fields:
                logger.debug(
                    f"[{self.node_name}] Output filter removed {len(removed_fields)} fields: "
                    f"{removed_fields[:10]}{'...' if len(removed_fields) > 10 else ''}"
                )
            return filtered_output
        
        return output
    
    def validate(self, output: Dict[str, Any]) -> List[ContractViolation]:
        """
        Validate output without filtering (for inspection/debugging).
        
        Args:
            output: The output dictionary to validate
            
        Returns:
            List of contract violations found
        """
        return self.validator.validate_output(output)
    
    def get_stats(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about what would be filtered/validated.
        
        Args:
            output: The output dictionary
            
        Returns:
            Dict with validation statistics
        """
        contract = self.validator.get_output_contract()
        allowed_fields = contract.all_fields
        
        all_keys = set(output.keys())
        valid_keys = all_keys & allowed_fields
        invalid_keys = all_keys - allowed_fields
        missing_guaranteed = set(contract.guaranteed) - all_keys
        
        # Calculate sizes
        import json
        original_size = len(json.dumps(output, default=str))
        filtered_size = len(json.dumps({k: output[k] for k in valid_keys}, default=str))
        
        return {
            "node_name": self.node_name,
            "original_field_count": len(all_keys),
            "valid_field_count": len(valid_keys),
            "invalid_field_count": len(invalid_keys),
            "invalid_fields": list(invalid_keys),
            "missing_guaranteed": list(missing_guaranteed),
            "original_size_bytes": original_size,
            "filtered_size_bytes": filtered_size,
            "size_reduction_pct": round((1 - filtered_size / original_size) * 100, 1) if original_size > 0 else 0
        }
