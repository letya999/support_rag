"""
DEPRECATED: app/cache/session_manager.py

This file has been moved to app/services/cache/session.py

This stub exists only for backward compatibility.
Please update your imports to use:
    from app.services.cache.session import SessionManager
"""

import warnings

warnings.warn(
    "Importing from app.cache.session_manager is deprecated. "
    "Use 'from app.services.cache.session import SessionManager' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.services.cache.session import SessionManager

__all__ = ["SessionManager"]
