# PLEA defect register (DRAFT, for the owner's approval)

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation and not a declaration. Nothing is repaired by it. **This is a draft**: it is kept on the branch
`diagnostic-amend16-alarm-2026-11-21` only, until the owner says where the permanent register lives.

**What it is.** Part A is the register as it was last issued: section 3 of the review pack's second edition,
transcribed without change. Part B is the status history since that edition. Part C adds, separately, four findings
outside the courier from the diagnostics of Amendment 16 (S-1 to S-4) and the deployment-security blockers. Part D
keeps the eight confirmed defects of the courier at `e25a297`. No row of Part A is changed, renumbered, regraded or
removed. Part E, added later on 21 November, holds the findings of the design gate (S-5 to S-7); Parts A to D are as
they were.

## The source of Part A, and how it was transcribed

- **Source.** `PLEA_Verification_Record_review_pack_2026-11-20.pdf`, "PLEA Verification Record: review pack", second
  edition, 20 November 2026, 36 pages, made 20 November 2026 03:48:48 UTC, sha256
  `1d2853a231b9301ecf9ebd41271319a8a10d53475a50405c46c5c2bfcfc162c3`. Its section 3, "Current defect register", pages
  17 to 28, holds D1 to D50. The file is in the session's working files, not in the repository.
- **Method.** The words were taken from the page source the PDF was printed from (`parts/03_defects.html`, written at
  the same minute) and set as Markdown: code as code, bold as bold, the table as a table. Then every piece of the
  Markdown, with its marks taken off, was looked for in the text of the PDF itself: 377 pieces (the 350 cells of the
  table's 50 rows, and 27 headings, paragraphs and list items); none was missing. White space was ignored in that
  comparison, since the PDF breaks lines where it likes.
- **What was not carried over.** The working notes at the foot of the page source, which are not in the PDF. Nothing
  else.
- **A correction.** `verify/DEFECT_REGISTER_ENTRIES_AMEND16_2026-11-21.md` (commit `d4e3a56`) said that no register
  holding D34 to D50 could be found and that the last issued register was the first edition's. That was wrong: the
  search behind it did not look in the folder that holds the second edition. The second edition was found on 21
  November and is the source here.

## Part A. The register as issued in the second edition of the review pack, 20 November 2026

Everything from here to the start of Part B is the review pack's text. "This edition" in it means the second edition
of 20 November 2026, and "the author" is the pack's.

### Current defect register

Every defect and limit on branch `verification-amendment-15`, commit `1b132e2`, open or repaired since, merged from
the declarations of Amendments 2 to 15 ("What stays open", "What is not tested"), the amendments,
`verify/DIAGNOSTIC_F17_2026-11-19.md` (branch `diagnostic-f17-2026-11-19`, `77a637c`),
`verify/DIAGNOSTIC_NOTIFY_2026-11-20.md` (branch `diagnostic-notify-2026-11-20`, `017529a`), `verify/REPORT_FRONT.md`
and sections 12 and 13 of the white paper (revision 15). All of it comes from the author's own work and reviews, made
by the author or by separate AI agents instructed by the author; those are internal reviews. Nobody outside has looked
for defects yet. The first edition (15 November 2026, on `118e2a3`) listed D1 to D35 as open. In this edition no row
is deleted: a row that an amendment changed keeps what it said, and adds what changed and when ("Since Amendment N").
D36 to D50 are new.

#### The eight numbered findings

Found after the first results of 11 November, each in the author's own work and reviews: four repaired, three closed
only for callers through the front door, one narrowed (white paper, abstract and section 6).

1. **The caller chose the baseline.** Closed only at the front door (F6); the first client keeps it (F1). Found by the
   author (`verify/AMENDMENT_2026-11-11.md`). Remains: D5, D6.
2. **One malformed design broke a record.** Closed only at the front door (F7); the first client keeps it (F2). Found
   by the author. Remains: D6.
3. **A stored card that is no longer a card gave no notice.** Repaired, Amendment 2, `8fa5973`, `285edd0` (R14, R16,
   F15). Found by the author. Remains: D32, D33.
4. **A notice could be written over another.** Repaired, Amendment 2 (F17, R16). Found by AI agents the author set to
   look (`verify/DECLARED_AMEND2.md`). Remains: D22, D28.
5. **A number the database hands back changed.** Closed only at the front door, Amendment 2 (F18). Found by those
   agents. Remains: D6.
6. **What a baselined check prints.** Repaired, Amendment 2 (R15, R16). Found by those agents. Remains: D20, D32.
7. **A sender's words shown as the service's.** Narrowed, Amendment 3, `948c293`, `eb1c923` (R17, F20). Found by an AI
   agent the author set to play a caller (`verify/DECLARED_AMEND3.md`). Remains: D30.
8. **A notice said what was not so of its run.** Repaired, Amendments 4 and 5, `4c665ab` and `9cd64a8`, results
   `99e59c6` and `a5cc3d1` (R18, F21). Found by an AI reviewer of the paper, working for the author
   (`verify/DECLARED_AMEND5.md`). Remains: D31.

**Listed as open before, and closed since,** so not in the table: Finding 3, open in `REPORT_FRONT.md` (`285edd0`);
the Verdict row and a revised baseline's banner (`DECLARED_AMEND3.md`; paper, revisions 9 and 10), repaired under
Amendment 4 (`4c665ab`, results `99e59c6`); "Baseline …, unchanged." (`DECLARED_AMEND4.md`) and the front door's own
text printing a design whole (`DECLARED_AMEND3.md`, in part), under Amendment 5 (`9cd64a8`, results `a5cc3d1`); and,
through the first client, a notice for a made-up hash landing in a real engineer's inbox (`DECLARED_AMEND2.md`), under
Amendment 6 (`23b8146`, results `118e2a3`; R19). D4, repaired since the first edition, stays in the table with its
status, so that its history is kept.

#### The owner's release gates of 19 November

A list of six, distinct from the hypothetical gap table G1 to G21 and from the gateway's tests G04 to G06 (D27).
**G1** reproducible assessment bundle with clean-room instructions: not started. **G2** strong disposable sandbox for
customer-supplied checks: implemented and internally tested (Amendments 12, 15), with open items (D19, D37 to D40,
D45). **G3** real separation of services, OS identities and keys on at least two hosts: not started (D8). **G4**
supported MCP/front-door route only, tested with real host products: not started (D6, D18). **G5** independent
notification path with delivery evidence: implemented and internally tested (Amendment 11), with open items; a mailbox
receipt shows the mailbox took the notice, not that a person read it; and an internal review of 20 November found that
a dishonest service holding only its database role could leave the engineer one alarm, worded as the witness not
answering, and no notice of the failed runs (D12, D46 to D50). **G6** witness-signed freshness checkpoints:
implemented and internally tested (Amendment 10), with open items (D7). None is closed: closing is the owner's
decision, and none has been independently assessed.

#### How to read the table

**Status.** *open*: not repaired. *narrowed*: an amendment repaired part of it; the rest is open, and is said in the
row. *repaired*: the amendment named repaired it, by internal tests only. No row is independently validated.

**Severity.** **High**: a failure can be hidden, a wrong verdict accepted, or a failure fail to reach the engineer, in
a plausible deployment. **Medium**: one of those only after damage or in an unusual set-up, or the evidence is
weakened. **Low**: wording, tidiness or inconvenience. The grading is the author's judgement under this rule. A row
whose grade changed in this edition gives the earlier one ("was").

**Blocks a pilot** means a team's trial on its own requirement and check, run as step 3 of the paper's section 13
suggests: through the front door and the MCP server, the service and its keys on a second machine. "Yes" if step 3
names the item, or if it is high and such a trial could meet it in use, by mistake or by a caller. Limits of the claim
itself are "no". In the first edition D1, D7 and D8 blocked a pilot because step 3 (revision 14) named them, and D2 to
D6 because they were high and could be met in use. In this edition step 3 is read in revision 15, which names the
console and the gate under separate accounts and the witness's statement of the latest sequence number, not the
journal: so D3, D7 and D8 block because step 3 names them, and D5 and D6 because they are high and could be met in
use. The notes below the table give each change of grade.

**Recorded in.** DA2 to DA15: `verify/DECLARED_AMEND2.md` to `DECLARED_AMEND15.md` ("open": "What stays open";
"untested": "What is not tested"). AM7 to AM15: `verify/AMENDMENT_7_2026-11-16.md` to
`verify/AMENDMENT_15_2026-11-20.md`. DIAG: `verify/DIAGNOSTIC_F17_2026-11-19.md`. DN:
`verify/DIAGNOSTIC_NOTIFY_2026-11-20.md`, branch `diagnostic-notify-2026-11-20` (`017529a`), an internal review by a
separate agent; no code changed, no official run. DF: `verify/DECLARED_FRONT.md`, "What is not tested". A1:
`verify/AMENDMENT_2026-11-11.md`. RF: `verify/REPORT_FRONT.md`, section 4. RM: `verify/README_FRONT.md`, "What it does
not do". RV: `verify/REPORT_VERIFY.md`. WP n: the white paper, section n. R and F tests are in `tests/verify_tests.py`
and `tests/verify_front_tests.py`, and all pass on this branch (`verify/results_*_amended15_2026-11-20.json`).

| id | area | what happens | status | severity | recorded in | blocks a pilot? |
|---|---|---|---|---|---|---|
| D1 | Front door | Every accepted design, repeats included, is appended to a journal with no size limit (`front_door.py`, `_submit()`). One job certificate, at the pace allowed, can add about 3 to 8 GB a day. A full disk then stops notices for every job (D2). **Since Amendment 7:** a new run is refused before anything is run or counted, with 507 `STORAGE_FULL`, when the journal would pass 1 GiB or the disk keep less than 512 MiB for notices; a repeat adds no line; a torn line is taken back (F22, F23, F26). **Since Amendment 8:** each baseline has a 64 MiB share, so one job no longer fills it for all, and the engineer is sent one notice a day for each reason (F30, F31). **Open:** the limits are defaults; more than sixteen baselines can still fill the journal between them; no archive or rotation, and room made by hand removes the tie of a run to its design; the front door reads the whole journal for each answer. | narrowed (A7, A8) | medium (was high) | DA2 open; DA7, DA8 open; WP 12; WP 13 | no (was yes) |
| D2 | Delivery | If the inbox or the tool's ledger cannot be written (full disk, changed permission, a file in place of the folder), the run is counted, never a pass, with no verdict and no notice. A part-written notice can be left. **Since Amendment 7:** the verdict is returned whatever happens to its notice, and says where it went; a notice the inbox cannot take is kept in `undelivered/`, which the console lists; a notice is written whole or not at all; the ledger never stops a run (R20, F19, F25). **Open:** a notice no place can take is not written (the answer says so); a kept notice reaches the engineer only through the console or the store; a kill the process cannot see can leave a temporary file, or, with no hard links, a part-written notice; a real full disk and real accounts were simulated. Since Amendment 11 the courier is a second path (D12). | narrowed (A7) | medium (was high) | DA2 open; DA7 open, untested; DA8 open; WP 12 | no (was yes) |
| D3 | Delivery | With the console and the gate under two accounts, the inbox the console makes is the console's. If the gate cannot write in it, a failing run stops with no verdict and no notice. This is the first step of separation, not damage. **Since Amendment 7:** the verdict is returned and the notice kept in the store (D2). **Since Amendment 8:** the gate checks that it can write each inbox, as it starts, on every run and on a look of its own; a job is enrolled or moved, and a new run admitted, only on a good check; refusals are noticed (R22, F28 to F32). **Since Amendment 9** this is called an inbox-writability check (`INBOX_UNCHECKED`; "proof of delivery" and `DELIVERY_UNPROVEN` in Amendment 8's files). **Open:** real accounts were never used, only a file in place of the inbox; for up to 30 s after an inbox goes bad, and 120 s after the gate stops, the check reads as good; the check is an unsigned file. | narrowed (A7, A8, A9) | medium (was high) | DA6 open; DA7, DA8 open, untested; DA9; WP 12 | yes (step 3 names it) |
| D4 | Baselining | The card's rules accept a check's stated limits that are not text (`baseline.py`, line 240); a notice joins them as text (line 436). On such a card, which can be signed today, a failing run gets no verdict and no notice. **Since Amendment 7, repaired:** each stated limit must be non-empty text; such a card is refused at baselining and at every run, as not a baseline card, with its notice in fixed words (R21). | repaired (A7) | high (when open) | DA2 open; DA7; WP 6; WP 12 | no (was yes) |
| D5 | Gate | The gate's tool gets the run's arguments, not the budget admitted (`plea_gateway/gate_host.py`, line 265), so the gate does not bind the baseline it decides to the budget charged. Only the front door makes them agree. The repair is a gateway change; not built. **Unchanged** by Amendments 7 to 15: `gate_host.py` is the same on `1b132e2`. | open | high | A1; F1; DA7, DA8 open; WP 12; WP 13 | yes |
| D6 | First client | `verify_client.py` holds the database credential and names the baseline. It keeps Findings 1, 2 and 5, and accepts half a surrogate pair (no notice can be written), a design nested about a thousand deep, wrong-shaped arguments and a hash not of 64 hex digits (UNKNOWN, no notice). Its answer to a made-up hash wrongly says the engineer was told. `verify/README.md` still calls it "The assistant's command". **Since Amendment 9:** unchanged but for its status listing, its view of the requirement and its help; through it a cut-off run still gets no notice from the service. | open | high | A1; DA2 open; DA6 open; DA9 open; F1; F2; WP 12; WP 13 | yes |
| D7 | Record | A record proves integrity up to its sequence number, not freshness. An older record leaves out later runs, still verifies, and needs no key to show. Nothing signs the latest sequence number. **Since Amendment 10:** the witness signs checkpoints; a record carries one (check 9); given a checkpoint obtained separately the checker says whether the record is current; a keeper refuses rollbacks and forks (R25; C19). **Open:** an old checkpoint handed over with an old record reads CURRENT within the age allowed; only one the reader fetched with a nonce of their own shows "current now"; the witness is one party, and a consistent false chain is not caught; the keeper is on the same machine and account. Release gate G6 is not closed. | narrowed (A10) | medium (was high) | `check_record.py`, opening note; WP 8; WP 12; WP 13; DA10 open, untested | yes (step 3 names it) |
| D8 | Deployment | Logical separation only, in an author-run demonstration: every service and key on one machine under one account, separated by process and credential. An assistant with a shell there could read the keys. No defence against an assistant or insider with access to that machine; separation by machine is not done. **Since Amendments 10 to 12:** the keeper, the courier and the mailbox run there too, and the service runs as root. Release gate G3 not started. | open | high | RM; DF; WP abstract; WP 8; WP 12; WP 13; AM10 to AM12 open | yes |
| D9 | Keys | One party holds the witness, gate and engineer keys and the database: by the author's analysis, all it takes to drop or reorder runs in a record that verifies. Key custody, withdrawal, identity and independent time are not designed. **Since Amendments 10 and 11:** the keeper and the courier catch a witness that contradicts what it told them, not one that tells everyone the same false chain; one authority, run by the same party, issues every certificate. | open | high | RV section 5; WP 8; WP 13; DA10, DA11 open | no (limit of the claim) |
| D10 | Scope | A record shows what the declared check returned, not that the check is right, the requirement complete or the design the part built. A wrong check is recorded faithfully and signed. Work done elsewhere has no record. **Since Amendment 9** a pass is shown as the declared check met, with what the check does not cover (R24, F33); the signed verdict is still PASS. **Since Amendment 12** the sandbox keeps the check from the service; it does not make the check right. | open | high | RV section 5; WP 12; DA9, DA12 open | no (limit of the claim) |
| D11 | Delivery | A run cut off when the gate host dies is counted INTERRUPTED, never run again, and gets no notice. **Since Amendment 7:** the engineer is sent one notice once the gate signs the run interrupted, at the next ask for its design (F24, F27). **Since Amendment 9:** the front door asks for runs left pending itself, after two minutes, at most twelve times (F34, F35). **Since Amendment 11:** the courier sends a notice of a run with no outcome after 15 minutes, and of its interruption once signed (R26). **Open:** the look runs only while the front door runs and only for designs the journal holds, and leaves a run after twelve asks with no notice that it has; through the first client the service writes no notice; a record does not require a notice for a run with no outcome yet. | narrowed (A7, A9, A11) | medium | F12; WP 12; DA7, DA9, DA11 open | no |
| D12 | Delivery | A notice is an unsigned file in a folder, outside the record (`verify_tools.py`, `_notify()`), so whoever can write the inbox can remove or alter one. That the engineer reads it is assumed; email or chat is not built. **Since Amendment 11:** a second path. A courier that reads only the witness signs a notice of each run that calls for one and delivers it to the engineer's mailbox, which signs a receipt; a record can carry both (check 10; R26; C20). The service's own notices are unchanged, and this row stands for them. **Open:** a receipt is not reading; the courier believes the witness; courier, mailbox, witness and service share one machine and account; no heartbeat. Since the internal review of 20 November (DN): with an honest service the path does what Amendment 11 says, as far as reviewed; against a dishonest service holding only its database role the engineer may get one alarm, worded as the witness not answering, and no notice of the failed runs (D46 to D50; open, not repaired). Release gate G5 is not closed. | narrowed (A11) | medium | WP 12; WP 13; DA8 open; DA11 open, untested; DN | no |
| D13 | Delivery | `inbox/unclaimed/` is read by nobody and not counted by the console. In damaged services a real baseline's notices go there too: one made before Amendment 6 whose folder was removed, or whose folder of baselines could not be searched, before the repaired tool first started; or one whose folder is gone and whose inbox's hash file is missing, unreadable or another's, or whose inbox is now a file. | open | medium | DA6 open; WP 12 | no |
| D14 | Changes | A change shows in a record only as a revision; a relaxed requirement can still be baselined as new, unlinked. A second job's reason is in a log signed line by line, not chained, not in the record, and is not asked while another job's stored baseline is unusable. **Since Amendment 9:** the console refuses a second baseline for a requirement id it holds unless it is a revision or the engineer gives a reason, which the signed card carries with every baseline held for it (R23). **Open:** a new id, another service, a card made by other means (not refused by the gate), ids whose letters only look alike, and a folder put in by someone who can write the service's home. | narrowed (A9) | medium | RF; DA2 open; DA9 open; WP 12; WP 13 | no |
| D15 | Service files | Whoever can write them can make the tool wait for ever (an endless file; no read or time limit), make the front door drop every connection (a deeply nested jobs file), make answers fail after a run (a damaged journal), or add unsigned parts to a stored baseline that are handed out and copied into a record. Verdicts are not affected. **Since Amendment 8:** a journal line nested too deep to read is passed over when the journal is read for an answer (F30). | open | medium | DA2 open; DA8; WP 12 | no |
| D16 | Front door | The latest binding seen, pacing counters and locks are in memory; after a restart an earlier signed binding put back can undo a revocation (untested). A binding naming one baseline and another's budget is noticed and still sent on. | open | medium | RF; RM; DF; DA2 open; WP 12 | no |
| D17 | Job certificate | A bearer credential: its holder can spend the job's runs and cause notices, not change what is verified against. Renewal is not built. | open | medium | RF; RM; WP 12 | no |
| D18 | MCP | A host may shorten or drop a result and an assistant misreport it; the record and notice do not depend on them, and nothing more is done. Only stdio is tested. **Since Amendment 9** the answer's field is `declared_check_met`; a host product reading it is not tested. Release gate G4 not started. | open | medium | RF; RM; DF; DA9 untested; WP 12 | no |
| D19 | Check | Runs as a separate process in an empty folder under the same account, not a sandbox; Python only, 30 seconds. **Since Amendment 12:** each run gets a disposable sandbox: ids of its own, new namespaces, a root in memory with /usr read-only, control groups (1 GiB, 64 processes), per-process limits, a system-call filter; the check is not run unless the sandbox is made (R27; C21). **Since Amendment 15:** six prerequisites checked before every run, the file table's floor worked out, runs counted for the machine (R29). **Open:** the sandbox is the kernel's, not a machine's; the service runs as root; the memory group counts most of a run's use, not all; standard library only; x86-64 and cgroup v1 only; D37 to D40, D45. Release gate G2 is not closed. | narrowed (A12, A15) | medium | WP 12; WP 13; DA12, DA15 open, untested | no |
| D20 | Baselining | Controls are not put to the record's checker: a check giving over 28 significant digits is accepted, then every run on it is UNKNOWN; a control rounding across its limit would leave the record unable to verify. | open | medium | DA2 open; WP 12 | no |
| D21 | Identifiers | The record builder prefers the journal's copy of a design under a 96-bit key; a collision (about 2 to the power 48 hashes, not tried) leaves a record unable to verify until rebuilt. The attempt identity is 64 bits: a collision between two designs needs about 2 to the power 32 hashes, by the birthday bound. The paper says a collision can cause only a refusal or a replay of the other design's verdict, not a false pass (white paper, section 6). Inspection only. | open | medium | DA2 open; WP 6; WP 12 | no |
| D22 | Untested: load | No load or stress test; nothing with more than two requests at once; nor two gate hosts writing one inbox at once (that no notice is overwritten rests on create-if-absent). Two threads writing an inbox's hash file at once: by reading the code only. **Since Amendments 13 and 15:** no baseline with hundreds or thousands of runs (R28 reads 15, F36 makes 25); not four runs each holding every file they can at once. | open | medium | DA2, DA6 untested; DF; WP 12; DA13, DA15 untested | no |
| D23 | Untested: coverage | Inputs are sampled: 872 numbers, 14 kinds of bad card, 8 of odd output, 4,765 texts, widths 80 to 200 columns, the toy card only for R17 and F20, four designs through the front door for F21, an empty design in process only. R16 and R19 call the tool directly; a restart and an unsearchable folder are simulated; the front door's card race is never made; the console's part of Amendment 6 and its threads are untested, and three wrong versions there are not caught. | open | medium | DA2 to DA6 untested; WP 12 | no |
| D24 | Evidence | One party wrote code and tests, with an AI coding assistant; reviews were inspections by it or its agents. Planted defects show tests can fail, not that they suffice; test and mutant counts are not an assurance measure. Tests of Amendments 3 to 5 first passed 22 of 43, 19 of 32 and 20 of 28 wrong repairs; the first plug-in's and the front door's tests were never reviewed for wrong repairs. The notice tests leave two rows free text, hold criteria to each other and not to the check, and hold the wording itself; whether a reader is misled is untested. **Since Amendment 7:** each amendment's code went through several forms and internal reviews by separate agents; the last form was in most cases read by no reviewer, and Amendment 12's sixth review was cut short, its findings weighed by the author alone (AM8 to AM15). Two reviews and three planted-defect passes each found something R28 could not see (AM14). | open | medium | DA2 to DA6; WP 12; AM8 to AM15 | no |
| D25 | Assistants | No host product or assistant has used the MCP tools. The trial is not an effectiveness trial: 24 runs without the record, 6 with it, the 6 through the first client; one vendor, one short job. The trial was not made again after the amendments. The demonstration was last run with the fourth amendment's repair in place (verify/sample/amended4/), not on this commit. No engineering team has been asked whether it has the problem. **Since the first edition:** "this commit" was `118e2a3`; no demonstration transcript in the repository is later than `verify/sample/amended4/`, so none was made with the sandbox. The trials' preparation was changed under Amendment 9 to give a reason for a second baseline; the trial was not run again. | open | medium | RV; RF; DA2 untested; WP 12; WP 13; AM9 | no |
| D26 | Worked case | Fixtures are small. The case's numbers were taken by a research agent from a manufacturer's public catalogue and recomputed by the author; no electrical engineer has reviewed them, and its 5 % limit is a compliance limit. No mechanical or civil case. | open | medium | RV section 5; WP 12; WP 13 | no |
| D27 | Gateway | v1.2.1 is not cleared. Nothing above its contract is composed with the model checks; one witness service; v1.2.2 not built; the author's rehearsal of the release failed at two install steps; no result from the outside assessment; G04 to G06 not started; staging scenarios run once each. Part 5 is not frozen; G1 is not passed. **Note for this edition:** G04 to G06 are the gateway's tests (WP 4, WP 13) and G1 its milestone, not the owner's release gates G1 to G6; still so on `1b132e2`. Since Amendments 10 and 11 the witness service carries additions (section 1). | open | medium | WP 4; WP 12; WP 13 | no |
| D28 | Test timing | F17 needs two failing runs to finish in the same second. On a slower or busier machine none of its six tries does, and it fails with no defect in the code, as its declaration foresees. Seen once, in the author's clean-clone try of 15 November, on a freshly restarted machine; run again alone, it passed. R16 tests the same repair in process. **Since Amendment 12:** in the official run F17 failed two of its three checks: in all six tries the two runs did not end in the same second, so the case it exists to test was never made; that run showed neither that a notice is written over another nor that it is not. That result stands. Cause (DIAG): F17 had about 0.1 s to spare; the sandbox adds about 0.07 s per run; every answer slowed by about 0.05 s per earlier run (D36). F17 passed in Amendment 13's official run, still resting on timing. **Since Amendment 14:** restated: the naming checked with no clock; the case made through the service by two jobs at once; it says COLLISION_HANDLED, COLLISION_MISHANDLED or PRECONDITION_NOT_MET. It said COLLISION_HANDLED in the official runs of 14 and 15. **Open:** the case through the service is still made by timing, with more margin (0.6 to 0.95 s into the second); on a slower machine F17 fails and says PRECONDITION_NOT_MET, a failure to test, never a pass. | restated (A14); open in part | medium | DA2 (note under F17); AM12; DIAG; AM13; AM14; DA14 open, untested | no |
| D29 | Front door | 3 and 3.0 are two designs: two official runs, two notices. | open | low | DA2 open; WP 12 | no |
| D30 | Sender's words | Up to 20 characters of each name or text, quoted, on lines marked "sent:", and numbers of up to 24 characters still reach a notice and the reason; below 80 columns a row can begin inside them. Ledger, database, journal, record files and `--json` output hold the design whole; answer data, status listings and the front door's own text show the caller its design or reason as held. | open | low | DA3 open; WP 12 | no |
| D31 | Notice wording | A CHECK_ERROR or CHECK_OUTPUT_INVALID notice says nothing of the check's files. The two banners order counts differently; counts are taken at revision; a card without them prints "?". The front door's own text gives a pass the reason "MET", a code; the no-card notice does not say which copy failed; a requirement's line break starts a row; the reason follows the card's parameter order; the print cuts long reasons at 300 characters. Two lines are not so: an unreadable data file is called missing, and mismatched key lists ask to restore an intact baseline. | open | low | DA3 to DA5 open; WP 12 | no |
| D32 | Engineer's tools | The consoles and the first client stop with a traceback for some unusable files; the file must be restored before a record is built. A fixed-word error keeps only its kind; a check that cannot start is answered in words that can hold a path; a check printing an exponent near a million gets a reason about a million characters long, untested end to end. | open | low | DA2 open; WP 12 | no |
| D33 | Earlier state | Runs interrupted before Amendment 2 stay interrupted, without notice; older notices and signed reasons keep their old words. Each repair needs the gate host restarted. | open | low | DA2, DA4, DA5 open; WP 12 | no |
| D34 | Tidiness | Starting the tool writes in `VERIFY_HOME`; the ledger's notice field names no folder; `inbox/unclaimed/` sits beside the inboxes; the hash file's name is written in two files; one F19 comment is stale. | open | low | DA6 open | no |
| D35 | Current-state text | `verify/README.md` lists tests R1 to R13 and calls the first client "the assistant's command"; `verify/README_FRONT.md` lists F1 to F16; the vault test file's opening note says thirteen tests. The test files, declarations and amendments are current. **Checked again on `1b132e2`:** still so (`verify/README.md` lines 29 and 40, `verify/README_FRONT.md` line 116, `tests/vault_tests.py` line 2), though both readmes now carry dated notes on Amendments 7 to 15. | open | low | found while writing this pack | no |
| D36 | Front door | Each answer took longer with every run already made on the baseline: about 0.05 s per earlier run; 0.49 s for the first of thirty, 1.97 s for the thirtieth; about 50 s projected at 1,000 runs, near the client's 60 s limit. Found 19 November by the F17 diagnostic. Cause: `attempts_of` opened five database connections per earlier run. **Repaired, Amendment 13:** one transaction on one connection, two connections a reading (R28, F36). **Open:** an answer still does work that grows with the runs (every row moved, the journal read and hashed); not measured at thousands of runs; F36 is a test of time and can be wrong both ways; the store still opens a connection for every call. | repaired (A13); open in part | medium | DIAG; AM13; DA13 open, untested | no |
| D37 | Sandbox | One run of a check could fill the machine's file table, through files held by memory mappings (2.6 million measured; the table 1,644,500). Found in Amendment 12's fourth review; met there by requiring `fs.file-max` of at least 2^40, a figure never measured, with the table raised by hand to the kernel's maximum. **Repaired differently, Amendment 15:** the floor worked out, twice what four runs can hold (33,617,920 on the test machine); a run below it is refused, closed, with the reasons; an operator's command (R29). **Open:** the setting is made by hand and lost at each start of the machine; the floor is 134,283,776 where `vm.max_map_count` is 1,048,576 (Ubuntu 24.04 as usually started); the count is an argument, not a measurement; a table at the floor removes a guard the kernel sets for itself. | repaired (A15); open in part | medium | DA12; AM15; DA15 open, untested | no |
| D38 | Sandbox | Runs at once were limited for each process, not for the machine: two processes that run checks could make eight. Found by the first internal review of Amendment 15. **Repaired, Amendment 15:** four locks in `/run/verify-sandbox`, taken by every service that sees the folder (R29). **Open:** services that do not share /run (containers on one kernel), or an older copy of the service, are not counted together; waiting for a place has no queue. | repaired (A15); open in part | medium | AM15; DA15 open, untested | no |
| D39 | Sandbox | **Open.** A run left frozen when its service is killed keeps its files until swept (ten minutes or more), while its place is free at once, so a fifth run can begin beside it. The margin of two covers one such; repeated kills would use it up. Found by the second internal review of Amendment 15. Not repaired. | open | medium | AM15; DA15 open, untested | no |
| D40 | Sandbox | **Open** (not new; found in review of Amendment 15). If `VERIFY_SANDBOX_CGROUP_ROOT` points at ordinary folders the run is made with no memory or process group, only its per-process limits; and the code that makes control groups can raise on an unreadable `/proc/self/cgroup` line instead of refusing (the gate's tool turns that into UNKNOWN). Both need control of the service's environment or an unusual kernel. Not repaired. | open | medium | AM15; DA15 open, untested | no |
| D41 | Test | R28 as declared in Amendment 13 could not see five kinds of fault in the reading it tests (found by an internal review; listed in DA14). Its official result under Amendment 13 stands. **Restated, Amendment 14.** **Open:** R28 changes the store by hand, so shows what the reading does with such rows, not that they can arise; its reference is the old reading, so a fault both share would not show; that it now sees everything is not claimed. | restated (A14); open in part | medium | AM14; DA14 open, untested | no |
| D42 | Process | Amendment 12's official commands were first given with an interpreter that could not import the cryptography library: no test ran, and stale output files were copied into the results files (deleted, unread as results, before commit). The two logs are kept. **Since Amendment 13:** each declaration names the project's virtual-environment interpreter and removes each output file before its command. | repaired (A13) | medium | AM12; DA13 | no |
| D43 | Record | `verify/AMENDMENT_12_2026-11-19.md` says "When F17 fails, each of its runs takes about a second" and "Why is still not known". Neither is so: no run took a second, and the cause is known (D28). **Corrected in Amendment 14's write-up**, not in place: historical files are not edited. | corrected (A14) | low | AM12; DIAG; AM14 | no |
| D44 | Test | **Open, unexplained.** `w4_service_crash`, a whole-gate test of the frozen gateway and not one of the two official commands, failed once in Amendment 15's development: in one of its 18 cases a retry after a kill timed out. It runs none of the code changed there. It passed in six runs after. Cause not found. | open | medium | AM15 | no |
| D45 | Sandbox | **Open.** cgroup v2 is not supported by the sandbox. A machine with cgroup v2 only is refused in words, and every run there is UNKNOWN; tested only with a file that reads as such a machine, not on a real one. Making the sandbox use cgroup v2 would be a separate amendment. | open | medium | DA12 open; AM15; DA15 open, untested | no |
| D46 | Courier | **Open.** One run the courier cannot read (an answer over 32 MiB, a dropped connection) stops each pass before later runs are read, and runs are read in the order of their names: one such run named to sort first hides every run after it. The mailbox gets one COURIER_BLOCKED notice, worded as the witness not answering, then nothing: two failed runs were never noticed in six passes (`tests/diag_notify/exp1_poison.py`). A dishonest service holding only its database role could cause it, by storing a very large result. Shown by experiment with a stand-in witness; not shown end to end through the real witness and database. Weighed high by the reviewer. Not repaired. | open | high | DN finding 1 | no (see notes) |
| D47 | Courier | **Open.** A run whose name the witness's reading refuses (over 512 characters, or a control character) is never noticed; the courier sends COURIER_BLOCKED once, and after that first alarm no further alarm is raised for later such runs (`exp2_oddaid.py`). R26's second check takes the refusal as right. Whether the gate host admits such a name was not looked at. Not repaired. | open | medium | DN finding 3 | no |
| D48 | Courier | **Open.** A run name the service chooses is put raw into the plain words of a notice the courier signs: a name with line breaks made a notice read as if the courier said no action is needed, in a notice that ends "The verification service did not write it" (`exp4_words.py`). Amendments 3 and 4 repaired this kind of thing for the service's own notices, not here. Not repaired. | open | medium | DN finding 4 | no |
| D49 | Courier | **Open.** The courier takes a gate-signed result's verdict as given and does not derive it again from the result's own numbers, as the record's sixth check does: a signed PASS whose numbers miss the limit gets no notice and is marked done. (Whoever holds the gate's key can sign a false PASS in any case, as Amendment 11 declares.) Not repaired. | open | medium | DN finding 2 | no |
| D50 | Courier; wording | **Open.** The courier watches a fixed list of budgets: a new baseline has no courier notices, and nothing says so; the witness has no reading that lists budgets. Also four places in code and help text say "the engineer's mailbox" or "runs under the engineer's account" (`mailbox_service.py`, `deploy.py`, `check_record.py` twice), where in the demonstration the deployment makes the mailbox key and runs it under the service's account. Not repaired. | open | medium | DN finding 5; "A receipt and a person" | no |

