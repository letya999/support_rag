"""
RAG Pipeline Graph Entry Point.

Constructs the LangGraph workflow using the builder.
"""
from app.pipeline.graph_builder import build_graph

# Compile the graph
rag_graph = build_graph()
