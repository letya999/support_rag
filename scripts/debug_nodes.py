import sys
import os
import traceback

sys.path.append(os.getcwd())

nodes = [
    "app.nodes.session_starter.node",
    "app.nodes.check_cache.node",
    "app.nodes.language_detection.node",
    "app.nodes.dialog_analysis.node",
    "app.nodes.state_machine.node",
    "app.nodes.aggregation.node",
    "app.nodes.query_translation.node",
    "app.nodes.lexical_search.node",
    "app.nodes.hybrid_search.node",
    # Correct path for cache nodes (they are in app.cache.nodes)
    # "app.nodes.store_in_cache.node", # INCORRECT
]

# Manual check for cache nodes
print("Testing app.cache.nodes...", end=" ")
try:
    import app.cache.nodes
    print("✅ OK")
except:
    print("❌ FAIL")
    traceback.print_exc()

for node_module in nodes:
    print(f"Testing {node_module}...", end=" ")
    try:
        __import__(node_module)
        print("✅ OK")
    except Exception as e:
        print("❌ FAIL")
        traceback.print_exc()
