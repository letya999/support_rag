import logging
import sys
from pythonjsonlogger import jsonlogger

# Define the logger
logger = logging.getLogger("support_rag")

def setup_logging():
    """Setup structured JSON logging."""
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Create JSON formatter
    # Field names can be customized here
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    
    handler.setFormatter(formatter)
    
    # Basic configuration
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    
    # Set levels for specific loggers if needed
    logger.setLevel(logging.INFO)
    
    # Prevent propagation to avoid double logging if root logger is used
    logger.propagate = False
    logger.addHandler(handler)

    # Silence some noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    # Test logging
    setup_logging()
    logger.info("Structured logging initialized", extra={"test": True})
