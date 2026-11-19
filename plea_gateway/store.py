"""The transactional store: contract v3.1 section 1's "transactional storage", around the pure reference.

apply(root_id, op) is one transaction:
  1. validate the operation (evaluation step 1) before touching the store: malformed input never reaches it;
  2. lock the root row (SELECT ... FOR UPDATE), or run the transaction SERIALIZABLE with retry;
  3. load the attempt rows and build the reference's RootState, which validates itself;
  4. decide with the reference: decision, new_state = apply(state, op);
  5. if APPLIED, write the changed attempt rows and the root's modes;
  6. append the decision to the audit log with a hash chain, whatever its kind;
  7. commit.
No counter is stored.  Every view is recomputed from the attempt rows under the lock, so G01's admission is
decided against the committed state and nothing else.

Authority (v0.1 -> v1.0).  Every authoritative write goes through one owner-side SECURITY DEFINER function
(plea_write, AUTHORITY below), which reserves each per-attempt phase transition and every mode change to the login
credential of the contract operation that produces it: gateway (plea_local), witness (plea_witness) or control
plane (plea_control).  A gateway holding plea_local cannot apply an acceptance, free a consumed budget, or change a
mode however its code is written: the database raises insufficient_privilege or check_violation and the transaction
rolls back.  v1.0: the accepted bindings (request, nonce) are immutable in place; a stored outcome can only be
written for an admitted, consumed attempt; the functions reference every table schema-qualified with pg_temp last
in search_path and PUBLIC's default EXECUTE revoked.  v1.1: the audit record is authored by the database -- the
observation it stores is derived from the rows just written, the decision kind is bound to whether the state
changed, the operation named is bound to the transition performed, and the chain hash is recomputed and verified
in-database over exactly what is stored; a root (a budget) is provisioned only by the control plane.  No login
role holds direct DML on the authoritative tables or the results cache, and none may create objects in public.

v1.2: every record is the contract's own decision, and every budget has an origin.  plea_write evaluates the
contract's single-root step in the database (plea_step, a PL/pgSQL port of the reference engine, differential-tested
against it and the independent oracle) on the state before the write, and refuses a record unless its kind, its
code and every row and mode it changed are exactly what the operation it names produces there -- so an operation's
operands (attempt, request, nonce, verdict, evidence label), a batch's extent and every mode guard are bound, and a
refusal is checked as strictly as a change.  plea_new_root appends an immutable record to a hash-linked provisioning
log (root, k, m, issuing credential, contract, release, database time) and the root's chain starts at that record's
hash, computed by the database; verify_chain checks the anchor and the budget against it.
"""
import hashlib
import json
from dataclasses import dataclass

import psycopg
from psycopg import errors

from . import plea_budget_ref as ref
from .faults import crash_point

SCHEMA = """
-- v1.2: the provisioning log.  One record per provisioning, hash-linked to the record before it (the first to the
-- genesis); a root's audit chain starts at its record's hash.  Append-only (AUTHORITY), never part of a root's
-- decision log, so the contract's single-root replay is unchanged.
CREATE TABLE IF NOT EXISTS provisions (
  seq        bigint PRIMARY KEY CHECK (seq > 0),
  root_id    text NOT NULL,
  k          integer NOT NULL CHECK (k >= 0),
  m          integer NOT NULL CHECK (m >= 0),
  issuer     text NOT NULL,
  contract   text NOT NULL,
  release    text NOT NULL,
  created_at text NOT NULL,
  prev_hash  text NOT NULL,
  hash       text NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS roots (
  root_id       text PRIMARY KEY,
  k             integer NOT NULL CHECK (k >= 0),
  m             integer NOT NULL CHECK (m >= 0),
  witness       text NOT NULL,
  business      text NOT NULL,
  reregistered  boolean NOT NULL DEFAULT false,
  seq           bigint NOT NULL DEFAULT 0,
  head_hash     text NOT NULL,
  provision_seq bigint REFERENCES provisions(seq)
);
ALTER TABLE roots ADD COLUMN IF NOT EXISTS provision_seq bigint REFERENCES provisions(seq);   -- v1.2, on an upgraded v1.1 database
CREATE TABLE IF NOT EXISTS attempts (
  root_id  text NOT NULL REFERENCES roots(root_id) ON DELETE CASCADE,
  aid      text NOT NULL,
  req      text NOT NULL,
  phase    text NOT NULL,
  nonce    text,
  receipt  boolean NOT NULL DEFAULT false,
  crossed  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (root_id, aid),
  UNIQUE (root_id, req),
  UNIQUE (root_id, nonce)
);
CREATE TABLE IF NOT EXISTS decisions (
  root_id     text NOT NULL REFERENCES roots(root_id) ON DELETE CASCADE,
  seq         bigint NOT NULL,
  op          jsonb NOT NULL,
  kind        text NOT NULL,
  code        text NOT NULL,
  observation jsonb NOT NULL,
  prev_hash   text NOT NULL,
  hash        text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (root_id, seq)
);
CREATE TABLE IF NOT EXISTS results (
  root_id text NOT NULL REFERENCES roots(root_id) ON DELETE CASCADE,
  aid     text NOT NULL,
  result  jsonb NOT NULL,
  PRIMARY KEY (root_id, aid)
);
CREATE TABLE IF NOT EXISTS receipts (
  root_id   text NOT NULL REFERENCES roots(root_id) ON DELETE CASCADE,
  aid       text NOT NULL,
  op        text NOT NULL,
  seq       bigint NOT NULL,
  receipt   jsonb NOT NULL,
  PRIMARY KEY (root_id, aid, op)
);
CREATE TABLE IF NOT EXISTS evidence (
  root_id   text NOT NULL REFERENCES roots(root_id) ON DELETE CASCADE,
  aid       text NOT NULL,
  seq       bigint NOT NULL,
  evidence  jsonb NOT NULL,
  derived   text NOT NULL,
  PRIMARY KEY (root_id, seq)
);
"""

