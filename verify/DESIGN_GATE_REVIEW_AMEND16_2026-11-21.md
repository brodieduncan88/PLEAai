# Amendment 16 design gate: the independent reviewer's reports, as returned

21 November 2026. Private working material. This file holds, without change, the two reports of the one Opus-tier
reviewer the owner authorised for the design gate, a model separate from the one that wrote the design. It is an
internal review. It is not an independent validation and not a declaration.

**How the review was run.** In two phases, so that the reviewer formed its own view first.

- *Phase 1.* The reviewer was given the pinned code of `e25a297`, the threat-model baseline at `0da1a85e`, the
  property file, the owner's four design questions, the raw outputs and scripts of the gate's tests, and a database of
  its own for experiments. It was not given the gate note, the Step 2 note, the erratum or the model, and was told not
  to open them. Its report is Part 1.
- *Phase 2.* Only after Part 1 was returned was it sent the draft gate note (as it stood before the author saw Part 1),
  the Step 2 note, the erratum and the model, and asked for a standing on every claim. Its report is Part 2.

**What the author did not do.** Change either report. The reviewer could not write its phase 2 file itself (its
file-writing tool refused), so Part 2 is the text it returned, saved as returned. Its own scripts and outputs are in
`tests/diag_amend16_gate/review/`. What was done with each finding is in the gate note,
`verify/DESIGN_GATE_AMEND16_2026-11-21.md`, section 9. The draft the reviewer judged is that file at the commit before
the one that adds section 9.

**The author's spot-checks of the reviewer's work** (not a re-run of it): the code lines it cites for the courier's
skipped phases (courier.py 403), the courier's 32 MiB limit (178), the record checker's single gate key (854) and the
record's default of no deliveries (verify_ctl.py 239) are as it says; its outputs for P1 to P5 and for its item-chain
enumerator exist and read as it reports; the six main files of the pinned copy are byte-identical to `e25a297`; no
service was left running; the repository stayed on `verification-amendment-16` at `0da1a85e`.

---

# Part 1. Phase 1, as returned

# Amendment 16 design gate: reviewer's phase 1 (my own view, written before reading the author's design)

21 November 2026. This is one Opus-tier internal reviewer's own view. It is not an independent validation. Labels: **RUN** means I ran it and saw the output in the file named. **ARGUED** means code reading or reasoning, not tested. "Author RUN" means a result in the author's pack that I checked against the raw fields next to it, without running it again myself.

## 0. Ground rules kept, and what I was exposed to

- **Not opened:** the branch `diagnostic-amend16-alarm-2026-11-21` and `gate/sealed/`. I also saw files named `STEP2_DESIGN_AMEND16_2026-11-21.md` and `AMEND16_ERRATUM_FRESHNESS_2026-11-21.md` in `S/amend16/` and did not open them.
- **Exposure to the author's rule.** The pack scripts that I was allowed to read (`gate_common.verdict_pairs`, `gate_release.step2_view`) show the shape of the author's candidate rule: "set D" of distinct (claim, digest) pairs, and a "count rule". My pair rule in Q1 was formed from `run_outcome` and the store rules. It coincides with set D, and I cannot rule out that seeing it influenced me.
- **Repository untouched.** `/home/user/PLEAai` is still on `verification-amendment-16` at HEAD `0da1a85`, with `git status` clean.
- **Pinned source untouched by me.** `src_before.sha256` matched after my runs (output "SRC_UNCHANGED"). But the author's pack harness writes its deployments into the pinned tree: `S/amend16/diag2/src/outputs/verify_tests/{GR,GS,GT,GU,GV,GW,GZ}` exist. I redirected `VT.OUT` in my copy `review/rv_common.py`.
- **Powers I used:** `plea_local`, the governor certificate (POST /accept), the gate key, and the courier certificate for readings. In R5 I also used the courier's key, to stand in for an honest courier whose notice was delivered late. I did not use the owner's password. The author's `gate_release.py` does use it (`OWNER = plea:plea`) to read the evidence table in C1, C4 and C8. That is outside the service's powers. Those results are observation only, and a courier cannot make them.
- **My runs:** `review/rv_conflict.py`. Output is in `review/out/rv_conflict_run2.txt` and `review/out/rv_conflict.json`. `rv_conflict_run1.txt` is a failed run, kept: my harness reused a design and the client replayed the stored result instead of making a new run. Clocks are in `review/out/clocks_reviewer.txt` and sizes in `review/out/sizes_reviewer.txt`. One deployment at a time; none left running.

---

## Q1. Verdict transitions and UNKNOWN

### What the code actually does (ARGUED from code; RUN where marked)

- **"UNKNOWN" means three different things.** Any rule must keep them apart.
  - **(a)** An `EFFECT_REPORT` whose `claim` is `UNKNOWN`. The honest gate host signs one at `gate_host.py` 257-259 (an interrupted row, after a takeover or restart) and at 269 (the tool raised an exception).
  - **(b)** A `claim` of `EFFECT` whose result says `verdict: UNKNOWN`. This is final. Author RUN B1e: the "crash" mode gave phase EFFECT and outcome UNKNOWN.
  - **(c)** The governor's stored marker `{'outcome':'unknown'}` (`governor.py` 230). `plea_put_result` lets it be replaced (`store.py` 838). The service chooses this field: it is not gate-signed.
- **Store transitions** (`store.py` 397-407):
  - RECONCILE UNKNOWN/AUTHORISED on CONSUMED is a NOOP, and the phase stays CONSUMED.
  - A verdict on CONSUMED is APPLIED.
  - Any RECONCILE on EFFECT or NO_EFFECT is DUPLICATE (same claim) or DENIED `VERDICT_IS_FINAL`.
  - **Every one of these, DENIED and NOOP included, stores the evidence row** (`plea_write` 786-795 does not condition on kind). RUN R1: after a committed FAIL, the witness recorded a second EFFECT (DUPLICATE), a NO_EFFECT (DENIED VERDICT_IS_FINAL, label AUTHORISED), a re-signed copy of the FAIL (DUPLICATE) and an UNKNOWN (DENIED). All five stand in GET /run.
- **What `run_outcome` and the courier ignore** (`check_record.py` 186-203). At phase EFFECT, NO_EFFECT claims are ignored; only EFFECT digests count. At phase NO_EFFECT, it returns REFUNDED without looking at any report. The courier does not even ask /run for NO_EFFECT or INDETERMINATE runs (`courier.py` 403).
  - RUN R1: four distinct final pairs, `[EFFECT×3, NO_EFFECT×1]`, and e25a297 still gives "FAIL". The second courier pass made nothing.
  - RUN R1: the record failed *only* because of the RELEASE-path report ("gate report at 10: not recorded with a reconcile decision"). The DUPLICATE forged PASS and the DENIED NO_EFFECT raised no check-6 failure.

### Assumptions a sound design needs

