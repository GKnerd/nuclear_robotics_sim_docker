./build/room_source macros/run.mac
python3 export_radiation_tensor.py --sigma 1
python3 visualize_radiation_map_interactive.py radiation_map.csv --mode both --sigma 1