# External AI review of `b97fe6b`: sanitised summary (23 November 2026)

A different AI system reviewed commit `b97fe6b` of this repository, read-only, on the owner's instruction, using a brief that fixed the
commit, the rules and the report format. **This is a summary, not the report.** The original is kept private by the owner. This summary
gives each finding's identity, severity class and status. For findings not yet repaired it gives nothing more: no file, no subsystem, no
description. It is a finding source for the author's work and **is not independent validation**: the reviewer's own account is that
every finding was argued from the code and not run. The author checked two of them by running code.

Status words: **repaired** means changed and tested internally by the author, and not closed; **open** means not changed.

| ID | reviewer's severity | status |
| --- | --- | --- |
| F-1 | high | **repaired** (Amendment 20): a number written as a bound in a baseline card was read inexactly |
| F-2 | high | **repaired** (Amendment 20): a released design and a submitted design were read less strictly than a check's output |
| F-3 | high (for one kind of compromised account) | **open** |
| F-4 | medium | **repaired in part** (Amendment 20): a negative zero and an unbounded reason text; the third part (a length limit) is deferred by decision |
| F-5 | medium | **open** |
| F-6 | medium | **open** |
| F-7 | medium | **open** |
| F-8 | medium | **open** |
| F-9 | low | **repaired** (Amendment 20): a verdict's design was compared with the one sent as program values |
| F-10 | low | **open** |
| F-11 | low | **open** |

**The reviewer's answer to its central question** (does any out-of-bounds design or value obtain a signed PASS that verifies offline?) was
"yes, conditionally", through F-1 and F-2. The author's own reproduction agrees, and both are repaired as above. For cards whose bounds
are written as text (every fixture in the repository), the reviewer found no way to such a PASS.

**What the reviewer did not do:** run any test suite, service or database. **What the author has not done:** verify the open findings, or
ask a second reviewer to confirm the repairs. D20-F (a related defect, in the reading of a check's printed numbers) is separate and is
dealt with in Amendments 19 and 20.
