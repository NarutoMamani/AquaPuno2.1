import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import math
from typing import List

from core.graph import GeoGraph
from utils.logger import logger

try:
    from matplotlib.collections import LineCollection
    _HAS_LINECOLLECTION = True
except ImportError:
    _HAS_LINECOLLECTION = False


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
        
        self.canvas.mpl_connect('button_press_event', self._on_canvas_click)
        
        self.graph = None
        self.selected_node_id = None
        self.on_node_selected = None
        self.sensor_data = None
        self.highlight_scatter = None
        
        self._base_drawn_graph_id = None
        self._base_nodes_scatter = None
        self._base_reservoir_scatter = None
        self._mst_collection = None
        self._mst_scatter = None
        self._path_collections = []
        self._leak_artists = []

    def set_node_selection_callback(self, callback):
        """Establecer el callback que se ejecuta cuando se selecciona un nodo"""
        self.on_node_selected = callback
    
    def _on_canvas_click(self, event):
        """Manejador de clics en el canvas"""
        if event.inaxes != self.ax or not self.graph:
            return
        
        click_x, click_y = event.xdata, event.ydata
        closest_node_id, distance = self._find_closest_node(click_x, click_y)
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]
        avg_range = (x_range + y_range) / 2
        dynamic_threshold = max(avg_range * 0.005, 0.0001)
        
        if closest_node_id and distance < dynamic_threshold:
            self.selected_node_id = closest_node_id
            self._refresh_highlight_only()
            if self.on_node_selected:
                node = self.graph.nodes[closest_node_id]
                self.on_node_selected(closest_node_id, node, self.sensor_data)
        else:
            self.selected_node_id = None
            self._refresh_highlight_only()
            if self.on_node_selected:
                self.on_node_selected(None, None, None)
    
    def _find_closest_node(self, click_x, click_y):
        """Encontrar el nodo más cercano al punto de clic usando el índice espacial"""
        if not self.graph or not self.graph.nodes:
            return None, float('inf')
        
        try:
            if hasattr(self.graph, 'spatial_index') and self.graph.spatial_index is not None:
                candidates = self.graph.spatial_index.query_candidates(click_x, click_y, radius=0.005)
                if candidates:
                    closest_node_id = None
                    min_distance = float('inf')
                    for node_id in candidates:
                        node = self.graph.nodes[node_id]
                        distance = math.sqrt((node.x - click_x)**2 + (node.y - click_y)**2)
                        if distance < min_distance:
                            min_distance = distance
                            closest_node_id = node_id
                    return closest_node_id, min_distance
        except Exception:
            pass
        
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
        
        if self.selected_node_id and self.selected_node_id in self.graph.nodes:
            node = self.graph.nodes[self.selected_node_id]
            self.highlight_scatter = self.ax.scatter([node.x], [node.y], color="#00FF00", s=80, 
                           marker="o", edgecolors="white", linewidths=2.5, zorder=10)
        
        self.canvas.draw_idle()
    
    def _highlight_selected_node(self):
        """Resaltar el nodo seleccionado en el mapa"""
        if not self.selected_node_id or not self.graph:
            return
        
        if self.highlight_scatter is not None:
            try:
                self.highlight_scatter.remove()
            except Exception:
                pass
            self.highlight_scatter = None
        
        node = self.graph.nodes[self.selected_node_id]
        self.highlight_scatter = self.ax.scatter([node.x], [node.y], color="#00FF00", s=80, 
                       marker="o", edgecolors="white", linewidths=2.5, zorder=10)
        self.canvas.draw_idle()

    def draw_base_network(self, graph: GeoGraph, pressure_data=None):
        current_graph_id = id(graph)
        needs_redraw = self._base_drawn_graph_id != current_graph_id

        self.clear_dynamic_layers()

        if needs_redraw:
            current_xlim = self.ax.get_xlim()
            current_ylim = self.ax.get_ylim()
            has_limits = not (current_xlim == (0, 1) and current_ylim == (0, 1))
            
            self.graph = graph
            self.sensor_data = pressure_data
            self.ax.clear()
            self.highlight_scatter = None
            self._base_nodes_scatter = None
            self._base_reservoir_scatter = None
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
            self._base_nodes_scatter = self.ax.scatter(
                lons, lats, color="#00F0FF", s=1.5, alpha=0.5, zorder=2
            )
            
            if graph.reservoir_nodes:
                reservoir_lons = [graph.nodes[nid].x for nid in graph.reservoir_nodes if nid in graph.nodes]
                reservoir_lats = [graph.nodes[nid].y for nid in graph.reservoir_nodes if nid in graph.nodes]
                
                if reservoir_lons:
                    self._base_reservoir_scatter = self.ax.scatter(
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
            
            if has_limits:
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
            
            self._base_drawn_graph_id = current_graph_id
        else:
            if self.highlight_scatter is not None:
                try:
                    self.highlight_scatter.remove()
                except Exception:
                    pass
                self.highlight_scatter = None
            self.graph = graph
            self.sensor_data = pressure_data
        
        if self.selected_node_id and self.selected_node_id in graph.nodes:
            self._highlight_selected_node()
        else:
            self.canvas.draw_idle()

    def highlight_path(self, graph: GeoGraph, path: list, algorithm_name: str):
        if not path or len(path) < 2:
            self.canvas.draw_idle()
            return

        segments = []
        start_node = graph.nodes[path[0]]
        end_node = graph.nodes[path[-1]]
        for i in range(len(path) - 1):
            u = graph.nodes[path[i]]
            v = graph.nodes[path[i + 1]]
            segments.append([(u.x, u.y), (v.x, v.y)])

        if _HAS_LINECOLLECTION:
            collection = LineCollection(
                segments,
                color="#FF9900",
                linewidth=2.5,
                zorder=4,
            )
            self.ax.add_collection(collection)
            self._path_collections.append(collection)
        else:
            for i in range(len(path) - 1):
                u = graph.nodes[path[i]]
                v = graph.nodes[path[i + 1]]
                line, = self.ax.plot(
                    [u.x, v.x],
                    [u.y, v.y],
                    color="#FF9900",
                    linewidth=2.5,
                    zorder=4,
                )
                self._path_collections.append(line)

        start_scatter = self.ax.scatter([start_node.x], [start_node.y], color="#FF9900", s=30, marker="^", zorder=5)
        end_scatter = self.ax.scatter([end_node.x], [end_node.y], color="#FF3333", s=30, marker="v", zorder=5)
        self._path_collections.extend([start_scatter, end_scatter])

        self.canvas.draw_idle()

    def highlight_mst(self, graph: GeoGraph, mst_edges: list):
        if not mst_edges:
            self.clear_dynamic_layers()
            return

        mst_node_ids = set()
        segments = []
        for u, v, _ in mst_edges:
            mst_node_ids.add(u)
            mst_node_ids.add(v)
            if u in graph.nodes and v in graph.nodes:
                node_u = graph.nodes[u]
                node_v = graph.nodes[v]
                segments.append([(node_u.x, node_u.y), (node_v.x, node_v.y)])

        if self._mst_collection is not None:
            try:
                self._mst_collection.remove()
            except Exception:
                pass
            self._mst_collection = None
        if self._mst_scatter is not None:
            try:
                self._mst_scatter.remove()
            except Exception:
                pass
            self._mst_scatter = None

        if segments:
            if _HAS_LINECOLLECTION:
                self._mst_collection = LineCollection(
                    segments,
                    color="#00E5FF",
                    linewidth=3.5,
                    zorder=4,
                )
                self.ax.add_collection(self._mst_collection)
            else:
                for seg in segments:
                    self.ax.plot(
                        [seg[0][0], seg[1][0]],
                        [seg[0][1], seg[1][1]],
                        color="#00E5FF",
                        linewidth=3.5,
                        zorder=4,
                        solid_capstyle="round",
                    )

        mst_lons = [graph.nodes[nid].x for nid in mst_node_ids if nid in graph.nodes]
        mst_lats = [graph.nodes[nid].y for nid in mst_node_ids if nid in graph.nodes]
        if mst_lons:
            self._mst_scatter = self.ax.scatter(
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

        self.canvas.draw_idle()

    def highlight_critical_nodes(self, graph: GeoGraph, critical_node_ids: list):
        if not critical_node_ids:
            self.canvas.draw_idle()
            return

        lons = [graph.nodes[nid].x for nid in critical_node_ids if nid in graph.nodes]
        lats = [graph.nodes[nid].y for nid in critical_node_ids if nid in graph.nodes]

        scatter = self.ax.scatter(lons, lats, color="#FF3333", s=40, marker="o", edgecolors="white", zorder=5)
        self._leak_artists.append(scatter)
        self.canvas.draw_idle()

    def highlight_leak_nodes(self, graph: GeoGraph, red_nodes: list, orange_nodes: list):
        self._clear_artists(self._leak_artists)
        
        if not red_nodes and not orange_nodes:
            self.canvas.draw_idle()
            return

        if red_nodes:
            red_lons = [graph.nodes[nid].x for nid in red_nodes if nid in graph.nodes]
            red_lats = [graph.nodes[nid].y for nid in red_nodes if nid in graph.nodes]
            if red_lons:
                scatter = self.ax.scatter(red_lons, red_lats, color="#FF0000", s=80, marker="o",
                                edgecolors="white", linewidths=2.5, zorder=8, label="Fuga Crítica")
                self._leak_artists.append(scatter)

        if orange_nodes:
            orange_lons = [graph.nodes[nid].x for nid in orange_nodes if nid in graph.nodes]
            orange_lats = [graph.nodes[nid].y for nid in orange_nodes if nid in graph.nodes]
            if orange_lons:
                scatter = self.ax.scatter(orange_lons, orange_lats, color="#FF9800", s=65, marker="o",
                                edgecolors="white", linewidths=2.0, zorder=8, label="Fuga Media")
                self._leak_artists.append(scatter)

        self.canvas.draw_idle()

    def highlight_close_valves(self, graph: GeoGraph, close_valve_ids: list):
        if not close_valve_ids:
            self.canvas.draw_idle()
            return

        lons = [graph.nodes[nid].x for nid in close_valve_ids if nid in graph.nodes]
        lats = [graph.nodes[nid].y for nid in close_valve_ids if nid in graph.nodes]
        if lons:
            scatter = self.ax.scatter(
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
            self._leak_artists.append(scatter)

        self.canvas.draw_idle()

    def highlight_alternative_paths(self, graph: GeoGraph, paths: List[List[str]]):
        if not paths:
            self.canvas.draw_idle()
            return

        colors = ["#FF00FF", "#00FFFF", "#FFFF00", "#FF8800", "#88FF00"]
        all_segments = []
        start_points = []
        end_points = []
        
        for idx, path in enumerate(paths):
            if len(path) < 2:
                continue
            color = colors[idx % len(colors)]
            for i in range(len(path) - 1):
                u = graph.nodes[path[i]]
                v = graph.nodes[path[i + 1]]
                all_segments.append([(u.x, u.y), (v.x, v.y)])
            start_points.append((graph.nodes[path[0]].x, graph.nodes[path[0]].y, color))
            end_points.append((graph.nodes[path[-1]].x, graph.nodes[path[-1]].y, color))

        if _HAS_LINECOLLECTION and all_segments:
            collection = LineCollection(
                all_segments,
                colors=colors[:len(paths)] * (len(all_segments) // len(paths) + 1),
                linewidth=2.0,
                zorder=4,
            )
            self.ax.add_collection(collection)
            self._path_collections.append(collection)
        else:
            for idx, path in enumerate(paths):
                if len(path) < 2:
                    continue
                color = colors[idx % len(colors)]
                for i in range(len(path) - 1):
                    u = graph.nodes[path[i]]
                    v = graph.nodes[path[i + 1]]
                    line, = self.ax.plot(
                        [u.x, v.x],
                        [u.y, v.y],
                        color=color,
                        linewidth=2.0,
                        zorder=4,
                    )
                    self._path_collections.append(line)

        for x, y, color in start_points:
            scatter = self.ax.scatter([x], [y], color=color, s=25, marker="^", zorder=5)
            self._path_collections.append(scatter)
        for x, y, color in end_points:
            scatter = self.ax.scatter([x], [y], color=color, s=25, marker="v", zorder=5)
            self._path_collections.append(scatter)

        self.canvas.draw_idle()
    
    def clear_selection(self):
        """Limpiar la selección actual"""
        self.selected_node_id = None

    def _clear_artists(self, artists_list):
        for artist in artists_list:
            try:
                artist.remove()
            except Exception:
                pass
        artists_list.clear()

    def clear_dynamic_layers(self):
        if self._mst_collection is not None:
            try:
                self._mst_collection.remove()
            except Exception:
                pass
            self._mst_collection = None
        if self._mst_scatter is not None:
            try:
                self._mst_scatter.remove()
            except Exception:
                pass
            self._mst_scatter = None
        self._clear_artists(self._path_collections)
        self._clear_artists(self._leak_artists)
