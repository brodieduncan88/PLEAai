"""The rule catalogue the suite is traced against: Amendment 16 specification, VERSION 6
(`spec/SPEC_v6_as_sent_to_review.md`, 989 lines, SHA-256 8eb8fe4b7ecb869670bba85a359093ee2817cf02fc77a8a150a4667c2509f836).

MUST: the rule ids of sections 1 to 8 (and section 11) whose text carries MUST or MUST NOT, plus SAF-1 to SAF-11.
NORMATIVE: rule ids without the word MUST whose text still says what the system does (tested and traced too).
UNTESTABLE: rules no test against an implementation can establish before (or at all without) a deployment, with why.
DECISION: the owner's decisions of 21 November (section 13) each rule serves.
"""
SPEC = {'version': 6, 'file': 'spec/SPEC_v6_as_sent_to_review.md', 'lines': 989,
        'sha256': '8eb8fe4b7ecb869670bba85a359093ee2817cf02fc77a8a150a4667c2509f836'}

MUST = ['K-CAP-1', 'ACC-1', 'ACC-2', 'ACC-5', 'K-CNT-1', 'K-CNT-2', 'K-CNT-3', 'K-CNT-4', 'K-1', 'K-3', 'K-4', 'K-N-2',
        'O-2', 'O-4', 'O-R-4', 'O-C-3', 'O-W-1', 'O-L-2', 'I-2', 'I-E-4', 'I-E-5', 'I-O-4', 'E-Q-3a', 'E-Q-4', 'E-R-1',
        'E-X-3', 'E-X-4', 'M-T-1', 'M-T-2', '11-LIMITS', '11-EARLIER-FORMS'] + [f'SAF-{i}' for i in range(1, 12)]

NORMATIVE = ['D-2', 'D-3', 'D-5', 'D-6', 'D-12', 'K-CNT-5', 'K-CONFLICT', 'K-UNKNOWN-VERDICT', 'K-FENCE', 'K-PHASE',
             'K-EARLY', 'K-NONCE', 'K-DIGEST', 'K-CLAIM', 'K-MISSING', 'K-2', 'K-5', 'K-6', 'K-7', 'K-BEL-1', 'K-BEL-2',
             'K-BEL-3', 'K-BEL-4', '3.4', 'K-N-1', 'K-N-3', 'K-REC-1', 'K-REC-2', 'K-REC-3', 'K-REC-4',
             'O-1', 'O-3', 'O-5', 'O-6', 'O-7', 'O-R-1', 'O-R-2', 'O-R-3', '4.3', 'O-S-1', 'O-C-1', 'O-C-2', 'O-C-4',
             'O-P-1', 'O-P-2', 'O-W-2', 'O-L-1', 'O-L-3', 'I-1', 'I-3', 'I-4', 'I-ID-1', 'I-ID-2', 'I-ID-3', 'I-ID-4',
             'I-K-1', 'I-E-1', 'I-E-2', 'I-E-3', 'I-E-6', 'I-E-7', 'I-E-8', 'I-E-9', 'I-S-1', 'I-S-2', 'I-S-3',
             'I-O-1', 'I-O-2', 'I-O-3', 'I-O-4a', 'I-O-5', 'I-O-6', 'I-O-7', 'I-O-8', 'E-1', 'E-2', 'E-3', 'E-Q-1', 'E-Q-2',
             'E-Q-3', 'E-Q-5', 'E-Q-6', 'E-R-2', 'E-B-1', 'E-B-2', 'E-B-3', 'E-B-4', 'E-B-5', 'E-B-6', 'E-X-1', 'E-X-2',
             'E-X-5', 'M-T-3', 'M-T-4', 'M-T-5', 'M-T-6', 'M-K-1', 'M-K-2', 'M-K-3', 'M-K-4', 'M-K-5', 'M-K-6',
             'DL-1', 'DL-2', 'DL-3', 'DL-4', 'DL-5', 'DL-6', 'M-D-1', 'M-D-2', '7.4', 'ST-1', 'ST-2', 'ST-3', 'ST-4',
             'ST-5', 'ST-6', 'ST-7', 'ST-8', 'ST-9', 'M-S-1', 'M-S-2', 'C-1', 'C-1.1', 'C-1.2', 'C-1.3', 'C-1.4',
             'C-1.5', 'C-1.6', 'C-1.7', 'C-1.8', 'C-2', 'C-3', 'C-4', '8.2', 'C-S-1', 'C-S-2', 'C-S-3',
             'N-1', 'N-2', 'N-3', 'N-4', 'N-5', 'N-6', '11-INTERFACE', '11-CLIENTS']

