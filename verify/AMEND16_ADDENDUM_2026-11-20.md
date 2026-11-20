# Amendment 16: addendum to the property file. The courier's reading and sending are designed again

20 November 2026. Private working material. Internal work by the author of the code, under the owner's direction. It is
not an independent validation.

This file is committed on the branch `verification-amendment-16` before any code of the fifth form is written. It does
not change `verify/AMEND16_PROPERTY_2026-11-20.md`: P1 to P7 and T1 to T8 stand as written there. It says how the
courier is to be built to meet them, and adds what the tests must show for the new design. It is not the declaration.

## Why

Four forms of the repair were built on this branch and each was reviewed internally. Each review found serious faults in
the repair itself; they are recorded in the development log and will be listed in the declaration. The fourth review
(of `769f6e4`) found three more of high weight:

1. Two notices that cannot be delivered, one first and one last in the waiting list, held back every notice between
   them at every pass, with the mailbox answering.
2. An answer of the witness that made the courier fail in a way it did not expect (deeply nested JSON) left the budget
   unread with no alarm, and a status that read as before.
3. An entry of the chain whose run name was not text was kept by the courier, which at the next pass judged its own
   state malformed and read that budget no more, telling the mailbox nothing.

The judgement of the reviewer and of the coordinator is that the design is at fault and not only its details. One loop
decided, run by run, what to ask for under a limit of time, and decided in the same breath what to send; by the fourth
form it kept about ten marks that bear on one another (tiers, digests of entries, unread, suspect with a count of clean
readings, runs put off, waits, a flag for a failed delivery, a set of refused notices, a second notice tried as a probe,
times set back). Each review found a new combination. On 20 November the owner chose to design the loop again and not
to patch a fifth time, and to leave the coverage lease (a signed heartbeat) to Amendment 17.

## What is kept from the four forms

Notices of form 2 and their signed words; `shown()`, `field_name()`, `printable()` and the checker's use of them; the
witness's rule on names at POST /accept; the coverage statement (WATCHING), its check in the record and
`--require-delivery`; the UNREADABLE and INCONSISTENT notices; the three states' wording; a deadline for a whole
request, with the answer closed at the deadline; times later than the clock set to the clock; the checks of R30 and R26
that test these. What is replaced is how a pass chooses what to ask for, how notices are sent, and what happens when
the witness's answer, or the courier itself, is not as expected.

## The design

### A. Asking: two lines, each in order, each with a stated share

For one budget in one pass, after the checkpoint and the chain are read:

- **Runs that need no request** to the witness are settled in every pass. They are never put off and count for nothing below.
- **Every other run not yet done is in one of two lines.** *New*: never asked for, or the chain's entry for it is not
  what it was when it was last asked for; in the chain's order. *Old*: all the others, the one asked for longest ago
  first. A run in trouble is in the old line like any other: there are no further tiers.
- **Time.** A budget's pass has `pass_seconds` for asking. While both lines hold runs, each line has half of it; a line
  that is empty gives its half to the other. Whatever the time, at least `floor` runs of each line that is not empty
  are asked for, where `floor` is worked out from `pass_seconds` and the deadline of a request (a request and the
  question that follows a failed one cost at most two deadlines), and is never less than 1.
- **The bound, stated and shown.** A run in the old line is asked for at least once in every
  ceil(old line / floor) passes; the status gives the two lines' lengths, how many of each were asked for at the last
  pass, and that number of passes. Open and to be stated: if the service adds new runs faster than a pass can ask for
  them, the new line grows without end; that is shown (its length, runs put off, exit status 1, no WATCHING
  statement), not repaired.
- **One mark for trouble.** A run whose reading failed, or after which the witness stopped answering, is recorded once
  as unread, with since when and why. The mark is for the status and for the UNREADABLE notice; it does not decide the
  order. It is removed when the run is read. There is no separate list of runs "after which the witness stopped
  answering", and no count of clean readings. After a failed reading the run was asked for last, so it stands at the
  end of the old line and every other run comes before it.
- **A run put off** (not asked for, for want of time) is listed as put off, never as unread; if it bears the mark and
  the waiting time has passed, its UNREADABLE notice is made, in words true of a run not asked again.
- **WATCHING** is made only after a pass in which every run not done was asked for or needed no request.

### B. Sending: an outbox apart from the reading

- Every notice made is put in the budget's outbox with a record of its own: when made, how many times tried, when last
  tried, and what came of the last try (accepted; refused by the mailbox; no valid receipt; could not be sent).
- **Whether the mailbox can be reached is asked of the mailbox, not inferred from a notice.** Before notices are sent in
  a call, and again after a notice fails as a transport fails, the courier asks the mailbox for its key (GET /pubkey,
  which the mailbox already answers). If that is answered with the key the courier was given, the mailbox can be
  reached and the notice that failed is the one in trouble: it is kept, counted, and the next is tried. If it is not
  answered, nothing more is sent in that call, and nothing else is tried in that pass.
