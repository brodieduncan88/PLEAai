import json, mmap, os
fds, maps, e1, e2 = [], [], None, None
try:
    for _ in range(2000000): fds.append(os.open("/dev/null", os.O_RDONLY))
except OSError as e: e1 = repr(e)
try:
    for _ in range(200000): maps.append(mmap.mmap(-1, 4096))
except (OSError, ValueError) as e: e2 = repr(e)
print("SPIKE_RESULT " + json.dumps({"job": "fdmmap", "opened": len(fds), "fd_stop": e1, "mappings": len(maps), "map_stop": e2}))
