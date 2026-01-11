from pathlib import Path
from typing import Dict, List
import yaml

class NodeRegistry:
    EXCLUDED_DIRS = ["base_node", "__pycache__"]
    
    def __init__(self, nodes_dir: str = "app/nodes"):
        self.nodes_dir = Path(nodes_dir)
        self._nodes = self._discover_nodes()
    
    def _discover_nodes(self) -> Dict[str, dict]:
        """Auto-discover all nodes in app/nodes/ where config.yaml exists"""
        nodes = {}
        if not self.nodes_dir.exists():
            return nodes

        for node_path in self.nodes_dir.iterdir():
            if not node_path.is_dir():
                continue
            if node_path.name in self.EXCLUDED_DIRS:
                continue
            
            config_file = node_path / "config.yaml"
            if config_file.exists():
                try:
                    with open(config_file, encoding="utf-8") as f:
                        config = yaml.safe_load(f) or {}
                        nodes[node_path.name] = config
                except Exception as e:
                    print(f"⚠️ Error loading config for node {node_path.name}: {e}")
        return nodes
    
    def get_node_config(self, node_name: str) -> dict:
        return self._nodes.get(node_name, {})
    
    def get_all_nodes(self) -> List[str]:
        return list(self._nodes.keys())
    
    def is_node_enabled(self, node_name: str) -> bool:
        config = self.get_node_config(node_name)
        # Check 'node' key -> 'enabled'
        node_section = config.get("node", {})
        return node_section.get("enabled", False)

    def refresh(self):
        self._nodes = self._discover_nodes()

# Global instance
node_registry = NodeRegistry()
