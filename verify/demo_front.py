#!/usr/bin/env python3
"""The pump-station job through the MCP server: what a host application sees, and what it cannot do.

    python verify/demo_front.py      needs PostgreSQL with the PLEA schema and roles (top-level README.md, "Reproduce")

The job is the pump-station sub-main (verify/cases/pump-station-submain): no allowed cable meets the 5 % voltage-drop
limit; the best reaches 5.74 %.  This script is not an AI assistant.  It plays an assistant's host application: it
starts plea_verify_mcp.py with the job folder and nothing else, and makes tool calls.

Part 1, the three tools: the requirement as baselined, the best allowed design submitted (FAIL), and the same again.
Part 2, ways to change the question from the assistant's side: a size the requirement does not allow, a limit or a
baseline passed as an argument, a request written by hand that names a relaxed baseline, the job's certificate
tried on the witness service and the gate host, and a design the database could not store.
Part 3, the legitimate way: the engineer issues a revision allowing 120 mm2, with a reason, and moves the job to it.

It leaves a transcript and the records in outputs/verify_front_demo/.
"""
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'tests'))
import check_record      # noqa: E402
import deploy_front      # noqa: E402
import verify_ctl        # noqa: E402
from deploy_front import text_of                     # noqa: E402
from plea_gateway.tls import TLSClient               # noqa: E402

CASE = HERE / 'cases' / 'pump-station-submain'
OUT = HERE.parent / 'outputs' / 'verify_front_demo'
BEST = {'size_mm2': 95, 'install': 'buried', 'breaker_A': 125}


def first(result) -> str:
    return (text_of(result).splitlines() or [''])[0]


