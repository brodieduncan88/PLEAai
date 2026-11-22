#!/usr/bin/env python3
"""The same tools, ungoverned: a plain MCP server over stdio.  The control case for the demonstration, and the
upstream that plea_mcp.py proxies in the M3 test."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from demo_tools import TOOLS   # noqa: E402

PROTOCOL = '2024-11-05'


def handle(msg):
    method, rid, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
    if method == 'initialize':
        return {'jsonrpc': '2.0', 'id': rid, 'result': {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'vanilla-tools', 'version': '0'}}}
    if method == 'ping':
        return {'jsonrpc': '2.0', 'id': rid, 'result': {}}
    if method == 'tools/list':
        return {'jsonrpc': '2.0', 'id': rid, 'result': {'tools': [{'name': n, 'description': d, 'inputSchema': s} for n, (d, s, *_) in TOOLS.items()]}}
    if method == 'tools/call':
        name, args = params.get('name'), params.get('arguments') or {}
        if name not in TOOLS:
            return {'jsonrpc': '2.0', 'id': rid, 'result': {'content': [{'type': 'text', 'text': f'unknown tool {name}'}], 'isError': True}}
        try:
            value = TOOLS[name][2](**args)
            return {'jsonrpc': '2.0', 'id': rid, 'result': {'content': [{'type': 'text', 'text': value}], 'isError': False}}
        except Exception as exc:
            return {'jsonrpc': '2.0', 'id': rid, 'result': {'content': [{'type': 'text', 'text': f'tool error: {exc}'}], 'isError': True}}
    if rid is None:
        return None
    return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': -32601, 'message': f'method not found: {method}'}}


for line in sys.stdin:
    line = line.strip()
    if line:
        reply = handle(json.loads(line))
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + '\n'); sys.stdout.flush()
