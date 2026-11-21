# Diagnostic: does the witness's reading show both reports of a replaced verdict, and when can one be kept from view?

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, it is not a declaration, and no official run was made. No code of the service, the gateway, the witness, the
mailbox or the courier is changed. The code under test is `e25a297`, which is INCOMPLETE, failed its eighth internal
review and is not declared.

## What was asked

After `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` showed that a FAIL the gate host signed and the witness recorded
can be replaced by a PASS with no notice, the owner asked, before any implementation work: does the existing witness
read interface expose both conflicting gate-signed reports of the run; if so, can the courier and the record's checker
tell the conflict without a change to the gateway; and can either report be concealed by the service or replaced before
it is observed. Detecting conflicting signatures is to be kept apart from proving which verdict is true.

## What was run

`tests/diag_amend16_powers/visibility_check.py`, from a copy of the tree at `e25a297`, against a real deployment (witness
service, gate host and mailbox under mutual TLS) on a database made fresh for it (`plea22`), 12:32 UTC. Results:
`tests/diag_amend16_powers/results_2026-11-21/visibility_check.txt` and `.json`. The machine had restarted at 12:29 UTC
and PostgreSQL was started again. The harness acts as the service with what the property file gives it: the gate's key,
the client's certificate and the role `plea_local`. Two predicates in the harness show what the data already given
allows; they are not proposed code.

## Findings

**1. Both reports are exposed (V2).** After the replacement, GET /run with the courier's certificate returns both EFFECT
reports of the run, at decisions 8 and 9, with two different digests. Each is signed by the gate's key for this budget,
run and nonce. The chain, read the same way, holds two RECONCILE decisions for the run: APPLIED / VERDICT_RECORDED at 8
and DUPLICATE / VERDICT_RETRY at 9, and each report sits at the decision of one of them.

**2. The conflict can be told from what is already given, with no change to the gateway. Nothing tells it today (V2,
V3).** "Two different digests among the genuine EFFECT reports of one run" is true of the replaced run from the
courier's own reading, and true of the record, which carries both reports. The courier concluded PASS and made no
notice, with the 900 s waiting time and when started afterwards. The record verified, with no failing check, and gives
the run as PASS. Telling the conflict would be a change to the courier and to the record's checker only.

**3. An honest repeat does not look like a conflict (V4).** The gate host's own report sent to the witness a second
time is also recorded as DUPLICATE / VERDICT_RETRY with a report, and the two reports carry the same digest. The
predicate is false for it.

**4. A forgery made before the witness sees anything leaves nothing to tell (V5).** The gate host signed FAIL. The
service sent the witness only a report of its own over a forged PASS and stored the PASS. The client was told "DECLARED
CHECK MET". The witness holds one report and one RECONCILE decision; the courier made no notice; the record verified.
No reading and no check in this path can see it. The only trace is in the gate host's own state, which is the
service's.

**5. No role the store grants can remove or change a recorded report (V6).** DELETE and UPDATE of the first (FAIL)
report were refused for `plea_local`, `plea_witness` and `plea_control`. So within the granted roles a report, once
recorded, stays in the witness's answer: neither of the two can be concealed, and neither can be replaced before a
later reader sees it.

**6. With the owner's password, which the repository gives, a report can be removed (V7).** The first report was
deleted as the owner. GET /run then returned one report; the conflict could no longer be told from the reports; the
courier made no notice and the record verified. One trace remained: the chain still holds two RECONCILE decisions for
the run against one report. The chain does not bind a report's digest, so which digest was removed cannot be recovered
from it.

**7. What a reader can and cannot conclude.** Two genuine reports with different digests show that the gate's key
signed two different results for one run. They do not show which result is true, nor that the first is: the same key
signed both, and by finding 4 the first recorded report can itself be the forgery. In the case shown the first was the
gate host's own, but nothing in the data says so.

**8. Before observation.** A courier that reads the run between the first report and the replacement sees one report
and no stored result, and concludes UNVERIFIED, which it sends only after its waiting time. For the courier to conclude
PASS the PASS digest must already be recorded, so at that reading both reports are in the answer. The replacement
cannot therefore be finished unseen by a reader that looks for two digests; it can only be finished unnoticed by one
that does not.

## Limits

One deployment, one machine, the self-test fixture, each case made once. The harness's author acted as the service. No
planted-defect pass was made on the harness. Whether an operator's own tooling outside this path would notice any of
this was not examined. Nothing here proposes or makes a repair.
