# F17 under Amendment 12: diagnosis

19 November 2026, on the branch `diagnostic-f17-2026-11-19`, made from `bc33c4b`. Private working material. Times are UTC.

This is internal work by the author of the code, under the owner's direction. It is not an independent validation. It adds
instrumentation and a diagnostic test, and changes nothing the service does. The declaration of Amendment 12, its official
results and its amendment are as they were: F17 failed in the official run, and that stands.

## What was asked

Why F17 did not make its case, two failures in the same second, in the official run of Amendment 12; and a test of the same
property that says for itself whether its case was made.

## What was found

**1. F17 never had more than about a tenth of a second to spare, and the sandbox used it.** F17 sends two failing designs one
after the other, beginning 0.03 s into a second. Each notice is named for the second in which its run's check ends, so the
second check must end before 1.000. Measured on this machine, on the code of the declaration:

- a job's first submission on a new baseline takes about 0.49 s, of which the sandbox is 0.10 s; about 0.27 s passes before
  the check begins (the front door, the governor, the witness);
- so the second check ends at about 0.90 to 1.01 s. In one traced run of the whole front door suite it ended at 1.010, ten
  milliseconds late, and F17's first try missed; its second try made the case, and F17 passed.

Before Amendment 12 a check ran as a plain child process, in a few hundredths of a second, and the pair ended near 0.9 s.
The sandbox takes about 0.07 s more for each run. That is the whole of the cause of the first miss.

**2. Each submission on a baseline is slower than the one before, so after one miss F17 cannot recover.** This was not known
before. Thirty submissions in a row on one baseline took 0.49 s for the first and 1.97 s for the thirtieth: about 0.05 s
more for every run already made. The sandbox's time does not change (0.10 s each), and nor does the time before the check
begins; the time grows after the check ends. F17's six tries are twelve runs on one baseline, so its later tries cannot end
within a second, and it fails all six once it has missed the first. Whether F17 passes is decided by a few hundredths of a
second in its first try.

**3. Two statements made before were wrong.**

- The amendment says that when F17 fails, "each of its runs takes about a second". That was read from the notices' names,
  which show only that the second run ended in the next second. No run was that slow. The amendment is not changed; this
  corrects it.
- The declaration says both development runs in which F17 failed began within minutes of a pass of deliberate defects, and
  offers that as all that was known. It was a coincidence. The sweep of stale groups, changed in the eighth form because of
  it, was not the cause.

**4. Where the growth is has not been found exactly.** After a verdict the front door asks the service for the job's runs
(`front_door.py`, `_submit` and what it calls), and the answer carries their totals. Something there, or in the gate, reads
or checks every earlier run. It was measured from outside, not traced inside. At this rate a baseline with 100 runs would
take about 5.5 s for a submission, and one with 1,000 about 50 s, near the client's 60-second limit. This is a defect of
its own, to be entered in the register: it is not in the sandbox, and it is not repaired here.

## The evidence

- `verify/diag_f17_collision_2026-11-19.json`: one run of the diagnostic, 23:38 on 19 November, with the sandbox traced.
- The traced run of the whole front door suite, 23:29 to 23:33: F17's four submissions began their checks at 0.426, 0.906,
  2.270 and 2.817 s after the second in which the first try began, and ended them at 0.530, 1.010, 2.368 and 2.917.
- Thirty submissions on one baseline, in seconds: 0.488, 0.507, 0.582, 0.624, 0.693, 0.731, 0.792, 0.797, 0.841, 0.878,
  0.928, 0.996, 1.057, 1.095, 1.143, 1.230, 1.274, 1.323, 1.406, 1.448, 1.464, 1.542, 1.753, 1.661, 1.680, 1.734, 1.735,
  1.790, 1.859, 1.966. A straight line through them rises 0.051 s for each run.
- The sandbox, six runs in a row, started from a foreground and from a background command: 0.096 to 0.118 s each, in the
  same control groups either way. How a suite was started does not matter, though every failing run had been started in
  the background.

## What was added

**`verify/sandbox.py`: timings, off unless asked for.** With `VERIFY_SANDBOX_TRACE` naming a file, each run appends when it
began, when its ids, groups and launcher were ready, when the check's output ended, how long freezing took, and when it
ended. Unset, nothing is written and nothing else differs. This file is not the declared one; the declared file is on
`verification-amendment-12`.

**`tests/diag_f17_collision.py`: a diagnostic, not a declared test.** Three parts:

- **A, timing.** F17's own way, with each submission timed, and the sandbox's phases beside it when traced. It reports.
- **B, component.** Two notices published with one stem, straight through `notices.publish`. No clock is involved: the
  second gets the name with `_2`, each holds its own text, and no part-written file is left.
- **C, together.** Two jobs are enrolled on one baseline, and each sends one of the two designs at the same moment. (One job
  cannot: the front door takes one design at a time for a job, and answers the second IN_PROGRESS.) The pair ends 0.6 to
  0.95 s into the second, not at 1.0.

B and C each end in exactly one of COLLISION_HANDLED, COLLISION_MISHANDLED, or PRECONDITION_NOT_MET. C checks its
precondition for itself: only when both notices are named for the same second and the same eight digits is anything judged,
and a case not made is never counted as a pass.

## What was run, and what came out

All on 19 November, on this branch, with the project's interpreter, the machine's file table raised for this start of the
machine only, and PostgreSQL 16.

- The diagnostic, whole, once, traced (the kept file): A made the case in 2 of 6 tries; B COLLISION_HANDLED; C
  COLLISION_HANDLED at its first try, the pair ending at 0.798 s.
- An earlier whole run: A made it in 2 of 6; B COLLISION_HANDLED; C PRECONDITION_NOT_MET in all six tries, because it then
  sent both designs from one job and one of each pair was refused IN_PROGRESS. That was the diagnostic's own error, and it
  reported itself as not having made its case. C was changed to use two jobs.
- B and C alone, six more times: COLLISION_HANDLED each time, C at its first try each time, the pair ending between 0.587
  and 0.941 s.
- The front door's whole declared suite, once, traced: 35 of 35, F17 passing at its second try. This is a diagnostic run
  on this branch's code, not an official result.

## What this does not show

- C is not deterministic. It leaves 0.06 to 0.4 s to spare where F17 leaves none, and it says when it has not made its
  case; on a slower machine it could fail to make it. Only B never depends on time, and B tests the naming alone, not the
  service.
- A case made with certainty, through the service, needs the service to be told the time, or the two runs to be held and
  let go together. Either is a change to declared code.
- Nothing here was read by a reviewer.

## What is proposed, for a separate, dated amendment

None of this is done here. Each would need its own declaration and official runs.

1. **Restate F17** to make its case as C does, with its precondition checked and reported apart from the property, and with
   PRECONDITION_NOT_MET a failure to test, not a pass.
2. **Find and repair the growth** in a submission's time with the number of earlier runs, and declare a test that measures it.
3. **Correct the amendment's sentence** about a run taking a second, in the amendment that follows, not in place.
