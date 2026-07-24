from pathlib import Path

path = Path('ui/main_window.py')
text = path.read_text(encoding='utf-8-sig')

start = text.find('    def run_valve_shutdown(self):')
first_end = text.find('    def run_pathfinding_simulation(self):')

old_block = text[start:first_end]
new_block = old_block + '''
        self.valves_to_close = [v["valve_id"] for v in close_valves]
        self.write_scada_log(f"Válvulas recomendadas para cerrar: {len(close_valves)}")
        self._refresh_map_view()

    def run_pathfinding_simulation(self):
'''

if old_block in text:
    text = text.replace(old_block, new_block, 1)
    path.write_text(text, encoding='utf-8-sig')
    print('Fixed run_valve_shutdown')
else:
    print('Pattern not found')
