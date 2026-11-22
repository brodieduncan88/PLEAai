# T01/T10/T12: echo the host-supplied nonce and the guest-side view. Stdlib only.
import json, os, time
P = globals().get("PARAMS", {})
try:
    open("/dev/vdb", "rb").read(1)
    vdb = "READABLE"
except OSError as e:
    vdb = f"denied:{e.errno}"
print(json.dumps({"nonce": P.get("nonce"), "uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups(),
                  "devs": sorted(os.listdir("/sys/block")), "vdb_as_workload": vdb}, sort_keys=True))
time.sleep(float(P.get("sleep", 0)))  # T10 keeps VMs alive together for host-side checks