#### Notes on the grading in this edition

- **D1, D2 from high to medium, and from yes to no.** Since Amendments 7 and 8 the journal refuses before anything is
  run, the engineer is told of a refusal, and a verdict is returned whatever happens to its notice. What is left is
  availability (D1) or needs both places to be unwritable and the courier not running (D2), so neither hides a failure
  in a plausible deployment, and step 3 of revision 15 does not name the journal. This is the author's judgement under
  the rule.
- **D3 and D7 from high to medium, still yes.** The faults as first written no longer occur in the tests, but step 3
  of revision 15 names the console and the gate under separate accounts, which has never been tried on real accounts,
  and the witness's statement of the latest sequence number, which is now built while the witness is still held by the
  same party. They stay "yes" under the rule that step 3 names them. Revision 15 was written before Amendment 10; if a
  later revision of step 3 drops D7, it would be "no" under the same rule.
- **D4 repaired;** its severity is the one it had when open.
- **New rows.** D36 to D40 and D44, D45 are graded medium: none hides a failure or passes a wrong verdict, but each
  weakens the evidence or depends on an unusual set-up. D45 makes every run UNKNOWN on a machine with cgroup v2 only,
  which is safe and stops the work; a pilot must be run on a machine that meets the six prerequisites. D42 is medium
  because a results file nearly held outputs no test of the run had made; it was caught before commit. D43 is low, as
  wording.
