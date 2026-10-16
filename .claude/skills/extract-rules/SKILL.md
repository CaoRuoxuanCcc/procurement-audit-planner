---
name: extract-rules
description: Extract every testable rule from data/contract-rules.pdf into outputs/rules.json with clause references, thresholds, approvers and verified verbatim quotes.
---

# extract-rules

Turn the council's Contract Rules PDF into a machine-readable list of testable
rules. Downstream, `spend-analyst` parameterises its tests from the threshold
values in this file and `risk-assessment` cites rules by `rule_id`, so every
number and quote here must be exact and traceable.

Governing principles (from CLAUDE.md): never fabricate; every quote verifiable;
missing or malformed input means stop and report; where the spec is silent,
ask rather than invent.

## Inputs and outputs

| | Path |
| --- | --- |
| Input | `data/contract-rules.pdf` (read-only) |
| Output | `outputs/rules.json` |
| Working text | `<scratchpad>/contract-rules.txt` (plain) and `contract-rules-layout.txt` (layout) |
| Verifier | `.claude/skills/extract-rules/verify_quotes.py` |

## Procedure

### Step 1: Preconditions (stop on failure)

1. `data/contract-rules.pdf` exists and is non-empty.
2. `pdftotext` is on PATH (`which pdftotext`). If not, check for the `pypdf`
   Python package. If neither is available, stop and tell the user how to
   install one (`brew install poppler` or `pip install pypdf`).
3. If `outputs/rules.json` already exists, say so and ask whether to overwrite
   before writing.

### Step 2: Extract the text twice

```bash
pdftotext data/contract-rules.pdf <scratchpad>/contract-rules.txt
pdftotext -layout data/contract-rules.pdf <scratchpad>/contract-rules-layout.txt
```

- The **plain** file is the source of truth for quotes. It keeps each table
  cell contiguous and drops end-of-line hyphens (e.g. layout `Call-\nIn`
  becomes plain `CallIn`). Pages are separated by form feeds (`\f`); page N
  is the Nth form-feed-delimited chunk, starting at 1.
- The **layout** file is only for reading tables (Appendices A, B, C) so that
  you can see which cells belong to which row.
- Read both files in full. The document is about 15 pages; that is fine.
  (Context discipline applies to datasets, not to the rulebook.)
- Note the page footer pattern (a `.docx` filename followed by a page
  number). Never include footer text in a quote.

### Step 3: Enumerate every clause and table row

Walk the document in order and list every numbered clause (`4.3`, `7.4.2`,
`10.7.9.1` …) and every row of every appendix table. Each one ends up in
exactly one of `rules` or `excluded`. Do not skip any; the excluded list is
how the human checks that nothing was missed.

### Step 4: Classify: testable or excluded

A clause is **testable** when, given a specific contract or payment and the
council's records, an auditor could answer yes/no whether it was followed.
It must contain at least one of:

| Type | Signal | Example |
| --- | --- | --- |
| `threshold` | A monetary band that triggers a process | Appendix B rows |
| `required-action` | "must", "shall", "no … shall", "is required" attached to a concrete action or record | written evidence of all purchases |
| `approver` | Names who must approve, authorise, or decide | Appendix A rows; waiver approvals |
| `anti-avoidance` | Prohibits splitting, disaggregating, or structuring to avoid a threshold or process | the no-artificial-splitting clause |

**Exclude** (with a one-line reason) clauses that are:

