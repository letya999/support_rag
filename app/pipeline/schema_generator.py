from typing import TypedDict, Dict, Any, Type, List
from typing import get_type_hints
from app.pipeline.state import State
import logging

logger = logging.getLogger(__name__)

# Get type hints from State for mapping
# We use global scope for efficiency
try:
    STATE_HINTS = get_type_hints(State, globals(), locals())
except Exception as e:
    logger.error(f"Failed to get type hints from State: {e}")
    STATE_HINTS = {}

def generate_node_schema(node_name: str, node_instance: Any) -> Type[TypedDict]:
    """
    Generates a TypedDict schema for a node based on its INPUT_CONTRACT.
    This schema is used by LangGraph to filter the state passed to the node.
    """
    # 1. Check if node has INPUT_CONTRACT
    if not hasattr(node_instance, "INPUT_CONTRACT"):
        # If no contract, we cannot filter safely. Return generic Dict or State.
        # But we must return a type.
        return State 

    contract = node_instance.INPUT_CONTRACT
    required_keys = contract.get("required", [])
    optional_keys = contract.get("optional", [])
    
    all_keys = set(required_keys + optional_keys)
    
    if not all_keys:
        # If contract IS defined but empty, it implies the node needs NO input?
        # Or maybe it wasn't configured.
        # Safest fallback is State.
        return State

    fields = {}
    for key in all_keys:
        if key in STATE_HINTS:
            fields[key] = STATE_HINTS[key]
        else:
            # If key is not in Global State definition, strict typing implies we shouldn't ask for it.
            # But maybe it's a temp key?
            fields[key] = Any
            logger.warning(f"Node '{node_name}' requests key '{key}' not in global State.")
            
    # Create the TypedDict
    # Name it like "CheckCacheInput"
    clean_name = node_name.replace('_', ' ').title().replace(' ', '')
    schema_name = f"{clean_name}Input"
    
    # We create a new TypedDict class dynamically
    # total=False would make all keys optional, but we want to specify the *structure*.
    # LangGraph uses this to filter.
    return TypedDict(schema_name, fields)
