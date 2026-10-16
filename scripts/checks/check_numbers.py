#!/usr/bin/env python3
"""QA check: figures in the pack.

Every figure in planning-memo.md, risk-control-matrix.md and audit-program.md
that has a £ sign or three or more digits must be a value in analytics.json,
pack-figures.json, rules.json or outputs/samples/*.csv, at the precision shown
(£2,112,742 matches 2112741.83; 45% matches a share of 0.452).

Skipped: inline code spans (paths, file names, metric paths), row ids, ids
(CPR-07, R-01, C-01.1, T-01.1, PBC-01, AUD-11), dates, years, and clause,
section, paragraph, row, table and page references. Digits inside a word
(Over500, P02) are not figures.

Run: .venv/bin/python -I scripts/checks/check_numbers.py [--out-dir D]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import PACK_DOCS, ROW_ID_RE, args, read_csv, read_json, read_text, run  # noqa: E402

CODE_RE = re.compile(r"`[^`]*`")
ID_RE = re.compile(r"\b[A-Z]{1,5}-\d+(?:\.\d+)?\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T[\d:.+-]+)?\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
REF_RE = re.compile(r"\b(?:clauses?|paras?|paragraphs?|sections?|pages?|rows?|tables?|figures?|appendix|app|"
                    r"part|phase|step)\.?\s+[A-Z]?\d+(?:\.\d+)*[a-z]?\b|\bpp?\.?\s?\d+(?:\s?[-–]\s?\d+)?\b", re.I)
YEAR_RE = re.compile(r"(?<![£\d,.])\b(?:19|20)\d\d(?:\s?[/–-]\s?\d{2,4})?\b(?![,.]\d)")
GBP_RE = re.compile(r"£\s?(\d[\d,]*(?:\.\d+)?)\s?([km](?![a-z]))?", re.I)
NUM_RE = re.compile(r"(?<![\w.,£])(\d[\d,]*(?:\.\d+)?)(%?)(?![\w])")


def numbers(o, out):
    """Every numeric leaf (and numeric dict key) in a JSON document."""
    if isinstance(o, bool) or o is None:
        return
    if isinstance(o, (int, float)):
        out.append(float(o))
    elif isinstance(o, dict):
        for k, v in o.items():
            try:
                out.append(float(k))
            except ValueError:
                pass
            numbers(v, out)
    elif isinstance(o, list):
        for v in o:
            numbers(v, out)


def strip_skipped(line):
    for rx in (CODE_RE, ROW_ID_RE, ID_RE, DATE_RE, REF_RE, YEAR_RE):
        line = rx.sub(" ", line)
    return line


def figures(line):
    """[(token, value_text, decimals, scale, is_pct)] for the figures in one line."""
    t = strip_skipped(line)
    out = []
    for m in GBP_RE.finditer(t):
        txt = m.group(1).rstrip(",.")
        scale = {"k": 1e3, "m": 1e6}.get((m.group(2) or "").lower(), 1)
        out.append((m.group(0).strip(), txt, scale, False))
    t = GBP_RE.sub(" ", t)
    for m in NUM_RE.finditer(t):
        txt = m.group(1).rstrip(",.")
        if sum(c.isdigit() for c in txt) >= 3:
            out.append((m.group(0), txt, 1, m.group(2) == "%"))
    return out


def main():
    a = args(__doc__.split("\n")[0])

    def body():
        vals = []
        for name in ("analytics.json", "pack-figures.json", "rules.json"):
            numbers(read_json(os.path.join(a.out_dir, name)), vals)
        pct_vals = list(vals)
        files = sorted(glob.glob(os.path.join(a.out_dir, "samples", "*.csv")))
        for p in files:
            for row in read_csv(p):
                for v in row.values():
                    try:
                        vals.append(float(str(v).replace(",", "")))
                    except (TypeError, ValueError):
                        pass
        known = {d: {f"{v:.{d}f}" for v in vals} for d in range(4)}
        known_pct = {d: {f"{v * 100:.{d}f}" for v in pct_vals} for d in range(4)}
        failures, checked = [], 0
        for doc in PACK_DOCS:
            text = read_text(os.path.join(a.out_dir, doc))
            for ln, line in enumerate(text.splitlines(), 1):
                for token, txt, scale, pct in figures(line):
                    checked += 1
                    plain = txt.replace(",", "")
                    d = len(plain.split(".")[1]) if "." in plain else 0
                    if d > 3:
                        failures.append(f"{doc}:{ln} {token!r}: more than three decimals")
                        continue
                    if scale != 1:
                        ok = any(f"{v / scale:.{d}f}" == f"{float(plain):.{d}f}" for v in vals)
                    else:
                        ok = f"{float(plain):.{d}f}" in (known_pct[d] if pct else known[d]) or (
                            pct and f"{float(plain):.{d}f}" in known[d])
                    if not ok:
                        ctx = line.strip()
                        i = ctx.find(token.strip())
                        snippet = ctx[max(0, i - 60): i + len(token) + 40]
                        failures.append(f"{doc}:{ln} {token.strip()!r} is not a value in analytics.json, "
                                        f"pack-figures.json, rules.json or samples/*.csv: …{snippet}…")
        return checked, failures, f"{len(files)} sample file(s) indexed"

    return run("check_numbers", body)


if __name__ == "__main__":
    sys.exit(main())
