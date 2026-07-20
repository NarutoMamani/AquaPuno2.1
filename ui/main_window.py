import os
import sys
import random  # Necesario para simular los sensores
import threading
import math
import customtkinter as ctk
from ui.map_canvas import MapCanvasWidget
from algorithms.pathfinding import PathfindingEngine
from algorithms.mst import MSTEngine
from algorithms.backtracking import BacktrackingEngine
from core.graph import GeoGraph
from gis.nominatim_client import NominatimClient
from utils.logger import logger


class MainWindow(ctk.CTk):
    def __init__(self, spatial_graph):
        super().__init__()
        self.spatial_graph = spatial_graph
        self.current_mst = []

        self.sensor_data = {}
        self.critical_nodes = []
        self.leak_active = False
        self.leak_red_nodes = []
        self.leak_orange_nodes = []
        self.leak_response_routes = []
        self.leak_reroute = []
        self.pathfinding_routes = []
        self.backtracking_routes = []
        self._leak_cx = None
        self._leak_cy = None
        self._leak_radius = None
        self._is_running = True
        self.after_ids = []  # Rastrear IDs de callbacks para limpiarlos al cerrar
        
        # Inicializar cliente de Nominatim para obtener direcciones
        self.nominatim_client = NominatimClient()

        self.title("AquaPuno SCADA Control Room - v5.0")
        self.geometry("1200x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._build_ui()
        logger.info("Lanzando Interfaz SCADA Operacional - AquaPuno [Versión 5.0]")

        self.protocol("WM_DELETE_WINDOW", self.on_close_window)

        self._schedule(500, self.initialize_map_rendering)
        self._schedule(3000, self.simulate_sensor_telemetry)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.title_label = ctk.CTkLabel(
            self.sidebar,
            text="AQUAPUNO SMARTWATER",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#00F0FF",
        )
        self.title_label.pack(pady=(20, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar,
            text="Consola de Instrumentación v5.0",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="#888888",
        )
        self.subtitle_label.pack(pady=(0, 20))

        self.frame_path = ctk.CTkFrame(self.sidebar)
        self.frame_path.pack(fill=ctk.X, padx=10, pady=10)

        ctk.CTkLabel(
            self.frame_path,
            text="[ Control de Flujo Óptimo ]",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00F0FF",
        ).pack(anchor="w", padx=10, pady=5)

        self.btn_simulate = ctk.CTkButton(
            self.frame_path,
            text="Calcular Ruta y Válvulas de Seccionamiento",
            command=self.run_pathfinding_simulation,
        )
        self.btn_simulate.pack(fill=ctk.X, padx=10, pady=10)

        self.btn_backtracking = ctk.CTkButton(
            self.frame_path,
            text="Calcular Rutas Alternativas",
            command=self.run_backtracking_simulation,
        )
        self.btn_backtracking.pack(fill=ctk.X, padx=10, pady=(0, 10))

        self.frame_valves = ctk.CTkFrame(self.frame_path)
        self.frame_valves.pack(fill=ctk.X, padx=10, pady=(0, 10))

        ctk.CTkLabel(
            self.frame_valves,
            text="[ Válvulas de Seccionamiento ]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFD700",
        ).pack(anchor="w", padx=10, pady=(5, 0))

        self.valves_textbox = ctk.CTkTextbox(
            self.frame_valves,
            height=120,
            font=ctk.CTkFont(family="monospace", size=10),
            fg_color="#050505",
            text_color="#00FF66",
        )
        self.valves_textbox.pack(fill=ctk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.valves_textbox.insert(ctk.END, "Ejecute el algoritmo para ver las válvulas recomendadas...")

        self.frame_mst = ctk.CTkFrame(self.sidebar)
        self.frame_mst.pack(fill=ctk.X, padx=10, pady=10)

        ctk.CTkLabel(
            self.frame_mst,
            text="[ Gestión Estructural Estática ]",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00FF66",
        ).pack(anchor="w", padx=10, pady=5)

        self.btn_mst = ctk.CTkButton(
            self.frame_mst,
            text="Trazar Red Troncal Principal",
            command=self.toggle_mst_display,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
        )
        self.btn_mst.pack(fill=ctk.X, padx=10, pady=10)

        self.frame_mst_stats = ctk.CTkFrame(self.frame_mst)
        self.frame_mst_stats.pack(fill=ctk.X, padx=10, pady=(0, 10))

        ctk.CTkLabel(
            self.frame_mst_stats,
            text="[ Estadísticas Troncal ]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#00E5FF",
        ).pack(anchor="w", padx=10, pady=(5, 0))

        self.label_mst_edges = ctk.CTkLabel(
            self.frame_mst_stats,
            text="Aristas: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_mst_edges.pack(anchor="w", padx=10, pady=2)

        self.label_mst_length = ctk.CTkLabel(
            self.frame_mst_stats,
            text="Longitud total: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_mst_length.pack(anchor="w", padx=10, pady=2)

        self.label_mst_nodes = ctk.CTkLabel(
            self.frame_mst_stats,
            text="Nodos conectados: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_mst_nodes.pack(anchor="w", padx=10, pady=2)

        self.label_mst_reservoirs = ctk.CTkLabel(
            self.frame_mst_stats,
            text="Reservorios incluidos: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_mst_reservoirs.pack(anchor="w", padx=10, pady=(2, 10))

        self.btn_leak = ctk.CTkButton(
            self.frame_mst,
            text="Simular Fuga",
            command=self.toggle_leak_simulation,
            fg_color="#B71C1C",
            hover_color="#7F0000",
        )
        self.btn_leak.pack(fill=ctk.X, padx=10, pady=(0, 10))

        self.btn_pdf = ctk.CTkButton(
            self.frame_mst,
            text="Exportar Reporte PDF",
            command=self.export_scada_pdf_report,
            fg_color="#A9007F",
            hover_color="#7A005B",
        )
        self.btn_pdf.pack(fill=ctk.X, padx=10, pady=(0, 10))

        # Marco de información del nodo seleccionado
        self.frame_node_info = ctk.CTkFrame(self.sidebar)
        self.frame_node_info.pack(fill=ctk.X, padx=10, pady=10)

        ctk.CTkLabel(
            self.frame_node_info,
            text="[ Información del Nodo ]",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00FFFF",
        ).pack(anchor="w", padx=10, pady=5)

        self.label_node_id = ctk.CTkLabel(
            self.frame_node_info,
            text="ID: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_node_id.pack(anchor="w", padx=10, pady=2)

        self.label_node_coords = ctk.CTkLabel(
            self.frame_node_info,
            text="Coords: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_node_coords.pack(anchor="w", padx=10, pady=2)

        self.label_node_location = ctk.CTkLabel(
            self.frame_node_info,
            text="📍 Ubicación: Cargando...",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#FFD700",
            wraplength=270,
            justify="left"
        )
        self.label_node_location.pack(anchor="w", padx=10, pady=3)

        self.label_node_type = ctk.CTkLabel(
            self.frame_node_info,
            text="Tipo: Nodo Normal",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#00E5FF",
        )
        self.label_node_type.pack(anchor="w", padx=10, pady=2)

        self.label_node_pressure = ctk.CTkLabel(
            self.frame_node_info,
            text="Presión: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_node_pressure.pack(anchor="w", padx=10, pady=2)

        self.label_node_flow = ctk.CTkLabel(
            self.frame_node_info,
            text="Caudal: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_node_flow.pack(anchor="w", padx=10, pady=2)

        self.label_node_estado = ctk.CTkLabel(
            self.frame_node_info,
            text="Estado: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_node_estado.pack(anchor="w", padx=10, pady=2)

        self.label_node_elevation = ctk.CTkLabel(
            self.frame_node_info,
            text="Elevación: --",
            font=ctk.CTkFont(size=10),
            text_color="#FFFFFF",
        )
        self.label_node_elevation.pack(anchor="w", padx=10, pady=(2, 10))

        self.log_textbox = ctk.CTkTextbox(
            self.sidebar,
            height=150,
            font=ctk.CTkFont(family="monospace", size=10),
            fg_color="#050505",
            text_color="#00FF66",
        )
        self.log_textbox.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)
        self.write_scada_log("Sistema Listo. Monitoreando malla hídrica de Puno...")

        self.canvas_frame = ctk.CTkFrame(self, fg_color="#151515")
        self.canvas_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.map_widget = MapCanvasWidget(self.canvas_frame)
        self.map_widget.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

    def initialize_map_rendering(self):
        if not self._is_running:
            return
        if self.spatial_graph and self.map_widget:
            # Configurar el callback para la selección de nodos
            self.map_widget.set_node_selection_callback(self.on_node_selected)
            self._refresh_map_view()
            self.write_scada_log("Malla urbana de Puno renderizada correctamente en pantalla.")

    def _refresh_map_view(self):
        if self.map_widget:
            self.map_widget.draw_base_network(self.spatial_graph, pressure_data=self.sensor_data)
            if self.leak_active:
                self.map_widget.highlight_leak_nodes(
                    self.spatial_graph,
                    self.leak_red_nodes,
                    self.leak_orange_nodes,
                )
                for path in self.leak_response_routes:
                    if len(path) >= 2:
                        self.map_widget.highlight_path(self.spatial_graph, path, "Ruta de Intervención")
                for path in self.leak_reroute:
                    if len(path) >= 2:
                        self.map_widget.highlight_path(self.spatial_graph, path, "Ruta Alternativa")
            for path in self.pathfinding_routes:
                if len(path) >= 2:
                    self.map_widget.highlight_path(self.spatial_graph, path, "Camino Óptimo")
            if hasattr(self, 'backtracking_routes') and self.backtracking_routes:
                self.map_widget.highlight_alternative_paths(self.spatial_graph, self.backtracking_routes)
            if hasattr(self, 'valves_to_close') and self.valves_to_close:
                self.map_widget.highlight_close_valves(self.spatial_graph, self.valves_to_close)
            if self.current_mst:
                self.map_widget.highlight_mst(self.spatial_graph, self.current_mst)

    def on_node_selected(self, node_id: str, node, sensor_data):
        """Mostrar información del nodo seleccionado o limpiar si node_id es None"""
        if node_id is None:
            # Deseleccionar: limpiar toda la información
            self.label_node_id.configure(text="ID: --")
            self.label_node_coords.configure(text="Coords: --")
            self.label_node_elevation.configure(text="Elevación: --")
            self.label_node_pressure.configure(text="Presión: --")
            self.label_node_flow.configure(text="Caudal: --")
            self.label_node_estado.configure(text="Estado: --")
            self.label_node_location.configure(text="📍 Ubicación: --")
            self.label_node_type.configure(text="Tipo: --")
            self.write_scada_log("Deseleccionado")
            return
        
        # Mostrar información inmediata del nodo
        self.label_node_id.configure(text=f"ID: {node_id}")
        self.label_node_coords.configure(text=f"Coords: ({node.x:.6f}, {node.y:.6f})")
        self.label_node_elevation.configure(text=f"Elevación: {node.elevation:.2f} m")
        
        # Mostrar tipo de nodo (Reservorio o Normal)
        if self.spatial_graph.is_reservoir(node_id):
            self.label_node_type.configure(text="Tipo: 🌊 RESERVORIO (EMSAPUNO)", text_color="#00E5FF")
        else:
            self.label_node_type.configure(text="Tipo: Nodo de Distribución", text_color="#FFFFFF")
        
        # Mostrar información del sensor
        if sensor_data and node_id in sensor_data:
            data = sensor_data[node_id]
            presion = data.get("presion", "--")
            caudal = data.get("caudal", "--")
            estado = data.get("estado", "--")
            
            if presion is not None:
                # CAMBIADO DE PSI A MCA PARA ESTANDARIZAR
                self.label_node_pressure.configure(text=f"Presión: {presion} mca")
            else:
                self.label_node_pressure.configure(text="Presión: --")
            
            if caudal is not None:
                self.label_node_flow.configure(text=f"Caudal: {caudal} LPS")
            else:
                self.label_node_flow.configure(text="Caudal: --")
            
            estado_display = self._get_estado_display(estado)
            self.label_node_estado.configure(text=f"Estado: {estado_display}")
        else:
            self.label_node_pressure.configure(text="Presión: --")
            self.label_node_flow.configure(text="Caudal: --")
            self.label_node_estado.configure(text="Estado: --")
        
        # Mostrar "Cargando..." mientras se obtiene la dirección
        self.label_node_location.configure(text="📍 Ubicación: Cargando...")
        
        # Obtener dirección en un hilo separado para no bloquear la UI
        thread = threading.Thread(
            target=self._fetch_and_display_address,
            args=(node_id, node),
            daemon=True
        )
        thread.start()
        
        self.write_scada_log(f"✓ Nodo seleccionado: {node_id}")

    def _fetch_and_display_address(self, node_id: str, node):
        """Obtener dirección desde Nominatim en hilo separado"""
        try:
            # Nominatim usa (lat, lon) pero OSM usa (lon, lat), así que intercambiamos
            address_info = self.nominatim_client.get_address_from_coordinates(node.y, node.x)
            
            # Actualizar la UI de forma segura desde el hilo
            self._schedule(0, self._update_address_display, address_info)
            
        except Exception as e:
            logger.error(f"Error al obtener dirección: {str(e)}")
            self._schedule(0, self._update_address_display, None)

    def _update_address_display(self, address_info):
        """Actualizar los labels de dirección en el hilo principal"""
        if address_info is None:
            self.label_node_location.configure(text="📍 Ubicación: Error")
            return
        
        street = address_info.get('street', '--') or '--'
        suburb = address_info.get('suburb', '--') or '--'
        
        location_text = f"📍 {street}, {suburb}"
        self.label_node_location.configure(text=location_text)

    def _get_estado_display(self, estado):
        """Convertir estado a formato legible"""
        estado_map = {
            "baja": "Baja",
            "media": "Media",
            "regular": "Regular",
            "sin_marca": "Normal (Simulado)",
            "critica": "Crítica"
        }
        return estado_map.get(estado, estado)

    def simulate_sensor_telemetry(self):
        if not self._is_running:
            return

        node_ids = list(self.spatial_graph.nodes.keys())
        if not node_ids:
            self._schedule(10000, self.simulate_sensor_telemetry)
            return

        orange_nodes = list(node_ids[:10])
        red_nodes = list(node_ids[10:15])

        if len(node_ids) < 15:
            red_nodes = node_ids[-min(5, len(node_ids)):]
            orange_nodes = node_ids[:min(10, len(node_ids) - len(red_nodes))]

        self.critical_nodes = []
        self.sensor_data = {}

        self.write_scada_log("=== ESCANEO COMPLETO DE RED ===")
        self.write_scada_log(f"Evaluando {len(node_ids)} nodos de la red hidráulica...")

        for nid in node_ids:
            if self.leak_active and nid in self.leak_red_nodes:
                pressure = round(random.uniform(3.0, 8.0), 2)
                flow = round(random.uniform(2.0, 6.0), 2)
                self.sensor_data[nid] = {"presion": pressure, "caudal": flow, "estado": "critica"}
            elif self.leak_active and nid in self.leak_orange_nodes:
                pressure = round(random.uniform(10.0, 16.0), 2)
                flow = round(random.uniform(8.0, 12.0), 2)
                self.sensor_data[nid] = {"presion": pressure, "caudal": flow, "estado": "media"}
            elif nid in red_nodes:
                pressure = 10.0
                flow = 7.0
                self.sensor_data[nid] = {"presion": pressure, "caudal": flow, "estado": "baja"}
                self.critical_nodes.append(nid)

            elif nid in orange_nodes:
                pressure = 22.0
                flow = 14.0
                self.sensor_data[nid] = {"presion": pressure, "caudal": flow, "estado": "media"}

            else:
                # CAMBIADO: Usar la presión ideal que asignamos a cada nodo en main.py en lugar de None
                base_pressure = self.spatial_graph.nodes[nid].pressure_mca
                # El caudal puede ser fijo o nulo si no quieres mostrarlo
                self.sensor_data[nid] = {"presion": base_pressure, "caudal": "--", "estado": "sin_marca"}

        self._refresh_map_view()
        self.after(10000, self.simulate_sensor_telemetry)

    def _schedule(self, delay, callback, *args):
        """Programar un callback y rastrear su ID para limpiar después"""
        after_id = self.after(delay, callback, *args)
        self.after_ids.append(after_id)
        return after_id
    
    def _cancel_all_callbacks(self):
        """Cancelar todos los callbacks programados"""
        for after_id in self.after_ids:
            try:
                self.after_cancel(after_id)
            except:
                pass  # Ya se ejecutó o fue cancelado
        self.after_ids.clear()
    
    def on_close_window(self):
        self._is_running = False
        self._cancel_all_callbacks()
        self.destroy()

    def write_scada_log(self, text: str):
        if not self._is_running:
            return
        self.log_textbox.insert(ctk.END, f"> {text}\n")
        self.log_textbox.see(ctk.END)

    def run_pathfinding_simulation(self):
        if not self.spatial_graph:
            self.write_scada_log("No hay grafo cargado.")
            return

        reservoir_ids = list(self.spatial_graph.reservoir_nodes)
        if not reservoir_ids:
            self.write_scada_log("No hay reservorios definidos.")
            return

        self.pathfinding_routes = []
        self.valves_to_close = []

        if self.leak_active and self.leak_red_nodes:
            reservoir_id = self.leak_response_routes[0][0] if self.leak_response_routes else random.choice(reservoir_ids)
            targets = self.leak_red_nodes[:5]
            self.write_scada_log("=== CONTROL DE FLUJO AUTOMÁTICO (modo fuga) ===")
        else:
            reservoir_id = random.choice(reservoir_ids)
            safe_nodes = [nid for nid in self.spatial_graph.nodes.keys() if not self.spatial_graph.is_reservoir(nid)]
            random.shuffle(safe_nodes)
            targets = safe_nodes[:3]
            self.write_scada_log("=== CONTROL DE FLUJO AUTOMÁTICO ===")

        self.valves_textbox.delete("0.0", "end")
        self.valves_textbox.insert(ctk.END, f"Origen: {reservoir_id}\n")
        self.valves_textbox.insert(ctk.END, "="*40 + "\n")

        self.valves_to_close = []

        for idx, target in enumerate(targets, 1):
            path_d, _ = PathfindingEngine.dijkstra(self.spatial_graph, reservoir_id, target)
            path_a, _ = PathfindingEngine.a_star(self.spatial_graph, reservoir_id, target)
            chosen = path_d if path_d else path_a
            if chosen:
                self.pathfinding_routes.append(chosen)
                self.valves_textbox.insert(ctk.END, f"Ruta {idx} -> {target}\n")
                self.valves_textbox.insert(ctk.END, f"  Nodos: {len(chosen)}\n")
                for i, nid in enumerate(chosen):
                    state = "ABRIR" if i < len(chosen) - 1 else "DESTINO"
                    self.valves_textbox.insert(ctk.END, f"  [{state}] Válvula {nid}\n")
                self.valves_textbox.insert(ctk.END, "\n")
                self.write_scada_log(f"Ruta {idx} -> {target}: {len(chosen)} nodos")

                path_set = set(chosen)
                close_valves = []
                for nid in chosen:
                    if nid == reservoir_id or nid == target:
                        continue
                    for edge in self.spatial_graph.adjacency_list.get(nid, []):
                        neighbor = edge.target
                        if neighbor not in path_set:
                            close_valves.append(neighbor)
                close_valves = list(set(close_valves))
                self.valves_to_close.extend(close_valves)

                if close_valves:
                    self.valves_textbox.insert(ctk.END, f"  Válvulas a CERRAR en ruta {idx}:\n")
                    for cid in close_valves:
                        self.valves_textbox.insert(ctk.END, f"    [CERRAR] Válvula {cid}\n")
                    self.valves_textbox.insert(ctk.END, "\n")

        self.valves_textbox.insert(ctk.END, "="*40 + "\n")
        self.valves_textbox.insert(ctk.END, "RECOMENDACIÓN SCADA:\n")
        self.valves_textbox.insert(ctk.END, "- Abrir válvulas de la ruta principal al 100%\n")
        self.valves_textbox.insert(ctk.END, "- Cerrar válvulas laterales para evitar pérdidas\n")
        self.valves_textbox.insert(ctk.END, "- Monitorear presión en nodos intermedios\n")

        self._refresh_map_view()

    def run_backtracking_simulation(self):
        if not self.spatial_graph:
            self.write_scada_log("No hay grafo cargado.")
            return

        reservoir_ids = list(self.spatial_graph.reservoir_nodes)
        if not reservoir_ids:
            self.write_scada_log("No hay reservorios definidos.")
            return

        reservoir_id = random.choice(reservoir_ids)
        safe_nodes = [nid for nid in self.spatial_graph.nodes.keys() if not self.spatial_graph.is_reservoir(nid)]
        if not safe_nodes:
            self.write_scada_log("No hay nodos de demanda disponibles.")
            return

        random.shuffle(safe_nodes)
        targets = safe_nodes[:2]

        self.valves_textbox.delete("0.0", "end")
        self.valves_textbox.insert(ctk.END, f"Origen: {reservoir_id}\n")
        self.valves_textbox.insert(ctk.END, "="*40 + "\n")
        self.valves_textbox.insert(ctk.END, "Backtracking - Rutas Alternativas\n")
        self.valves_textbox.insert(ctk.END, "="*40 + "\n")

        self.backtracking_routes = []
        self.valves_to_close = []

        for idx, target in enumerate(targets, 1):
            paths, tel = BacktrackingEngine.find_alternative_routes(
                self.spatial_graph, reservoir_id, target, max_paths=3, max_depth=7
            )
            self.write_scada_log(f"Backtracking -> {target}: {len(paths)} rutas, {tel.nodes_visited_count} nodos visitados")
            self.valves_textbox.insert(ctk.END, f"Destino {idx}: {target}\n")
            self.valves_textbox.insert(ctk.END, f"  Rutas encontradas: {len(paths)}\n")

            for p_idx, path in enumerate(paths, 1):
                self.backtracking_routes.append(path)
                self.valves_textbox.insert(ctk.END, f"  Ruta {p_idx}: {' -> '.join(path)} ({len(path)} nodos)\n")

                path_set = set(path)
                close_valves = []
                for nid in path:
                    if nid == reservoir_id or nid == target:
                        continue
                    for edge in self.spatial_graph.adjacency_list.get(nid, []):
                        neighbor = edge.target
                        if neighbor not in path_set:
                            close_valves.append(neighbor)
                close_valves = list(set(close_valves))
                self.valves_to_close.extend(close_valves)

                if close_valves:
                    self.valves_textbox.insert(ctk.END, f"    Válvulas a CERRAR:\n")
                    for cid in close_valves:
                        self.valves_textbox.insert(ctk.END, f"      [CERRAR] Válvula {cid}\n")

            self.valves_textbox.insert(ctk.END, "\n")

        self.valves_textbox.insert(ctk.END, "="*40 + "\n")
        self.valves_textbox.insert(ctk.END, "RECOMENDACIÓN SCADA:\n")
        self.valves_textbox.insert(ctk.END, "- Usar estas rutas como alternativas redundantes\n")
        self.valves_textbox.insert(ctk.END, "- Cerrar válvulas laterales para evitar derrames\n")
        self.valves_textbox.insert(ctk.END, "- Monitorear presión en nodos intermedios\n")

        self._refresh_map_view()

    def _build_strategic_subgraph(self, graph):
        strategic_ids = set(graph.reservoir_nodes)
        if not strategic_ids:
            return graph

        for reservoir_id in list(strategic_ids):
            if reservoir_id not in graph.nodes:
                continue
            reservoir_node = graph.nodes[reservoir_id]
            candidates = []
            for nid, node in graph.nodes.items():
                if nid in strategic_ids:
                    continue
                dx = node.x - reservoir_node.x
                dy = node.y - reservoir_node.y
                candidates.append((math.hypot(dx, dy), nid))
            candidates.sort()
            for _, nid in candidates[:3]:
                strategic_ids.add(nid)

        extra = set()
        for nid in list(strategic_ids):
            for edge in graph.adjacency_list.get(nid, []):
                extra.add(edge.target)
        strategic_ids.update(extra)

        subgraph = GeoGraph()
        subgraph.nodes = {nid: graph.nodes[nid] for nid in strategic_ids if nid in graph.nodes}
        subgraph.reservoir_nodes = [nid for nid in graph.reservoir_nodes if nid in subgraph.nodes]
        for nid in strategic_ids:
            if nid not in graph.adjacency_list:
                continue
            for edge in graph.adjacency_list[nid]:
                if edge.target in strategic_ids:
                    subgraph.adjacency_list.setdefault(nid, []).append(edge)
        logger.info(f"Subgrafo estratégico: {len(subgraph.nodes)} nodos, {sum(len(v) for v in subgraph.adjacency_list.values())} aristas")
        return subgraph

    def _run_mst_logic(self):
        print("[DEBUG] _run_mst_logic called")
        subgraph = self._build_strategic_subgraph(self.spatial_graph)
        print(f"[DEBUG] subgraph nodes: {len(subgraph.nodes)}, aristas: {sum(len(v) for v in subgraph.adjacency_list.values())}")
        mst_edges, tel_mst = MSTEngine.kruskal(subgraph)
        print(f"[DEBUG] MST edges: {len(mst_edges)}")
        self.current_mst = mst_edges
        self.write_scada_log("=== TELEMETRÍA TRONCAL ===")
        self.write_scada_log(f"MST calculado con {len(mst_edges)} aristas.")

        total_length = 0.0
        mst_node_ids = set()
        mst_reservoir_count = 0
        for u, v, weight in mst_edges:
            total_length += weight
            mst_node_ids.add(u)
            mst_node_ids.add(v)
            if self.spatial_graph.is_reservoir(u) or self.spatial_graph.is_reservoir(v):
                mst_reservoir_count += 1

        self.label_mst_edges.configure(text=f"Aristas: {len(mst_edges)}")
        self.label_mst_length.configure(text=f"Longitud total: {total_length:.2f} m")
        self.label_mst_nodes.configure(text=f"Nodos conectados: {len(mst_node_ids)}")
        self.label_mst_reservoirs.configure(text=f"Reservorios incluidos: {mst_reservoir_count}")

        if self.map_widget:
            self._refresh_map_view()

    def toggle_mst_display(self):
        print(f"[DEBUG] toggle_mst_display called, current_mst={len(self.current_mst) if self.current_mst else 0}")
        if not self.spatial_graph:
            self.write_scada_log("No hay grafo cargado.")
            return

        if self.current_mst:
            self.current_mst = []
            self.pathfinding_routes = []
            self.valves_to_close = []
            self.btn_mst.configure(
                text="Trazar Red Troncal Principal",
                fg_color="#2E7D32",
                hover_color="#1B5E20",
            )
            self.label_mst_edges.configure(text="Aristas: --")
            self.label_mst_length.configure(text="Longitud total: --")
            self.label_mst_nodes.configure(text="Nodos conectados: --")
            self.label_mst_reservoirs.configure(text="Reservorios incluidos: --")
            if self.map_widget:
                self._refresh_map_view()
            self.write_scada_log("Vista base restaurada.")
        else:
            self.btn_mst.configure(
                text="Restaurar Vista Base",
                fg_color="#37474F",
                hover_color="#263238",
            )
            self._run_mst_logic()

    def toggle_leak_simulation(self):
        if not self.spatial_graph:
            self.write_scada_log("No hay grafo cargado.")
            return

        if self.leak_active:
            self.leak_active = False
            self.leak_red_nodes = []
            self.leak_orange_nodes = []
            self.leak_response_routes = []
            self.leak_reroute = []
            self.valves_to_close = []
            self.btn_leak.configure(text="Simular Fuga", fg_color="#B71C1C", hover_color="#7F0000")
            if self.map_widget:
                self._refresh_map_view()
            self.write_scada_log("Simulación de fuga DESACTIVADA. Vista normal.")
        else:
            node_ids = list(self.spatial_graph.nodes.keys())
            if len(node_ids) < 5:
                self.write_scada_log("No hay suficientes nodos para simular fuga.")
                return

            xs = [self.spatial_graph.nodes[nid].x for nid in node_ids]
            ys = [self.spatial_graph.nodes[nid].y for nid in node_ids]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            range_x = max_x - min_x
            range_y = max_y - min_y
            max_range = max(range_x, range_y)

            reservoir_ids = list(self.spatial_graph.reservoir_nodes)
            if not reservoir_ids:
                self.write_scada_log("No hay reservorios definidos en el grafo.")
                return

            reservoir_id = random.choice(reservoir_ids)
            reservoir_node = self.spatial_graph.nodes[reservoir_id]
            cx, cy = reservoir_node.x, reservoir_node.y

            radius = max_range * 0.35
            self._leak_cx = cx
            self._leak_cy = cy
            self._leak_radius = radius
            queue = __import__('collections').deque([(reservoir_id, 0)])
            visited = {reservoir_id}
            nearby_connected = []
            depth_map = {}

            while queue:
                nid, depth = queue.popleft()
                if depth > 0:
                    dx = self.spatial_graph.nodes[nid].x - cx
                    dy = self.spatial_graph.nodes[nid].y - cy
                    if math.hypot(dx, dy) <= radius:
                        nearby_connected.append(nid)
                        depth_map[nid] = depth
                if depth >= 5:
                    continue
                for edge in self.spatial_graph.adjacency_list.get(nid, []):
                    neighbor = edge.target
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

            nearby_connected = [nid for nid in nearby_connected if not self.spatial_graph.is_reservoir(nid)]

            if len(nearby_connected) < 3:
                self.write_scada_log("No hay suficientes nodos conectados cercanos al reservorio seleccionado.")
                return

            nearby_with_dist = []
            for nid in nearby_connected:
                dx = self.spatial_graph.nodes[nid].x - cx
                dy = self.spatial_graph.nodes[nid].y - cy
                nearby_with_dist.append((math.hypot(dx, dy), nid))
            nearby_with_dist.sort()

            close_nodes = [nid for _, nid in nearby_with_dist[:len(nearby_with_dist)//2]]
            far_nodes = [nid for _, nid in nearby_with_dist[len(nearby_with_dist)//2:]]

            n_orange = max(4, len(close_nodes) // 2)
            n_red = max(3, len(far_nodes) // 2)
            self.leak_orange_nodes = close_nodes[:n_orange]
            self.leak_red_nodes = far_nodes[:n_red]
            self.leak_active = True
            self.btn_leak.configure(text="Desactivar Fuga", fg_color="#FF9800", hover_color="#E65100")
            self.write_scada_log("=== SIMULACIÓN DE FUGA ACTIVADA ===")
            self.write_scada_log(f"Reservorio asociado: {reservoir_id}")
            self.write_scada_log(f"Nodos en fuga crítica (ROJO): {len(self.leak_red_nodes)}")
            self.write_scada_log(f"Nodos en fuga media (NARANJA): {len(self.leak_orange_nodes)}")

            for nid in self.leak_red_nodes:
                self.sensor_data[nid] = {
                    "presion": round(random.uniform(2.0, 6.0), 2),
                    "caudal": round(random.uniform(1.0, 5.0), 2),
                    "estado": "critica"
                }
            for nid in self.leak_orange_nodes:
                self.sensor_data[nid] = {
                    "presion": round(random.uniform(8.0, 14.0), 2),
                    "caudal": round(random.uniform(6.0, 11.0), 2),
                    "estado": "media"
                }

            self.leak_response_routes = []
            self.leak_reroute = []

            original_critical = list(self.spatial_graph.critical_nodes)
            self.spatial_graph.critical_nodes = list(set(original_critical + self.leak_red_nodes + self.leak_orange_nodes))

            try:
                safe_nodes = [nid for nid in list(self.spatial_graph.nodes.keys())
                              if nid not in self.leak_red_nodes and nid not in self.leak_orange_nodes
                              and not self.spatial_graph.is_reservoir(nid)]

                for target in self.leak_red_nodes[:10]:
                    path, _ = PathfindingEngine.dijkstra(self.spatial_graph, reservoir_id, target)
                    if path:
                        self.leak_response_routes.append(path)
                        self.write_scada_log(f"Ruta intervención -> {target}: {len(path)} nodos")

                if safe_nodes:
                    random.shuffle(safe_nodes)
                    reroute_targets = safe_nodes[:min(8, len(safe_nodes))]
                    for target in reroute_targets:
                        path, _ = PathfindingEngine.dijkstra(self.spatial_graph, reservoir_id, target)
                        if path:
                            self.leak_reroute.append(path)
                            self.write_scada_log(f"Ruta alternativa -> {target}: {len(path)} nodos")
            finally:
                self.spatial_graph.critical_nodes = original_critical

        self._refresh_map_view()

    def export_scada_pdf_report(self):
        try:
            from weasyprint import HTML
        except ImportError:
            self.write_scada_log("Error: weasyprint no está instalado. Ejecute: pip install weasyprint")
            return

        timestamp = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        leak_section = ""
        if self.leak_active:
            leak_section = f"""
            <h2>Simulación de Fuga Activa</h2>
            <p><strong>Reservorio asociado:</strong> {self.leak_response_routes[0][0] if self.leak_response_routes else 'N/A'}</p>
            <p><strong>Nodos en fuga crítica (ROJO):</strong> {len(self.leak_red_nodes)}</p>
            <p><strong>Nodos en fuga media (NARANJA):</strong> {len(self.leak_orange_nodes)}</p>
            <h3>Presión y Caudal en Nodos Afectados</h3>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><th>Nodo</th><th>Presión (mca)</th><th>Caudal (L/s)</th><th>Estado</th></tr>
            """
            for nid in self.leak_red_nodes:
                data = self.sensor_data.get(nid, {})
                leak_section += f"<tr><td>{nid}</td><td>{data.get('presion', 'N/A')}</td><td>{data.get('caudal', 'N/A')}</td><td>Crítica</td></tr>"
            for nid in self.leak_orange_nodes:
                data = self.sensor_data.get(nid, {})
                leak_section += f"<tr><td>{nid}</td><td>{data.get('presion', 'N/A')}</td><td>{data.get('caudal', 'N/A')}</td><td>Media</td></tr>"
            leak_section += "</table>"

            if self.leak_response_routes:
                leak_section += "<h3>Rutas de Intervención</h3><ul>"
                for path in self.leak_response_routes:
                    leak_section += f"<li>Ruta: {' -> '.join(path)} ({len(path)} nodos)</li>"
                leak_section += "</ul>"

            if self.leak_reroute:
                leak_section += "<h3>Rutas Alternativas</h3><ul>"
                for path in self.leak_reroute:
                    leak_section += f"<li>Ruta: {' -> '.join(path)} ({len(path)} nodos)</li>"
                leak_section += "</ul>"

            if hasattr(self, 'valves_to_close') and self.valves_to_close:
                leak_section += "<h3>Válvulas a Cerrar</h3><ul>"
                for vid in self.valves_to_close:
                    leak_section += f"<li>Válvula {vid}</li>"
                leak_section += "</ul>"

        mst_section = ""
        if self.current_mst:
            mst_section = f"""
            <h2>Red Troncal Principal (MST)</h2>
            <p><strong>Aristas:</strong> {self.label_mst_edges.cget('text').replace('Aristas: ', '')}</p>
            <p><strong>Longitud total:</strong> {self.label_mst_length.cget('text').replace('Longitud total: ', '')}</p>
            <p><strong>Nodos conectados:</strong> {self.label_mst_nodes.cget('text').replace('Nodos conectados: ', '')}</p>
            <p><strong>Reservorios incluidos:</strong> {self.label_mst_reservoirs.cget('text').replace('Reservorios incluidos: ', '')}</p>
            """

        pathfinding_section = ""
        if self.pathfinding_routes:
            pathfinding_section = "<h2>Control de Flujo Óptimo</h2><h3>Rutas Calculadas</h3><ul>"
            for path in self.pathfinding_routes:
                pathfinding_section += f"<li>Ruta: {' -> '.join(path)} ({len(path)} nodos)</li>"
            pathfinding_section += "</ul>"

            if hasattr(self, 'valves_to_close') and self.valves_to_close:
                pathfinding_section += "<h3>Válvulas a Cerrar</h3><ul>"
                for vid in self.valves_to_close:
                    pathfinding_section += f"<li>Válvula {vid}</li>"
                pathfinding_section += "</ul>"

        log_text = self.log_textbox.get("0.0", "end").strip()

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Reporte SCADA AquaPuno</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
                h1 {{ color: #0057B8; text-align: center; }}
                h2 {{ color: #0057B8; border-bottom: 2px solid #0057B8; padding-bottom: 5px; margin-top: 30px; }}
                h3 {{ color: #0077C8; margin-top: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background-color: #0057B8; color: white; }}
                td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .footer {{ margin-top: 50px; font-size: 12px; color: #777; text-align: center; }}
                .log-box {{ background-color: #f8f8f8; border: 1px solid #ccc; padding: 10px; font-family: monospace; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }}
            </style>
        </head>
        <body>
            <h1>Reporte SCADA AquaPuno</h1>
            <p><strong>Fecha y hora:</strong> {timestamp}</p>
            <p><strong>Nodos totales:</strong> {len(self.spatial_graph.nodes)}</p>
            <p><strong>Aristas totales:</strong> {sum(len(v) for v in self.spatial_graph.adjacency_list.values())}</p>
            <p><strong>Reservorios:</strong> {len(self.spatial_graph.reservoir_nodes)}</p>

            {leak_section}
            {mst_section}
            {pathfinding_section}

            <h2>Log del Sistema SCADA</h2>
            <div class="log-box">{log_text}</div>

            <div class="footer">Reporte generado automáticamente por AquaPuno SCADA v5.0</div>
        </body>
        </html>
        """

        output_path = __import__('os').path.join(__import__('os').getcwd(), "reporte_scada_aquapuno.pdf")
        HTML(string=html_content).write_pdf(output_path)
        self.write_scada_log(f"Reporte PDF generado exitosamente: {output_path}")