# Applied once by the owner role.  plea_local, plea_witness and plea_control get table access; the one write path
# (plea_write) reserves each phase transition and every mode change to the credential whose contract operation
# produces it.  The owner role is an administrative credential that is never handed to a gateway.
AUTHORITY = r"""
-- v0.8/v0.9: the login credentials (plea_local gateway, plea_witness, plea_control control plane) hold NO direct
-- INSERT/UPDATE/DELETE on the authoritative tables.  Every mutation goes through owner-side SECURITY DEFINER
-- functions, so even hand-written SQL as plea_local cannot rewrite accepted facts, budgets, control modes or audit
-- history.  The functions see session_user (the login role, unchanged under SECURITY DEFINER).
--
-- v0.9 closes two holes the v0.8 review reproduced:
--   A. plea_write trusted the caller-supplied post-state, checking only the *new* phase's authority and the
--      *aggregate* counters (worsening-only), so a per-attempt transition the contract never produces -- e.g.
--      CONSUMED->DISCARDED -- slipped through and freed budget.  v0.9 enforces the legal per-attempt transition
--      relation: every (old phase -> new phase) must be one a contract operation produces, and each is reserved to
--      the credential class of that operation (gateway / witness / control).  An illegal pair is rejected outright.
--   B. the witness HELD->ACTIVE guard trusted the caller-supplied operation name (op0), so a forged call naming
--      'RECOVER' flipped the mode without any approval.  v0.9 reserves *every* mode change to the control-plane
--      credential (session_user), independent of op0; a compromised gateway cannot change any mode.
-- v1.0 closes the v0.9 review's findings:
--   C. plea_write guarded phase transitions but not the bindings carried on an attempt, so a same-phase rewrite
--      could replace an accepted nonce (the executor/action binding) in place.  v1.0 makes req immutable and lets the
--      nonce change only where the contract does: set by START (TOKEN->INTENT_PENDING), cleared by RECOVER
--      (INTENT_PENDING->TOKEN); every other update, same-phase included, must carry it unchanged.
--   D. the results cache was directly writable by the gateway and the governor replayed a stored value before any
--      admission.  v1.0 routes every results write through plea_put_result, which requires an admitted (crossed),
--      consumed attempt, and the governor re-verifies the executor's signed effect report on every replay.
--   E. SECURITY DEFINER hardening per the PostgreSQL manual: every table reference is schema-qualified, search_path
--      is pinned to pg_catalog with pg_temp explicitly last (a temporary relation can never shadow a name), and
--      PUBLIC's default EXECUTE on the functions is revoked before the named grants.  No login role may create
--      objects in public.

-- v1.1 closes the v1.0 review's findings:
--   F1. plea_write stored the caller's op/kind/code/observation/hash as long as the chain linked, so a hash-consistent
--       but false record (e.g. "STOP APPLIED" with the business mode left OPEN) could be appended by the gateway.  v1.1
--       makes the database the author of the record: the observation is derived from the rows just written and the
--       caller's must equal it; the kind is bound to whether the state actually changed (APPLIED iff it did); the
--       operation named is bound to the transition performed (an insert is a RESERVE, RESERVING->RESERVED is an
--       ACCEPT_RESERVATION, a witness hold is a HOLD, a restart in STOPPING a REREGISTER, ...); and the chain hash is recomputed in-database over exactly
--       what is stored, with a canonical form identical to the client's, and the caller's hash must equal it.  So a
--       record that does not describe the transition it accompanies cannot exist, and verify_chain -- ordinary hash
--       verification -- again attests to real history.  What remains the caller's text is the code label, and, on a
--       record of a refusal (nothing changed), which operation was refused; replay lockstep still checks those.
--   F2. the gateway credential could create a root with any budget, i.e. mint itself a fresh allowance.  v1.1
--       reserves plea_new_root to the control plane: a root is provisioned (plea_ctl provision) before a gateway
--       runs against it; the gateway can neither create one nor change its budget.

-- v1.2 closes the v1.1 review's findings:
--   P1. a root's origin was not part of any audit history: plea_new_root inserted the row and nothing recorded who
--       issued the budget.  v1.2 appends every provisioning to an immutable, hash-linked provisioning log (root, k, m,
--       the issuing credential, the contract and release, the database time); no login role writes it, the owner
--       cannot rewrite or remove a record, and a root's k, m and record are immutable.
--   P2. the starting hash of a root's chain was a caller argument.  v1.2 removes the argument: the chain starts at the
--       provisioning record's hash (the anchor), computed here, and verify_chain checks it.
--   P3. plea_write bound the operation's *name* to the transition, not its operands, nor the extent of a batch: a
--       RESERVE logged for one attempt could insert another, or two.  v1.2 evaluates the contract's single-root step
--       in the database (plea_step) on the state before the write and refuses any record whose kind, code, rows or
--       modes differ from what the named operation produces there -- operands, batches and mode guards included.
--   P4. a record of a refusal was unchecked text.  The same evaluation now checks it: a refusal (or NOOP, DUPLICATE)
--       must be the contract's own for the operation named, code included, and a control-plane operation is recorded,
--       applied or refused, only by the control plane.  What remains: a refusal the contract would give can still
--       be recorded for a request that was never made -- it moves no state, and the database cannot know.
--   Found while closing P3: the evidence row stored with a decision was caller text under a caller-chosen sequence
--       number, writable by any credential.  v1.2 reserves it to the witness and binds it to its decision.
DROP FUNCTION IF EXISTS plea_new_root(text, integer, integer, text);   -- v1.1's signature took the starting hash

-- Python-identical canonical JSON (json.dumps(value, sort_keys=True, separators=(',', ':'))): object keys in code
-- point order, no whitespace, integers only, strings escaped exactly as Python's ensure_ascii does.
CREATE OR REPLACE FUNCTION plea_jstr(s text) RETURNS text AS $$
DECLARE out text := '"'; i int; ch text; cp int; n int := length(s);
BEGIN
  FOR i IN 1..n LOOP
    ch := substr(s, i, 1); cp := ascii(ch);
    IF ch = '"' THEN out := out || '\"';
    ELSIF ch = '\' THEN out := out || '\\';
    ELSIF cp = 10 THEN out := out || '\n';
    ELSIF cp = 13 THEN out := out || '\r';
    ELSIF cp = 9 THEN out := out || '\t';
    ELSIF cp = 8 THEN out := out || '\b';
    ELSIF cp = 12 THEN out := out || '\f';
    ELSIF cp < 32 OR cp = 127 THEN out := out || '\u' || lpad(to_hex(cp), 4, '0');
    ELSIF cp > 127 THEN
      IF cp > 65535 THEN
        out := out || '\u' || lpad(to_hex(55296 + ((cp - 65536) >> 10)), 4, '0') || '\u' || lpad(to_hex(56320 + ((cp - 65536) & 1023)), 4, '0');
      ELSE
        out := out || '\u' || lpad(to_hex(cp), 4, '0');
      END IF;
    ELSE out := out || ch;
    END IF;
  END LOOP;
  RETURN out || '"';
END $$ LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog, pg_temp;

CREATE OR REPLACE FUNCTION plea_canonical(j jsonb) RETURNS text AS $$
DECLARE t text;
BEGIN
  IF j IS NULL THEN RAISE EXCEPTION 'canonical form: missing value' USING ERRCODE = 'check_violation'; END IF;
  CASE jsonb_typeof(j)
    WHEN 'null' THEN RETURN 'null';
    WHEN 'boolean' THEN RETURN (j #>> '{}');
    WHEN 'number' THEN
      t := j #>> '{}';
      IF t !~ '^-?[0-9]+$' THEN RAISE EXCEPTION 'canonical form: non-integer number %', t USING ERRCODE = 'check_violation'; END IF;
      RETURN t;
    WHEN 'string' THEN RETURN public.plea_jstr(j #>> '{}');
    WHEN 'array' THEN
      RETURN '[' || coalesce((SELECT string_agg(public.plea_canonical(e), ',' ORDER BY o) FROM jsonb_array_elements(j) WITH ORDINALITY AS x(e, o)), '') || ']';
    WHEN 'object' THEN
      RETURN '{' || coalesce((SELECT string_agg(public.plea_jstr(k) || ':' || public.plea_canonical(v), ',' ORDER BY k COLLATE "C") FROM jsonb_each(j) AS x(k, v)), '') || '}';
    ELSE RAISE EXCEPTION 'canonical form: unsupported value' USING ERRCODE = 'check_violation';
  END CASE;
END $$ LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog, pg_temp;

-- The chain hash, as the client computes it: sha256(prev_hash || canonical({seq, op, kind, code, observation})).
CREATE OR REPLACE FUNCTION plea_decision_hash(p_prev text, p_body jsonb) RETURNS text AS $$
  SELECT encode(sha256(convert_to(p_prev || public.plea_canonical(p_body), 'UTF8')), 'hex');
$$ LANGUAGE sql IMMUTABLE SET search_path = pg_catalog, pg_temp;

-- v1.2: the section 7 observation of a state given by its facts -- the database's one derivation of an observation,
-- used for the stored state (plea_observe) and for the contract's evaluation (plea_step) alike.
CREATE OR REPLACE FUNCTION plea_obs_of(p_k jsonb, p_m jsonb, p_w text, p_b text, p_rr boolean, p_attempts jsonb) RETURNS jsonb AS $$
  SELECT jsonb_build_object(
    'k', p_k, 'm', p_m, 'witness', p_w, 'business', p_b, 'reregistered', p_rr,
    'live', jsonb_build_array(s.lr, s.lc, s.n), 'accepted', jsonb_build_array(s.ar, s.ac, s.n), 'credit', least(s.n, (p_m #>> '{}')::bigint),
    'attempts', coalesce(s.atts, '[]'::jsonb))
  FROM (SELECT count(*) FILTER (WHERE e->>2 IN ('RESERVING','RESERVED','TOKEN')) AS lr,
               count(*) FILTER (WHERE e->>2 IN ('INTENT_PENDING','CONSUMED','NO_EFFECT','EFFECT','INDETERMINATE')) AS lc,
               count(*) FILTER (WHERE e->>2 IN ('RESERVED','TOKEN','INTENT_PENDING')) AS ar,
               count(*) FILTER (WHERE e->>2 IN ('CONSUMED','NO_EFFECT','EFFECT','INDETERMINATE')) AS ac,
               count(*) FILTER (WHERE e->>2 = 'NO_EFFECT') AS n,
               jsonb_agg(e ORDER BY (e->>0) COLLATE "C") AS atts
        FROM jsonb_array_elements(coalesce(p_attempts, '[]'::jsonb)) AS e) s;
$$ LANGUAGE sql IMMUTABLE SET search_path = pg_catalog, pg_temp;

-- The section 7 observation of a root, derived from its rows: what the client's observe() computes from the same rows.
CREATE OR REPLACE FUNCTION plea_observe(p_root text) RETURNS jsonb AS $$
  SELECT public.plea_obs_of(to_jsonb(r.k), to_jsonb(r.m), r.witness, r.business, r.reregistered,
           (SELECT jsonb_agg(jsonb_build_array(a.aid, a.req, a.phase, a.nonce, a.receipt, a.crossed)) FROM public.attempts a WHERE a.root_id = p_root))
  FROM public.roots r WHERE r.root_id = p_root;
$$ LANGUAGE sql STABLE SET search_path = pg_catalog, pg_temp;

-- v1.2: the contract's single-root step (v3.1 section 5), a port of the reference engine (plea_budget_ref.apply) with
-- its codes: evaluation step 1 (a malformed operation raises), step 2 (an INDETERMINATE attempt is frozen), step 3
-- (the operation's rules in the contract's order; the first that matches decides).  Pure: an observation and an
-- operation in, {kind, code, observation after} out.  plea_write requires every record to be exactly this.
CREATE OR REPLACE FUNCTION plea_step(p_obs jsonb, p_op jsonb) RETURNS jsonb AS $$
DECLARE
  name text; nargs int; arity int; aid text; a jsonb; ph text; arg2 text; arg3 text;
  w text := p_obs->>'witness'; b text := p_obs->>'business'; rr boolean := (p_obs->>'reregistered')::boolean;
  k bigint := (p_obs->>'k')::bigint; m bigint := (p_obs->>'m')::bigint;
  atts jsonb := coalesce((SELECT jsonb_agg(e ORDER BY (e->>0) COLLATE "C") FROM jsonb_array_elements(coalesce(p_obs->'attempts', '[]'::jsonb)) AS e), '[]'::jsonb);
  kind text; code text; nw text; nb text; nrr boolean; natts jsonb; nrow jsonb; post jsonb; charge bigint;
  named text[] := ARRAY['RESERVE','ACCEPT_RESERVATION','TOKEN','START','ACCEPT_INTENT','RECEIPT','CROSS','RELEASE','RECONCILE','TIMEOUT','MISSING_RECEIPT'];
  unresolved text[] := ARRAY['RESERVING','RESERVED','TOKEN','INTENT_PENDING','CONSUMED'];
  consumption text[] := ARRAY['CONSUMED','NO_EFFECT','EFFECT'];
BEGIN
  -- step 1: the operation is well formed, as the reference's parse_op requires
  IF p_op IS NULL OR jsonb_typeof(p_op) <> 'array' OR jsonb_array_length(p_op) = 0 OR jsonb_typeof(p_op->0) <> 'string' THEN
    RAISE EXCEPTION 'malformed operation %: not a list that starts with an operation name', p_op USING ERRCODE = 'check_violation';
  END IF;
  name := p_op->>0; nargs := jsonb_array_length(p_op) - 1;
  arity := CASE name WHEN 'RESERVE' THEN 2 WHEN 'ACCEPT_RESERVATION' THEN 1 WHEN 'TOKEN' THEN 1 WHEN 'START' THEN 2
                     WHEN 'ACCEPT_INTENT' THEN 1 WHEN 'RECEIPT' THEN 1 WHEN 'CROSS' THEN 1 WHEN 'RELEASE' THEN 2
                     WHEN 'RECONCILE' THEN 3 WHEN 'TIMEOUT' THEN 1 WHEN 'MISSING_RECEIPT' THEN 1 WHEN 'CRASH' THEN 0
                     WHEN 'HOLD' THEN 0 WHEN 'STOP' THEN 0 WHEN 'TERMINALISE' THEN 0 WHEN 'TERMINAL' THEN 0
                     WHEN 'RECOVER' THEN 2 WHEN 'REREGISTER' THEN 0 END;
  IF arity IS NULL THEN
    RAISE EXCEPTION 'malformed operation %: unknown operation', p_op USING ERRCODE = 'check_violation';
  END IF;
  IF nargs <> arity THEN
    RAISE EXCEPTION 'malformed operation %: % takes % argument(s), got %', p_op, name, arity, nargs USING ERRCODE = 'check_violation';
  END IF;
  IF name = ANY(named) AND NOT (jsonb_typeof(p_op->1) = 'string' AND p_op->>1 <> '') THEN
    RAISE EXCEPTION 'malformed operation %: the attempt identity is not a non-empty string', p_op USING ERRCODE = 'check_violation';
  END IF;
  IF name IN ('RESERVE', 'START') AND NOT (jsonb_typeof(p_op->2) = 'string' AND p_op->>2 <> '') THEN
    RAISE EXCEPTION 'malformed operation %: the request key or nonce is not a non-empty string', p_op USING ERRCODE = 'check_violation';
  END IF;
  IF name = 'RELEASE' AND NOT (jsonb_typeof(p_op->2) = 'string' AND p_op->>2 IN ('BOUND_FENCE','NONE','WRONG_BINDING')) THEN
    RAISE EXCEPTION 'malformed operation %: unknown RELEASE evidence label', p_op USING ERRCODE = 'check_violation';
  END IF;
  IF name = 'RECONCILE' AND NOT (jsonb_typeof(p_op->2) = 'string' AND p_op->>2 IN ('NO_EFFECT','EFFECT','UNKNOWN')
                                 AND jsonb_typeof(p_op->3) = 'string' AND p_op->>3 IN ('AUTHORISED','NONE','WRONG_BINDING')) THEN
    RAISE EXCEPTION 'malformed operation %: unknown verdict or RECONCILE evidence label', p_op USING ERRCODE = 'check_violation';
  END IF;
  IF name = 'RECOVER' AND NOT (jsonb_typeof(p_op->1) = 'boolean' AND jsonb_typeof(p_op->2) = 'boolean') THEN
    RAISE EXCEPTION 'malformed operation %: RECOVER takes two booleans', p_op USING ERRCODE = 'check_violation';
  END IF;

  -- step 2 (D9): an INDETERMINATE attempt is frozen
  IF name = ANY(named) THEN
    aid := p_op->>1;
    SELECT e INTO a FROM jsonb_array_elements(atts) AS e WHERE e->>0 = aid;
    ph := a->>2;
    IF ph = 'INDETERMINATE' THEN
      IF name IN ('TIMEOUT', 'MISSING_RECEIPT') THEN
        RETURN jsonb_build_object('kind', 'NOOP', 'code', 'INDETERMINATE_NEVER_REFUNDS', 'observation', p_obs);
      END IF;
      RETURN jsonb_build_object('kind', 'DENIED', 'code', 'INDETERMINATE_IS_FROZEN', 'observation', p_obs);
    END IF;
  END IF;

  -- step 3: the operation's own rules, in the contract's order (5.1 - 5.13)
  nw := w; nb := b; nrr := rr; natts := atts;
  CASE name
  WHEN 'RESERVE' THEN
    arg2 := p_op->>2;
    IF a IS NOT NULL AND ph = 'DISCARDED' THEN kind := 'DENIED'; code := 'RESERVE_DISCARDED_ATTEMPT';
    ELSIF a IS NOT NULL AND a->>1 = arg2 THEN kind := 'DUPLICATE'; code := 'RESERVE_RETRY';
    ELSIF a IS NOT NULL THEN kind := 'DENIED'; code := 'ATTEMPT_BOUND_TO_OTHER_REQUEST';
    ELSIF EXISTS (SELECT 1 FROM jsonb_array_elements(atts) AS e WHERE e->>1 = arg2) THEN kind := 'DENIED'; code := 'REQUEST_BOUND_TO_OTHER_ATTEMPT';
    ELSIF NOT (w = 'ACTIVE' AND b = 'OPEN') THEN kind := 'DENIED'; code := 'NOT_ACTIVE_AND_OPEN';
    ELSE
      SELECT count(*) FILTER (WHERE e->>2 IN ('RESERVING','RESERVED','TOKEN','INTENT_PENDING','CONSUMED','NO_EFFECT','EFFECT','INDETERMINATE'))
             - least(count(*) FILTER (WHERE e->>2 = 'NO_EFFECT'), m) INTO charge FROM jsonb_array_elements(atts) AS e;
      IF charge >= k THEN kind := 'DENIED'; code := 'BUDGET_EXHAUSTED';
      ELSE
        kind := 'APPLIED'; code := 'RESERVATION_COMMITTED';
        natts := atts || jsonb_build_array(jsonb_build_array(aid, arg2, 'RESERVING', NULL, false, false));
      END IF;
    END IF;
  WHEN 'ACCEPT_RESERVATION' THEN
    IF a IS NULL OR ph = 'DISCARDED' THEN kind := 'DENIED'; code := 'UNKNOWN_OR_DISCARDED_ATTEMPT';
    ELSIF ph <> 'RESERVING' THEN kind := 'DUPLICATE'; code := 'RESERVATION_ALREADY_ACCEPTED';
    ELSIF w = 'HELD' THEN kind := 'DENIED'; code := 'WITNESS_HELD';
    ELSE kind := 'APPLIED'; code := 'RESERVATION_ACCEPTED'; nrow := jsonb_set(a, '{2}', '"RESERVED"');
    END IF;
  WHEN 'TOKEN' THEN
    IF a IS NULL OR ph IN ('RELEASED', 'DISCARDED') THEN kind := 'DENIED'; code := 'UNKNOWN_RELEASED_OR_DISCARDED_ATTEMPT';
    ELSIF ph = 'RESERVING' THEN kind := 'DENIED'; code := 'RESERVATION_NOT_ACCEPTED';
    ELSIF ph IN ('TOKEN','INTENT_PENDING','CONSUMED','NO_EFFECT','EFFECT') THEN kind := 'DUPLICATE'; code := 'TOKEN_ALREADY_RELEASED';
    ELSIF NOT (w = 'ACTIVE' AND b = 'OPEN') THEN kind := 'DENIED'; code := 'NOT_ACTIVE_AND_OPEN';
    ELSIF ph <> 'RESERVED' THEN RAISE EXCEPTION 'contract violation: TOKEN reached rule 5 with % in %', aid, ph;
    ELSE kind := 'APPLIED'; code := 'TOKEN_RELEASED'; nrow := jsonb_set(a, '{2}', '"TOKEN"');
    END IF;
  WHEN 'START' THEN
    arg2 := p_op->>2;
    IF a IS NULL THEN kind := 'DENIED'; code := 'UNKNOWN_ATTEMPT';
    ELSIF a->>3 IS NOT NULL THEN
      IF a->>3 = arg2 THEN kind := 'DUPLICATE'; code := 'START_RETRY'; ELSE kind := 'DENIED'; code := 'ATTEMPT_HOLDS_OTHER_NONCE'; END IF;
    ELSIF EXISTS (SELECT 1 FROM jsonb_array_elements(atts) AS e WHERE e->>3 = arg2) THEN kind := 'DENIED'; code := 'NONCE_HELD_BY_OTHER_ATTEMPT';
    ELSIF NOT (w = 'ACTIVE' AND b = 'OPEN') THEN kind := 'DENIED'; code := 'NOT_ACTIVE_AND_OPEN';
    ELSIF ph <> 'TOKEN' THEN kind := 'DENIED'; code := 'TOKEN_NOT_RELEASED';
    ELSE kind := 'APPLIED'; code := 'INTENT_COMMITTED_LOCALLY'; nrow := jsonb_set(jsonb_set(a, '{2}', '"INTENT_PENDING"'), '{3}', to_jsonb(arg2));
    END IF;
  WHEN 'ACCEPT_INTENT' THEN
    IF a IS NULL THEN kind := 'DENIED'; code := 'UNKNOWN_ATTEMPT';
    ELSIF ph = ANY(consumption) THEN kind := 'DUPLICATE'; code := 'INTENT_ALREADY_ACCEPTED';
    ELSIF ph <> 'INTENT_PENDING' THEN kind := 'DENIED'; code := 'NO_PENDING_INTENT';
    ELSIF w = 'HELD' THEN kind := 'DENIED'; code := 'WITNESS_HELD';
    ELSE kind := 'APPLIED'; code := 'INTENT_ACCEPTED'; nrow := jsonb_set(a, '{2}', '"CONSUMED"');
    END IF;
  WHEN 'RECEIPT' THEN
    IF a IS NULL OR NOT (ph = ANY(consumption)) THEN kind := 'DENIED'; code := 'NO_ACCEPTED_INTENT';
    ELSIF (a->>4)::boolean THEN kind := 'DUPLICATE'; code := 'RECEIPT_ALREADY_DELIVERED';
    ELSE kind := 'APPLIED'; code := 'RECEIPT_RECORDED'; nrow := jsonb_set(a, '{4}', 'true');
    END IF;
  WHEN 'CROSS' THEN
    IF a IS NULL OR ph <> 'CONSUMED' THEN kind := 'DENIED'; code := 'NOT_CONSUMED';
    ELSIF (a->>5)::boolean THEN kind := 'DENIED'; code := 'ALREADY_CROSSED';
    ELSIF NOT (a->>4)::boolean THEN kind := 'DENIED'; code := 'RECEIPT_NOT_DELIVERED';
    ELSIF NOT (w = 'ACTIVE' AND b = 'OPEN') THEN kind := 'DENIED'; code := 'NOT_ACTIVE_AND_OPEN';
    ELSE kind := 'APPLIED'; code := 'CROSSED'; nrow := jsonb_set(a, '{5}', 'true');
    END IF;
  WHEN 'RELEASE' THEN
    arg2 := p_op->>2;
    IF a IS NULL OR ph = 'DISCARDED' THEN kind := 'DENIED'; code := 'UNKNOWN_OR_DISCARDED_ATTEMPT';
    ELSIF ph = 'RELEASED' THEN kind := 'DUPLICATE'; code := 'ALREADY_RELEASED';
    ELSIF ph = 'INTENT_PENDING' THEN kind := 'DENIED'; code := 'PENDING_INTENT_NEEDS_RECOVERY';
    ELSIF ph = ANY(consumption) THEN kind := 'DENIED'; code := 'CONSUMPTION_IS_FINAL';
    ELSIF ph = 'RESERVING' THEN kind := 'DENIED'; code := 'RESERVATION_NOT_ACCEPTED';
    ELSIF arg2 <> 'BOUND_FENCE' THEN kind := 'DENIED'; code := 'NO_BOUND_FENCING_EVIDENCE';
    ELSIF w = 'HELD' THEN kind := 'DENIED'; code := 'WITNESS_HELD';
    ELSIF ph NOT IN ('RESERVED', 'TOKEN') THEN RAISE EXCEPTION 'contract violation: RELEASE reached rule 8 with % in %', aid, ph;
    ELSE kind := 'APPLIED'; code := 'RESERVATION_RELEASED'; nrow := jsonb_set(a, '{2}', '"RELEASED"');
    END IF;
  WHEN 'RECONCILE' THEN
    arg2 := p_op->>2; arg3 := p_op->>3;
    IF a IS NULL THEN kind := 'DENIED'; code := 'UNKNOWN_ATTEMPT';
    ELSIF ph IN ('NO_EFFECT', 'EFFECT') THEN
      IF arg2 = ph AND arg3 = 'AUTHORISED' THEN kind := 'DUPLICATE'; code := 'VERDICT_RETRY'; ELSE kind := 'DENIED'; code := 'VERDICT_IS_FINAL'; END IF;
    ELSIF ph <> 'CONSUMED' THEN kind := 'DENIED'; code := 'NOT_CONSUMED';
    ELSIF arg3 <> 'AUTHORISED' THEN kind := 'DENIED'; code := 'VERDICT_NOT_AUTHORISED';
    ELSIF w = 'HELD' THEN kind := 'DENIED'; code := 'WITNESS_HELD';
    ELSIF arg2 = 'UNKNOWN' THEN kind := 'NOOP'; code := 'VERDICT_UNKNOWN_STAYS_CHARGED';
    ELSE kind := 'APPLIED'; code := 'VERDICT_RECORDED'; nrow := jsonb_set(a, '{2}', to_jsonb(arg2));
    END IF;
  WHEN 'TIMEOUT', 'MISSING_RECEIPT' THEN
    IF a IS NULL THEN kind := 'DENIED'; code := 'UNKNOWN_ATTEMPT'; ELSE kind := 'NOOP'; code := 'NEVER_REFUNDS'; END IF;
  WHEN 'CRASH' THEN
    kind := 'NOOP'; code := 'CRASH_NEVER_REFUNDS';
  WHEN 'HOLD' THEN
    IF w = 'HELD' THEN kind := 'DENIED'; code := 'ALREADY_HELD'; ELSE kind := 'APPLIED'; code := 'HELD'; nw := 'HELD'; END IF;
  WHEN 'STOP' THEN
    IF b <> 'OPEN' THEN kind := 'DENIED'; code := 'NOT_OPEN'; ELSE kind := 'APPLIED'; code := 'STOPPING'; nb := 'STOPPING'; END IF;
  WHEN 'TERMINALISE' THEN
    IF b <> 'STOPPING' THEN kind := 'DENIED'; code := 'NOT_STOPPING';
    ELSIF w = 'HELD' THEN kind := 'DENIED'; code := 'WITNESS_HELD';
    ELSE kind := 'APPLIED'; code := 'TERMINALISING'; nb := 'TERMINALISING';
    END IF;
  WHEN 'TERMINAL' THEN
    IF b <> 'TERMINALISING' THEN kind := 'DENIED'; code := 'NOT_TERMINALISING';
    ELSIF w = 'HELD' THEN kind := 'DENIED'; code := 'WITNESS_HELD';
    ELSIF EXISTS (SELECT 1 FROM jsonb_array_elements(atts) AS e WHERE e->>2 = ANY(unresolved)) THEN kind := 'DENIED'; code := 'UNRESOLVED_ATTEMPTS';
    ELSE kind := 'APPLIED'; code := 'TERMINAL'; nb := 'TERMINAL';
    END IF;
  WHEN 'RECOVER' THEN
    IF w <> 'HELD' THEN kind := 'DENIED'; code := 'NOT_HELD';
    ELSIF NOT (p_op->>1)::boolean THEN kind := 'DENIED'; code := 'NOT_APPROVED';
    ELSE
      natts := coalesce((SELECT jsonb_agg(CASE e->>2 WHEN 'RESERVING' THEN jsonb_set(e, '{2}', '"DISCARDED"')
                                                   WHEN 'INTENT_PENDING' THEN jsonb_set(jsonb_set(e, '{2}', '"TOKEN"'), '{3}', 'null')
                                                   ELSE e END ORDER BY (e->>0) COLLATE "C")
                         FROM jsonb_array_elements(atts) AS e), '[]'::jsonb);
      nw := CASE WHEN (p_op->>2)::boolean THEN 'ACTIVE' ELSE 'HELD' END;
      IF natts = atts AND nw = w THEN kind := 'NOOP'; code := 'NOTHING_TO_RECOVER';
      ELSE kind := 'APPLIED'; code := CASE WHEN (p_op->>2)::boolean THEN 'RECOVERED' ELSE 'RECOVERED_STILL_HELD' END;
      END IF;
    END IF;
  WHEN 'REREGISTER' THEN
    IF b = 'TERMINAL' THEN kind := 'DENIED'; code := 'TERMINAL';
    ELSIF rr THEN kind := 'DENIED'; code := 'ALREADY_REREGISTERED';
    ELSE
      natts := coalesce((SELECT jsonb_agg(CASE WHEN e->>2 = ANY(unresolved) THEN jsonb_set(e, '{2}', '"INDETERMINATE"') ELSE e END ORDER BY (e->>0) COLLATE "C")
                         FROM jsonb_array_elements(atts) AS e), '[]'::jsonb);
      kind := 'APPLIED'; code := 'REREGISTERED_REDUCED'; nw := 'ACTIVE'; nb := 'STOPPING'; nrr := true;
    END IF;
  END CASE;

  IF kind <> 'APPLIED' THEN
    RETURN jsonb_build_object('kind', kind, 'code', code, 'observation', p_obs);
  END IF;
  IF nrow IS NOT NULL THEN
    natts := (SELECT jsonb_agg(CASE WHEN e->>0 = aid THEN nrow ELSE e END ORDER BY (e->>0) COLLATE "C") FROM jsonb_array_elements(atts) AS e);
  END IF;
  post := public.plea_obs_of(p_obs->'k', p_obs->'m', nw, nb, nrr, natts);
  IF post = public.plea_obs_of(p_obs->'k', p_obs->'m', w, b, rr, atts) THEN
    RAISE EXCEPTION 'contract violation: % was APPLIED without changing the state', p_op;   -- the reference's T8 guard
  END IF;
  RETURN jsonb_build_object('kind', kind, 'code', code, 'observation', post);
END $$ LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog, pg_temp;

CREATE OR REPLACE FUNCTION plea_witness_only_decisions() RETURNS trigger AS $$
BEGIN
  IF (NEW.op->>0) IN ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'RELEASE', 'RECONCILE', 'CROSS')
     AND current_user NOT IN ('plea_witness', 'plea') THEN
    RAISE EXCEPTION 'operation % is reserved to the witness (role %)', NEW.op->>0, current_user
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS witness_only_decisions ON decisions;
CREATE TRIGGER witness_only_decisions BEFORE INSERT ON decisions
  FOR EACH ROW EXECUTE FUNCTION plea_witness_only_decisions();

CREATE OR REPLACE FUNCTION plea_witness_only_phases() RETURNS trigger AS $$
BEGIN
  IF NEW.phase IN ('RESERVED', 'CONSUMED', 'RELEASED', 'NO_EFFECT', 'EFFECT')
     AND (TG_OP = 'INSERT' OR NEW.phase IS DISTINCT FROM OLD.phase)
     AND current_user NOT IN ('plea_witness', 'plea') THEN
    RAISE EXCEPTION 'phase % is set only by the witness (role %)', NEW.phase, current_user
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF NEW.crossed AND (TG_OP = 'INSERT' OR NEW.crossed IS DISTINCT FROM OLD.crossed)
     AND current_user NOT IN ('plea_witness', 'plea') THEN
    RAISE EXCEPTION 'crossed is set only by the witness (role %)', current_user
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS witness_only_phases ON attempts;
CREATE TRIGGER witness_only_phases BEFORE INSERT OR UPDATE ON attempts
  FOR EACH ROW EXECUTE FUNCTION plea_witness_only_phases();

-- v1.2: the provisioning log is append-only for everyone, the owner included (only DROP, an administrative act outside
-- any write path, removes it); and a root's identity, budget, allowance and provisioning record never change.
CREATE OR REPLACE FUNCTION plea_provisions_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'the provisioning log is append-only (% refused)', TG_OP USING ERRCODE = 'check_violation';
END $$ LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp;
DROP TRIGGER IF EXISTS provisions_append_only ON provisions;
CREATE TRIGGER provisions_append_only BEFORE UPDATE OR DELETE ON provisions
  FOR EACH ROW EXECUTE FUNCTION plea_provisions_append_only();
DROP TRIGGER IF EXISTS provisions_no_truncate ON provisions;
CREATE TRIGGER provisions_no_truncate BEFORE TRUNCATE ON provisions
  FOR EACH STATEMENT EXECUTE FUNCTION plea_provisions_append_only();

CREATE OR REPLACE FUNCTION plea_roots_immutable() RETURNS trigger AS $$
BEGIN
  IF NEW.root_id IS DISTINCT FROM OLD.root_id OR NEW.k IS DISTINCT FROM OLD.k OR NEW.m IS DISTINCT FROM OLD.m
     OR NEW.provision_seq IS DISTINCT FROM OLD.provision_seq THEN
    RAISE EXCEPTION 'a root''s identity, budget, allowance and provisioning record never change' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp;
DROP TRIGGER IF EXISTS roots_immutable ON roots;
CREATE TRIGGER roots_immutable BEFORE UPDATE ON roots
  FOR EACH ROW EXECUTE FUNCTION plea_roots_immutable();

-- The one write path.  Appends one audit decision (always), and when the reference APPLIED a change, the attempt
-- upserts and the mode change, enforcing by session_user:
--   * the legal per-attempt transition relation (below), each transition reserved to its operation's credential
--     class -- so no caller can post an attempt state the contract never produces, nor one above its authority;
--   * crossed and receipt are monotone (never reset/cleared) and appear only on a consumption phase;
--   * a new attempt is always a bare RESERVING (RESERVE is the only insert);
--   * every mode change is reserved to the control plane (plea_control), with business never returning to OPEN and
--     never leaving TERMINAL;
--   * the budget k and allowance m are immutable (never written here); live R+live C-credit never exceeds k and
--     live C never exceeds k+m (I1, I2), as a worsening-margin backstop behind the transition relation;
--   * the decision chain is append-only and sequential.  No row is ever deleted.
-- The transition relation is the per-attempt closure of section 5's rules (the producing operation in brackets):
--   insert        -> RESERVING                 [RESERVE]                       gateway
--   RESERVED      -> TOKEN                      [TOKEN]                         gateway
--   TOKEN         -> INTENT_PENDING             [START]                         gateway
--   RESERVING     -> RESERVED                   [ACCEPT_RESERVATION]            witness
--   INTENT_PENDING-> CONSUMED                   [ACCEPT_INTENT]                 witness
--   {RESERVED,TOKEN}-> RELEASED                 [RELEASE]                       witness
--   CONSUMED      -> {NO_EFFECT,EFFECT}         [RECONCILE]                     witness
--   RESERVING     -> DISCARDED                  [RECOVER]                       control
--   INTENT_PENDING-> TOKEN                      [RECOVER, nonce cleared]        control
--   {RESERVING,RESERVED,TOKEN,INTENT_PENDING,CONSUMED} -> INDETERMINATE [REREGISTER]  control
-- plus the in-place flag changes: receipt false->true on a consumption phase [RECEIPT, gateway]; crossed
-- false->true on CONSUMED [CROSS, witness].  Any other (old,new) pair is rejected as illegal.
-- v1.2, after every earlier rule: the root must carry a provisioning record; the record must be exactly the
-- contract's own decision for the operation it names, on the state before the write (plea_step) -- kind, code and
-- every changed row and mode; a control-plane operation is recorded, applied or refused, only by the control plane;
-- and an evidence row is the witness's, for this decision only.
CREATE OR REPLACE FUNCTION plea_write(
    p_root text, p_attempts jsonb, p_modes jsonb, p_seq bigint, p_head text,
    p_op jsonb, p_kind text, p_code text, p_observation jsonb, p_prev_hash text, p_evidence jsonb
) RETURNS void AS $$
DECLARE
  r public.roots%ROWTYPE; a jsonb; op0 text := p_op->>0;
  old_phase text; old_crossed boolean; old_receipt boolean; old_nonce text; old_req text;
  new_phase text; new_crossed boolean; new_receipt boolean; new_nonce text; new_req text; tkey text;
  br int; bc int; bn int; ar int; ac int; an int; bcr int; acr int;
  liveR text[] := ARRAY['RESERVING','RESERVED','TOKEN'];
  liveC text[] := ARRAY['INTENT_PENDING','CONSUMED','NO_EFFECT','EFFECT','INDETERMINATE'];
  consum text[] := ARRAY['CONSUMED','NO_EFFECT','EFFECT','INDETERMINATE'];
  gw_trans  text[] := ARRAY['>RESERVING','RESERVED>TOKEN','TOKEN>INTENT_PENDING'];
  wit_trans text[] := ARRAY['RESERVING>RESERVED','INTENT_PENDING>CONSUMED','RESERVED>RELEASED','TOKEN>RELEASED','CONSUMED>NO_EFFECT','CONSUMED>EFFECT'];
  ctl_trans text[] := ARRAY['RESERVING>DISCARDED','INTENT_PENDING>TOKEN','RESERVING>INDETERMINATE','RESERVED>INDETERMINATE','TOKEN>INDETERMINATE','INTENT_PENDING>INDETERMINATE','CONSUMED>INDETERMINATE'];
  obs_before jsonb; obs_after jsonb; changed boolean; implied text; h text; new_w text; new_b text; new_rr boolean;
  expected jsonb;
BEGIN
  IF op0 IN ('ACCEPT_RESERVATION','ACCEPT_INTENT','RELEASE','RECONCILE','CROSS')
     AND session_user NOT IN ('plea_witness','plea') THEN
    RAISE EXCEPTION 'operation % is reserved to the witness (role %)', op0, session_user USING ERRCODE = 'insufficient_privilege';
  END IF;
  SELECT * INTO r FROM public.roots WHERE root_id = p_root;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown root %', p_root USING ERRCODE = 'no_data_found'; END IF;
  IF r.provision_seq IS NULL THEN   -- v1.2: a root without a provisioning record (not made by plea_new_root) is not written to
    RAISE EXCEPTION 'root % has no provisioning record', p_root USING ERRCODE = 'check_violation';
  END IF;
  IF p_seq IS DISTINCT FROM r.seq + 1 THEN RAISE EXCEPTION 'non-sequential decision % (expected %)', p_seq, r.seq + 1 USING ERRCODE = 'check_violation'; END IF;
  IF p_prev_hash IS DISTINCT FROM r.head_hash THEN RAISE EXCEPTION 'audit chain mismatch' USING ERRCODE = 'check_violation'; END IF;
  -- v1.1: the record's shape, and the state before any write (the kind is bound to the change below)
  IF op0 IS NULL OR op0 NOT IN ('RESERVE','ACCEPT_RESERVATION','TOKEN','START','ACCEPT_INTENT','RECEIPT','CROSS','RELEASE','RECONCILE',
                                 'TIMEOUT','MISSING_RECEIPT','CRASH','HOLD','STOP','TERMINALISE','TERMINAL','RECOVER','REREGISTER') THEN
    RAISE EXCEPTION 'unknown operation %', op0 USING ERRCODE = 'check_violation';
  END IF;
  IF coalesce(p_kind, '') NOT IN ('APPLIED','NOOP','DUPLICATE','DENIED') THEN
    RAISE EXCEPTION 'unknown decision kind %', p_kind USING ERRCODE = 'check_violation';
  END IF;
  IF p_code IS NULL OR p_observation IS NULL OR p_head IS NULL THEN
    RAISE EXCEPTION 'an audit record needs its code, observation and hash' USING ERRCODE = 'check_violation';
  END IF;
  obs_before := public.plea_observe(p_root);

  SELECT count(*) FILTER (WHERE phase = ANY(liveR)), count(*) FILTER (WHERE phase = ANY(liveC)),
         count(*) FILTER (WHERE phase = 'NO_EFFECT') INTO br, bc, bn FROM public.attempts WHERE root_id = p_root;

  IF p_attempts IS NOT NULL THEN
    FOR a IN SELECT * FROM jsonb_array_elements(p_attempts) LOOP
      new_phase := a->>'phase'; new_crossed := (a->>'crossed')::boolean; new_receipt := (a->>'receipt')::boolean;
      new_nonce := a->>'nonce'; new_req := a->>'req';
      SELECT phase, crossed, receipt, nonce, req INTO old_phase, old_crossed, old_receipt, old_nonce, old_req
        FROM public.attempts WHERE root_id = p_root AND aid = a->>'aid';
      tkey := coalesce(old_phase, '') || '>' || new_phase;

      -- v1.1: the operation named must be the one that produces this change (the record is bound to the transition)
      IF old_phase IS DISTINCT FROM new_phase THEN
        implied := CASE tkey
          WHEN '>RESERVING' THEN 'RESERVE' WHEN 'RESERVED>TOKEN' THEN 'TOKEN' WHEN 'TOKEN>INTENT_PENDING' THEN 'START'
          WHEN 'RESERVING>RESERVED' THEN 'ACCEPT_RESERVATION' WHEN 'INTENT_PENDING>CONSUMED' THEN 'ACCEPT_INTENT'
          WHEN 'RESERVED>RELEASED' THEN 'RELEASE' WHEN 'TOKEN>RELEASED' THEN 'RELEASE'
          WHEN 'CONSUMED>NO_EFFECT' THEN 'RECONCILE' WHEN 'CONSUMED>EFFECT' THEN 'RECONCILE'
          WHEN 'RESERVING>DISCARDED' THEN 'RECOVER' WHEN 'INTENT_PENDING>TOKEN' THEN 'RECOVER'
          WHEN 'RESERVING>INDETERMINATE' THEN 'REREGISTER' WHEN 'RESERVED>INDETERMINATE' THEN 'REREGISTER' WHEN 'TOKEN>INDETERMINATE' THEN 'REREGISTER'
          WHEN 'INTENT_PENDING>INDETERMINATE' THEN 'REREGISTER' WHEN 'CONSUMED>INDETERMINATE' THEN 'REREGISTER' END;
        IF implied IS NOT NULL AND op0 <> implied THEN
          RAISE EXCEPTION 'operation % does not produce the transition %->% (% does)', op0, coalesce(old_phase, '(new)'), new_phase, implied USING ERRCODE = 'check_violation';
        END IF;
      ELSE
        IF new_receipt AND NOT coalesce(old_receipt, false) AND op0 <> 'RECEIPT' THEN
          RAISE EXCEPTION 'operation % does not record a receipt (RECEIPT does)', op0 USING ERRCODE = 'check_violation';
        END IF;
        IF new_crossed AND NOT coalesce(old_crossed, false) AND op0 <> 'CROSS' THEN
          RAISE EXCEPTION 'operation % does not record the crossing (CROSS does)', op0 USING ERRCODE = 'check_violation';
        END IF;
      END IF;

      -- v1.0: the accepted bindings are immutable.  req never changes.  nonce is set only by START
      -- (TOKEN->INTENT_PENDING) and cleared only by RECOVER (INTENT_PENDING->TOKEN); on every other update -- a
      -- same-phase rewrite included -- it must be carried unchanged.
      IF old_phase IS NOT NULL THEN
        IF old_req IS DISTINCT FROM new_req THEN
          RAISE EXCEPTION 'the request binding of attempt % is immutable', a->>'aid' USING ERRCODE = 'check_violation';
        END IF;
        IF tkey = 'TOKEN>INTENT_PENDING' THEN
          IF old_nonce IS NOT NULL OR new_nonce IS NULL THEN
            RAISE EXCEPTION 'START must bind a fresh nonce to attempt %', a->>'aid' USING ERRCODE = 'check_violation';
          END IF;
        ELSIF tkey = 'INTENT_PENDING>TOKEN' THEN
          IF new_nonce IS NOT NULL THEN
            RAISE EXCEPTION 'RECOVER clears the nonce of attempt %', a->>'aid' USING ERRCODE = 'check_violation';
          END IF;
        ELSIF old_nonce IS DISTINCT FROM new_nonce THEN
          RAISE EXCEPTION 'the accepted executor/action binding (nonce) of attempt % is immutable', a->>'aid' USING ERRCODE = 'check_violation';
        END IF;
      END IF;

      -- legal per-attempt phase transition, reserved to its operation's credential class
      IF old_phase IS DISTINCT FROM new_phase THEN
        IF tkey = ANY(wit_trans) THEN
          IF session_user NOT IN ('plea_witness','plea') THEN
            RAISE EXCEPTION 'transition %->% is reserved to the witness (role %)', coalesce(old_phase,'(new)'), new_phase, session_user USING ERRCODE = 'insufficient_privilege';
          END IF;
        ELSIF tkey = ANY(ctl_trans) THEN
          IF session_user NOT IN ('plea_control','plea') THEN
            RAISE EXCEPTION 'transition %->% is reserved to the control plane (role %)', coalesce(old_phase,'(new)'), new_phase, session_user USING ERRCODE = 'insufficient_privilege';
          END IF;
        ELSIF tkey = ANY(gw_trans) THEN
          NULL;   -- any authenticated writer may drive a gateway-class transition
        ELSE
          RAISE EXCEPTION 'illegal attempt transition %->% (not produced by any contract operation)', coalesce(old_phase,'(new)'), new_phase USING ERRCODE = 'check_violation';
        END IF;
        IF old_phase IS NULL AND (new_crossed OR new_receipt OR (a->>'nonce') IS NOT NULL) THEN
          RAISE EXCEPTION 'a new attempt must be a bare reservation' USING ERRCODE = 'check_violation';
        END IF;
      END IF;

      -- crossed: witness-only, monotone, only on a consumption phase
      IF new_crossed AND (old_crossed IS NULL OR old_crossed = false) AND session_user NOT IN ('plea_witness','plea') THEN
        RAISE EXCEPTION 'crossed is set only by the witness (role %)', session_user USING ERRCODE = 'insufficient_privilege';
      END IF;
      IF old_crossed = true AND new_crossed = false THEN
        RAISE EXCEPTION 'crossed cannot be reset (T7)' USING ERRCODE = 'check_violation';
      END IF;
      IF new_crossed AND NOT (new_phase = ANY(consum)) THEN
        RAISE EXCEPTION 'crossed only on a consumption phase (got %)', new_phase USING ERRCODE = 'check_violation';
      END IF;

      -- receipt: monotone, and recorded only on an accepted consumption
      IF old_receipt = true AND new_receipt = false THEN
        RAISE EXCEPTION 'receipt cannot be cleared' USING ERRCODE = 'check_violation';
      END IF;
      IF new_receipt AND (old_receipt IS NULL OR old_receipt = false) AND new_phase NOT IN ('CONSUMED','NO_EFFECT','EFFECT') THEN
        RAISE EXCEPTION 'receipt is recorded only on an accepted consumption (got %)', new_phase USING ERRCODE = 'check_violation';
      END IF;
      IF new_receipt AND NOT (new_phase = ANY(consum)) THEN
        RAISE EXCEPTION 'receipt only on a consumption phase (got %)', new_phase USING ERRCODE = 'check_violation';
      END IF;

      INSERT INTO public.attempts (root_id, aid, req, phase, nonce, receipt, crossed)
        VALUES (p_root, a->>'aid', new_req, new_phase, new_nonce, new_receipt, new_crossed)
        ON CONFLICT (root_id, aid) DO UPDATE SET phase = EXCLUDED.phase, nonce = EXCLUDED.nonce,
                                                 receipt = EXCLUDED.receipt, crossed = EXCLUDED.crossed;
    END LOOP;
  END IF;

  IF p_modes IS NOT NULL THEN
    IF session_user NOT IN ('plea_control','plea') THEN
      RAISE EXCEPTION 'a mode change is reserved to the control plane (role %)', session_user USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (p_modes->>'business') = 'OPEN' AND r.business <> 'OPEN' THEN RAISE EXCEPTION 'business cannot return to OPEN' USING ERRCODE = 'check_violation'; END IF;
    IF r.business = 'TERMINAL' THEN RAISE EXCEPTION 'TERMINAL is final' USING ERRCODE = 'check_violation'; END IF;
    -- v1.1: every mode change is the one its operation makes, and only the contract's mode pairs exist
    new_w := p_modes->>'witness'; new_b := p_modes->>'business'; new_rr := (p_modes->>'reregistered')::boolean;
    IF new_w IS NULL OR new_w NOT IN ('ACTIVE','HELD') OR new_b IS NULL OR new_b NOT IN ('OPEN','STOPPING','TERMINALISING','TERMINAL') OR new_rr IS NULL THEN
      RAISE EXCEPTION 'unknown mode' USING ERRCODE = 'check_violation';
    END IF;
    IF new_w IS DISTINCT FROM r.witness THEN
      IF new_w = 'HELD' AND op0 <> 'HOLD' THEN RAISE EXCEPTION 'operation % does not hold the witness (HOLD does)', op0 USING ERRCODE = 'check_violation'; END IF;
      IF new_w = 'ACTIVE' AND op0 NOT IN ('RECOVER','REREGISTER') THEN RAISE EXCEPTION 'operation % does not reactivate the witness (RECOVER, REREGISTER do)', op0 USING ERRCODE = 'check_violation'; END IF;
    END IF;
    IF new_b IS DISTINCT FROM r.business THEN
      -- the contract's business pairs: OPEN->STOPPING (STOP, REREGISTER), STOPPING->TERMINALISING (TERMINALISE),
      -- TERMINALISING->TERMINAL (TERMINAL), and TERMINALISING->STOPPING (REREGISTER restarts in STOPPING, erratum E6)
      IF NOT ((r.business = 'OPEN' AND new_b = 'STOPPING') OR (r.business = 'STOPPING' AND new_b = 'TERMINALISING')
              OR (r.business = 'TERMINALISING' AND new_b = 'TERMINAL') OR (r.business = 'TERMINALISING' AND new_b = 'STOPPING')) THEN
        RAISE EXCEPTION 'illegal business transition %->%', r.business, new_b USING ERRCODE = 'check_violation';
      END IF;
      IF new_b = 'STOPPING' AND NOT (op0 = 'REREGISTER' OR (op0 = 'STOP' AND r.business = 'OPEN')) THEN
        RAISE EXCEPTION 'operation % does not move the run to STOPPING from % (STOP from OPEN, REREGISTER do)', op0, r.business USING ERRCODE = 'check_violation';
      END IF;
      IF new_b = 'TERMINALISING' AND op0 <> 'TERMINALISE' THEN RAISE EXCEPTION 'operation % does not terminalise (TERMINALISE does)', op0 USING ERRCODE = 'check_violation'; END IF;
      IF new_b = 'TERMINAL' AND op0 <> 'TERMINAL' THEN RAISE EXCEPTION 'operation % does not make the run terminal (TERMINAL does)', op0 USING ERRCODE = 'check_violation'; END IF;
    END IF;
    IF new_rr IS DISTINCT FROM r.reregistered THEN
      IF r.reregistered OR op0 <> 'REREGISTER' THEN RAISE EXCEPTION 'only REREGISTER re-registers, once' USING ERRCODE = 'check_violation'; END IF;
    END IF;
    UPDATE public.roots SET witness = p_modes->>'witness', business = p_modes->>'business',
                     reregistered = (p_modes->>'reregistered')::boolean WHERE root_id = p_root;
  END IF;

  SELECT count(*) FILTER (WHERE phase = ANY(liveR)), count(*) FILTER (WHERE phase = ANY(liveC)),
         count(*) FILTER (WHERE phase = 'NO_EFFECT') INTO ar, ac, an FROM public.attempts WHERE root_id = p_root;
  bcr := least(bn, r.m); acr := least(an, r.m);
  IF ac > r.k + r.m AND ac > bc THEN
    RAISE EXCEPTION 'I1 violated: live C % > k+m %', ac, r.k + r.m USING ERRCODE = 'check_violation';
  END IF;
  IF (ar + ac - acr) > r.k AND (ar + ac - acr) > (br + bc - bcr) THEN
    RAISE EXCEPTION 'I2 violated: live R+C-credit % > k %', ar + ac - acr, r.k USING ERRCODE = 'check_violation';
  END IF;

  -- v1.1: the record is bound to the state it records.  The observation is derived from the rows now written; the
  -- kind is APPLIED exactly when the state changed; the hash is recomputed over exactly what is stored.
  obs_after := public.plea_observe(p_root);
  changed := (obs_before <> obs_after);
  IF (p_kind = 'APPLIED') <> changed THEN
    RAISE EXCEPTION 'decision kind % does not describe this write (state changed: %)', p_kind, changed USING ERRCODE = 'check_violation';
  END IF;
  IF p_observation <> obs_after THEN
    RAISE EXCEPTION 'the recorded observation does not describe the state after this decision' USING ERRCODE = 'check_violation';
  END IF;
  h := public.plea_decision_hash(p_prev_hash, jsonb_build_object('seq', p_seq, 'op', p_op, 'kind', p_kind, 'code', p_code, 'observation', obs_after));
  IF p_head IS DISTINCT FROM h THEN
    RAISE EXCEPTION 'the decision hash does not bind this record to the state it records' USING ERRCODE = 'check_violation';
  END IF;
  -- v1.2: the record is the contract's own decision.  The contract's step, evaluated here on the state before the
  -- write, must give exactly this kind and code, and exactly the state now written: so the operands the record names
  -- (attempt, request, nonce, verdict, evidence label), the extent of a batch and every mode guard are bound to the
  -- rows, and a refusal, NOOP or DUPLICATE must be the one the contract gives.
  expected := public.plea_step(obs_before, p_op);
  IF expected->>'kind' IS DISTINCT FROM p_kind OR expected->>'code' IS DISTINCT FROM p_code THEN
    RAISE EXCEPTION 'the contract decides % here as % (%), not % (%)', p_op, expected->>'kind', expected->>'code', p_kind, p_code
      USING ERRCODE = 'check_violation';
  END IF;
  IF expected->'observation' IS DISTINCT FROM obs_after THEN
    RAISE EXCEPTION 'operation % does not produce the rows written: the attempts or modes it changes differ from its contract transition', p_op
      USING ERRCODE = 'check_violation';
  END IF;
  IF op0 IN ('HOLD','STOP','TERMINALISE','TERMINAL','RECOVER','REREGISTER') AND session_user NOT IN ('plea_control','plea') THEN
    RAISE EXCEPTION 'operation % is the control plane''s to record, applied or refused (role %)', op0, session_user USING ERRCODE = 'insufficient_privilege';
  END IF;
  -- v1.2: an evidence row (the report the witness verified and the label it derived) belongs to its decision: only the
  -- witness records one, only with a RELEASE or RECONCILE, and only for this decision's attempt, sequence number and
  -- label.  (Before, any writer could attach one to any record, under any sequence number -- taking the slot of the
  -- witness's next RELEASE, whose own evidence then failed to insert -- with any label.)
  IF p_evidence IS NOT NULL THEN
    IF session_user NOT IN ('plea_witness','plea') THEN
      RAISE EXCEPTION 'evidence is recorded only by the witness (role %)', session_user USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF op0 NOT IN ('RELEASE','RECONCILE') OR p_evidence->>'aid' IS DISTINCT FROM p_op->>1
       OR (p_evidence->>'seq') IS DISTINCT FROM p_seq::text
       OR p_evidence->>'derived' IS DISTINCT FROM p_op->>(jsonb_array_length(p_op) - 1)
       OR coalesce(jsonb_typeof(p_evidence->'evidence'), 'null') = 'null' THEN
      RAISE EXCEPTION 'the evidence row must belong to this decision: a RELEASE or RECONCILE, its attempt, its sequence number and its derived label'
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  UPDATE public.roots SET seq = p_seq, head_hash = h WHERE root_id = p_root;
  INSERT INTO public.decisions (root_id, seq, op, kind, code, observation, prev_hash, hash)
    VALUES (p_root, p_seq, p_op, p_kind, p_code, obs_after, p_prev_hash, h);
  IF p_evidence IS NOT NULL THEN
    INSERT INTO public.evidence (root_id, aid, seq, evidence, derived)
      VALUES (p_root, p_evidence->>'aid', (p_evidence->>'seq')::bigint, p_evidence->'evidence', p_evidence->>'derived');
  END IF;
END $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp;

-- The only way to create a root -- i.e. to provision a budget.  v1.1: reserved to the control plane (the gateway
-- credential cannot mint itself an allowance); rejects a duplicate.  v1.2: appends the provisioning record -- root, k,
-- m, the issuing credential, the contract and release, the database time -- to the provisioning log, linked to the
-- record before it, and starts the root's chain at that record's hash (the anchor).  No caller supplies a hash.
-- Provisionings serialise on a transaction advisory lock, so the log stays one contiguous chain.
CREATE OR REPLACE FUNCTION plea_new_root(p_root text, p_k integer, p_m integer) RETURNS jsonb AS $$
DECLARE prev text; n bigint; body jsonb; h text;
BEGIN
  IF session_user NOT IN ('plea_control', 'plea') THEN
    RAISE EXCEPTION 'provisioning a root is reserved to the control plane (role %)', session_user USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF p_root IS NULL OR p_root = '' THEN RAISE EXCEPTION 'a root identity is a non-empty string' USING ERRCODE = 'check_violation'; END IF;
  IF p_k IS NULL OR p_m IS NULL OR p_k < 0 OR p_m < 0 THEN RAISE EXCEPTION 'invalid budget or allowance' USING ERRCODE = 'check_violation'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('plea-provisioning-log', 0));
  IF EXISTS (SELECT 1 FROM public.roots WHERE root_id = p_root) THEN
    RAISE EXCEPTION 'root % is already provisioned', p_root USING ERRCODE = 'unique_violation';
  END IF;
  SELECT seq, hash INTO n, prev FROM public.provisions ORDER BY seq DESC LIMIT 1;
  IF NOT FOUND THEN
    n := 0; prev := encode(sha256(convert_to('plea-gateway-v0', 'UTF8')), 'hex');   -- the genesis, as the client's GENESIS
  END IF;
  body := jsonb_build_object('record', 'PROVISION', 'seq', n + 1, 'root', p_root, 'k', p_k, 'm', p_m, 'issuer', session_user::text,
                             'contract', 'attempt-budget contract v3.1', 'release', 'plea-gateway v1.2',
                             'created_at', to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  h := public.plea_decision_hash(prev, body);
  INSERT INTO public.provisions (seq, root_id, k, m, issuer, contract, release, created_at, prev_hash, hash)
    VALUES (n + 1, p_root, p_k, p_m, session_user::text, body->>'contract', body->>'release', body->>'created_at', prev, h);
  INSERT INTO public.roots (root_id, k, m, witness, business, head_hash, provision_seq)
    VALUES (p_root, p_k, p_m, 'ACTIVE', 'OPEN', h, n + 1);
  RETURN body || jsonb_build_object('prev_hash', prev, 'hash', h);
END $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp;

-- v1.0: the only way to store an outcome.  An outcome exists only for an attempt the witness admitted (crossed) and
-- that is consumed; the first stored outcome stands, except that an 'unknown' is replaced by a later one.  So a
-- results row can never be fabricated for an attempt that was never admitted, and never rewritten once known.
CREATE OR REPLACE FUNCTION plea_put_result(p_root text, p_aid text, p_result jsonb) RETURNS void AS $$
DECLARE ph text; cr boolean;
BEGIN
  SELECT phase, crossed INTO ph, cr FROM public.attempts WHERE root_id = p_root AND aid = p_aid;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'no attempt % to store an outcome for', p_aid USING ERRCODE = 'check_violation';
  END IF;
  IF ph NOT IN ('CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE') OR NOT cr THEN
    RAISE EXCEPTION 'an outcome is stored only for an admitted, consumed attempt (% is % and crossed=%)', p_aid, ph, cr USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO public.results AS res (root_id, aid, result) VALUES (p_root, p_aid, p_result)
    ON CONFLICT (root_id, aid) DO UPDATE SET result = EXCLUDED.result WHERE (res.result->>'outcome') = 'unknown';
END $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp;

-- Authoritative tables and the results cache: no direct writes for any login role; they write through the
-- functions only.  Receipts are a client cache the governor re-verifies on read (signature and chain hash), so the
-- gateway and witness may insert them; never delete or rewrite one.  The control plane never writes a cache.
REVOKE INSERT, UPDATE, DELETE ON public.roots, public.attempts, public.decisions, public.evidence, public.results
  FROM plea_local, plea_witness, plea_control;
GRANT SELECT ON public.roots, public.attempts, public.decisions, public.results, public.receipts, public.evidence
  TO plea_local, plea_witness, plea_control;
GRANT INSERT ON public.receipts TO plea_local, plea_witness;
REVOKE UPDATE, DELETE ON public.receipts FROM plea_local, plea_witness;
REVOKE INSERT, UPDATE, DELETE ON public.receipts FROM plea_control;
-- v1.2: the provisioning log is read by every login role (verification) and written by none (plea_new_root only).
REVOKE ALL ON public.provisions FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.provisions FROM plea_local, plea_witness, plea_control;
GRANT SELECT ON public.provisions TO plea_local, plea_witness, plea_control;
-- v1.0: PostgreSQL grants EXECUTE on a new function to PUBLIC by default; revoke it, then grant by name.  The
-- gateway and the witness drive the write function; the control plane too (mode changes); only the control plane
-- provisions roots (v1.1); only the gateway (the governor) stores outcomes; the canonical-form, hash and
-- observation helpers are the owner's (plea_write calls them) and no login role may call them.
REVOKE EXECUTE ON FUNCTION plea_jstr(text), plea_canonical(jsonb), plea_decision_hash(text, jsonb), plea_observe(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION plea_obs_of(jsonb, jsonb, text, text, boolean, jsonb), plea_step(jsonb, jsonb) FROM PUBLIC;   -- v1.2: the owner's
REVOKE EXECUTE ON FUNCTION plea_write(text, jsonb, jsonb, bigint, text, jsonb, text, text, jsonb, text, jsonb) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION plea_new_root(text, int, int) FROM PUBLIC, plea_local, plea_witness;   -- v1.2 signature (no caller hash)
REVOKE EXECUTE ON FUNCTION plea_put_result(text, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION plea_write(text, jsonb, jsonb, bigint, text, jsonb, text, text, jsonb, text, jsonb) TO plea_local, plea_witness, plea_control;
GRANT EXECUTE ON FUNCTION plea_new_root(text, int, int) TO plea_control;
GRANT EXECUTE ON FUNCTION plea_put_result(text, text, jsonb) TO plea_local;
-- No login role may create objects in public (v0.9), on top of the qualified references and pg_temp-last path.
REVOKE CREATE ON SCHEMA public FROM PUBLIC, plea_local, plea_witness, plea_control;
"""