def main():
    import http.client
    import urllib.error
    import urllib.request
    from front_client import FrontClient
    shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
    lines = []

    def say(text=''):
        print(text, flush=True); lines.append(text)

    s = deploy_front.FrontServices(OUT / 'service').start()
    try:
        env = s.baseline(CASE, json.loads((CASE / 'card.json').read_text())); h = env['baseline_sha256']
        job = s.enrol('pump-station-17', h)
        say('SET UP  K. Dalton baselined the requirement and enrolled the job pump-station-17 for it.')
        say(f'  baseline {h[:16]}…; control cases at baselining: ' + ', '.join(f"{c['expect'].lower()} as expected" for c in env['controls_run']))
        say('  the assistant\'s side is given a folder holding: ' + ', '.join(sorted(p.name for p in job.iterdir())))

        m = s.mcp(job)
        say(); say('PART 1  The host application starts the MCP server with that folder and nothing else.')
        say('  tools offered: ' + ', '.join(t['name'] for t in m.tools()))
        shown = text_of(m.call('plea_show_requirement')).splitlines()
        say('  plea_show_requirement:'); [say('    ' + l[:150]) for l in shown[:2] + [l for l in shown if l.startswith('  voltage_drop') or l.startswith('  size_mm2')]]
        r = m.call('plea_submit_design', {'design': BEST})
        say('  plea_submit_design, the best allowed design (95 mm2 buried, 125 A):')
        [say('    ' + l[:170]) for l in text_of(r).splitlines() if l.startswith(('FAIL', 'Reason', 'Verdict')) or '->' in l]
        say(f'    marked as a tool error: {r["isError"]}.  As fields: outcome {r["structuredContent"]["outcome"]}, met {r["structuredContent"]["met"]}, run {r["structuredContent"]["aid"]}')
        again = m.call('plea_submit_design', {'design': BEST})
        say(f'  the same design again: {first(again)}  (the same run, {again["structuredContent"]["aid"]}; the check ran {len(s.ledger("called"))} time)')

        say(); say('PART 2  Ways to change the question from the assistant\'s side.')
        r = m.call('plea_submit_design', {'design': dict(BEST, size_mm2=120)}); say(f'  1  120 mm2, which the requirement does not allow:   {first(r)}')
        r = m.call('plea_submit_design', {'design': BEST, 'limit': '7.0'}); say(f'  2  a limit passed as an argument:                    {text_of(r)[:60]}…  (tool error: {r["isError"]})')
        relaxed = json.loads((CASE / 'card.json').read_text()); relaxed['criteria'][0]['limit'] = '7.0'; relaxed['job_note'] = 'a relaxed copy, baselined as new'
        hb = s.baseline(CASE, relaxed, alongside_reason='a relaxed copy, made for this demonstration of a caller naming another baseline')['baseline_sha256']   # Amendment 9: a second baseline of a requirement needs a reason
        r = m.call('plea_submit_design', {'design': BEST, 'baseline_sha256': hb}); say(f'  3  a relaxed baseline named as an argument:          {text_of(r)[:60]}…  (tool error: {r["isError"]})')
        c = FrontClient(job); conn = http.client.HTTPSConnection(c.host, c.port, context=c.ctx, timeout=60)
        conn.request('POST', '/submit', body=json.dumps({'design': BEST, 'baseline_sha256': hb}), headers={'Content-Type': 'application/json'}); resp = conn.getresponse(); body = json.loads(resp.read()); conn.close()
        say(f'  4  the same, in a request written by hand:           HTTP {resp.status} {body["refused"]}: {body["text"][:86]}')
        reach = []
        for name, port in (('witness service', s.ports['witness']), ('gate host', s.ports['host'])):
            try:
                urllib.request.urlopen(f'https://127.0.0.1:{port}/pubkey', timeout=20, context=TLSClient(s.pki['ca'], str(job / 'job.crt'), str(job / 'job.key')).context()); reach.append(f'{name} answered')
            except urllib.error.HTTPError as exc:
                reach.append(f'{name} HTTP {exc.code}')
        say(f'  5  the job\'s certificate tried on the service itself: {", ".join(reach)}')
        r = m.call('plea_submit_design', {'design': dict(BEST, install='buried\u0000')}); say(f'  6  a design the database could not store:            {text_of(r)}')
        status = m.call('plea_status')
        say('  plea_status:'); [say('    ' + l[:150]) for l in text_of(status).splitlines()[1:]]
        record = s.record(h); ok, checks, summary = check_record.verify(record, s.keys)
        (OUT / 'record_revA.json').write_text(json.dumps(record, indent=1) + '\n'); (OUT / 'keys.json').write_text(json.dumps(s.keys, indent=1) + '\n')
        okb, _, sb = check_record.verify(s.record(hb), s.keys)
        say(f"  record of the job's baseline: official runs {summary['official_runs']}, met {summary['met']}, not met {summary['not_met']}, unknown {summary['unknown']}.  "
            f"Notices in K. Dalton's inbox: {len(s.inbox(h))}.  Verifies offline: {ok}.  Status: {summary['status']}.")
        say(f"  record of the relaxed copy:   official runs {sb['official_runs']}.  Notices: {len(s.inbox(hb))}.")

        say(); say('PART 3  The legitimate way.  K. Dalton decides to change the terminals and issues revision B allowing 120 mm2.')
        draft = json.loads((CASE / 'card.json').read_text())
        draft['requirement'] = dict(draft['requirement'], revision='B'); draft['design_space']['size_mm2']['choice'] = [25, 35, 50, 70, 95, 120]
        reason = 'Terminals at both ends to be replaced to accept 120 mm2 (change request CR-112, approved by the asset owner).'
        env_b = verify_ctl.revise(s.home, CASE, draft, s.engineer, h, reason); hrev = env_b['baseline_sha256']
        r = m.call('plea_submit_design', {'design': dict(BEST, size_mm2=70)}); say(f'  a further run on revision A: {text_of(r)[:112]}  (tool error: {r["isError"]})')
        try:
            s.rebind('pump-station-17', hb); moved = 'moved'
        except Exception as exc:
            moved = f'refused: {str(exc)[:118]}…'
        say(f'  moving the job to the relaxed copy instead: {moved}')
        s.rebind('pump-station-17', hrev); say('  K. Dalton moves the job to revision B.')
        shown = text_of(m.call('plea_show_requirement')).splitlines()
        say('  plea_show_requirement now begins:'); [say('    ' + l[:230]) for l in shown[:2]]
        r = m.call('plea_submit_design', {'design': dict(BEST, size_mm2=120)}); say(f'  plea_submit_design, 120 mm2 buried, 125 A: {first(r)}')
        record_b = s.record(hrev); (OUT / 'record_revB.json').write_text(json.dumps(record_b, indent=1) + '\n')
        ok_b, checks_b, summary_b = check_record.verify(record_b, s.keys)
        say('  the offline check of revision B\'s record says:')
        for line in check_record.render(ok_b, checks_b, summary_b).splitlines():
            if line.strip().startswith(('CHANGED AFTER', 'RECORD', 'STATUS')):
                say('    ' + line.strip())
        m.close()
        say(); say('One machine does not show separation: here the service, its keys and this script share one account.')
        say('MCP delivers a result to the host application; it does not make the host show it.  The record and the engineer\'s notice do not depend on that.')
        say(f'Left in {OUT.relative_to(HERE.parent)}/: record_revA.json, record_revB.json, keys.json, transcript.txt')
    finally:
        s.stop()
    (OUT / 'transcript.txt').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
