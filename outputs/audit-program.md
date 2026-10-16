# Audit program: Procurement compliance: Contract Procedure Rules

_Built by `build_pack.py` on 2026-10-16 from risk register revision 1 and `outputs/audit-plan.json`. All entries are risk indicators to investigate, not findings about the council, any department or any supplier._

## R-01 Requirements split across payments below a quotation or tender tier

Rating L3 × I3 → 9, Medium - High; sample size by score: 15 unit(s) per test.

### T-01.1 Groups crossing the three-quotes and notice tier

- **Controls tested:** C-01.1 Requisitioners estimate the total value of a requirement across all orders and payments before choosing the procedure, and a requirement is not split or disaggregated to avoid the Rules [CPR-07].; C-01.2 Where the aggregated value enters the three-quotes tier, invitations to quote are sent through the Procurement Portal to at least three appropriate sources [CPR-49] [CPR-51] and a contract notice is published on the CDP [CPR-50] [CPR-52].
- **Test step:** For each sampled group, use the listing of the group's payments in the sample file to obtain the purchase order or orders, any contract or call-off the payments were made under, and the invoice for the largest payment of each distinct narrative. From these, establish whether the payments meet one requirement (same goods, service or works, same budget holder, ordered together or in sequence). If they do, obtain the Procurement Portal invitations to at least three sources and the CDP contract notice for the aggregated value [CPR-49] [CPR-50]. The control operates if the payments are separate requirements, or if quotations and a notice exist for the combined value, or a framework call-off or a waiver approved as tested under T-09.2 covers it [CPR-07] [`tests.split_purchases.general_procurement.per_threshold["25000"].groups`].
- **Sample:** `analytics-full/split_purchases.csv` where `main_tag` in ["general_procurement", "premises"] and `T` eq CPR-49 threshold_low (£25,000); one per `supplier_norm`; sorted by `group_total` descending; first units taken; size 15 by score. Population 55 unit(s); drawn 15, 485 transaction(s) (every transaction of each unit), £2,105,457. Pull list: `samples/T-01.1.csv`.
- **Why this sample:** Largest groups first, one per supplier so that the sample covers as many suppliers as possible; general procurement and premises are taken before placements, as the register's focus requires, because the placement caveat does not explain these tags. Every payment in each group is listed so that the whole requirement can be assessed; invoices are vouched for the largest payment of each distinct narrative.
- **PBC:** PBC-01, PBC-02, PBC-03
- **Caveat (split_purchases):** Recurring care placements produce many groups; general_procurement is reported separately. Overlapping windows are merged, so a group can span more than 30 days; each constituent window spans at most 29 days.
- **Caveat (split_purchases):** Groups are indicators to investigate whether payments relate to one requirement, not findings.

### T-01.2 Groups crossing the App B row C boundary

- **Controls tested:** C-01.1 Requisitioners estimate the total value of a requirement across all orders and payments before choosing the procedure, and a requirement is not split or disaggregated to avoid the Rules [CPR-07].; C-01.3 Where the aggregated value reaches the App B row C boundary, a full competitive tender is run seeking at least five written tenders through the Procurement Portal [CPR-53].
- **Test step:** For every group at the App B row C boundary, use the listing of the group's payments in the sample file to obtain the purchase order or orders, any contract or call-off the payments were made under, and the invoice for the largest payment of each distinct narrative, and establish whether the payments meet one requirement. If they do, obtain the tender record showing at least five written tenders sought through the Procurement Portal [CPR-53], or the framework call-off relied on, or a waiver approved as tested under T-09.2. The control operates if the payments are separate requirements or the tender record exists for the aggregated value [CPR-07] [`tests.split_purchases.general_procurement.per_threshold["500000"].groups`].
- **Sample:** `analytics-full/split_purchases.csv` where `main_tag` in ["general_procurement", "premises", "agency_staff"] and `T` eq CPR-53 threshold_low (£500,000); sorted by `group_total` descending; first units taken; size all eligible units. Population 3 unit(s); drawn 3 (all eligible), 136 transaction(s) (every transaction of each unit), £6,763,256. Pull list: `samples/T-01.2.csv`.
- **Why this sample:** The population at the highest tier outside placements and grants is small, so every group is tested in full, as the register's focus prioritises this boundary. Every payment in each group is listed so that the whole requirement can be assessed.
- **PBC:** PBC-01, PBC-04
- **Caveat (split_purchases):** Recurring care placements produce many groups; general_procurement is reported separately. Overlapping windows are merged, so a group can span more than 30 days; each constituent window spans at most 29 days.
- **Caveat (split_purchases):** Groups are indicators to investigate whether payments relate to one requirement, not findings.

### T-01.3 Groups crossing the one-quote tier

