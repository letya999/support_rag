
import sys
import pkg_resources

try:
    dist = pkg_resources.get_distribution("langfuse")
    print(f"Langfuse version: {dist.version}")
    print(f"Location: {dist.location}")
except Exception as e:
    print(f"Could not check langfuse version: {e}")

try:
    import langfuse
    print("Successfully imported langfuse")
    print(f"Dir(langfuse): {dir(langfuse)}")
except ImportError:
    print("Could not import langfuse")

try:
    import langfuse.callback
    print("Successfully imported langfuse.callback")
except ImportError as e:
    print(f"Failed to import langfuse.callback: {e}")

try:
    from langfuse.callback import CallbackHandler
    print("Successfully imported CallbackHandler")
except ImportError:
    print("Failed to import CallbackHandler")
