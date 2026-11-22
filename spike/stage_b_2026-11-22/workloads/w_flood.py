# T08/T09: write `bytes` bytes to stdout (console in console mode, the result pipe otherwise).
import os, sys
P = globals().get("PARAMS", {})
n = int(P.get("bytes", 8 << 20))
line = (b"0123456789abcdef" * 4 + b"\n") * 1024  # 65 KiB block of 65-byte lines
out = sys.stdout.buffer
while n > 0:
    k = min(n, len(line))
    out.write(line[:k])
    n -= k
out.flush()