UNTESTABLE = {
    'ACC-1': 'an obligation on whoever claims a deployment complies (B-1, B-2 resolved): organisational, no behaviour of '
             'the code to test; the suite prints ACC-2 instead and makes no compliance claim',
    'E-Q-3a': 'an obligation on the operator\'s sizing of NOTICE_QUOTA and ALARM_RESERVE; the code is not required to '
              'refuse a smaller value, so there is nothing an implementation does or fails to do. Its consequences '
              '(E-X-4, N-6) are tested',
    'K-3/P-KEYS': 'that the engineer configures the witness\'s pinned gate keys: an operational precondition. K-CNT-4\'s '
                  'detection of a difference is tested',
    'M-T-1 (real suspension)': 'the behaviour of CLOCK_BOOTTIME across a REAL suspension (N-4) cannot be produced in a test; '
                               'tested through the injected clock and a static source check only',
    'M-T-7/L-9': 'a pause from outside the machine is invisible by the text\'s own account',
    'E-X-2 (bound by provisioning)': 'argued from the store\'s accounting, not testable at the mailbox interface',
    'I-E-9': 'by the text, the mailbox cannot check that a reading was from 0: there is nothing to test at the mailbox; '
             'the courier side (I-E-5) is tested',
    'ACC-2 (production)': 'no test can establish the production contract (N-5); the runner enforces the statement',
    'O-3 (clearing an anchor)': 'outside the specification by its own words',
    'E-R-1': 'a rule for "a reader" of GET /evidence; the specification names no reading component of the implementation '
             '(the courier stores evidence, it does not read it back), so the seam has nothing to bind. The suite\'s own '
             'reader applies it (S6-OBJ-01, S6-READ-01)',
    'C-2': 'a statement of what COVERED means, not a behaviour; each of its clauses is tested through C-1.1 to C-1.8, ST-1 to ST-9',
    'K-REC-4': 'a statement that records and notices are two channels; nothing to test beyond K-REC-1 (the record fails on its reports)',
    'I-O-3 (head that IS a position of the courier\'s chain)': 'producing a genuine 409 CHAIN_POSITION whose head is behind the '
             'courier inside its own chain needs either the mailbox\'s key or a crash between store and answer; no seam for '
             'either was assumed. The other branch (not a position: state lost) is tested (C5-IE-02). Testable once a crash '
             'injection seam exists',
}

DECISION_OF = [
    (1, ('K-', 'D-', '3.', 'K-CAP-1')),
    (2, ('I-E-', 'I-ID-', 'I-O-', 'I-S-', 'I-K-', 'I-1', 'I-2', 'I-3', 'I-4', 'ST-5', 'ST-6', 'SAF-4', 'SAF-5', 'SAF-6', 'SAF-10')),
    (3, ('E-', 'DL-3', 'DL-4', 'M-D-', 'O-W-1', 'SAF-2', 'SAF-11', 'O-L-')),
    (4, ('ACC-', 'N-5')),
    (5, ('C-', 'O-C-', '4.3', 'O-S-', 'O-3', 'O-4', 'ST-6', 'O-R-', 'O-1', 'O-2', 'O-5', 'O-6', 'O-7', 'O-P-', 'O-W-2', '8.', 'M-T-', 'M-K-',
         'ST-', 'DL-', '7.4', 'M-S-', 'SAF-1', 'SAF-3', 'SAF-7', 'SAF-8', 'SAF-9', 'N-', '11-')),
    (6, ('ACC-2',)),
]


def decisions_for(rules):
    out = set()
    for r in rules:
        for d, prefixes in DECISION_OF:
            if any(r == p or r.startswith(p) for p in prefixes):
                out.add(d)
    return sorted(out) or [5]
