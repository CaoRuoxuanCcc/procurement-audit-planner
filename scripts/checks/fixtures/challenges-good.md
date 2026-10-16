# Challenges to the audit pack

_Test fixture for scripts/checks/test_checks.py: a closed challenger record for the two-risk fixture pack. All entries concern risk indicators to investigate and the strength of the plan, not findings about the council, any department or any supplier._

| # | Round | Type | Risk | Route | Challenge (with citation) | Ask | Planner response | Status | Verified in |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | sample | R-01 | planner | T-01.1 omits premises groups although the focus names them [metric:$.tests.split_purchases.by_tag.premises.count] [pack:T-01.1] | Add premises to the T-01.1 filter. | accepted: premises added to T-01.1 | resolved | v2 |
| 2 | 1 | rating | R-04 | for the auditor | Spend after expiry sits in procurement tags [metric:$.tests.expired_notice_spend.counts.flagged] | Should R-04 impact be Medium? | for the auditor | for the auditor | n/a |
| 3 | 2 | control | R-04 | planner | C-04.1 cites the extension rule only [rule:CPR-58] [pack:C-04.1] | Cite the variation rule too. | declined: no variation in scope for R-04 | declined | n/a |

## For the auditor

- #2: whether R-04 impact should be Medium [metric:$.tests.expired_notice_spend.counts.flagged].

## Summary

Three challenges: one resolved, one declined, one for the auditor.
