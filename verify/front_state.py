"""The front door's record of the latest binding it has seen for each job, kept in PostgreSQL.  (Amendment 17, D16.)

Before this amendment the front door kept, in its own memory, the highest sequence number of each job's signed binding that
it had seen.  A restart forgot it, so an earlier signed binding put back in `front/jobs.json` (an ENROL or a REBIND signed
before a REVOKE) admitted the job again.  Now each binding the front door reads is put to `verify_front_observe`, which keeps,
for each job, the highest sequence number seen, the digest of that binding and whether it revoked the job, and answers:

    CURRENT   the binding is the latest seen, and does not revoke the job: the front door may admit it
    REVOKED   the job has been revoked, by this binding or by an earlier one: revocation is absorbing, no later binding undoes it.
              A revoking binding is kept whatever its number (after the second review, M1)
    STALE     a later binding has been seen: this one was put back, or is out of date
    CONFLICT  another binding with the same sequence number has been seen: two signed bindings disagree
    INVALID   the arguments are not a binding's

Only CURRENT admits.  The function is the only way to the table: it is SECURITY DEFINER, owned by the database owner, and
EXECUTE on it is granted to the service's role, `plea_local`, and to the engineer's console's role, `plea_control` (which
records each revocation before it is written to `jobs.json`, so that a revocation does not wait for the front door to see it);
neither has any privilege on the table itself.  A job's name in the record is taken from what the engineer signed: the
engineer's public key and the job's name (state_name), which every binding of that name by that engineer shares; at most 200
characters.  It only moves
forward: a sequence number is raised and never lowered, and a revocation is never cleared.  It takes the row's lock
(SELECT ... FOR UPDATE, and an INSERT that loses a race reads the winner's row), so concurrent front doors agree.

What it does not do.
  - It cannot check the engineer's signature: PostgreSQL holds no Ed25519.  The front door checks the signature before it
    asks.  So a caller holding `plea_local` itself (CAP-DB) can call the function with a made-up sequence number or a made-up
    revocation and refuse a job admission for ever.  That fails closed: it can deny a job, never admit one.
  - A restore of the database to an earlier state forgets later bindings.  With `front/jobs.json` also put back to a binding
    signed before a revocation, the revoked job would be admitted again.  Undoing that needs the database's owner or its
    operator (CAP-OWNER), not the service's role; it is stated as a limit, not met.
  - Pacing counters and the per-job lock are still in the front door's memory.

How a job is named in the record (after the fourth and fifth reviews).  It was once named by a realm: first the hash of the
certificate authority's file, then a name the operator gave the front door, then a name kept in HOME/front/realm.  Each could
be changed by someone short of the engineer: a change of authority, a restart under another name, or a write to that file,
which anyone who can put back jobs.json can make.  After any of them a revocation recorded under the old name was not found,
and the earlier binding put back admitted the job again (fourth review, H1'').  It was then named, at 818bee9, by the job's
certificate hash and its name.  That let a re-used name escape: a job enrolled again after its entry was removed from
jobs.json had a row of its own, and its revocation did not cover the earlier enrolment (fifth review, N-M1).

A job is now named by the engineer's public key (the binding's signer) and the job's name.  Neither can be changed without
the engineer's key: a binding is used only if a pinned engineer key signed it, and only for the job it names (the front
door's usable(), and the console's _current()).  No file and no setting of the front door's bears on it.  Every binding of
one job name by one engineer falls on one row, so a name is used once: a second enrolment of it has the number 1 again, is
answered CONFLICT, and admits nobody; a revocation of the name covers every enrolment of it.  Each engineer's names are
apart, and so are a test deployment's, each having its own engineer key.  Two front doors on one database, pinning the same
engineer and using the same job names, share rows, which fails closed.  A change of the engineer's key starts new rows: a
binding signed by the earlier key, while that key is still pinned, falls on the earlier key's rows.  Rows written by
earlier forms of this development (named by a realm, or by a certificate's hash) are not read; no deployment holds them.

A row's lock held open by a caller holding plea_local stalls the console's revocation, and that job's admissions with it:
nothing is admitted meanwhile.  CREATE TABLE IF NOT EXISTS does not add a CHECK to a table made before it; the function's
own test of its arguments stands in.
"""

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS public.verify_front_binding (
    job             text        PRIMARY KEY CHECK (length(job) <= 200),
    seq             bigint      NOT NULL CHECK (seq >= 1),
    binding_sha256  text        NOT NULL CHECK (binding_sha256 ~ '^[0-9a-f]{64}$'),
    revoked         boolean     NOT NULL,
    seen_at         timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON public.verify_front_binding FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.verify_front_observe(p_job text, p_seq bigint, p_sha text, p_revoked boolean) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    r public.verify_front_binding%ROWTYPE;
BEGIN
    IF p_job IS NULL OR length(p_job) > 200 OR p_seq IS NULL OR p_seq < 1 OR p_sha IS NULL OR p_sha !~ '^[0-9a-f]{64}$' OR p_revoked IS NULL THEN
        RETURN 'INVALID';
    END IF;
    IF p_revoked THEN                                    -- Amendment 17, after its second review (M1): a revocation of any number is kept
        INSERT INTO public.verify_front_binding AS b (job, seq, binding_sha256, revoked) VALUES (p_job, p_seq, p_sha, true)
            ON CONFLICT (job) DO UPDATE SET revoked = true, seq = GREATEST(b.seq, EXCLUDED.seq), seen_at = now();
        RETURN 'REVOKED';
    END IF;
    SELECT * INTO r FROM public.verify_front_binding WHERE job = p_job FOR UPDATE;
    IF NOT FOUND THEN
        INSERT INTO public.verify_front_binding (job, seq, binding_sha256, revoked) VALUES (p_job, p_seq, p_sha, p_revoked)
            ON CONFLICT (job) DO NOTHING;
        IF FOUND THEN
            RETURN CASE WHEN p_revoked THEN 'REVOKED' ELSE 'CURRENT' END;
        END IF;
        SELECT * INTO r FROM public.verify_front_binding WHERE job = p_job FOR UPDATE;   -- another front door wrote it first
    END IF;
    IF r.revoked THEN
        RETURN 'REVOKED';                                                              -- absorbing
    END IF;
    IF p_seq < r.seq THEN
        RETURN 'STALE';
    END IF;
    IF p_seq = r.seq THEN
        IF r.binding_sha256 <> p_sha THEN
            RETURN 'CONFLICT';
        END IF;
        RETURN CASE WHEN p_revoked THEN 'REVOKED' ELSE 'CURRENT' END;                 -- cannot be revoked here: r.revoked is false
    END IF;
    UPDATE public.verify_front_binding SET seq = p_seq, binding_sha256 = p_sha, revoked = p_revoked, seen_at = now() WHERE job = p_job;
    RETURN CASE WHEN p_revoked THEN 'REVOKED' ELSE 'CURRENT' END;
END $$;
REVOKE ALL ON FUNCTION public.verify_front_observe(text, bigint, text, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.verify_front_observe(text, bigint, text, boolean) TO plea_local;
GRANT EXECUTE ON FUNCTION public.verify_front_observe(text, bigint, text, boolean) TO plea_control;   -- the engineer's console (after review H1)
"""

import re

ANSWERS = ('CURRENT', 'REVOKED', 'STALE', 'CONFLICT', 'INVALID')
HEX64 = re.compile(r'[0-9a-f]{64}')


def nameable(binding) -> bool:
    """True if the binding has what state_name needs.  The front door uses no binding without it (usable())."""
    signer, job = (binding.get('signer'), binding.get('job')) if isinstance(binding, dict) else (None, None)
    return isinstance(signer, str) and HEX64.fullmatch(signer) is not None and isinstance(job, str) and 0 < len(job) <= 64


def state_name(binding: dict) -> str:
    """A job's name in the record (after the fifth review, N-H1 and N-M1): the engineer's public key that signed the binding,
    and the job's name, both signed.  The front door and the engineer's console use it.  Raises ValueError for a binding
    without them (nameable)."""
    if not nameable(binding):
        raise ValueError('a binding names its engineer by a public key of 64 hex digits and its job by a name')
    return f"{binding['signer']}:{binding['job']}"


class StateUnavailable(Exception):
    """The record of bindings could not be read or written: the front door admits nobody."""


def install(owner_store) -> None:
    """Install or update the table and the function.  Needs the database owner's credential: an operator's step at
    installation, as the gateway's own schema is.  Running it again changes nothing that is stored."""
    with owner_store.connect() as conn:
        conn.execute(SCHEMA)


def observe(store, job: str, seq: int, binding_sha256: str, revoked: bool) -> str:
    """Put one binding the front door has read, and whose signature it has checked, to the record.  Raises
    StateUnavailable if the database cannot answer, or answers anything not in ANSWERS."""
    try:
        with store.connect() as conn:
            row = conn.execute('SELECT public.verify_front_observe(%s, %s, %s, %s)', (job, seq, binding_sha256, revoked)).fetchone()
    except Exception as exc:
        raise StateUnavailable(f'{type(exc).__name__}') from None
    answer = row[0] if row else None
    if answer not in ANSWERS:
        raise StateUnavailable(f'unexpected answer {answer!r}')
    return answer
