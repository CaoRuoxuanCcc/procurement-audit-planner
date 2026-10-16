# Challenges to the audit pack

_Challenger record for register revision 1, pack versions v1–v3. All entries
concern risk indicators to investigate and the strength of the plan, not
findings about the council, any department or any supplier._

| # | Round | Type | Risk | Route | Challenge (with citation) | Ask | Planner response | Status | Verified in |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | test | R-03 | planner | The notice export starts at the earliest year in [metric:$.contracts.per_publication_year], so a contract let earlier always shows as no notice found; T-03.2 and T-03.3 do not check the contract register first and do not name PBC-08 [rule:CPR-29] [pack:T-03.2] [pack:T-03.3] [pack:PBC-08] | Add PBC-08 to T-03.2/T-03.3 and open both steps with a contract-register lookup of the contract and its start date; for a contract let before the export window, test the notice and award approval held on file | accepted: PBC-08 and contract-register lookup at the start of T-03.2/T-03.3 | resolved | v2 |
| 2 | 1 | test | R-01 | planner | T-01.1/T-01.2 accept "a recorded waiver" as the control operating, but T-09.2 tests advance approval of waivers only for the T-03.2/T-03.3 samples [rule:CPR-15] [rule:CPR-21] [pack:T-01.1] [pack:T-01.2] [pack:T-09.2] | Extend T-09.2 to the T-01.1 and T-01.2 samples; in T-01.1/T-01.2 read "a waiver approved as tested under T-09.2" | accepted: T-01.1/T-01.2 read "a waiver approved as tested under T-09.2"; T-09.2 covers T-01.1, T-01.2, T-03.2, T-03.3 and also C-09.2 | resolved | v2 |
| 3 | 1 | test | R-05 | planner | C-05.1/C-05.2 split on "the Threshold", which the analytics records as null and skipped [metric:$.thresholds.skipped]; T-05.1 names no evidence of which figure applies, so it cannot tell whether CPR-59 or CPR-60 approval was required [rule:CPR-59] [rule:CPR-60] [pack:T-05.1] [pack:PBC-12] | Add to T-05.1 and a PBC item: obtain the Threshold the council applied per contract and record which of CPR-59/CPR-60 applies before testing; name the null Threshold in the memo limitations | accepted: T-05.1 obtains the Threshold per contract and records CPR-59 or CPR-60; PBC-12 extended; memo Limitations name the unset Threshold | resolved | v2 |
| 4 | 1 | sample | R-07 | planner | T-07.1 is systematic, so of the five largest placement suppliers [metric:$.tests.off_contract.top_5_by_tag.care_or_education_placement] only the first is sampled; board approval above the Threshold (C-07.3) [rule:CPR-62] is most likely to apply to those [pack:T-07.1] [pack:C-07.3] | Add T-07.2 for C-07.3: top placement suppliers by annualised_estimate (top, by_score, largest) from off_contract.csv no_notice_found; keep T-07.1 for C-07.1/C-07.2 | accepted: new T-07.2 for C-07.3, top by annualised_estimate; T-07.1 keeps C-07.1/C-07.2 | resolved | v2 |
| 5 | 1 | control | R-06 | planner | C-06.1 cites CPR-26 (written evidence of every purchase) for an Accounts Payable pre-payment duplicate check and recovery, which CPR-26 does not require; the duplicates test has "no specific rule" [metric:$.tests.duplicates.rule_note] [rule:CPR-26] [history:AUD-11] [pack:C-06.1] [pack:T-06.3] | Limit C-06.1 to what CPR-26 requires; state in T-06.3 that the AP duplicate check and recovery log are tested as payment-accuracy practice with no CPR clause, referencing [history:AUD-11] | accepted: C-06.1 limited to CPR-26; T-06.3 states the AP check is payment-accuracy practice with no CPR clause, ref AUD-11 | resolved | v2 |
| 6 | 1 | coverage | R-03 | planner | CPR-05 is one of the off_contract test's rule_ids [metric:$.tests.off_contract.rule_ids] but is listed in rules_not_tested as "not observable in the spend data"; T-03.4 already obtains the notice [rule:CPR-05] [pack:T-03.4] [pack:rules_not_tested] | Move CPR-05 out of rules_not_tested and add to T-03.4: compare the CDP notice date with any other advertisement on file; or give a CPR-05-specific reason | accepted: CPR-05 out of rules_not_tested; cited by C-03.1 and tested in T-03.4 | resolved | v2 |
| 7 | 1 | sample | R-03 | planner | Payments to other public bodies are excluded in cleaning [metric:$.cleaning.excluded.public_body.count], but one T-03.2 unit is another local authority under an abbreviated name ("BRACKNELL FOREST BOROUGH CNCL"); notice and quotation evidence does not fit an inter-authority arrangement [metric:$.tests.off_contract.by_tag.general_procurement.no_notice_found.count] [pack:T-03.2] | Add a not_in filter on supplier_norm for that unit in T-03.2 so the next supplier is drawn; note the missed public-body name in the memo limitations | accepted: not_in filter for that unit and for a second council name in the same population; memo Limitations note both | resolved | v2 |
| 8 | 1 | rating | R-07 | for the auditor | The only Limited Assurance opinion among recent audits is Personal Budgets (Direct Payments), Children with Disabilities and SEN Teams [history:AUD-12]; R-07 cites only [history:AUD-14] (Reasonable) and takes no uplift [metric:$.tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count] [pack:T-07.1] | Does AUD-12 count as a prior adverse finding on R-07's theme, so R-07 likelihood takes the +1 uplift (L2 to L3)? Yes / No | for the auditor: the plan changes nothing; a re-rating would come through a register revision | for the auditor | n/a |
| 9 | 2 | sample | R-03 | planner | In v2 the T-03.3 pull list has one unit (SOVEREIGN HOUSING GROUP) whose largest payment is tagged grant, while the memo Limitations says grants "are not sampled in any test" and R-08 is rejected [metric:$.tests.off_contract.by_tag.premises.no_notice_found.count] [pack:T-03.3] [pack:memo.Limitations] | Add a supplier_norm not_in filter for that unit to T-03.3 so the next premises supplier is drawn; or keep it and correct the memo sentence with the reason | accepted: not_in filter added to T-03.3; planner checked no other grant-tagged rows in the v2 sample files | resolved | v3 |