GENESIS = hashlib.sha256(b'plea-gateway-v0').hexdigest()       # v1.2: the genesis of the provisioning log
PROVISION_FIELDS = ('record', 'seq', 'root', 'k', 'm', 'issuer', 'contract', 'release', 'created_at')   # the hashed body
WITNESS_OPS = ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'RELEASE', 'RECONCILE', 'CROSS')   # v0.7: the crossing is witnessed


@dataclass(frozen=True)
class Decision:
    kind: str
    code: str


class RootExists(Exception):
    pass


class UnknownRoot(Exception):
    pass


class AuthorityError(PermissionError):
    """The database refused the operation to this role.  The transaction was rolled back."""


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _jsonable(obs: dict) -> dict:
    """The section 7 observation with tuples as lists, as JSON stores it."""
    return json.loads(json.dumps(obs))


def chain_hash(prev_hash: str, seq: int, op, kind: str, code: str, observation: dict) -> str:
    body = _canonical({'seq': seq, 'op': op, 'kind': kind, 'code': code, 'observation': observation})
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def provision_hash(prev_hash: str, record: dict) -> str:
    """v1.2: the hash of a provisioning record, as plea_new_root computes it: sha256(prev || canonical(body))."""
    return hashlib.sha256((prev_hash + _canonical({f: record[f] for f in PROVISION_FIELDS})).encode()).hexdigest()


