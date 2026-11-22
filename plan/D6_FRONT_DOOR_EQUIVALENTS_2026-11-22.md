# D6: front-door equivalents of R14, R17, R18, R25 and R26 (specification)

22 November 2026. Private working material. A specification, not an implementation. Under the owner's decision of 22
November 2026 (point 2), R14, R17, R18, R25 and R26 stay on the test-only route as supplementary evidence, and these
equivalents are to exist and pass through the production front door before D6 is closed. This is internal work by the
author; nothing here is validated.

## What stays as it is

- **R1 to R13** keep all 53 assertions. They already run through the front door (Amendment 17's official run).
- **R29** is kept.
- **The five tests** stay as they are, on `tests/service_route.py`, which holds the service's own database role
  (CAP-DB). Their results are supplementary evidence only.
- **The database-role-only false-verdict question** (Finding 2 of D6; the second review's M7) stays open until it is
  independently tested. It asks whether a holder of the service's role alone can make a record that verifies with a
  verdict the check did not give, for instance through a design holding a NUL or a number that is not finite, which
  the gateway does not refuse. None of the equivalents below answers it: they all go through the front door, which
  refuses such designs (F7).

## Why the five were moved (Amendment 17 development log, entry 9)

In each, what the gate signed and recorded was as before. The difference was the way in:

- **R14:** the front door words a missing card in its own terms.
- **R17:** one design is not an object, and the front door refuses it before the gate sees it.
- **R18:** one check is about the first client's own answer.
- **R25 and R26:** they reach the witness with certificates the plain deployment admits and a front-door deployment does
  not.

## The equivalents

Each is a new test of the front suite (`tests/verify_front_tests.py`), named here FE14, FE17, FE18, FE25 and FE26.
- Each runs on a `deploy_front.FrontServices` deployment, enrols its job with `front_ctl.py`, sends every design with
  `front_client.py` from a clean environment, and builds the record with `front_ctl.py record`.
- Each check is written, with its expected counts, in a declaration committed before its first run (VP-5).
- Where the front door answers in its own words, the check names those words and the gate-side facts separately.

**FE14: a stored baseline that is no longer a card.**
- *Procedure:* for each of the fourteen unusable stored baselines of R14 (the same list), replace the stored card, send
  a design through the front door, then restore it.
- *Gate-side checks, as R14:*
  - the gate signs UNKNOWN with the reason BASELINE_MISMATCH, and nothing is left interrupted;
  - the gate host keeps running;
  - the record holds fourteen UNKNOWN with that reason;
  - every one is sent to the engineer in a notice that is not empty;
  - no line of the changed file, and no path of the service's folder, is in a notice, the record or an answer;
  - with the file restored, the failing and the passing design are decided as before;
  - the record verifies with fourteen unknown, one not met and one met.
- *Front-door checks, new:*
  - the answer to the assistant is the front door's text for when it holds no usable card (F21's words), with the
    exit status of an UNKNOWN (3);
  - it calls the result neither a pass nor a failure.
- *To decide in its declaration:* whether the front door sends the design on while its own copy of the card is
  unusable (so that the gate signs it), or answers NO_BASELINE without a run. Today's code decides this, and the test
  states it; it is not to be changed to fit the test.

**FE17: what a design supplies is never read as the service's words.**
- *Procedure:* the sixteen designs of R17 outside the baseline, and the one sent while no usable baseline is held,
  each through the front door.
- *Gate-side checks, as R17:*
  - the signed reasons repeat no sender's words;
  - the notices and the checker's print hold a sender's words only on `sent:` lines, in the rule's form, at every
    width from 80 to 200 columns;
  - the in-process cases (the 4,765 texts and the 15,792 designs) are unchanged, since they do not depend on the way
    in;
  - the record verifies with sixteen not met, one unknown and none met.
- *Front-door checks, new:*
  - the answers the front door gives set out what was sent in the same form;
  - a design that is not an object is refused by the front door before the gate sees it, with its own refusal, and is
    counted apart: R17's count of seventeen notices becomes sixteen plus one front-door refusal, stated in the
    declaration (F7 covers that refusal alone today);
  - a design of forty names, and a number of forty digits, reach the gate, or are refused by the front door, as the
    front door's limits decide. The declaration states which, from the code.

**FE18: a notice and an answer say only what is so for their run.**
- *Procedure:* the eight runs of R18, one for each verdict the gate gives and one while the gate holds no usable copy
  of the card, and the revision with its counts, through the front door.
- *Gate-side checks, as R18:*
  - each notice states its verdict, says the check's files matched only when they did, never says nothing changed,
    and says so when no usable card was held;
  - the revised baseline counts every run of the one it replaced (8, 1 met, 2 not met, 5 unknown);
  - the new record's print gives the three counts;
  - the in-process cases of `face()` are unchanged;
  - the new record verifies.
- *Front-door checks, new, in place of the first client's:*
  - the front door's answers say the same as the notices for each verdict;
  - while the gate holds no usable card, the front door's answer says so and does not call the card unchanged;
  - the front door's `/requirement` after the revision gives all three counts (F21 has part of this today).

**FE25: the witness's checkpoints.**
- *Procedure:* the runs that build R25's chain are made through the front door. The keeper's certificate and the
  checker's commands are used as R25 uses them.
- *Deployment:* the front-door deployment must admit the keeper's certificate at the witness (read-only, as in R25).
  If `FrontServices` does not, adding it is a test-deployment change, to be made and declared in its own commit, not
  a change to the witness.
- *Checks:* R25's twenty, unchanged. None depends on the way the runs were made, only on the chain the witness holds.

**FE26: the courier and the mailbox.**
- *Procedure and deployment:* as FE25, with the courier's and the mailbox's certificates and keys, and the runs
  (failures, a pass, a run cut off, the oddly named attempt) made through the front door where the front door can
  make them.
- *Checks:* R26's, unchanged, except where an attempt can only be made by the gateway's own role.
  - The case of an attempt the gateway names oddly ("!x") cannot be made through the front door, which names attempts
    itself. It stays in R26 only, and FE26's declaration says so.

## Acceptance (before D6 is closed; the owner's act)

- FE14, FE17, FE18, FE25 and FE26 are declared, then pass in official runs with every check true.
- R1 to R13 and R29 pass in the same runs.
- Each FE test, as declared, has a planted defect caught (one that removes the property it checks).
- Every gate-side check of the five R tests has its counterpart in an FE test, or a stated reason it cannot (as for
  "!x").
- The database-role-only false-verdict question is answered by a separate, independent test.
