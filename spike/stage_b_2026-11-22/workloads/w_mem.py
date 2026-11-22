# T05/T06: allocate and touch memory in chunks beyond the guest's RAM; expect the guest OOM killer.
import json, sys
P = globals().get("PARAMS", {})
target, chunk = int(P.get("target_mib", 512)), int(P.get("chunk_mib", 8))
held, got = [], 0
try:
    while got < target:
        b = bytearray(chunk << 20)
        b[::4096] = b"\x01" * len(range(0, chunk << 20, 4096))  # touch every page
        held.append(b)
        got += chunk
        print(got, flush=True)
    print(json.dumps({"allocated_mib": got, "outcome": "target_reached"}))
except MemoryError:
    print(json.dumps({"allocated_mib": got, "outcome": "MemoryError"}))