- **Controls tested:** C-01.1 Requisitioners estimate the total value of a requirement across all orders and payments before choosing the procedure, and a requirement is not split or disaggregated to avoid the Rules [CPR-07].; C-01.4 Where the aggregated value enters the one-quote tier, at least one quote is sought from an appropriate source for the combined requirement [CPR-48].
- **Test step:** For each sampled group, use the listing of the group's payments in the sample file to obtain the purchase order or orders and the invoice for the largest payment of each distinct narrative, and establish whether the payments meet one requirement and, if so, whether at least one quote was sought for the combined value [CPR-48]. The control operates if the payments are separate requirements or a quote exists for the combined value [CPR-07].
- **Sample:** `analytics-full/split_purchases.csv` where `main_tag` in ["general_procurement", "premises"] and `T` eq CPR-48 threshold_low (£1,000); one per `supplier_norm`; sorted by `group_total` descending; evenly spaced units taken; size 15 by score. Population 103 unit(s); drawn 15, 94 transaction(s) (every transaction of each unit), £68,078. Pull list: `samples/T-01.3.csv`.
- **Why this sample:** Evenly spread across the value range, one group per supplier, to see whether the aggregation control operates at the lower tier as well as at the higher tiers tested in T-01.1 and T-01.2. Every payment in each group is listed so that the whole requirement can be assessed.
- **PBC:** PBC-01, PBC-02
- **Caveat (split_purchases):** Recurring care placements produce many groups; general_procurement is reported separately. Overlapping windows are merged, so a group can span more than 30 days; each constituent window spans at most 29 days.
- **Caveat (split_purchases):** Groups are indicators to investigate whether payments relate to one requirement, not findings.

### T-01.4 Walkthrough of how the value of a requirement is estimated

- **Controls tested:** C-01.1 Requisitioners estimate the total value of a requirement across all orders and payments before choosing the procedure, and a requirement is not split or disaggregated to avoid the Rules [CPR-07].
- **Test step:** With Procurement and two services that appear in the T-01.1 sample, walk through how the total value of a requirement is estimated before ordering, how repeat orders to one supplier are monitored, and what guidance requisitioners are given on aggregation [CPR-07]. The control is designed adequately if the guidance requires aggregation across orders and someone reviews repeat orders to one supplier.
- **Sample:** none. Walkthrough and review of guidance; no transactions are pulled.
- **PBC:** PBC-05

## R-02 Order values set just under a quotation tier

Rating L2 × I2 → 4, Moderate; sample size by score: 10 unit(s) per test.

### T-02.1 Walkthrough of how order values near the tiers are set

- **Controls tested:** C-02.1 Order values are set from the estimated value of the requirement, and the quotation step for the tier the value falls in is followed: at least one quote in the one-quote tier [CPR-48] and three invitations through the Procurement Portal in the three-quotes tier [CPR-49].
- **Test step:** As part of the T-01.4 walkthrough, establish how order values near the App B tiers are set and approved, and whether anyone reviews orders just under a tier [CPR-48] [CPR-49]. The analytics show no unusual build-up just under the tiers in general procurement [`tests.threshold_clustering.counts.per_threshold["25000"].by_tag.general_procurement.ratio_band_to_comparison`], so this is a design check; perform T-02.2 only if the walkthrough finds no guidance or review over values near the tiers.
- **Sample:** none. Walkthrough with Procurement; no transactions are pulled.
- **PBC:** PBC-05

### T-02.2 Payments just under the three-quotes tier (conditional on T-02.1)

- **Controls tested:** C-02.1 Order values are set from the estimated value of the requirement, and the quotation step for the tier the value falls in is followed: at least one quote in the one-quote tier [CPR-48] and three invitations through the Procurement Portal in the three-quotes tier [CPR-49].
- **Test step:** Only if T-02.1 raises concerns: for each sampled payment, obtain the order and invoice and establish the estimated value of the requirement. If the requirement's value enters the three-quotes tier, obtain the Procurement Portal invitations to three sources [CPR-49]; otherwise confirm that at least one quote was sought [CPR-48]. The control operates if the order value reflects the requirement and the matching quotation step was followed.
- **Sample:** `analytics-full/threshold_clustering.csv` where `tag` in ["general_procurement", "premises"] and `T` eq CPR-49 threshold_low (£25,000); sorted by `amount` descending; first units taken; size 10 by score. Population 10 unit(s); drawn 10 (all eligible), 10 transaction(s) (every transaction of each unit), £238,671. Pull list: `samples/T-02.2.csv`.
- **Why this sample:** The register's focus is light-touch: if needed, test general procurement and premises payments just under the three-quotes tier, where the step skipped would be the widest, largest first.
- **PBC:** PBC-01, PBC-02
- **Caveat (threshold_clustering):** A payment near a threshold is a risk indicator to investigate; the comparison band gives context for whether the band is unusually full.

