# Erratum to the Amendment 16 threat-model addendum: the freshness of COVERED

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, not a declaration and not an implementation. It corrects one definition of a design baseline. Nothing is
built: the mailbox gives no challenge today, and nothing here says that it meets what follows.

## What is corrected, and where

- **The baseline.** `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` on `verification-amendment-16`, commit
  `0da1a85e819daac4839e51917402f3fcd67d5caf`, section 7, the paragraph "Definition" (line 278) and the paragraph "The
  waiting limit" (line 302).
- **The baseline is not edited.** It stays as accepted, on a branch that stays at that commit. This erratum is kept on
  `diagnostic-amend16-alarm-2026-11-21` and is to be read with it. Where the two differ on the freshness of COVERED,
  this erratum is the corrected design, by the owner's instruction of 21 November.
- **Everything else in the baseline stands:** the locked powers, the preconditions DP1 to DP4, the clauses O1 to O4, the
  observation boundary, what COVERED and NOT COVERED mean and do not mean, and that the guarantee is proposed,
  conditional, and not built.

**The words corrected.** The baseline says:

> For a budget B, a mailbox M and a time t on M's clock, B is COVERED to decision N if and only if M holds a coverage
> statement signed by the courier's key, which M receipted at a time r with t − r no more than the waiting limit, and
> every clause below is true of one reading by the courier that the statement names.

**Why they are wrong.** A receipt shows when a statement arrived. It does not show when the budget was observed. A
reading can be slow, and its statement can wait in the courier's outbox for any time (the mailbox's code and the
courier's give no bound: Step 2 note, section 1, M14). So an old observation can be given a fresh receipt, and the budget
then reads COVERED on it.

**The evidence.** The Step 2 model's variant `receipt_time` is the baseline's wording. Searched to the end (7,478,677
states), it breaks two invariants. The shortest trace, nine steps: a report for a run is recorded; the courier begins a
reading at mailbox time 0; the value FAIL is stored for the run after the courier has asked for it; the mailbox's clock
moves to 2; the reading ends whole, with nothing to notice; its statement is receipted at time 2. The budget reads
COVERED at time 2, and the FAIL committed at time 0 has no notice. (`tests/diag_amend16_model/results_2026-11-21/`,
commit `2938fca`.) This is bounded evidence from a small model written by the author of the rules; it shows the fault
and proves nothing more.

## The corrected definition

For a budget B, a mailbox M and a moment t of M's trusted time (below), B is **COVERED to decision N** if and only if M
holds a coverage statement S for which every one of F1 to F6 is so, and every clause O1 to O4 of the baseline is true of
the one reading S names. Otherwise B is **NOT COVERED**.

- **F1, a challenge of this mailbox.** S carries a challenge C that M itself issued: signed with M's key, in M's
  current epoch, for budget B and for the courier key that signs S.
- **F2, bound to the checkpoint.** S carries a checkpoint K, signed by a witness key given, for budget B, at decision
  N, whose signed nonce is C's token. This is the baseline's O1 with the nonce fixed: it is the mailbox's token, not
  one of the courier's own.
- **F3, bound to the observation.** The courier's signature on S covers C, K, B, N, K's head, and the commitments to
  everything S rests on: every notice and every piece of evidence the courier has sent for B, and the observation of
  each run (Step 2 note, section 15).
- **F4, used once.** No other statement that M holds was made on C's token.
- **F5, within the deadline.** The age of C at t is no more than the waiting limit L. The age is counted by M's
  trusted time from the moment M issued C, and L is the one in force when C was issued, which C carries.
- **F6, with its evidence.** M holds every item S commits to.

The receipt of S plays no part. A statement that arrives after C's age has passed L is kept as evidence and never
makes the budget COVERED. **A fresh receipt cannot make an old observation look fresh**, because nothing is counted
from a receipt: the count begins before the reading does.

## The challenge token

- **Issued by the mailbox, before the reading.** The courier asks M for a challenge for B. M makes a token, records it
  durably with its epoch, a serial number, B, the courier's key, L and the moment of issue, and returns the challenge
  signed.
- **Unpredictable.** 32 bytes from the operating system's source of randomness, written in 43 characters of the
  URL-safe alphabet. Nobody can hold a checkpoint that bears a token before M has issued it.
- **Bound three ways.** To the budget: C, K and S each name B, and all three must agree. To the checkpoint: the
  witness signs the token back as K's nonce. To the observation: the courier signs C, K and the commitments together.
- **No change to the gateway.** The witness already signs back a nonce of up to 64 characters of letters, digits, `_`
  and `-` in a checkpoint (`plea_gateway/witness_service.py` 98, 115-116; `verify/check_record.py` 88), and the courier
  already asks for a checkpoint with a nonce and refuses one that does not sign it back (`verify/courier.py`,
  `checkpoint()`). Read, not tested with a token from a mailbox, since no mailbox gives one.

## Replay

