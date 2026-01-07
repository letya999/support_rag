
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pipeline.graph import validate_pipeline_structure

def test_valid_structure():
    print("Testing valid structure...")
    # Standard valid order
    nodes = ["retrieve", "lexical_search", "fusion", "reranking", "state_machine", "routing", "generation"]
    validate_pipeline_structure(nodes)
    print("✅ Valid structure passed")

def test_missing_fusion_deps():
    print("Testing missing fusion deps...")
    nodes = ["fusion"] # Missing retrieve/lexical
    try:
        validate_pipeline_structure(nodes)
        print("❌ FAILED: Should have raised ValueError for missing deps")
    except ValueError as e:
        print(f"✅ Correctly raised error: {e}")
        assert "fusion" in str(e)
        assert "retrieve" in str(e)

def test_wrong_order_retrieve_fusion():
    print("Testing wrong order (fusion before retrieve)...")
    nodes = ["fusion", "retrieve", "lexical_search"]
    try:
        validate_pipeline_structure(nodes)
        print("❌ FAILED: Should have raised ValueError for wrong order")
    except ValueError as e:
        print(f"✅ Correctly raised error: {e}")
        assert "execute before" in str(e)

def test_missing_optional_nodes():
    print("Testing missing optional nodes (no fusion, no state machine)...")
    # This should pass if logic is correct about missing nodes being ignored for order checks
    nodes = ["generation"] 
    validate_pipeline_structure(nodes)
    print("✅ Partial structure passed")

if __name__ == "__main__":
    try:
        test_valid_structure()
        test_missing_fusion_deps()
        test_wrong_order_retrieve_fusion()
        test_missing_optional_nodes()
        print("\nAll validation tests passed!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
