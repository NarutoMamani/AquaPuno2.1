import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import math
from typing import List

from core.graph import GeoGraph
from utils.logger import logger


class MapCanvasWidget(ctk.CTkFrame):
    def __init__(self, master: any, **kwargs):
        super().__init__(master, **kwargs)

        plt.style.use("dark_background")
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.figure.patch.set_facecolor("#1A1A1A")
        self.ax.set_facecolor("#1A1A1A")

        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side=ctk.BOTTOM, fill=ctk.X)
        
        # Conectar el evento de clic
        self.canvas.mpl_connect('button_press_event', self._on_canvas_click)
        
        # Variables para gestionar la selección
        self.graph = None
        self.selected_node_id = None
        self.on_node_selected = None  # Callback para cuando se selecciona un nodo
        self.sensor_data = None
        self.highlight_scatter = None

    def set_node_selection_callback(self, callback):
        """Establecer el callback que se ejecuta cuando se selecciona un nodo"""
        self.on_node_selected = callback
    
    def _on_canvas_click(self, event):
        """Manejador de clics en el canvas"""
        if event.inaxes != self.ax or not self.graph:
            return
        
        # Obtener las coordenadas del clic
        click_x, click_y = event.xdata, event.ydata
        
        # Encontrar el nodo más cercano
        closest_node_id, distance = self._find_closest_node(click_x, click_y)
        
        # Calcular umbral dinámico basado en el rango visible del eje
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]
        avg_range = (x_range + y_range) / 2
        dynamic_threshold = avg_range * 0.005  # 0.5% del rango visible
        
        # Si está lo suficientemente cerca, seleccionar el nodo
        if closest_node_id and distance < dynamic_threshold:
            self.selected_node_id = closest_node_id
            # Solo redibuja el resaltado sin redibujar todo el mapa
            self._refresh_highlight_only()
            
            # Llamar al callback si existe
            if self.on_node_selected:
                node = self.graph.nodes[closest_node_id]
                self.on_node_selected(closest_node_id, node, self.sensor_data)
        else:
            # Si se hace clic en el vacío, deseleccionar
            self.selected_node_id = None
            # Solo redibuja el resaltado sin redibujar todo el mapa
            self._refresh_highlight_only()
            
            # Llamar al callback con None para indicar deselección
            if self.on_node_selected:
                self.on_node_selected(None, None, None)
    
    def _find_closest_node(self, click_x, click_y):
        """Encontrar el nodo más cercano al punto de clic"""
        if not self.graph or not self.graph.nodes:
            return None, float('inf')
        
        closest_node_id = None
        min_distance = float('inf')
        
        for node_id, node in self.graph.nodes.items():
            distance = math.sqrt((node.x - click_x)**2 + (node.y - click_y)**2)
            if distance < min_distance:
                min_distance = distance
                closest_node_id = node_id
        
        return closest_node_id, min_distance
    
    def _refresh_highlight_only(self):
        """Redibuja rápidamente solo la capa de resaltado sin tocar el resto del mapa"""
        if self.highlight_scatter is not None:
            self.highlight_scatter.remove()
            self.highlight_scatter = None
        
        # Redibujar el resaltado del nodo actual
        if self.selected_node_id and self.selected_node_id in self.graph.nodes:
            node = self.graph.nodes[self.selected_node_id]
            self.highlight_scatter = self.ax.scatter([node.x], [node.y], color="#00FF00", s=80, 
                           marker="o", edgecolors="white", linewidths=2.5, zorder=10)
        
        self.canvas.draw()
    
    def _highlight_selected_node(self):
        """Resaltar el nodo seleccionado en el mapa"""
        if not self.selected_node_id or not self.graph:
            return
        
        node = self.graph.nodes[self.selected_node_id]
        self.highlight_scatter = self.ax.scatter([node.x], [node.y], color="#00FF00", s=80, 
                       marker="o", edgecolors="white", linewidths=2.5, zorder=10)
        self.canvas.draw()

    def draw_base_network(self, graph: GeoGraph, pressure_data=None):
        # Guardar los límites actuales del eje (posición de la cámara/zoom)
        current_xlim = self.ax.get_xlim()
        current_ylim = self.ax.get_ylim()
        has_limits = not (current_xlim == (0, 1) and current_ylim == (0, 1))
        
        # Guardar referencias
        self.graph = graph
        self.sensor_data = pressure_data
        
        self.ax.clear()
        self.highlight_scatter = None
        self.ax.set_facecolor("#1A1A1A")

        processed_edges = set()
        for u, edges in graph.adjacency_list.items():
            node_u = graph.nodes[u]
            for edge in edges:
                pair = tuple(sorted([u, edge.target]))
                if pair in processed_edges:
                    continue
                processed_edges.add(pair)

                node_v = graph.nodes[edge.target]
                self.ax.plot(
                    [node_u.x, node_v.x],
                    [node_u.y, node_v.y],
                    color="#333333",
                    linewidth=0.8,
                    alpha=0.7,
                    zorder=1,
                )

        lons = [node.x for node in graph.nodes.values()]
        lats = [node.y for node in graph.nodes.values()]
        self.ax.scatter(lons, lats, color="#00F0FF", s=1.5, alpha=0.5, zorder=2)
        
        # Pintar reservorios en celeste más grande
        if graph.reservoir_nodes:
            reservoir_lons = [graph.nodes[nid].x for nid in graph.reservoir_nodes if nid in graph.nodes]
            reservoir_lats = [graph.nodes[nid].y for nid in graph.reservoir_nodes if nid in graph.nodes]
            
            if reservoir_lons:
                self.ax.scatter(
                    reservoir_lons,
                    reservoir_lats,
                    color="#00E5FF",
                    s=45,
                    marker="s",
                    edgecolors="white",
                    linewidths=1.5,
                    alpha=0.9,
                    zorder=5,
                    label="Reservorios"
                )

        self.ax.set_title("Malla de Infraestructura Hidráulica - Puno", color="white", fontsize=10, pad=10)
        
        # Restaurar los límites del eje (posición de la cámara/zoom) si existen
        if has_limits:
            self.ax.set_xlim(current_xlim)
            self.ax.set_ylim(current_ylim)
        
        # Resaltar el nodo seleccionado si existe
        if self.selected_node_id and self.selected_node_id in graph.nodes:
            self._highlight_selected_node()
        else:
            self.canvas.draw()

    def highlight_path(self, graph: GeoGraph, path: list, algorithm_name: str):
        if not path or len(path) < 2:
            self.canvas.draw()
            return

        for i in range(len(path) - 1):
            u = graph.nodes[path[i]]
            v = graph.nodes[path[i + 1]]
            self.ax.plot(
                [u.x, v.x],
                [u.y, v.y],
                color="#FF9900",
                linewidth=2.5,
                zorder=4,
            )

        start_node = graph.nodes[path[0]]
        end_node = graph.nodes[path[-1]]
        self.ax.scatter([start_node.x], [start_node.y], color="#FF9900", s=30, marker="^", zorder=5)
        self.ax.scatter([end_node.x], [end_node.y], color="#FF3333", s=30, marker="v", zorder=5)

        self.canvas.draw()

    def highlight_mst(self, graph: GeoGraph, mst_edges: list):
        print(f"[DEBUG] highlight_mst called with {len(mst_edges) if mst_edges else 0} edges")
        print(f"[DEBUG] graph nodes count: {len(graph.nodes)}")
        if mst_edges:
            print(f"[DEBUG] first edge: {mst_edges[0]}")
            print(f"[DEBUG] first edge nodes in graph: {mst_edges[0][0] in graph.nodes}, {mst_edges[0][1] in graph.nodes}")
        if not mst_edges:
            self.canvas.draw()
            return

        mst_node_ids = set()
        for u, v, _ in mst_edges:
            mst_node_ids.add(u)
            mst_node_ids.add(v)

        for u, v, _ in mst_edges:
            if u in graph.nodes and v in graph.nodes:
                node_u = graph.nodes[u]
                node_v = graph.nodes[v]
                self.ax.plot(
                    [node_u.x, node_v.x],
                    [node_u.y, node_v.y],
                    color="#00E5FF",
                    linewidth=3.5,
                    zorder=4,
                    solid_capstyle="round",
                )

        mst_lons = [graph.nodes[nid].x for nid in mst_node_ids if nid in graph.nodes]
        mst_lats = [graph.nodes[nid].y for nid in mst_node_ids if nid in graph.nodes]
        print(f"[DEBUG] MST nodes to scatter: {len(mst_lons)}")
        if mst_lons:
            self.ax.scatter(
                mst_lons,
                mst_lats,
                color="#00E5FF",
                s=60,
                marker="s",
                edgecolors="white",
                linewidths=1.5,
                zorder=6,
                label="Tronco Principal",
            )

        self.canvas.draw()

    def highlight_critical_nodes(self, graph: GeoGraph, critical_node_ids: list):
        if not critical_node_ids:
            self.canvas.draw()
            return

        lons = [graph.nodes[nid].x for nid in critical_node_ids if nid in graph.nodes]
        lats = [graph.nodes[nid].y for nid in critical_node_ids if nid in graph.nodes]

        self.ax.scatter(lons, lats, color="#FF3333", s=40, marker="o", edgecolors="white", zorder=5)
        self.canvas.draw()

    def highlight_leak_nodes(self, graph: GeoGraph, red_nodes: list, orange_nodes: list):
        if not red_nodes and not orange_nodes:
            self.canvas.draw()
            return

        if red_nodes:
            red_lons = [graph.nodes[nid].x for nid in red_nodes if nid in graph.nodes]
            red_lats = [graph.nodes[nid].y for nid in red_nodes if nid in graph.nodes]
            if red_lons:
                self.ax.scatter(red_lons, red_lats, color="#FF0000", s=80, marker="o",
                                edgecolors="white", linewidths=2.5, zorder=8, label="Fuga Crítica")

        if orange_nodes:
            orange_lons = [graph.nodes[nid].x for nid in orange_nodes if nid in graph.nodes]
            orange_lats = [graph.nodes[nid].y for nid in orange_nodes if nid in graph.nodes]
            if orange_lons:
                self.ax.scatter(orange_lons, orange_lats, color="#FF9800", s=65, marker="o",
                                edgecolors="white", linewidths=2.0, zorder=8, label="Fuga Media")

        self.canvas.draw()

    def highlight_close_valves(self, graph: GeoGraph, close_valve_ids: list):
        if not close_valve_ids:
            self.canvas.draw()
            return

        lons = [graph.nodes[nid].x for nid in close_valve_ids if nid in graph.nodes]
        lats = [graph.nodes[nid].y for nid in close_valve_ids if nid in graph.nodes]
        if lons:
            self.ax.scatter(
                lons,
                lats,
                color="#FFD700",
                s=55,
                marker="X",
                edgecolors="white",
                linewidths=1.5,
                zorder=7,
                label="Válvulas a Cerrar",
            )

        self.canvas.draw()

    def highlight_alternative_paths(self, graph: GeoGraph, paths: List[List[str]]):
        if not paths:
            self.canvas.draw()
            return

        colors = ["#FF00FF", "#00FFFF", "#FFFF00", "#FF8800", "#88FF00"]
        for idx, path in enumerate(paths):
            if len(path) < 2:
                continue
            color = colors[idx % len(colors)]
            for i in range(len(path) - 1):
                u = graph.nodes[path[i]]
                v = graph.nodes[path[i + 1]]
                self.ax.plot(
                    [u.x, v.x],
                    [u.y, v.y],
                    color=color,
                    linewidth=2.0,
                    zorder=4,
                )
            start_node = graph.nodes[path[0]]
            end_node = graph.nodes[path[-1]]
            self.ax.scatter([start_node.x], [start_node.y], color=color, s=25, marker="^", zorder=5)
            self.ax.scatter([end_node.x], [end_node.y], color=color, s=25, marker="v", zorder=5)

        self.canvas.draw()
    
    def clear_selection(self):
        """Limpiar la selección actual"""
        self.selected_node_id = None
