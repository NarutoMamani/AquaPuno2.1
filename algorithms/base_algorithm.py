# CREAR
from typing import List, Dict, Any, Tuple
import time

class AlgorithmTelemetry:
    """
    Contenedor de métricas y trazas para el análisis de complejidad, 
    evaluación de rendimiento y reproducción de animaciones en la interfaz SCADA.
    """
    def __init__(self, algorithm_name: str):
        self.algorithm_name: str = algorithm_name
        self.execution_time_ms: float = 0.0
        self.nodes_visited_count: int = 0
        self.total_path_cost: float = 0.0
        self.complexity_theoretical: str = "O(E * log V)"
        # Pasos detallados de la ejecución para renderizado diferido/animaciones
        # Formato: ("VISIT", node_id) o ("RELAX", source_id, target_id)
        self.steps_history: List[Tuple[str, Any]] = []

    def reset(self):
        self.execution_time_ms = 0.0
        self.nodes_visited_count = 0
        self.total_path_cost = 0.0
        self.steps_history.clear()

    def record_step(self, action_type: str, data: Any):
        self.steps_history.append((action_type, data))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm_name,
            "time_ms": self.execution_time_ms,
            "nodes_visited": self.nodes_visited_count,
            "cost_m": self.total_path_cost,
            "complexity": self.complexity_theoretical,
            "total_steps": len(self.steps_history)
        }