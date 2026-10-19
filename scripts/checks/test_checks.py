#!/usr/bin/env python3
"""Test the QA checks on the current outputs and on a fixture pack with planted faults.

1. Current outputs: each check runs and gives a RESULT. check_quotes must PASS;
   the other three need a built pack, so until the planner has built one they
   must STOP and name the missing file (once a pack exists they must PASS).
2. Fixture: a register and pack built in a temporary directory from the
   audit-program fixtures (two risks, both approved) plus
   fixtures/challenges-good.md. All four checks must PASS on it; then each
   planted fault (a bad figure, a missing row, and others) must fail exactly
   the check that owns it. outputs/ and data/ are not touched.

Run: .venv/bin/python -I scripts/checks/test_checks.py
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
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "outputs")
FIXTURE_SOURCE = os.path.join(HERE, "fixtures", "baseline")
SKILLS = os.path.join(ROOT, ".claude", "skills")
AP = os.path.join(SKILLS, "audit-program")
REGISTER = os.path.join(SKILLS, "risk-assessment", "build_register.py")
sys.path.insert(0, HERE)
from qa_common import split_row  # noqa: E402

CHECKS = ("check_quotes", "check_numbers", "check_trace", "check_samples")
failures, dirs = [], []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n     {str(detail)[-1500:]}"))
    if not cond:
        failures.append(name)


def py(args):
    r = subprocess.run([sys.executable, "-I"] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def result(check_name, out_dir):
    code, out = py([os.path.join(HERE, f"{check_name}.py"), "--out-dir", out_dir])
    line = next((ln for ln in reversed(out.splitlines()) if ln.startswith("RESULT ")), None)
    return code, (json.loads(line[7:]) if line else {"status": "NONE", "failures": [out[-500:]]})


def statuses(out_dir):
    return {c: result(c, out_dir)[1] for c in CHECKS}


# ------------------------------------------------ 1. current outputs
cur = statuses(OUT)
check("current outputs: check_quotes PASS", cur["check_quotes"]["status"] == "PASS", cur["check_quotes"])
pack_built = os.path.exists(os.path.join(OUT, "planning-memo.md"))
for c in CHECKS[1:]:
    r = cur[c]
    if pack_built:
        check(f"current outputs: {c} PASS", r["status"] == "PASS", r)
    else:
        check(f"current outputs: {c} STOPs on the missing pack, naming the file",
              r["status"] == "STOP" and "not found" in r["failures"][0], r)
print(f"     (current outputs: " + ", ".join(f"{c} {cur[c]['status']}" for c in CHECKS) + ")")


# ------------------------------------------------ 2. fixture pack
def build_fixture():
    d = tempfile.mkdtemp(prefix="qa-test-")
    dirs.append(d)
    for f in ("rules.json", "analytics.json", "history.json"):
        shutil.copy(os.path.join(FIXTURE_SOURCE, f), d)
    os.makedirs(os.path.join(d, "analytics-full"))
    shutil.copy(os.path.join(FIXTURE_SOURCE, "analytics-full", "spend_clean.csv"), os.path.join(d, "analytics-full"))
    with open(os.path.join(AP, "fixtures", "ratings-two-risks.json")) as f:
        ratings = json.load(f)
    rp = os.path.join(d, "risk-ratings.json")
    inputs = ["--analytics", os.path.join(d, "analytics.json"), "--history", os.path.join(d, "history.json"),
              "--rules", os.path.join(d, "rules.json")]
    with open(rp, "w") as f:
        json.dump(ratings, f)
    code, out = py([REGISTER, "--ratings", rp, "--out-dir", d] + inputs)
    assert code == 0, out
    cp = os.path.join(d, "auditor-comments.md")
    lines = []
    for line in open(cp).read().splitlines():
        if re.match(r"^\| R-\d{2} \|", line):
            c = split_row(line)
            c[3], c[4] = "APPROVE", "Fixture."
            line = "| " + " | ".join(c) + " |"
        lines.append(line)
    open(cp, "w").write("\n".join(lines) + "\n")
    ratings["revision"] = {"number": 1, "summary": "Applies the fixture decisions.", "changes": []}
    with open(rp, "w") as f:
        json.dump(ratings, f)
    code, out = py([REGISTER, "--ratings", rp, "--out-dir", d] + inputs)
    assert code == 0, out
    shutil.copy(os.path.join(AP, "fixtures", "plan-two-risks.json"), os.path.join(d, "audit-plan.json"))
    code, out = py([os.path.join(AP, "build_pack.py"), "--ratings", rp, "--comments", cp,
                    "--state", os.path.join(d, "risk-register.state.json"), "--plan", os.path.join(d, "audit-plan.json"),
                    "--analytics-full", os.path.join(FIXTURE_SOURCE, "analytics-full"), "--out-dir", d] + inputs)
    assert code == 0, out
    shutil.copy(os.path.join(HERE, "fixtures", "challenges-good.md"), os.path.join(d, "challenges.md"))
    return d


def planted(fn):
    """A fresh copy of the good fixture with one fault planted by fn(d)."""
    d = tempfile.mkdtemp(prefix="qa-test-")
    dirs.append(d)
    shutil.rmtree(d)
    shutil.copytree(GOOD, d)
    fn(d)
    return statuses(d)


def edit(d, name, fn):
    p = os.path.join(d, name)
    with open(p, encoding="utf-8") as f:
        txt = f.read()
    new = fn(txt)
    assert new != txt, f"plant did not change {name}"
    with open(p, "w", encoding="utf-8") as f:
        f.write(new)


def only_fails(res, owner, needle):
    others = {c: r["status"] for c, r in res.items() if c != owner}
    hit = any(needle in x for x in res[owner]["failures"])
    return res[owner]["status"] == "FAIL" and hit and all(s == "PASS" for s in others.values()), \
        {c: (r["status"], r["failures"][:3]) for c, r in res.items()}


GOOD = build_fixture()
good = statuses(GOOD)
for c in CHECKS:
    check(f"fixture: {c} PASS", good[c]["status"] == "PASS", good[c])
check("fixture: check_numbers checked figures", good["check_numbers"]["checked"] > 0, good["check_numbers"])
check("fixture: check_samples checked transactions", good["check_samples"]["checked"] > 0, good["check_samples"])
code, out = py([os.path.join(HERE, "run_checks.py"), "--out-dir", GOOD, "--label", "v1"])
check("fixture: run_checks prints the table and READY FOR SIGN-OFF",
      code == 0 and "| check_trace | PASS |" in out and out.rstrip().endswith("VERDICT: READY FOR SIGN-OFF"), out)


# planted bad figure: one £ figure in the memo off by one pound
def bad_figure(d):
    def f(txt):
        m = re.search(r"£(\d[\d,]*)", txt.split("## Sampling summary")[1])
        v = int(m.group(1).replace(",", "")) + 1
        return txt.replace(m.group(0), f"£{v:,}", 1)
    edit(d, "planning-memo.md", f)


res = planted(bad_figure)
ok, info = only_fails(res, "check_numbers", "is not a value in")
check("planted bad figure: check_numbers fails, the others pass", ok, info)
code, out = py([os.path.join(HERE, "run_checks.py"), "--out-dir", dirs[-1]])
check("planted bad figure: run_checks verdict BLOCKED", code == 1 and out.rstrip().endswith("VERDICT: BLOCKED"), out)


# planted missing row: a sampled transaction whose sheet row does not exist
def missing_row(d):
    edit(d, "samples/T-04.1.csv", lambda t: re.sub(r"(\|Data to publish\|R)\d+", r"\g<1>99999", t, count=1))


ok, info = only_fails(planted(missing_row), "check_samples", "not in spend_clean.csv")
check("planted missing row: check_samples fails, the others pass", ok, info)


# missing from spend_clean.csv only: the sample row is real but the cleaned data lost it
def dropped_from_clean(d):
    rid = next(csv.DictReader(open(os.path.join(d, "samples", "T-04.1.csv"))))["row_id"]
    edit(d, "analytics-full/spend_clean.csv",
         lambda t: "\n".join(ln for ln in t.split("\n") if not ln.startswith(rid + ",")))


ok, info = only_fails(planted(dropped_from_clean), "check_samples", "not in spend_clean.csv")
check("row missing from spend_clean.csv: check_samples fails", ok, info)


# spend_clean.csv and the sample agree with each other but not with the workbook
def off_workbook(d):
    row = next(csv.DictReader(open(os.path.join(d, "samples", "T-04.1.csv"))))
    rid, amt = row["row_id"], row["amount"]
    new = f"{float(amt) + 1:.2f}"
    edit(d, "analytics-full/spend_clean.csv",
         lambda t: "\n".join(re.sub(rf",{re.escape(amt)},", f",{new},", ln) if ln.startswith(rid + ",") else ln
                             for ln in t.split("\n")))
    edit(d, "samples/T-04.1.csv", lambda t: t.replace(f",{amt}\n", f",{new}\n", 1))


res = planted(off_workbook)
ok, info = only_fails(res, "check_samples", "workbook amount")
check("amount that differs from the council workbook: check_samples fails", ok, info)


def open_challenge(d):
    edit(d, "challenges.md", lambda t: t.replace("| resolved | v2 |", "| open | n/a |", 1))


ok, info = only_fails(planted(open_challenge), "check_trace", "every row must be closed")
check("open challenge: check_trace fails", ok, info)


def uncited_challenge(d):
    edit(d, "challenges.md", lambda t: t.replace(" [rule:CPR-58] [pack:C-04.1]", " [pack:C-04.1]", 1))


ok, info = only_fails(planted(uncited_challenge), "check_trace", "cites no evidence")
check("challenge row without evidence: check_trace fails", ok, info)


def unaccounted_rule(d):
    edit(d, "audit-program.md", lambda t: t.replace(", CPR-62 |", " |", 1))


ok, info = only_fails(planted(unaccounted_rule), "check_trace", "CPR-62 is not cited")
check("rule dropped from 'Rules not tested': check_trace fails", ok, info)


def untested_control(d):
    edit(d, "risk-control-matrix.md", lambda t: re.sub(r"(\*\*C-04\.1\*\*.*\| )T-04\.1 \|", r"\1 |", t))


ok, info = only_fails(planted(untested_control), "check_trace", "C-04.1 (R-04) is tested by no test")
check("control with no test in the matrix: check_trace fails", ok, info)


def no_challenges(d):
    os.remove(os.path.join(d, "challenges.md"))


res = planted(no_challenges)
check("missing challenges.md: check_trace stops", res["check_trace"]["status"] == "STOP"
      and "challenges.md not found" in res["check_trace"]["failures"][0], res["check_trace"])


def bad_quote(d):
    # Rule ids follow each extraction's numbering, so plant on CPR-07's own quote.
    with open(os.path.join(d, "rules.json")) as f:
        words = next(r["verbatim_quote"] for r in json.load(f)["rules"] if r["rule_id"] == "CPR-07").split()
    edit(d, "risk-register.md", lambda t: t.replace(" ".join(words[:6]), " ".join(words[:4] + words[5:6]), 1))


ok, info = only_fails(planted(bad_quote), "check_quotes", "CPR-07: quote is not")
check("altered rule quote in the register: check_quotes fails", ok, info)

for x in dirs:
    shutil.rmtree(x, ignore_errors=True)
print()
print("ALL TESTS PASSED" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
