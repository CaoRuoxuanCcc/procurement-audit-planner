#!/usr/bin/env python3
"""Test build_pack.py on fixtures/ratings-two-risks.json and fixtures/plan-two-risks.json.

Each case builds a real register with build_register.py in its own temporary
directory (revision 0, both risks APPROVE, revision 1), then runs build_pack.py
against it with the real outputs/analytics.json, history.json, rules.json and
analytics-full/. outputs/ is not touched.

Run: .venv/bin/python -I .claude/skills/audit-program/test_build_pack.py
"""
import copy
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RA = os.path.join(os.path.dirname(HERE), "risk-assessment")
BUILD = os.path.join(HERE, "build_pack.py")
REGISTER = os.path.join(RA, "build_register.py")
sys.path.insert(0, RA)
from build_register import split_row  # noqa: E402

with open(os.path.join(HERE, "fixtures", "ratings-two-risks.json")) as f:
    RATINGS = json.load(f)
with open(os.path.join(HERE, "fixtures", "plan-two-risks.json")) as f:
    PLAN = json.load(f)
SPEND = {r["row_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "outputs", "analytics-full", "spend_clean.csv"),
                                                    newline="", encoding="utf-8"))}

failures, dirs = [], []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n     {detail[-1500:]}"))
    if not cond:
        failures.append(name)