1. **The verdict scope is (root, aid, nonce as the chain records it).** The chain binds the nonce in the observation entry; the evidence row does not bind it.
2. **Every gate key that is given counts, not only one.** `run_outcome` takes a list, but check 6 uses one `gkey`. An equivocation across two pinned keys must count too.
3. **Report identity is the pair (claim, result_digest), never the report's bytes or signature.**
   - Not supported by the evidence until now. RUN R1: I signed the honest FAIL message again with a random Ed25519 r (pure RFC 8032 arithmetic). `cryptography` verified it, the witness recorded it (DUPLICATE VERDICT_RETRY), and it differs in bytes.
   - Distinct pairs: 4. Distinct report hashes: 5. A rule keyed on bytes, signature or `sha(report)` would raise a false conflict.
   - Ed25519's determinism is a signing convention, not something verification checks.
4. **Honest emission of UNKNOWN and of UNKNOWN followed by a verdict.**
   - Honest UNKNOWN is shown end to end with the real governor. Author RUN B1b: host killed and restarted; the client was told "UNKNOWN: THE RUN WAS INTERRUPTED"; recorded as NOOP; outcome INTERRUPTED.
   - Honest UNKNOWN followed by EFFECT is shown (author RUN B2) **only in a topology the harness built**:
     - SIGSTOP on host 1, which is a DP2-excluded power;
     - a second host process on a second port, started by the harness;
     - the UNKNOWN posted to the witness by the harness, not by a governor.
   - In `deploy.py` (84-100: one `gate_url`, one port, `stop_host` = SIGKILL), a stalled host keeps its port and a killed host cannot finish. So honest UNKNOWN-then-verdict cannot arise in the shipped topology (ARGUED).
   - B2 also never exercised the store's 'unknown' → value replacement: `stored_result` was null at B2c.

### Invariants I would require

**Safety**

- **V1 (one final pair).** For each scope, let F be the set of distinct (claim, result_digest) pairs, for claim in {EFFECT, NO_EFFECT}, over **all** genuine in-scope reports the reading or record holds. That means any decision kind (APPLIED, DUPLICATE, DENIED, NOOP) and any operation (RECONCILE or RELEASE), including reports recorded before the attempt or its nonce existed.
  - If |F| > 1: record verification FAILs, and the courier makes a conflict notice. Neither pair is believed and the run's outcome is not PASS.
  - Repeats of one pair, with any signature bytes, never conflict.
- **V2 (UNKNOWN is never a verdict).** UNKNOWN-claim reports never enter F, never make a pair believed, and never move a final outcome back. Late UNKNOWN after a verdict (author RUN B2f; my R1) is allowed and inert.
- **V3 (phase agrees with F).** Phase EFFECT needs F = {(EFFECT, d)}. Phase NO_EFFECT needs F ⊆ {(NO_EFFECT, d0)}. Any other combination is equivocation, for example phase EFFECT with a NO_EFFECT report (RUN R1, seq 11). This needs a reading at NO_EFFECT and INDETERMINATE too, which the courier does not make (`courier.py` 403).
- **V4 (belief only from decisions the chain says carry a report).** The believed digest must come from a report at a chain row `['RECONCILE', aid, v, 'AUTHORISED']`. A report at a RELEASE row, a WRONG_BINDING row or a NONE row can only *add* to F (evidence of equivocation), never be believed.
  - RUN R3 shows why. A PASS report planted with RECONCILE while the attempt was in TOKEN (label WRONG_BINDING, DENIED NOT_CONSUMED). Then an honest FAIL was APPLIED and the PASS stored. e25a297 `run_outcome` gave "PASS" and the courier made nothing.
- **V5 (record completeness for authorised rows).** Every audit row `['RECONCILE', aid, v, 'AUTHORISED']`, of any kind, must have a carried report at that seq claiming v.
  - RUN R2 (S-1 replacement). With the honest FAIL report dropped from the record the service assembles: e25a297 gave no failure for that run, outcome PASS. My predicate found the uncarried authorised row `[21]`.
  - (The whole record failed for an unrelated run in the same budget; see 4.1.)
- **V6 (evidence of equivocation is not evidence of correctness).** A conflict notice says only that the gate key signed two results for one run. It carries both reports, or references to them (Q3), and names neither as true.

**Liveness:** none is claimed. A conflict is seen only when the run is read (Q2, Q4).

### Permitted transitions (my statement)

For each scope, reports arrive as **U\* P (U | P)\***, where U is any UNKNOWN report and P is one fixed final pair. Anything with two P's is EQUIVOCATION. Phase follows the store (CONSUMED → EFFECT / NO_EFFECT, or INDETERMINATE).

**On the owner's fail-closed default.**

- *Permitting* "U before P" is not supersession. U was never a verdict.
- Permitting it **cannot conceal a conflict when V1 is taken over all reports**. Any trace U…P that the adversary can make, it can also make as P alone, which is UM6(a) and equally undetectable (ARGUED). So the transition adds no power.
- It *would* add power if a rule let "the latest report after an UNKNOWN" stand in for F, or let the store's 'unknown' marker (meaning c) be read as a gate-signed UNKNOWN.
- *Forbidding* it costs only false failures in a failover topology that deploy.py does not have. That is a liveness or usability cost, not a safety one.
- Either choice is safe under V1 to V5. The owner's two conditions are met only in part: emission is shown (B1b); emission followed by a verdict is shown only under harness glue (B2).

### Failure cases and counterexamples

- **Post-final second digest, courier blind** (RUN R1). The second courier pass made nothing, and `run_outcome` = FAIL with four final pairs on record.
- **S-1 before commitment** (RUN R2): PASS believed, courier silent. Record omission undetected at e25a297 (R2).
- **Planting before the nonce is in the chain, through RECONCILE rather than RELEASE** (RUN R3): believed by e25a297.
  - The record check on R3 is not clean: my forged value was a bare `{'verdict':'PASS'}`, so check 6's re-derivation caught it as another baseline and design. The author's C2 and C6 used a realistic forgery.
- **NO_EFFECT report on an EFFECT run** (RUN R1 seq 11): ignored by e25a297.
- **Verdict followed by UNKNOWN** (RUN R1 seq 13; author RUN B2f): inert at e25a297, and must stay inert.

### What stays unprovable without changing the witness or the store

- **The evidence row is not in the chain hash** (`chain_hash` binds seq, op, kind, code and observation only; `check_record.py` 145-146).
  - The chain implies that a report exists only at AUTHORISED rows. For RELEASE, WRONG_BINDING and NONE rows, the chain cannot tell whether a report row should exist. A record that leaves such a report out cannot be caught.
  - So "two distinct digests must FAIL record verification" can be enforced only over reports the record carries, or that V5 forces it to carry. A second digest kept only at a non-authorised row can be hidden from the record, though not from a courier reading the witness. Closing this needs the evidence digest inside the decision's hashed op or observation.
- **GET /run is unsigned.** Witness honesty is assumed (A1-A5; property 18).
- **UM6(a)**, a forgery that is the only report the witness ever sees, stays undetectable.

