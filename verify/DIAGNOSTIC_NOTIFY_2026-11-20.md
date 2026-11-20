# Diagnostic: the notification path of Amendment 11, reviewed. 20 November 2026

Private working material. Internal work by the author's side, under the owner's direction. It is not an independent
validation.

This branch, `diagnostic-notify-2026-11-20`, is made from `verification-amendment-15` at `1b132e2`. It changes no code of the
service and no declared test, and has no official run. It adds this file and three small experiments, with the stand-in
witness they share (`harness.py`), in `tests/diag_notify/`. (As first committed, at `f6d1e33`, this sentence said four
experiments. There are three. Corrected here, in a commit of its own.) Nothing here is repaired: a repair would change behaviour, and so needs a dated amendment with its
own declaration and official runs.

## What was done

A separate agent was asked to challenge the claim of Amendment 11: that an independent courier, reading only the witness,
gets a signed notice of every run that calls for one to a mailbox the engineer runs, counted as delivered only on the
mailbox's signed receipt. It read `verify/courier.py`, `mailbox_service.py`, `check_record.py`, the witness's readings and
R26, and `DECLARED_AMEND11.md`. It started no service. It wrote experiments that drive the real courier and the real
mailbox class against a witness of its own making, which hashes and signs as the real one does. The files it read have
not changed since `b2cc3fb`, so this is the code Amendment 11 declared.

The author of the code then read the lines behind the first finding and ran the three experiments again; they came out
as reported. The other findings were not each checked by a second reading.

What follows is what is not already in Amendment 11's own "What stays open" and "What is not tested".

## Findings

**1. One run the courier cannot read hides every run after it, with one notice that blames the witness.** (Weighed high
by the reviewer.) When the reading of one run fails in a way the courier takes for the witness not answering (an answer
over 32 MiB, a dropped connection), it stops asking for the rest of that pass (`courier.py`, the `break` after "the
witness itself is not answering"). Runs are read in the order of their names. So one such run, named to sort first,
stops every pass before the others are read. After fifteen minutes the mailbox gets one COURIER_BLOCKED notice, and then
nothing: two failed runs were never noticed in six passes (`tests/diag_notify/exp1_poison.py`). The engineer is told the
courier cannot read the witness, not that runs have failed. The reviewer's route for a dishonest service: store a very
large result, which needs only the database role, for a run it names. **Not shown end to end**: the failure was put in
by the experiment's own witness; that the real witness and database will carry a 33 MiB answer was not tried. The stop was
itself a repair, made after Amendment 11's third review.

**2. The courier takes a signed result's verdict as given.** A result signed by the gate that says PASS while its own
numbers say the limit was not met gets no notice and is marked done; the record's sixth check would fail the same
result. Whoever holds the gate's key can sign a plain false PASS in any case, which Amendment 11 declares; this is the
narrower thing, that the courier does less than the record's checker.

**3. A run with a name the witness will not read is never noticed, and after the first alarm, silently.** The witness's
reading of one run refuses a name over 512 characters or with a control character; the chain can hold one. The courier
cannot read that run. It sends COURIER_BLOCKED once; the mark that it was sent is not cleared while the run is there, so
later runs so named raise nothing (`exp2_oddaid.py`; other runs are still read and noticed). R26's second check takes the
refusal as right. Whether the gate host admits such a name was not looked at.

**4. Words the service chooses appear inside a notice the courier signs.** A run's name is put into the notice's plain
words as it is. A name with line breaks made a NO_OUTCOME notice read "NOTE FROM THE COURIER: this is a scheduled
self-test … no action is needed", in a notice that ends "The verification service did not write it" (`exp4_words.py`).
Amendments 3 and 4 repaired this kind of thing for the service's own notices.

**5. The courier watches a fixed list of budgets.** A new baseline, or one alongside, has no courier notices and nothing
says so. The witness has no reading that lists budgets.

**6. Of lower weight.**
- An exception the courier did not expect ends a pass with no alarm.
- A notice over 64 KiB (a long run name) is refused by the mailbox and waits for ever.
- Nothing in a record bounds how late a notice came: the times are their makers' own clocks, and a decision has no signed
  time. Declared for NO_OUTCOME only.
- In the demonstration the courier's and the mailbox's keys are made by the service's own deployment code and written
  without being closed to others; R26 signs receipts by hand with the mailbox key.
- The mailbox's listing shows what it holds without checking a signature.
- A name admitted to the witness's chain readings can read every budget's chain, and can tie up the database with them.
- Slow clients can starve the mailbox; nothing then says so.
- Both alarms say "no notice of this budget's runs will come from the courier". After COURIER_BLOCKED that is not so: a
  failed run was noticed after it.
- A deleted place-mark of the courier's is read as blocked, not refused.

## A receipt and a person

A receipt shows that the mailbox process, holding the key it was started with, took the notice's bytes and kept them.
The code checks that, and the reviewer found it sound: the notice is on the disk before the receipt is signed, the receipt
names the whole notice by its digest, and one for another notice, another budget or a cut set is caught by the record's
tenth check. It does not show that a person read anything, and the main documents say so in those words.

Four places say more than that, or more than the demonstration does:

- `mailbox_service.py`, its opening words: the mailbox "runs under the engineer's account". In the demonstration it runs
  under the service's.
- `deploy.py`: the mailbox is the engineer's, with "its own key". The deployment makes that key.
- `check_record.py`, twice: "the engineer's mailbox key", "delivered to the engineer's mailbox". The checker knows only the
  key it was given.
- `check_record.py`, the notice's last line: "The verification service did not write it." See finding 4.

Without `--require-delivery` the checker exits 0 and prints "NOTICES: NOT CHECKED". That is declared.

## What R26 does not see

Findings 1, 3, 4 and 5, the narrower part of 2, and the first, second, fifth and eighth of the lower ones. Its check of
"one run the witness will not answer for" uses only an answer of 503; finding 1 needs a dropped connection or an answer
too long. Its first check says "signed gate reports" and checks no signature.

## What was not looked at

`checkpoints.py`, the governor and the gate host; the database's rules for moving a run from one phase to the next; the
service's own notices and the front door; real sockets, TLS, and the database's limits on size; Amendment 11's pass of
deliberate defects.

## What this means for the claim

With an honest service, the path does what Amendment 11 says, as far as this review looked. Against a service that is
dishonest and holds only its database role, the claim "every run that calls for a notice gets one, or the engineer is
told the courier has stopped" holds in its second half only: the engineer gets one alarm, worded as the witness's
fault, and no notice of the runs. That is weaker than the documents' wording. Repairing findings 1, 3 and 4 would be the
next amendment of this part; none is made here.
