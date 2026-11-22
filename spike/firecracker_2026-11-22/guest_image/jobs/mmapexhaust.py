import json, mmap
maps, err = [], None
try:
    for i in range(200000):
        m = mmap.mmap(-1, 4096)                    # each its own VMA is not guaranteed to merge; count regardless
        maps.append(m)
except (OSError, ValueError) as e:
    err = repr(e)
try:
    mc = int(open("/proc/sys/vm/max_map_count").read())
except OSError:
    mc = None
print("SPIKE_RESULT " + json.dumps({"job": "mmapexhaust", "mappings": len(maps), "vm_max_map_count": mc, "stopped_by": err}))