---

## Q2. Mailbox freshness, deadlines, courier absence

### Facts (RUN where marked)

- **The mailbox today** (`mailbox_service.py`):
  - It serves only POST /deliver and GET /pubkey (172-192). It issues no token and keeps no clock state.
  - Receipt time is wall-clock `time.gmtime` at one-second resolution (70-71). It never checks a notice's own `time`.
  - Identical redelivery returns the first receipt (121-124). A damaged stored copy is *rewritten with a new time* (125).
- **RUN R5:**
  - a WATCHING statement signed with a time 3 h old was accepted, with a receipt time of now (`2026-11-21T18:43:27Z` against notice time `15:43:27Z`);
  - after a mailbox restart, the *same* receipt came back;
  - after the mailbox lost its folder, a *new* receipt with a new time came back.
- **This is a counterexample to §7's definition as written** (t − r ≤ waiting limit, with r = receipt time). An honest courier's outbox delivering a coverage statement late (A3: the mailbox down for a while) gives a fresh r for a stale observation. So does any replay to a mailbox that has lost its storage. The courier-made nonce of O1 gives freshness to the courier, not to the mailbox.
- **Token through the real checkpoint** (RUN R4; matches author RUN A1/A2):

  | Form | Length | Status |
  |---|---|---|
  | base64url, no padding | 43 | 200, signed back, verifies |
  | lower-case hex | 64 | 200, signed back, verifies |
  | hex | 65 | 400 |
  | base64url with padding | 44 | 400 |

  - The limit is `[A-Za-z0-9_-]{1,64}` (`witness_service.py` 98).
  - The same token twice gives two valid checkpoints: the witness keeps no memory of a nonce (RUN R4; author A5).
  - The same token gives a valid checkpoint for another budget (author RUN A4, not re-run by me).
  - The checkpoint signs `root`, `seq`, `head`, `nonce`, `at` and `head_at` together (`receipts.py` 91-93). So it **binds the token to the budget (root) and to the chain head only**.
  - It does **not** bind the token to any run reading (GET /run is unsigned and takes no nonce), nor to the mailbox.
- **Clocks** (RUN `clocks_reviewer.txt`; author `clocks.txt`):
  - CLOCK_BOOTTIME is available. BOOTTIME − MONOTONIC = 0, so no suspend has happened; suspend was not, and cannot be, tested here.
  - Kernel `6.18.44-fc` looks like a Firecracker guest (my reading of the name). A pause by the host is not seen by guest BOOTTIME (ARGUED).
  - Everything runs as uid 0, so the "service" can set CLOCK_REALTIME, signal the mailbox, or edit its folder (DP2 not met).

### Assumptions

- **Sound design needs:**
  - a mailbox clock the service cannot slow (DP2);
  - an elapsed-time source that counts every interval in which the outside world moved: BOOTTIME, which does not count a hypervisor pause;
  - durable mailbox storage, or else a mailbox that fails closed when storage is lost;
  - an honest courier (A1) for everything the witness does not sign.
- **Not supported by the evidence:**
  - DP2;
  - suspend-awareness, as tested;
  - BOOTTIME across a VM pause;
  - the mailbox's resistance to the same uid.

### Invariants

**Safety**

- **M1 (freshness from issuance, not receipt).** Budget B is COVERED at mailbox time t only if the mailbox holds an accepted coverage statement S for B, made under a token τ that the mailbox issued for B at tick i(τ), in the current epoch, with t − i(τ) ≤ L on CLOCK_BOOTTIME.
  - The epoch is the boot_id plus a fresh random value per mailbox start, stored with every token.
  - With this rule, delayed delivery and replay can only make S *staler*, never fresher. Replay is therefore harmless to safety even if single-use is lost.
- **M2 (binding at acceptance).** The mailbox accepts S only if:
  - τ is outstanding for exactly B;
  - S is courier-signed and names τ, B, N and head;
  - S carries a checkpoint, signed by a given witness key, with `nonce == τ`, `root == B`, `seq == N` and the same head. This means configuring the mailbox with witness keys, which it does not have today;
  - every notice S names is held (O4; see Q3).
- **M3 (single use).** τ is marked used, durably, before the receipt is sent. A second statement under τ, or τ for another budget, is refused.
- **M4 (fail closed on discontinuity).** If the epoch changes (mailbox restart without the registry, reboot, lost folder), every earlier token and statement counts for nothing: NOT COVERED until a fresh round.
  - A stored tick from an older epoch is never compared with the current clock.
  - A wall-clock change has no effect, because wall time is never used.

**Liveness (conditional only):** a budget becomes COVERED only if, within L, the mailbox issues τ, the courier runs, the witness answers the checkpoint, the chain and every triggered /run (Q4), and the mailbox accepts. The service can deny this indefinitely (R1 and R2 of the baseline, UM1). **No bounded notification can be claimed.** The mailbox cannot know of failures it is not told of; it can only bound how stale COVERED is.

**When NOT COVERED becomes externally observable without a working courier.** It is the default: it needs only that M1 fails at the reader's time. For a reader *outside* the mailbox to see it, the mailbox needs a reading the reader can trust:

- GET /coverage?budget=B&nonce=R, signed by the mailbox key, carrying R, epoch, the current tick, the token issue tick and statement digest behind any COVERED, and L.
- The reader treats a missing, unsigned or wrong-nonce answer as NOT COVERED.
- Today none exists: only local files under the same uid (`mailbox_service.py list`).

### Attack sequences

| Case | Today (e25a297 / §7 as written) | Under M1 to M4 |
|---|---|---|
| Delayed delivery | Fresh receipt for a stale observation (RUN R5) | Stale by construction: age is t − i(τ) |
| Replay, same budget, same mailbox | First receipt returned (RUN R5) | Refused by M3; harmless anyway by M1 |
| Replay after the mailbox loses its folder | Fresh receipt (RUN R5) | Token unknown, or a new epoch: NOT COVERED |
| Cross-budget token | The witness signs it for any root (author RUN A4) | M2 refuses: cp.root ≠ token's budget |
| Courier absent | WATCHING never lapses (D-d) | No statement within L: NOT COVERED |
| Clock rollback | Receipt wall time can be set back by uid 0 | BOOTTIME cannot be set (EINVAL; author RUN clocks.txt); the same uid can still kill or ptrace the mailbox (DP2) |
| Suspension | n/a | MONOTONIC would *under-count*, which is a **safety** failure; BOOTTIME is needed; a hypervisor pause stays open |

### What stays unprovable without a witness change

The token binds only the checkpoint. The binding of the run observations of O3 to τ rests on the courier's signature alone. A witness-signed /run carrying the nonce would be needed to make it rest on the witness.

---

## Q3. The 64 KiB limit and the evidence of a conflict

### Facts