| Attempt | What must happen |
|---|---|
| The same statement delivered again | the first receipt is returned; nothing is counted afresh, since nothing is counted from a receipt |
| An old statement delivered late | kept as evidence; never COVERED, by F5 |
| A second, different statement on a token already used | not counted, by F4; the first stands; the second is kept as evidence of the attempt |
| A token of an earlier epoch | not counted, by F1 |
| A token issued for another budget, or to another courier key | refused, by F1 |
| An old checkpoint offered with a new token | cannot be made: the witness's signature covers the nonce |
| A statement made for this mailbox offered to another | refused: the challenge is not signed by that mailbox's key |
| A token asked for early and used later | no gain: its age counts from its issue |
| Many tokens asked for and never used | each is small; M keeps a bounded number for each budget and courier key, and one dropped is void |

## The mailbox's trusted time

The baseline says "the mailbox's clock". The mailbox's only clock today is its host's wall clock in whole seconds, used
once, with nothing to guard it (Step 2 note, section 1, M4). That is not a trusted time source. The corrected design
requires this of M:

- **T1, an epoch.** Each start of M makes a new epoch identifier, random, recorded durably before M answers anything.
- **T2, elapsed time.** Within an epoch, M measures elapsed time by a clock that cannot be set and that goes on
  counting while the machine is suspended.
- **T3, the wall clock is for people.** It is written beside what M signs so that a person can read it. No decision
  about freshness uses it alone.
- **T4, age.** The age of a challenge is the elapsed time of T2 since its issue. It is defined only inside the epoch
  that issued it.
- **T5, a clock set back, or jumping.** Whenever M works out an age it also compares how far the wall clock has moved
  with how far T2 has. If the wall clock has gone backwards, or the two differ by more than a tolerance the operator
  sets, M records a clock anomaly durably and shows it in every status it gives until the operator clears it. Where
  the two disagree, the age used is the larger. So an anomaly can only make an observation look older. It can never
  make one look fresher.
- **T6, nobody else's time.** M never takes a time from the courier, the witness, a notice or a checkpoint as a basis
  for freshness. The checkpoint's own time is the witness's clock and is evidence of nothing here.

## Restart, and anything M cannot be sure of: fail closed

- **Restart.** A new epoch (T1). Every challenge of an earlier epoch is void. Every budget reads NOT COVERED until a
  statement arrives that was made on a challenge of the new epoch. Statements and notices held from before stay held,
  as evidence.
- **A record M cannot read.** If M cannot read its own record of challenges, statements or the limit, every budget it
  cannot answer for reads NOT COVERED.
- **The courier's side.** A courier told that its challenge is void takes a new one and reads again. Nothing it holds
  from before the restart can be made fresh.
- **NOT COVERED is the default.** It needs no statement, no alarm and no working courier to be true, and it never
  says that a run failed.

## The deadline

- **Who sets it.** The mailbox's operator, at the mailbox, before acceptance testing. Not the courier, and not the
  service.
- **How it is carried.** L is part of each challenge, so a statement is judged by the limit that was in force when its
  reading began. A change of L takes effect with a new epoch.
- **How it is measured.** By T2 and T4, from the issue of the challenge.
- **What it must leave room for.** A whole reading and the delivery of its statement, both inside L. Measured on 21
  November on one machine with the self-test check: whole readings under honest load took 0.3 to 3.2 s; a reading from
  nothing over 996 runs took 98 s. An L shorter than a reading from nothing means a courier that has lost its state can
  never bring the budget back to COVERED. That is the operator's trade to make. These figures are an envelope, not a
  capacity, and promise nothing.

## What a reader may rely on

Only M can say what its trusted time is. So "COVERED to N" or "NOT COVERED" is evidence to anyone else only as a status
that M signs: the budget, the state, N if COVERED, the epoch, whether a clock anomaly is recorded, and the wall-clock
time for a person to read. A reader who works it out from M's folder with their own clock is using their own clock, and
must say so.

## What this erratum does not do

- It builds nothing. Every "must" above is a requirement on a Step 3 that has not been approved.
- It does not make the guarantee unconditional. DP1 and DP2 are not met by the demonstration.
- It promises no time by which a budget becomes COVERED.
- It is not proved. The model's clean result for the token rule is a search of two runs, three decisions and three
  ticks of one clock. The model has no epochs, no restart, no replay, no clock anomaly and no second mailbox: F1, F4,
  T1, T5 and the replay table are specified here and checked nowhere. They are proof obligations (Step 2 note,
  section 19).

## Trace

| | |
|---|---|
| Baseline corrected | `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md`, section 7, at `0da1a85e819daac4839e51917402f3fcd67d5caf`; not edited |
| Fault shown by | the model's variant `receipt_time`, `tests/diag_amend16_model/`, commit `2938fca`; the mailbox inspection, Step 2 note section 1 |
| Put to the owner | Step 2 note, first revision, section 5, commit `2938fca` |
| Decided | by the owner, 21 November 2026: a mailbox-issued, unpredictable challenge taken before the reading; replay protection; trusted time with rollback handling; restart failing closed; delayed delivery; an operator-established deadline on the mailbox's trusted time |
| Detailed in | `verify/STEP2_DESIGN_AMEND16_2026-11-21.md`, second revision, sections 12 and 15 to 17 |
| Status | design only; nothing implemented; awaiting the owner's approval before any Step 3 |