def _provision_dict(row) -> dict:
    seq, root, k, m, issuer, contract, release, created_at, prev_hash, h = row
    return {'record': 'PROVISION', 'seq': seq, 'root': root, 'k': k, 'm': m, 'issuer': issuer, 'contract': contract,
            'release': release, 'created_at': created_at, 'prev_hash': prev_hash, 'hash': h}


_PROVISION_COLUMNS = 'p.seq, p.root_id, p.k, p.m, p.issuer, p.contract, p.release, p.created_at, p.prev_hash, p.hash'


class Store:
    def __init__(self, dsn: str, mode: str = 'lock'):
        if mode not in ('lock', 'serializable'):
            raise ValueError(mode)
        self.dsn, self.mode = dsn, mode

    # ------------------------------------------------------------------ connections and schema
    def connect(self):
        return psycopg.connect(self.dsn, autocommit=False)

    def init_schema(self, drop: bool = False) -> None:
        with self.connect() as conn:
            if drop:
                conn.execute('DROP TABLE IF EXISTS evidence, receipts, results, decisions, attempts, roots, provisions CASCADE')
            conn.execute(SCHEMA)
            conn.commit()

    def init_authority(self) -> None:
        """Owner only: install the witness-only triggers and the role grants."""
        with self.connect() as conn:
            conn.execute(AUTHORITY)
            conn.commit()

    # ------------------------------------------------------------------ roots
    def new_root(self, root_id: str, k: int, m: int) -> dict:
        """Provision a root (the control plane, or the owner).  v1.2: returns the provisioning record, whose hash is the
        root's anchor; the database computes it -- no caller supplies a starting hash."""
        ref._require_count(k, 'budget k'); ref._require_count(m, 'replacement allowance m')
        ref._require_identity(root_id, 'root identity')
        with self.connect() as conn:
            try:
                record = conn.execute('SELECT plea_new_root(%s, %s, %s)', (root_id, k, m)).fetchone()[0]
                conn.commit()
                return record
            except errors.UniqueViolation:
                conn.rollback(); raise RootExists(root_id)
            except errors.InsufficientPrivilege as exc:       # v1.1: provisioning is the control plane's
                conn.rollback(); raise AuthorityError(str(exc).splitlines()[0]) from None

    def provisioning(self, root_id: str):
        """v1.2: the provisioning record a root's chain starts from, or None (no such root, or no record)."""
        with self.connect() as conn:
            row = conn.execute(f'SELECT {_PROVISION_COLUMNS} FROM roots r JOIN provisions p ON p.seq = r.provision_seq '
                               'WHERE r.root_id = %s', (root_id,)).fetchone()
        return None if row is None else _provision_dict(row)

    def verify_provisioning(self) -> tuple[bool, str, int]:
        """v1.2: walk the whole provisioning log from the genesis: contiguous, each record linked to the one before it
        and hashing to its stored hash.  Returns (ok, detail, records)."""
        with self.connect() as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            rows = conn.execute(f'SELECT {_PROVISION_COLUMNS} FROM provisions p ORDER BY p.seq').fetchall()
            conn.rollback()
        prev = GENESIS
        for i, row in enumerate(rows, 1):
            rec = _provision_dict(row)
            if rec['seq'] != i:
                return False, f'record {rec["seq"]}: the log is not contiguous (expected {i})', len(rows)
            if rec['prev_hash'] != prev:
                return False, f'record {i}: not linked to the record before it', len(rows)
            if provision_hash(prev, rec) != rec['hash']:
                return False, f'record {i}: its hash does not match its content', len(rows)
            prev = rec['hash']
        return True, 'ok', len(rows)

    def put_state(self, root_id: str, state) -> None:
        """Overwrite a root with a constructed state (for conformance vectors that build states directly).  Owner only.
        v1.2: the root is provisioned as any root is (so it carries a record and an anchor), then its facts are set."""
        if not isinstance(state, ref.RootState):
            raise ref.InvalidInput('not a root state')
        with self.connect() as conn:
            conn.execute('DELETE FROM roots WHERE root_id = %s', (root_id,))
            conn.execute('SELECT plea_new_root(%s, %s, %s)', (root_id, state.k, state.m))
            conn.execute('UPDATE roots SET witness = %s, business = %s, reregistered = %s WHERE root_id = %s',
                         (state.witness.value, state.business.value, state.reregistered, root_id))
            for a in state.attempts:
                conn.execute('INSERT INTO attempts (root_id, aid, req, phase, nonce, receipt, crossed) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                             (root_id, a.aid, a.req, a.phase.value, a.nonce, a.receipt, a.crossed))
            conn.commit()

    def _load(self, conn, root_id: str, lock: bool = False):
        # No FOR UPDATE (v0.8): the gateway credential holds no UPDATE privilege, and SELECT ... FOR UPDATE requires
        # it.  Writers serialise on a per-root transaction advisory lock taken in _apply_in instead; reads are
        # unlocked, from a consistent snapshot where it matters (observe/state/verify_chain use REPEATABLE READ).
        row = conn.execute('SELECT k, m, witness, business, reregistered, seq, head_hash FROM roots WHERE root_id = %s',
                           (root_id,)).fetchone()
        if row is None:
            raise UnknownRoot(root_id)
        k, m, witness, business, reregistered, seq, head = row
        rows = conn.execute('SELECT aid, req, phase, nonce, receipt, crossed FROM attempts WHERE root_id = %s ORDER BY aid',
                            (root_id,)).fetchall()
        attempts = tuple(ref.AttemptFacts(aid, req, phase, nonce, receipt, crossed) for aid, req, phase, nonce, receipt, crossed in rows)
        state = ref.RootState(k, m, witness, business, attempts, reregistered)       # validates itself (section 8)
        return state, seq, head

    # ------------------------------------------------------------------ the operation
    def apply(self, root_id: str, op) -> tuple[Decision, dict]:
        decision, observation, _, _ = self.apply_ex(root_id, op)
        return decision, observation

    def apply_ex(self, root_id: str, op, evidence=None, derived: str | None = None) -> tuple[Decision, dict, int, str]:
        """apply, also returning the audit sequence number and hash of the recorded decision.  evidence (v0.6): the
        report the witness verified for this decision and the label it derived, recorded in the same transaction as
        the decision, so neither can exist without the other (the v0.4 review found them committed separately)."""
        parsed = ref.parse_op(op)                                                   # step 1: InvalidInput before the store
        op_json = json.loads(json.dumps(op))
        while True:
            with self.connect() as conn:
                if self.mode == 'serializable':
                    conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
                try:
                    result = self._apply_in(conn, root_id, parsed, op_json, evidence, derived)
                    crash_point('before_commit')
                    conn.commit()
                    crash_point('after_commit')
                    return result
                except errors.SerializationFailure:
                    conn.rollback()
                    if self.mode != 'serializable':
                        raise
                    continue                                                        # retry, as serializable mode requires
                except errors.InsufficientPrivilege as exc:
                    conn.rollback()
                    raise AuthorityError(str(exc).splitlines()[0]) from None

    def _apply_in(self, conn, root_id, parsed, op_json, evidence=None, derived=None):
        if self.mode == 'lock':
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (root_id,))   # serialise writers to this root
        state, seq, head = self._load(conn, root_id)
        crash_point('after_lock')
        decision, new_state = ref.apply(state, parsed)                              # the verified pure engine decides
        crash_point('after_decide')
        kind, code = decision.kind.value, decision.code
        attempts_payload, modes_payload = [], None
        if kind == 'APPLIED':
            before = {a.aid: a for a in state.attempts}
            for a in new_state.attempts:
                old = before.get(a.aid)
                if old is None or old != a:
                    attempts_payload.append({'aid': a.aid, 'req': a.req, 'phase': a.phase.value,
                                             'nonce': a.nonce, 'receipt': a.receipt, 'crossed': a.crossed})
            if (new_state.witness, new_state.business, new_state.reregistered) != (state.witness, state.business, state.reregistered):
                modes_payload = {'witness': new_state.witness.value, 'business': new_state.business.value,
                                 'reregistered': new_state.reregistered}
        crash_point('after_attempts')
        observation = _jsonable(ref.observe(new_state))
        new_seq = seq + 1
        digest = chain_hash(head, new_seq, op_json, kind, code, observation)
        ev_payload = {'aid': op_json[1], 'seq': new_seq, 'evidence': evidence, 'derived': derived} if evidence is not None else None
        # One guarded write (plea_write, SECURITY DEFINER): the gateway credential cannot mutate the authoritative
        # tables any other way.  The function enforces the structural invariants and the witness-only authority, so a
        # correct apply writes exactly as before and a forged call cannot rewrite accounting.  In serializable mode
        # two transactions both UPDATE the root row inside the function; one gets a serialization failure and retries.
        conn.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                     (root_id, json.dumps(attempts_payload), json.dumps(modes_payload) if modes_payload is not None else None,
                      new_seq, digest, json.dumps(op_json), kind, code, json.dumps(observation), head,
                      json.dumps(ev_payload) if ev_payload is not None else None))
        crash_point('after_audit')
        return Decision(kind, code), observation, new_seq, digest

    # ------------------------------------------------------------------ reads
    def observe(self, root_id: str) -> dict:
        """The section 7 observation from one consistent snapshot (REPEATABLE READ), with no lock."""
        with self.connect() as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            state, _, _ = self._load(conn, root_id, lock=False)
            conn.rollback()
        return _jsonable(ref.observe(state))

    def state(self, root_id: str):
        with self.connect() as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            state, seq, head = self._load(conn, root_id, lock=False)
            conn.rollback()
        return state, seq, head

    def audit(self, root_id: str) -> list:
        with self.connect() as conn:
            return self._audit_in(conn, root_id)

    @staticmethod
    def _audit_in(conn, root_id: str) -> list:
        rows = conn.execute('SELECT seq, op, kind, code, observation, prev_hash, hash FROM decisions WHERE root_id = %s ORDER BY seq',
                            (root_id,)).fetchall()
        return [{'seq': s, 'op': op, 'kind': kind, 'code': code, 'observation': obs, 'prev_hash': p, 'hash': h}
                for s, op, kind, code, obs, p, h in rows]

    def audit_snapshot(self, root_id: str) -> tuple[list, dict]:
        """The audit log and the current observation from one consistent snapshot (v0.6; the v0.4 review noted that a
        replay read them from two)."""
        with self.connect() as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            log = self._audit_in(conn, root_id)
            state, _, _ = self._load(conn, root_id, lock=False)
            conn.rollback()
        return log, _jsonable(ref.observe(state))

    def root_exists(self, root_id: str) -> bool:
        """Whether the store holds this root (verification Amendment 11: one rule for the witness's readings)."""
        with self.connect() as conn:
            return conn.execute('SELECT 1 FROM roots WHERE root_id = %s', (root_id,)).fetchone() is not None

    def audit_after(self, root_id: str, after: int, limit: int) -> list:
        """The audit rows after sequence number `after`, at most `limit` of them, in order (verification Amendment 11: the
        witness's reading for a courier).  An unknown root raises UnknownRoot."""
        with self.connect() as conn:
            if conn.execute('SELECT 1 FROM roots WHERE root_id = %s', (root_id,)).fetchone() is None:
                raise UnknownRoot(root_id)
            rows = conn.execute('SELECT seq, op, kind, code, observation, prev_hash, hash FROM decisions WHERE root_id = %s AND seq > %s ORDER BY seq LIMIT %s',
                                (root_id, after, limit)).fetchall()
        return [{'seq': s, 'op': op, 'kind': kind, 'code': code, 'observation': obs, 'prev_hash': p, 'hash': h}
                for s, op, kind, code, obs, p, h in rows]

    def decision_hash(self, root_id: str, seq: int):
        with self.connect() as conn:
            row = conn.execute('SELECT hash FROM decisions WHERE root_id = %s AND seq = %s', (root_id, seq)).fetchone()
        return None if row is None else row[0]

    def verify_chain(self, root_id: str) -> tuple[bool, str]:
        """Recompute every hash from the root's anchor and check the root's head, from one snapshot (v0.7: read in two,
        a concurrent append made it report a head that did not match the log).  v1.2: the chain starts at the hash of
        the root's provisioning record, which must hash to itself and name this root, k and m; every recorded
        observation must carry that k and m."""
        with self.connect() as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            head_row = conn.execute('SELECT seq, head_hash, k, m, provision_seq FROM roots WHERE root_id = %s', (root_id,)).fetchone()
            prov = None
            if head_row is not None and head_row[4] is not None:
                prov = conn.execute(f'SELECT {_PROVISION_COLUMNS} FROM provisions p WHERE p.seq = %s', (head_row[4],)).fetchone()
            log = self._audit_in(conn, root_id) if head_row is not None else []
            conn.rollback()
        if head_row is None:
            return False, 'unknown root'
        if prov is None:
            return False, 'no provisioning record'
        rec = _provision_dict(prov)
        if provision_hash(rec['prev_hash'], rec) != rec['hash']:
            return False, 'the provisioning record does not hash to itself'
        if rec['root'] != root_id or (rec['k'], rec['m']) != (head_row[2], head_row[3]):
            return False, 'the root differs from its provisioning record'
        prev = rec['hash']
        for d in log:
            if d['prev_hash'] != prev:
                return False, f"seq {d['seq']}: prev_hash mismatch"
            expect = chain_hash(prev, d['seq'], d['op'], d['kind'], d['code'], d['observation'])
            if d['hash'] != expect:
                return False, f"seq {d['seq']}: hash mismatch"
            if (d['observation'].get('k'), d['observation'].get('m')) != (rec['k'], rec['m']):
                return False, f"seq {d['seq']}: records a budget other than the one provisioned"
            prev = d['hash']
        if (head_row[0], head_row[1]) != (len(log), prev):
            return False, 'root head does not match the log'
        return True, 'ok'

    # ------------------------------------------------------------------ results and receipts
    def put_result(self, root_id: str, aid: str, result) -> None:
        """The first outcome stored wins, except that an 'unknown' outcome is replaced by a later one (v0.7: unknown is
        not final; the host may learn the verdict after all)."""
        with self.connect() as conn:
            conn.execute('SELECT public.plea_put_result(%s, %s, %s::jsonb)', (root_id, aid, json.dumps(result)))   # v1.0: admitted, consumed attempts only
            conn.commit()

    def get_result(self, root_id: str, aid: str):
        with self.connect() as conn:
            row = conn.execute('SELECT result FROM results WHERE root_id = %s AND aid = %s', (root_id, aid)).fetchone()
        return None if row is None else row[0]

    def put_receipt(self, root_id: str, aid: str, seq: int, receipt_json: dict, op: str = 'ACCEPT_INTENT') -> None:
        with self.connect() as conn:
            conn.execute('INSERT INTO receipts (root_id, aid, op, seq, receipt) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (root_id, aid, op) DO NOTHING',
                         (root_id, aid, op, seq, json.dumps(receipt_json)))
            conn.commit()

    def put_evidence(self, root_id: str, aid: str, seq: int, evidence_json, derived: str) -> None:
        """The report the witness verified for the decision at seq, and the label it derived (G03 audit)."""
        with self.connect() as conn:
            conn.execute('INSERT INTO evidence (root_id, aid, seq, evidence, derived) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (root_id, seq) DO NOTHING',
                         (root_id, aid, seq, json.dumps(evidence_json), derived))
            conn.commit()

    def evidence_for(self, root_id: str, aid: str) -> list:
        with self.connect() as conn:
            rows = conn.execute('SELECT seq, evidence, derived FROM evidence WHERE root_id = %s AND aid = %s ORDER BY seq', (root_id, aid)).fetchall()
        return [{'seq': s, 'evidence': e, 'derived': d} for s, e, d in rows]

    def get_receipt(self, root_id: str, aid: str, op: str = 'ACCEPT_INTENT'):
        with self.connect() as conn:
            row = conn.execute('SELECT receipt FROM receipts WHERE root_id = %s AND aid = %s AND op = %s', (root_id, aid, op)).fetchone()
        return None if row is None else row[0]

    def attempt_for_request(self, root_id: str, req: str):
        with self.connect() as conn:
            row = conn.execute('SELECT aid, phase FROM attempts WHERE root_id = %s AND req = %s', (root_id, req)).fetchone()
        return row
