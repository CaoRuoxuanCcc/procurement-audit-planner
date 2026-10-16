#!/usr/bin/env python3
"""Test build_register.py on fixtures/ratings-good-and-broken.json.

The fixture holds one good risk (R-01) and one broken risk (R-02). Every case
runs the builder against the real outputs/analytics.json, history.json and
rules.json, writing into its own temporary directory; outputs/ is not touched.

Run: .venv/bin/python -I .claude/skills/risk-assessment/test_build_register.py
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
BUILD = os.path.join(HERE, "build_register.py")
FIXTURE = os.path.join(HERE, "fixtures", "ratings-good-and-broken.json")
CHOICES = os.path.join(HERE, "scoring_choices.json")
sys.path.insert(0, HERE)
from build_register import split_row  # noqa: E402

with open(FIXTURE) as f:
    BASE = json.load(f)
with open(os.path.join(ROOT, "outputs", "history.json")) as f:
    HISTORY = json.load(f)
with open(os.path.join(ROOT, "outputs", "analytics.json")) as f:
    ANALYTICS = json.load(f)

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n     {detail}"))
    if not cond:
        failures.append(name)


def cell(L, I):
    for row in HISTORY["risk_scoring_method"]["matrix"]:
        if row["impact_score"] == I:
            for c in row["cells"]:
                if c["likelihood_score"] == L:
                    return c["score"]


def run(d, ratings, choices=None):
    rp = os.path.join(d, "ratings.json")
    with open(rp, "w") as f:
        json.dump(ratings, f)
    args = [sys.executable, "-I", BUILD, "--ratings", rp, "--out-dir", d]
    if choices is not None:
        cp = os.path.join(d, "choices.json")
        with open(cp, "w") as f:
            json.dump(choices, f)
        args += ["--choices", cp]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def read(d, name):
    with open(os.path.join(d, name)) as f:
        return f.read()


def decide(d, rid, decision, comment):
    p = os.path.join(d, "auditor-comments.md")
    out = []
    for line in read(d, "auditor-comments.md").splitlines():
        if re.match(rf"^\|\s*{rid}\s*\|", line):
            c = split_row(line)
            c[3], c[4] = decision, comment
            line = "| " + " | ".join(x.replace("|", "\\|") for x in c) + " |"
        out.append(line)
    with open(p, "w") as f:
        f.write("\n".join(out) + "\n")


def good_only():
    r = copy.deepcopy(BASE)
    r["risks"] = [x for x in r["risks"] if x["risk_id"] == "R-01"]
    return r


def section(reg, rid):
    m = re.search(rf"^### {rid} .*?(?=^### |^## )", reg, re.S | re.M)
    return m.group(0) if m else ""


def fresh():
    return tempfile.mkdtemp(prefix="rr-test-")


dirs = []


def new_dir():
    d = fresh()
    dirs.append(d)
    return d


# 1. The fixture: R-01 rated with figures and score filled in, R-02 dropped.
d = new_dir()
code, out = run(d, BASE)
check("fixture builds (exit 0)", code == 0, out)
reg = read(d, "risk-register.md") if code == 0 else ""
s1 = section(reg, "R-01")
gp = ANALYTICS["tests"]["split_purchases"]["general_procurement"]
check("R-01 rated", bool(s1), reg[:500])
check("R-01 placeholder filled from analytics.json", f"In general procurement, {gp['groups']:,} supplier groups" in s1, s1[:600])
check("R-01 £ figure filled", f"£{gp['total_gbp']:,.0f}" in s1)
check("R-01 no placeholder left", "{{" not in s1 and "⚠" not in s1)
check("R-01 score read from the council matrix", f"score **{cell(3, 3)}**" in s1, s1[:300])
check("R-01 band from Table 4 with both conflict markers", "Medium - High (Amber)†‡" in s1)
check("R-01 split_purchases caveats carried", "(split_purchases)" in s1)
ex = reg.split("## Excluded risks")[-1].split("## Citations")[0] if "## Excluded risks" in reg else ""
check("R-02 listed as excluded", "R-02" in ex, reg[-1500:])
check("R-02 dropped: likelihood has no resolvable citation", "likelihood justification has no resolvable" in ex)
check("R-02 dropped: IMP item alone is not evidence", "impact justification has no resolvable" in ex)
check("R-02 dropped: placeholder cannot be filled", "no_such_metric" in ex)
check("R-02 not rated in the register", not section(reg, "R-02"))
check("each unresolved R-02 citation reported",
      all(x in out for x in ("CPR-99", "AUD-99", "flagged_total")), out)
check("typed figure in R-02 warned", "figure typed in prose '£25,000'" in out, out)
com = read(d, "auditor-comments.md") if code == 0 else ""
check("auditor-comments has R-01 with blank decision", re.search(r"^\| R-01 \|.*\|  \|  \| awaiting decision \|$", com, re.M) is not None, com)
check("auditor-comments has no row for dropped R-02", "| R-02 |" not in com)
check("register ends with Auditor decisions", reg.rstrip().split("\n## ")[-1].startswith("Auditor decisions"))
check("register header names the conflicts", "DIS-04" in reg and "DIS-03" in reg and "CH-1" in reg)

# 2. Decisions are kept when the file is rewritten.
decide(d, "R-01", "APPROVE", "Agreed | as rated")
code, out = run(d, BASE)
com = read(d, "auditor-comments.md")
check("draft rebuild keeps the auditor's decision", code == 0 and "| APPROVE | Agreed \\| as rated |" in com, out + com[-400:])

# 3. A draft change after the auditor started deciding fails.
r = copy.deepcopy(BASE)
r["risks"][0]["title"] = "Changed title"
code, out = run(d, r)
check("draft change after decisions fails", code == 1 and "revision" in out, out)

# 4. A revision applies an AMEND and names it.
d = new_dir()
run(d, BASE)
decide(d, "R-01", "AMEND", "Narrow the focus to the three-quotes tier")
r = copy.deepcopy(BASE)
r["risks"][0]["proposed_focus"] = "Sample the groups crossing the three-quotes tier from analytics-full/split_purchases.csv."
r["revision"] = {"number": 1, "summary": "Focus narrowed as asked.",
                 "changes": [{"risk_id": "R-01", "fields": ["proposed_focus"], "decision_ref": "R-01",
                              "note": "Focus narrowed to the three-quotes tier."}]}
code, out = run(d, r)
reg = read(d, "risk-register.md") if code == 0 else ""
check("revision 1 builds", code == 0, out)
check("revision header names the change", "## Revision 1: changes since revision 0" in reg
      and re.search(r"\| R-01 \| proposed_focus \| AMEND on R-01", reg) is not None, reg[:1500])
check("comments status shows the decision applied", "applied in revision 1" in read(d, "auditor-comments.md"))

# 4b. Rebuilding the same revision is allowed.
code, out = run(d, r)
check("rebuilding revision 1 is allowed", code == 0, out)

# 5. A change the auditor did not ask for fails.
d = new_dir()
run(d, BASE)
decide(d, "R-01", "AMEND", "Narrow the focus to the three-quotes tier")
r2 = copy.deepcopy(r)
r2["risks"][0]["title"] = "A different title"
code, out = run(d, r2)
check("undeclared change fails", code == 1 and "R-01: title changed but not declared" in out, out)

# 5b. A change on an APPROVE'd risk fails even if declared.
d = new_dir()
run(d, BASE)
decide(d, "R-01", "APPROVE", "")
code, out = run(d, r)
check("change without an AMEND decision fails", code == 1 and "not backed by a pending AMEND" in out, out)

# 6. An AMEND left unapplied fails.
d = new_dir()
run(d, BASE)
decide(d, "R-01", "AMEND", "Narrow the focus to the three-quotes tier")
r3 = copy.deepcopy(BASE)
r3["revision"] = {"number": 1, "summary": "No changes.", "changes": []}
code, out = run(d, r3)
check("unapplied AMEND fails", code == 1 and "is not applied" in out, out)

# 7. An undecided risk blocks a revision.
d = new_dir()
run(d, BASE)
code, out = run(d, r3)
check("undecided risk fails a revision", code == 1 and "undecided" in out, out)

# 8. An auditor override is applied and marked.
d = new_dir()
run(d, BASE)
decide(d, "R-01", "AMEND", "Raise likelihood to 4: the auditor knows of a recent incident")
r4 = copy.deepcopy(BASE)
r4["risks"][0]["likelihood"]["override"] = {"score": 4, "decision_ref": "R-01",
                                             "note": "Raised at the auditor's request."}
r4["revision"] = {"number": 1, "summary": "Override applied.",
                  "changes": [{"risk_id": "R-01", "fields": ["likelihood.override"], "decision_ref": "R-01",
                               "note": "Likelihood set by the auditor."}]}
code, out = run(d, r4)
reg = read(d, "risk-register.md") if code == 0 else ""
s1 = section(reg, "R-01")
check("override builds", code == 0, out)
check("override marked in the risk", "auditor override" in s1 and "the rubric gives 3" in s1, s1[:800])
check("override score from the matrix", f"score **{cell(4, 3)}**" in s1)
check("override listed in the revision header", "**Auditor overrides**" in reg)

# 9. An override in a draft fails.
d = new_dir()
r5 = copy.deepcopy(r4)
del r5["revision"]
code, out = run(d, r5)
check("override in a draft fails", code == 1 and "override in a draft" in out, out)

# 10. Repeat-finding uplift: adverse opinion required.
d = new_dir()
r6 = good_only()
r6["risks"][0]["likelihood"]["uplift"] = {"audit": "AUD-01", "reason": "Same theme as Contract Letting."}
code, out = run(d, r6)
check("uplift on a Reasonable opinion fails", code == 1 and "not an adverse opinion" in out, out)
adverse = next(a for a in HISTORY["audits_completed"] if a["opinion"].lower().startswith(("limited", "weak")))
r6["risks"][0]["likelihood"]["uplift"] = {"audit": adverse["id"], "reason": "Test: theme treated as the same."}
code, out = run(d, r6)
s1 = section(read(d, "risk-register.md"), "R-01") if code == 0 else ""
check(f"uplift on an adverse opinion ({adverse['id']}) gives likelihood 4", code == 0 and
      "Likelihood 4" in s1 and "+1 repeat-finding uplift" in s1 and f"score **{cell(4, 3)}**" in s1, out + s1[:800])

# 11. Impact must cite the Table 1 level that matches its score.
d = new_dir()
r7 = good_only()
r7["risks"][0]["impact"]["score"] = 4
code, out = run(d, r7)
check("impact score without its IMP citation fails", code == 1 and "must cite [history:IMP-4]" in out, out)

# 11b. A typed score is refused: the builder computes it.
d = new_dir()
r8 = good_only()
r8["risks"][0]["likelihood"]["score"] = 3
code, out = run(d, r8)
check("typed likelihood score refused", code == 1 and "fields the builder does not take: ['score']" in out, out)

# 12. A detected conflict with no recorded choice fails.
d = new_dir()
with open(CHOICES) as f:
    ch = json.load(f)
ch["choices"] = [c for c in ch["choices"] if c["id"] != "CH-1"]
code, out = run(d, good_only(), ch)
check("undeclared scoring conflict fails", code == 1 and "conflict crr_threshold detected" in out
      and "DIS-04" in out, out)

# 13. Switching a choice changes the marked reading.
d = new_dir()
with open(CHOICES) as f:
    ch = json.load(f)
next(c for c in ch["choices"] if c["id"] == "CH-1")["use"] = "figure4"
code, out = run(d, good_only(), ch)
s1 = section(read(d, "risk-register.md"), "R-01") if code == 0 else ""
check("figure4 reading puts score 9 on the Corporate Risk Register", code == 0 and
      "escalation: Corporate Risk Register (Figure 4" in s1, out + s1[:500])

for x in dirs:
    shutil.rmtree(x, ignore_errors=True)
print()
print("ALL TESTS PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)
