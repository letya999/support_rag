import logging

class PipelineLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(f"pipeline.{name}")
        # Ensure it has a handler if not configured elsewhere, or assume root logger is configured.
        # For now, we rely on the application's logging config.
    
    def log_node_added(self, node_name: str):
        self.logger.debug(f"✓ Node added: {node_name}")
    
    def log_edge_added(self, from_node: str, to_node: str):
        self.logger.debug(f"✓ Edge: {from_node} → {to_node}")
    
    def log_conditional_edge_added(self, from_node: str, condition_name: str, path_map: dict):
        self.logger.debug(f"✓ Conditional Edge: {from_node} --({condition_name})--> {path_map}")
    
    def log_validation_result(self, success: bool, message: str):
        if success:
            self.logger.info(f"✓ {message}")
        else:
            self.logger.warning(f"✗ {message}")
    
    def log_config_loaded(self, node_count: int):
        self.logger.info(f"Loaded {node_count} nodes from config")
    
    def debug(self, message: str):
        self.logger.debug(message)

    def warning(self, message: str):
        self.logger.warning(message)

# Global instance to be used by graph builder
pipeline_logger = PipelineLogger("builder")
