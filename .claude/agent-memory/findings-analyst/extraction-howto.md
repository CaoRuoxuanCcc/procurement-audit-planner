---
name: committee-pdf-extraction-howto
description: How-to lessons for quoting committee PDFs so verify_history.py passes (layout-line quoting, Table 1 / Figure 4 quirks)
metadata:
  type: feedback
---

Build history.json with a generator script (scratchpad) that pulls quotes as WHOLE normalised layout lines (`pdftotext -layout -f N -l N`, collapse whitespace, drop empty lines) located by a unique substring; fail loudly if not unique.

**Why:** hand-typed fragments of multi-column table lines often don't match; whole layout lines always match the verifier's page-normalised text. Verifier passed first run with this approach.

**How to apply:**
- Strategy Table 1 (p14): cells interleave across columns; quote rows by layout line-index ranges (one source per physical line) rather than substrings.
- Figure 4 (p21) layout lines interleave three columns; review-frequency text ("Six monthly ... Ethics Committee") is contiguous only in plain mode.
- Bullet glyphs stay inside layout lines; include "•" in the search substring when the line has one.
- Plain mode keeps table *cells* contiguous (appetite Table 3, Sources of Risk table) — quote cell text from plain, row/column assignment from layout.
- Run `scripts/test_verify_history.py` too; it confirms the verifier itself is unchanged.
