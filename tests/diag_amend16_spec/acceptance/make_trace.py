#!/usr/bin/env python3
"""Write trace.json: for every rule id with MUST / MUST NOT in sections 1 to 8 (and 11), SAF-1 to SAF-11, and the other
normative rules, the tests that cover it; and the rules not testable before an implementation exists, with why."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import acc  # noqa: E402
import rules as R  # noqa: E402
import run_acceptance as RA  # noqa: E402

V5_CHANGED = {
    'I-E-1/I-E-2/I-E-3/DL-3/11 (closes, EPOCH_STALE, MAILBOX_STATE_LOST)': ['S5-EPOCH-STALE-01', 'S5-EPOCH-FIRST-01', 'S5-REASON-MSL-01', 'C5-IE-01', 'S7-DL3-02'],
    'I-E-4 (unanswered EPOCH_OPEN re-sent; stale -> new challenge)': ['C5-IE-03', 'C5-IE-04'],
    'I-O-4/SAF-10/L-10 (the courier\'s own anchor)': ['C5-IO-04', 'C5-IO-04B', 'C5-IO-04C', 'S9-SAF-10'],
    'I-E-8 (wording)': ['C5-IE-02 (docstring only)'],
    'DL-2 and 7.4 (only statements refused at 7.4 answered again; refused statement kept without reveal, was F33)': ['S7-DL2-02', 'S7-DL2-03', 'S7-REFUSED-02'],
    'I-S-1 (statement only after receipts)': ['C5-IS-01', 'S7-DL3-01'],
    'E-Q-4 (drop before store, was F34)': ['S6-RETIRE-ALARM-01'],
    'every test builder of EPOCH_OPEN': ['fixtures/form3.py Driver.open_epoch carries `closes`'],
}
V6_CHANGED = {
    'I-O-4 rewritten (own anchor = highest verified witness checkpoint; never lowered; every reading; ROLLBACK/FORK)':
        ['C5-V6-ANCHOR-01 (the version-5 trace, rollback)', 'C5-V6-ANCHOR-02 (the same, fork)', 'C5-V6-ANCHOR-04 (INCREMENTAL, refusal does not move it)', 'C5-IO-04C (rules re-cited)'],
    'I-O-4a new (receipt beyond head, or receipted statement above the challenge anchor; alarm after EPOCH_OPEN)':
        ['C5-IO-04 (alarm is the item after EPOCH_OPEN added)', 'C5-IO-04B (rule and reason re-cited: the receipt, not the challenge anchor alone)', 'C5-V6-ANCHOR-03 (a refusal alone is no MAILBOX_ROLLBACK)'],
    'I-E-4 (own anchor kept through a new epoch)': ['C5-V6-ANCHOR-05'],
    'I-O-2 (one item at a time)': ['C5-V6-ONE-01', 'fixtures/netfix.py logs mailbox_begin'],
    'E-Q-4 (alarm bodies dropped only when the new alarm will be stored)': ['S6-RETIRE-ALARM-02'],
    'E-Q-4 (retirement where the last statement carries nothing)': ['not tested: a MAY; nothing an implementation must do'],
    'SAF-10, L-10 (reworded)': ['C5-V6-ANCHOR-01', 'C5-V6-ANCHOR-02', 'C5-IO-04C'],
    'header and results': ['rules.SPEC = version 6 and its SHA-256; SELF-ACC2-01 checks both'],
}

tests = RA.load_tests(os.path.join(HERE, 'tests'))
by_rule = {}
for tid, cls, m, fn, mod, fname in tests:
    for r in fn._acc['rules']:
        by_rule.setdefault(r, []).append(tid)
cov = lambda ids: {r: sorted(by_rule.get(r, [])) for r in ids}
must = cov(R.MUST)
out = {
    'acc2': acc.ACC2, 'spec': R.SPEC,
    'must_rules': must,
    'must_rules_without_a_test': sorted(r for r, t in must.items() if not t),
    'normative_rules': cov(R.NORMATIVE),
    'normative_rules_without_a_test': sorted(r for r in R.NORMATIVE if not by_rule.get(r)),
    'other_rule_ids_cited_by_tests': {r: sorted(t) for r, t in by_rule.items() if r not in R.MUST and r not in R.NORMATIVE},
    'not_testable_before_an_implementation': R.UNTESTABLE,
    'changed_for_version_5': V5_CHANGED,
    'changed_for_version_6': V6_CHANGED,
    'tests': {tid: {k: fn._acc[k] for k in ('rules', 'cap', 'decisions', 'catches', 'open_finding')} for tid, cls, m, fn, mod, fname in tests},
}
json.dump(out, open(os.path.join(HERE, 'trace.json'), 'w'), indent=1, sort_keys=False)
print('MUST without test:', out['must_rules_without_a_test'])
print('NORMATIVE without test:', out['normative_rules_without_a_test'])
print('tests:', len(tests))
