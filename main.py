import sys
import random
from core.graph import GeoGraph
from gis.osm_client import OverpassClient
from gis.map_transformer import MapTransformer
from ui.main_window import MainWindow
from utils.logger import logger

def start_scada_application():
    # 1. Instanciar el contenedor del grafo espacial
    spatial_graph = GeoGraph()
    puno_center_bbox = (-15.8450, -70.0350, -15.8320, -70.0200)
    
    # 2. Descargar y poblar la topología urbana de Puno
    osm_client = OverpassClient()
    raw_osm_data = osm_client.fetch_puno_roads(puno_center_bbox)
    
    if raw_osm_data:
        MapTransformer.populate_graph_from_osm(raw_osm_data, spatial_graph)
    
    # 3. Asignar 17 reservorios en posiciones estratégicas distribuidas por toda la ciudad
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
    else:
        logger.warning(f"Solo se encontraron {len(node_ids)} nodos, se esperaban al menos 17 reservorios")
    
    # =====================================================================
    # NUEVO: Asignar presión aleatoria ideal (15 a 50 mca) a todos los nodos
    # =====================================================================
    for node_obj in spatial_graph.nodes.values():
        node_obj.pressure_mca = round(random.uniform(15.0, 50.0), 2)
    # =====================================================================
    
    # 4. Inicializar la interfaz pasando el grafo como argumento
    app = MainWindow(spatial_graph)
    
    app.mainloop()

if __name__ == "__main__":
    start_scada_application()