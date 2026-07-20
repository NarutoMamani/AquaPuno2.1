# CREAR
import time
from typing import List, Dict, Tuple
from core.graph import GeoGraph, Edge
from algorithms.base_algorithm import AlgorithmTelemetry
from utils.logger import logger

class DisjointSet:
    """
    Estructura Union-Find optimizada con compresión de caminos y unión por rango.
    Evita la formación de ciclos durante la construcción del MST.
    """
    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def make_set(self, node_id: str):
        self.parent[node_id] = node_id
        self.rank[node_id] = 0

    def find(self, node_id: str) -> str:
        # Compresión de caminos recursiva
        if self.parent[node_id] != node_id:
            self.parent[node_id] = self.find(self.parent[node_id])
        return self.parent[node_id]

    def union(self, node_x: str, node_y: str) -> bool:
        root_x = self.find(node_x)
        root_y = self.find(node_y)

        if root_x == root_y:
            return False  # Ya pertenecen al mismo conjunto (detectado potencial ciclo)

        # Unión por rango
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
        return True


class MSTEngine:
    """
    Motor encargado de calcular la red troncal óptima de distribución de agua
    utilizando el algoritmo de Kruskal.
    """
    @staticmethod
    def kruskal(graph: GeoGraph) -> Tuple[List[Tuple[str, str, float]], AlgorithmTelemetry]:
        """
        Genera el Árbol de Expansión Mínima (MST).
        Complejidad Temporal: O(E log E) debido al ordenamiento de las aristas.
        """
        telemetry = AlgorithmTelemetry("Kruskal MST")
        telemetry.complexity_theoretical = "O(E log E)"
        
        start_time = time.perf_counter()
        mst_edges: List[Tuple[str, str, float]] = []
        
        # 1. Extraer y filtrar todas las aristas únicas del grafo (evitar duplicados simétricos)
        unique_edges: List[Tuple[float, str, str]] = []
        seen_pairs = set()
        
        for source_id, node_edges in graph.adjacency_list.items():
            for edge in node_edges:
                if edge.state in ["ROTURA", "MANTENIMIENTO"]:
                    continue
                # Emparejamiento ordenado para identificar el par único no dirigido
                pair = tuple(sorted([source_id, edge.target]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    unique_edges.append((edge.length, source_id, edge.target))

        # 2. Ordenar las aristas de manera ascendente según su longitud
        unique_edges.sort(key=lambda x: x[0])
        
        # 3. Inicializar la estructura DisjointSet para todos los nodos
        ds = DisjointSet()
        for node_id in graph.nodes:
            ds.make_set(node_id)

        # 4. Procesar y conectar aristas
        for length, u, v in unique_edges:
            telemetry.record_step("EVALUATE", (u, v))
            
            # Si no forman un ciclo, se consolida la arista en la troncal
            if ds.union(u, v):
                mst_edges.append((u, v, length))
                telemetry.total_path_cost += length
                telemetry.nodes_visited_count += 1
                telemetry.record_step("ADD_TO_MST", (u, v))
                
                # Criterio de parada temprana: MST completo si aristas == V - 1
                if len(mst_edges) == len(graph.nodes) - 1:
                    break

        telemetry.execution_time_ms = (time.perf_counter() - start_time) * 1000.0
        return mst_edges, telemetry