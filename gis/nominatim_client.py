import requests
import time
from utils.logger import logger
from functools import lru_cache

class NominatimClient:
    """Cliente para obtener información de direcciones usando Nominatim (OpenStreetMap)"""
    
    BASE_URL = "https://nominatim.openstreetmap.org/reverse"
    MIN_REQUEST_INTERVAL = 1.0  # Nominatim requiere al menos 1 segundo entre requests
    last_request_time = 0
    
    def __init__(self):
        self.cache = {}  # Caché local para evitar requests repetidos
        self.headers = {
            'User-Agent': 'AquaPuno SCADA (github.com/aquapuno)'
        }
    
    def get_address_from_coordinates(self, lat: float, lon: float) -> dict:
        """
        Obtener información de dirección desde coordenadas.
        
        Args:
            lat: Latitud
            lon: Longitud
            
        Returns:
            dict con address, street, suburb, city, district, postcode
        """
        # Verificar caché primero
        cache_key = f"{lat:.6f}_{lon:.6f}"
        if cache_key in self.cache:
            logger.debug(f"Caché hit para ({lat:.6f}, {lon:.6f})")
            return self.cache[cache_key]
        
        try:
            # Respetar el límite de rate
            current_time = time.time()
            time_since_last = current_time - NominatimClient.last_request_time
            
            if time_since_last < self.MIN_REQUEST_INTERVAL:
                sleep_time = self.MIN_REQUEST_INTERVAL - time_since_last
                time.sleep(sleep_time)
            
            NominatimClient.last_request_time = time.time()
            
            # Hacer la request a Nominatim
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'zoom': 18,
                'addressdetails': 1
            }
            
            logger.debug(f"Consultando Nominatim para ({lat:.6f}, {lon:.6f})")
            response = requests.get(self.BASE_URL, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Respuesta de Nominatim: {data.get('address', {})}")
            
            # Extraer información de direcciones
            address_data = data.get('address', {})
            
            result = {
                'address': data.get('display_name', 'Desconocido'),
                'street': address_data.get('road', address_data.get('highway', '')),
                'suburb': address_data.get('suburb', address_data.get('neighbourhood', '')),
                'city': address_data.get('city', address_data.get('town', 'Puno')),
                'district': address_data.get('county', address_data.get('district', '')),
                'postcode': address_data.get('postcode', ''),
                'country': address_data.get('country', '')
            }
            
            # Guardar en caché
            self.cache[cache_key] = result
            logger.info(f"✓ Obtenida dirección: {result.get('street', '--')} - {result.get('suburb', '--')}")
            
            return result
            
        except requests.exceptions.Timeout:
            logger.warning(f"Nominatim timeout para ({lat:.6f}, {lon:.6f})")
            return self._get_empty_address()
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Nominatim conexión fallida: {str(e)}")
            return self._get_empty_address()
        except Exception as e:
            logger.error(f"Error en Nominatim: {type(e).__name__}: {str(e)}")
            return self._get_empty_address()
    
    def _get_empty_address(self) -> dict:
        """Retornar estructura vacía cuando hay error"""
        return {
            'address': 'No disponible',
            'street': '--',
            'suburb': '--',
            'city': 'Puno',
            'district': '--',
            'postcode': '--',
            'country': 'Perú'
        }
    
    def clear_cache(self):
        """Limpiar caché local"""
        self.cache.clear()
        logger.info("Caché de Nominatim limpiado")
