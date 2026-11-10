#!/usr/bin/env python3
"""The holdout: its manifest, its public id list, its sealed labels, and the rules every submission is checked by.

    holdout.py init DIR --name NAME --labels labels.csv [--decimals 2] [--classes a,b,c]
                        [--max-bytes 20971520] [--max-rows 1000000] [--max-unscored 10] [--max-requests 60]

init reads an owner's labels file (CSV, header "id,label") and writes three files into DIR:

  manifest.json   public.  The holdout's name, metric, decimals, row count, the hash of the id list, the allowed
                  classes, the limits, and the hash of the sealed labels file.  Its own hash (sha256 of its canonical
                  JSON) is carried in every signed result, so a reader can tell which rules a score was produced under.
  ids.txt         public.  One id per line, in the owner's order.
  labels.sealed   mode 0600.  A first line "#salt,<64 hex>" (one random 32-byte value per holdout), then "id,label"
                  rows.  The salt stops the labels being guessed from the hash in the manifest.  Nothing else holds it.

A valid submission is a UTF-8 CSV with the header "id,prediction", exactly `rows` data rows of two fields, every public
id exactly once, every prediction one of the manifest's classes, and a size within the limit.  validate() checks that
from public information only (the manifest and the id list), in a fixed order, and names the first failure with one of
seven codes.  It never opens the labels.

The score is accuracy, correct rows over total rows, rounded to `decimals` places in whole numbers with ties to even,
as text: 87 of 100 is "0.87", 2 of 3 is "0.67".  correct() compares every row and never stops early.

Standard library only.  The scoring tool, the front door and the tests import this; the offline verifier does not.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import pathlib
import re
import secrets

CODES = ('TOO_LARGE', 'NOT_UTF8', 'BAD_HEADER', 'ROW_COUNT', 'UNKNOWN_ID', 'DUPLICATE_ID', 'BAD_CLASS')
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')      # holdout and submitter names: no separators, no traversal
HEX64 = re.compile(r'^[0-9a-f]{64}$')
RESERVED = ('governor', 'witness', 'host', 'vault')            # the deployment's own certificate names
LIMITS = {'max_bytes': 20 * 1024 * 1024, 'max_rows': 1_000_000, 'max_unscored': 10, 'max_requests_per_minute': 60}


class LabelsDamaged(Exception):
    """The sealed labels file is missing or no longer hashes to the manifest's labels_sha256."""


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def round_score(correct: int, rows: int, decimals: int) -> str:
    """correct/rows to `decimals` places, ties to even, in whole numbers; returned as text."""
    if rows <= 0 or not 0 <= correct <= rows or decimals < 0:
        raise ValueError('round_score: need 0 <= correct <= rows, rows > 0, decimals >= 0')
    scale = 10 ** decimals
    q, r = divmod(correct * scale, rows)
    if 2 * r > rows or (2 * r == rows and q % 2 == 1):
        q += 1
    return str(q) if decimals == 0 else f'{q // scale}.{q % scale:0{decimals}d}'


class Holdout:
    def __init__(self, directory):
        self.dir = pathlib.Path(directory)
        self.manifest = json.loads((self.dir / 'manifest.json').read_text())
        self.manifest_sha256 = sha256_hex(canonical(self.manifest).encode())
        ids_bytes = (self.dir / 'ids.txt').read_bytes()
        if sha256_hex(ids_bytes) != self.manifest['ids_sha256']:
            raise ValueError('ids.txt does not hash to the manifest\'s ids_sha256')
        self.ids = ids_bytes.decode().split('\n')[:-1] if ids_bytes.endswith(b'\n') else ids_bytes.decode().split('\n')
        self.idset = frozenset(self.ids)
        self.classes = frozenset(self.manifest['classes'])
        self.rows, self.decimals, self.limits = self.manifest['rows'], self.manifest['decimals'], self.manifest['limits']
        self.name = self.manifest['holdout']
        if len(self.ids) != self.rows or len(self.idset) != self.rows:
            raise ValueError('ids.txt does not hold exactly `rows` distinct ids')

    def root(self, submitter: str) -> str:
        return f'{self.name}/{submitter}'

    def upload_path(self, submitter: str, sha256: str) -> pathlib.Path:
        if not NAME.match(submitter) or not HEX64.match(sha256):
            raise ValueError('submitter or hash is not well formed')
        return self.dir / 'uploads' / submitter / f'{sha256}.csv'

    def validate(self, data: bytes) -> tuple[str | None, dict]:
        """(None, {id: prediction}) for a valid submission, else (code, {}).  Public information only."""
        if len(data) > self.limits['max_bytes']:
            return 'TOO_LARGE', {}
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            return 'NOT_UTF8', {}
        try:
            rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
        except csv.Error:
            return 'ROW_COUNT', {}
        if not rows or rows[0] != ['id', 'prediction']:
            return 'BAD_HEADER', {}
        body = rows[1:]
        if len(body) != self.rows or any(len(r) != 2 for r in body):
            return 'ROW_COUNT', {}
        predictions = {}
        for rid, prediction in body:
            if rid not in self.idset:
                return 'UNKNOWN_ID', {}
            if rid in predictions:
                return 'DUPLICATE_ID', {}
            if prediction not in self.classes:
                return 'BAD_CLASS', {}
            predictions[rid] = prediction
        return None, predictions

    def labels(self) -> dict:
        """Open the sealed labels.  Only the scoring tool calls this, and only after validate() has passed."""
        try:
            data = (self.dir / 'labels.sealed').read_bytes()
        except OSError as exc:
            raise LabelsDamaged(str(exc))
        if sha256_hex(data) != self.manifest['labels_sha256']:
            raise LabelsDamaged('labels.sealed does not hash to the manifest\'s labels_sha256')
        rows = list(csv.reader(io.StringIO(data.decode('utf-8'), newline='')))
        return {rid: label for rid, label in rows[2:]}          # after the salt line and the header

    def correct(self, predictions: dict, labels: dict) -> int:
        """Every row is compared; there is no early exit, so the time taken does not depend on where the errors are."""
        n = 0
        for rid in self.ids:
            n += 1 if predictions[rid] == labels[rid] else 0
        return n

    def result(self, correct: int, submission_sha256: str) -> dict:
        """The object the gate host returns and signs.  Nothing in it depends on the labels except the score."""
        return {'score': round_score(correct, self.rows, self.decimals), 'metric': self.manifest['metric'], 'decimals': self.decimals,
                'rows': self.rows, 'submission_sha256': submission_sha256, 'manifest_sha256': self.manifest_sha256}


