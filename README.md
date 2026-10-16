# Procurement Audit Planning Agent (West Berkshire Council)

## Overview

This project is an agentic system that plans an internal audit of procurement
for West Berkshire Council from the council's public data. It turns the
Contract Procedure Rules into testable rules and analyses the full spend
population against them. It then folds in past audit history and rates the
risks on the council's own likelihood × impact method. Finally it produces a
cross-checked audit planning pack that a human auditor approves and signs off.

Four design principles apply throughout:

- **The LLM reads and judges; Python computes every number.** Agents write
  judgments with citations and `{{$.path}}` placeholders. Scripts fill in every
  figure, score and sample.
- **Everything is traceable.** Rule quotes are verified against the PDF, every
  metric is named and reproducible, and every rating cites a rule, a metric or
  a prior audit.
- **Indicators, not accusations.** Outputs describe risk indicators to
  investigate, never wrongdoing by the council, a department or a supplier.
- **Missing or malformed input means stop and report.** Nothing is fabricated.

Inputs (all public, read-only, in `data/`): the Contract Procedure Rules PDF,
three monthly "Expenditure over £500" workbooks, a Contracts Finder notice
export, and Governance Committee papers. The full specification is in
`CLAUDE.md`.

## Skills I created

| Skill | Reads | Writes | Checker |
| --- | --- | --- | --- |
| `extract-rules` (invoked by the human) | `data/contract-rules.pdf` | `outputs/rules.json`: one entry per testable rule, with clause, thresholds, required action, approver and a verbatim quote; untestable clauses in an `excluded` list with a reason | `.claude/skills/extract-rules/verify_quotes.py`: every quote is in the PDF on its stated page; structure, ids and parameters are well formed |
| `risk-assessment` (loaded by risk-assessor) | `rules.json`, `analytics.json`, `history.json`, `auditor-comments.md` | The agent writes `outputs/risk-ratings.json` (judgments and citations only); the builder writes `risk-register.md`, `auditor-comments.md` and `risk-register.state.json` | `build_register.py --strict`: resolves every citation, fills every figure, scores from the council matrix and enforces revision rules after the auditor's decisions. Tested by `test_build_register.py` |
| `audit-program` (loaded by planner) | Register, `auditor-comments.md`, `risk-ratings.json`, `rules.json`, `analytics.json`, `analytics-full/` | The agent writes `outputs/audit-plan.json`; the builder writes `planning-memo.md`, `risk-control-matrix.md`, `audit-program.md`, `samples/T-*.csv` and `pack-figures.json` | `build_pack.py`: approval gate (`--gate`), citation and placeholder resolution, deterministic sampling sized by risk score (`sampling.json`), every sampled transaction checked against `spend_clean.csv`, and every control and rule accounted for. Tested by `test_build_pack.py` |

## Agents I created

### Sub-agents

| Agent | Role | Output | Checker |
| --- | --- | --- | --- |
| `spend-analyst` | Writes and runs Python (`scripts/`) that cleans the spend workbooks, parses the contract notices and runs seven tests against the thresholds in `rules.json` | `outputs/analytics.json`; full flagged lists with row ids in `outputs/analytics-full/` | `scripts/self_check.py`: reopens the raw workbooks, reconciles rows and £, re-derives one item per test, resolves every row id, and scans for hardcoded thresholds and banned words |
| `findings-analyst` | Reads the committee papers: audit opinions, follow-ups, risk themes and the council's risk scoring method | `outputs/history.json`, every item sourced to file, page and a copy-exact quote | `scripts/verify_history.py` (tested by `test_verify_history.py` on good and bad fixtures) |
| `risk-assessor` | Rates risks following the risk-assessment skill. It recommends; the auditor decides | `outputs/risk-ratings.json` → rendered register and decision template | `build_register.py --strict` |

### Agent team (Phase 3)

| Teammate | Role | Output |
| --- | --- | --- |
| `planner` | Runs the gate and writes the plan for the approved risks only. Rebuilds after challenges and QA failures, and never re-rates or changes scope | `outputs/audit-plan.json`, rendered by `build_pack.py` into the pack |
| `challenger` | Raises cited challenges in two rounds (at most eight, then four). Rating and scope challenges go to the auditor; sample, control, test and coverage challenges go to the planner. It verifies accepted changes and closes every row | `outputs/challenges.md` |
| `qa-reviewer` | Runs `scripts/checks/run_checks.py` on every pack version and reports failures to their owner. After both teammates finish it does the final run | `outputs/review.md`: results as printed, verdict, auditor sign-off block |

The QA checks in `scripts/checks/` are:

- `check_quotes.py`: the rule quotes against the PDF and the register.
- `check_numbers.py`: every figure in the pack is a value in the outputs.
- `check_trace.py`: rule → risk → control → test, High risks, and the challenge record.
- `check_samples.py`: every sampled transaction is in `spend_clean.csv` and at its row in the council workbook.

