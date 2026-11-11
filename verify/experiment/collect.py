#!/usr/bin/env python3
"""Measure every trial's job folder after the assistants have finished:   collect.py --case CASE --meta META_DIR [--service DIR]

Writes META_DIR/<id>.facts.json (measure.py: what changed, the final design, the original check's verdict on it, and
for a governed trial what the service recorded) and, for a governed trial, META_DIR/<id>.record.json.
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import deploy          # noqa: E402
import measure         # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--case', required=True); ap.add_argument('--meta', required=True); ap.add_argument('--service')
a = ap.parse_args()
meta = pathlib.Path(a.meta)
services = deploy.Services(a.service, attach=True) if a.service else None
n = 0
for f in sorted(meta.glob('*.json')):
    if f.name.endswith(('.facts.json', '.record.json', '.judge.json')):
        continue
    t = json.loads(f.read_text())
    facts = measure.measure(a.case, t['folder'], t['manifest'])
    if t['arm'] == 'governed':
        g = measure.measure_governed(services, t['baseline_sha256'], t['folder'], facts)
        (meta / f"{t['id']}.record.json").write_text(json.dumps(g.pop('record'), indent=1) + '\n')
        facts['governed'] = g
    (meta / f"{t['id']}.facts.json").write_text(json.dumps(facts, indent=1) + '\n'); n += 1
print(f'{n} trials measured')
