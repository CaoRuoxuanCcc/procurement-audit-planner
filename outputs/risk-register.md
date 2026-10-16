# Procurement risk register: West Berkshire Council

**Revision 1** (revised after the auditor's decisions on revision 0). Built 2026-10-16 by `.claude/skills/risk-assessment/build_register.py` from `outputs/risk-ratings.json`; every figure, score and band below was filled in by the builder.

> All entries are risk indicators to investigate, not findings about the council, any department or any supplier.

**Status:** 9 risks rated; 0 excluded for missing citations or figures; auditor decisions recorded for 9 of 9. Decisions go in `outputs/auditor-comments.md`.

## Revision 1: changes since revision 0

Applies the auditor decisions of 2026-10-16 on revision 0: seven risks approved as rated, R-06 amended (impact lowered by auditor override), R-08 rejected (grants to be covered by a separate review).

Decisions answered in this revision: 7 APPROVE, 1 AMEND, 1 REJECT.

| Risk | What changed | Auditor decision | Note |
| --- | --- | --- | --- |
| R-06 | impact.override | AMEND on R-06: Allen Cao, 2026-10-16: Lower impact to 4: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately. | Auditor override of impact, as asked in the AMEND: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately. Rubric step, Table 1 level and justification left as they were. |

**Auditor overrides** (the score differs from the evidence rubric because the auditor asked):
- R-06 impact: **4** (the rubric gives 5). Auditor (Allen Cao, 2026-10-16) lowered impact: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately

**Moved out of scope by the auditor:** R-08.

Unchanged since revision 0: R-01, R-02, R-03, R-04, R-05, R-07, R-08, R-09.

## Inputs

| File | sha256 |
| --- | --- |
| `outputs/analytics.json` | `e3c5d87f4befd47b…` |
| `outputs/history.json` | `60b5b7052c3c1252…` |
| `outputs/rules.json` | `d0e28d0aceab1ef7…` |
| `scoring_choices.json` | `dafd1ddfe22b8734…` |

## Scoring method

- **Council method:** risk-management-strategy-2024-27.pdf, as extracted into `outputs/history.json` (`risk_scoring_method`). Likelihood LIK-1…LIK-5 (1 Rare, 2 Unlikely, 3 Likely, 4 Almost Certain, 5 Certain); impact IMP-1…IMP-5 (1 Negligible, 2 Minor, 3 Medium, 4 Major, 5 Critical).
- **Score:** read from the Figure 1 matrix cell for the likelihood and impact (MTX-I1…MTX-I5). The strategy states no formula (GAP-06), so the builder looks the cell up rather than multiplying. The matrix was rebuilt from the PDF layout by findings-analyst.
- **Band, colour, escalation and response:** Table 4 (BND-1…BND-4), matched on the cell's score. Table 4 prints no colour for Moderate (GAP-07).
- **Level rated:** Actual (EVL-2): Ratings use the Actual (current) level: the spend indicators show how controls operate now, with mitigation already in place.
- **Likelihood rubric** (SKILL.md): L1 test ran and flagged nothing in scope = 1; L2 inherent risk only, or a weak or explained signal = 2; L3 signal in a procurement-relevant scope = 3; L4 the same and pervasive (share at least 50%, from a test without the missing-notices caveat) = 4. Likelihood 5 only through the uplift or an auditor override.
- **Repeat-finding uplift:** +1 when a prior audit on the same theme had an adverse opinion. The papers do not define the opinion levels (GAP-05); the builder reads Limited and Weak (and Unsatisfactory follow-up progress) as adverse.
- **Hard rule:** each likelihood and impact justification cites at least one rule, analytics metric or audit/theme item that resolves. A risk without one is excluded and listed at the end.

### Conflicts in the scoring method

The strategy contradicts itself in places. Each conflict below uses one reading and marks the other; the choices are in `.claude/skills/risk-assessment/scoring_choices.json` for the auditor to change.

| Choice | Discrepancy | Topic | Used | Other reading (marked) |
| --- | --- | --- | --- | --- |
| CH-1 | DIS-04 | Score at which a risk goes on the Corporate Risk Register | Table 4: the Extreme band (15-25) is added to the Corporate Risk Register (detected: ESC-1 score 9 or above vs BND-1 from 15) | Figure 4: risks that score 9 or above go on the Corporate Risk Register — marked **‡** where it gives a different result |
| CH-2 | DIS-03 | Name of the band for scores 8-12 | Table 4 band name (Medium - High), which carries the RAG colour, escalation and response (detected: Figure 1 'High' vs Table 4 'Medium - High') | Figure 1 cell name (High) — marked **†** where it gives a different result |
| CH-3 | DIS-01 | Number of the Medium impact level | Table 1 and Figure 1: Medium = 3 | Para 4.3: Medium (2) |
| CH-4 | DIS-02 | Overlapping financial-loss bands in Table 1 | The £ figures, which do not overlap (Medium £175k-£500k, Major £500k-£2M) | The % of budget figures, where Medium 0.1%-0.3% and Major 0.25%-1% overlap |
| CH-5 | DIS-08 | Where an Extreme risk is escalated | Table 4: add to the Corporate Risk Register | Para 6.3: escalate to the Executive Director, to consider the Directorate or the Corporate register |

Discrepancies that do not affect scoring: DIS-05 (Version of the appetite guidance cited; does not change a score, band or appetite level.); DIS-06 (Name of the committee; does not change scoring.); DIS-07 (Names of the evaluation levels only; the register rates the Actual/Current level (rated_level).); DIS-09 (Cross-reference to the policy appendix; does not change scoring.); DIS-10 (Cross-reference to the definitions appendix; does not change scoring.)

## Summary

| Risk | Title | Likelihood | Impact | Score | Matrix label | Band | Escalation (used reading) | Scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-06 | Duplicate payments to the same supplier | 3 Likely | 4 Major (override) | 12 | High | Medium - High (Amber)†‡ | Seek assurance that identified controls are effective | in scope |
| R-01 | Requirements split across payments below a quotation or tender tier | 3 Likely | 3 Medium | 9 | High | Medium - High (Amber)†‡ | Seek assurance that identified controls are effective | in scope |
| R-03 | Spend above the notice tier with no published contract notice | 3 Likely | 3 Medium | 9 | High | Medium - High (Amber)†‡ | Seek assurance that identified controls are effective | in scope |
| R-05 | Spend beyond the awarded contract value | 3 Likely | 3 Medium | 9 | High | Medium - High (Amber)†‡ | Seek assurance that identified controls are effective | in scope |
| R-04 | Spend continuing after a contract notice has ended | 3 Likely | 2 Minor | 6 | Moderate | Moderate (no colour stated, GAP-07) | None | in scope |
| R-09 | Exceptions and waivers of competition not documented or approved | 2 Unlikely | 3 Medium | 6 | Moderate | Moderate (no colour stated, GAP-07) | None | in scope |
| R-02 | Order values set just under a quotation tier | 2 Unlikely | 2 Minor | 4 | Moderate | Moderate (no colour stated, GAP-07) | None | in scope |
| R-07 | Care and education placements arranged without the App C records and approvals | 2 Unlikely | 2 Minor | 4 | Moderate | Moderate (no colour stated, GAP-07) | None | in scope |
| R-08 | Grants awarded without the procurement steps that apply to contracts | 3 Likely | 2 Minor | 6 | Moderate | Moderate (no colour stated, GAP-07) | None | out of scope (auditor) |

‡ Score at which a risk goes on the Corporate Risk Register: the other reading (Figure 4: risks that score 9 or above go on the Corporate Risk Register) gives a different result for this risk (CH-1, DIS-04).  
† Name of the band for scores 8-12: the other reading (Figure 1 cell name (High)) gives a different result for this risk (CH-2, DIS-03).  

## Risks

### R-06 · Duplicate payments to the same supplier

**Rating:** likelihood 3 × impact 4 → score **12** (cell MTX-I4); matrix label High; band **Medium - High (Amber)†‡**; escalation: Seek assurance that identified controls are effective; response: Allocate to Service Director to put in place Controls Assurance. Scope: in scope.

**Risk.** Risk that the same invoice or amount is paid more than once to a supplier, leading to overpayment that is not recovered [AUD-11]. *Theme: Finance.*

**Likelihood 3 Likely** (rubric step L3: 3). 1,502 same-supplier, same-amount pairs within the duplicate window have different timestamps [`tests.duplicates.counts.by_class.different_timestamp.pairs`], including 40 in general procurement [`tests.duplicates.by_tag.general_procurement.count`] and 178 in premises [`tests.duplicates.by_tag.premises.count`]. Most pairs are placements, which the caveat explains as recurring fixed-rate payments; the procurement-tag pairs are not explained by it.

**Impact 4 Major** — **auditor override**; the agent rated 5. Auditor (Allen Cao, 2026-10-16) lowered impact: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately. Table 1, financial loss: "> 1% annual WBC budget >£2m". Value exposed: £3,254,021. Table 1 Critical [IMP-5]: the repeat value beyond the first payment in clusters with different timestamps [`tests.duplicates.totals_gbp.repeat_value_beyond_first_clusters_with_different_timestamp`] is the money that could be lost if those repeats were not valid. It is a ceiling across all tags, most of it in placements where repeats are often legitimate.

**Evidence.**
- Different-timestamp pairs: 1,502 [`tests.duplicates.counts.by_class.different_timestamp.pairs`].
- Placement pairs: 1,283 [`tests.duplicates.by_tag.care_or_education_placement.count`].
- Accounts Payable audit, Reasonable Assurance [AUD-11].

**Proposed focus.** Sample different-timestamp clusters from analytics-full/duplicates_clusters.csv, all general procurement and premises clusters first, then the largest placement clusters; for each, match the payments to distinct invoices or to a recurring schedule, and confirm recovery of any repeat payment.

**Caveats carried from analytics.json.**
- (duplicates) same_timestamp pairs are probably lines of one payment run and are reported separately; top_20 uses different_timestamp pairs only.
- (duplicates) Recurring fixed-rate payments (e.g. weekly care) can repeat legitimately; pairs are indicators to investigate.

**Auditor decision:** AMEND: Allen Cao, 2026-10-16: Lower impact to 4: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately. (applied in revision 1).

### R-01 · Requirements split across payments below a quotation or tender tier

**Rating:** likelihood 3 × impact 3 → score **9** (cell MTX-I3); matrix label High; band **Medium - High (Amber)†‡**; escalation: Seek assurance that identified controls are effective; response: Allocate to Service Director to put in place Controls Assurance. Scope: in scope.

**Risk.** Risk that a single requirement is met through several smaller payments to one supplier, so that the combined value crosses an App B tier that no single payment reaches, and the quotation, notice or tender steps for that tier are not run [CPR-07] [CPR-48] [CPR-49] [CPR-53]. *Theme: Contracts & Partnerships.*

**Likelihood 3 Likely** (rubric step L3: 3). In general procurement, 119 supplier groups [`tests.split_purchases.general_procurement.groups`] have payments within a short window whose combined total crosses a tier that each payment stays under, including 45 groups at the three-quotes and notice tier [`tests.split_purchases.general_procurement.per_threshold["25000"].groups`] and 2 at the App B row C boundary [`tests.split_purchases.general_procurement.per_threshold["500000"].groups`]. The placement caveat does not explain general procurement groups. No test gives a flagged share of the scoped population, so L4 cannot be assessed; a share of general procurement suppliers in groups would settle it.

**Impact 3 Medium**. Table 1, compliance: "Reasonable possibility of successful legal challenge. Reasonable possibility of regulatory interest". Table 1 Medium [IMP-3]: a requirement disaggregated to avoid the Rules or the Procurement Legislation [CPR-07] gives a reasonable possibility of challenge where the aggregated value reaches the notice or tender tiers [CPR-50] [CPR-53].

**Evidence.**
- General procurement groups crossing a tier: 119 [`tests.split_purchases.general_procurement.groups`], combined value £9,485,431 [`tests.split_purchases.general_procurement.total_gbp`].
- Premises groups: 41 [`tests.split_purchases.by_tag.premises.count`].
- Anti-splitting rule, clause 6.16 [CPR-07].

**Proposed focus.** Sample general procurement and premises groups from analytics-full/split_purchases.csv, prioritising groups at the three-quotes tier and the App B row C boundary; for each, establish whether the payments relate to one requirement and, if so, whether quotations, a notice or a tender were obtained at the aggregated value.

**Caveats carried from analytics.json.**
- (split_purchases) Recurring care placements produce many groups; general_procurement is reported separately. Overlapping windows are merged, so a group can span more than 30 days; each constituent window spans at most 29 days.
- (split_purchases) Groups are indicators to investigate whether payments relate to one requirement, not findings.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-03 · Spend above the notice tier with no published contract notice

**Rating:** likelihood 3 × impact 3 → score **9** (cell MTX-I3); matrix label High; band **Medium - High (Amber)†‡**; escalation: Seek assurance that identified controls are effective; response: Allocate to Service Director to put in place Controls Assurance. Scope: in scope.

**Risk.** Risk that suppliers whose annualised spend enters the App B notice-publication tier are engaged without a published contract notice, written contract or recorded award approval [CPR-50] [CPR-52] [CPR-27] [CPR-45]. *Theme: Contracts & Partnerships.*

**Likelihood 3 Likely** (rubric step L3: 3). In general procurement, 159 suppliers above the notice tier [`tests.off_contract.by_tag.general_procurement.no_notice_found.count`] have no exact-matched notice, 87% of that tag's annualised estimate [`tests.off_contract.by_tag.general_procurement.no_notice_found.share_of_population_annualised_estimate`]; premises 24 [`tests.off_contract.by_tag.premises.no_notice_found.count`]. The placement caveat does not cover these tags. The share comes from a test whose notices may be incomplete, so it cannot carry L4.

**Impact 3 Medium**. Table 1, compliance: "Reasonable possibility of successful legal challenge. Reasonable possibility of regulatory interest". Table 1 Medium [IMP-3]: a contract in the notice tier let without a notice [CPR-50] gives a reasonable possibility of successful legal challenge and of regulatory interest.

**Evidence.**
- General procurement suppliers above the tier with no notice found: 159 of 208 [`tests.off_contract.by_tag.general_procurement.population.count`].
- Agency staff suppliers above the tier with no notice found: 1 [`tests.off_contract.by_tag.agency_staff.no_notice_found.count`].
- Population for contract evidence requests: 673 suppliers enter the three-quotes tier [`tests.high_value_suppliers.counts.suppliers`].
- Contract Letting audit, Reasonable Assurance [AUD-01].

**Proposed focus.** Sample general procurement, premises and agency staff suppliers from analytics-full/off_contract.csv (no notice found), and resolve analytics-full/off_contract_candidates.csv first; for each, request the contract, the quotations or tender, the notice (Contracts Finder or the Central Digital Platform) and the award approval, using analytics-full/high_value_suppliers.csv as the request population. Check whether a framework, waiver or App C exclusion applies before treating any item as an exception.

**Caveats carried from analytics.json.**
- (high_value_suppliers) annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.
- (high_value_suppliers) This is a sampling population, not a list of exceptions.
- (off_contract) Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- (off_contract) Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- (off_contract) Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- (off_contract) annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-05 · Spend beyond the awarded contract value

**Rating:** likelihood 3 × impact 3 → score **9** (cell MTX-I3); matrix label High; band **Medium - High (Amber)†‡**; escalation: Seek assurance that identified controls are effective; response: Allocate to Service Director to put in place Controls Assurance. Scope: in scope.

**Risk.** Risk that spend with a contracted supplier runs beyond the awarded value without an approved variation [CPR-59] [CPR-60]. *Theme: Contracts & Partnerships.*

**Likelihood 3 Likely** (rubric step L3: 3). Of 18 suppliers with one live single-supplier notice and an award value [`tests.spend_vs_award.counts.population`], 7 [`tests.spend_vs_award.counts.flagged`] have an annualised estimate at or above the flag ratio of the award per year, mainly in general procurement (6) [`tests.spend_vs_award.by_tag.general_procurement.count`]. The flagged share is below the pervasive level, so L4 does not apply.

**Impact 3 Medium**. Table 1, compliance: "Reasonable possibility of successful legal challenge. Reasonable possibility of regulatory interest". Table 1 Medium [IMP-3]: a variation above the Threshold needs board approval [CPR-60], and an unapproved increase in scope gives a reasonable possibility of successful legal challenge.

**Evidence.**
- Flagged suppliers: 7 [`tests.spend_vs_award.counts.flagged`], window spend £633,768 [`tests.spend_vs_award.totals_gbp.flagged_window_total`].
- Variation approvals, App C row E [CPR-59] [CPR-60].

**Proposed focus.** Test every supplier in analytics-full/spend_vs_award.csv: request the contract value, any variations and their approvals; note that award values may be estimates or maxima.

**Caveats carried from analytics.json.**
- (spend_vs_award) Awarded values may be estimates or maxima; a ratio above 1.25 is an indicator to request variation approvals, not a finding.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-04 · Spend continuing after a contract notice has ended

**Rating:** likelihood 3 × impact 2 → score **6** (cell MTX-I2); matrix label Moderate; band **Moderate (no colour stated, GAP-07)**; escalation: None; response: Monitor risk. Scope: in scope.

**Risk.** Risk that payments continue to suppliers after their contract has ended without an approved extension [CPR-58]. *Theme: Contracts & Partnerships.*

**Likelihood 3 Likely** (rubric step L3: 3). Of 46 exact-matched suppliers paid in the window [`tests.expired_notice_spend.counts.exact_matched_suppliers_paid`], 8 [`tests.expired_notice_spend.counts.flagged`] have only notices that ended before the window, all in general procurement (6) [`tests.expired_notice_spend.by_tag.general_procurement.count`] and premises (2) [`tests.expired_notice_spend.by_tag.premises.count`]. The missing-notices caveat keeps this at L3 at most.

**Impact 2 Minor**. Table 1, compliance: "Low possibility of legal challenge. Low possibility regulatory interest". Table 1 Minor [IMP-2]: where the contract provides for extension, the control at issue is the internal S151 Officer approval [CPR-58], giving a low possibility of legal challenge; the value involved is £243,364 in the window [`tests.expired_notice_spend.totals_gbp.flagged_window_total`].

**Evidence.**
- Suppliers flagged: 8 [`tests.expired_notice_spend.counts.flagged`].
- Window spend with these suppliers: £243,364 [`tests.expired_notice_spend.totals_gbp.flagged_window_total`].

**Proposed focus.** Test every supplier in analytics-full/expired_notice_spend.csv: request the extension and its S151 Officer approval, or a newer contract and its notice.

**Caveats carried from analytics.json.**
- (expired_notice_spend) A newer contract or an approved extension may exist with no notice.
- (expired_notice_spend) Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-09 · Exceptions and waivers of competition not documented or approved

**Rating:** likelihood 2 × impact 3 → score **6** (cell MTX-I3); matrix label Moderate; band **Moderate (no colour stated, GAP-07)**; escalation: None; response: Monitor risk. Scope: in scope.

**Risk.** Risk that competition is waived above the three-quotes tier without a valid ground, a written exception report or the S151 Officer and Monitoring Officer approvals [CPR-13] [CPR-15] [CPR-19] [CPR-21]. *Theme: Contracts & Partnerships.*

**Likelihood 2 Unlikely** (rubric step L2: 2). No analytics test measures waivers; the risk rests on the rules [CPR-13] [CPR-19] and on the Contracts & Partnerships source of risk in the Risk Management Strategy [THM-21]. Unmatched suppliers under R-03 may rely on waivers, which the audit would test.

**Impact 3 Medium**. Table 1, compliance: "Reasonable possibility of successful legal challenge. Reasonable possibility of regulatory interest". Table 1 Medium [IMP-3]: a waiver above the tier without a valid ground [CPR-13] gives a reasonable possibility of successful legal challenge.

**Evidence.**
- Waiver grounds and approvals, clause 7.2 and clause 7.5 [CPR-13] [CPR-21].
- Contracts & Partnerships source of risk [THM-21].

**Proposed focus.** Obtain the waiver and exception register for the period; test a sample for a valid ground, the written exception report and the approvals; cross-match waivers to the R-03 sample.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-02 · Order values set just under a quotation tier

**Rating:** likelihood 2 × impact 2 → score **4** (cell MTX-I2); matrix label Moderate; band **Moderate (no colour stated, GAP-07)**; escalation: None; response: Monitor risk. Scope: in scope.

**Risk.** Risk that order values are set just under an App B tier so that the one-quote or three-quotes steps are not triggered [CPR-48] [CPR-49] [CPR-07]. *Theme: Contracts & Partnerships.*

**Likelihood 2 Unlikely** (rubric step L2: 2). In the procurement-relevant tags the band just under each tier is no fuller than the comparison band below it: general procurement ratio 1.00 at the one-quote tier [`tests.threshold_clustering.counts.per_threshold["1000"].by_tag.general_procurement.ratio_band_to_comparison`] and 0.90 at the three-quotes tier [`tests.threshold_clustering.counts.per_threshold["25000"].by_tag.general_procurement.ratio_band_to_comparison`]; premises 0.89 [`tests.threshold_clustering.counts.per_threshold["1000"].by_tag.premises.ratio_band_to_comparison`]. A ratio above one in a procurement tag would raise this to L3.

**Impact 2 Minor**. Table 1, compliance: "Low possibility of legal challenge. Low possibility regulatory interest". Table 1 Minor [IMP-2]: values held under the one-quote or three-quotes tier mainly affect the internal quotation steps [CPR-48] [CPR-49], with a low possibility of legal challenge.

**Evidence.**
- General procurement band-to-comparison ratio at the one-quote tier: 1.00 [`tests.threshold_clustering.counts.per_threshold["1000"].by_tag.general_procurement.ratio_band_to_comparison`].
- General procurement band-to-comparison ratio at the three-quotes tier: 0.90 [`tests.threshold_clustering.counts.per_threshold["25000"].by_tag.general_procurement.ratio_band_to_comparison`].
- Placements show a higher ratio at the one-quote tier, 1.26 [`tests.threshold_clustering.counts.per_threshold["1000"].by_tag.care_or_education_placement.ratio_band_to_comparison`]; placements are considered under R-07.

**Proposed focus.** Light-touch: in walkthroughs, confirm how order values near the App B tiers are set; sample a few general procurement payments from analytics-full/threshold_clustering.csv only if the walkthrough raises concerns.

**Caveats carried from analytics.json.**
- (threshold_clustering) A payment near a threshold is a risk indicator to investigate; the comparison band gives context for whether the band is unusually full.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-07 · Care and education placements arranged without the App C records and approvals

**Rating:** likelihood 2 × impact 2 → score **4** (cell MTX-I2); matrix label Moderate; band **Moderate (no colour stated, GAP-07)**; escalation: None; response: Monitor risk. Scope: in scope.

**Risk.** Risk that placements and care packages arranged outside competition under App C lack the recorded reasons for provider choice, the PSR process or the board approval that App C requires [CPR-56] [CPR-61] [CPR-62]. *Theme: Contracts & Partnerships.*

**Likelihood 2 Unlikely** (rubric step L2: 2). Placements show many flagged items, 309 suppliers above the notice tier with no notice [`tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count`] and 233 split-purchase groups [`tests.split_purchases.by_tag.care_or_education_placement.count`], but the analytics caveats explain these routinely: placements are often arranged under App C exclusions or frameworks and recur. No test measures whether the App C records exist; a case-file sample would.

**Impact 2 Minor**. Table 1, compliance: "Low possibility of legal challenge. Low possibility regulatory interest". Table 1 Minor [IMP-2]: the requirement is to record reasons on case notes [CPR-61] and obtain board approval above the Threshold [CPR-62]; gaps give a low possibility of legal challenge. The Purchase of Residential and Nursing Care Provision audit gave Reasonable Assurance [AUD-14].

**Evidence.**
- Placement suppliers above the notice tier with no notice: 309 [`tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count`].
- Purchase of Residential and Nursing Care Provision, Reasonable Assurance [AUD-14].
- App C row F, records of provider choice [CPR-61].

**Proposed focus.** Sample placement suppliers from analytics-full/off_contract.csv (care_or_education_placement) and confirm the App C basis: case-note reasons for provider choice, the PSR record where applicable, framework call-off or board approval above the Threshold.

**Caveats carried from analytics.json.**
- (off_contract) Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- (off_contract) Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- (off_contract) Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- (off_contract) annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.
- (split_purchases) Recurring care placements produce many groups; general_procurement is reported separately. Overlapping windows are merged, so a group can span more than 30 days; each constituent window spans at most 29 days.
- (split_purchases) Groups are indicators to investigate whether payments relate to one requirement, not findings.

**Auditor decision:** APPROVE: Allen Cao, 2026-10-16. (applied in revision 1).

### R-08 · Grants awarded without the procurement steps that apply to contracts

**Rating:** likelihood 3 × impact 2 → score **6** (cell MTX-I2); matrix label Moderate; band **Moderate (no colour stated, GAP-07)**; escalation: None; response: Monitor risk. Scope: out of scope (auditor).

**Risk.** Risk that grants, which clause 1.6.2 treats as contracts, are awarded above the notice tier without a published notice, written agreement or recorded approval [CPR-50] [CPR-27]. *Theme: Contracts & Partnerships.*

**Likelihood 3 Likely** (rubric step L3: 3). 123 grant recipients above the notice tier [`tests.off_contract.by_tag.grant.no_notice_found.count`] have no exact-matched notice, with 0 matched [`tests.off_contract.by_tag.grant.exact_match_any_notice.count`]. No analytics caveat gives a routine explanation for grants. The missing-notices caveat keeps this at L3 at most.

**Impact 2 Minor**. Table 1, compliance: "Low possibility of legal challenge. Low possibility regulatory interest". Table 1 Minor [IMP-2]: the main exposure is to the written-contract and notice requirements [CPR-27] [CPR-50] for grant agreements, with a low possibility of legal challenge.

**Evidence.**
- Grant recipients above the tier with no notice found: 123 of 123 [`tests.off_contract.by_tag.grant.population.count`].
- Written contract requirement, clause 10.2 [CPR-27].

**Proposed focus.** Sample grant recipients from analytics-full/off_contract.csv (grant tag) and request the grant agreement, the basis for award (competition, exclusion or exception) and its approval.

**Caveats carried from analytics.json.**
- (off_contract) Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- (off_contract) Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- (off_contract) Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- (off_contract) annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

**Auditor decision:** REJECT: Allen Cao, 2026-10-16: Grants will be covered by a separate review. (applied in revision 1).

## Considered and not rated

- **high_value_suppliers**: Population for contract evidence requests, not exceptions [`tests.high_value_suppliers.counts.suppliers`]; used in R-03's evidence and focus.

## Citations

| Citation | Resolves to | Source |
| --- | --- | --- |
| AUD-01 | Contract Letting: Reasonable Assurance (End of March 2025) | audit-completed-work-2024-25-annual.pdf p1 |
| AUD-11 | Accounts Payable: Reasonable Assurance (End of December 2025) | audit-completed-work-2025-26-q3.pdf p1 |
| AUD-14 | Purchase of Residential and Nursing Care Provision: Reasonable Assurance (End of December 2025) | audit-completed-work-2025-26-q3.pdf p1 |
| IMP-2 | Impact 2 Minor (Table 1) | risk-management-strategy-2024-27.pdf p14 |
| IMP-3 | Impact 3 Medium (Table 1) | risk-management-strategy-2024-27.pdf p14 |
| IMP-5 | Impact 5 Critical (Table 1) | risk-management-strategy-2024-27.pdf p14 |
| THM-21 | Risk theme: Contracts & Partnerships | risk-management-strategy-2024-27.pdf p33 |
| `$.tests.duplicates.by_tag.care_or_education_placement.count` | 1283 | analytics.json |
| `$.tests.duplicates.by_tag.general_procurement.count` | 40 | analytics.json |
| `$.tests.duplicates.by_tag.premises.count` | 178 | analytics.json |
| `$.tests.duplicates.counts.by_class.different_timestamp.pairs` | 1502 | analytics.json |
| `$.tests.duplicates.totals_gbp.repeat_value_beyond_first_clusters_with_different_timestamp` | 3254020.77 | analytics.json |
| `$.tests.expired_notice_spend.by_tag.general_procurement.count` | 6 | analytics.json |
| `$.tests.expired_notice_spend.by_tag.premises.count` | 2 | analytics.json |
| `$.tests.expired_notice_spend.counts.exact_matched_suppliers_paid` | 46 | analytics.json |
| `$.tests.expired_notice_spend.counts.flagged` | 8 | analytics.json |
| `$.tests.expired_notice_spend.totals_gbp.flagged_window_total` | 243364.42 | analytics.json |
| `$.tests.high_value_suppliers.counts.suppliers` | 673 | analytics.json |
| `$.tests.off_contract.by_tag.agency_staff.no_notice_found.count` | 1 | analytics.json |
| `$.tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count` | 309 | analytics.json |
| `$.tests.off_contract.by_tag.general_procurement.no_notice_found.count` | 159 | analytics.json |
| `$.tests.off_contract.by_tag.general_procurement.no_notice_found.share_of_population_annualised_estimate` | 0.87 | analytics.json |
| `$.tests.off_contract.by_tag.general_procurement.population.count` | 208 | analytics.json |
| `$.tests.off_contract.by_tag.grant.exact_match_any_notice.count` | 0 | analytics.json |
| `$.tests.off_contract.by_tag.grant.no_notice_found.count` | 123 | analytics.json |
| `$.tests.off_contract.by_tag.grant.population.count` | 123 | analytics.json |
| `$.tests.off_contract.by_tag.premises.no_notice_found.count` | 24 | analytics.json |
| `$.tests.spend_vs_award.by_tag.general_procurement.count` | 6 | analytics.json |
| `$.tests.spend_vs_award.counts.flagged` | 7 | analytics.json |
| `$.tests.spend_vs_award.counts.population` | 18 | analytics.json |
| `$.tests.spend_vs_award.totals_gbp.flagged_window_total` | 633768.19 | analytics.json |
| `$.tests.split_purchases.by_tag.care_or_education_placement.count` | 233 | analytics.json |
| `$.tests.split_purchases.by_tag.premises.count` | 41 | analytics.json |
| `$.tests.split_purchases.general_procurement.groups` | 119 | analytics.json |
| `$.tests.split_purchases.general_procurement.per_threshold["25000"].groups` | 45 | analytics.json |
| `$.tests.split_purchases.general_procurement.per_threshold["500000"].groups` | 2 | analytics.json |
| `$.tests.split_purchases.general_procurement.total_gbp` | 9485430.51 | analytics.json |
| `$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.care_or_education_placement.ratio_band_to_comparison` | 1.26 | analytics.json |
| `$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.general_procurement.ratio_band_to_comparison` | 1.0 | analytics.json |
| `$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.premises.ratio_band_to_comparison` | 0.89 | analytics.json |
| `$.tests.threshold_clustering.counts.per_threshold["25000"].by_tag.general_procurement.ratio_band_to_comparison` | 0.9 | analytics.json |
| CPR-07 | 6.16: "There shall be no artificial splitting or disaggregation of a contract to avoid the application of the provisions of the Procurement Legislation and/or these Rules." | contract-rules.pdf p5 |
| CPR-13 | 7.2: "Subject to 7.4 the requirement for the Council to conduct a competitive purchasing process, contracts with a value of more than £24,999.99, may be excepted or waived in the following circumstance:" | contract-rules.pdf p6 |
| CPR-15 | 7.3: "Only the Monitoring Officer and/or the S.151 Officer may grant a waiver or an exception to these Rules, subject to exception values and delegation thresholds detailed in these Rules and/or elsewhere in the Constitution. An officer who seeks a waiver of these Rules shall do so only in advance and only in exceptional circumstances." | contract-rules.pdf p6 |
| CPR-19 | 7.5.1: "All exceptions or waivers to these Rules must: 7.5.1 be fully documented;" | contract-rules.pdf p6 |
| CPR-21 | 7.5.3: "be subject to approval by the S.151 Officer who shall record they have considered the reasons for the waiver and that they are satisfied that the circumstances justifying the waiver are genuinely exceptional (applications for waivers which are a result of poor contract planning will rarely be considered genuinely exceptional);" | contract-rules.pdf p7 |
| CPR-27 | 10.2: "All contracts entered into by the Council as detailed in Appendix B must be in writing in a form approved by the Monitoring Officer or their delegated officer." | contract-rules.pdf p8 |
| CPR-45 | App A row 2: "Relevant Service Director (following recommendation of the S151 officer and Monitoring Officer) shall have delegated authority to award the contract provided a written report by the relevant Service Director (or such officers as nominated by them in writing) has been provided and approved by the relevant board." | contract-rules.pdf p11 |
| CPR-48 | App B row A: "At least one quote must be sought from an appropriate source." | contract-rules.pdf p12 |
| CPR-49 | App B row B1: "Invitations to quote must be sent via the Procurement Portal to at least three appropriate sources, including at least one SME* or VCSE* organisation and one local supplier ****(where appropriate and possible**)." | contract-rules.pdf p12 |
| CPR-50 | App B row B1 (advertising): "A contract notice must be published on the CDP" | contract-rules.pdf p12 |
| CPR-52 | App B row B2 (advertising): "A contract notice must be published on the CDP" | contract-rules.pdf p12 |
| CPR-53 | App B row C: "Full competitive tender process applies and at least five written tenders must be sought via the Procurement Portal." | contract-rules.pdf p12 |
| CPR-56 | App C row B: "Key decisions must be recorded and the relevant process under PSR followed" | contract-rules.pdf p14 |
| CPR-58 | App C row D: "Approval of the S151 Officer" | contract-rules.pdf p14 |
| CPR-59 | App C row E (below Threshold): "For contract value below the Threshold prior written approval from the Monitoring Officer and S151 Officer is required." | contract-rules.pdf p14 |
| CPR-60 | App C row E (above Threshold): "For contract value greater than the Threshold, approval of the relevant board, following the submission of an extension report to the relevant board with recommendation from Monitoring Officer and S151 Officer" | contract-rules.pdf p14 |
| CPR-61 | App C row F: "Service Directors must ensure that a record of the reasons for the choice of provider is maintained on the individual’s case notes." | contract-rules.pdf p15 |
| CPR-62 | App C closing note: "In the interests of clarity where an exemption is applied all contracts with an annual or total value of more than the Threshold must be approved by the relevant board." | contract-rules.pdf p15 |

## Figures

Every figure in this register, with its path in `outputs/analytics.json` and the value before rounding.

| Shown | Path | Value |
| --- | --- | --- |
| 119 | `$.tests.split_purchases.general_procurement.groups` | 119 |
| 45 | `$.tests.split_purchases.general_procurement.per_threshold["25000"].groups` | 45 |
| 2 | `$.tests.split_purchases.general_procurement.per_threshold["500000"].groups` | 2 |
| £9,485,431 | `$.tests.split_purchases.general_procurement.total_gbp` | 9485430.51 |
| 41 | `$.tests.split_purchases.by_tag.premises.count` | 41 |
| 1.00 | `$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.general_procurement.ratio_band_to_comparison` | 1.0 |
| 0.90 | `$.tests.threshold_clustering.counts.per_threshold["25000"].by_tag.general_procurement.ratio_band_to_comparison` | 0.9 |
| 0.89 | `$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.premises.ratio_band_to_comparison` | 0.89 |
| 1.26 | `$.tests.threshold_clustering.counts.per_threshold["1000"].by_tag.care_or_education_placement.ratio_band_to_comparison` | 1.26 |
| 159 | `$.tests.off_contract.by_tag.general_procurement.no_notice_found.count` | 159 |
| 87% | `$.tests.off_contract.by_tag.general_procurement.no_notice_found.share_of_population_annualised_estimate` | 0.87 |
| 24 | `$.tests.off_contract.by_tag.premises.no_notice_found.count` | 24 |
| 208 | `$.tests.off_contract.by_tag.general_procurement.population.count` | 208 |
| 1 | `$.tests.off_contract.by_tag.agency_staff.no_notice_found.count` | 1 |
| 673 | `$.tests.high_value_suppliers.counts.suppliers` | 673 |
| 46 | `$.tests.expired_notice_spend.counts.exact_matched_suppliers_paid` | 46 |
| 8 | `$.tests.expired_notice_spend.counts.flagged` | 8 |
| 6 | `$.tests.expired_notice_spend.by_tag.general_procurement.count` | 6 |
| 2 | `$.tests.expired_notice_spend.by_tag.premises.count` | 2 |
| £243,364 | `$.tests.expired_notice_spend.totals_gbp.flagged_window_total` | 243364.42 |
| 18 | `$.tests.spend_vs_award.counts.population` | 18 |
| 7 | `$.tests.spend_vs_award.counts.flagged` | 7 |
| 6 | `$.tests.spend_vs_award.by_tag.general_procurement.count` | 6 |
| £633,768 | `$.tests.spend_vs_award.totals_gbp.flagged_window_total` | 633768.19 |
| 1,502 | `$.tests.duplicates.counts.by_class.different_timestamp.pairs` | 1502 |
| 40 | `$.tests.duplicates.by_tag.general_procurement.count` | 40 |
| 178 | `$.tests.duplicates.by_tag.premises.count` | 178 |
| 1,283 | `$.tests.duplicates.by_tag.care_or_education_placement.count` | 1283 |
| £3,254,021 | `$.tests.duplicates.totals_gbp.repeat_value_beyond_first_clusters_with_different_timestamp` | 3254020.77 |
| 309 | `$.tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count` | 309 |
| 233 | `$.tests.split_purchases.by_tag.care_or_education_placement.count` | 233 |
| 123 | `$.tests.off_contract.by_tag.grant.no_notice_found.count` | 123 |
| 0 | `$.tests.off_contract.by_tag.grant.exact_match_any_notice.count` | 0 |
| 123 | `$.tests.off_contract.by_tag.grant.population.count` | 123 |

## Auditor decisions

Record decisions in `outputs/auditor-comments.md` (APPROVE, AMEND or REJECT, with a comment for AMEND and REJECT), then have the risk-assessor re-run. This table is a copy and is rewritten on every build.

| Risk | Rating | Decision | Comment | Status |
| --- | --- | --- | --- | --- |
| R-01 | L3 × I3 → 9, Medium - High (Amber)†‡ | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
| R-02 | L2 × I2 → 4, Moderate (no colour stated, GAP-07) | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
| R-03 | L3 × I3 → 9, Medium - High (Amber)†‡ | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
| R-04 | L3 × I2 → 6, Moderate (no colour stated, GAP-07) | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
| R-05 | L3 × I3 → 9, Medium - High (Amber)†‡ | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
| R-06 | L3 × I4 → 12, Medium - High (Amber)†‡ | AMEND | Allen Cao, 2026-10-16: Lower impact to 4: the loss figure is a ceiling and most repeated amounts are care and education placements, which often recur legitimately. | applied in revision 1 |
| R-07 | L2 × I2 → 4, Moderate (no colour stated, GAP-07) | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
| R-08 | L3 × I2 → 6, Moderate (no colour stated, GAP-07) | REJECT | Allen Cao, 2026-10-16: Grants will be covered by a separate review. | applied in revision 1 |
| R-09 | L2 × I3 → 6, Moderate (no colour stated, GAP-07) | APPROVE | Allen Cao, 2026-10-16. | applied in revision 1 |
