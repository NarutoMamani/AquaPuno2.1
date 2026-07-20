# REEMPLAZAR COMPLETAMENTE EL ARCHIVO
from typing import Dict, Any, Optional, Tuple
import urllib.request
import urllib.parse
import urllib.error
import json
import random
import time
from utils.logger import logger

class OverpassClient:
    """
    Cliente de red síncrono para interactuar con la API Overpass de OpenStreetMap.
    Incluye un motor Fallback para simular topología local ante caídas de servidor (HTTP 504).
    Incluye reintentos automáticos y mejor manejo de errores de conexión.
    """
    def __init__(self, timeout: int = 60, retries: int = 3):
        self.endpoint = "https://overpass-api.de/api/interpreter"
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = 2  # segundos entre reintentos

    def fetch_puno_roads(self, bbox: Tuple[float, float, float, float]) -> Optional[Dict[str, Any]]:
        """
        Descarga las calles transitables del BBOX provisto. Si el servidor remoto falla o
        da Timeout, genera automáticamente una topología de respaldo para no detener la app.
        Incluye reintentos automáticos en caso de fallo temporal.
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        
        query = f"""
        [out:json][timeout:{self.timeout}];
        (
          way["highway"~"primary|secondary|tertiary|residential|service|living_street"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        logger.info(f"Conectando con Overpass API. Descargando topología para BBOX: {bbox}...")
        logger.info(f"Timeout establecido: {self.timeout}s | Reintentos: {self.retries}")
        
        for attempt in range(self.retries):
            try:
                data = urllib.parse.urlencode({'data': query}).encode('utf-8')
                req = urllib.request.Request(
                    self.endpoint, 
                    data=data, 
                    headers={'User-Agent': 'AquaPunoSmartWater_v2.0'}
                )
                
                logger.info(f"Intento {attempt + 1}/{self.retries} de conexión a Overpass API...")
                
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    if response.status == 200:
                        raw_json = json.loads(response.read().decode('utf-8'))
                        elements_count = len(raw_json.get('elements', []))
                        logger.info(f"✓ Descarga exitosa de OSM. Elementos recibidos: {elements_count}")
                        return raw_json
                    else:
                        logger.warning(f"Respuesta HTTP {response.status} de Overpass. Reintentando...")
                        if attempt < self.retries - 1:
                            time.sleep(self.retry_delay)
                        continue
                    
            except urllib.error.URLError as e:
                logger.warning(f"Error de conexión URLError: {str(e)}")
                if attempt < self.retries - 1:
                    logger.info(f"Reintentando en {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                continue
                
            except urllib.error.HTTPError as e:
                logger.warning(f"Error HTTP {e.code}: {str(e)}")
                if attempt < self.retries - 1:
                    logger.info(f"Reintentando en {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                continue
                
            except TimeoutError as e:
                logger.warning(f"Timeout en conexión a Overpass ({self.timeout}s): {str(e)}")
                if attempt < self.retries - 1:
                    logger.info(f"Reintentando en {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                continue
                
            except Exception as e:
                logger.warning(f"Error inesperado: {type(e).__name__}: {str(e)}")
                if attempt < self.retries - 1:
                    logger.info(f"Reintentando en {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                continue
        
        # Si todos los reintentos fallaron, usar fallback
        logger.warning("✗ Todos los intentos de conexión a Overpass fallaron. Activando plan de contingencia local...")
        return self._generate_fallback_data(bbox)

    def _generate_fallback_data(self, bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
        """Genera una malla estructural de respaldo que imita calles céntricas de Puno."""
        min_lat, min_lon, max_lat, max_lon = bbox
        logger.info("Generando matriz topológica local de emergencia para el centro de Puno...")
        
        elements = []
        node_id_counter = 1000000
        way_id_counter = 5000000
        
        # Crear una rejilla virtual de 25 nodos (5x5) distribuidos uniformemente en el BBOX
        grid_size = 5
        grid_nodes = []
        
        lat_step = (max_lat - min_lat) / (grid_size - 1)
        lon_step = (max_lon - min_lon) / (grid_size - 1)
        
        for i in range(grid_size):
            row = []
            for j in range(grid_size):
                n_id = node_id_counter
                node_id_counter += 1
                lat = min_lat + (i * lat_step)
                lon = min_lon + (j * lon_step)
                
                elements.append({
                    "type": "node",
                    "id": n_id,
                    "lat": lat,
                    "lon": lon
                })
                row.append(n_id)
            grid_nodes.append(row)
            
        # Unir los nodos para formar calles (Ways) horizontales y verticales
        names = ["Jr. Lima", "Jr. Deustua", "Jr. Puno", "Jr. Arequipa", "Av. La Torre"]
        
        # Vías Horizontales
        for i in range(grid_size):
            elements.append({
                "type": "way",
                "id": way_id_counter,
                "nodes": grid_nodes[i],
                "tags": {"name": names[i % len(names)], "highway": "residential"}
            })
            way_id_counter += 1
            
        # Vías Verticales
        for j in range(grid_size):
            col_nodes = [grid_nodes[i][j] for i in range(grid_size)]
            elements.append({
                "type": "way",
                "id": way_id_counter,
                "nodes": col_nodes,
                "tags": {"name": f"Pasaje Longitudinal {j+1}", "highway": "residential"}
            })
            way_id_counter += 1
            
        logger.info(f"Mapeo de Contingencia completado: {len(elements)} elementos inyectados en memoria.")
        return {"elements": elements}