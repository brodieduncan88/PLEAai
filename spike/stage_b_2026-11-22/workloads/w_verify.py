# T03: deterministic standard-library computation. The host runs the same file locally and compares hashes.
import hashlib, json, math, sys, zlib

def primes_below(n):
    s = bytearray([1]) * n
    s[0:2] = b"\x00\x00"
    for i in range(2, math.isqrt(n - 1) + 1):
        if s[i]:
            s[i * i::i] = bytes(len(range(i * i, n, i)))
    return sum(s)

h = b"plea-stage-b"
for _ in range(20000):
    h = hashlib.sha256(h).digest()
a, b = 0, 1
for _ in range(90):
    a, b = b, a + b
data = bytes(range(256)) * 1024
doc = {"sha256_chain_20000": h.hex(), "primes_below_200000": primes_below(200000), "fib_90": a,
       "sum_isqrt_1_100000": sum(math.isqrt(i) for i in range(1, 100001)), "crc32_256k": zlib.crc32(data),
       "blake2b_256k": hashlib.blake2b(data, digest_size=16).hexdigest()}
doc["json_roundtrip_ok"] = json.loads(json.dumps(doc, sort_keys=True)) == doc
print(json.dumps(doc, sort_keys=True))
print("guest_python", sys.version.split()[0], file=sys.stderr)
