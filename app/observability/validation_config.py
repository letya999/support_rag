"""
Validation Configuration for Observability.

Provides configuration options for state validation behavior.
Can be enabled/disabled and configured through environment or config files.
"""

from typing import Optional
from dataclasses import dataclass
import os


@dataclass
class ValidationConfig:
    """Configuration for state validation."""
    
    # Master switch for validation
    enabled: bool = True
    
    # Strict mode removes undeclared fields, non-strict only logs
    strict_mode: bool = False
    
    # Log removed/unexpected fields at DEBUG level
    log_filtering: bool = True
    
    # Log contract violations at WARNING level
    log_violations: bool = True
    
    # Whether to filter inputs (remove fields not in contract)
    filter_inputs: bool = True
    
    # Whether to filter outputs (remove fields not in contract)
    filter_outputs: bool = True
    
    # Raise error when required inputs are missing
    strict_required_inputs: bool = False
    
    @classmethod
    def from_env(cls) -> "ValidationConfig":
        """
        Load configuration from environment variables.
        
        Environment variables:
            - OBSERVABILITY_VALIDATION_ENABLED: "true"/"false"
            - OBSERVABILITY_STRICT_MODE: "true"/"false"
            - OBSERVABILITY_LOG_FILTERING: "true"/"false"
            - OBSERVABILITY_LOG_VIOLATIONS: "true"/"false"
            - OBSERVABILITY_FILTER_INPUTS: "true"/"false"
            - OBSERVABILITY_FILTER_OUTPUTS: "true"/"false"
        """
        def get_bool(name: str, default: bool) -> bool:
            val = os.environ.get(name, "").lower()
            if val in ("true", "1", "yes"):
                return True
            if val in ("false", "0", "no"):
                return False
            return default
        
        return cls(
            enabled=get_bool("OBSERVABILITY_VALIDATION_ENABLED", True),
            strict_mode=get_bool("OBSERVABILITY_STRICT_MODE", False),
            log_filtering=get_bool("OBSERVABILITY_LOG_FILTERING", True),
            log_violations=get_bool("OBSERVABILITY_LOG_VIOLATIONS", True),
            filter_inputs=get_bool("OBSERVABILITY_FILTER_INPUTS", True),
            filter_outputs=get_bool("OBSERVABILITY_FILTER_OUTPUTS", True),
            strict_required_inputs=get_bool("OBSERVABILITY_STRICT_REQUIRED_INPUTS", False),
        )
    
    @classmethod  
    def disabled(cls) -> "ValidationConfig":
        """Returns a config with all validation disabled."""
        return cls(
            enabled=False,
            strict_mode=False,
            log_filtering=False,
            log_violations=False,
            filter_inputs=False,
            filter_outputs=False,
            strict_required_inputs=False,
        )
    
    @classmethod
    def strict(cls) -> "ValidationConfig":
        """Returns a strict configuration for development/testing."""
        return cls(
            enabled=True,
            strict_mode=True,
            log_filtering=True,
            log_violations=True,
            filter_inputs=True,
            filter_outputs=True,
            strict_required_inputs=True,
        )


# Global configuration instance (lazy-loaded)
_config: Optional[ValidationConfig] = None


def get_validation_config() -> ValidationConfig:
    """
    Get the global validation configuration.
    
    Loads from environment on first call, then caches.
    """
    global _config
    if _config is None:
        _config = ValidationConfig.from_env()
    return _config


def set_validation_config(config: ValidationConfig) -> None:
    """
    Set the global validation configuration.
    
    Useful for testing or programmatic configuration.
    """
    global _config
    _config = config


def reset_validation_config() -> None:
    """Reset the global configuration to reload from environment."""
    global _config
    _config = None