They are tested by `test_checks.py`, which plants faults in a fixture pack.

## How they work together

```
 data/contract-rules.pdf
          │
 (1) /extract-rules  ── SKILL, run by the human ──►  rules.json
          │
          ├──────────────────────────────┐
 (2) spend-analyst  (sub-agent)    findings-analyst  (sub-agent)
     spend workbooks + notices       committee papers
          │                              │
     analytics.json                 history.json
          └──────────────┬───────────────┘
 (3) risk-assessor  (sub-agent + risk-assessment skill)
          │  build_register.py
     risk-register.md + auditor-comments.md
          │
 (4) HUMAN GATE: auditor records APPROVE / AMEND / REJECT per risk
          │  risk-assessor builds the revision that applies them
          │
 (5) AGENT TEAM  (gate: build_pack.py --gate)
     planner ──PACK READY vN──► challenger ──CHALLENGE #n──► planner
        │                       qa-reviewer ──QA vN: PASS/FAIL──► planner
        │  build_pack.py → memo, matrix, program, samples
        └─ PLANNER DONE · CHALLENGER DONE · QA DONE → review.md
          │
 (6) HUMAN GATE: auditor signs off review.md
```

## Key results from my run

All figures are taken from the files named.

**Rules** (`rules.json`): 62 testable rules and 106 excluded clauses, each
with a reason. One rule is flagged anti-avoidance (CPR-07, clause 6.16). The
four statutory-threshold parameters are left null pending the auditor's figure.

**Spend analytics** (`analytics.json`; `self_check` status PASS):

- **Spend window:** 2026-05-01 to 2026-07-31 (3 months, annualisation factor 4).
- **Cleaning:** 10,607 rows read. 2,084 rows were excluded: 2,015 redacted suppliers, 46 public bodies, and 23 pension or statutory payments. That leaves 8,523 rows tested, worth £66,252,291.98.
- **Contract notices:** 141 council notices kept and 9 dropped; 62 were live in the spend window.

| Test | Result |
| --- | --- |
| threshold_clustering | 367 flagged payments |
| split_purchases | 405 groups (119 in general procurement) |
| off_contract | 673 suppliers above the notice tier; 40 exact-match a notice |
| duplicates | 4,245 pairs; 1,502 with different timestamps |
| expired_notice_spend | 8 of 46 exact-matched suppliers flagged |
| spend_vs_award | 7 of 18 eligible suppliers flagged |
| high_value_suppliers | 673 suppliers enter the three-quotes tier |

**History** (`history.json`):

- 4 source documents read.
- 16 completed audits, 3 follow-ups, 1 advisory review and 24 risk themes.
- The council's scoring method was extracted from the Risk Management Strategy.
- 10 discrepancies and 11 gaps recorded.

**Risk register** (`risk-register.md`, revision 1): 9 risks rated on the
council matrix. The auditor approved 7, amended 1 (R-06 impact lowered to 4)
and rejected 1 (R-08, grants).

| Risk | Score | Band |
| --- | --- | --- |
| R-06 Duplicate payments | 12 | Medium - High |
| R-01 Split purchases | 9 | Medium - High |
| R-03 Spend above the notice tier with no notice | 9 | Medium - High |
| R-05 Spend beyond the awarded value | 9 | Medium - High |
| R-04 Spend after a notice ended | 6 | Moderate |
| R-09 Waivers and exceptions | 6 | Moderate |
| R-08 Grants (out of scope) | 6 | Moderate |
| R-02 Order values just under a tier | 4 | Moderate |
| R-07 Care and education placements | 4 | Moderate |

**Audit pack** (`pack-figures.json`, pack v3):

- 8 risks in scope.
- 22 expected controls and 20 tests.
- 14 sample files: 206 sample units and 1,078 transactions, worth £19,675,846.65.
- 16 items to request from the council (PBC items).
- 36 of 62 rules cited; 26 listed as not tested, each with a reason.

**Challenges** (`challenges.md`): 9 challenges (8 in round 1, 1 in round 2).
Eight were resolved and verified in the pack, none was declined, and one (#8,
the R-07 rating) went to the auditor.

**QA** (`review.md`): all four checks passed on the final run, with verdict
READY FOR SIGN-OFF. The pack was signed off by the auditor on 2026-10-16.
Challenge #8 was not accepted as a repeat finding, so R-07 stays at L2.

## Confirmation

I completed all 27 steps of the guide at
https://procurement-audit-planner.vercel.app/. My run differed from the guide
in two ways:

- **Revision 1 instead of revision 2.** I recorded all 9 auditor decisions in
  Lesson 3, so a single revision applied them all and the register finished at
  revision 1.
- **Two usage-limit pauses during the agent-team run.** The team was resumed
  after each pause and completed both challenge rounds and the final QA run.
