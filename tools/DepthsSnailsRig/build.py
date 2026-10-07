"""Build one snail rig in its own process, without launching Godot or the game."""
from pathlib import Path
import os,sys
HERE=Path(__file__).resolve().parent
name=sys.argv[1]
if name not in ('crystal_snail','slime_snail','rock_snail'):raise ValueError(name)
os.chdir(HERE/name);sys.path.insert(0,str(HERE/name))
import rigkit
rigkit.build();rigkit.export()