- **The limit:** `MAX_NOTICE = 65536` (`mailbox_service.py` 51). At the edge, 65,536 bytes is accepted and 65,537 refused (author RUN D2).
- **What the mailbox refuses:** an unknown outcome ("CONFLICT" → 400) and an extra field ("evidence" → 400) (author RUN D2). A new outcome or field therefore needs a change to `check_record.notice_problems`, which the mailbox shares (`check_record.py` 484-492).
- **Report sizes:**
  - honest report: 499 bytes, so two honest reports are about 1 KB;
  - a report with a 512-character non-ASCII run name: 3,522 bytes;
  - a report with a 70,000-character nonce: 70,448 bytes, recorded and served by GET /run at 70,613 bytes (author RUN D1).
- **Further unbounded fields** (ARGUED): `result_digest` is a free string inside the signed message (`evidence.py` `_parse`), and POST /accept reads any Content-Length (`witness_service.py` 157). A single genuine report can be made larger than 64 KiB. So **full reports cannot be guaranteed to fit**.

### Assumptions and invariants (safety)

- **E1 (a reference that binds the whole report).** A conflict notice carries, for each conflicting report:
  - seq, the decision's op, kind and code;
  - claim and result_digest, or their SHA-256 if oversized;
  - signer;
  - `sha256(canonical(report))`.
  - It carries full reports only when each is at most a fixed bound, for example 8 KiB.
- **E2 (retrieval and re-checking).** Full bytes are retrievable from GET /run by (root, aid, seq). The courier should also keep the full reports in its own durable state. A verifier re-fetches them, re-hashes, re-verifies the signature and confirms the pair.
  - A missing or mismatched report counts as present-and-conflicting, never as absent: fail closed.
- **E3 (oversize is itself an anomaly).** A genuine report whose result_digest is not 64 lower-case hex, or whose nonce is not the chain's, is flagged. An honest gate never signs one (`binding.result_digest`).
- **Durability caveat.** The retrieval source is the witness's store, append-only for `plea_local` (`store.py` 844) but not for the owner (DP1). The courier's copy is the only durable copy under the courier's control.

### The cumulative notice set at about 1,000 runs

- A flat list of 1,000 notice digests in canonical JSON is **67,001 bytes, over 65,536**. At most about 955 fit with 1.5 KB of notice overhead (RUN `sizes_reviewer.txt`). With run names inside, worst case about 20.
- **So O4 needs an accumulator.** Per budget, the mailbox keeps an append-only, hash-chained log of the notices it accepted, in its own order. It is ordered by the mailbox's own sequence, not by wall time, because `held()` sorts by second-resolution wall time (133-140).
- The coverage statement carries (count, log head) as the courier computed it. The mailbox accepts only if they equal its own.
- A third party verifies by fetching the log and recomputing. Omission shows as a count or head mismatch.

### Minimum mailbox interface and storage changes (ARGUED)

| Kind | Change |
|---|---|
| New readings | POST /challenge (budget) → token; GET /coverage (budget, reader nonce) → signed status (Q2); GET /log (budget, after) → notices, receipts and the head chain |
| New storage | Token registry {τ, budget, epoch, tick, used}, written durably; per-budget notice log with a head; the epoch |
| Rule changes | New outcomes CONFLICT and COVERAGE (or a new form) in `notice_problems`; a fixed bound per field; the mailbox told the witness keys (M2) |

---

## Q4. Incremental consistency and scaling

### Facts (RUN where marked)

- **Every evidence row sits at a RELEASE or RECONCILE decision whose op[1] names its run.** By code: `plea_write` 786-795, the same seq, aid = op[1]; `plea_local` has no INSERT on evidence (844). Author RUN C4 and C8 (36 rows, all so), read with the owner role.
- **So the chain does show "something was recorded for run X" at every report**, including:
  - RELEASE-path reports (author RUN C1; RUN R1 seq 10);
  - reports recorded before the attempt existed (author RUN C6: `UNKNOWN_OR_DISCARDED_ATTEMPT`) or before its nonce existed (RUN R3: label WRONG_BINDING).
- **But the observation entry of a final run does not change** when such a report is added. RUN R1: `chain_observation_entry_changed_after_cursor: false`. The courier's only trigger is a changed entry (`lines()`), and final runs are dropped for good (`courier.py` 731). So **post-final reports are never examined**. RUN R1: second courier pass, `made: []`.
- **Fork, rollback and missing decisions:**
  - Fork: the courier's `head_at` comparison (`courier.py` ~637).
  - Rollback: "at is beyond the chain" (`courier.py` ~347).
  - A missing decision cannot pass the hash chain to the signed head (`verify_rows`).
  - All three need the courier's own state (seq, head) to persist.

### Invariants

**Safety**

- **I1 (trigger set).** A reading to decision N is whole only if every run named by op[1] of any RELEASE or RECONCILE row in (N_prev, N] is re-read by GET /run in that reading, **whether or not it is final**, and V1 to V4 are evaluated on all its reports with seq ≤ N. Otherwise no coverage statement is made.
  - This replaces §7 O3's "final already, carried over", which as written lets a post-final conflicting report escape. Counterexample: RUN R1.
- **I2 (a run named before it exists).** It needs no memory. The first reading of the attempt returns every row with seq ≤ N. RUN R3: the planted row at seq 26 was returned for a run created later.
- **I3 (cursor continuity).**
  - The persisted (seq, head) must equal the checkpoint's `head_at(seq)`.
  - On loss of state: cold start, NOT COVERED until done.
  - The coverage statement names N_prev and head_prev, so the mailbox can check that statements chain. A gap in the statements means NOT COVERED.

**Liveness:** none. One run can be given unboundedly many reports, and each re-read returns all of them; past 32 MiB the run is unreadable and the budget NOT COVERED. This is availability only.

### Transfer costs (author RUN `measure2_chain.txt`, my model in `sizes_reviewer.txt`)

| Measure | Value |
|---|---|
| Decisions per run | 8 (7,968 decisions for 996 runs) |
| One decision | 3.8 KB, plus about 124 B per run in the budget (126,949 B at 996 runs) |
| Model of the total, 996 runs | ≈ 520 MB (measured 508 MB, 37 s) |
| Marginal cost per new run at 1,000 runs | ≈ 1.0 MB (8 × 127 KB) |
| Each triggered GET /run, honest | ≈ 2 KB |

- **Following a budget incrementally costs the same Θ(n²) in total as a cold start.** The cursor bounds the cost of a pass by the decisions since the last pass, but each decision still carries the whole budget's state.
- **Linear scaling cannot be claimed.** It needs the witness to serve decisions without the full observation, or as deltas: a witness change.

### Checking the author's claim about the release path

The author says the release path is covered. That a RELEASE-path report is visible to a cursor-following reader is a result I checked in the raw fields (author C1 and C2, `seen by cursor: true`) and saw myself (RUN R1). That it "cannot evade conflict detection" holds only with I1 and with V1 taken over all decision kinds. It is not so at e25a297: in R1 the RELEASE report did not move the courier at all.

### What stays unprovable without a witness or store change

