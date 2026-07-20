from typing import Dict, List, Tuple, Any, Optional
import math
from core.spatial_index import SpatialGridIndex
from utils.logger import logger

class Node:
    def __init__(self, node_id: str, x: float, y: float, elevation: float = 3810.0):
        self.id = node_id
        self.x = x
        self.y = y
        self.elevation = elevation
        self.pressure_mca: float = 0.0  # NUEVO: Atributo para guardar la presión base
        self.attributes: Dict[str, Any] = {}

class Edge:
    def __init__(self, source: str, target: str, length: float, name: str = "Tubería"):
        self.source = source
        self.target = target
        self.length = length
        self.name = name
        self.diameter_mm: float = 110.0
        self.material: str = "PVC"
        self.state: str = "OPERACIONAL"
        self.flow_rate_lps: float = 0.0
        self.pressure_psi: float = 30.0
        self.attributes: Dict[str, Any] = {}

class GeoGraph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.adjacency_list: Dict[str, List[Edge]] = {}
        self.spatial_index = SpatialGridIndex()
        self.reservoir_nodes: List[str] = []  # Lista de IDs de nodos que son reservorios
        self.critical_nodes: List[str] = []

    def clear(self):
        self.nodes.clear()
        self.adjacency_list.clear()
        self.spatial_index.clear()
        logger.info("Estructuras del Grafo Geoespacial reiniciadas por completo.")

    def add_node(self, node_id: str, x: float, y: float, elevation: float = 3810.0, **kwargs) -> bool:
        if node_id in self.nodes: return False
        node = Node(node_id, x, y, elevation)
        node.attributes.update(kwargs)
        self.nodes[node_id] = node
        self.adjacency_list[node_id] = []
        self.spatial_index.insert(node_id, x, y)
        return True

    def add_edge(self, source: str, target: str, name: str = "Tubería", bidirectional: bool = True) -> bool:
        if source not in self.nodes or target not in self.nodes: return False
        length = self._calculate_haversine(self.nodes[source], self.nodes[target])
        
        for existing_edge in self.adjacency_list[source]:
            if existing_edge.target == target: return False

        edge_forward = Edge(source, target, length, name)
        self.adjacency_list[source].append(edge_forward)

        if bidirectional:
            for existing_edge in self.adjacency_list[target]:
                if existing_edge.target == source: return False
            edge_backward = Edge(target, source, length, name)
            self.adjacency_list[target].append(edge_backward)
        return True

    def get_neighbors(self, node_id: str) -> List[Edge]:
        return self.adjacency_list.get(node_id, [])

    def find_nearest_node(self, x: float, y: float) -> Optional[str]:
        node_id, _ = self.spatial_index.find_nearest_node(x, y)
        return node_id

    def _calculate_haversine(self, node1: Node, node2: Node) -> float:
        R = 6371000.0
        lat1, lon1 = math.radians(node1.y), math.radians(node1.x)
        lat2, lon2 = math.radians(node2.y), math.radians(node2.x)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_summary(self) -> Tuple[int, int]:
        return len(self.nodes), sum(len(edges) for edges in self.adjacency_list.values())
    
    def add_reservoir(self, node_id: str) -> bool:
        """Marcar un nodo como reservorio"""
        if node_id not in self.nodes:
            logger.warning(f"Intento de marcar como reservorio un nodo inexistente: {node_id}")
            return False
        if node_id not in self.reservoir_nodes:
            self.reservoir_nodes.append(node_id)
            logger.info(f"Nodo {node_id} marcado como reservorio")
        return True
    
    def is_reservoir(self, node_id: str) -> bool:
        """Verificar si un nodo es reservorio"""
        return node_id in self.reservoir_nodes
    
    def set_reservoirs(self, node_ids: List[str]) -> None:
        """Establecer múltiples nodos como reservorios"""
        self.reservoir_nodes = [nid for nid in node_ids if nid in self.nodes]
        logger.info(f"Se establecieron {len(self.reservoir_nodes)} reservorios")