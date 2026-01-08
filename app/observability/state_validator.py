"""
State Validator System for Observability.

Provides abstract base classes and utilities for defining and validating
input/output contracts for pipeline nodes.

This solves the "State Pollution" and "State Bloat" problems by:
1. Defining explicit input contracts (what each node needs)
2. Defining explicit output contracts (what each node produces)
3. Filtering inputs to only what's needed
4. Validating outputs to only what's declared
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Type
from dataclasses import dataclass, field


@dataclass
class InputContract:
    """Defines what inputs a node requires and optionally accepts."""
    required: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    
    @property
    def all_fields(self) -> Set[str]:
        """Returns all fields that are allowed as input."""
        return set(self.required) | set(self.optional)


@dataclass  
class OutputContract:
    """Defines what outputs a node can produce."""
    guaranteed: List[str] = field(default_factory=list)
    conditional: List[str] = field(default_factory=list)
    
    @property
    def all_fields(self) -> Set[str]:
        """Returns all fields that are allowed as output."""
        return set(self.guaranteed) | set(self.conditional)


@dataclass
class ContractViolation:
    """Represents a contract violation for logging/debugging."""
    node_name: str
    violation_type: str  # 'missing_required_input', 'unexpected_output', 'unexpected_input'
    field_name: str
    message: str


class StateValidator(ABC):
    """
    Abstract base class for state validation.
    
    Each node should implement this interface to define its contracts.
    The BaseNode will use these contracts to filter inputs and validate outputs.
    """
    
    @abstractmethod
    def get_input_contract(self) -> InputContract:
        """
        Returns the input contract for this node.
        
        Returns:
            InputContract with required and optional input fields.
        """
        pass
    
    @abstractmethod
    def get_output_contract(self) -> OutputContract:
        """
        Returns the output contract for this node.
        
        Returns:
            OutputContract with guaranteed and conditional output fields.
        """
        pass
    
    def validate_input(self, state: Dict[str, Any]) -> List[ContractViolation]:
        """
        Validates that the state contains all required inputs.
        
        Args:
            state: The current state dictionary
            
        Returns:
            List of ContractViolation objects for missing required inputs
        """
        contract = self.get_input_contract()
        violations = []
        
        for field in contract.required:
            if field not in state or state[field] is None:
                violations.append(ContractViolation(
                    node_name=getattr(self, 'name', self.__class__.__name__),
                    violation_type='missing_required_input',
                    field_name=field,
                    message=f"Required input '{field}' is missing or None"
                ))
        
        return violations
    
    def validate_output(self, output: Dict[str, Any]) -> List[ContractViolation]:
        """
        Validates that the output contains only declared fields.
        
        Args:
            output: The output dictionary from the node
            
        Returns:
            List of ContractViolation objects for unexpected fields
        """
        contract = self.get_output_contract()
        violations = []
        
        allowed_fields = contract.all_fields
        
        for field in output.keys():
            if field not in allowed_fields:
                violations.append(ContractViolation(
                    node_name=getattr(self, 'name', self.__class__.__name__),
                    violation_type='unexpected_output',
                    field_name=field,
                    message=f"Output field '{field}' is not declared in output contract"
                ))
        
        return violations
    
    def filter_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filters the state to only include fields in the input contract.
        
        Args:
            state: The full state dictionary
            
        Returns:
            Filtered state with only allowed fields
        """
        contract = self.get_input_contract()
        allowed_fields = contract.all_fields
        
        return {k: v for k, v in state.items() if k in allowed_fields}
    
    def filter_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filters the output to only include fields in the output contract.
        
        Args:
            output: The full output dictionary
            
        Returns:
            Filtered output with only allowed fields
        """
        contract = self.get_output_contract()
        allowed_fields = contract.all_fields
        
        return {k: v for k, v in output.items() if k in allowed_fields}


# Default contracts for nodes that don't define their own
class DefaultContracts:
    """Provides default empty contracts - no filtering."""
    
    @staticmethod
    def no_filter_input() -> InputContract:
        """Returns a contract that allows all inputs (no filtering)."""
        return InputContract(required=[], optional=[])
    
    @staticmethod  
    def no_filter_output() -> OutputContract:
        """Returns a contract that allows all outputs (no filtering)."""
        return OutputContract(guaranteed=[], conditional=[])
