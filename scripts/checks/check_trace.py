#!/usr/bin/env python3
"""QA check: traceability, read from the rendered documents.

- Every rule in rules.json is cited by a rated risk (risk-register.md), a
  control (risk-control-matrix.md) or a test (audit-program.md), or is listed
  under "Rules not tested" in audit-program.md with a reason.
- Every register risk has an auditor decision. Every approved (APPROVE /
  AMEND) risk appears in the matrix and the program, and has at least one
  control that cites a rule and is tested by a test present in the program.
  No rejected risk appears in the matrix or the program.
- Every High risk (band naming High or Extreme) is in scope, or is REJECTed
  with a reason that the planning memo records in its out-of-scope table.
- outputs/challenges.md exists; every challenge row cites evidence
  ([rule:...], [metric:...] or [history:...]) and has a closed status
  (resolved, declined, for the auditor); none is open.

Run: .venv/bin/python -I scripts/checks/check_trace.py [--out-dir D]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import Stop, args, md_rows, read_json, read_text, run, split_row  # noqa: E402

RULE_REF = re.compile(r"\[(CPR-\d+)\]")
EVIDENCE = re.compile(r"\[(?:rule|metric|history):[^\]]+")
HIGH = re.compile(r"\b(?:High|Extreme)\b")
CLOSED = ("resolved", "declined", "for the auditor")


def sections(text, level, pattern):
    """{id: body} for headings like '## R-01 ...' (level 2) or '### T-01.1 ...' (level 3)."""
    hs = "#" * level
    out = {}
    parts = re.split(rf"^(?={hs} )", text, flags=re.M)
    for p in parts:
        m = re.match(rf"{hs} ({pattern})\b", p)
        if m:
            body = re.split(rf"^#{{1,{level}}} ", p[len(m.group(0)):], maxsplit=1, flags=re.M)[0]
            out[m.group(1)] = body
    return out


def main():
    a = args(__doc__.split("\n")[0])

    def body():
        out = a.out_dir
        rules = [r["rule_id"] for r in read_json(os.path.join(out, "rules.json")).get("rules", [])]
        reg = read_text(os.path.join(out, "risk-register.md"))
        com = read_text(os.path.join(out, "auditor-comments.md"))
        memo = read_text(os.path.join(out, "planning-memo.md"))
        rcm = read_text(os.path.join(out, "risk-control-matrix.md"))
        prog = read_text(os.path.join(out, "audit-program.md"))
        chal = read_text(os.path.join(out, "challenges.md"))
        failures, checked = [], 0

        # register risks and decisions
        decisions = {}
        for c in md_rows(com) or []:
            if re.fullmatch(r"R-\d{2}", c[0]) and len(c) >= 5:
                decisions[c[0]] = {"title": c[1], "rating": c[2], "decision": c[3].strip().upper(), "comment": c[4]}
        if not decisions:
            raise Stop("auditor-comments.md has no risk rows")
        m = re.search(r"^## Risks\s*$(.*?)(?=^## )", reg, re.S | re.M)
        if not m:
            raise Stop("risk-register.md has no '## Risks' section")
        reg_risks = {}
        for p in re.split(r"^(?=### R-\d{2})", m.group(1), flags=re.M):
            mm = re.match(r"### (R-\d{2})", p)
            if mm:
                reg_risks[mm.group(1)] = p
        for rid in sorted(set(reg_risks) ^ set(decisions)):
            failures.append(f"{rid} is in {'risk-register.md' if rid in reg_risks else 'auditor-comments.md'} only")
        in_scope, out_scope = [], []
        for rid, d in sorted(decisions.items()):
            checked += 1
            if d["decision"] in ("APPROVE", "AMEND"):
                in_scope.append(rid)
            elif d["decision"] == "REJECT":
                out_scope.append(rid)
            else:
                failures.append(f"{rid} has no auditor decision ({d['decision'] or 'blank'})")

        # matrix
        rcm_rows = [c for c in (md_rows(rcm) or []) if c and re.match(r"R-\d{2}\b", c[0])]
        controls = {}
        for c in rcm_rows:
            if len(c) < 5:
                failures.append(f"risk-control-matrix.md: row {c[0][:20]!r} has {len(c)} cells, expected 5")
                continue
            rid = c[0][:4]
            cm = re.search(r"\*\*(C-\d{2}\.\d+)\*\*", c[2])
            if not cm:
                failures.append(f"risk-control-matrix.md: {rid} row has no control id")
                continue
            controls[cm.group(1)] = {"risk": rid, "rules": set(RULE_REF.findall(c[2])),
                                     "tests": re.findall(r"T-\d{2}\.\d+", c[4])}
        prog_risks = sections(prog, 2, r"R-\d{2}")
        prog_tests = {}
        for rid, b in prog_risks.items():
            for tid, tb in sections(b, 3, r"T-\d{2}\.\d+").items():
                prog_tests[tid] = (rid, tb)
        for rid in in_scope:
            checked += 1
            mine = {cid: x for cid, x in controls.items() if x["risk"] == rid}
            if not mine:
                failures.append(f"{rid} is approved but has no control in risk-control-matrix.md")
            if rid not in prog_risks:
                failures.append(f"{rid} is approved but has no section in audit-program.md")
            tested = False
            for cid, x in mine.items():
                if not x["rules"]:
                    failures.append(f"{cid} ({rid}) cites no rule in risk-control-matrix.md")
                if not x["tests"]:
                    failures.append(f"{cid} ({rid}) is tested by no test in risk-control-matrix.md")
                for tid in x["tests"]:
                    if tid not in prog_tests:
                        failures.append(f"{cid} ({rid}) names {tid}, which has no section in audit-program.md")
                    elif prog_tests[tid][0] != rid:
                        failures.append(f"{cid} ({rid}) names {tid}, which audit-program.md places under "
                                        f"{prog_tests[tid][0]}")
                    elif re.search(rf"\b{re.escape(cid)}\b", prog_tests[tid][1]):
                        tested = True
                    else:
                        failures.append(f"{tid} in audit-program.md does not list {cid} as a control tested")
            if mine and not tested:
                failures.append(f"{rid} has no control with a test present in audit-program.md")
        for rid in out_scope:
            if any(x["risk"] == rid for x in controls.values()) or rid in prog_risks:
                failures.append(f"{rid} is out of scope (REJECT) but appears in the matrix or the program")
        for rid in set(prog_risks) - set(in_scope) - set(out_scope):
            failures.append(f"audit-program.md has a section for {rid}, which is not an approved register risk")

        # High risks
        memo_out = {}
        scope_rows = md_rows(memo, "Scope approved by the auditor") or []
        for c in scope_rows:
            if re.fullmatch(r"R-\d{2}", c[0]) and len(c) == 4:
                memo_out[c[0]] = c[3]
        for rid, d in decisions.items():
            band = d["rating"].split(",", 1)[1] if "," in d["rating"] else d["rating"]
            if not HIGH.search(band):
                continue
            checked += 1
            if rid in in_scope:
                continue
            if d["decision"] != "REJECT" or not d["comment"].strip():
                failures.append(f"{rid} is a High risk ({band.strip()}) neither in scope nor rejected with a reason")
            elif not memo_out.get(rid, "").strip():
                failures.append(f"{rid} is a High risk rejected by the auditor, but planning-memo.md does not record "
                                "its exclusion and reason in the out-of-scope table")

        # rules
        cited = set()
        for b in reg_risks.values():
            cited |= set(RULE_REF.findall(b))
        for x in controls.values():
            cited |= x["rules"]
        for _, tb in prog_tests.values():
            cited |= set(RULE_REF.findall(tb))
        not_tested = {}
        nt_rows = md_rows(prog, "Rules not tested")
        if nt_rows is None:
            failures.append("audit-program.md has no '## Rules not tested' section")
            nt_rows = []
        for c in nt_rows:
            for r in re.findall(r"CPR-\d+", c[0]):
                not_tested[r] = c[1] if len(c) > 1 else ""
        for r in rules:
            checked += 1
            if r in cited:
                continue
            if r not in not_tested:
                failures.append(f"{r} is not cited by a rated risk, a control or a test, and not listed as not tested")
            elif not not_tested[r].strip():
                failures.append(f"{r} is listed as not tested without a reason")
        for r in not_tested:
            if r not in rules:
                failures.append(f"audit-program.md lists {r} as not tested, but it is not in rules.json")

        # challenges
        lines = chal.splitlines()
        hdr_i = next((i for i, ln in enumerate(lines) if ln.startswith("|") and
                      "Status" in split_row(ln) and "#" in split_row(ln)), None)
        if hdr_i is None:
            failures.append("challenges.md has no challenge table (a header with '#' and 'Status')")
        else:
            hdr = split_row(lines[hdr_i])
            si = hdr.index("Status")
            n = 0
            for ln in lines[hdr_i + 2:]:
                if not ln.startswith("|"):
                    break
                c = split_row(ln)
                n += 1
                checked += 1
                cid = c[0] if c else "?"
                if not EVIDENCE.search(ln):
                    failures.append(f"challenges.md #{cid} cites no evidence ([rule:], [metric:] or [history:])")
                st = c[si].strip().lower() if si < len(c) else ""
                if st not in CLOSED:
                    failures.append(f"challenges.md #{cid} status is {st or 'blank'!r}; every row must be closed "
                                    f"({', '.join(CLOSED)})")
        return checked, failures, (f"{len(in_scope)} in scope, {len(out_scope)} out; {len(controls)} controls, "
                                   f"{len(prog_tests)} tests; {len(cited & set(rules))} rules cited, "
                                   f"{len(set(not_tested) - cited)} not tested")

    return run("check_trace", body)


if __name__ == "__main__":
    sys.exit(main())
