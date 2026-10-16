---
name: analytics-and-pack-inspection
description: How to inspect analytics.json, history.json and the pack's sample files quickly and resolve citation paths, for challenger work
metadata:
  type: reference
---

- analytics.json: `top_5_by_tag` is a dict keyed by tag, each a list of row dicts; per-tag counts live under `tests.<test>.by_tag.<tag>.<class>.count` for off_contract, `by_tag.<tag>.count` for split/duplicates. threshold_clustering ratios are under `counts.per_threshold["T"].by_tag.<tag>.ratio_band_to_comparison`.
- Paths with `["25000"]` need a resolver that handles both `.key` and `["key"]` tokens; write the checker to a scratchpad .py file (zsh breaks on `$`/`[` inside `python -c "..."`).
- history.json: audits are under `audits_completed` (fields `audit_title`, `service`, `opinion`), follow-ups under `follow_ups` (`opinion_report`, `implementation_progress`); `agreed_actions` may be empty.
- `analytics.contracts.per_publication_year` shows the notice export's earliest year (contracts let earlier always look unmatched).
- Sample CSVs (`outputs/samples/T-*.csv`) have columns unit_no, supplier_norm, tag per row; group by (unit_no, supplier_norm) to list units and spot rows tagged out-of-scope (e.g. a `largest` payment tagged grant).
- `rules.json` is a dict with `rules`, `parameters` (statutory Threshold values, may be null), `excluded`.
- Banned words: import `BANNED_RE` from `scripts/common.py` to scan challenges.md.
