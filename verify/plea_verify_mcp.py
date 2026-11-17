#!/usr/bin/env python3
"""The verification service as three MCP tools, for an assistant's host application.

    plea_verify_mcp.py --job-dir DIR          (or PLEA_JOB_DIR=DIR)

    plea_show_requirement   read-only: the requirement as the responsible engineer baselined it
    plea_submit_design      {"design": {...}}: one official run, decided and signed by the verification service
    plea_status             read-only: every official run so far, and whether any design has met the check

and one read-only resource, plea://baseline, the signed baseline itself.

This process is a relay and nothing more.  It holds the job folder front_ctl.py enrol wrote: the service's address,
the authority's certificate, and the job's certificate and key.  It holds no database credential and no signing key,
it keeps no state between calls, and it decides nothing: every answer is the verification service's (front_door.py),
passed on.  There is no tool here that baselines, revises, acknowledges, builds a record, or names a baseline, a
limit, a check or a run, and plea_submit_design accepts no argument but the design.

One tool call is one HTTPS request.  Nothing here retries.  If the service cannot be reached the call says so; sending
the same design again is safe, because the service answers from the verdict it already has and never runs the check
twice.

A FAIL is not a tool error.  A pass (the declared check met), a FAIL and an UNKNOWN are all the service working: the verdict comes first in the text
and again in structuredContent, and isError is false.  isError is true only when nothing was decided: the call was
malformed, the service refused it (stopped, held, exhausted, not enrolled), or the service could not be reached.

What this cannot do.  MCP delivers a tool's result to the host application; it does not make the host show it, and
it does not make an assistant repeat it truthfully.  The failure does not depend on either: the service keeps the
signed verdict and sends a FAIL or UNKNOWN to the responsible engineer itself.

Protocol.  stdio, one JSON-RPC 2.0 message per line.  Both forms are served: the `initialize` handshake of revisions
2024-11-05 to 2025-11-25, and the per-request metadata of revision 2026-07-28 (with server/discover).

Standard library only; it needs front_client.py beside it.
"""
import argparse
import json
import os
import pathlib
import ssl
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from front_client import FrontClient, Unreachable, unreachable_text   # noqa: E402

LEGACY = ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05')     # revisions that open with `initialize`
MODERN = ('2026-07-28',)                                              # revisions that carry their version on every request
META = 'io.modelcontextprotocol/'
SERVER = {'name': 'plea-verification', 'version': '0.1.0'}
CAPABILITIES = {'tools': {}, 'resources': {}}
BASELINE_URI = 'plea://baseline'
MAX_LINE = 1024 * 1024

INSTRUCTIONS = ('This server relays to an engineering verification service.  The requirement, its limits, the load case, the design space and the check were fixed '
                'by the responsible engineer and cannot be changed or chosen here.  Read the requirement with plea_show_requirement, then submit a design with '
                'plea_submit_design.  The service, not the assistant, decides whether the declared check was met, not met (FAIL) or could not be decided (UNKNOWN).  '
                'Report a pass as "declared check met", with what the check does not cover: it says what the declared check returned against the limits, not that '
                'the check is correct, the requirement complete or the design safe.  A FAIL or UNKNOWN is a result to report as it stands, with its reason; it is '
                'recorded, and the service writes a notice of it for the responsible engineer.  UNKNOWN is never a pass.')