## R-03 Spend above the notice tier with no published contract notice

Rating L3 × I3 → 9, Medium - High; sample size by score: 15 unit(s) per test.

### T-03.1 Resolve trading-name and similar-name candidates

- **Controls tested:** C-03.1 A contract in the notice-publication tier is advertised on the CDP before any other advertisement [CPR-05] and has a contract notice published on the CDP [CPR-50] [CPR-52], approved and issued by the Service Lead for Procurement and Commissioning [CPR-06].
- **Test step:** Before any supplier is treated as having no notice, compare each candidate's spend supplier with every candidate notice supplier listed for it in off_contract_candidates.csv, using the supplier master record (registered name, trading names, Companies House number) and the contract register. Record for each candidate, for the auditor to confirm, whether it is the same entity as a notice supplier and whether that notice covers the spend [CPR-50] [`tests.off_contract.counts.overall.candidates.count`]. A candidate confirmed as matched is treated as having a notice; a candidate rejected is tested under the T-03.2 step.
- **Sample:** `analytics-full/off_contract_candidates.csv`; one per `supplier_norm`; sorted by `annualised_estimate` descending; first units taken; size all eligible units. Population 31 unit(s); drawn 17 (all eligible), 17 transaction(s) (largest per unit), £278,841. Pull list: `samples/T-03.1.csv`.
- **Why this sample:** The register's focus requires all candidates to be resolved first; the population is small, so every candidate supplier is taken, with its largest payment to identify the supplier record.
- **PBC:** PBC-08, PBC-09
- **Caveat (off_contract):** Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- **Caveat (off_contract):** Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- **Caveat (off_contract):** Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- **Caveat (off_contract):** annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

### T-03.2 General procurement suppliers above the notice tier with no notice found

- **Controls tested:** C-03.1 A contract in the notice-publication tier is advertised on the CDP before any other advertisement [CPR-05] and has a contract notice published on the CDP [CPR-50] [CPR-52], approved and issued by the Service Lead for Procurement and Commissioning [CPR-06].; C-03.2 Every contract in App B is in writing in a form approved by the Monitoring Officer or their delegated officer [CPR-27], and every award is notified to the Service Lead so that it is recorded on the contract register [CPR-29].; C-03.3 Quotations are invited through the Procurement Portal from at least three appropriate sources in the three-quotes tier [CPR-49] [CPR-51]; where a framework or other Purchasing Scheme is used instead, advice confirming the Council may use it is obtained first [CPR-22].; C-03.4 Each award is documented in a written report of the key decisions [CPR-23] and approved at the level App A sets for the contract value [CPR-44] [CPR-45] [CPR-46] [CPR-47].
- **Test step:** First locate the supplier's contract on the contract register [CPR-29] and record its start date; where it was let before the earliest notice year in the export [`contracts.per_publication_year`], test the notice and award approval held on file at award rather than treating the supplier as having no notice. Then, for each sampled supplier, request the contract, the quotation or tender record, the contract notice (Contracts Finder or the Central Digital Platform) and the award report and approval. First establish whether a framework call-off, a recorded waiver or an App C exclusion covers the spend: for a framework call-off, obtain the call-off and the advice that the Council may use the framework [CPR-22]; for a waiver or App C exclusion, test it under T-09.2. Otherwise the controls operate if a written contract in an approved form exists [CPR-27], quotations were invited through the Portal [CPR-49], a notice was published [CPR-50] and the award was approved at the App A level for its value [CPR-45] [`tests.off_contract.by_tag.general_procurement.no_notice_found.count`].
- **Sample:** `analytics-full/off_contract.csv` where `main_tag` eq "general_procurement" and `match_status` eq "no_notice_found" and `supplier_norm` not_in ["BRACKNELL FOREST BOROUGH CNCL", "CITY OF LONDON COUNCILS"]; sorted by `annualised_estimate` descending; first units taken; size 15 by score. Population 157 unit(s); drawn 15, 15 transaction(s) (largest per unit), £5,590,369. Pull list: `samples/T-03.2.csv`.
- **Why this sample:** Largest annualised estimates first, where the value at stake and the tier reached are highest; the file holds only suppliers above the notice tier, and general procurement is not explained by the placement caveat. The largest payment identifies the contract to request. Two names that appear to be other public bodies, missed by the cleaning pattern, are left out because notice and quotation evidence does not fit an inter-authority arrangement.
- **PBC:** PBC-01, PBC-02, PBC-03, PBC-06, PBC-07, PBC-08
- **Caveat (off_contract):** Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- **Caveat (off_contract):** Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- **Caveat (off_contract):** Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- **Caveat (off_contract):** annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

