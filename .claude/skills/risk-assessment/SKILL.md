---
name: risk-assessment
description: Rate procurement risks on the council's likelihood × impact method from rules.json, analytics.json and history.json. The agent writes judgments with citations to outputs/risk-ratings.json; build_register.py fills every figure, looks up score and band, and renders outputs/risk-register.md and outputs/auditor-comments.md. Also handles revisions after the auditor's decisions.
---

# risk-assessment

You judge; the builder computes. You write **`outputs/risk-ratings.json`**:
which risks exist, the rubric step for likelihood, the Table 1 level for
impact, and the reasons, each reason citing its source. You never type a
number. `build_register.py` (next to this file) resolves every citation, fills
every figure from analytics.json, reads the score, matrix label and band from
the council's matrix in history.json, drops any risk without evidence, and
writes the register, the auditor's decision template and a state file.

Governing principles (CLAUDE.md): LLM reads and judges, Python computes every
number; everything traceable; indicators, not accusations; context discipline;
missing or malformed input means stop and report.

## Inputs and outputs

| | Path |
| --- | --- |
| In | `outputs/rules.json`, `outputs/analytics.json` (+ `analytics-full/`), `outputs/history.json` |
| In (auditor) | `outputs/auditor-comments.md` once decisions are recorded |
| Method choices | `.claude/skills/risk-assessment/scoring_choices.json`: read it, never edit it (the auditor's to change) |
| You write | `outputs/risk-ratings.json` |
| Builder writes | `outputs/risk-register.md`, `outputs/auditor-comments.md`, `outputs/risk-register.state.json` |
| Builder | `.venv/bin/python -I .claude/skills/risk-assessment/build_register.py --strict` |
| Builder test | `.venv/bin/python -I .claude/skills/risk-assessment/test_build_register.py` |

Never edit `risk-register.md`, `auditor-comments.md` or the state file by hand.

## Step 1: Preconditions (stop and report on failure)

1. The three input files exist and parse.
2. `analytics.json` → `self_check.status` is `"PASS"`.
3. `.venv/bin/python -I scripts/verify_history.py outputs/history.json` prints
   `ALL CHECKS PASSED`.
4. `history.json` → `risk_scoring_method.status`. If it is not `"extracted"`,
   the builder falls back to 1–5 Very low…Very high and says so in the
   register header. Do not invent a council scale.
5. If `outputs/auditor-comments.md` has decisions in it, this is a **revision**
   run: go to Step 6 instead of starting over.

## Step 2: Read the structures, not the data

analytics.json is large. Inspect it with short Python one-liners that print
keys, counts and `status` per test, and the `top_20`/`caveats` you need. Never
print a whole file. history.json: list ids with their title/opinion/theme.
rules.json: list `rule_id`, `clause`, `type`. Note the **exact paths and ids**
you will cite: a citation that does not resolve is treated as absent.

## Step 3: Decide the risks

A risk is a statement of what could go wrong in procurement, in indicator
language ("risk that…", "indicators of…"). Use these starting points. Each
analytics test that ran must be either cited by a rated risk or listed in
`not_rated` with a reason (the builder warns otherwise).

| Theme | Main evidence | Rules to cite |
| --- | --- | --- |
| Requirements split to stay under a tier | `split_purchases` (use `general_procurement`; placements dominate the totals) | anti-avoidance rule (`type: anti-avoidance`), App B tiers |
| Order values set just under a tier | `threshold_clustering` `ratio_band_to_comparison` per threshold and tag | App B tiers |
| Spend above the notice tier with no published notice | `off_contract` by tag, never below the tier | App B advertising rows |
| Spend after a notice ended | `expired_notice_spend` | App C row D |
| Spend beyond the awarded value | `spend_vs_award` | App C row E |
| Duplicate payments | `duplicates` different-timestamp class only | none (payment accuracy); cite history (e.g. Accounts Payable audit) |
| Contract evidence for high-value suppliers | `high_value_suppliers`: a population, not exceptions; cannot by itself raise likelihood above L2 | App B rows B1/B2 |
| Care placements and grants | the tag rows of the tests above; App C exclusions | App C rows, clause on grants |

Add a history-only risk only if an audit or theme in history.json bears on
procurement; it rates L2 at most before any uplift. Merge overlapping risks.
Aim for 6–10 risks; quality over count.

## Step 4: Rate each risk

### Likelihood rubric (pick one step; the builder maps it to the score)

Evaluate the **scope the risk is about** (normally the procurement-relevant
tags: `general_procurement`, `premises`, `agency_staff`; placements and grants
only when the risk is about them). Take the **highest** step whose conditions
all hold:

| Step | Score | Conditions (all must hold) |
| --- | --- | --- |
| L1 | 1 Rare | The test ran and flagged **nothing** in scope. Cite the zero metric. |
| L2 | 2 Unlikely | Either no test measures the risk (rule only, or history only); or the test flagged items but the signal is weak or explained: the band-to-comparison ratio is at most 1, or the flagged items sit only in tags whose analytics caveats give a routine explanation (placements under App C, recurring payment runs). |
| L3 | 3 Likely | The test flagged items in scope, the signal is not explained away by a caveat, and where a comparison exists the ratio is above 1. Cite at least one metric. |
| L4 | 4 Almost Certain | L3 holds **and** the indicator is pervasive: a flagged share of at least 0.5 of the scoped population, given as `likelihood.share`, from a test **without** the missing-notices caveat (not `off_contract` or `expired_notice_spend`). |
| — | 5 Certain | Never from the rubric. Only by the uplift from L4, or an auditor override. |

Then the **repeat-finding uplift** (CLAUDE.md): if a prior audit or follow-up
on the **same theme** had an adverse opinion (Limited or Weak Assurance, or
Unsatisfactory follow-up progress), add `likelihood.uplift` with that item's id
and a reason saying why the theme is the same. The builder adds one point,
states it, and refuses an uplift cited to a Reasonable or Substantial opinion.
Same theme means the same process (for example contract letting, accounts
payable, purchase of care), not just the same directorate.

Two runs on the same evidence must pick the same step. When torn between
two steps, take the lower one and say what would raise it.

### Impact (Table 1 of the Risk Management Strategy)

1. Pick the one Table 1 column that best describes the consequence:
   `financial_loss`, `personal`, `assets`, `reputation`, `compliance`. For
   procurement-rule risks this is normally `compliance` (legal challenge,
   regulatory interest).
2. Pick the level whose cell text fits, and cite it as `[history:IMP-n]` with
   n equal to `impact.score`. The builder quotes the cell in the register.
3. Use `financial_loss` only where money could actually be lost (for example
   duplicate payments: the repeat value beyond the first payment). Then set
   `impact.exposure` to one placeholder; the builder checks it falls in that
   level's £ band (choice CH-4). Flagged spend is **value exposed, not loss**:
   never use a flagged spend total as a financial loss.
4. Cite at least one piece of evidence as well. The IMP item is the scale,
   not evidence.

### Citations and figures

| Write | Means | Resolves against |
| --- | --- | --- |
| `[rule:CPR-07]` | a rule | `rules.json` `rules[].rule_id` |
| `[metric:$.tests.split_purchases.general_procurement.groups]` | a named metric | `analytics.json`; the test must have status `ran`; value not null |
| `[history:AUD-12]` | a history item | any `id` in `history.json` |
| `{{$.tests.split_purchases.general_procurement.total_gbp}}` | a figure, filled in by the builder | `analytics.json` |
| `{{$.path\|pct}}` | a figure with an explicit format | formats: `gbp`, `int`, `pct` (fraction → %), `ratio`, `num`, `raw` |

- Paths: `$.a.b`, list items `[0]`, keys that are numbers or have spaces
  `["25000"]` (e.g. `$.tests.threshold_clustering.counts.per_threshold["25000"].ratio_band_to_comparison`).
- The default format follows the key: `*gbp*`, `*total*`, `*amount*`,
  `*estimate*` → £; `share*` → %; `*ratio*` → 2 dp; integers → with commas.
- **Evidence** for the hard rule is a rule, a metric, or a history item from
  `audits_completed`, `follow_ups`, `advisory_reviews`, `agreed_actions` or
  `risk_themes`. Scale items (IMP, LIK, MTX, BND…), gaps (GAP) and
  discrepancies (DIS) resolve but are not evidence.
- **Never type a figure** in prose: no £, %, counts, days or ratios. Clause
  and row references, ids and years are fine. The builder warns on each typed
  figure; fix every warning.
- Any document citing `off_contract` or `expired_notice_spend` must carry
  their caveat. The builder copies the caveats of every cited test into the
  risk; do not repeat them, but do not contradict them.
- Words such as fraud, breach, non-compliant, suspicious (the
  `scripts/common.py` list) fail the build.

## Step 5: Write risk-ratings.json and build

```json
{
  "generated_on": "YYYY-MM-DD",
  "risks": [
    {
      "risk_id": "R-01",
      "title": "Requirements split across payments below a quotation tier",
      "theme": "Contracts & Partnerships",
      "description": "Risk that … [rule:CPR-07].",
      "likelihood": {
        "rubric": "L3",
        "justification": "… {{$.tests…groups}} groups [metric:$.tests…groups] …",
        "share": "$.path or {\"numerator\": \"$.p\", \"denominator\": \"$.q\"} (L4 only)",
        "uplift": {"audit": "AUD-12", "reason": "why this is the same theme"}
      },
      "impact": {
        "score": 3,
        "criterion": "compliance",
        "exposure": "{{$.path}} (financial_loss only)",
        "justification": "Table 1 Medium [history:IMP-3]: … [rule:CPR-49] …"
      },
      "evidence": ["one line per piece of evidence, each with a citation"],
      "proposed_focus": "what the audit should test and which analytics-full list to sample"
    }
  ],
  "not_rated": [
    {"topic": "high_value_suppliers", "reason": "Population for evidence requests, not exceptions [metric:$.tests.high_value_suppliers.counts.suppliers]; used in R-03's focus."}
  ]
}
```

Omit `share`, `uplift`, `exposure` and `override` when they do not apply.
Write no other field: a likelihood score, a band or any computed value is an
error, because the builder computes them.

Run the builder with `--strict`, which turns every warning into a failure.
Exit 0 = built; 1 = errors (or warnings), nothing written; 2 = an input is
missing. Read every `WARN` and `DROP` line:

- `DROP`: the risk is excluded and listed in the register. Fix its citations
  if the risk is real; otherwise remove it.
- `WARN … figure typed in prose`: replace the number with a placeholder.
- `WARN test … ran but no rated risk … cites it`: rate it or add a `not_rated`
  entry.

Iterate until it exits 0 with no warnings. A warning you can only clear by
editing an input, this skill or the builder: stop and report it. Then read
`risk-register.md` once, top to bottom, as the auditor would.

## Step 6: Revision after the auditor's decisions

The auditor fills in `outputs/auditor-comments.md`: APPROVE, AMEND (with what
to change) or REJECT (with why), one per risk. Then:

1. Every risk must have a decision. If any is blank, stop and report which.
2. Leave APPROVE'd and REJECT'd risks exactly as they are. The builder moves
   REJECT'd risks out of scope itself; do not delete them.
3. For each AMEND, make the change asked for and nothing else. If the auditor
   sets a rating ("raise likelihood to 4"), add
   `"override": {"score": 4, "decision_ref": "R-0n", "note": "…"}` to
   `likelihood` or `impact`, leaving the rubric step and justification as
   they were; the register marks it as an auditor override. If an AMEND
   comment is unclear, ask through the main agent; do not guess.
4. Add a `revision` block:

```json
"revision": {
  "number": 1,
  "summary": "one or two sentences",
  "changes": [
    {"risk_id": "R-02", "fields": ["likelihood.override"], "decision_ref": "R-02", "note": "what changed and why"}
  ]
}
```

`fields` names exactly what changed, at the level `title`, `description`,
`evidence`, `proposed_focus`, `likelihood.<key>`, `impact.<key>`; use
`["added"]` for a new risk (its `decision_ref` is the AMEND that asked for it)
and `["removed"]` for a deleted one. The builder diffs against the revision
the auditor decided on and **fails** if a change is not declared, a declared
change did not happen, a change has no pending AMEND behind it, an AMEND is
left unapplied, or an input file changed since. The register gets a revision
header naming every change. Decisions in auditor-comments.md are kept; their
Status column shows where each was applied.

To rebuild the same revision after a fix, keep the same `number`.

## Conflicts in the council's method

The strategy contradicts itself on the Corporate Risk Register threshold
(DIS-04), the name of the 8–12 band (DIS-03), the number of the Medium level
(DIS-01), the financial bands (DIS-02) and Extreme escalation (DIS-08).
`scoring_choices.json` records which reading is used and how the other is
marked; the register header prints the table and marks affected risks
(‡, †). The builder detects the first two in history.json itself and fails if
a detected conflict, or any discrepancy in history.json, has no entry. Do not
work around a conflict in prose; if you think a choice is wrong, say so in
your report for the auditor.

## Step 7: Report

Under 200 words, to the main agent: revision number; risks rated, with score
and band; risks dropped and why; warnings left and why; any conflict choice
you think the auditor should revisit; and that the auditor's next step is to
complete `outputs/auditor-comments.md`.
