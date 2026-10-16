#!/usr/bin/env python3
"""QA check: rule quotes.

1. Runs the extract-rules verifier (.claude/skills/extract-rules/verify_quotes.py)
   on outputs/rules.json against data/contract-rules.pdf: every verbatim_quote
   is in the PDF on its stated page, and the file is well formed.
2. Every rule quote excerpt in outputs/risk-register.md (its Citations table:
   `| CPR-xx | <clause>: "<quote>" | contract-rules.pdf pN |`) names a rule in
   rules.json, with the same clause and page, and the quote is that rule's
   verbatim_quote or a contiguous excerpt of it (whitespace aside).

Run: .venv/bin/python -I scripts/checks/check_quotes.py [--out-dir D] [--data-dir D]
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import ROOT, Stop, args, md_rows, need, read_json, read_text, run  # noqa: E402

VERIFIER = os.path.join(ROOT, ".claude", "skills", "extract-rules", "verify_quotes.py")
CELL_RE = re.compile(r'^(?P<clause>.+?): "(?P<quote>.*)"$', re.S)
SRC_RE = re.compile(r"^(?P<file>\S+) p(?P<page>\d+)$")


def ws(s):
    return re.sub(r"\s+", " ", s).strip()


def main():
    a = args(__doc__.split("\n")[0])

    def body():
        rules_path = need(os.path.join(a.out_dir, "rules.json"))
        pdf = need(os.path.join(a.data_dir, "contract-rules.pdf"))
        need(VERIFIER)
        failures, checked = [], 0
        r = subprocess.run([sys.executable, "-I", VERIFIER, rules_path, pdf], capture_output=True, text=True)
        out = r.stdout + r.stderr
        checked += 1
        if r.returncode != 0 or "ALL CHECKS PASSED" not in out:
            fails = [ln[6:] for ln in out.splitlines() if ln.startswith("FAIL: ")] or [out.strip()[-300:]]
            failures += [f"verify_quotes: {x}" for x in fails]
        rules = {x["rule_id"]: x for x in read_json(rules_path).get("rules", [])}
        reg = read_text(os.path.join(a.out_dir, "risk-register.md"))
        rows = md_rows(reg, "Citations")
        if rows is None:
            raise Stop("risk-register.md has no '## Citations' section")
        n_quotes = 0
        for cells in rows:
            if len(cells) < 3 or not re.fullmatch(r"CPR-\d+", cells[0]):
                continue
            n_quotes += 1
            checked += 1
            rid = cells[0]
            rule = rules.get(rid)
            m, s = CELL_RE.match(cells[1]), SRC_RE.match(cells[2])
            if rule is None:
                failures.append(f"risk-register.md {rid}: no such rule_id in rules.json")
                continue
            if not m:
                failures.append(f"risk-register.md {rid}: quote cell is not 'clause: \"quote\"': {cells[1][:80]!r}")
                continue
            if m.group("clause") != rule["clause"]:
                failures.append(f"risk-register.md {rid}: clause {m.group('clause')!r} ≠ rules.json {rule['clause']!r}")
            q = ws(m.group("quote"))
            if not q or q not in ws(rule["verbatim_quote"]):
                failures.append(f"risk-register.md {rid}: quote is not the rules.json verbatim_quote or an excerpt "
                                f"of it: {m.group('quote')[:100]!r}")
            if not s or int(s.group("page")) != rule["page"]:
                failures.append(f"risk-register.md {rid}: source {cells[2]!r} ≠ rules.json page {rule['page']}")
        if n_quotes == 0:
            failures.append("risk-register.md Citations table has no rule quotes")
        return checked, failures, f"{len(rules)} rules verified against the PDF; {n_quotes} register excerpts"

    return run("check_quotes", body)


if __name__ == "__main__":
    sys.exit(main())