### T-03.3 Agency staff and premises suppliers above the notice tier with no notice found

- **Controls tested:** C-03.1 A contract in the notice-publication tier is advertised on the CDP before any other advertisement [CPR-05] and has a contract notice published on the CDP [CPR-50] [CPR-52], approved and issued by the Service Lead for Procurement and Commissioning [CPR-06].; C-03.2 Every contract in App B is in writing in a form approved by the Monitoring Officer or their delegated officer [CPR-27], and every award is notified to the Service Lead so that it is recorded on the contract register [CPR-29].; C-03.3 Quotations are invited through the Procurement Portal from at least three appropriate sources in the three-quotes tier [CPR-49] [CPR-51]; where a framework or other Purchasing Scheme is used instead, advice confirming the Council may use it is obtained first [CPR-22].; C-03.4 Each award is documented in a written report of the key decisions [CPR-23] and approved at the level App A sets for the contract value [CPR-44] [CPR-45] [CPR-46] [CPR-47].
- **Test step:** First locate the supplier's contract on the contract register [CPR-29] and record its start date; where it was let before the earliest notice year in the export [`contracts.per_publication_year`], test the notice and award approval held on file at award rather than treating the supplier as having no notice. Then, as T-03.2, for the agency staff supplier and the sampled premises suppliers: establish whether a framework (with the advice that the Council may use it [CPR-22]), a waiver or an App C exclusion (tested under T-09.2) applies; otherwise obtain the written contract [CPR-27], quotation record [CPR-49], notice [CPR-50] and award approval [CPR-45] [`tests.off_contract.by_tag.premises.no_notice_found.count`] [`tests.off_contract.by_tag.agency_staff.no_notice_found.count`].
- **Sample:** `analytics-full/off_contract.csv` where `main_tag` in ["agency_staff", "premises"] and `match_status` eq "no_notice_found" and `supplier_norm` not_in ["SOVEREIGN HOUSING GROUP"]; sorted by `main_tag` ascending, `annualised_estimate` descending; first units taken; size 15 by score. Population 24 unit(s); drawn 15, 15 transaction(s) (largest per unit), £427,263. Pull list: `samples/T-03.3.csv`.
- **Why this sample:** The register's focus names agency staff and premises alongside general procurement; sorting by tag first puts the single agency staff supplier in the sample, then premises suppliers follow largest annualised estimate first. One supplier whose largest payment is grant-tagged is left out, because grants are out of scope by the auditor's decision.
- **PBC:** PBC-01, PBC-02, PBC-03, PBC-06, PBC-07, PBC-08
- **Caveat (off_contract):** Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- **Caveat (off_contract):** Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- **Caveat (off_contract):** Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- **Caveat (off_contract):** annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

### T-03.4 Exact-matched suppliers: controls where a notice exists

- **Controls tested:** C-03.1 A contract in the notice-publication tier is advertised on the CDP before any other advertisement [CPR-05] and has a contract notice published on the CDP [CPR-50] [CPR-52], approved and issued by the Service Lead for Procurement and Commissioning [CPR-06].; C-03.2 Every contract in App B is in writing in a form approved by the Monitoring Officer or their delegated officer [CPR-27], and every award is notified to the Service Lead so that it is recorded on the contract register [CPR-29].; C-03.4 Each award is documented in a written report of the key decisions [CPR-23] and approved at the level App A sets for the contract value [CPR-44] [CPR-45] [CPR-46] [CPR-47].
- **Test step:** For each sampled supplier with an exact-matched notice, obtain the notice and confirm it was approved and issued by the Service Lead for Procurement and Commissioning [CPR-06], and compare the CDP notice date with the date of any other advertisement of the opportunity on the procurement file [CPR-05]; obtain the written contract and confirm the form was approved [CPR-27] and the award is on the contract register [CPR-29]; and obtain the award report and its approval at the App A level for the contract value [CPR-23] [CPR-44] [CPR-46] [CPR-47]. This gives a baseline of how the controls operate where a notice exists [`tests.off_contract.counts.overall.exact_match_any_notice.count`].
- **Sample:** `analytics-full/high_value_suppliers.csv` where `main_tag` in ["general_procurement", "premises"] and `match_status` eq "exact_match"; sorted by `annualised_estimate` descending; evenly spaced units taken; size 15 by score. Population 38 unit(s); drawn 15, 15 transaction(s) (largest per unit), £425,430. Pull list: `samples/T-03.4.csv`.
- **Why this sample:** Drawn from the contract evidence population named in the register's focus, evenly spread across the value range, so the award approval tiers of App A are all likely to appear.
- **PBC:** PBC-03, PBC-06, PBC-08
- **Caveat (high_value_suppliers):** annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.
- **Caveat (high_value_suppliers):** This is a sampling population, not a list of exceptions.

