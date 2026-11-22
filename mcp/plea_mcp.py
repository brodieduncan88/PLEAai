#!/usr/bin/env python3
"""Governed tools over MCP: an agent's tools pass through the governor without the agent changing.

    plea_mcp.py --root R --budget K [--replacement M] --witness-url URL [--tools MODULE] [--upstream "CMD ..."]
                [--gate-host URL] [--tls-ca CA --tls-cert CERT --tls-key KEY]      (v0.5: https to the services)

The server speaks MCP's stdio transport (newline-delimited JSON-RPC 2.0): initialize, ping, tools/list,
tools/call.  Its tools come either from a Python module exposing TOOLS (name -> (description, input schema,
function)), or from an upstream MCP server it spawns and proxies.  Every tools/call runs through
Governor.attempt, so:

  - the request key is the tool name plus the canonical JSON of its arguments, unless the caller passes
    `_plea_request_key`; an identical call is therefore the contract's DUPLICATE and returns the stored result
    without running the tool again;
  - a call beyond the budget, or on a held or stopped run, returns an MCP tool error (isError) that names the
    reason, and the tool does not run;
  - every run is behind a verified receipt, and every verdict is a gate-signed effect report.

The agent cannot hold, stop or recover the run: those are operator actions (plea_ctl.py).  One read-only tool,
plea_status, reports the budget view.

v1.1: this process holds only the gateway credential.  The root (the budget) is provisioned beforehand by the control
plane -- `plea_ctl.py ROOT provision --budget K` -- and the server refuses to start against an unprovisioned root.
--control-dsn (an operator's launch) or --admin-dsn (tests) provisions it on start instead; neither belongs in an
agent-facing deployment.
"""
import argparse
import hashlib
import importlib
import json
import os
import pathlib
import shlex
import subprocess
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway import (BudgetExhausted, GateHostClient, GateRefusedRun, GateSigner, Governor, Held, InProgress,  # noqa: E402
                          NoEffect, OutcomeInvalid, RemoteWitness, RequestKeyReused, Store, Stopped, VerdictRefused)
from plea_gateway.tls import add_client_args, client_from_args    # noqa: E402
from plea_gateway.governor import identity_form                   # noqa: E402  (Amendment 17)

PROTOCOL = '2024-11-05'


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def request_key(name: str, arguments: dict, legacy: bool = False) -> str:
    """Amendment 17 (D21): the whole hash, not 96 bits; legacy=True for a budget that already holds the earlier form."""
    h = hashlib.sha256(canonical(arguments).encode()).hexdigest()
    return f'{name}:' + (h[:24] if legacy else h)


