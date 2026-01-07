from langfuse.langchain import CallbackHandler

def get_langfuse_callback_handler(**kwargs) -> CallbackHandler:
    """
    Get Langchain/LangGraph callback handler.
    """
    return CallbackHandler(**kwargs)
