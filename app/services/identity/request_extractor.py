import time
from typing import Dict, Any
from fastapi import Request

class RequestMetadataExtractor:
    """
    Helper to extract technical fingerprints from HTTP requests.
    """

    @staticmethod
    def extract(request: Request) -> Dict[str, Any]:
        """
        Extracts IP, Headers, and other fingerprints from the raw request.
        """
        return {
            "network": {
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent"),
                "accept_language": request.headers.get("accept-language"),
                "x_forwarded_for": request.headers.get("x-forwarded-for"),
                "port": request.client.port if request.client else None
            },
            "server_time": time.time(),
            "headers_fingerprint": hash(str(dict(request.headers))) # Simple hash of standard headers
        }
