# D20-F: confirmation on the merged tree `59de0dc` (23 November 2026), sanitised extract

An AI agent, instructed separately by the author, was asked the owner's condition for closing D20-F: on the merged tree, does the
original below-limit check output receive the correct verdict, and does the signed record agree? **This is an internal review, not
independent validation.** The full report, with its probes, is kept privately. This extract keeps the answer and the evidence for
the closed path, and describes the two items that stay open only as classes (register G19).

**Answer.** On `59de0dc`, the original output (199.99999999999999 against a requirement of at least 200) gets FAIL: LIMIT_NOT_MET,
held as printed, and the record's own checker re-derives the same verdict. No signed false PASS that verifies offline was found by the
check-output mechanism: 0 violations in 228 adversarial printed numbers and a 42-row matrix.

**The matrix** (the check's printed number against the requirement; the earlier tree `2c1af26` against `59de0dc`):

| requirement | printed | `2c1af26` | `59de0dc` |
| --- | --- | --- | --- |
| at least 200 | 199.99999999999999 | PASS, achieved 200 | FAIL, achieved 199.99999999999999 |
| at most 200 | 200.00000000000001 | PASS, achieved 200 | FAIL, achieved 200.00000000000001 |
| at least 200 | 1.9999999999999999e2 | PASS | FAIL |
| at least 200 | 27 significant digits just below 200 | PASS | FAIL |
| at least 200 | 32 significant digits just below 200 | PASS | UNKNOWN (output not usable) |
| at least 200 | the same number printed as a string | FAIL | FAIL |
| at least -5 | -5.00000000000000001 | PASS | FAIL |

The false PASS shows in 17 rows before and in none after. Every PASS and FAIL after is accepted by the record's checker.

**The original counterexample** (a check printing 199.99999999999999 for the design that gave the false PASS), decided by the corrected
tree: FAIL, LIMIT_NOT_MET, achieved `199.99999999999999`, margin `-0.00000000000001`; the record's checker agrees. A check printing
exactly 200 gives PASS with achieved `200`; one printing 200.00000000000001 gives PASS with achieved `200.00000000000001`.

**The decision path** has no tolerance, no epsilon, and no conversion of a decimal to a float. Decimal comparison is exact; the 28-digit
limit affects only how a value is written, and any disagreement between the written form and the decision becomes UNKNOWN.

**The adversarial set** (228 printed numbers over 8 requirements, with an independent exact-fraction oracle): 17 to 40 significant
digits near the limit, exponent forms, negatives, zero and tiny values, strings, plausible-range edges, a truth value, null, an array and a
5000-digit integer. No false PASS, no false FAIL, and none decided outside the plausible range. Numbers of 29 or more digits near the
limit are UNKNOWN, never PASS.

**The official results read** (not re-run by the reviewer): the gate suite 36 of 36 at Amendment 20; R35 passes, including the run through
the front door that signs and verifies a record offline.

**Which paths the closure covers.** A check's printed output, to the signed verdict and its offline re-derivation: yes. A design sent
to the front door and through the command-line client: read strictly since Amendment 20. The assistant-facing interface: **not
covered** (D20-G). **Earlier signed records:** the corrected checker cannot tell a record signed before Amendment 19 from a correct
one, so the old record still verifies (D20-H). Both are recorded as open in the register.

**Low observations:** a check printing a repeated key is decided on the last; values with more than 28 significant digits far from the
limit are written rounded (as the register already says of D20); a very small number inside a range that includes zero gives a verdict
of over 1 MB; some decimal-string spellings are read as numbers.

**Not checked by the reviewer:** the live services end to end (the sandbox was a stand-in), the signed-bytes form, other Python
versions, and how any particular assistant host parses JSON.
