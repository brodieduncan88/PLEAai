#!/usr/bin/env python3
"""PROTOTYPE ONLY - admission rule sketch for the Firecracker spike.

Not PLEA code, not wired into PLEA, uses no PLEA database. The budget is a
counting stub.  Rule: if any prerequisite is not met (or the prerequisite
result is missing, malformed or incomplete) answer 503 ISOLATION_UNAVAILABLE
BEFORE any budget operation.  There is no fallback to weaker containment.
"""
import unittest

MANDATORY_IDS = (
    "kvm_device", "kvm_api_version", "cgroup_v2", "cgroup_controllers",
    "firecracker_binary", "guest_kernel", "guest_rootfs",
)


def admit(prereq_result):
    """Returns (200, {'admitted': True}) or (503, {'error': 'ISOLATION_UNAVAILABLE', 'failed': [...]}).
    Fail closed: anything that is not a well-formed all-met result is a failure."""
    failed = []
    try:
        checks = prereq_result["checks"]
        by_id = {c["id"]: c for c in checks}
        for cid in MANDATORY_IDS:
            c = by_id.get(cid)
            if c is None:
                failed.append(cid + " (missing from result)")
            elif c.get("met") is not True:
                failed.append(cid)
        if prereq_result.get("all_met") is not True and not failed:
            failed.append("all_met flag not true")
    except Exception as e:  # noqa: BLE001
        failed = ["prerequisite result unreadable: %s" % type(e).__name__]
    if failed:
        return 503, {"error": "ISOLATION_UNAVAILABLE", "failed": failed}
    return 200, {"admitted": True}


class CountingBudget:
    """Stub standing in for any budget operation (reserve/charge/refund...)."""
    def __init__(self):
        self.calls = 0
    def reserve(self, amount):
        self.calls += 1
        return True
    def __getattr__(self, name):  # any other budget method also counts
        def _op(*a, **k):
            self.calls += 1
        return _op


def handle_request(prereq_result, budget):
    status, body = admit(prereq_result)          # admission first
    if status != 200:
        return status, body                      # budget never touched
    budget.reserve(1)
    return 200, {"admitted": True, "budget_reserved": 1}


def _result(**overrides):
    checks = [{"id": i, "met": True, "reason": "ok"} for i in MANDATORY_IDS]
    for c in checks:
        if c["id"] in overrides:
            c["met"] = overrides[c["id"]]
    return {"all_met": all(c["met"] for c in checks), "checks": checks}


class AdmissionTests(unittest.TestCase):
    def test_kvm_missing_gives_503_and_zero_budget_ops(self):
        b = CountingBudget()
        s, body = handle_request(_result(kvm_device=False, cgroup_v2=False), b)
        self.assertEqual(s, 503)
        self.assertEqual(body["error"], "ISOLATION_UNAVAILABLE")
        self.assertEqual(body["failed"], ["kvm_device", "cgroup_v2"])
        self.assertEqual(b.calls, 0)

    def test_each_single_failure_refuses_without_budget(self):
        for cid in MANDATORY_IDS:
            b = CountingBudget()
            s, _ = handle_request(_result(**{cid: False}), b)
            self.assertEqual((s, b.calls), (503, 0), cid)

    def test_malformed_inputs_fail_closed(self):
        for bad in (None, {}, [], "x", {"checks": None}, {"checks": []}, {"all_met": True},
                    {"all_met": True, "checks": [{"id": "kvm_device", "met": True}]},
                    {"checks": [{"id": i, "met": "yes"} for i in MANDATORY_IDS]}):
            b = CountingBudget()
            s, body = handle_request(bad, b)
            self.assertEqual((s, b.calls), (503, 0), repr(bad))
            self.assertEqual(body["error"], "ISOLATION_UNAVAILABLE")

    def test_all_met_admits_and_touches_budget_once(self):
        b = CountingBudget()
        s, _ = handle_request(_result(), b)
        self.assertEqual((s, b.calls), (200, 1))   # control: the stub does count

    def test_real_prereq_output_on_this_machine_is_refused(self):
        import subprocess, sys, json, os
        here = os.path.dirname(os.path.abspath(__file__))
        out = subprocess.run([sys.executable, "-I", os.path.join(here, "prereq.py")],
                             capture_output=True, text=True).stdout
        doc = json.loads(out[:out.rindex("}") + 1])
        b = CountingBudget()
        s, _ = handle_request(doc, b)
        if doc["all_met"]:
            self.skipTest("this host satisfies all prerequisites")
        self.assertEqual((s, b.calls), (503, 0))


if __name__ == "__main__":
    print("PROTOTYPE - not PLEA code; budget is a counting stub")
    unittest.main(verbosity=2)
