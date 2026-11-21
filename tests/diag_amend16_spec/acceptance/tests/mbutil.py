"""Helpers shared by the mailbox tests (sections 5 to 9 at the mailbox's interface)."""
import json
import os
import re

from fixtures.crypto import canonical


def refused(tc, st, body, d, *checks, msg=''):
    """A 422 naming at least these checks of 7.4."""
    tc.assertEqual(st, 422, f'{msg}: expected 422 (7.4), got {st} {str(body)[:300]}')
    got = d.c.failed_checks(body)
    for c in checks:
        tc.assertIn(c, got, f'{msg}: the 422 does not name {c}; it names {sorted(got)}')


def error(tc, st, body, d, status, code, msg=''):
    tc.assertEqual(st, status, f'{msg}: expected {status} {code}, got {st} {str(body)[:300]}')
    if code:
        tc.assertEqual(d.c.error(body), code, f'{msg}: expected the answer to name {code}, got {str(body)[:300]}')


def head_k(d):
    """The k of the mailbox's head for the open chain epoch, from a fresh challenge."""
    ch = d.challenge()
    h = d.c.ch_head(ch)
    return (h[1] if h else 0), ch


def store_text(store_dir):
    """Every byte of the mailbox's durable store, for searching (a statement's reveal must not be in it)."""
    out = []
    for root, _dirs, files in os.walk(store_dir):
        for f in files:
            try:
                with open(os.path.join(root, f), 'rb') as fh:
                    out.append(fh.read())
            except OSError:
                pass
    return b'\n'.join(out)


CLAIM_WORDS = re.compile(r'\b(guarantee[sd]?|will be (notified|told|covered)|notif(y|ied) by|permanent(ly)?|forever|'
                         r'always (covered|held)|is correct|verdict (is )?correct|still covered|live(ness)? (is )?guaranteed)\b', re.I)
FAIL_WORDS = re.compile(r'\b(FAIL|FAILED|failed|run failed|did not pass)\b')