- GET /run is unsigned, and evidence rows are not in the chain hash. The completeness of the reports at a seq rests on witness honesty plus DP1 and DP3. The chain proves that *a* decision happened, not *which* report sits there.
- Linear transfer needs a witness change.
- A reading that lists budgets (UM4) is out of reach.

---

## 4. The evidence pack: what I trust, what I do not

1. **Whole-budget record verdicts are contaminated.** Author C3's "honest run" record fails because of earlier runs X and Y in the same budget, so it shows nothing about an honest run. My R2 has the same problem; I filtered failures by run instead.
2. **B3 is near-tautological as a test of the rule.** It compares "D as sent" with "D as read" using the same function, so it tests only that the witness stores every report.
   - It uses one deterministic signer, so it never meets byte-different reports of the same pair (my R1 does).
   - It uses synthetic, uncrossed attempts, so the stored-result path is not exercised.
   - It sends reports through RECONCILE only.
3. **B2 relies on DP2 powers and harness glue** (SIGSTOP, a second port, the harness posting the UNKNOWN), and does not exercise 'unknown' → value. Q1 cannot lean on it as deployment evidence for the shipped topology.
4. **`gate_sizes_run1.txt`** died with a TLS "certificate signature failure", not explained; run 2 passed. I did not reproduce D1 or D2.
5. **`gate_result_store`:** "accepted" means "no error", not "stored"; the `after` fields are the truth. The case "a final run with no stored result" was not found, so it was not tested. The database it ran on is not named in the output.
6. **The author's harness wrote deployments under the pinned source tree** (`src/outputs/verify_tests/G*`).
7. **The author's harness used the owner password** for reads (C1, C4, C8). The fact "every evidence row sits at a RELEASE or RECONCILE decision" comes from an out-of-scope view.
8. **Not reproduced by me:** A4 (cross-budget), A6 to A9, B1, B2, C5 to C8, D1 to D3, measure2. I checked these against their raw fields only.
9. **`clocks.txt`** shows only that BOOTTIME exists. It does not show that it is suspend-aware on this host, and says nothing about a hypervisor pause.
10. **Fields I did not use as conclusions:** every STEP2, PREDICATE, set D and conflict field. Where they agree with the raw report lists (C1 and C2: two authentic EFFECT digests), I took only the raw lists.

## 5. Unprovable without changing the witness or the store (summary)

- **(a) Report rows are not in the chain hash.** Omission at non-authorised rows cannot be caught. Reports cannot be authenticated except through an honest witness.
- **(b) GET /run is unsigned and takes no nonce.** Run observations cannot be bound to the mailbox token.
- **(c) Transfer is Θ(n²)** for incremental and cold readings alike.
- **(d) No list of budgets** (UM4).
- **(e) UM6(a)**, a sole forged report.
- **(f) Stored results are not chain-bound.** RUN, author `gate_result_store`: storing a result adds no decision. So "committed" (stored as a value) cannot be seen from the chain.
- **(g) Outside the guest:** suspend and hypervisor pause.
- **(h) DP1 and DP2 are unmet in the demonstration.** Under them, everything above is moot: the owner can delete reports (baseline §5), and uid 0 can stop the mailbox or courier or edit their files.

*Stopping here, awaiting phase 2.*

---

# Part 2. Phase 2, as returned

[tier: opus] Phase 2 is done. My standings differ from the author's on G1.2, G1.3, G1.4, G1.10, G3.2 (wider), G3.4, G4.6 and part of G4.9. I also withdraw one phase 1 finding (section 0).

**`review/report.md` was not written.** The file-write tool refused it ("Subagents should return findings as text, not write report files"). The full report is below for you to file verbatim. Everything else is under `S/amend16/gate/review/`:
- `rv_phase2.py`, with output in `out/rv_phase2_run1.txt` and `out/rv_phase2.json`
- `rv_itemchain_model.py`, with output in `out/rv_itemchain_model_run1.txt` and `out/rv_itemchain_model.json`
- `authormodel/`: an unmodified copy of the author's `model.py` (same sha256 prefix) and its rerun output `run.txt`

Hard rules kept:
- The repository is still on `verification-amendment-16` at HEAD 0da1a85, clean.
- I changed no code and did not use the owner password.
- One deployment at a time, on plea25; none is left running.
- The eight key files of the pinned copy are byte-identical to `git show e25a297:<file>`.

---

# Amendment 16 design gate: the reviewer's report (phase 2)

21 November 2026. One Opus-tier internal reviewer, independent of the model that wrote the design. This is internal review, not independent validation. Phase 1 (`review/phase1.md`) stands verbatim; where this report corrects it, it says so.

**Labels.**
- **RUN**: I ran it and saw the output in `review/out/` or `review/authormodel/`.
- **Author RUN**: a result in the author's pack, checked against its raw fields.
- **ARGUED**: code reading or reasoning, not tested.

## 0. A correction to my own phase 1 (read this first)

In phase 1 (R2 and R3) I said that the service could leave the honest FAIL report out of the record and e25a297 would not notice. **That is wrong, and I withdraw it.**

- The record is signed by the engineer's key (`verify_ctl.record(…, key, …)`), and its check 1 fails any record that has been changed.
- In phase 1 I filtered failures by run name. That hid the failure "1 record signature: bad signature: the record was changed after it was signed". RUN P1 shows it directly.
- So leaving a report out of the record is a power of whoever builds and signs the record, not of `plea_local`.
- What survives is narrower. A report missing at a decision labelled NONE cannot be detected from the witness's answer or from the chain. The author has this right as L-1, an owner (DP1) power.
- My V5 rule (every AUTHORISED row must carry its report) is still sound for the record checker. I have not shown an in-scope attack that needs it.

## A. Standing of every claim

