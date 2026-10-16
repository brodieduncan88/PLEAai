"""Crash injection for the chaos run: a process dies, without cleanup, at a named point.

PLEA_CRASH_AT=<label> makes crash_point(label) call os._exit(137).  The server rolls back the open transaction
when the connection drops, which is exactly what a real crash does.
"""
import os

CRASH_POINTS = ('after_lock', 'after_decide', 'after_attempts', 'after_audit', 'before_commit', 'after_commit')


def crash_point(label: str) -> None:
    if os.environ.get('PLEA_CRASH_AT') == label:
        os._exit(137)
