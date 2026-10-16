---
name: sample-recipe-lessons
description: How-to lessons for audit-plan.json draw recipes (split groups size, candidates one_per, typed-figure rules)
metadata:
  type: feedback
---

- split_purchases.csv groups at the higher tiers can hold dozens of payments each (payment-run lines), so `transactions: all` lists hundreds of rows. Keep `all` (the whole group is needed to judge one requirement) but write the step so invoices are vouched selectively (e.g. largest payment per distinct narrative) rather than "every invoice".
- off_contract_candidates.csv has several rows per supplier (one per candidate notice); use `one_per: supplier_norm` and tell the step to compare against every candidate notice listed for that supplier.
- Typed-figure check ignores single digits, years, ids like T-01.1, and "row B1"/"clause 7.2" references; any other 2+ digit number in prose fails.
- Grants (R-08 type, if rejected) must be filtered out of every draw by tag; split, off_contract and duplicates files all contain grant rows. A supplier's `main_tag` is not every payment's tag: with `transactions: largest` the pulled payment can be grant-tagged, so after each build scan `samples/T-*.csv` for `tag == grant` and exclude that supplier.
- Cleaning's public-body pattern misses abbreviated names (e.g. "... BOROUGH CNCL", "... COUNCILS"); scan supplier-level draws for them before announcing.

**Why:** found while building the first pack; the builder passes these, but the auditor's workload and the reviewers' reading depend on them.
**How to apply:** check per-test transaction counts in pack-figures.json (`pack.tests`) after every build.