| Id | Author | Mine | Evidence, and why I differ |
|---|---|---|---|
| G1.1 | PASS | **PASS** | B1b end to end (real governor, host restarted); code at gate_host.py 257-259 and 269. B2 step 3 is harness glue. |
| G1.2 | PASS as staged | **Code path PASS; honest deployment UNPROVEN** | B2 needed powers and steps outside an honest deployment (see notes after the table). |
| G1.3 | PASS (≤4 reports, 5 kinds) | **PASS only for runs starting CONSUMED, RECONCILE only, witness ACTIVE, one key.** "And no others" is unsupported. | My recount of `gate_unknown_B3_len4.json` agrees: 780 sequences, 0 mismatches, 95 FAIL-first-yet-PASS. But the note's own 5.1 table shows NOT_CONSUMED with AUTHORISED, UNKNOWN_ATTEMPT and VERDICT_NOT_AUTHORISED; store.py 403 gives WITNESS_HELD; RUN P4 shows AUTHORISED with DENIED NOT_CONSUMED twice. |
| G1.4 | PASS within B3 | **PASS by construction; the B3 counts are not evidence for it** | B3 compares "D as sent" and "D as read" through the same `verdict_pairs` function. The 480/480 and 0/300 counts can only fail if the witness loses or alters a report, so they are evidence for G1.8, not G1.4. That UNKNOWN changes nothing follows from the rule excluding it. |
| G1.5 | UNPROVEN | **UNPROVEN** | My own argument agrees (any U…P trace has a P-alone equivalent, which is UM6 a). It holds only if conflicts are counted over all decision kinds and operations. |
| G1.6 | rule PASS on data; e25a297 FAIL | **e25a297 FAIL; rule UNPROVEN** (not built; one gap) | Phase 1 R1 (RUN): two extra EFFECT pairs and a NO_EFFECT pair via RECONCILE raised no check-6 failure; only the RELEASE-path report did. The data is present: P1 `record_full` carries both pairs, and an unchanged fresh-budget record verifies (`record_before: [true, []]`). Gap: null nonce (B1.1). |
| G1.7 | PASS on data | **PASS, on my evidence, not B3's** | B3 signs deterministically, so equal pairs were byte-equal. Phase 1 R1 (RUN): the same (claim, digest) re-signed with another r was recorded as DUPLICATE and verifies: 4 distinct pairs, 5 distinct report hashes. Any rule or notice keyed on bytes would give false conflicts (B1.4). |
| G1.8 | PASS | **PASS for retention; resistance to the granted roles not reproduced by me** | Retention: B3 780/780, my R1 and P1-P5. "Against every granted role" rests on the author's earlier V6 and commit_check, not on B3. |
| G1.9 | UNPROVEN | **UNPROVEN** | No wording exists. |
| G1.10 | UNPROVEN | **FAIL as worded** (my bounded model) | C-3 is keyed on the courier's memory ("a run for which an INTERRUPTED notice was made"). Trace and model in section F. Keyed on the witness's data instead (UNKNOWN report plus verdict), the invariant holds over 1,443 states. |
| G2.1 | PASS | **PASS** | Phase 1 R4 (RUN): 43-character base64url and 64-character hex both give 200 and are signed back. |
| G2.2 | PASS | **PASS** | R4 (RUN): 65 characters and 44 with padding give 400. The other characters are A2 only. |
| G2.3 | PASS | **PASS** | A3 and A4 (author); R4 found no problems. |
| G2.4 | FAIL | **FAIL** | R4 (RUN): the same token twice, both valid. Cross-budget is A4 only. |
| G2.5 | UNPROVEN | **UNPROVEN, with rule-level defects** | B2. |
| G2.6 | PASS for availability | **PASS for availability and that it cannot be set; UNPROVEN for suspend or a hypervisor pause** | `clocks.txt` and my `clocks_reviewer.txt`: the same boot (the boot moments computed from the two readings agree). |
| G2.7 | PASS in model only | **Baseline wording fails: PASS** (RUN on the real mailbox). **Corrected rule: UNPROVEN** | Phase 1 R5: a statement signed 3 h earlier got a receipt with the current time, and a lost folder gave a fresh receipt. The author's model reproduces (F.3), but its acceptance rule differs from 3.3 (B2.1), so it does not model the mailbox as specified. |
| G2.8 | UNPROVEN | **UNPROVEN** | The §10 interface also lacks the reads a reader needs (B3.4). |
| G2.9 | not claimed | agree | — |
| G3.1 | PASS | **PASS** | D1/D2: 1,002 bytes; 7,044 at the longest run name. |
| G3.2 | FAIL | **FAIL, wider than stated** | D1: a 70,000-character nonce. **RUN P2**: a genuine report with a signed `result_digest` of 200,000 characters was recorded (DUPLICATE VERDICT_RETRY); GET /run returned 202,558 bytes, authentic for the scope. S-6 names only the nonce. |
| G3.3 | FAIL | **FAIL** | D2 (not reproduced). |
| G3.4 | UNPROVEN | **FAIL as specified** | Four text defects (B3.1-B3.4). |
| G3.5 | UNPROVEN | **UNPROVEN, plus two specification defects** | B3.4 (nothing for a reader to read) and B3.5 (head-of-line blocking). |
| G4.1 | PASS | **PASS** | Code: plea_write 786-795. C4/C8 were read with the owner password (`gate_release.py OWNER`), an out-of-scope view the note does not label. Consistent with my R1 and P1-P5 via GET /run. |
| G4.2 | PASS | **PASS** | C1, C2, C5, C6; my R1: five rows after the cursor, each naming the run. |
| G4.3 | PASS on data; e25a297 FAIL | **e25a297 FAIL** (R1, R2, R3; C1b, C2b). **Design UNPROVEN.** | The design needs the courier to read runs in phases it skips today (B1.2, B4.2). |
| G4.4 | FAIL | **FAIL** | C7. |
| G4.5 | FAIL | **FAIL** | Code; C7, C8. L-1 is right (section 0). |
| G4.6 | PASS for the service's role | **PASS for an EFFECT verdict with a stored value; "settled" undefined in other phases** | E (author): no decision is added; a second value is silently not stored. Gaps in B4.2. |
| G4.7 | UNPROVEN | UNPROVEN | — |
| G4.8 | UNPROVEN | UNPROVEN | — |
| G4.9 | PASS | **PASS for the chain figures; FAIL for the unsettled-run cost in 5.2 and 5.4** | Chain: `measure2_chain.txt` gives 508,180,089 bytes; my model gives ≈520 MB. Unsettled-run cost: see below. |

**G1.2: why the honest-deployment part is UNPROVEN.**
- B2 used SIGSTOP on the first host, a power DP2 excludes.
- The harness started the second host on another port.
- The harness posted the UNKNOWN report to the witness itself.
- The note says this was done "as a governor that tries again would". But in deploy.py the governor's only `gate_url` is the first host's port (lines 84-100, 137). A governor retrying would reach the stalled host, not the second one, so this path cannot be reached in the shipped topology.
- The 'unknown' → value replacement was never exercised: `stored_result` was null at B2c.

**G4.9: what is understated.**
- 5.2 says an honest re-read costs "0.04 to 0.06 s, about 2 KB". `measure.txt` gives 0.030 to 0.101 s; baseline §8 gives a median of 0.060 s and a longest of 0.163 s under load.
- **RUN P3**: one run kept CONSUMED with five UNKNOWN reports of 1,000,000-character digests returns **5,002,287 bytes per GET /run**. The service chooses this cost, up to the courier's 32 MiB cap per run per pass.
- "Bounded by the budget" holds for the number of re-reads, not for the bytes.

## B. The four decisions, challenged

### B1. The set rule T1 to T5 and C-1 to C-4

1. **The null-nonce scope admits a released run (RUN P5).**
   - A RESERVED run was given a gate-signed EFFECT report with `nonce: null` (WRONG_BINDING; DENIED NOT_CONSUMED), then released with a fence report (APPLIED, BOUND_FENCE).
   - The EFFECT report is authentic for scope (root, aid, null), and `run_outcome` given it reads PASS.
   - The record checker raised nothing for it; it flagged only the fence report ("not an effect report").
   - Under T3 this run has "one signed result", while the same key also signed FENCED_NO_START for it.
   - Needed: a scope is valid only with a non-null chain nonce and a run in a consumption phase, and an EFFECT or NO_EFFECT report beside a FENCE report for the same run counts as equivocation.
   - Side observation, not investigated: the record checker fails any record that carries a fence report.