## R-04 Spend continuing after a contract notice has ended

Rating L3 × I2 → 6, Moderate; sample size by score: 10 unit(s) per test.

### T-04.1 Spend after the last notice ended

- **Controls tested:** C-04.1 An extension provided for in the contract is approved by the S151 Officer before spend continues past the original end date [CPR-58]; otherwise a new contract is let and its notice published [CPR-50].
- **Test step:** For every flagged supplier, obtain the contract and its end date, then either the extension with its S151 Officer approval dated before the original end date [CPR-58], or a newer contract with its notice [CPR-50]. The control operates if one of these covers the payments in the window [`tests.expired_notice_spend.counts.flagged`].
- **Sample:** `analytics-full/expired_notice_spend.csv`; sorted by `window_total` descending; first units taken; size all eligible units. Population 8 unit(s); drawn 8 (all eligible), 8 transaction(s) (largest per unit), £159,252. Pull list: `samples/T-04.1.csv`.
- **Why this sample:** The register's focus is to test every flagged supplier; the population is small, so all are taken, with the largest payment to identify the contract.
- **PBC:** PBC-10
- **Caveat (expired_notice_spend):** A newer contract or an approved extension may exist with no notice.
- **Caveat (expired_notice_spend):** Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.

### T-04.2 Contract register and monthly reporting of expiring contracts

- **Controls tested:** C-04.2 Each award is notified to the Service Lead so that the contract and its end date are on the contract register [CPR-29], and contract information is reported to the relevant board every month [CPR-03], so that contracts nearing expiry are visible.
- **Test step:** For each supplier in the T-04.1 sample, confirm the contract is on the contract register with its end date [CPR-29]. Obtain the monthly contract reports to the relevant board for the analytics window and establish whether they show contracts nearing expiry [CPR-03]. The control operates if the flagged contracts were on the register and reported before they ended.
- **Sample:** none. Uses the T-04.1 suppliers and the client's register and reports; no further transactions are pulled.
- **PBC:** PBC-08, PBC-11

## R-05 Spend beyond the awarded contract value

Rating L3 × I3 → 9, Medium - High; sample size by score: 15 unit(s) per test.

### T-05.1 Spend running ahead of the awarded value

- **Controls tested:** C-05.1 A variation that increases a contract below the Threshold has prior written approval from the Monitoring Officer and the S151 Officer [CPR-59].; C-05.2 A variation to a contract above the Threshold is approved by the relevant board after an extension report with the recommendation of the Monitoring Officer and S151 Officer [CPR-60].
- **Test step:** For every flagged supplier, first obtain the Threshold figure the council applied to the contract (contract type and value, per the Procurement Legislation) and record whether a variation needed Monitoring Officer and S151 Officer approval [CPR-59] or board approval [CPR-60]. Then obtain the contract, its awarded value (noting whether the published value is an estimate or a maximum), the spend to date over the contract life and any variations. Where spend exceeds the awarded value, obtain the variation and the approval recorded as applicable. The control operates if spend stays within the awarded value or a variation approved at the applicable level covers it [`tests.spend_vs_award.counts.flagged`] [`thresholds.skipped`].
- **Sample:** `analytics-full/spend_vs_award.csv` where `flagged` eq true; sorted by `ratio` descending; first units taken; size all eligible units. Population 7 unit(s); drawn 7 (all eligible), 7 transaction(s) (largest per unit), £263,634. Pull list: `samples/T-05.1.csv`.
- **Why this sample:** Every supplier whose annualised spend reaches the flag ratio of the award per year is tested, as the register's focus requires; suppliers below the ratio are within their award on the estimate and need no variation.
- **PBC:** PBC-06, PBC-12
- **Caveat (spend_vs_award):** Awarded values may be estimates or maxima; a ratio above 1.25 is an indicator to request variation approvals, not a finding.

## R-06 Duplicate payments to the same supplier

Rating L3 × I4 → 12, Medium - High; sample size by score: 15 unit(s) per test.

### T-06.1 General procurement and premises clusters with different timestamps

