from langfuse.langchain import CallbackHandler

def get_langfuse_callback_handler() -> CallbackHandler:
    """
    Get Langchain/LangGraph callback handler.
    """
    return CallbackHandler()