## For the auditor

**#8 [rating] R-07.** Question: does the Limited Assurance opinion on Personal Budgets (Direct Payments), Children with Disabilities and SEN Teams [history:AUD-12] count as a prior adverse finding on R-07's theme, so that the repeat-finding uplift raises R-07 likelihood from L2 to L3? Yes / No.
- Evidence: R-07 cites only the Reasonable Assurance opinion on residential and nursing care [history:AUD-14]; placements show flagged items [metric:$.tests.off_contract.by_tag.care_or_education_placement.no_notice_found.count] which the caveats largely explain.
- Planner's position: for the auditor; the plan changes nothing, and a re-rating would come through a register revision.
- Challenger's position: AUD-12 is the only adverse opinion among the completed audits in history.json (the adverse follow-up opinions concern schools) and covers how care and SEN provision is arranged and paid for; whether that is the same theme as App C placements is a judgment for the auditor.

## Summary

Closes on pack v3 (register revision 1). 9 challenges: round 1 on v1, 8; round 2 on v2, 1.

| Status | Count | Challenges |
| --- | --- | --- |
| resolved | 8 | #1–#7 (verified in v2, still present in v3), #9 (verified in v3) |
| declined | 0 | |
| for the auditor | 1 | #8 |

| Type | Count |
| --- | --- |
| test | 3 (#1, #2, #3) |
| sample | 3 (#4, #7, #9) |
| control | 1 (#5) |
| coverage | 1 (#6) |
| rating | 1 (#8) |
| scope | 0 |
