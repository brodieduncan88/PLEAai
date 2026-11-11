#!/usr/bin/env python3
"""Run one verification service until told to stop:   serve.py DIRECTORY [--witness-port N] [--host-port N]

Starts the witness service and the gate host (deploy.Services), writes DIRECTORY/state.json (public keys, ports,
certificate paths), prints "ready", and waits.  It stops the services when DIRECTORY/stop appears.
"""
import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import deploy          # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('directory'); ap.add_argument('--witness-port', type=int, default=8971); ap.add_argument('--host-port', type=int, default=8972)
a = ap.parse_args()
s = deploy.Services(a.directory, a.witness_port, a.host_port).start()
print('ready', flush=True)
try:
    while not (pathlib.Path(a.directory) / 'stop').exists():
        time.sleep(1)
        for name, p in s.procs.items():
            if p.poll() is not None:
                print(f'{name} exited with {p.returncode}', flush=True); raise SystemExit(1)
finally:
    s.stop()
print('stopped', flush=True)