2. **The courier never reads NO_EFFECT, INDETERMINATE or RELEASED runs.** courier.py 403 asks GET /run only for EFFECT and CONSUMED, so T5 cannot be applied to these phases unless the courier asks. Phase 1 R1 (RUN): a NO_EFFECT report on an EFFECT run is kept and ignored. The note never says these phases are read.
3. **Gate-key sets may differ (ARGUED).**
   - check_record.py 854 compares against a single `gkey`, while `run_outcome` and the witness take lists.
   - The courier cannot learn the witness's pinned set: its certificate is refused at GET /pubkey (witness_service.py 89-91).
   - A report signed by a key the witness pins but the courier lacks is APPLIED by the witness and is invisible to T5. The verdict then fails safe as UNVERIFIED, but a conflict made through that key is not seen.
   - Needed: an explicit precondition that the reader's key set equals the witness's.
4. **"Differs" must mean a different pair, not different bytes.** T5 is stated on pairs. But 4.2 says "the earliest that differs"; read as bytes, the re-signed copy of R1 (seq 12) becomes a false conflict.
5. **Oversized or malformed digests (RUN P2).** A 200,000-character digest is a distinct pair, correctly, since an honest host signs only 64 lowercase hex characters. The note should say that a non-canonical digest is itself equivocation. 4.2 then cannot carry the digest (B3.1).
6. **A conflict with no VERDICT_RECORDED (RUN P4).**
   - Two different EFFECT reports were recorded at INTENT_PENDING (AUTHORISED; DENIED NOT_CONSUMED), then the intent was accepted.
   - The run is CONSUMED with two pairs and no VERDICT_RECORDED; e25a297 says NO_OUTCOME.
   - T5 calls it a conflict (right), but 5.1(a) ("the verdict is the report at its one APPLIED VERDICT_RECORDED decision") and 4.2's selection rule are both undefined here.
7. **C-1, C-2 and C-4 are sound. C-3 is broken as worded** (G1.10, F.1).

### B2. The token life table (3.3) and NOT COVERED (3.4)

The token machine is unmodelled by me; these counterexamples are argued from the text.

1. **SPENT-on-F6 versus the model.** In the table, a statement that fails "any check" (F6: every item held) makes its token SPENT. The outbox sends the oldest-tried item first, so a statement can arrive before an item it commits to. The author's own `spec` trace 3 does exactly that: COV is delivered, then the CONFLICT notice, and the model counts COVERED once both are held. Under 3.3 that trace burns the token. It is a loss of liveness, not of safety, but it means the model's "PASS" for G2.7 is not about 3.3 as written.
2. **Continuation versus a new chain.** 3.3 requires each statement to continue the last one accepted and name its digest. Step 2 §15 lets a courier that has lost its state begin a new chain.
   - As written, a courier that has lost its state can never be accepted again, and 3.4 item 4 keeps the budget NOT COVERED with no way back.
   - If a new chain is allowed, the continuation check is bypassed by design (PO-B).
   - The note must choose, and say how the mailbox tells a legitimate new chain from a dropped one.
