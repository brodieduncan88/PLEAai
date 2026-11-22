#!/usr/bin/env python3
"""TEST HARNESS ONLY: the service's own caller, for tests R14, R17, R18, R25 and R26.  Never deployed; never given to an assistant.

Amendment 17 (22 November 2026, D6) retired the first plug-in's command, verify_client.py, which held the gateway's database
credential in an assistant's workspace.  These five tests are about what the gate, its notices, its records and the witness do,
under the plain deployment (verify/deploy.py), and reached them through that command.  Through the front door they cannot all be
made: the front door refuses some of their designs before the gate sees them, words some answers its own way, and its deployment
admits other certificates.  So they reach the service here, by the first client's code exactly as it was at 1b132e2, run as a
separate process with a configuration the test writes.  It holds what the service's own role holds (CAP-DB): the gateway's
database credential and a client certificate.  The assistant's route is tested by R1 to R13 and R30 to R33 through the front door,
and by the front door's own suite.
"""
import argparse
import json
import pathlib
import sys
import urllib.error

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'verify'))   # test harness: the service's modules
from plea_gateway import (BudgetExhausted, GateHostClient, GateRefusedRun, Governor, GovernedError, Held, InProgress, OutcomeInvalid,   # noqa: E402
                          ReceiptInvalid, RemoteWitness, RequestKeyReused, Store, Stopped, TransportError, UnknownRoot, WitnessUnavailable)
from plea_gateway.tls import TLSClient                              # noqa: E402
from baseline import does_not_cover, face, root_for                  # noqa: E402
from verify_record import arguments_for, attempts_of, load_envelope, request_key   # noqa: E402


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
    def __init__(self, config_path):
        self.cfg = json.loads(pathlib.Path(config_path).read_text())
        base = pathlib.Path(config_path).resolve().parent
        self.path = lambda p: str(p if pathlib.Path(p).is_absolute() else base / p)
        self.envelope = load_envelope(self.path(self.cfg['baseline']), self.cfg['engineer_key'])
        self.card, self.baseline = self.envelope['card'], self.envelope['baseline_sha256']
        self.root = root_for(self.card)
        self.store = Store(self.cfg['local_dsn'])

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

    def submit(self, design) -> tuple[int, str]:
        args = arguments_for(self.baseline, design); key = request_key(args)
        with open(self.path(self.cfg.get('journal', 'submissions.jsonl')), 'a') as f:
            f.write(json.dumps(args) + '\n')                       # so an interrupted run can still be tied to what was sent
        try:
            verdict = self.governor().attempt(key, 'verify', **args)
        except UnknownRoot:
            return 4, 'REFUSED: this baseline has no budget at the control plane.  It was not provisioned by the responsible engineer.'
        except BudgetExhausted:
            return 4, 'REFUSED: the number of official runs allowed on this baseline is used up.  Nothing was run.'
        except Stopped:
            return 4, 'REFUSED: this baseline has been stopped (it was superseded or closed by the responsible engineer).  Nothing was run.'
        except Held:
            return 4, 'REFUSED: this baseline is on hold by the responsible engineer.  Nothing was run.'
        except InProgress:
            return 4, 'REFUSED: this design is already being verified.  Ask again for its result.'
        except GovernedError as exc:
            return 4, f'REFUSED: {exc.decision.code}.  Nothing was run.'
        except (GateRefusedRun, OutcomeInvalid, RequestKeyReused, ReceiptInvalid, PermissionError) as exc:
            return 4, f'REFUSED by the verification service ({type(exc).__name__}).  NOT VERIFIED.'
        except (WitnessUnavailable, TransportError, urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            return 4, f'The verification service could not be reached ({type(exc).__name__}).  NOT VERIFIED.  The run may be pending; ask again.'
        except RuntimeError:
            runs, _ = self.runs()
            return 3, ('UNKNOWN: THE RUN WAS INTERRUPTED\n\nThe verification service stopped while this design was being checked.  No verdict exists, the run is '
                       f'counted, and it will not be run again.  NOT VERIFIED.\nOfficial runs {runs["total"]} on this baseline: {runs["PASS"]} met, {runs["FAIL"]} not met, {runs["UNKNOWN"]} unknown.')
        runs, attempts = self.runs()
        aid = next((a['aid'] for a in attempts if a['request_key'] == key), None)
        return {'PASS': 0, 'FAIL': 2}.get(verdict.get('verdict'), 3), face(self.card, verdict, runs, aid)

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


def main():
    ap = argparse.ArgumentParser(description='Verify a design against the baselined requirement.')
    ap.add_argument('--config', required=True); ap.add_argument('action', choices=['show', 'submit', 'status']); ap.add_argument('design', nargs='?')
    a = ap.parse_args()
    try:
        client = Client(a.config)
    except (OSError, ValueError, KeyError) as exc:
        print(f'The verification client is not configured correctly: {exc}'); sys.exit(4)
    if a.action == 'show':
        print(client.show()); return
    if a.action == 'status':
        try:
            print(client.status())
        except UnknownRoot:
            print('This baseline has no budget at the control plane.'); sys.exit(4)
        return
    if not a.design:
        ap.error('submit needs a design file')
    try:
        design = json.loads(pathlib.Path(a.design).read_text())
    except (OSError, ValueError) as exc:
        print(f'{a.design} could not be read as JSON: {exc}.  Nothing was submitted.'); sys.exit(4)
    code, out = client.submit(design)
    print(out); sys.exit(code)


if __name__ == '__main__':
    main()