- definitions, purpose, scope, or legal-basis text;
- principles or values with no concrete action ("presumption in favour of
  competition", "fair treatment");
- discretionary ("should consider", "may", "care must be taken", "advice
  should be sought") unless the discretion is itself gated by a named
  approver, in which case it is an `approver` rule;
- delegations to external documents whose content is not in the PDF
  (intranet guidance, the Procurement Legislation itself); the *obligation to
  follow* them is not testable without the external text;
- duplicates of a rule already captured (e.g. a prose clause restating an
  appendix row). Keep the more specific one and exclude the other with reason
  `"duplicate of CPR-NN"`.

When genuinely unsure, exclude with reason starting `"ambiguous: "`. Never
guess.

### Step 5: Build each rule entry

Fields (all present; use `null` when not applicable):

```json
{
  "rule_id": "CPR-07",
  "clause": "App B row B1",
  "page": 12,
  "type": "threshold",
  "scope": "goods-services",
  "condition": "goods or services contract, total value £25,000 or more and below the statutory Threshold",
  "threshold_low": 25000,
  "threshold_low_inclusive": true,
  "threshold_high": null,
  "threshold_high_inclusive": false,
  "threshold_high_ref": "STATUTORY_THRESHOLD_GOODS_SERVICES",
  "required_action": "send invitations to quote via the Procurement Portal to at least three appropriate sources, including at least one SME or VCSE and one local supplier where appropriate and possible; publish a contract notice on the CDP",
  "approver": null,
  "evidence_source": "spend-data",
  "verbatim_quote": "Invitations to quote must be sent via the Procurement Portal to at least three appropriate sources, including at least one SME* or VCSE* organisation and one local supplier ****(where appropriate and possible**)."
}
```

Field rules:

- `rule_id`: `CPR-NN`, zero-padded, in document order.
- `clause`: the clause number as printed (`"6.16"`), or `"App A row 2"`,
  `"App B row B1"`, `"App C row E"` for table rows. Rows are numbered by the
  letter/number printed in the table's first column; where none, count from 1.
- `page`: the PDF page (1-based) where the quote appears. The verifier checks
  this.
- `type`: one of `threshold`, `required-action`, `approver`, `anti-avoidance`.
  A rule may have thresholds and an approver regardless of its type; `type`
  is the primary reason the rule is testable.
- `scope`: `goods-services`, `works-concession-light-touch`, or `all`.
- `threshold_low` / `threshold_high`: the boundary figures **as printed in
  the document**, as GBP integers (£2.5million → `2500000`;
  `£24,999.99` → `25000` with `threshold_low_inclusive: true`, because "more
  than £24,999.99" means £25,000 and above). Record inclusivity in the
  `_inclusive` booleans rather than adjusting the figure. Open-ended → `null`.
- `threshold_high_ref` / `threshold_low_ref`: when a bound is a named
  external figure ("the Threshold", "the relevant Procurement Legislation
  threshold") set the numeric field to `null` and put a parameter name here.
  Declare every parameter name in the top-level `parameters` object.
- `required_action`: paraphrase, one sentence, imperative mood.
- `approver`: the role(s) as named in the text, or `null`.
- `evidence_source`: what could test it. `spend-data` (payments CSV),
  `contracts-register` (Contracts Finder export), `council-records` (needs
  internal files: reports, approvals, contract files). Pick the most public
  source that could test the rule.
- `verbatim_quote`: see Step 6.

### Step 6: Verbatim quotes

- Copy the complete sentence(s) that state the rule from the **plain** text
  file. Join line breaks with a single space; change nothing else. Keep the
  document's curly quotes, `£`, asterisks, en dashes, and typos exactly.
- A quote may span several lines and several sentences but must not straddle
  a page footer. Bulleted lists: quote the item text only; the verifier
  ignores bullet glyphs, page footers, and differences in whitespace or
  curly-vs-straight quote characters, nothing else.
- For a table row, quote the cell that states the obligation (the "Award
  Procedure" or "Delegated decision" cell). Put the band text in `condition`,
  not in the quote, unless it is in the same cell.
- Minimum: one full sentence. Maximum: the clause or cell.

### Step 7: Top-level file structure

```json
{
  "source": {
    "file": "data/contract-rules.pdf",
    "title": "<title as printed>",
    "version": "<as printed, or null>",
    "pages": 15,
    "extracted_on": "YYYY-MM-DD",
    "extraction_tool": "pdftotext (poppler)"
  },
  "parameters": {
    "STATUTORY_THRESHOLD_GOODS_SERVICES": {
      "value": null,
      "description": "Procurement Act 2023 threshold for goods and services, sub-central authorities",
      "defined_by": "clause 1.4 refers to the Procurement Legislation and the Procurement intranet page",
      "note": "Not stated in the PDF. Auditor to supply the figure and its source before spend-analyst runs."
    }
  },
  "notes": [
    "Document-level observations: internal contradictions, blanks, drafting errors. One string each, citing clauses."
  ],
  "rules": [ ... ],
  "excluded": [
    { "clause": "2.1", "page": 2, "reason": "purpose statement; no testable obligation" }
  ]
}
```

- `parameters` values are always `null` at extraction. Do not fill them from
  memory or the web; the figure must come from the auditor with a citation.
- `notes` is for things the auditor should know but that are not rules: e.g.
  two clauses that disagree on whether contract value includes VAT, or
  placeholders like `Part []` left in the text. Cite the clauses.

### Step 8: Verify, then fix until clean

```bash
python3 .claude/skills/extract-rules/verify_quotes.py outputs/rules.json data/contract-rules.pdf
```

The verifier checks: JSON parses; required fields present with the right
types; `rule_id`s unique and sequential; every `threshold_*_ref` is declared
in `parameters`; every `verbatim_quote` is found in the PDF text
(whitespace-normalised, footers removed); the `page` field matches the page
where the quote was found. Fix every failure by re-reading the plain text and
re-run. Do not loosen a quote to make it pass; if a quote cannot be found,
the quote is wrong.

Exit code 0 with `ALL CHECKS PASSED` is required before reporting.

### Step 9: Report to the user

In the final message give:

1. Counts: rules by type, excluded count, parameters awaiting values.
2. A compact table of rules: `rule_id`, `clause`, `type`, one-line condition.
3. The parameters the auditor must supply, and why.
4. Anything in `notes`.
5. A reminder that the human step is to spot-check quotes against the PDF
   (suggest three: one prose clause, one appendix row, one with a threshold).

## Not this skill's job

- Rating risk, testing data, or interpreting whether the council complies.
- Filling in statutory threshold figures.
- Editing anything under `data/`.
