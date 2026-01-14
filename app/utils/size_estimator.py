from typing import Any

def estimate_size(obj: Any, visited: set = None) -> int:
    """Fast size estimation of an object without full serialization."""
    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return 0
    visited.add(obj_id)

    if isinstance(obj, str):
        return len(obj)
    elif isinstance(obj, (int, float, bool, type(None))):
        return 8
    elif isinstance(obj, (list, tuple)):
        return sum(estimate_size(item, visited) for item in obj)
    elif isinstance(obj, dict):
        return sum(estimate_size(k, visited) + estimate_size(v, visited)
                   for k, v in obj.items())
    elif hasattr(obj, '__dict__'):
        return estimate_size(obj.__dict__, visited)
    else:
        return len(str(obj))
