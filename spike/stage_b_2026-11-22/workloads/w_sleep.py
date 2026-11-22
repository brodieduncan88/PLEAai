# T11: stay busy for `seconds` (bounded) so the VMM can be killed mid-execution.
import time
P = globals().get("PARAMS", {})
end = time.monotonic() + float(P.get("seconds", 30))
while time.monotonic() < end:
    time.sleep(0.2)
print("finished")
