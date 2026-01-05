"""
Metrics for Input Guardrails Node

Tracks security-related metrics:
- Blocked requests count
- Risk score distribution
- Scanner trigger frequency
- Performance metrics
"""
from typing import Dict, Any, List
from app.nodes.base_node.metrics.base_metric import BaseMetric


class GuardrailsMetric(BaseMetric):
    """
    Metrics for guardrails node.
    
    Tracks:
    - Total requests processed
    - Blocked requests count
    - Risk score distribution
    - Scanner trigger frequency
    - Average latency
    """
    
    def calculate(self, expected: Any, actual: Any, **kwargs) -> Any:
        """
        Calculate metric comparing expected and actual values.
        For guardrails, compares if blocking decision was correct.
        """
        # Expected: should be blocked (True/False)
        # Actual: was blocked (True/False)
        return 1.0 if expected == actual else 0.0
    
    def __init__(self):
        super().__init__()
        
        # Counters
        self.total_requests = 0
        self.blocked_requests = 0
        self.sanitized_requests = 0
        self.safe_requests = 0
        
        # Risk scores
        self.risk_scores = []
        
        # Scanner triggers
        self.scanner_triggers = {
            "regex_patterns": 0,
            "token_limit": 0,
            "language": 0,
            "secrets": 0,
            "prompt_injection": 0,
            "toxicity": 0,
            "ban_topics": 0
        }
        
        # Latency tracking
        self.latencies = []
    
    def record(self, state: Dict[str, Any]):
        """
        Record metrics from state.
        
        Expected state fields:
        - guardrails_blocked: bool
        - guardrails_sanitized: bool
        - guardrails_risk_score: float
        - guardrails_triggered: List[str]
        """
        self.total_requests += 1
        
        # Count outcomes
        if state.get("guardrails_blocked"):
            self.blocked_requests += 1
        elif state.get("guardrails_sanitized"):
            self.sanitized_requests += 1
        else:
            self.safe_requests += 1
        
        # Record risk score
        risk_score = state.get("guardrails_risk_score", 0.0)
        self.risk_scores.append(risk_score)
        
        # Record triggered scanners
        triggered = state.get("guardrails_triggered", [])
        for scanner in triggered:
            if scanner in self.scanner_triggers:
                self.scanner_triggers[scanner] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics.
        
        Returns:
            Dict with all tracked metrics
        """
        if self.total_requests == 0:
            return {
                "total_requests": 0,
                "blocked_rate": 0.0,
                "avg_risk_score": 0.0
            }
        
        # Calculate rates
        blocked_rate = self.blocked_requests / self.total_requests
        sanitized_rate = self.sanitized_requests / self.total_requests
        safe_rate = self.safe_requests / self.total_requests
        
        # Calculate average risk score
        avg_risk_score = sum(self.risk_scores) / len(self.risk_scores) if self.risk_scores else 0.0
        
        # Calculate max risk score
        max_risk_score = max(self.risk_scores) if self.risk_scores else 0.0
        
        # Find most triggered scanner
        most_triggered = max(self.scanner_triggers.items(), key=lambda x: x[1]) if any(self.scanner_triggers.values()) else ("none", 0)
        
        return {
            "total_requests": self.total_requests,
            "blocked_requests": self.blocked_requests,
            "sanitized_requests": self.sanitized_requests,
            "safe_requests": self.safe_requests,
            "blocked_rate": blocked_rate,
            "sanitized_rate": sanitized_rate,
            "safe_rate": safe_rate,
            "avg_risk_score": avg_risk_score,
            "max_risk_score": max_risk_score,
            "scanner_triggers": self.scanner_triggers,
            "most_triggered_scanner": most_triggered[0],
            "most_triggered_count": most_triggered[1]
        }
    
    def reset(self):
        """Reset all metrics"""
        self.total_requests = 0
        self.blocked_requests = 0
        self.sanitized_requests = 0
        self.safe_requests = 0
        self.risk_scores = []
        self.scanner_triggers = {k: 0 for k in self.scanner_triggers}
        self.latencies = []
