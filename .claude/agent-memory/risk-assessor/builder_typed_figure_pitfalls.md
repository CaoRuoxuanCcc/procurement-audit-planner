---
name: builder-typed-figure-pitfalls
description: How build_register.py's typed-figure check misfires on officer titles and clause ranges, and path syntax that resolves
metadata:
  type: feedback
---

Prose wording that trips the `--strict` typed-figure warning in build_register.py:
- "S.151 Officer" is flagged ('151'); write "S151 Officer" (no dot), as the rules themselves do.
- "clauses 7.2 to 7.5": only the first reference after "clause" is exempt; write "clause 7.2 and clause 7.5".
- Bare digits of two or more ("30-day", "7 days") count as typed figures; use words ("a short window", "the duplicate window").

Paths that resolve: numeric keys need bracket-and-quote syntax, e.g.
`$.tests.split_purchases.general_procurement.per_threshold["25000"].groups` and
`$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.<tag>.ratio_band_to_comparison`.
Per-tag off_contract metrics live at `$.tests.off_contract.by_tag.<tag>.no_notice_found.count`.

**Why:** found on the 2026-10-16 first build; each one cost a rebuild cycle.
**How to apply:** follow these when drafting risk-ratings.json prose, before the first builder run.

Revision runs: the builder appends a full stop after an `override.note`, so write the note without a trailing period (otherwise the register shows "..").
An auditor rating in an AMEND ("lower impact to 4") goes in `override.score`; the builder accepts the digit there without a typed-figure warning, but keep digits out of `note`.
