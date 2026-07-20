import time
from typing import List, Tuple, Optional
from core.graph import GeoGraph
from algorithms.base_algorithm import AlgorithmTelemetry


class BacktrackingEngine:
    """
    Backtracking limitado para enumerar rutas simples entre dos nodos.
    Se usa para proponer rutas alternativas de seccionamiento.
    """

    @staticmethod
    def find_alternative_routes(
        graph: GeoGraph,
        start_node: str,
        end_node: str,
        max_paths: int = 5,
        max_depth: int = 8,
    ) -> Tuple[List[List[str]], AlgorithmTelemetry]:
        telemetry = AlgorithmTelemetry("Backtracking Alternativas")
        telemetry.complexity_theoretical = "Peor caso O(V!) con límite de profundidad"
        start_time = time.perf_counter()

        results: List[List[str]] = []
        visited = set()
        path = [start_node]
        visited.add(start_node)

        critical_nodes = getattr(graph, 'critical_nodes', [])

        def dfs(current: str, depth: int) -> None:
            telemetry.nodes_visited_count += 1
            telemetry.record_step("VISIT", current)

            if len(results) >= max_paths:
                return

            if current == end_node:
                results.append(list(path))
                return

            if depth >= max_depth:
                return

            for edge in graph.get_neighbors(current):
                if edge.state in ["ROTURA", "MANTENIMIENTO"]:
                    continue
                if edge.target in critical_nodes:
                    continue
                if edge.target in visited:
                    continue

                visited.add(edge.target)
                path.append(edge.target)
                telemetry.record_step("PUSH", edge.target)

                dfs(edge.target, depth + 1)

                path.pop()
                visited.remove(edge.target)
                telemetry.record_step("POP", edge.target)

        dfs(start_node, 0)
        telemetry.execution_time_ms = (time.perf_counter() - start_time) * 1000.0
        return results, telemetry
