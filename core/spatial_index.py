from typing import List, Tuple, Dict, Any

class SpatialGridIndex:
    def __init__(self, cell_size: float = 0.001):
        self.cell_size = cell_size
        self.grid: Dict[Tuple[int, int], List[Tuple[str, float, float]]] = {}

    def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
        return int(x // self.cell_size), int(y // self.cell_size)

    def insert(self, node_id: str, x: float, y: float):
        cell = self._get_cell(x, y)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append((node_id, x, y))

    def find_nearest_node(self, x: float, y: float, max_radius: float = 0.01) -> Tuple[str, float]:
        center_cell_x, center_cell_y = self._get_cell(x, y)
        cell_radius = int(max_radius // self.cell_size) + 1
        best_node_id = None
        min_dist = float('inf')

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (center_cell_x + dx, center_cell_y + dy)
                if cell in self.grid:
                    for node_id, nx, ny in self.grid[cell]:
                        dist = ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
                        if dist < min_dist and dist <= max_radius:
                            min_dist = dist
                            best_node_id = node_id
        return best_node_id, min_dist

    def query_candidates(self, x: float, y: float, radius: float = 0.005) -> List[str]:
        center_cell_x, center_cell_y = self._get_cell(x, y)
        cell_radius = int(radius // self.cell_size) + 1
        candidates: Dict[str, float] = {}

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (center_cell_x + dx, center_cell_y + dy)
                if cell in self.grid:
                    for node_id, nx, ny in self.grid[cell]:
                        dist = ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
                        if dist <= radius:
                            if node_id not in candidates or dist < candidates[node_id]:
                                candidates[node_id] = dist

        return list(candidates.keys())

    def clear(self):
        self.grid.clear()
