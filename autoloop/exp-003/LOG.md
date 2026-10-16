# exp-003 execution log

1. Confirmed main at v2.4.0 / 3413381, with only pre-existing untracked
   soccer-practice-arena/. Created the requested branch from main.
2. Read exp-002, the fixed scorer, policy text and fingerprint implementation.
   Recorded the corpus, canary, 1202-test baseline and governance projection.
3. Authored 8 positive / 59 negative pairs and the new public-service test
   before any product change. All 8 positives reproduced missing recall.
4. Transcribed 26 records from WHO ATC, with human-review notice and references.
   Initial whole-course-only matcher scored 67/67, no false pending. Full suite
   rejected its new helper import. Moved the stdlib loader into note_context
   without changing the frozen allowlist; 1278 passed / 10 xfailed.
5. Added a second paired batch during review: 3 other drug positives and
   4 incomplete-course linkage negatives. All four negatives falsely passed
   the initial candidate. Reverted both product modules immediately to main;
   saved unsafe source, failing scores, and reverted scores. The reverted
   engine still had one inherited false pass on the mixed class/drug challenge.
6. Revised the candidate so eligible unresolved drug context cannot disappear
   alongside another course. No case labels or assertions were changed.
   All 74 pairs plus 9 integrity tests pass. Replayed main in memory to measure
   expanded baseline; 49/74 exact, one false pending, 11 missed positives.
7. Final gates: 74/74 authored, zero false pending; corpus 52/52 with identical
   proposals/fingerprints; exp-002 64/69 with unchanged five misses and zero
   false pending. Governance unchanged. make test: 1285 passed / 10 xfailed;
   make lint green. Wrote full review table, limitations and scope audit.

No generators, clock/monitor changes, existing test/assertion changes, tags,
PRs, or main mutation. Optional recall families were skipped to prioritize the
required table and linkage safety. All file access was scoped to this repository;
WHO web pages were used for authoring only, never evaluation.