- **Order.** Notices are tried the one tried longest ago first (never tried first, in the order made). So no notice,
  and no pair of notices, can stand in front of another for ever: a notice that can be delivered is tried in every
  call in which the mailbox can be reached.
- A notice is never dropped. One not yet accepted is listed in the status with its kind, its count and the last reason.
- Sending a notice as soon as it is made is kept. Sending never changes what is asked of the witness, and a failure to
  send never ends the reading of a budget.

### C. What the witness says is checked where it comes in, and nothing ends in silence

- The chain's entries are made into records of a fixed shape as they are read: a list of the length the chain gives, a
  run's name that is text, a phase that is text. An entry that is not so is not kept in the courier's state. Whether
  the witness's own acceptance can put such an entry in a chain is to be found out first. If it can, that is closed at
  the witness by the same rule as D47 (the change to the gateway's file and its necessity to be named in the
  declaration), and the courier treats a chain that holds one as it treats any answer of the witness that cannot be
  believed: the budget is stopped, with its alarm. So the courier's own state is never made malformed by what the
  witness says, and "the courier's own state is malformed" is left for a state file damaged on disk.
- An answer that cannot be parsed for any reason (too deep, too large for memory) is "not readable", as one that is
  not JSON is.
- **Every way a budget's pass can end is one of these, and each is recorded in the state and shown in the status:**
  read (whole, or with runs put off); the witness could not be reached (blocked, alarm after the waiting time);
  what the witness said cannot be believed (stopped, alarm at once); the courier itself failed (any other error: it is
  recorded as the courier's failure with the error's name, the budget is marked as not read, and after the waiting time
  the alarm that the courier cannot read the budget is sent, in words that say the fault is the courier's). What the
  last pass came to is written whatever happened, so the status cannot show an earlier pass's success after a later
  failure.
- Local words follow the signed ones: where a pass ended because the witness stopped answering after one run, the
  summary and the status say that, and do not say the budget was not read.

### D. Not in this amendment

A signed heartbeat by which the mailbox, or a reader of the record, can tell that the courier is still watching (so
that a courier that is not running, or whose own state is damaged, is seen from outside) is Amendment 17. Until then:
CONFIRMED in a record shows that the courier began to watch; a courier that is down tells the mailbox nothing; budgets
are read one after another, so a slow budget delays the next. Release gates G2, G5 and G6 stay implemented and
internally tested, with open obligations. One machine, one kernel and no real separation of the parties are unchanged.

## What the tests must show, besides T1 to T8

Each by a check that fails when the property is broken, shown by planting the breakage; a planted fault that makes a
test hang or stop with an error is counted apart and is not counted as caught.

- **U1 (A).** With old runs in flight, runs that hang and new slow runs added at every pass: a run whose entry in the
  chain comes to say FAIL is noticed in that pass; a run whose entry does not change but whose outcome becomes FAIL is
  noticed within the number of passes the status states; that number is the one worked out from the lines' lengths.
- **U2 (A).** A run after which the witness stops answering, every time or every other time: every other run that
  failed is noticed; the run is listed as unread and gets its UNREADABLE notice after the waiting time; it stands last.
- **U3 (A).** A pass that put runs off makes no WATCHING statement, exits 1, and the status says how many of which
  line; a run read cleanly since its trouble gets no UNREADABLE notice when put off.
- **U4 (B).** With one, two (first and last) and several notices that cannot be delivered, in each way (refused; no
  valid receipt; the connection dropped; an answer that is not JSON; no answer before the deadline), every other notice
  is accepted in the same pass; each stuck notice is listed with its kind and count; none is lost or sent twice.
- **U5 (B).** With the mailbox not answering at all, a pass costs a stated number of deadlines for that budget and no
  more, whatever the number of notices waiting; when it answers again, all are delivered.
- **U6 (C).** An entry of the wrong shape in the chain (a name that is not text; too short; not a list): the courier's
  state is not made malformed, the budget is stopped with its alarm, and the next budget is read. If the witness can be
  made to accept such an entry, it refuses it after the change, and adds no decision.
- **U7 (C).** An answer nested too deeply, at the checkpoint, the chain and a run: at the first two the pass ends as
  "the witness cannot be read" with its alarm after the waiting time; at a run, the run is unread and the others are
  read. An error planted inside the courier's own handling of a pass: recorded as the courier's failure, shown in the
  status, alarm after the waiting time, the next budget read.
- **U8 (C).** After each way a pass can end, the status says that way and no other, and coverage does not read as
  plainly CONFIRMED after a pass that did not read the budget whole.
- **U9.** Every check of R30 and R26 that the four forms added for what is kept still holds, or is restated by name in
  the declaration with the reason.
