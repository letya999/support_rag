import os
from dotenv import load_dotenv

load_dotenv()

# Default confidence threshold for routing
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("DEFAULT_CONFIDENCE_THRESHOLD", "0.7"))
