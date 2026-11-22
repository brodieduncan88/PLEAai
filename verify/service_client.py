#!/usr/bin/env python3
"""The service's own reading of one baseline's runs: the governor it drives, the runs it lists, and the words it shows.

Amendment 17 (22 November 2026, D6 and D35).  This is the part of the first plug-in, `verify_client.py`, that the front door
was built on (`front_door.ServiceClient`), moved here unchanged in what it does.  It is used by the service only: it is never
given to an assistant, it reads no configuration file of its own, and it holds no credential of its own.  The front door
gives it the service's store, certificate and keys for each request.  The assistant-side command that held the gateway's
database credential (`verify_client.py`) is retired: it now refuses to run.

The text of every method is as it was in `verify_client.py` at 1b132e2, except that a Client is no longer made from a
workspace configuration file, and `submit`, which was the assistant's transport, is not here.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import GateHostClient, Governor, RemoteWitness    # noqa: E402
from plea_gateway.tls import TLSClient                              # noqa: E402
from baseline import does_not_cover                                 # noqa: E402
from verify_record import attempts_of                               # noqa: E402


OUTCOME_WORDS = {'PASS': 'MET'}     # Amendment 9: a listing shows a pass as the declared check met; the record keeps the signed word


def met_lines(card, attempts: list) -> list:
    """Amendment 9.  Where a design has met the declared check, what that does and does not say, and what the check does not
    cover, so that a listing never shows a pass bare."""
    met = [a for a in attempts if a.get('outcome') == 'PASS']
    if not met:
        return []
    designs = sorted({str((a.get('result') or {}).get('design_sha256') or '?')[:16] for a in met})
    return [f"DECLARED CHECK MET, for design {', '.join(d + '…' for d in designs)} only.  This says what the declared check returned against the "
            'baselined limits.  It does not say the check is correct, the requirement is complete, or the design is safe.',
            does_not_cover(card) if card is not None else 'What the check does not cover cannot be shown here: the stored baseline could not be read.']


def alongside_lines(card) -> list:
    """Amendment 9.  The other baselines held for this requirement when this one was made, not as a revision, and why."""
    side = (card or {}).get('alongside')
    if not side:
        return []
    return [f"  ALSO BASELINED FOR THIS REQUIREMENT, NOT AS A REVISION OF IT: "
            + ', '.join(f"{b['baseline_sha256'][:16]}… (rev {b['revision']})" for b in side['baselines']) + f".  Reason given by the engineer: {side['reason']}"]


def tally(attempts: list) -> dict:
    runs = {'total': len(attempts), 'PASS': 0, 'FAIL': 0, 'UNKNOWN': 0}
    for a in attempts:
        runs[a['outcome'] if a['outcome'] in ('PASS', 'FAIL') else 'UNKNOWN'] += 1
    return runs


class Client:
    """What the service reads for one baseline.  A subclass (front_door.ServiceClient) sets cfg, path, store, envelope, card,
    baseline and root from what the service holds."""

    def governor(self) -> Governor:
        t = self.cfg['tls']; tls = TLSClient(self.path(t['ca']), self.path(t['cert']), self.path(t['key']))
        keys = self.cfg['witness_keys']
        witness = RemoteWitness(self.cfg['witness_url'], keys if len(keys) > 1 else keys[0], tls=tls)
        host = GateHostClient(self.cfg['gate_url'], tls=tls, public_key=self.cfg['gate_key'])
        obs = self.store.observe(self.root)
        return Governor(self.store, witness, self.root, obs['k'], obs['m'], host=host)

    def runs(self) -> tuple[dict, list]:
        attempts, _ = attempts_of(self.store, self.root, self.journal())
        return tally(attempts), attempts

    def journal(self) -> list:
        p = pathlib.Path(self.path(self.cfg.get('journal', 'submissions.jsonl')))
        if not p.exists():
            return []
        out = []
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    def show(self) -> str:
        c, req, chk = self.card, self.card['requirement'], self.card['check']
        L = [f"BASELINED REQUIREMENT  {req['id']} rev {req['revision']}: {req['title']}", f"  \"{req['statement']}\"", f"  Source: {req['source']}",
             f"  Baselined {c.get('baselined_at', '?')} by {c['responsible_engineer']['name']}, responsible engineer.  Baseline hash {self.baseline}", '', 'ACCEPTANCE LIMITS']
        for k in c['criteria']:
            L.append(f"  {k['id']}: {k['quantity']} {'at most' if k['comparison'] == '<=' else 'at least'} {k['limit']} {k['units']}")
        L += ['', 'LOAD CASE', f"  {c['load_case']}", '', 'DESIGN SPACE (what may be varied)']
        for name, rule in c['design_space'].items():
            L.append(f"  {name}: " + ('one of ' + ', '.join(map(str, rule['choice'])) if 'choice' in rule else f"a number from {rule['min']} to {rule['max']}"))
        L += ['', f"DECLARED CHECK  {chk['id']} v{chk['version']}, written by {chk['author']}, reviewed by {chk['reviewed_by']}", '  It does not cover: ' + '; '.join(chk['stated_limits']), '',
              'A design is checked against this baseline only by:  submit DESIGN.json   (a JSON object giving exactly the design-space parameters).',
              'The requirement, the limits, the load case, the design space and the check cannot be changed from here.',
              f"Only {c['responsible_engineer']['name']} can issue a revised baseline or accept a failure."]
        if c.get('supersedes'):
            s = c['supersedes']; L.insert(1, f"  THIS BASELINE SUPERSEDES {s['baseline_sha256'][:16]}… ({s.get('official_runs', '?')} official runs, {s.get('not_met', '?')} not met); "
                                            f"{s.get('unknown', '?')} unknown, {s.get('met', '?')} met.  Reason given: {s['reason']}")     # Amendment 4
        L[1:1] = alongside_lines(c)                                                                         # Amendment 9
        return '\n'.join(L)

    def status(self) -> str:
        runs, attempts = self.runs()
        L = [f"{self.root}", f"Official runs {runs['total']}: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown."]
        for a in attempts:
            r = a['result'] or {}
            what = '; '.join(f"{c['id']} {c['achieved']} vs {c['limit']} {c['units']}" for c in r.get('criteria', []) if c.get('achieved') is not None) or r.get('detail', '')
            L.append(f"  {a['aid']}  {OUTCOME_WORDS.get(a['outcome'], a['outcome']):<11} {r.get('reason_code', ''):<24} {what}")    # Amendment 9: MET, not PASS
        if not runs['PASS']:
            L.append('NOT VERIFIED: no design has met the declared check on this baseline.')
        L += met_lines(self.card, attempts)                                                                 # Amendment 9
        return '\n'.join(L)
