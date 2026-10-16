# QA review of the audit pack

_Pack v3, risk register revision 1; checks run 2026-10-16T02:16:05.
The pack describes risk indicators to investigate, not findings about the
council, any department or any supplier._

## Results

```text
QA checks on pack v3, run 2026-10-16T02:16:05

| Check | Result | Items checked | Failures | Note |
| --- | --- | --- | --- | --- |
| check_quotes | PASS | 19 | 0 | 62 rules verified against the PDF; 18 register excerpts |
| check_numbers | PASS | 63 | 0 | 14 sample file(s) indexed |
| check_trace | PASS | 92 | 0 | 8 in scope, 1 out; 22 controls, 20 tests; 36 rules cited, 26 not tested |
| check_samples | PASS | 1078 | 0 | 1078 sampled transaction(s) in 14 file(s); 0 row id(s) in audit-program.md |

VERDICT: READY FOR SIGN-OFF
```

## Verdict

**READY FOR SIGN-OFF**

## Team record

- Planner: "PLANNER DONE v3"; "Challenges: #1–#7 accepted, #8 for the auditor, #9 accepted."; "For the auditor: #8 R-07 rating vs AUD-12 uplift."
- Challenger: "CHALLENGER DONE v3"; "Challenges 9 (round 1: 8, round 2: 1): resolved 8, declined 0, for the auditor 1."; "For the auditor: #8 [rating] R-07." (relayed word for word by the lead); items for the auditor are in `outputs/challenges.md` under "For the auditor".
- QA history:
  - v1: check_quotes PASS · check_numbers PASS · check_trace PASS · check_samples PASS
  - v2: check_quotes PASS · check_numbers PASS · check_trace FAIL (7, challenges.md items pending with the challenger) · check_samples PASS
  - v3: check_quotes PASS · check_numbers PASS · check_trace FAIL (1, challenges.md item pending with the challenger) · check_samples PASS
  - v3 final: check_quotes PASS · check_numbers PASS · check_trace PASS · check_samples PASS
- Checks unchanged during the run: yes (hash comparison: all 8 files in `scripts/checks/` OK).

## Auditor sign-off

I have reviewed the planning memo, the risk-control matrix, the audit
program, the sample files, the challenges and these QA results.

| | |
| --- | --- |
| Auditor | Allen Cao |
| Decision (SIGNED OFF / RETURNED) | SIGNED OFF |
| Date | 2026-10-16 |
| Comments | Challenge #8 not accepted as a repeat finding, because AUD-12 (Personal Budgets) covers a different process from R-07, so R-07 stays at L2. Statutory thresholds and the two council names missed by cleaning are noted for follow-up. |