class UpstreamStdio:
    """An upstream MCP server over stdio, proxied tool by tool."""

    def __init__(self, cmd: str):
        self.proc = subprocess.Popen(shlex.split(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self._id, self._lock = 0, threading.Lock()
        self._rpc('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'plea-mcp', 'version': '0.5'}})
        self._notify('notifications/initialized')

    def _send(self, msg: dict):
        self.proc.stdin.write(json.dumps(msg) + '\n'); self.proc.stdin.flush()

    def _notify(self, method, params=None):
        self._send({'jsonrpc': '2.0', 'method': method, 'params': params or {}})

    def _rpc(self, method, params=None):
        with self._lock:
            self._id += 1; rid = self._id
            self._send({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params or {}})
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    raise RuntimeError('upstream closed')
                msg = json.loads(line)
                if msg.get('id') == rid:
                    if 'error' in msg:
                        raise RuntimeError(msg['error'].get('message', 'upstream error'))
                    return msg['result']

    def tools(self) -> list:
        return self._rpc('tools/list')['tools']

    def call(self, name: str, arguments: dict):
        result = self._rpc('tools/call', {'name': name, 'arguments': arguments})
        if result.get('isError'):
            raise RuntimeError('upstream tool error: ' + ' '.join(c.get('text', '') for c in result.get('content', [])))
        return result.get('content', [])


class GovernedServer:
    def __init__(self, governor: Governor, tools: dict, upstream: UpstreamStdio | None = None):
        self.gov, self.tools, self.upstream = governor, tools, upstream
        self.host = governor.host                       # v0.4: in host mode the tools live at the gate host

    # ------------------------------------------------------------------ tools
    def list_tools(self) -> list:
        listed = [{'name': n, 'description': d, 'inputSchema': schema} for n, (d, schema, *_) in self.tools.items()]   # Amendment 17: an entry may carry a binder
        if self.upstream:
            listed += self.upstream.tools()
        if self.host:
            listed += self.host.tools()
        listed.append({'name': 'plea_status', 'description': 'The budget view of this governed run (read-only).',
                       'inputSchema': {'type': 'object', 'properties': {}}})
        return listed

    def call_tool(self, name: str, arguments: dict) -> dict:
        if name == 'plea_status':
            return {'content': [{'type': 'text', 'text': json.dumps(self.gov.status())}], 'isError': False}
        arguments = dict(arguments or {})
        key = arguments.pop('_plea_request_key', None) or request_key(name, arguments, legacy=identity_form(self.gov.store, self.gov.root) == 'legacy')
        if self.host:
            run = name                                  # host mode: the governor sends the tool name to the gate host
        elif name in self.tools:
            fn = self.tools[name][2]; run = lambda: fn(**arguments)
        elif self.upstream:
            run = lambda: self.upstream.call(name, arguments)
        else:
            return {'content': [{'type': 'text', 'text': f'unknown tool {name}'}], 'isError': True}
        try:
            value = self.gov.attempt(key, run, **arguments) if self.host else self.gov.attempt(key, run)
        except BudgetExhausted:
            return self._refused(f'PLEA: budget exhausted for run {self.gov.root!r}; the call did not run')
        except Held:
            return self._refused(f'PLEA: run {self.gov.root!r} is held; no new actions are admitted')
        except Stopped:
            return self._refused(f'PLEA: run {self.gov.root!r} is stopped; no new actions are admitted')
        except InProgress:
            return self._refused('PLEA: an identical call is still in progress')
        except GateRefusedRun as exc:
            return self._refused(f'PLEA: the gate host refused to run the call: {exc}')
        except VerdictRefused as exc:
            return self._refused(f'PLEA: the call ran but the witness refused the verdict ({exc.decision.code}); the attempt stays charged and the result is withheld: {json.dumps(exc.result)[:200]}')
        except RequestKeyReused:
            return self._refused('PLEA: this request key is bound to a different call (other tool or arguments); the call did not run')
        except OutcomeInvalid as exc:
            return self._refused(f'PLEA: the result returned for this call is not the one the gate signed for; retry to fetch the signed one: {exc}')
        except NoEffect:
            return {'content': [{'type': 'text', 'text': 'no effect: the gate reported NO_EFFECT for this call; a replacement is credited only within the run\'s allowance (see plea_status)'}], 'isError': False}
        except Exception as exc:
            return {'content': [{'type': 'text', 'text': f'tool error: {exc}'}], 'isError': True}
        if isinstance(value, list) and all(isinstance(c, dict) and 'type' in c for c in value):
            return {'content': value, 'isError': False}                       # proxied content, as the upstream returned it
        return {'content': [{'type': 'text', 'text': value if isinstance(value, str) else json.dumps(value)}], 'isError': False}

    @staticmethod
    def _refused(text: str) -> dict:
        return {'content': [{'type': 'text', 'text': text}], 'isError': True}

    # ------------------------------------------------------------------ JSON-RPC over stdio
    def handle(self, msg: dict):
        method, rid, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
        if method == 'initialize':
            return self._ok(rid, {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}},
                                  'serverInfo': {'name': 'plea-governed-tools', 'version': '0.5'}})
        if method == 'notifications/initialized' or method is None and rid is None:
            return None
        if method == 'ping':
            return self._ok(rid, {})
        if method == 'tools/list':
            return self._ok(rid, {'tools': self.list_tools()})
        if method == 'tools/call':
            return self._ok(rid, self.call_tool(params.get('name', ''), params.get('arguments') or {}))
        if rid is None:
            return None                                                         # an unknown notification
        return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': -32601, 'message': f'method not found: {method}'}}

    @staticmethod
    def _ok(rid, result):
        return {'jsonrpc': '2.0', 'id': rid, 'result': result}

    def serve(self, inp=sys.stdin, out=sys.stdout):
        for line in inp:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                out.write(json.dumps({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'parse error'}}) + '\n'); out.flush()
                continue
            reply = self.handle(msg)
            if reply is not None:
                out.write(json.dumps(reply) + '\n'); out.flush()


def load_tools(module_name: str | None) -> dict:
    if not module_name:
        return {}
    sys.path.insert(0, os.getcwd())
    return importlib.import_module(module_name).TOOLS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True); ap.add_argument('--budget', type=int, required=True); ap.add_argument('--replacement', type=int, default=0)
    ap.add_argument('--witness-url', required=True)
    ap.add_argument('--local-dsn', default=os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea'))
    ap.add_argument('--admin-dsn', default=os.environ.get('PLEA_ADMIN_DSN'), help='the owner (tests only): provisions the root on start')
    ap.add_argument('--control-dsn', default=os.environ.get('PLEA_CONTROL_DSN'), help='the control plane (an operator launch): provisions the root on start')
    ap.add_argument('--gate-key', default=os.environ.get('PLEA_GATE_KEY'), help='the gate private key (hex); the witness must pin its public key')
    ap.add_argument('--tools', help='a Python module exposing TOOLS'); ap.add_argument('--upstream', help='an upstream MCP server command to proxy')
    ap.add_argument('--gate-host', help='v0.4: the gate host URL; the tools live there and this process holds no gate key')
    ap.add_argument('--witness-key', action='append', default=[], help='a witness public key to pin (hex); repeatable; none fetches it')
    add_client_args(ap)
    a = ap.parse_args()
    tls = client_from_args(a)
    witness = RemoteWitness(a.witness_url, a.witness_key or None, tls=tls)
    admin = Store(a.admin_dsn) if a.admin_dsn else None; control = Store(a.control_dsn) if a.control_dsn else None
    if a.gate_host:
        gov = Governor(Store(a.local_dsn), witness, a.root, a.budget, a.replacement, admin=admin, control=control,
                       host=GateHostClient(a.gate_host, tls=tls))
    else:
        gov = Governor(Store(a.local_dsn), witness, a.root, a.budget, a.replacement, admin=admin, control=control,
                       gate=GateSigner(a.gate_key))
    upstream = UpstreamStdio(a.upstream) if a.upstream else None
    GovernedServer(gov, load_tools(a.tools), upstream).serve()


if __name__ == '__main__':
    main()
