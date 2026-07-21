import sys
import random
from core.graph import GeoGraph
from gis.osm_client import OverpassClient
from gis.map_transformer import MapTransformer
from ui.main_window import MainWindow
from utils.logger import logger

def start_scada_application():
    spatial_graph = GeoGraph()
    puno_center_bbox = (-15.8450, -70.0350, -15.8320, -70.0200)
    
    osm_client = OverpassClient()
    raw_osm_data = osm_client.fetch_puno_roads(puno_center_bbox)
    
    if raw_osm_data:
        MapTransformer.populate_graph_from_osm(raw_osm_data, spatial_graph)
    
    node_ids = list(spatial_graph.nodes.keys())
    if len(node_ids) >= 17:
        xs = [spatial_graph.nodes[nid].x for nid in node_ids]
        ys = [spatial_graph.nodes[nid].y for nid in node_ids]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        cols, rows = 5, 4
        cell_w = (max_x - min_x) / cols
        cell_h = (max_y - min_y) / rows

        reservoir_ids = []
        for r in range(rows):
            for c in range(cols):
                if len(reservoir_ids) >= 17:
                    break
                cx = min_x + (c + 0.5) * cell_w
                cy = min_y + (r + 0.5) * cell_h

                best_nid = None
                best_dist = float('inf')
                for nid in node_ids:
                    if nid in reservoir_ids:
                        continue
                    dx = spatial_graph.nodes[nid].x - cx
                    dy = spatial_graph.nodes[nid].y - cy
                    dist = dx * dx + dy * dy
                    if dist < best_dist:
                        best_dist = dist
                        best_nid = nid

                if best_nid is not None:
                    reservoir_ids.append(best_nid)

        spatial_graph.set_reservoirs(reservoir_ids)
        logger.info(f"✓ Se asignaron {len(reservoir_ids)} reservorios estratégicos en cuadrícula {cols}x{rows}")
        print(f"[MAIN] Nodos tras set_reservoirs: {len(spatial_graph.nodes)}")
        
        spatial_graph.assign_sectors()
        print(f"[MAIN] Nodos tras assign_sectors: {len(spatial_graph.nodes)}")
        print(f"[MAIN] Sectores creados: {len(spatial_graph.sector_graphs)}")
        
        spatial_graph.isolate_sectors()
        print(f"[MAIN] Nodos tras isolate_sectors: {len(spatial_graph.nodes)}")
        print(f"[MAIN] Aristas totales post-aislamiento: {sum(len(v) for v in spatial_graph.adjacency_list.values())}")
        
        trunk_graph = spatial_graph.get_trunk_graph()
        print(f"[MAIN] Trunk nodes={len(trunk_graph.nodes)}, trunk edges={sum(len(v) for v in trunk_graph.adjacency_list.values())}")
        
        try:
            import json
            import os
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            sector_payload = {
                "reservoir_nodes": spatial_graph.reservoir_nodes,
                "sector_count": len(spatial_graph.sector_graphs),
                "sectors": {}
            }
            for rid, sg in spatial_graph.sector_graphs.items():
                sector_payload["sectors"][rid] = {
                    "nodes": list(sg.nodes.keys()),
                    "edges": []
                }
                for nid, edges in sg.adjacency_list.items():
                    for edge in edges:
                        sector_payload["sectors"][rid]["edges"].append({
                            "source": edge.source,
                            "target": edge.target,
                            "length": edge.length,
                            "name": edge.name,
                        })
            
            trunk_payload = {
                "reservoir_nodes": trunk_graph.reservoir_nodes,
                "nodes": {nid: {"x": node.x, "y": node.y, "elevation": node.elevation} for nid, node in trunk_graph.nodes.items()},
                "edges": []
            }
            for nid, edges in trunk_graph.adjacency_list.items():
                for edge in edges:
                    trunk_payload["edges"].append({
                        "source": edge.source,
                        "target": edge.target,
                        "length": edge.length,
                        "name": edge.name,
                    })
            
            with open(os.path.join(base_dir, "sectorized_network.json"), "w", encoding="utf-8") as f:
                json.dump(sector_payload, f, indent=2, ensure_ascii=False)
            
            with open(os.path.join(base_dir, "trunk_network.json"), "w", encoding="utf-8") as f:
                json.dump(trunk_payload, f, indent=2, ensure_ascii=False)
            
            logger.info("Modelo sectorizado y troncal guardados en disco.")
        except Exception as e:
            logger.warning(f"No se pudo guardar el modelo sectorizado: {e}")
        
        logger.info(f"Red troncal sectorizada lista. Sectores: {len(spatial_graph.sector_graphs)}, "
                    f"Nodos troncal: {len(trunk_graph.nodes)}, Aristas troncal: {sum(len(v) for v in trunk_graph.adjacency_list.values())}")
    else:
        logger.warning(f"Solo se encontraron {len(node_ids)} nodos, se esperaban al menos 17 reservorios")
        if node_ids:
            spatial_graph.set_reservoirs(node_ids[:max(1, len(node_ids)//10)])
    
    for node_obj in spatial_graph.nodes.values():
        node_obj.pressure_mca = round(random.uniform(15.0, 50.0), 2)
    
    app = MainWindow(spatial_graph)
    
    app.mainloop()

if __name__ == "__main__":
    start_scada_application()
