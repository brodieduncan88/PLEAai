# Amendment 16: the property, and what its tests must show. Written before the code

20 November 2026. Private working material. Internal work by the author of the code, under the owner's direction. It is
not an independent validation.

This file is committed on the branch `verification-amendment-16` before any code of the amendment is written. It is not
the declaration: that comes later, with the code fixed and the development work recorded, before the official runs. If
what is built differs from what is written here, the declaration says where and why, and this file is not changed.

## What the amendment answers

An internal review of Amendment 11's courier, recorded on `diagnostic-notify-2026-11-20`
(`verify/DIAGNOSTIC_NOTIFY_2026-11-20.md`), found five things, D46 to D50 in the defect register. The owner asked on 20
November for these, in this order: D46, D47, D48, D50, and D49 evaluated.

## Who is trusted, and who is not

For this amendment the courier trusts: its own key, state and configuration; the witness's key (declared in Amendment
11: one consistent false chain is not caught); the mailbox's key for receipts.

It does not trust the service. The service is taken to hold the gate's key, the front door and a database role, and so
to choose: the names of runs; every field of a result, signed or not; how large a stored result is; and which budgets
exist. None of these may decide whether the engineer's mailbox is told, or what a courier-signed notice says in the
courier's voice.

Unchanged, and still material: the witness and the service share a database, and all parties share one machine and one
kernel in the demonstration. A service that can rewrite the chain is outside what this amendment answers.

## Three things that are not one another

1. **The courier is blocked or cannot read**: the courier's own statement about itself. It says nothing got through.
2. **The mailbox accepted**: the mailbox process, holding the key it was started with, stored the notice and signed a
   receipt. This is what "delivered" means, and all it means.
3. **The engineer acknowledged**: a person read it and said so. Nothing in this path shows that, and nothing in this
   amendment may say or imply it.

No wording, status or exit code added here may let the first or second be read as the third, or the absence of the first
be read as the second.

## The properties

**P1. No run hides another (D46).** In every pass in which the witness answers a checkpoint and gives its chain, every
run that may call for a notice is examined, whatever happened when any other run was asked for. A run the courier cannot
read does not end the pass, does not delay another run's notice beyond that pass, and does not change the order so that
it can.

**P2. A run that cannot be read stays unresolved and visible (D46, D47).** Such a run is never marked done. It is in the
courier's status for as long as it cannot be read, with since when and why. Once it has been unreadable for the
courier's waiting time, the mailbox is sent a signed notice of that run, in words that say the courier could not read
it and does not know its outcome: not that the witness is down, and not that the run passed or failed. One such run
does not use up, or silence, the notice for the next.

**P3. The witness down is told apart from one run unreadable.** When a run cannot be asked for, the courier asks the
witness for a checkpoint. If that is answered, the witness is up and the trouble is the run's (P2). Only if it is not
is the pass ended as "the witness cannot be read", as before.

**P4. Names the readings cannot serve are refused at the door, and survivable if present (D47).** It was checked: the
gateway admits any non-empty text as a run's name, while the witness's reading of a run refuses a name over 512
characters or holding a control character. So the chain could hold a run no courier can ask for. The witness's
acceptance is to refuse such a name from now on, with the same rule as its reading. A chain that already holds one, or
gets one another way, falls under P2.

**P5. The courier's words are the courier's (D48).** In the signed plain words of a notice, everything the service can
choose is shown as data: a run's name, a reason code, a criterion's name, units and numbers, a detail. Shown as data
means: on one line, with no line break or control or format character of the service's choosing, bounded in length,
marked as quoted where it is not a plain token, and its full form recoverable from the notice's other signed fields or
named by its SHA-256. A name the service chooses cannot begin a line, end the notice, or put a sentence in the
courier's voice. For every name the honest service makes, the words are exactly as they were, so records made before
this amendment still verify. The mailbox's readable copy shows the same words. The record's checker makes the words
again by the same rule.

**P6. Coverage is confirmed, not assumed (D50).** A budget is "watched by the courier" only from when (a) it is in the
courier's configuration, (b) the courier has read its chain to a checkpoint, and (c) the mailbox has signed a receipt
for the courier's signed statement that it has begun, naming the budget and the decision it began from. Until then
every place that speaks of courier notices for that budget says that coverage is not confirmed: the courier's status,
and the record's checker, which under `--require-delivery` fails a record whose budget has no such statement. A budget
the courier is not configured for is never reported by the courier as covered. That the courier cannot discover budgets
by itself is stated, not repaired, unless the witness can list them without a change to the gateway's store.

**P7. A signed verdict is looked at, not only taken (D49): to be evaluated.** The courier has no card and cannot do what
the record's sixth check does. It can read the result's own criteria. The candidate: where a gate-signed result says
PASS and its own stated numbers do not meet its own stated limits, the courier sends a notice saying so. The rule for
adopting it: it may only ever add a notice. It must not be able to turn a FAIL, an UNKNOWN or any other notice into
silence, so that a fault it shares with the gate or the checker cannot hide anything that is noticed today. If that
cannot be shown, it is left out and the reason given.

## What the declared tests must show

Each by a test that fails if the property is broken, shown by planting the breakage.

- **T1 (P1, P2).** With one run made unreadable in each of these ways: the witness's answer for it too long; the
  connection dropped while it is read; an answer that is not readable; a name the reading refuses. Every other run that
  failed gets its notice in the same pass, wherever the unreadable run sorts, first, last or between. Shown with more
  than one unreadable run at once.
- **T2 (P2).** The unreadable run is in the courier's status, pass after pass, never marked done; after the waiting time
  the mailbox holds a signed notice of that run whose words say unreadable and outcome not known; a second unreadable
  run gets its own. If it becomes readable, its true notice follows.
- **T3 (P3).** With the witness truly not answering, no run is reported unreadable; the courier's blocked notice is made
  as before, once the time has passed, and says the witness.
- **T4 (P4).** The witness refuses to accept an operation for a run whose name is over 512 characters or holds a control
  character, and adds no decision; names at the edge are accepted and can be read back.
- **T5 (P5).** For a run's name, a reason code, a criterion's name and units, and a detail, each holding line breaks,
  control and format characters, a forged courier sentence, a forged ending, and great length: the signed words have
  exactly the lines the courier's own form has, the service's text appears only inside its quoted place, and the
  record's checker accepts the notice and makes the same words. For plain names the words are byte for byte those of
  Amendment 11. The mailbox's readable copy is the same.
- **T6 (P6).** A budget not in the courier's configuration: no status calls it covered, and a record of it fails
  `--require-delivery` saying coverage is not confirmed. A budget configured but not yet read, or read but with the
  mailbox not answering: not confirmed. Read and receipted: confirmed, from the decision named. A record carrying another
  budget's statement, or one without a receipt, is not confirmed.
- **T7 (the three states).** A blocked courier, a notice made and not yet accepted, and a notice accepted are told apart
  in the courier's status, the summary of a pass and the checker's output; none of them uses a word for a person having
  read anything.
- **T8 (P7, if adopted).** A signed PASS whose own numbers miss its own limit gets a notice. And, with the added check
  made to fail in every way it can, each notice that would have been sent without it is still sent.

R26, Amendment 11's test, is to keep passing as declared. If a check of it must change because the behaviour it fixed
was the defect (its second check takes the refusal of a name as right), it is restated in the declaration, by name.

## What this amendment does not do

It does not close release gate G5. G2, G5 and G6 remain implemented and internally tested, with open obligations. It
does not separate the parties onto machines of their own, give the courier a way to know a person read a notice, or
answer a service that rewrites the chain in the database.
