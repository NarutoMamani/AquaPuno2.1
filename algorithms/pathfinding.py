import heapq
import math
import time
from typing import List, Dict, Tuple, Optional
from core.graph import GeoGraph, Edge
from algorithms.base_algorithm import AlgorithmTelemetry
from utils.logger import logger

class PathfindingEngine:
    @staticmethod
    def _calculate_haversine_heuristic(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        R = 6371000.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

    @staticmethod
    def dijkstra(graph: GeoGraph, start_node: str, end_node: str) -> Tuple[List[str], AlgorithmTelemetry]:
        telemetry = AlgorithmTelemetry("Dijkstra")
        telemetry.complexity_theoretical = "O((E + V) log V)"
        
        if start_node not in graph.nodes or end_node not in graph.nodes:
            logger.error("Nodos origen o destino ausentes en el grafo de simulación.")
            return [], telemetry
            
        start_time = time.perf_counter()
        distances = {node_id: float('inf') for node_id in graph.nodes}
        predecessors = {node_id: None for node_id in graph.nodes}
        visited_nodes = set()
        distances[start_node] = 0.0
        pq = [(0.0, start_node)]
        
        # Recuperar nodos críticos inyectados por el sistema de telemetría SCADA
        critical_nodes = getattr(graph, 'critical_nodes', [])
        
        while pq:
            current_dist, current_node = heapq.heappop(pq)
            if current_node in visited_nodes:
                continue
                
            visited_nodes.add(current_node)
            telemetry.nodes_visited_count += 1
            telemetry.record_step("VISIT", current_node)
            
            if current_node == end_node:
                break
                
            if current_dist > distances[current_node]:
                continue
                
            for edge in graph.get_neighbors(current_node):
                # AISLAMIENTO SCADA: Omitir tuberías en rotura, mantenimiento o con presión crítica
                if edge.state in ["ROTURA", "MANTENIMIENTO"] or edge.target in critical_nodes:
                    continue
                    
                new_dist = current_dist + edge.length
                if new_dist < distances[edge.target]:
                    distances[edge.target] = new_dist
                    predecessors[edge.target] = current_node
                    heapq.heappush(pq, (new_dist, edge.target))
                    telemetry.record_step("RELAX", (current_node, edge.target))
                    
        path = []
        if distances[end_node] != float('inf'):
            curr = end_node
            while curr is not None:
                path.append(curr)
                curr = predecessors[curr]
            path.reverse()
            telemetry.total_path_cost = distances[end_node]
            
        telemetry.execution_time_ms = (time.perf_counter() - start_time) * 1000.0
        return path, telemetry

    @staticmethod
    def a_star(graph: GeoGraph, start_node: str, end_node: str) -> Tuple[List[str], AlgorithmTelemetry]:
        telemetry = AlgorithmTelemetry("A*")
        telemetry.complexity_theoretical = "O(E log V) promedio"
        
        if start_node not in graph.nodes or end_node not in graph.nodes:
            logger.error("Nodos origen o destino inválidos para cálculo con A*.")
            return [], telemetry
            
        start_time = time.perf_counter()
        target_node_obj = graph.nodes[end_node]
        g_scores = {node_id: float('inf') for node_id in graph.nodes}
        f_scores = {node_id: float('inf') for node_id in graph.nodes}
        predecessors = {node_id: None for node_id in graph.nodes}
        visited_nodes = set()
        
        g_scores[start_node] = 0.0
        h_start = PathfindingEngine._calculate_haversine_heuristic(
            graph.nodes[start_node].x, graph.nodes[start_node].y, 
            target_node_obj.x, target_node_obj.y
        )
        f_scores[start_node] = h_start
        pq = [(f_scores[start_node], start_node)]
        
        # Recuperar nodos críticos inyectados por el sistema de telemetría SCADA
        critical_nodes = getattr(graph, 'critical_nodes', [])
        
        while pq:
            _, current_node = heapq.heappop(pq)
            if current_node in visited_nodes:
                continue
                
            visited_nodes.add(current_node)
            telemetry.nodes_visited_count += 1
            telemetry.record_step("VISIT", current_node)
            
            if current_node == end_node:
                break
                
            for edge in graph.get_neighbors(current_node):
                # AISLAMIENTO SCADA: Omitir tuberías en rotura, mantenimiento o con presión crítica
                if edge.state in ["ROTURA", "MANTENIMIENTO"] or edge.target in critical_nodes:
                    continue
                    
                tentative_g_score = g_scores[current_node] + edge.length
                if tentative_g_score < g_scores[edge.target]:
                    predecessors[edge.target] = current_node
                    g_scores[edge.target] = tentative_g_score
                    h_score = PathfindingEngine._calculate_haversine_heuristic(
                        graph.nodes[edge.target].x, graph.nodes[edge.target].y, 
                        target_node_obj.x, target_node_obj.y
                    )
                    f_scores[edge.target] = tentative_g_score + h_score
                    heapq.heappush(pq, (f_scores[edge.target], edge.target))
                    telemetry.record_step("RELAX", (current_node, edge.target))
                    
        path = []
        if g_scores[end_node] != float('inf'):
            curr = end_node
            while curr is not None:
                path.append(curr)
                curr = predecessors[curr]
            path.reverse()
            telemetry.total_path_cost = g_scores[end_node]
            
        telemetry.execution_time_ms = (time.perf_counter() - start_time) * 1000.0
        return path, telemetry