- **Controls tested:** C-06.1 Each payment is supported by written evidence of a distinct purchase, an order and an invoice [CPR-26], so that a repeated amount can be matched to its own invoice.
- **Test step:** For each cluster, obtain the invoice behind every payment and compare invoice number, date, period and goods or service. The control operates if each payment matches a distinct invoice, or a contracted recurring schedule [CPR-26]. Where two payments settle one invoice, establish whether the repeat was identified and recovered, and obtain the recovery record [`tests.duplicates.by_tag.general_procurement.count`] [`tests.duplicates.by_tag.premises.count`].
- **Sample:** `analytics-full/duplicates_clusters.csv` where `tag` in ["general_procurement", "premises"] and `classes` contains "different_timestamp"; sorted by `repeat_value_beyond_first` descending; first units taken; size all eligible units. Population 51 unit(s); drawn 51 (all eligible), 155 transaction(s) (every transaction of each unit), £660,910. Pull list: `samples/T-06.1.csv`.
- **Why this sample:** The register's focus is to test all general procurement and premises clusters with different timestamps first, because the recurring-placement caveat does not explain them; every payment in each cluster is pulled to compare the invoices.
- **PBC:** PBC-01, PBC-13
- **Caveat (duplicates):** same_timestamp pairs are probably lines of one payment run and are reported separately; top_20 uses different_timestamp pairs only.
- **Caveat (duplicates):** Recurring fixed-rate payments (e.g. weekly care) can repeat legitimately; pairs are indicators to investigate.

### T-06.2 Largest placement clusters with different timestamps

- **Controls tested:** C-06.1 Each payment is supported by written evidence of a distinct purchase, an order and an invoice [CPR-26], so that a repeated amount can be matched to its own invoice.; C-06.2 Recurring fixed-rate payments are made under a written contract or placement agreement that sets the payment schedule [CPR-27].
- **Test step:** For each cluster, obtain the placement agreement or care package and its payment schedule [CPR-27] and match each payment to a distinct period on the schedule or a distinct invoice [CPR-26]. The control operates if every payment matches its own period or invoice; otherwise establish whether the repeat was identified and recovered [`tests.duplicates.by_tag.care_or_education_placement.count`].
- **Sample:** `analytics-full/duplicates_clusters.csv` where `tag` eq "care_or_education_placement" and `classes` contains "different_timestamp"; sorted by `repeat_value_beyond_first` descending; first units taken; size 15 by score. Population 204 unit(s); drawn 15, 101 transaction(s) (every transaction of each unit), £2,110,701. Pull list: `samples/T-06.2.csv`.
- **Why this sample:** Then the largest placement clusters, as the register's focus requires, ranked by the value beyond the first payment, which is the amount at stake if a repeat was not valid.
- **PBC:** PBC-01, PBC-13, PBC-14
- **Caveat (duplicates):** same_timestamp pairs are probably lines of one payment run and are reported separately; top_20 uses different_timestamp pairs only.
- **Caveat (duplicates):** Recurring fixed-rate payments (e.g. weekly care) can repeat legitimately; pairs are indicators to investigate.

### T-06.3 Walkthrough of the Accounts Payable duplicate check

- **Controls tested:** C-06.1 Each payment is supported by written evidence of a distinct purchase, an order and an invoice [CPR-26], so that a repeated amount can be matched to its own invoice.
- **Test step:** Walk through how the finance system and Accounts Payable detect a possible duplicate before payment (matching on supplier, invoice number, amount and date), who reviews the exception report, and how recoveries are recorded. These are tested as payment-accuracy practice: no clause of the Rules requires them [`tests.duplicates.rule_note`], and the Accounts Payable audit [AUD-11] is the reference point. Confirm that the evidence each payment rests on identifies a distinct invoice [CPR-26]. Obtain the duplicate-payment exception reports and recovery log for the analytics window. The practice is designed adequately if possible duplicates are blocked or reviewed before release and recoveries are tracked.
- **Sample:** none. Walkthrough and review of system reports; no transactions are pulled.
- **PBC:** PBC-13

## R-07 Care and education placements arranged without the App C records and approvals

Rating L2 × I2 → 4, Moderate; sample size by score: 10 unit(s) per test.

### T-07.1 Placement suppliers above the notice tier with no notice found

- **Controls tested:** C-07.1 Service Directors ensure that the reasons for the choice of provider are recorded on the individual's case notes [CPR-61].; C-07.2 Where the Provider Selection Regime applies, key decisions are recorded and the relevant PSR process is followed [CPR-56].
- **Test step:** For each sampled supplier, use the largest payment to identify the placement or care package, then establish the App C basis: the case-note record of the reasons for choice of provider [CPR-61], the PSR record where the regime applies [CPR-56], or the framework call-off. The control operates if the record exists [`tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count`].
- **Sample:** `analytics-full/off_contract.csv` where `main_tag` eq "care_or_education_placement" and `match_status` eq "no_notice_found"; sorted by `annualised_estimate` descending; evenly spaced units taken; size 10 by score. Population 309 unit(s); drawn 10, 10 transaction(s) (largest per unit), £115,152. Pull list: `samples/T-07.1.csv`.
- **Why this sample:** Evenly spread across the value range, so that individual packages of different sizes are seen for the case-note and PSR records; the largest providers are covered by T-07.2. The largest payment identifies the placement to trace.
- **PBC:** PBC-14
- **Caveat (off_contract):** Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- **Caveat (off_contract):** Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- **Caveat (off_contract):** Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- **Caveat (off_contract):** annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

