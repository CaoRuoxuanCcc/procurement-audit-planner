# Planning memo: Procurement compliance: Contract Procedure Rules

_Built by `build_pack.py` on 2026-10-16 from risk register revision 1 and `outputs/audit-plan.json`. All entries are risk indicators to investigate, not findings about the council, any department or any supplier._

## Background

The spend analytics cover 8,523 payments worth £66,252,292 from 2026-05-01 to 2026-07-31 [`cleaning.rows_tested`], tested against the App B tiers of the Contract Procedure Rules. They flag, among other risk indicators to investigate, 119 general procurement supplier groups whose combined payments cross a tier that each payment stays under [`tests.split_purchases.general_procurement.groups`]; 159 general procurement suppliers above the notice tier with no exact-matched contract notice [`tests.off_contract.by_tag.general_procurement.no_notice_found.count`]; 7 suppliers whose annualised spend runs ahead of the award per year [`tests.spend_vs_award.counts.flagged`]; 8 suppliers paid after their only notices ended [`tests.expired_notice_spend.counts.flagged`]; and 1,502 same-supplier, same-amount pairs with different timestamps [`tests.duplicates.counts.by_class.different_timestamp.pairs`]. Prior audits of Contract Letting [AUD-01], Accounts Payable [AUD-11] and the Purchase of Residential and Nursing Care Provision [AUD-14] gave Reasonable Assurance. None of these indicators is a finding; each is flagged for testing.

## Objective

To establish whether the controls that the Contract Procedure Rules require operate in practice for the approved risks: aggregation of requirements [CPR-07]; quotations, notices and tenders at the App B tiers [CPR-48] [CPR-49] [CPR-50] [CPR-53]; written contracts and award approvals [CPR-27] [CPR-45]; extensions and variations [CPR-58] [CPR-59] [CPR-60]; evidence for each payment [CPR-26]; the App C records for placements [CPR-61]; and waivers and exceptions [CPR-13] [CPR-21].

## Approach

The plan covers 8 approved risks with 22 expected controls and 20 tests. Samples are targeted at the flagged items rather than drawn at random: 206 sample units with 1,078 transactions worth £19,675,847 are drawn from the analytics, sized by each risk's score. General procurement and premises are tested before placements, because the analytics caveats explain much of the placement signal as recurring or App C activity. For contract notices, the trading-name and similar-name candidates are resolved first (T-03.1) before any supplier is treated as unmatched, and a framework, waiver or App C exclusion is checked before any item is reported as an exception. Exact-matched suppliers are also sampled (T-03.4) so that the controls can be seen operating where a notice exists. The waiver register is tested on its own population (T-09.1) and cross-matched to the contract-notice samples (T-09.2). Order values near the tiers are covered by a walkthrough, with a small targeted sample tested only if the walkthrough raises concerns (T-02.2).

## Timing and resources

Fieldwork dates, the audit team and the time budget are for the audit manager to set when the pack is signed off. Requests should go to Finance, Procurement, contract managers and Adult and Children's Social Care at the start of fieldwork, using the PBC list at the end of the audit program, so that documents for the larger samples (T-01.1, T-03.2, T-06.1) arrive first.

## Limitations

The analytics cover a short window, and supplier values are annualised estimates, not contract values. The statutory-threshold tiers are skipped because their parameters are not yet set in rules.json [`thresholds.skipped`], so groups and suppliers are not tested against the statutory thresholds; the auditor is to supply those figures with a citation. For the same reason the Threshold that decides which variation approval applies (C-05.1, C-05.2) and when placements need board approval (C-07.3) is not set in the analytics; T-05.1 and T-07.2 obtain the figure the council applied to each contract. Name matching to contract notices is exact on the normalised name only, and the spend data carries no Companies House number. Two suppliers in the contract-notice population, BRACKNELL FOREST BOROUGH CNCL and CITY OF LONDON COUNCILS, appear to be public bodies that the cleaning pattern did not catch; they are left out of T-03.2 and referred to spend-analyst to review. Grants are out of scope by the auditor's decision and are not sampled in any test. All results are risk indicators to investigate; the tests establish whether a documented reason or approval exists.

## Scope approved by the auditor

Register revision 1: 8 risk(s) in scope, 1 out of scope. Ratings are re-read from the council matrix by the builder; sample sizes follow the score (`sampling.json`: build_pack default (auditor to confirm or change)).

| Risk | Title | Rating | Decision | Auditor comment | Sample size per test |
| --- | --- | --- | --- | --- | --- |
| R-01 | Requirements split across payments below a quotation or tender tier | L3 × I3 → 9, Medium - High | APPROVE | Allen Cao, 2026-10-16. | 15 |
| R-02 | Order values set just under a quotation tier | L2 × I2 → 4, Moderate | APPROVE | Allen Cao, 2026-10-16. | 10 |
| R-03 | Spend above the notice tier with no published contract notice | L3 × I3 → 9, Medium - High | APPROVE | Allen Cao, 2026-10-16. | 15 |
| R-04 | Spend continuing after a contract notice has ended | L3 × I2 → 6, Moderate | APPROVE | Allen Cao, 2026-10-16. | 10 |
| R-05 | Spend beyond the awarded contract value | L3 × I3 → 9, Medium - High | APPROVE | Allen Cao, 2026-10-16. | 15 |
| R-06 | Duplicate payments to the same supplier | L3 × I4 → 12, Medium - High | AMEND | Allen Cao, 2026-10-16: Lower impact to 4: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately. | 15 |
| R-07 | Care and education placements arranged without the App C records and approvals | L2 × I2 → 4, Moderate | APPROVE | Allen Cao, 2026-10-16. | 10 |
| R-09 | Exceptions and waivers of competition not documented or approved | L2 × I3 → 6, Moderate | APPROVE | Allen Cao, 2026-10-16. | 10 |

