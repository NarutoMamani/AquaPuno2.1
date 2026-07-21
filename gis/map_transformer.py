# CREAR
import pandas as pd
from shapely.geometry import Point, LineString
from typing import Dict, Any, List
from core.graph import GeoGraph
from utils.logger import logger

class MapTransformer:
    """
    Componente encargado de parsear la respuesta JSON de OpenStreetMap, resolver
    la topología de aristas/nodos y poblar de forma transparente el grafo del sistema.
    """
    @staticmethod
    def populate_graph_from_osm(osm_data: Dict[str, Any], graph: GeoGraph) -> bool:
        if not osm_data or "elements" not in osm_data:
            logger.error("No hay datos válidos de OSM para transformar.")
            return False

        graph.clear()
        elements = osm_data["elements"]

        # Separar elementos usando diccionarios estructurados e indexados rápidos
        osm_nodes: Dict[int, Dict[str, Any]] = {}
        osm_ways: List[Dict[str, Any]] = []

        for elem in elements:
            elem_type = elem.get("type")
            if elem_type == "node":
                osm_nodes[elem["id"]] = elem
            elif elem_type == "way":
                osm_ways.append(elem)

        logger.info(f"Iniciando indexación de {len(osm_nodes)} nodos y {len(osm_ways)} vías urbanas...")

        # Fase 1: Inyectar nodos al Grafo si pertenecen a alguna calle procesada
        # Para ahorrar memoria y procesamiento, solo guardamos nodos que forman calles
        referenced_node_ids = set()
        for way in osm_ways:
            referenced_node_ids.update(way.get("nodes", []))

        nodes_inserted = 0
        for node_id in referenced_node_ids:
            if node_id in osm_nodes:
                node_data = osm_nodes[node_id]
                lon = node_data["lon"]
                lat = node_data["lat"]
                
                # Nivel de elevación base promedio de Puno (3810 msnm) de forma nativa temporal
                # hasta la fase de simulación hidráulica avanzada
                graph.add_node(
                    node_id=str(node_id),
                    x=lon,
                    y=lat,
                    elevation=3810.0 + (lat * 10.0) # Variación sintética topográfica controlada
                )
                nodes_inserted += 1

        # Fase 2: Construir aristas secuenciales conectando las secuencias de nodos de las calles
        edges_inserted = 0
        for way in osm_ways:
            way_nodes = way.get("nodes", [])
            way_name = way.get("tags", {}).get("name", "Calle sin Nombre")
            
            # Recorrer la secuencia de nodos encadenados para formar aristas topológicas reales
            for i in range(len(way_nodes) - 1):
                source_id = str(way_nodes[i])
                target_id = str(way_nodes[i+1])
                
                # Validar la existencia de los extremos en el Grafo
                if source_id in graph.nodes and target_id in graph.nodes:
                    # Inyectar arista bidireccional (las tuberías de agua van en ambos sentidos)
                    if graph.add_edge(source_id, target_id, name=way_name, bidirectional=True):
                        edges_inserted += 1

        v_nodes, v_edges = graph.get_summary()
        logger.info(f"Transformación GIS Finalizada. Grafo Topológico Poblado -> Nodos: {v_nodes}, Aristas Totales: {v_edges}")
        
        graph.assign_sectors()
        return True