- **D46 to D50** (the fact sheet's addendum, rows l to p) come from one internal review by a separate agent, recorded
  on a diagnostic branch with no official run; the author re-ran the three experiments and re-read the lines behind
  D46 only. D46 is graded high, as the reviewer weighed it: a failure can fail to reach the engineer by the second
  path. It is "no" for a pilot because it needs a dishonest service, which a trial would not meet by mistake or by a
  caller, and step 3 does not name it; a reviewer might grade it "yes". D47 to D50 are medium: each needs the service
  to choose odd names or weakens what the courier shows, and the service's own notices still go.
- The fact sheet's row for F17's test defect is merged into D28, which already held F17's timing, so that there is not
  a second row; D36 onward are numbered in the sheet's order without it.

## Part B. Status history since the second edition

As of 21 November 2026. No row's status, severity or "blocks a pilot?" is changed.

| Rows | What has happened since 20 November | Status |
|---|---|---|
| D46 to D50 | Amendment 16 was opened to answer them (`verify/AMEND16_PROPERTY_2026-11-20.md`). Eight forms of the courier were built on `verification-amendment-16`; each failed an internal review. The eighth, `e25a297`, is INCOMPLETE, rejected at internal review and undeclared. A threat-model addendum was accepted by the owner as a design baseline at `0da1a85e`, not as an implementation or a security declaration | open, as in Part A. Nothing in `e25a297` counts as a repair |
| D12, and release gate G5 | unchanged; the diagnostics of 21 November bear on them (Part C) | as in Part A |
| every other row | no work recorded | as in Part A |

## Part C. Findings outside the courier from the diagnostics of Amendment 16 (separate from D1 to D50 and from Part D)

Found on 21 November 2026 on real deployments built from `e25a297` over fresh databases. They are in the substrate,
the deployment and beside the frozen gateway, not in the courier. They are numbered apart (S-1 to S-4) so that the
D-numbers of the issued register are not disturbed; whether they take D-numbers in a later edition is the owner's.
Evidence is on the branch `diagnostic-amend16-alarm-2026-11-21`. All of it is the work of the code's own side; no
planted-defect pass was made on the harnesses. None is repaired. The frozen gateway is unchanged.

### S-1. Silent replacement of a verdict by a second gate-signed digest

- **What happens.** After the gate host has signed FAIL for a run and the witness has recorded that report, the service
  can withhold the result (or store one marked 'unknown'), have a second report recorded for the same run over a PASS
  result, and store the PASS. The witness records the second report as a duplicate decision with its report. The
  courier and the record's checker believe a stored result that matches any recorded digest. No notice is made, and the
  record verifies.
- **Where.** `plea_gateway/witness.py` 79-87 and `plea_gateway/store.py` 400-401, 773-788, 837-838 (frozen gateway);
  `verify/check_record.py` 188-203 (the courier and the checker).
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 3 (steps 3, 3b, 3c of
  `tests/diag_amend16_powers/commit_check.py`); `verify/DIAGNOSTIC_AMEND16_VISIBILITY_2026-11-21.md` (V1 to V5).
  Commits `1313dc9`, `1fc9046`.
- **Reproduction conditions.** The service holds the gate's key, the client's certificate and the database role
  `plea_local` (all three are in the locked table of powers). The run's result has not yet been stored as a value. With
  the courier's default waiting time, the replacement is made before that time has passed. Reproduce with
  `DIAG_DB=<fresh database> python tests/diag_amend16_powers/commit_check.py SRC OUT`, steps 3 to 3c, and
  `visibility_check.py`, V1 to V3.
- **What limits it.** A FAIL already stored as a value stays (by test). Both reports stay readable through the witness's
  existing reading, so the conflict can be detected without a change to the gateway; nothing detects it at `e25a297`.
  Detection shows that two results were signed, not which is true.
- **Affected trust boundaries.** Service to witness (what the witness records for a run); witness to courier and witness
  to record (what a reader concludes from the reports); gate-key custody.
- **Standing.** Open. An unmet requirement of Amendment 16 (UM6 b). It is the one finding of these diagnostics that
  turns a signed FAIL into silence.
- **Remediation status.** None made. Detection is specified in the Step 2 design note and is not implemented. The
  frozen gateway stays unchanged by the owner's decision, so refusing a second report at the witness is not in hand.

### S-2. Plaintext database role passwords

- **What happens.** The passwords of all four database roles, the owner's included, are literal text in the
  repository. Which role a party holds is a matter of which line of configuration it uses, not of what it can do.
- **Where.** 23 places listed in `tests/diag_amend16_powers/results_2026-11-21/roles.txt` (among them `README.md`,
  `verify/deploy.py`, `verify/verify_ctl.py`, `tests/common.py`).
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 1; the schema of every diagnostic database was
  installed with the owner's password from the README; with it a recorded gate report was deleted
  (`visibility_check.py`, V7).
- **Reproduction conditions.** Read access to the repository and network access to the database server. No other
  condition.
- **Affected trust boundaries.** Service to database owner; service to witness (the witness's role); every boundary
  the database's grants are meant to keep.
- **Standing.** Open. **A deployment-security blocker**, by the owner's decision of 21 November: it must be resolved
  before any claim that a deployment complies. Precondition DP1 of the addendum is not satisfied. It is an outstanding
  security defect, not an acceptable implementation of credential separation.
- **Remediation status.** None made. Tracked outside the Step 2 task. No credential or deployment configuration is
  edited here.

### S-3. Connection exhaustion affecting the witness

- **What happens.** No database role has a connection limit, and the server has no statement or idle timeout. The
  service's role took every free connection (97 of 100), after which every reading of the witness failed and the
  courier was blocked, for as long as the connections were held.
- **Where.** Database server configuration and role settings (`roles.txt`, sections 1 and 3).
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 4 (step 6a of `commit_check.py`). Commit
  `1313dc9`.
- **Reproduction conditions.** The role `plea_local` and network access to the database server shared with the witness.
- **Affected trust boundaries.** Service to witness, through the shared database server (availability).
- **Standing.** Open, as an operational risk (residual risk R1 of the addendum). It can keep a budget from being read;
  it cannot make an unread budget look read.
- **Remediation status.** None made. Not prevented; carried as a residual risk.

### S-4. Quadratic growth of a chain read from its start

- **What happens.** Every decision the witness gives carries the state of every run of its budget, so a decision grew
  from 3.8 KB to 127 KB over 996 runs, and the whole chain of that budget was 508 MB (126 pages, 37 s). A courier that
  is new, or has lost its state, pays this; the time a pass has for asking does not bound it.
- **Where.** The store's record of a decision (frozen gateway); the witness's GET /chain.
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 6 (`measure2.py chain`). Commit `1313dc9`.
- **Reproduction conditions.** A budget of about 1000 runs made through the client; read with
  `measure2.py chain SRC OUT ROOT`.
- **Affected trust boundaries.** Witness to courier (the cost of the first reading; recovery after loss of the
  courier's state).
- **Standing.** Open, as an operational risk and a stated limitation of the measured envelope.
- **Remediation status.** None made. A change would touch the frozen gateway.

### Deployment-security blockers

By the owner's decision of 21 November these must be resolved before any claim that a deployment complies. They are
tracked here and outside the Step 2 task. Nothing is edited for them.

| Blocker | What is so today | Evidence |
|---|---|---|
| B-1. Database credentials exposed (S-2) | every role's password is in the repository | `roles.txt`; V7 |
| B-2. No separation of operating-system accounts | one account runs the witness, the gate host, the mailbox, the courier and the client; that account stopped and continued the witness | `verify/deploy.py` 11-16; step 6b of `commit_check.py` |
| B-3. Custody of the gate's key | the property file takes the service to hold the gate's key; with it a report can be forged before the witness sees anything, which nothing in the notification path can detect | property file line 21; V5 |

## Part D. The eight confirmed defects of the courier at `e25a297` (kept as they are)

`e25a297` is INCOMPLETE, rejected at internal review and undeclared, and stays so. Its findings are not rewritten or
erased. The eight are recorded in full in section 9.1 of `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at
`0da1a85e`. D-b and D-c are current breaches of P5 (the courier's signed words must be its own true sentences). These
letters are not the D-numbers of Part A.

| Id | In short | Standing |
|---|---|---|
| D-a | the alarm's count is cleared by a pass that put runs off; no alarm in the test of 4500 s | open |
| D-b | false provenance sentence ("from what the witness gave it, read to decision 0"); a current breach of P5 | open |
| D-c | four notices carry a headline with no explanation; the UNVERIFIED headline was signed false of its run; a current breach of P5 | open |
| D-d | the statement of coverage is made with runs asked for and not read, and promises the future | open |
| D-e | one clock value for a whole pass over all budgets | open |
| D-f | "complete" has several meanings | open |
| D-g | an older failed run not noticed while the witness stops at a new run in every pass | open |
| D-h | a run that never reaches a final phase is asked for at every pass for ever (cost) | open |

Reported by the eighth internal review of `e25a297` and not re-confirmed: F1, F2, F4, F5. Their disposition against
the Step 2 model is in `verify/STEP2_DESIGN_AMEND16_2026-11-21.md`, section 8.

## Part E. Findings of the design gate of 21 November 2026 (added; Parts A to D are unchanged)

Found in the final design gate before any Step 3, on real deployments built from the unchanged `e25a297` over fresh
databases, by the author's tests and by the independent reviewer's. The note is
`verify/DESIGN_GATE_AMEND16_2026-11-21.md`; the evidence is in `tests/diag_amend16_gate/`; the reviewer's reports are in
`verify/DESIGN_GATE_REVIEW_AMEND16_2026-11-21.md`. They are numbered on from Part C. None is repaired. The frozen
gateway is unchanged. S-1 to S-4, B-1 to B-3 and Part D stand as they are.

### S-5. A verdict report recorded with a RELEASE decision, or before its run starts, is believed

- **What happens.** The witness keeps whatever evidence is sent with a RELEASE or a RECONCILE, whatever it decides, and
  its reading of a run gives all of it back. `check_record.run_outcome` counts any authentic EFFECT report of the
  run's scope, wherever it sits. So a gate-signed report over a PASS result can be put on record with a RELEASE (after
  the run is final, before its START, or before the attempt exists) or with a RECONCILE before the run's nonce is in
  the chain. With the PASS result then stored, the courier reads PASS and makes no notice for a run whose gate host
  signed FAIL.
- **Where.** `plea_gateway/store.py` 762-788 (frozen gateway); `verify/check_record.py` 188-203; `verify/courier.py`
  (the courier does not look at which decision a report sits at).
- **Evidence.** `tests/diag_amend16_gate/gate_release.py`, steps C1 to C6 (two real runs, X and Y: the courier made no
  notice); the reviewer's `review/rv_conflict.py`, R1 and R3.
- **Reproduction conditions.** As S-1: the gate's key, the client's certificate and the database role `plea_local`.
  `DIAG_DB=<fresh database> python tests/diag_amend16_gate/gate_release.py SRC OUT`.
- **What limits it.** The record's checker fails a record whose report sits at a RELEASE (its sixth check), while
  giving the run the outcome PASS. A report sent with a RECONCILE sits at a reconcile decision; no record of that case
  with a realistic forged result was made. Every such report comes with a decision of the chain naming the run, so a
  reader that follows the chain can see that something was recorded; nothing at `e25a297` reads the run again.
- **Affected trust boundaries.** As S-1.
- **Standing.** Open. A second route to S-1.
- **Remediation status.** None made. The design gate's rule (every gate-signed report of a run counts towards a
  conflict; only the report at the recorded verdict is believed) is specified, not reviewed in its corrected form, and
  not implemented.

### S-6. The size of a gate report is not bounded

- **What happens.** The store and the witness set no limit on a run's nonce or on a report's result digest short of
  the database's own limits, nor on the number of reports for one run. A report of 70,448 bytes (a nonce of 70,000
  characters) was recorded as a run's verdict; a report of 200,435 bytes (a result digest of 200,000 characters) was
  recorded as a repeat; one run's answer was made 5,002,287 bytes with five reports. Each report was authentic for its
  scope.
- **Where.** `plea_gateway/store.py` (START and evidence take any length); `plea_gateway/witness_service.py` 157 (any
  length of request); `plea_gateway/evidence.py` (the digest is a free string under the signature).
- **Evidence.** `tests/diag_amend16_gate/gate_sizes.py`, D1; the reviewer's `review/rv_phase2.py`, P2 and P3.
- **Reproduction conditions.** The gate's key and the database role `plea_local`.
- **What follows.** A notice in the mailbox's 64 KiB cannot always carry two reports whole, or one. Every reader of a
  run's answer must expect megabytes. A service can make each reading of a budget as slow as it likes, and so keep it
  NOT COVERED, which is a loss of liveness and not of safety.
- **Standing.** Open. An operational risk and a constraint on any design. A bound would be a change to the frozen
  gateway and is not proposed.
- **Remediation status.** None made.

### S-7. The courier does not read the reports of runs in some phases

- **What happens.** The courier of `e25a297` asks the witness for a run's reports only when the run is EFFECT or
  CONSUMED. For a run that is NO_EFFECT, INDETERMINATE or RELEASED it takes the chain's word and reads nothing. And
  for an EFFECT run, `run_outcome` ignores a NO_EFFECT report. So a second, conflicting report on such a run is never
  examined.
- **Where.** `verify/courier.py` 403; `verify/check_record.py` 196-199.
- **Evidence.** Code reading; the reviewer's R1 (a NO_EFFECT report on an EFFECT run, kept and ignored) and P5 (a
  released run carrying a gate-signed EFFECT report).
- **Standing.** Open. Found by the independent reviewer.
- **Remediation status.** None made.

### Observations of the design gate, not entered as defects

- The store answers a refused replacement of a stored result as success, and stores nothing
  (`tests/diag_amend16_gate/gate_result_store.py`).
- The witness gives a checkpoint, with any nonce, to the governor's certificate (`gate_token.py`, A8).
- The mailbox does not check a notice's words: a notice of an outcome it knows is taken with any text up to its limit
  (`gate_sizes.py`, D2).
- The record's sixth check compares reports with one gate key, where the courier and the witness take a list
  (`verify/check_record.py` 854; code reading by the reviewer).
- The record's checker appears to fail any record that carries a fence report (the reviewer's P5; not investigated).
- The baseline's receipt-counted freshness was broken on the real mailbox: a statement of coverage signed three hours
  earlier was receipted with the current time (the reviewer's R5). This is the fault the erratum of 21 November
  already corrects in the design; the mailbox itself is unchanged.

## Part F. The specification round of 21 November 2026 (added; Parts A to E are unchanged)

No code was changed and no defect of Parts A to E is closed by this round. The round produced a specification for a
Step 3 (`verify/STEP3_SPECIFICATION_AMEND16_2026-11-21.md`, version 6), eleven reports by three separate agents
(`verify/STEP3_SPEC_REVIEW_AMEND16_2026-11-21.md`, internal review and separately authored verification, not
independent validation), four bounded models and 200 prewritten acceptance tests (`tests/diag_amend16_spec/`). The
summary and the NO-GO recommendation are in `verify/STEP3_SPEC_ROUND_AMEND16_2026-11-21.md`.

- **About the code at `e25a297`.** S-5 and S-1, as demonstrated, need the gate's signing key (CAP-KEY). With the
  database role alone, no replay of a genuine PASS report made a failing run read PASS in the tests made; that no
  such path exists is not shown. The acceptance tests run against the unchanged `e25a297` give 124 FAIL, 52 NOT
  IMPLEMENTED and 24 PASS: a diagnostic result on one machine, not an official run.
- **Defects of the specification.** 94 findings were made against its six versions; 70 were corrected in the text; 24
  are open against version 6: one HIGH (T1, no wire format is fixed), eleven MEDIUM (M37, T2 to T11) and twelve LOW.
- **Failures of proposed repairs.** Version 2's anchor rule failed when the mailbox lost its record (M20). Version
  5's repair of it was broken by the model in 16 steps (M30). Version 6's repair holds in the model, and its wording
  claims too much for a courier restored from an older copy (M37).
- **Blockers.** B-1, B-2 and B-3 are unchanged and open.

---

## Part G. The maintained register: status log (append-only, from 22 November 2026)

**Where this file lives now.** By the owner's directive of 22 November 2026, this is the one maintained register. It is
on branch `hardening/prepentest-2026-11-22`. Everything above this Part is `verify/DEFECT_REGISTER.md` from
`d208f6e` (branch `diagnostic-amend16-alarm-2026-11-21`), copied byte for byte. Its SHA-256 there is `331d58fe6d7d2c08f0befa81c3411f7662b7482e03d9a70d28c4dc8054ec1e3f`. That
copy on the diagnostic branch is not changed.

**Rules for this Part.**
- Entries are only added. None is edited or removed.
- Every entry keeps the original identifier (D, S, B, G-n, T, M, F) and its source.
- A status change names the commit, the test evidence, who reviewed it, and what remains.
- The status words are those of the plan: *planned*, *implemented*, *internally tested*, *independently validated*.
- "Internally tested" means declared official runs made by the author or by agents the author instructs. A row is never
  closed by this file. Closing is the owner's act.

### G1. 22 November 2026: findings recorded while planning (`plan/GOVERNANCE_NOTE_2026-11-22.md`, commit `2a1804c`)

- **G-1 (low).** Row D35 cites `tests/vault_tests.py` as checked on `1b132e2`. That file is not in that tree; it is on
  `holdout-vault-demo`. The rest of the row holds.
- **G-2 (low).** D27's "two install steps" are not named in any record found so far. The owner directs that they be
  identified from their source records, not inferred (Stage D).
- **Process violation (VP-6).** The version 6 model's SAF-10 predicate was changed after a failed run without its source
  being kept (governance note, section 3).
