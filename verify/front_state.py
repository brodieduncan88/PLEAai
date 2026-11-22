"""The front door's record of the latest binding it has seen for each job, kept in PostgreSQL.  (Amendment 17, D16.)

Before this amendment the front door kept, in its own memory, the highest sequence number of each job's signed binding that
it had seen.  A restart forgot it, so an earlier signed binding put back in `front/jobs.json` (an ENROL or a REBIND signed
before a REVOKE) admitted the job again.  Now each binding the front door reads is put to `verify_front_observe`, which keeps,
for each job, the highest sequence number seen, the digest of that binding and whether it revoked the job, and answers:

    CURRENT   the binding is the latest seen, and does not revoke the job: the front door may admit it
    REVOKED   the job has been revoked, by this binding or by an earlier one: revocation is absorbing, no later binding undoes it
    STALE     a later binding has been seen: this one was put back, or is out of date
    CONFLICT  another binding with the same sequence number has been seen: two signed bindings disagree
    INVALID   the arguments are not a binding's

Only CURRENT admits.  The function is the only way to the table: it is SECURITY DEFINER, owned by the database owner, and
EXECUTE on it is granted to the service's role, `plea_local`, which has no privilege on the table itself.  It only moves
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
"""

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS public.verify_front_binding (
    job             text        PRIMARY KEY,
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
    IF p_job IS NULL OR p_seq IS NULL OR p_seq < 1 OR p_sha IS NULL OR p_sha !~ '^[0-9a-f]{64}$' OR p_revoked IS NULL THEN
        RETURN 'INVALID';
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
"""

ANSWERS = ('CURRENT', 'REVOKED', 'STALE', 'CONFLICT', 'INVALID')


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
