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
        self.sector_map: Dict[str, str] = {}  # Nodo -> Reservorio asignado
        self.sector_graphs: Dict[str, 'GeoGraph'] = {}  # Reservorio ID -> Subgrafo del sector

    def clear(self):
        self.nodes.clear()
        self.adjacency_list.clear()
        self.spatial_index.clear()
        self.reservoir_nodes = []
        self.critical_nodes = []
        self.sector_map = {}
        self.sector_graphs = {}
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

    def assign_sectors(self):
        """Asigna cada nodo a un sector según BFS desde cada reservorio (Zona de influencia)."""
        if not self.reservoir_nodes:
            logger.warning("Sin reservorios definidos para sectorizar.")
            return
        
        sectors = {rid: set([rid]) for rid in self.reservoir_nodes}
        assigned = dict(sectors)
        unassigned = set(self.nodes.keys()) - set(self.reservoir_nodes)
        
        from collections import deque
        queues = {rid: deque(list(assigned[rid])) for rid in self.reservoir_nodes}
        visited = {rid: set(assigned[rid]) for rid in self.reservoir_nodes}
        
        while unassigned:
            assigned_this_round = False
            for rid in self.reservoir_nodes:
                if not queues[rid]:
                    continue
                nid = queues[rid].popleft()
                for edge in self.adjacency_list.get(nid, []):
                    neighbor = edge.target
                    if neighbor in unassigned and neighbor not in visited[rid]:
                        visited[rid].add(neighbor)
                        queues[rid].append(neighbor)
                        assigned[neighbor] = rid
                        sectors[rid].add(neighbor)
                        unassigned.discard(neighbor)
                        assigned_this_round = True
            if not assigned_this_round:
                break
        
        self.sector_map = assigned
        
        for rid, node_set in sectors.items():
            subgraph = GeoGraph()
            subgraph.nodes = {nid: self.nodes[nid] for nid in node_set if nid in self.nodes}
            subgraph.reservoir_nodes = [rid] if rid in subgraph.nodes else []
            subgraph.spatial_index = SpatialGridIndex()
            for nid in subgraph.nodes:
                subgraph.spatial_index.insert(nid, subgraph.nodes[nid].x, subgraph.nodes[nid].y)
            for nid in node_set:
                if nid in self.adjacency_list:
                    for edge in self.adjacency_list[nid]:
                        if edge.target in node_set:
                            subgraph.adjacency_list.setdefault(nid, []).append(edge)
            self.sector_graphs[rid] = subgraph
        
        logger.info(f"Sectorización completada: {len(self.sector_graphs)} sectores, "
                    f"{sum(len(g.nodes) for g in self.sector_graphs.values())} nodos sectorizados.")

    def isolate_sectors(self):
        """Elimina aristas entre nodos de sectores diferentes, aislando cada región."""
        if not self.sector_map:
            logger.warning("No se puede aislar sectores sin sector_map.")
            return
        
        removed = 0
        kept = 0
        new_adj = {}
        for nid, edges in self.adjacency_list.items():
            sector = self.sector_map.get(nid)
            if not sector:
                new_adj[nid] = []
                continue
            filtered = []
            for edge in edges:
                neighbor_sector = self.sector_map.get(edge.target)
                if neighbor_sector == sector:
                    filtered.append(edge)
                    kept += 1
                else:
                    removed += 1
            new_adj[nid] = filtered
        
        self.adjacency_list = new_adj
        self.spatial_index.clear()
        for nid, node in self.nodes.items():
            self.spatial_index.insert(nid, node.x, node.y)
        
        logger.info(f"Aislamiento de sectores aplicado. Aristas eliminadas: {removed}, aristas internas mantenidas: {kept}.")

    def get_sector_for_node(self, node_id: str) -> Optional[str]:
        """Devuelve el ID del reservorio al que pertenece un nodo."""
        return self.sector_map.get(node_id)

    def get_sector_nodes(self, reservoir_id: str) -> List[str]:
        """Devuelve los nodos del sector de un reservorio, incluyendo el reservorio."""
        return list(self.sector_graphs.get(reservoir_id, {}).nodes.keys())

    def get_trunk_graph(self) -> 'GeoGraph':
        """Construye el grafo de la red troncal: nodos = reservorios, aristas = mínimas aristas entre sectores."""
        if len(self.reservoir_nodes) < 2:
            return GeoGraph()
        # Usar Dijkstra entre cada par de reservorios para encontrar el camino mínimo global
        # Luego tomar el MST de reservorios sobre esos caminos
        from algorithms.pathfinding import PathfindingEngine
        trunk = GeoGraph()
        trunk.reservoir_nodes = list(self.reservoir_nodes)
        
        # Calcular matrices de distancia entre reservorios
        for rid in self.reservoir_nodes:
            trunk.add_node(rid, self.nodes[rid].x, self.nodes[rid].y, self.nodes[rid].elevation)
        
        # Encontrar el nodo "puente" más cercano entre cada par de reservorios
        for i in range(len(self.reservoir_nodes)):
            for j in range(i + 1, len(self.reservoir_nodes)):
                r1 = self.reservoir_nodes[i]
                r2 = self.reservoir_nodes[j]
                path, _ = PathfindingEngine.dijkstra(self, r1, r2)
                if path and len(path) > 2:
                    # Conectar reservorios a través del nodo intermedio de menor índice
                    bridge_node = path[1]
                    if bridge_node not in trunk.nodes:
                        trunk.add_node(bridge_node, self.nodes[bridge_node].x, 
                                     self.nodes[bridge_node].y, self.nodes[bridge_node].elevation)
                    trunk.add_edge(r1, bridge_node, name="Troncal", bidirectional=False)
                    trunk.add_edge(bridge_node, r2, name="Troncal", bidirectional=False)
                elif path and len(path) == 2:
                    trunk.add_edge(r1, r2, name="Troncal", bidirectional=True)
        
        return trunk