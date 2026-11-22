#!/usr/bin/env python3
"""Retired by Amendment 17 (22 November 2026, D6 and D35).  This command refuses to run.

It was the first plug-in's assistant-side command: it held the gateway's database credential in the assistant's workspace
and named the baseline it ran against, so whoever held the workspace could run a design against another baseline's budget
(D5, shown by test F1) and leave a record unable to verify (F2).  The supported route is the front door alone: an
assistant's shell uses `front_client.py`, and a host application the MCP server `plea_verify_mcp.py`; neither holds a
database credential or names a baseline.  The part of this file the service itself uses is in `service_client.py`.

Its text as last released is in the repository's history, at `1b132e2`.
"""
import sys

WORDS = ('verify_client.py is retired (Amendment 17, 22 November 2026): it held the gateway\'s database credential in the '
         'assistant\'s workspace.  Use front_client.py with the job folder the responsible engineer enrolled, or the MCP '
         'server plea_verify_mcp.py.  Nothing was run.')


def main():
    print(WORDS, file=sys.stderr)
    sys.exit(4)


if __name__ == '__main__':
    main()
