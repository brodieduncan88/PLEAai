import json
chunks, err = [], None
try:
    while len(chunks) < 100000:
        b = bytearray(4 * 1024 * 1024)
        b[::4096] = b"\x01" * len(b[::4096])       # touch every page
        chunks.append(b)
except MemoryError as e:
    err = "MemoryError"
print("SPIKE_RESULT " + json.dumps({"job": "membloat", "mib_allocated": 4 * len(chunks), "stopped_by": err}))
