"""Probe A: in-process construction of a front door (8c4762f) with many shapes of engineer_keys.

EXPECTATION (written before running):
- single_engineer_key / Front accept exactly: a list or tuple (or subclass) holding one str of 64 lower-case hex digits.
- Refused (EngineerKeys, message contains 'not started'): (), [], (k,k), (k,other), (k.upper(),), (k[:63],), (k+'0',),
  (' '+k,), (k+'\\n',), (None,), (b'..',), a bare str k (-> '0 were given', fail closed but misleading message),
  a generator of one key, a set {k}, a frozenset, a dict {k: 1}, None (-> 0 given), an int.
- Unicode full-width digits / Arabic-Indic digits refused ([0-9a-f] is ASCII-only).
- A str subclass holding a valid key is accepted (isinstance str).
- No HOME/front directory is created for any refused case (the check is before the mkdir); created for the accepted case.
- Store(dsn) never connects in __init__, so a closed-port DSN is harmless.
- Front.engineer_keys for the accepted list input is a tuple (k,).
"""
import pathlib, sys, tempfile, shutil
SRC = pathlib.Path(__file__).resolve().parent / 'src'
sys.path[:0] = [str(SRC / 'verify'), str(SRC)]
import front_door
from plea_gateway import Store
from verify_record import Key

k = Key().public_hex; other = Key().public_hex
class S(str): pass
class L(list): pass
cases = {
    'tuple one': (k,), 'list one': [k], 'list subclass one': L([k]), 'str subclass one': (S(k),),
    'empty tuple': (), 'empty list': [], 'same twice': (k, k), 'two': (k, other), 'upper': (k.upper(),), 'short': (k[:63],),
    'long': (k + '0',), 'leading space': (' ' + k,), 'trailing newline': (k + '\n',), 'None in tuple': (None,), 'bytes': (k.encode(),),
    'bare str': k, 'generator': (x for x in [k]), 'set': {k}, 'frozenset': frozenset([k]), 'dict': {k: 1}, 'None': None, 'int': 5,
    'fullwidth digits': (k[:-1] + '１',), 'arabic-indic digit': (k[:-1] + '١',), 'nested tuple': ((k,),),
}
for label, keys in cases.items():
    home = pathlib.Path(tempfile.mkdtemp(prefix='pa_', dir=pathlib.Path(__file__).parent))
    try:
        door = front_door.Front(home, Store('postgresql://x:y@127.0.0.1:1/none'), {'journal': str(home / 'j')}, keys)
        res = f'MADE engineer_keys={door.engineer_keys!r:.30} type={type(door.engineer_keys).__name__} len={len(door.engineer_keys)}'
    except front_door.EngineerKeys as exc:
        res = f'REFUSED ({exc})'
    except Exception as exc:
        res = f'OTHER {type(exc).__name__}: {exc}'
    print(f'{label:20s} front_dir={(home / "front").exists()!s:5s} {res}')
    shutil.rmtree(home)
