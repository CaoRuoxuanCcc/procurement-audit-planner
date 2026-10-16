---
name: howto-pipeline-lessons
description: How-to lessons for the spend-analyst scripts (threshold-literal scan pitfalls, split-group span check, JSON size, blank-category expectation)
metadata:
  type: feedback
---

- The threshold-literal scan in self_check.py also matches comments and k-shorthand. It tripped on `// 1000` and on a comment containing "25k". Never write a tier value in any form in scripts/, comments included. The export-cap row count (also 1000) is written as `10 ** 3` with a comment, and that has to be disclosed in the report.
  **Why:** the 1000 row cap is not a monetary value, but the scan cannot tell a row count from a tier value.
  **How to apply:** derive any multiplier (e.g. Decimal.scaleb(3)) and read every T from rules.json.
- split_purchases: merged groups chain across windows, and recurring care groups span the whole quarter. The self-check therefore confirms that every row sits in a window of at most 29 days whose sum enters the tier. Requiring the group span itself to be at most 29 days would fail on a correct implementation.
- Keep row_ids out of the split_purchases top_20 in analytics.json, because some groups hold more than 100 rows. The self-check reads row_ids from the full CSV instead.
- Blank-category rows: most are Redacted-supplier lines (redacted is the first exclusion rule), not pension lines. Expect pension_or_statutory to be much smaller than the blank-category count.
- openpyxl read_only: get the Excel row from the first cell that has `.row`, because EmptyCell has none.
