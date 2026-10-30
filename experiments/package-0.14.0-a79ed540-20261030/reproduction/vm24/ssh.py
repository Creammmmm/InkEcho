import subprocess,sys
from pathlib import Path
raise SystemExit(subprocess.call(["python3",str(Path(__file__).parents[1]/"control.py"),"ssh","24","wayland",sys.argv[2],sys.argv[1]]))
