from typing import List
import numpy as np

class CalibrationMetrics:
    """
    Metrics to analyze how well the classifier's confidence matches its accuracy.
    """
    @staticmethod
    def calculate_gap(confidences: List[float], correct_flags: List[bool]) -> float:
        """
        Returns the gap between average confidence of correct vs incorrect predictions.
        Higher value means better calibration (more confident when right).
        """
        if not confidences or not any(correct_flags) or all(correct_flags):
            return 0.0
            
        conf_array = np.array(confidences)
        correct_array = np.array(correct_flags)
        
        avg_conf_correct = conf_array[correct_array].mean()
        avg_conf_incorrect = conf_array[~correct_array].mean()
        
        return float(avg_conf_correct - avg_conf_incorrect)