### T-07.2 Largest placement suppliers: board approval above the Threshold

- **Controls tested:** C-07.3 Where an exemption is applied, a contract with an annual or total value above the Threshold is approved by the relevant board [CPR-62].
- **Test step:** For each sampled supplier, obtain the placement contracts or framework call-offs behind the payments and their annual or total value, and the Threshold figure the council applied. Where the value is above the Threshold and an exemption is applied, obtain the relevant board's approval [CPR-62]. The control operates if each contract above the Threshold has board approval, or a framework or competed contract covers the spend [`tests.off_contract.top_5_by_tag.care_or_education_placement`].
- **Sample:** `analytics-full/off_contract.csv` where `main_tag` eq "care_or_education_placement" and `match_status` eq "no_notice_found"; sorted by `annualised_estimate` descending; first units taken; size 10 by score. Population 309 unit(s); drawn 10, 10 transaction(s) (largest per unit), £468,833. Pull list: `samples/T-07.2.csv`.
- **Why this sample:** Largest placement suppliers first, where board approval above the Threshold is most likely to apply; the largest payment identifies a placement to trace.
- **PBC:** PBC-14
- **Caveat (off_contract):** Notices may be missing for recent contracts: late publication, a partial current year, or publication on the Central Digital Platform / Find a Tender rather than Contracts Finder after the Procurement Act 2023 went live (24 Feb 2025). Auditor to confirm. Results that rely on notices must not be read as evidence that no contract exists.
- **Caveat (off_contract):** Placements and individual care packages are often arranged under App C exclusions (CPR-56, CPR-61) or frameworks and may have no notice of their own.
- **Caveat (off_contract):** Candidates (trading-name or similar-name) are for the auditor to confirm or reject and are never counted as matched.
- **Caveat (off_contract):** annualised_estimate = window total x annualisation_factor; an estimate, not a contract value.

## R-09 Exceptions and waivers of competition not documented or approved

Rating L2 × I3 → 6, Moderate; sample size by score: 10 unit(s) per test.

### T-09.1 Waiver and exception register

- **Controls tested:** C-09.1 Competition above the three-quotes tier is waived only on a ground in the Rules [CPR-13], sought in advance and granted only by the Monitoring Officer and/or the S151 Officer [CPR-15]; a discretionary exception has its reasons recorded in writing [CPR-14].; C-09.2 Every exception or waiver is fully documented [CPR-19] with a written exception report giving the reasons it is genuinely required [CPR-20].; C-09.3 The S151 Officer approves each waiver, recording that the reasons were considered and are genuinely exceptional [CPR-16] [CPR-21], with the consultation or Executive recommendation the value requires [CPR-17] [CPR-18].
- **Test step:** Obtain the waiver and exception register for the analytics window and confirm its completeness against the S151 Officer's approvals. For each sampled waiver, obtain the file and establish whether it states a ground in the Rules [CPR-13], was sought before the spend [CPR-15], has a written exception report [CPR-19] [CPR-20], and carries the S151 Officer approval with the recorded consideration [CPR-21] and the consultation or recommendation for its value [CPR-17] [CPR-18]. The control operates if all are present.
- **Sample:** select 10 item(s) (size by score) from Waivers and exceptions granted in the analytics window, from the waiver and exception register (PBC-15).
- **Why this sample:** No analytics test measures waivers, so the sample comes from the client's register; selection to favour the highest-value waivers and spread across services.
- **PBC:** PBC-15, PBC-16

### T-09.2 Waivers and App C exclusions relied on in the split-purchase and contract-notice samples

- **Controls tested:** C-09.1 Competition above the three-quotes tier is waived only on a ground in the Rules [CPR-13], sought in advance and granted only by the Monitoring Officer and/or the S151 Officer [CPR-15]; a discretionary exception has its reasons recorded in writing [CPR-14].; C-09.2 Every exception or waiver is fully documented [CPR-19] with a written exception report giving the reasons it is genuinely required [CPR-20].; C-09.3 The S151 Officer approves each waiver, recording that the reasons were considered and are genuinely exceptional [CPR-16] [CPR-21], with the consultation or Executive recommendation the value requires [CPR-17] [CPR-18].; C-09.4 Where an App C exclusion requiring it is relied on, prior written Monitoring Officer approval (and any other approval App C requires) is obtained [CPR-55] [CPR-57].
- **Test step:** For each group in the T-01.1 and T-01.2 samples and each supplier in the T-03.2 and T-03.3 samples where the service relies on a waiver or an App C exclusion, confirm that the waiver is on the register, is fully documented with a written exception report [CPR-19] [CPR-20], and was sought and approved in advance by the S151 Officer [CPR-15] [CPR-21]; or that the App C exclusion had prior written Monitoring Officer approval [CPR-55] [CPR-57]. The control operates if the waiver or exclusion is recorded, documented and approved before the spend.
- **Sample:** none. Cross-match of the T-01.1, T-01.2, T-03.2 and T-03.3 samples to the waiver register; no further transactions are pulled.
- **PBC:** PBC-15, PBC-16

