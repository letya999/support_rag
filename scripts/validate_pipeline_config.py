#!/usr/bin/env python3
"""
Validate that pipeline_config.yaml is correctly generated and all required parameters are present.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.config_loader.loader import load_pipeline_config, get_node_params
from app.pipeline.config_proxy import conversation_config

def validate_config():
    """Validate the generated pipeline config."""
    print("🔍 Validating pipeline_config.yaml...")
    
    # 1. Test loading
    try:
        config = load_pipeline_config()
        print("✅ pipeline_config.yaml loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load pipeline_config.yaml: {e}")
        return False
    
    # 2. Check structure
    if "pipeline" not in config:
        print("❌ Missing 'pipeline' section")
        return False
    print(f"✅ Pipeline section found ({len(config['pipeline'])} nodes)")
    
    if "details" not in config:
        print("❌ Missing 'details' section")
        return False
    print(f"✅ Details section found ({len(config['details'])} entries)")
    
    # 3. Test node params access
    required_nodes = {
        "routing": ["min_confidence_auto_reply", "clarification_enabled", "always_escalate_categories"],
        "aggregation": ["history_messages_count", "mode"],
        "generation": ["max_tokens", "temperature"],
        "reranking": ["top_k", "confidence_threshold"]
    }
    
    for node_name, params in required_nodes.items():
        node_params = get_node_params(node_name)
        if not node_params:
            print(f"⚠️  Warning: {node_name} has no parameters")
            continue
        
        for param in params:
            if param in node_params:
                print(f"  ✅ {node_name}.{param} = {node_params[param]}")
            else:
                print(f"  ❌ {node_name}.{param} is MISSING")
                return False
    
    # 4. Test config_proxy access
    print("\n🔍 Testing config_proxy...")
    try:
        _ = conversation_config.clarification_enabled
        print(f"  ✅ clarification_enabled = {conversation_config.clarification_enabled}")
        
        _ = conversation_config.clarification_confidence_range
        print(f"  ✅ clarification_confidence_range = {conversation_config.clarification_confidence_range}")
        
        _ = conversation_config.always_escalate_categories
        print(f"  ✅ always_escalate_categories = {conversation_config.always_escalate_categories}")
        
        _ = conversation_config.always_escalate_intents
        print(f"  ✅ always_escalate_intents = {conversation_config.always_escalate_intents}")
        
    except Exception as e:
        print(f"  ❌ config_proxy error: {e}")
        return False
    
    print("\n✅ All validation checks passed!")
    return True

if __name__ == "__main__":
    success = validate_config()
    sys.exit(0 if success else 1)
