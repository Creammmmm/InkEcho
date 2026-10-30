import sys,json
from focus_proof import inspect
print(json.dumps(inspect(int(sys.argv[1]),browser_pid=int(sys.argv[2]),browser_exe=sys.argv[3],profile=sys.argv[4]),indent=2))