Out of scope (auditor REJECT):

| Risk | Title | Rating | Reason given |
| --- | --- | --- | --- |
| R-08 | Grants awarded without the procurement steps that apply to contracts | L3 × I2 → 6, Moderate | Allen Cao, 2026-10-16: Grants will be covered by a separate review. |

## Sampling summary

| Test | Risk | Basis | Population | Sample | Transactions | Value | File |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-01.1 | R-01 | `split_purchases.csv` | 55 | 15 | 485 | £2,105,457 | `samples/T-01.1.csv` |
| T-01.2 | R-01 | `split_purchases.csv` | 3 | 3 (all) | 136 | £6,763,256 | `samples/T-01.2.csv` |
| T-01.3 | R-01 | `split_purchases.csv` | 103 | 15 | 94 | £68,078 | `samples/T-01.3.csv` |
| T-01.4 | R-01 | no sample (walkthrough) | n/a | n/a | n/a | n/a | n/a |
| T-02.1 | R-02 | no sample (walkthrough) | n/a | n/a | n/a | n/a | n/a |
| T-02.2 | R-02 | `threshold_clustering.csv` | 10 | 10 (all) | 10 | £238,671 | `samples/T-02.2.csv` |
| T-03.1 | R-03 | `off_contract_candidates.csv` | 31 | 17 (all) | 17 | £278,841 | `samples/T-03.1.csv` |
| T-03.2 | R-03 | `off_contract.csv` | 157 | 15 | 15 | £5,590,369 | `samples/T-03.2.csv` |
| T-03.3 | R-03 | `off_contract.csv` | 24 | 15 | 15 | £427,263 | `samples/T-03.3.csv` |
| T-03.4 | R-03 | `high_value_suppliers.csv` | 38 | 15 | 15 | £425,430 | `samples/T-03.4.csv` |
| T-04.1 | R-04 | `expired_notice_spend.csv` | 8 | 8 (all) | 8 | £159,252 | `samples/T-04.1.csv` |
| T-04.2 | R-04 | no sample (walkthrough) | n/a | n/a | n/a | n/a | n/a |
| T-05.1 | R-05 | `spend_vs_award.csv` | 7 | 7 (all) | 7 | £263,634 | `samples/T-05.1.csv` |
| T-06.1 | R-06 | `duplicates_clusters.csv` | 51 | 51 (all) | 155 | £660,910 | `samples/T-06.1.csv` |
| T-06.2 | R-06 | `duplicates_clusters.csv` | 204 | 15 | 101 | £2,110,701 | `samples/T-06.2.csv` |
| T-06.3 | R-06 | no sample (walkthrough) | n/a | n/a | n/a | n/a | n/a |
| T-07.1 | R-07 | `off_contract.csv` | 309 | 10 | 10 | £115,152 | `samples/T-07.1.csv` |
| T-07.2 | R-07 | `off_contract.csv` | 309 | 10 | 10 | £468,833 | `samples/T-07.2.csv` |
| T-09.1 | R-09 | client population | n/a | 10 to select | n/a | n/a | n/a |
| T-09.2 | R-09 | no sample (walkthrough) | n/a | n/a | n/a | n/a | n/a |

Totals: 206 units, 1,078 transactions, £19,675,847 drawn from the analytics. Every sampled transaction was checked against `analytics-full/spend_clean.csv`.

## Caveats carried from the analytics

- (duplicates) same_timestamp pairs are probably lines of one payment run and are reported separately; top_20 uses different_timestamp pairs only.
- (duplicates) Recurring fixed-rate payments (e.g. weekly care) can repeat legitimately; pairs are indicators to investigate.
- (expired_notice_spend) A newer contract or an approved extension may exist with no notice.
- (expired_notice_spend) Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- (high_value_suppliers) annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.
- (high_value_suppliers) This is a sampling population, not a list of exceptions.
- (off_contract) Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- (off_contract) Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- (off_contract) Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- (off_contract) annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.
- (spend_vs_award) Awarded values may be estimates or maxima; a ratio above 1.25 is an indicator to request variation approvals, not a finding.
- (split_purchases) Recurring care placements produce many groups; general_procurement is reported separately. Overlapping windows are merged, so a group can span more than 30 days; each constituent window spans at most 29 days.
- (split_purchases) Groups are indicators to investigate whether payments relate to one requirement, not findings.
- (threshold_clustering) A payment near a threshold is a risk indicator to investigate; the comparison band gives context for whether the band is unusually full.

## Rules coverage

36 of 62 rules are cited by an in-scope risk, control or test; 26 are listed as not tested with a reason (see the end of `audit-program.md`).
