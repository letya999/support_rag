
import sys
try:
    import langfuse
    print(f"Langfuse version: {getattr(langfuse, '__version__', 'unknown')}")
except ImportError:
    print("Could not import langfuse")
    sys.exit(1)

try:
    from langfuse.callback import CallbackHandler
    print("Successfully imported CallbackHandler from langfuse.callback")
except ImportError as e:
    print(f"Error importing from langfuse.callback: {e}")

try:
    from langfuse import CallbackHandler
    print("Successfully imported CallbackHandler from langfuse")
except ImportError as e:
    print(f"Error importing from langfuse: {e}")
    
import dir
print(dir(langfuse))