## Rules not tested

| Rule(s) | Reason |
| --- | --- |
| CPR-08, CPR-09, CPR-10, CPR-11, CPR-12 | Conduct of an individual tender exercise (electronic tender format, late tenders, opening, evaluation, award criteria). The approved risks test whether the required procedure was run, not how a tender was conducted; not observable in the spend data. |
| CPR-28, CPR-30, CPR-31, CPR-32, CPR-33, CPR-34, CPR-35, CPR-36, CPR-37, CPR-38, CPR-39, CPR-40, CPR-41, CPR-42, CPR-43 | Contract content and execution (standard clauses, minimum terms, DPIA, specifications, indemnities, bonds, insurance, sealing, Counsel). Outside the approved risks; suited to a contract management review. |
| CPR-01, CPR-02, CPR-04 | Social value, budget provision and supplier suitability checks. Outside the approved risks and not testable from the spend data. |
| CPR-24, CPR-25 | Record retention periods. The PBC requests will show whether sampled records are available, but retention is not assessed as a control in the approved risks. |
| CPR-54 | App B row D tier: the statutory-threshold parameter is null in rules.json, so the analytics skipped this tier; to be tested once the auditor supplies the figure and citation. |

## PBC list

| PBC | Item | Owner | Needed by |
| --- | --- | --- | --- |
| PBC-01 | Purchase orders and invoices for each sampled payment | Finance (Accounts Payable) | T-01.1, T-01.2, T-01.3, T-02.2, T-03.2, T-03.3, T-06.1, T-06.2 |
| PBC-02 | Procurement Portal quotation records (invitations, responses and evaluation) for each sampled group, payment or supplier, or the waiver or framework call-off relied on | Procurement | T-01.1, T-01.3, T-02.2, T-03.2, T-03.3 |
| PBC-03 | Contract notices (Contracts Finder or Central Digital Platform) for each sampled group or supplier, with the Service Lead's approval of issue | Procurement | T-01.1, T-03.2, T-03.3, T-03.4 |
| PBC-04 | Tender records (Procurement Portal tender list and written tenders received) for each group at the App B row C boundary | Procurement | T-01.2 |
| PBC-05 | Procedure notes and guidance on estimating the value of a requirement, aggregation and setting order values | Procurement | T-01.4, T-02.1 |
| PBC-06 | Written contract, award report and award approval for each sampled supplier | Contract managers; Legal Services | T-03.2, T-03.3, T-03.4, T-05.1 |
| PBC-07 | Framework call-off records and the advice confirming the Council may use the framework, or the waiver or App C exclusion relied on, for each sampled supplier | Procurement | T-03.2, T-03.3 |
| PBC-08 | Contract register extract for the analytics window (supplier, contract, start and end dates, value) | Procurement | T-03.1, T-03.2, T-03.3, T-03.4, T-04.2 |
| PBC-09 | Supplier master records (registered name, trading names, Companies House number) for each candidate supplier | Finance (Accounts Payable) | T-03.1 |
| PBC-10 | Contract, extension and S151 Officer approval, or the newer contract and its notice, for each flagged supplier | Contract managers | T-04.1 |
| PBC-11 | Monthly contract information reports to the relevant board for the analytics window | Procurement | T-04.2 |
| PBC-12 | Threshold figure the council applied to each flagged contract and its basis; awarded contract value, spend to date, variations and their approvals (Monitoring Officer and S151 Officer, or board and extension report) | Contract managers | T-05.1 |
| PBC-13 | Duplicate-payment exception reports, recurring payment schedules and the recovery log for the analytics window | Finance (Accounts Payable) | T-06.1, T-06.2, T-06.3 |
| PBC-14 | Placement agreements, case-note records of provider choice, PSR records or framework call-offs, and board approvals above the Threshold, for each sampled placement | Adult Social Care; Children's Services | T-06.2, T-07.1, T-07.2 |
| PBC-15 | Waiver and exception register for the analytics window | S151 Officer; Monitoring Officer | T-09.1, T-09.2 |
| PBC-16 | Waiver and exception files: exception reports and S151 Officer and Monitoring Officer approvals, for each sampled or relied-on waiver | S151 Officer; Monitoring Officer | T-09.1, T-09.2 |