def init(directory, name: str, labels_csv, decimals: int = 2, classes=None, limits: dict | None = None) -> Holdout:
    if not NAME.match(name):
        raise ValueError(f'holdout name {name!r}: letters, digits, "_", "." and "-" only, at most 64')
    rows = list(csv.reader(io.StringIO(pathlib.Path(labels_csv).read_text(encoding='utf-8'), newline='')))
    if not rows or rows[0] != ['id', 'label'] or len(rows) < 2 or any(len(r) != 2 or not r[0] or not r[1] for r in rows[1:]):
        raise ValueError('the labels file needs the header "id,label" and at least one "id,label" row, no empty fields')
    ids = [r[0] for r in rows[1:]]
    if len(set(ids)) != len(ids) or any('\n' in i or '\r' in i for i in ids):
        raise ValueError('ids must be distinct and hold no line breaks')
    found = sorted({r[1] for r in rows[1:]})
    classes = sorted(classes) if classes else found
    if not set(found) <= set(classes):
        raise ValueError('a label is not among --classes')
    lim = dict(LIMITS, **(limits or {}))
    if len(ids) > lim['max_rows']:
        raise ValueError(f'{len(ids)} rows is over the max_rows limit of {lim["max_rows"]}')
    d = pathlib.Path(directory); d.mkdir(parents=True, exist_ok=True); (d / 'uploads').mkdir(exist_ok=True)
    out = io.StringIO(newline='')
    w = csv.writer(out, lineterminator='\n'); w.writerow(['#salt', secrets.token_hex(32)]); w.writerow(['id', 'label']); w.writerows(rows[1:])
    sealed = out.getvalue().encode('utf-8')
    sealed_path = d / 'labels.sealed'
    fd = os.open(sealed_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)       # never overwrite a holdout's labels
    with os.fdopen(fd, 'wb') as f:
        f.write(sealed)
    ids_bytes = ('\n'.join(ids) + '\n').encode('utf-8')
    (d / 'ids.txt').write_bytes(ids_bytes)
    manifest = {'version': 1, 'holdout': name, 'metric': 'accuracy', 'decimals': decimals, 'rows': len(ids), 'ids_sha256': sha256_hex(ids_bytes),
                'classes': classes, 'labels_sha256': sha256_hex(sealed), 'limits': lim}
    (d / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
    return Holdout(d)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('init'); i.add_argument('dir'); i.add_argument('--name', required=True); i.add_argument('--labels', required=True)
    i.add_argument('--decimals', type=int, default=2); i.add_argument('--classes', help='comma-separated; default: the classes found in the labels')
    i.add_argument('--max-bytes', type=int); i.add_argument('--max-rows', type=int); i.add_argument('--max-unscored', type=int); i.add_argument('--max-requests', type=int)
    a = ap.parse_args()
    limits = {k: v for k, v in (('max_bytes', a.max_bytes), ('max_rows', a.max_rows), ('max_unscored', a.max_unscored),
                                ('max_requests_per_minute', a.max_requests)) if v is not None}
    h = init(a.dir, a.name, a.labels, a.decimals, a.classes.split(',') if a.classes else None, limits)
    print(json.dumps({'holdout': h.name, 'rows': h.rows, 'classes': sorted(h.classes), 'manifest_sha256': h.manifest_sha256}))


if __name__ == '__main__':
    main()
