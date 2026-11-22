#!/usr/bin/env python3
"""Minimal MODEL of the service admission rule (not PLEA's code):

  prereq NOT MET      -> HTTP 503 {"error": "ISOLATION_UNAVAILABLE"}; budget file untouched
  budget exhausted    -> HTTP 429 {"error": "BUDGET_EXHAUSTED"};     budget file untouched
  otherwise           -> HTTP 200 {"admitted": true}; budget debited by exactly one

The budget counter is a text file holding one non-negative integer (stand-in for the engineering budget).
The prereq check runs BEFORE the budget file is opened, so a refusal cannot touch it.
Usage: python3 -I -B admission.py <budget_file>
"""
import fcntl
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import prereq  # noqa: E402

check = prereq.check_all  # replaceable in selftest


def admit(budget_path, hash_images=False):
    pr = check(hash_images=hash_images)
    if not pr["all_met"]:
        return 503, {"error": "ISOLATION_UNAVAILABLE", "not_met": pr["not_met"]}
    fd = os.open(budget_path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        raw = os.read(fd, 64)
        text = raw.decode("ascii", "strict").strip()
        if not text.isdigit():
            return 500, {"error": "BUDGET_CORRUPT"}  # fail closed, file untouched
        n = int(text)
        if n <= 0:
            return 429, {"error": "BUDGET_EXHAUSTED", "budget": n}
        new = f"{n - 1}\n".encode()
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, new)
        os.fsync(fd)
        return 200, {"admitted": True, "budget_before": n, "budget_after": n - 1}
    finally:
        os.close(fd)


if __name__ == "__main__":
    code, body = admit(sys.argv[1])
    print(json.dumps({"http_status": code, "body": body}))
    sys.exit(0 if code == 200 else 1)
