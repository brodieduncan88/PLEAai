import hashlib, json, time
from decimal import Decimal, getcontext
t = time.monotonic(); getcontext().prec = 50
acc = Decimal(0)
for i in range(1, 20001):
    acc += Decimal(1) / (Decimal(i) * Decimal(i + 1))
data = json.dumps({"i": list(range(5000)), "s": "x" * 1000}, sort_keys=True).encode()
d = hashlib.sha256()
for _ in range(2000):
    d.update(data)
print("SPIKE_RESULT " + json.dumps({"job": "workload", "decimal": str(acc)[:40], "digest": d.hexdigest(),
                                    "elapsed_s": time.monotonic() - t}))
