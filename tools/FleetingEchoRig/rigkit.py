"""Use the project's existing weighted-mesh Spine authoring toolkit."""
import runpy
import sys
from pathlib import Path
here=Path(__file__).resolve().parent
shared=here.parent/'CaveMawRig'
sys.path.insert(0,str(shared));sys.path.insert(0,str(here))
runpy.run_path(str(shared/'rigkit.py'),run_name='__main__')