NO_ARGUMENTS = {'type': 'object', 'properties': {}, 'additionalProperties': False}
TOOLS = [
    {'name': 'plea_show_requirement', 'title': 'Show the baselined requirement',
     'description': ('Show the requirement exactly as the responsible engineer baselined it: the statement, the acceptance limits, the load case, the design space '
                     '(what may be varied) and the declared check with what it does not cover.  Read-only.  Call it before proposing a design.  Nothing shown '
                     'can be changed from here.'),
     'inputSchema': NO_ARGUMENTS,
     'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}},
    {'name': 'plea_submit_design', 'title': 'Submit a design for an official verification run',
     'description': ('Submit one design for an official run against the baselined requirement.  `design` is an object giving exactly the design-space parameters '
                     'that plea_show_requirement lists.  The verification service runs the declared check once and returns its signed verdict: declared check met '
                     '(signed as PASS), given with what the check does not cover and not as a statement that the check is correct; FAIL, with each limit and the '
                     'value achieved; or UNKNOWN, no verdict and never a pass.  Every run is counted and kept on the record, and the service writes a notice of a FAIL or '
                     'UNKNOWN for the responsible engineer.  The same design sent again returns the same verdict '
                     'without a second run.  The requirement, the limits, the load case, the design space and the check cannot be set here.  Report the verdict '
                     'as returned.'),
     'inputSchema': {'type': 'object', 'properties': {'design': {'type': 'object', 'description': 'The design-space parameters and their values, and nothing else.'}},
                     'required': ['design'], 'additionalProperties': False},
     'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}},
    {'name': 'plea_status', 'title': 'Show the official runs so far',
     'description': ('List every official run so far on this job\'s baseline, each with its verdict and reason, and say whether any design has met the declared '
                     'check, and what the check does not cover.  Read-only.'),
     'inputSchema': NO_ARGUMENTS,
     'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}},
]
NAMES = tuple(t['name'] for t in TOOLS)


class RpcError(Exception):
    def __init__(self, code: int, message: str, data=None):
        super().__init__(message); self.code, self.message, self.data = code, message, data


def tools_for(version: str) -> list:
    """The same three tools for every revision; fields a revision does not define are left out."""
    drop = {'2024-11-05': ('title', 'annotations'), '2025-03-26': ('title',)}.get(version, ())
    return [{k: v for k, v in t.items() if k not in drop} for t in TOOLS]


class Server:
    def __init__(self, client: FrontClient):
        self.client = client
        self.legacy = None                                  # the revision an `initialize` handshake settled on, for this process

    # ------------------------------------------------------------------ the three tools
    @staticmethod
    def _result(text: str, structured, is_error: bool, with_structured: bool) -> dict:
        content = [{'type': 'text', 'text': text}]
        out = {'content': content, 'isError': is_error}
        if with_structured and structured is not None:
            content.append({'type': 'text', 'text': json.dumps(structured, sort_keys=True)})    # the same fields as text, for hosts that pass on text only
            out['structuredContent'] = structured
        return out

    def call(self, name, arguments, with_structured: bool) -> dict:
        if name not in NAMES:
            raise RpcError(-32602, f'Unknown tool: {name}')
        if arguments is None:
            arguments = {}
        if name == 'plea_submit_design':
            if not isinstance(arguments, dict) or set(arguments) != {'design'} or not isinstance(arguments['design'], dict):
                return self._result('Nothing was sent.  plea_submit_design takes exactly one argument, `design`: an object of the design-space parameters.  '
                                    'It cannot name a baseline, a limit, a check or a run.', {'refused': 'BAD_ARGUMENTS'}, True, with_structured)
            ask = lambda: self.client.submit(arguments['design'])
        else:
            if arguments != {}:
                return self._result(f'Nothing was sent.  {name} takes no arguments.', {'refused': 'BAD_ARGUMENTS'}, True, with_structured)
            ask = self.client.requirement if name == 'plea_show_requirement' else self.client.status
        try:
            status, out = ask()                             # one request; no retry
        except Unreachable as exc:
            return self._result(unreachable_text(exc), {'refused': 'UNREACHABLE'}, True, with_structured)
        text = out.get('text') if isinstance(out.get('text'), str) else json.dumps(out)
        return self._result(text, {k: v for k, v in out.items() if k not in ('text', 'exit')}, status != 200, with_structured)

    def read_baseline(self, uri, legacy: bool) -> dict:
        if uri != BASELINE_URI:
            raise RpcError(-32002 if legacy else -32602, 'Resource not found', {'uri': uri})
        try:
            status, out = self.client.baseline()
        except Unreachable as exc:
            raise RpcError(-32603, unreachable_text(exc))
        if status != 200:
            raise RpcError(-32603, out.get('text') or 'the verification service refused')
        return {'contents': [{'uri': BASELINE_URI, 'mimeType': 'application/json', 'text': json.dumps(out, indent=1)}]}

    # ------------------------------------------------------------------ JSON-RPC
    def handle(self, msg):
        """The reply to one message, or None for a notification."""
        if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0' or not isinstance(msg.get('method'), str):
            if isinstance(msg, dict) and 'method' not in msg and ('result' in msg or 'error' in msg):
                return None                                 # a response: this server sends no requests, so none is expected
            return self._error(msg.get('id') if isinstance(msg, dict) else None, -32600, 'Invalid Request')
        method, rid = msg['method'], msg.get('id')
        if 'id' not in msg:
            return None                                     # notifications/initialized, notifications/cancelled, and any other
        if not isinstance(rid, (str, int)) or isinstance(rid, bool):
            return self._error(None, -32600, 'Invalid Request: the id must be a string or an integer')
        params = msg.get('params', {})
        if not isinstance(params, dict):
            return self._error(rid, -32602, 'Invalid params')
        try:
            return self._ok(rid, self._dispatch(method, params))
        except RpcError as exc:
            return self._error(rid, exc.code, exc.message, exc.data)
        except Exception as exc:                            # never a traceback on stdout
            print(f'plea_verify_mcp: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
            return self._error(rid, -32603, 'Internal error')

    def _dispatch(self, method: str, params: dict) -> dict:
        meta = params.get('_meta') if isinstance(params.get('_meta'), dict) else {}
        version = meta.get(META + 'protocolVersion')
        if method == 'initialize':                          # the handshake of the earlier revisions
            asked = params.get('protocolVersion')
            self.legacy = asked if asked in LEGACY else LEGACY[0]
            return {'protocolVersion': self.legacy, 'capabilities': CAPABILITIES, 'serverInfo': SERVER, 'instructions': INSTRUCTIONS}
        if version is not None:                             # a request that carries its own version: served on its own
            if version not in MODERN:
                raise RpcError(-32022, 'Unsupported protocol version', {'supported': list(MODERN + LEGACY), 'requested': version})
            if not isinstance(meta.get(META + 'clientCapabilities'), dict):
                raise RpcError(-32602, f'Invalid params: _meta must carry {META}clientCapabilities')
            return dict(self._serve(method, params, version, modern=True), resultType='complete', _meta={META + 'serverInfo': SERVER})
        if method == 'ping':
            return {}
        if self.legacy is None:
            raise RpcError(-32600, f'Invalid Request: send initialize first ({", ".join(LEGACY)}), or carry {META}protocolVersion in _meta ({", ".join(MODERN)})',
                           {'supported': list(MODERN + LEGACY)})
        return self._serve(method, params, self.legacy, modern=False)

    def _serve(self, method: str, params: dict, version: str, modern: bool) -> dict:
        if method == 'ping':
            return {}
        if method == 'server/discover' and modern:
            return {'supportedVersions': list(MODERN + LEGACY), 'capabilities': CAPABILITIES, 'instructions': INSTRUCTIONS}
        if method == 'tools/list':
            return {'tools': tools_for(version)}
        if method == 'tools/call':
            return self.call(params.get('name'), params.get('arguments'), with_structured=version >= '2025-06-18')
        if method == 'resources/list':
            return {'resources': [{'uri': BASELINE_URI, 'name': 'baseline', 'description': 'The baseline as the responsible engineer signed it: the card, the '
                                   'control cases as they ran, and the signature.  Read-only.', 'mimeType': 'application/json'}]}
        if method == 'resources/templates/list':
            return {'resourceTemplates': []}
        if method == 'resources/read':
            return self.read_baseline(params.get('uri'), legacy=not modern)
        raise RpcError(-32601, f'Method not found: {method}')

    @staticmethod
    def _ok(rid, result):
        return {'jsonrpc': '2.0', 'id': rid, 'result': result}

    @staticmethod
    def _error(rid, code, message, data=None):
        err = {'code': code, 'message': message}
        if data is not None:
            err['data'] = data
        return {'jsonrpc': '2.0', 'id': rid, 'error': err}

    def serve(self, inp=None, out=None):
        inp = inp or sys.stdin.buffer; out = out or sys.stdout
        while True:
            line = inp.readline(MAX_LINE + 1)
            if not line:
                return                                      # the host closed our input: stop
            if len(line) > MAX_LINE and not line.endswith(b'\n'):
                while line and not line.endswith(b'\n'):    # an over-long message: skip to its end, and say so
                    line = inp.readline(MAX_LINE + 1)
                reply = self._error(None, -32700, 'Parse error: the message is too long')
            elif not line.strip():
                continue
            else:
                try:
                    msg = json.loads(line.decode('utf-8'))
                except (ValueError, UnicodeDecodeError, RecursionError):
                    reply = self._error(None, -32700, 'Parse error')
                else:
                    reply = self.handle(msg)
            if reply is not None:
                out.write(json.dumps(reply) + '\n'); out.flush()


def main():
    ap = argparse.ArgumentParser(description='The verification service as three MCP tools (stdio).')
    ap.add_argument('--job-dir', default=os.environ.get('PLEA_JOB_DIR'), help='the folder front_ctl.py enrol wrote for this job')
    ap.add_argument('--timeout', type=float, default=120.0, help='seconds to wait for the service on one call')
    a = ap.parse_args()
    if not a.job_dir:
        print('plea_verify_mcp: give --job-dir (or PLEA_JOB_DIR)', file=sys.stderr); sys.exit(2)
    try:
        client = FrontClient(a.job_dir, a.timeout)
    except (OSError, ValueError, KeyError, ssl.SSLError) as exc:
        print(f'plea_verify_mcp: the job folder cannot be used: {exc}', file=sys.stderr); sys.exit(2)
    Server(client).serve()


if __name__ == '__main__':
    main()