def sh(args):
    r = subprocess.run([sys.executable, "-I"] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def decide(d, decisions):
    p = os.path.join(d, "auditor-comments.md")
    with open(p) as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        m = re.match(r"^\|\s*(R-\d{2})\s*\|", line)
        if m and m.group(1) in decisions:
            c = split_row(line)
            c[3], c[4] = decisions[m.group(1)]
            line = "| " + " | ".join(x.replace("|", "\\|") for x in c) + " |"
        out.append(line)
    with open(p, "w") as f:
        f.write("\n".join(out) + "\n")


def register(revision=True, decisions=None):
    """A temp dir holding a register built by build_register.py; revision 1 unless revision=False."""
    d = tempfile.mkdtemp(prefix="pack-test-")
    dirs.append(d)
    rp = os.path.join(d, "ratings.json")
    with open(rp, "w") as f:
        json.dump(RATINGS, f)
    code, out = sh([REGISTER, "--ratings", rp, "--out-dir", d])
    assert code == 0, out
    if not revision:
        return d
    decide(d, decisions or {"R-01": ("APPROVE", "Fixture."), "R-04": ("APPROVE", "Fixture.")})
    r = copy.deepcopy(RATINGS)
    r["revision"] = {"number": 1, "summary": "Applies the fixture decisions.", "changes": []}
    with open(rp, "w") as f:
        json.dump(r, f)
    code, out = sh([REGISTER, "--ratings", rp, "--out-dir", d])
    assert code == 0, out
    return d


def pack(d, plan=None, extra=(), gate=False):
    pp = os.path.join(d, "plan.json")
    with open(pp, "w") as f:
        json.dump(PLAN if plan is None else plan, f)
    args = [BUILD, "--ratings", os.path.join(d, "ratings.json"), "--comments", os.path.join(d, "auditor-comments.md"),
            "--state", os.path.join(d, "risk-register.state.json"), "--plan", pp, "--out-dir", d, *extra]
    return sh(args + (["--gate"] if gate else []))


def read(d, name):
    with open(os.path.join(d, name)) as f:
        return f.read()


def broken(fn):
    p = copy.deepcopy(PLAN)
    fn(p)
    return p


def risk(p, rid):
    return next(r for r in p["risks"] if r["risk_id"] == rid)


# 1. The good fixture builds.
d = register()
code, out = pack(d, gate=True)
check("gate open on revision 1 with both risks approved", code == 0 and "GATE OPEN" in out, out)
code, out = pack(d)
check("good fixture builds (exit 0)", code == 0, out)
figs = json.load(open(os.path.join(d, "pack-figures.json"))) if code == 0 else {"pack": {"risks": {}, "tests": {}}}
P = figs["pack"]
check("R-01 rated from the council matrix (L3 × I3 → 9)", P["risks"].get("R-01", {}).get("score") == 9, str(P["risks"]))
check("R-04 rated from the council matrix (L3 × I2 → 6)", P["risks"].get("R-04", {}).get("score") == 6, str(P["risks"]))
check("sample size follows the score (9 → 15, 6 → 10)",
      (P["risks"]["R-01"]["sample_size"], P["risks"]["R-04"]["sample_size"]) == (15, 10), str(P["risks"]))
t11, t12, t41 = (P["tests"].get(t, {}) for t in ("T-01.1", "T-01.2", "T-04.1"))
check("T-01.1 draws the score-based size", t11.get("sample_units") == 15, str(t11))
check("T-01.2 one per supplier, systematic", t12.get("sample_units") == 15 and t12["eligible_units"] <= t12["population_units"], str(t12))
check("T-04.1 size 'all' takes every eligible unit", t41.get("takes_all") is True, str(t41))
samples = {}
for t in ("T-01.1", "T-01.2", "T-04.1"):
    p = os.path.join(d, "samples", f"{t}.csv")
    samples[t] = list(csv.DictReader(open(p, newline="", encoding="utf-8"))) if os.path.exists(p) else []
check("sample files written for the three draws", all(samples.values()), str({k: len(v) for k, v in samples.items()}))
check("no sample file for the walkthrough", not os.path.exists(os.path.join(d, "samples", "T-01.3.csv")))
check("every sampled transaction exists in spend_clean.csv with the same amount",
      all(r["row_id"] in SPEND and SPEND[r["row_id"]]["amount"] == r["amount"] for v in samples.values() for r in v))
check("'largest' gives one transaction per unit", len(samples["T-04.1"]) == t41.get("sample_units"))
check("sampled value equals the sum of the sample file",
      abs(sum(float(r["amount"]) for r in samples["T-01.1"]) - t11.get("sampled_value_gbp", -1)) < 0.01)
memo = read(d, "planning-memo.md") if code == 0 else ""
prog = read(d, "audit-program.md") if code == 0 else ""
rcm = read(d, "risk-control-matrix.md") if code == 0 else ""
check("memo placeholders filled from pack figures",
      f"takes {t11.get('sample_units')} of {t11.get('population_units')} groups" in memo, memo[:2000])
check("memo has no placeholder or warning left", "{{" not in memo + prog + rcm and "⚠" not in memo + prog + rcm)
check("memo carries the missing-notices caveat (expired_notice_spend)", "(expired_notice_spend) Notices may be missing" in memo)
check("memo lists the scope and the indicator-language note",
      "## Scope approved by the auditor" in memo and "risk indicators to investigate" in memo)
check("matrix lists every control with its tests", "**C-01.1**" in rcm and "T-01.1, T-01.2, T-01.3" in rcm, rcm)
check("program ends with the PBC list", prog.rstrip().split("\n## ")[-1].startswith("PBC list"), prog[-800:])
check("program resolves the threshold filter from rules.json", "CPR-49 threshold_low (£25,000)" in prog, prog[:3000])
check("pack-figures lists the placeholders it filled",
      any(x["path"] == '$.pack.tests["T-01.1"].sample_units' for x in figs.get("placeholders", [])))

# 1b. Deterministic: a second build gives identical samples.
first = {t: read(d, f"samples/{t}.csv") for t in samples}
code, out = pack(d)
check("rebuild gives identical samples", code == 0 and all(read(d, f"samples/{t}.csv") == first[t] for t in first), out)

# 2. Gate: the register is not a revision.
d0 = register(revision=False)
code, out = pack(d0, gate=True)
check("gate fails on revision 0 (not a revision)", code == 1 and "not a revision" in out, out)

# 3. Gate: an undecided risk.
d1 = register()
decide(d1, {"R-04": ("", "")})
code, out = pack(d1, gate=True)
check("gate fails on an undecided risk", code == 1 and "R-04 has no auditor decision" in out, out)
code, out = pack(d1)
check("full build also stops at the gate", code == 1 and "GATE CLOSED" in out and not os.path.exists(
    os.path.join(d1, "planning-memo.md")), out)

# 3b. Gate: a register risk missing from auditor-comments.md.
d2 = register()
with open(os.path.join(d2, "auditor-comments.md")) as f:
    txt = f.read()
with open(os.path.join(d2, "auditor-comments.md"), "w") as f:
    f.write("\n".join(l for l in txt.splitlines() if not l.startswith("| R-04 |")) + "\n")
code, out = pack(d2, gate=True)
check("gate fails on a register risk missing from auditor-comments.md",
      code == 1 and "R-04 is in the register but missing from auditor-comments.md" in out, out)

# 3c. Gate: a decision changed after the revision was built (not applied).
d3 = register()
decide(d3, {"R-04": ("REJECT", "Changed my mind.")})
code, out = pack(d3, gate=True)
check("gate fails on a decision not yet applied", code == 1 and "not applied in revision 1" in out, out)

# 4. A missing risk: an approved risk absent from the plan.
code, out = pack(d, broken(lambda p: p["risks"].pop()))
check("fails on an approved risk missing from the plan",
      code == 1 and "R-04 is approved (in scope) but missing from audit-plan.json" in out, out)

# 5. An uncited control.
code, out = pack(d, broken(lambda p: risk(p, "R-04")["controls"][0].update(
    description="Extensions are approved before spend continues past the original end date.")))
check("fails on a control that cites no rule", code == 1 and "C-04.1.description cites no rule" in out, out)

# 6. An unaccounted rule.
code, out = pack(d, broken(lambda p: p["rules_not_tested"][0]["rule_ids"].remove("CPR-62")))
check("fails on a rule neither cited nor listed as not tested",
      code == 1 and "not listed in rules_not_tested with a reason: CPR-62" in out, out)

# 7. More failures the builder must catch.
code, out = pack(d, broken(lambda p: risk(p, "R-01")["tests"].__setitem__(
    slice(None), [t for t in risk(p, "R-01")["tests"] if t["test_id"] == "T-01.2"])))
check("fails on a control with no test", code == 1 and "C-01.2 has no test" in out, out)
code, out = pack(d, broken(lambda p: risk(p, "R-04")["tests"][0].update(step="Obtain the extension approval.")))
check("fails on a test step that cites no rule or metric", code == 1 and "T-04.1.step cites no rule or metric" in out, out)
code, out = pack(d, broken(lambda p: p["memo"]["sections"][0].update(text="Some 45 groups were found [rule:CPR-07].")))
check("fails on a figure typed into the memo", code == 1 and "figure typed in prose '45'" in out, out)
code, out = pack(d, broken(lambda p: p["memo"]["sections"][0].update(text="These payments show fraud [rule:CPR-07].")))
check("fails on accusatory wording", code == 1 and "accusatory wording" in out, out)
code, out = pack(d, broken(lambda p: risk(p, "R-01")["tests"][0]["sample"]["filter"][1].update(value=25000)))
check("fails on a threshold typed into a filter", code == 1 and "rules.json threshold typed by hand" in out, out)
code, out = pack(d, broken(lambda p: risk(p, "R-01")["tests"][0]["sample"]["filter"][0].update(value=["no_such_tag"])))
check("fails on a filter that leaves nothing to sample", code == 1 and "leaves no rows" in out, out)
code, out = pack(d, broken(lambda p: p["memo"]["sections"][0].update(
    text="There are {{$.tests.split_purchases.general_procurement.no_such_metric}} groups.")))
check("fails on a placeholder that does not resolve", code == 1 and "does not resolve" in out, out)

# 8. A sampled transaction missing from spend_clean.csv.
af = tempfile.mkdtemp(prefix="pack-test-af-")
dirs.append(af)
for name in os.listdir(os.path.join(ROOT, "outputs", "analytics-full")):
    if name.endswith(".csv"):
        shutil.copy(os.path.join(ROOT, "outputs", "analytics-full", name), af)
gone = samples["T-04.1"][0]["row_id"] if samples["T-04.1"] else ""
with open(os.path.join(af, "spend_clean.csv"), newline="", encoding="utf-8") as f:
    rows = list(csv.reader(f))
with open(os.path.join(af, "spend_clean.csv"), "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(r for r in rows if r[0] != gone)
code, out = pack(d, extra=["--analytics-full", af])
check("fails on a sampled transaction not in spend_clean.csv", code == 1 and "is not in spend_clean.csv" in out, out)

for x in dirs:
    shutil.rmtree(x, ignore_errors=True)
print()
print(f"{'ALL TESTS PASSED' if not failures else f'{len(failures)} FAILED'}")
sys.exit(1 if failures else 0)
