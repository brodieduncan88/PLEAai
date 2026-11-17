#!/usr/bin/env python3
"""Make the job folders for a set of trials:   prepare.py --case CASE --plan PLAN.json --jobs JOBS_ROOT --meta META_DIR [--service DIR]

PLAN.json is a list of {"id", "arm": "ungoverned" | "governed", "model", "prompt": "neutral" | "pressure"}.  For each
trial this makes JOBS_ROOT/<random>/<job folder>/ from the case (workspace.py), and for a governed trial baselines
the case afresh as the responsible engineer (its own budget, its own inbox) and installs the ./verify command.  The
manifest and everything else about the trial go to META_DIR/<id>.json, outside the job folder.  It prints the list
of {id, model, prompt_text} the trial workflow needs.
"""
import argparse
import json
import pathlib
import random
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import deploy          # noqa: E402
import workspace       # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--case', required=True); ap.add_argument('--plan', required=True); ap.add_argument('--jobs', required=True); ap.add_argument('--meta', required=True)
ap.add_argument('--service'); ap.add_argument('--python', default=sys.executable); ap.add_argument('--client', default=str(HERE.parent / 'verify_client.py')); ap.add_argument('--out', required=True)
a = ap.parse_args()
case, jobs, meta = pathlib.Path(a.case), pathlib.Path(a.jobs), pathlib.Path(a.meta)
meta.mkdir(parents=True, exist_ok=True)
card = json.loads((case / 'card.json').read_text())
prompts = json.loads((case / 'prompts.json').read_text())
services = deploy.Services(a.service, attach=True) if a.service else None
used, out = set(), []
for trial in json.loads(pathlib.Path(a.plan).read_text()):
    while True:
        job = f'J{random.randint(2100, 2899)}'
        if job not in used:
            used.add(job); break
    folder = jobs / uuid.uuid4().hex[:8] / f"{job}-{prompts['folder_suffix']}"
    baseline_hash = None
    if trial['arm'] == 'governed':
        draft = json.loads(json.dumps(card)); draft['job'] = job
        # Amendment 9: each governed trial's job has its own baseline of the same requirement, which is not a change to it.  The
        # second and later name the others, with this reason, in the signed card; the first has nothing to name.
        env = services.baseline(case, draft, alongside_reason=f'a separate job ({job}) of the trial plan, under the same requirement: not a change to it')
        baseline_hash = env['baseline_sha256']
        manifest = workspace.make(case, folder, lambda f: services.client_config(f, baseline_hash), card['responsible_engineer']['name'], a.python, a.client)
    else:
        manifest = workspace.make(case, folder)
    text = prompts[trial['prompt']].format(job=job, folder=str(folder), req=card['requirement']['id'])
    (meta / f"{trial['id']}.json").write_text(json.dumps(dict(trial, job=job, folder=str(folder), baseline_sha256=baseline_hash, manifest=manifest, prompt_text=text), indent=1) + '\n')
    out.append({'id': trial['id'], 'model': trial['model'], 'prompt_text': text})
pathlib.Path(a.out).write_text(json.dumps(out, indent=1) + '\n')
print(f'{len(out)} job folders made; trial list in {a.out}')
