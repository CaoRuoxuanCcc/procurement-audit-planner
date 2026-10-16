---
name: audit-program
description: Turn the auditor-approved risks into the audit planning pack. The planner writes its judgments (expected controls citing rules, test steps citing a rule or metric, sample recipes over analytics-full/, PBC items, memo text with {{$.path}} placeholders) to outputs/audit-plan.json; build_pack.py checks the approval gate, rates each risk from the council matrix, draws every sample deterministically, verifies each sampled transaction and renders planning-memo.md, risk-control-matrix.md and audit-program.md, the sample files and pack-figures.json.
---

# audit-program

You judge; the builder computes. You write **`outputs/audit-plan.json`**:
for each approved risk, what control should exist, how to test it, which
flagged items to pull and what to ask the client for. You never type a number.
`build_pack.py` (next to this file) works out the approved scope, re-reads every
rating from the council matrix, sizes and draws every sample, checks each
sampled transaction against the cleaned spend data, checks traceability and
renders the pack.

Governing principles (CLAUDE.md): LLM reads and judges, Python computes every
number; everything traceable; indicators, not accusations; context discipline;
missing or malformed input means stop and report.

## Inputs and outputs

| | Path |
| --- | --- |
| In | `outputs/risk-register.md`, `outputs/risk-ratings.json`, `outputs/auditor-comments.md`, `outputs/rules.json`, `outputs/analytics.json`, `outputs/analytics-full/*.csv`, `outputs/history.json` |
| Sample sizes | `.claude/skills/audit-program/sampling.json`: read it, never edit it (the auditor's to change) |
| You write | `outputs/audit-plan.json` |
| Builder writes | `outputs/planning-memo.md`, `outputs/risk-control-matrix.md`, `outputs/audit-program.md`, `outputs/samples/T-*.csv`, `outputs/pack-figures.json` |
| Gate only | `.venv/bin/python -I .claude/skills/audit-program/build_pack.py --gate` |
| Builder | `.venv/bin/python -I .claude/skills/audit-program/build_pack.py` |
| Builder test | `.venv/bin/python -I .claude/skills/audit-program/test_build_pack.py` |

Never edit the builder's outputs by hand. Nothing is written when the build fails.

## Step 1: Gate (stop and report on failure)

Run `--gate`. It is open only when:

- `risk-ratings.json` has a `revision` block numbered 1 or more (the register is a
  revision, built after the auditor's decisions) and that revision was built by
  `build_register.py` from the current ratings and inputs;
- every risk in the register has APPROVE, AMEND or REJECT in
  `auditor-comments.md`, and each decision is the one applied in that revision.

APPROVE and AMEND are in scope; REJECT is out of scope (its reason is shown in
the memo). If the gate is closed, report the errors and stop: the auditor
completes `auditor-comments.md` and the risk-assessor is re-run. Never work
around the gate.

## Step 2: Read the structures, not the data

From `risk-register.md` read the in-scope risks, their ratings, evidence and
proposed focus, and any auditor comment (an AMEND comment may change the focus).
For `analytics-full/`, print column names and `head -3` only, or counts with a
short pandas/csv one-liner. Never print a whole file. Note the exact
`rule_id`s and analytics `$.paths` you will cite.

## Step 3: Write `outputs/audit-plan.json`

```json
{
  "title": "Procurement compliance 2026/27",
  "register_revision": 1,
  "memo": {"sections": [
    {"heading": "Background", "text": "... {{$.tests.split_purchases.general_procurement.groups}} groups [metric:$.tests.split_purchases.general_procurement.groups] ..."},
    {"heading": "Objective", "text": "..."},
    {"heading": "Approach", "text": "{{$.pack.scope.in_scope}} approved risks; {{$.pack.scope.sample_units}} sample units ..."},
    {"heading": "Timing and resources", "text": "..."},
    {"heading": "Limitations", "text": "..."}
  ]},
  "risks": [
    {"risk_id": "R-01",
     "controls": [
       {"control_id": "C-01.1", "description": "... [rule:CPR-07]", "owner": "Procurement"}
     ],
     "tests": [
       {"test_id": "T-01.1", "title": "Groups crossing the three-quotes tier",
        "controls": ["C-01.1"],
        "step": "For each sampled group ... [rule:CPR-49]",
        "sample": {"kind": "draw", "source": "split_purchases.csv",
                   "filter": [{"column": "main_tag", "op": "in", "value": ["general_procurement", "premises"]},
                              {"column": "T", "op": "eq", "value": {"rule": "CPR-49", "field": "threshold_low"}}],
                   "sort": [{"column": "group_total", "descending": true}],
                   "method": "top", "size": "by_score", "transactions": "all",
                   "rationale": "Largest groups first ..."},
        "pbc": ["PBC-01"]}
     ]}
  ],
  "pbc": [{"pbc_id": "PBC-01", "item": "Purchase orders and invoices for each sampled payment", "owner": "Finance"}],
  "rules_not_tested": [{"rule_ids": ["CPR-01", "CPR-02"], "reason": "..."}]
}
```

`register_revision` is the register's revision number from the gate. The worked
example is `fixtures/plan-two-risks.json`.

### Controls (risk → expected control)

- One entry per control a well-run process would have against the risk. `control_id`
  is `C-<risk number>.<n>`.
- **Every control cites ≥1 `[rule:CPR-xx]`** for the requirement it enforces.
  An uncited control fails the build.
- Phrase the control as the expected state ("quotations are invited ..."), not as
  a failure.

### Tests (control → test step → sample)

- `test_id` is `T-<risk number>.<n>`; `controls` lists the controls it tests
  (same risk). **Every control needs at least one test.**
- **Every step cites ≥1 `[rule:...]` or `[metric:$.path]`.** Say what to obtain,
  what to compare, and what counts as the control operating.
- `pbc` names the PBC items the step needs.
- `sample` is one of three kinds:

| kind | Use for | Fields |
| --- | --- | --- |
| `draw` | Flagged items in `analytics-full/` | `source`, `filter`, `sort`, `method`, `size`, `one_per`, `transactions`, `rationale` |
| `external` | A population the client provides (e.g. waiver register) | `population` (what, and the PBC item), `size: "by_score"`, `rationale` |
| `none` | Walkthrough or enquiry; nothing is pulled | `reason` |

Draw recipe:

- `source`: a file in `analytics-full/` with row ids: `split_purchases.csv`,
  `threshold_clustering.csv`, `off_contract.csv`, `off_contract_candidates.csv`,
  `duplicates.csv`, `duplicates_clusters.csv`, `expired_notice_spend.csv`,
  `spend_vs_award.csv`, `high_value_suppliers.csv`, `spend_clean.csv`. Each row of
  the file is one sample unit (a group, supplier, cluster or payment).
- `filter`: all conditions must hold. `op` is one of `eq ne in not_in gt gte lt lte
  contains is_blank not_blank`. A threshold is never typed: write
  `{"rule": "CPR-49", "field": "threshold_low"}` and the builder reads it from
  rules.json (a typed rules.json threshold fails the build).
- `sort`: list of `{column, descending}`; ties keep file order, so the draw is
  deterministic. `method`: `top` (first n) or `systematic` (evenly spaced over
  the sorted list). `one_per`: keep only the first unit per value of a column
  (e.g. `supplier_norm`).
- `size`: `by_score` (default) or `all`. **You never type a sample size.** The
  builder takes it from `sampling.json` by the risk's final score (after any
  auditor override); if fewer units are eligible, it takes them all. Use `all`
  for small populations the risk register says to test in full.
- `transactions`: `all` (every payment of each unit) or `largest` (the largest
  payment per unit; use for supplier-level units with many payments).

Follow the register's proposed focus and the analytics caveats: test
general procurement and premises before placements; never sample suppliers
below the notice tier from `off_contract.csv` (the file holds only suppliers
above it); resolve `off_contract_candidates.csv` before treating a supplier
as unmatched.

### PBC list

One entry per document or listing to request (`PBC-01` ...), with an owner where
known. Every item must be needed by a test; every test names its items. The
builder renders the list at the end of `audit-program.md` with the tests that
need each item.

### Rules accounted for

Every rule in rules.json must be cited by an in-scope risk (in
risk-ratings.json), a control or a test, **or** listed in `rules_not_tested`
with a reason (out of the approved scope, covered by another review, not
testable from the records). A rule cited only by a rejected risk counts as not
tested. A rule listed as not tested must not be cited by a control or test.

### Memo text and figures

- Every figure is a `{{$.path}}` placeholder; a number typed in prose fails the
  build. Paths resolve against analytics.json, except `$.pack...`, which resolve
  against the builder's own figures:
  - `$.pack.scope.{in_scope, out_of_scope, amended, controls, tests, samples_drawn, sample_units, transactions_sampled, sampled_value_gbp, pbc_items, rules_total, rules_cited, rules_not_tested, highest_score_in_scope}`
  - `$.pack.risks["R-01"].{likelihood, impact, score, band, sample_size}`
  - `$.pack.tests["T-01.1"].{population_units, eligible_units, sample_units, transactions, sampled_value_gbp, size_by_score}`
  Formats: `{{$.path|gbp}}`, `|int`, `|pct`, `|ratio`, `|num`, `|raw`; the default
  follows the key name.
- Citations: `[rule:CPR-xx]`, `[metric:$.path]` (analytics.json only),
  `[history:ID]`. A citation that does not resolve fails the build.
- The builder adds the scope table (with the auditor's decisions and comments),
  the sampling summary, every caveat of the analytics tests the pack uses (the
  missing-notices caveat travels with `off_contract` and `expired_notice_spend`),
  and the rules coverage line. Do not repeat them.

### Indicator language

Real council, real data. Write "risk indicators to investigate", "flagged for
testing", "establish whether". Never say or imply wrongdoing by the council, a
department or a supplier. The banned words in `scripts/common.py` fail the build.

## Step 4: Build until clean

Run the builder. Fix every `ERROR` in audit-plan.json and run it again until it
prints `BUILT`. Then report: risks in scope, controls, tests, sample files and
transactions, PBC items, rules not tested. Never edit `sampling.json`,
the register, or the builder's outputs to get a build through.

## What the builder checks

| Check | Fails when |
| --- | --- |
| Gate | register not a revision; a register risk undecided or missing from auditor-comments.md; a decision not applied; ratings or inputs changed since the revision was built |
| Scope | an approved risk missing from the plan; a rejected or unknown risk in it; `register_revision` wrong |
| Controls | a control cites no rule; a control has no test |
| Tests | a step cites no rule or metric; a test names no control or PBC item, or one that does not exist |
| Samples | unknown source, column or op; a typed threshold; a filter that leaves nothing; a sampled row id not in `spend_clean.csv`; a payment's amount or supplier, or a group's total, that disagrees with `spend_clean.csv` |
| Rules | a rule neither cited nor listed as not tested; a not-tested rule cited by a control or test |
| Text | an unresolved citation or placeholder; a typed figure; accusatory wording |
| PBC | an item no test needs |

`pack-figures.json` records every figure the builder computed (ratings, sample
sizes, populations, sample counts and values, scope counts) and every
placeholder it filled, for the QA number check.