3. **The freshness bound in 3.4 says too much.** "The reading [that] began no more than L before the status" holds for the checkpoint and the triggered runs only. A settled run's observation is carried from an earlier reading of any age (5.2; the second half of O3), resting on "settled cannot change without a decision".
4. **Replays I could not get through (ARGUED).** I found no path for: same budget, another budget, another key, another epoch, another mailbox, a status replay (stopped by the reader's nonce), or a delayed delivery. Under F5, counting from the moment of issue, each one is refused or only makes the statement staler.
   - One residual: if the USED mark is lost but the epoch survives (a damaged folder with a live process), a second statement on the same token could be counted. It can be no fresher than the first, so freshness holds, but it breaks the letter of F4. Issuance and USED marks must be durable before any answer (MB-7).
5. **The service cannot force SPENT** without the courier's key (DP2 aside), since only a faulty courier makes a failing signed statement.

### B3. The conflict notice (4.2) and the chain of items (4.3)

1. **"Always carries … the report's claim and result digest" is impossible.** The digest has no bound (P2). It should carry SHA-256 and length, as it does for the nonce.
2. **The selection rule is undefined without VERDICT_RECORDED** (P4). With three or more pairs it is also arbitrary, which is acceptable if stated, since the commitment covers all of them.
3. **"SHA-256 of the whole report as the witness gave it" is not canonical.** The witness returns PostgreSQL's jsonb rendering, so a later verifier may get different bytes. It should be `sha256(canonical(report))`.
4. **Nothing in §10 lets a reader retrieve anything.** 4.2 says evidence "is given back by its digest", and 4.3 has "a reader who is given the mailbox's items". §10 has no read of items or evidence. So the stated minimum is **not sufficient** for G3.4, G3.5 or independent verification. It needs at least GET /items (root, chain, after) and GET /evidence (digest); otherwise a reader must read the folder on the mailbox's account (DP2).
5. **Head-of-line blocking.** "Refuses an item that is not the next of its chain" lets one unacceptable item block the chain. Example (argued from P2): a conflict notice carrying a 200,000-character digest whole exceeds 64 KiB, so the service can keep the budget NOT COVERED with a single report. That is safe, but it is a denial the service controls, and it forces new chains (PO-B).
6. **"A notice of a conflict fails the record whether or not its evidence can be produced"** holds only if records must carry deliveries and a coverage statement whose item chain includes the notice. Nothing requires that: `verify_ctl.record` defaults to `deliveries=None`. A record that carries both reports fails anyway (T5), and the engineer's signature protects it (section 0).

### B4. 5.1 to 5.4

1. **The restated count rule (5.1c) is sound on the code.** P1-P4 show no missing rows, and WRONG_BINDING implies a genuine report was sent (`derive_verdict`).
2. **"Settled" is defined only for a recorded verdict whose stored value hashes to its digest.** Undefined cases:
   - NO_EFFECT: the stored result is `{'outcome':'no_effect',…}`, which the courier ignores.
   - INDETERMINATE: never settled, and never read.
   - RELEASED with reports (P5).
   The note must say which phases are read with GET /run.
3. **The unsettled-set cost in bytes is chosen by the adversary** (P3).
4. **L-1 to L-6 are right as limits.** L-5 should also name the result digest.
5. **L-2 needs B3.3.** The only fixed record of which report the courier saw is its own signed commitment, so that hash must be canonical.
6. **5.3 over-reads C1** in its row "conflicting report added after a run was final … the run read again, the conflict found — by test: C1". C1 shows the decision is visible after the cursor (true; my R1 confirms it). Nothing re-read the run: the "found" is the harness's `step2_view`, and the courier made no notice (C1b `made []`; my R1 second pass `made []`). Should be UNPROVEN.

## C. Factual sentences the outputs do not support, or over-read

1. **§1 "fresh databases plea23 and plea24"**: A, C and D share plea23; B and E share plea24, per each JSON's `database` field. They were not fresh for each part.
2. **§1 "gate_sizes run 1 … started while B3 was running"**: run 1's output has no timestamp, so this cannot be checked. B3 ran 18:25:26 to 18:31:48; run 2 started 18:32:21.
3. **§1 "unchanged code"**: true of the code files (my byte check). But the harness wrote its deployments into the pinned copy (`src/outputs/verify_tests/{GR,GS,GT,GU,GV,GW,GZ}`).
4. **§2.1 "as a governor that tries again would"**: not so in deploy.py's topology (G1.2).
5. **§2.3 "Conceal", 480/480 and 0/300**: a predicate compared with itself; it shows retention only (G1.4).
6. **§2.2 "The witness records … No other answer was seen"**: true only within B3's scope (G1.3).
7. **G1.8 "B3 (780 of 780 kept)"**: shows retention, not resistance to the granted roles.
8. **§5.1 "every report row in the store (41)" and "PO-7's first half is now tested"**: read with the owner password, unlabelled.
9. **§5.2 "(0.04 to 0.06 s, about 2 KB)", "about a minute a pass" and "bounded by the budget"**: honest operation only, understated, and 5 MB per run adversarially (P3).
10. **§5.3 "by test: C1"**: over-read (B4.6).
11. **§5.3 "a checkpoint that bears the mailbox's token"**: no mailbox token exists; the harness made the token.
12. **§8 S-5 "a record of that case was not made"**: my phase 1 R3 made one for a RECONCILE plant before START. The position test passed; the record failed only because my forged value was not realistic, so that case is still not shown with a realistic forgery.
13. **§3.3 "Mailbox process stopped and continued — safety"**: not tested.
14. **§2.1 "the governor … asks the host again"**: true by code, not exercised in any test (B2's stored result was null).

The other figures I checked match the raw fields: B1 and B2 steps; 780, 6,830, 480, 300, 372, 258 and 95 (my recount); A1 to A8; D1 and D2; C1, C2 and C6 courier `made []` with run_outcome PASS; 508,180,089 bytes.

## D. Phase 1 findings the draft does not address

1. The phases the courier never reads: NO_EFFECT, INDETERMINATE, RELEASED (B1.2, B4.2).
2. The gate-key-set precondition, and check 6's single key (B1.3).
3. Pair, not bytes, for 4.2's "differs" (B1.4).
4. Unbounded result digests (S-6 names only the nonce), and non-canonical digests as equivocation (B1.5).
5. No interface for reading items or evidence in the minimum changes (B3.4).
6. The adversarial byte cost of the unsettled set (G4.9).
7. The harness writing into the pinned tree, and unlabelled owner-password reads (C.3, C.8).
8. Non-canonical report hashing (B3.3).

Addressed by the draft: delayed delivery (erratum); the clock primitive and MONOTONIC under-counting (3.2); the accumulator (4.3); the quadratic cost of incremental reading (5.4); unsafe carry-over (5.2); the unsigned-/run limit (L-2).

New in phase 2: the null-nonce scope (P5); a conflict without VERDICT_RECORDED (P4); C-3 under courier state loss (F.1); head-of-line blocking (B3.5); the contradiction between continuation and a new chain (B2.2).

## E. Before any Step 3, and what can only come during or after it

This is not a GO or NO-GO; that decision is the owner's.

**What the evidence supports now.**
- The facts about the frozen parts: G2.1-G2.3, G1.8, G4.1, G4.2, and the chain part of G4.9.
- The fault in the baseline's freshness wording, shown on the real mailbox.
- The outline of Decisions 1 and 4 is sound, but each has text defects that should be corrected before an implementer gets it: B1.1, B1.2, B1.6 and C-3.

**What should be true of the text before coding.**
1. Corrections B1.1, B1.2, B1.6 and C-3, with "settled" defined for every phase.
2. 4.2 with hashed, bounded fields and a canonical report hash (B3.1-B3.3).
3. One rule for a courier that has lost its state, continuation or new chain (B2.2), with PO-B argued for that rule.
4. Item and evidence reads added to the minimum mailbox interface (B3.4), and a stated way out of head-of-line blocking (B3.5).
5. The gate-key-set precondition (B1.3).
6. An independent model or test of the token machine (PO-A) and the item chain (PO-B). My enumerator covers only C-3 under state loss, at tiny bounds.
7. The owner's explicit acceptance of T4, knowing that honest UNKNOWN-then-verdict cannot be reached in deploy.py's topology (G1.2).
8. DP1 and DP2 (B-1, B-2). Without them no test can show the contract; that may be accepted as a standing limit, but not assumed.

**What can only be established during or after implementation.** That the mailbox enforces 3.3 (VT-26 to VT-29); suspend and hypervisor pause on the real host (PO-D); the G1.9 wording; coverage under adversarial cost (P3-style) and a cold start at the operator's L; fork and rollback under the cursor (G4.8); that earlier-form records still verify (F5).

## F. Modelling

**F.1 The item chain and C-3.** My script `review/rv_itemchain_model.py`, output `review/out/rv_itemchain_model_run1.txt`.
- **Bounds.** One budget, two runs: A starts with an UNKNOWN report and may get a verdict; B may get a FAIL. Up to 3 readings. The courier may deliver the head of its outbox (the mailbox takes only the next item of a chain), lose its state once (2 chains), and make a statement after any reading.
- **Left out.** No clock or token, no evidence pieces, no mailbox restart, no out-of-order delivery.
- **Invariant SOUND.** While COVERED: a FAIL existing at the statement's reading is held; and if INTERRUPTED_A is held and A had its verdict at that reading, VERDICT_A is held.
- **Result with C-3 as worded:** 598 states, SOUND broken. Shortest trace:
  1. the courier makes INTERRUPTED_A;
  2. run A gets its verdict;
  3. INTERRUPTED_A is delivered;
  4. the courier loses its state;
  5. it reads afresh and makes nothing;
  6. its statement for the new chain at k=0 is accepted.
  The budget is COVERED while the mailbox says "no verdict" for a run that has one.
- **Result with C-3 derived from the witness's data:** 1,443 states, SOUND holds.
- The bounds and the invariant are mine. It is not a proof; it shows only that C-3 must be keyed on the witness's data.

**F.2 The token state machine (PO-A): UNMODELLED by me.** B2 lists defects argued from the text.

**F.3 The author's model, re-run.** An unmodified copy in `review/authormodel/` (output `run.txt`) reproduces both figures the author quotes:
- `spec`: 4,137,699 states, no invariant broken;
- `receipt_time`: 7,478,677 states, CONSISTENT and NOTICED broken.

This reproduces the search, not its fidelity: per B2.1, the model's acceptance rule differs from 3.3.
