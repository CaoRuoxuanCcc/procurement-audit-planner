#!/usr/bin/env python3
"""Build the audit planning pack from the planner's judgments.

Reads:  outputs/audit-plan.json            planner's judgments: controls, test steps, sample recipes, PBC, memo text
        outputs/risk-ratings.json          the risks (the register's source)
        outputs/auditor-comments.md        the auditor's APPROVE / AMEND / REJECT per risk
        outputs/risk-register.state.json   which revision was built, on which inputs, with which decisions applied
        outputs/analytics.json, history.json, rules.json; outputs/analytics-full/*.csv
        .claude/skills/risk-assessment/scoring_choices.json   (scores are re-read from the council matrix)
        .claude/skills/audit-program/sampling.json            sample size per risk score
Writes: outputs/planning-memo.md, risk-control-matrix.md, audit-program.md,
        outputs/samples/T-*.csv, outputs/pack-figures.json.
        Nothing is written when there is an error.

The planner judges; the builder computes. It works out the approved scope,
re-reads every rating from the council matrix, resolves every citation and
{{$.path}} placeholder, draws every sample deterministically, checks every
sampled transaction against spend_clean.csv, and checks traceability (every
control tested, every rule accounted for).

Placeholders resolve against analytics.json, except paths that start with
$.pack., which resolve against the figures this builder computes (see
pack-figures.json -> pack).

Run:  .venv/bin/python -I .claude/skills/audit-program/build_pack.py [--gate]
      [--plan P] [--ratings P] [--comments P] [--state P] [--analytics P] [--history P]
      [--rules P] [--choices P] [--sampling P] [--analytics-full D] [--out-dir D]
Exit: 0 built (or gate open); 1 errors, nothing written (or gate closed);
      2 an input is missing or unreadable.
"""
import argparse
import csv
import datetime
import glob
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RA = os.path.join(os.path.dirname(HERE), "risk-assessment")
sys.path.insert(0, RA)
from build_register import (  # noqa: E402
    BANNED_RE, PH_RE, Ctx, Scoring, find_tags, fmt_value, load_json, md_cell,
    parse_range, process_text, rate_risk, read_comments, sha256)

LANGUAGE = ("All entries are risk indicators to investigate, not findings about "
            "the council, any department or any supplier.")
# Source file in analytics-full -> the analytics test whose caveats travel with it.
SOURCES = {
    "split_purchases.csv": "split_purchases",
    "threshold_clustering.csv": "threshold_clustering",
    "off_contract.csv": "off_contract",
    "off_contract_candidates.csv": "off_contract",
    "duplicates.csv": "duplicates",
    "duplicates_clusters.csv": "duplicates",
    "expired_notice_spend.csv": "expired_notice_spend",
    "spend_vs_award.csv": "spend_vs_award",
    "high_value_suppliers.csv": "high_value_suppliers",
    "spend_clean.csv": None,
}
# A unit's total column is re-derived from its transactions in spend_clean.csv.
TOTAL_COLUMNS = ("group_total", "window_total")
OPS = ("eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "contains", "is_blank", "not_blank")
LABEL_COLUMNS = ("supplier_norm", "T", "cluster_id", "notice_id", "main_tag", "tag", "match_status")
CONTROL_RE = re.compile(r"^C-(\d{2})\.\d+$")
TEST_RE = re.compile(r"^T-(\d{2})\.\d+$")
PBC_RE = re.compile(r"^PBC-\d{2}$")
RISK_KEYS = {"risk_id", "controls", "tests"}
CONTROL_KEYS = {"control_id", "description", "owner"}
TEST_KEYS = {"test_id", "title", "controls", "step", "sample", "pbc"}
SAMPLE_KEYS = {"draw": {"kind", "source", "filter", "sort", "method", "size", "one_per", "transactions", "rationale"},
               "external": {"kind", "population", "size", "rationale"},
               "none": {"kind", "reason"}}


# ---------------------------------------------------------------- small helpers


def new_out():
    return {"tests": set(), "cited": {}, "bad_placeholders": [], "figures": [], "warnings": [],
            "banned": [], "problems": []}


def num(s):
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def gbp(v):
    return f"£{v:,.0f}"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


class Text:
    """Resolves the prose fields of the plan and records everything found."""

    def __init__(self, ctx, errors):
        self.ctx, self.errors = ctx, errors
        self.rules, self.metrics, self.tests, self.figures = set(), set(), set(), []

    def __call__(self, text, field, need=None):
        """Rendered text. need: None, 'rule' or 'rule_or_metric' (error if missing)."""
        if not isinstance(text, str) or not text.strip():
            self.errors.append(f"{field} is missing")
            return ""
        out = new_out()
        rendered, cites = process_text(text, field, self.ctx, out)
        for p in out["problems"] + out["bad_placeholders"]:
            self.errors.append(p)
        for w in out["warnings"]:  # typed figures: every number must come from a placeholder
            self.errors.append(w)
        if out["banned"]:
            self.errors.append("accusatory wording (use indicator language): " + "; ".join(out["banned"]))
        for c in cites:
            if c["kind"] == "metric" and str(c["ref"]).startswith("$.pack"):
                self.errors.append(f"{field}: [metric:{c['ref']}] cites a pack figure; cite analytics.json metrics "
                                   "and use {{$.pack...}} placeholders for pack figures")
        ok = [c for c in cites if c["ok"]]
        if need == "rule" and not any(c["kind"] == "rule" for c in ok):
            self.errors.append(f"{field} cites no rule: every expected control cites ≥1 [rule:...] from rules.json")
        if need == "rule_or_metric" and not any(c["kind"] in ("rule", "metric") for c in ok):
            self.errors.append(f"{field} cites no rule or metric: every test step cites ≥1 [rule:...] or [metric:...]")
        self.rules |= {c["ref"] for c in ok if c["kind"] == "rule"}
        self.metrics |= {c["ref"] for c in ok if c["kind"] == "metric"}
        self.tests |= {t for t in out["tests"] if not t.startswith("__")}
        self.figures += [{"field": field, "path": p, "value": v, "text": t} for p, v, t in out["figures"]]
        return rendered


# ---------------------------------------------------------------- gate: approved scope


def gate(a, ratings, analytics, history, rules, choices, errors):
    """Approved scope, or errors. Returns (scope dict, views by risk_id, scoring)."""
    risks = {r.get("risk_id"): r for r in ratings.get("risks") or [] if isinstance(r, dict)}
    blk = ratings.get("revision")
    n = blk.get("number") if isinstance(blk, dict) else None
    if not isinstance(n, int) or n < 1:
        errors.append("the register is not a revision (risk-ratings.json has no revision block numbered 1 or more): "
                      "the auditor records decisions in auditor-comments.md and the risk-assessor builds the revision")
        return None, {}, None
    if not os.path.exists(a.comments):
        errors.append(f"auditor-comments.md not found at {a.comments}")
        return None, {}, None
    file_rev, decisions = read_comments(a.comments, errors)
    if not os.path.exists(a.state):
        errors.append(f"risk-register.state.json not found at {a.state}; the register was not built by build_register.py")
        return None, {}, None
    state = load_json(a.state, "risk-register.state.json")
    built = (state.get("revisions") or {}).get(str(n))
    if built is None:
        errors.append(f"revision {n} is in risk-ratings.json but was never built; run build_register.py")
        return None, {}, None
    if file_rev != n:
        errors.append(f"auditor-comments.md is for revision {file_rev}, the register is revision {n}; "
                      "re-run build_register.py")
    if built["risks"] != risks:
        errors.append(f"risk-ratings.json changed after revision {n} was built; re-run build_register.py")
    inputs = {"outputs/analytics.json": sha256(a.analytics), "outputs/history.json": sha256(a.history),
              "outputs/rules.json": sha256(a.rules), "scoring_choices.json": sha256(a.choices)}
    changed = [k for k in inputs if inputs[k] != built["inputs"].get(k)]
    if changed:
        errors.append(f"input(s) changed since revision {n} was built: {', '.join(changed)}; the register's figures "
                      "no longer match; re-run the risk-assessor")
    applied = state.get("applied") or {}
    for rid in built["rated"]:
        if rid not in decisions:
            errors.append(f"{rid} is in the register but missing from auditor-comments.md")
            continue
        d, c = decisions[rid]
        if not d:
            errors.append(f"{rid} has no auditor decision in auditor-comments.md (undecided)")
            continue
        ap = applied.get(rid)
        if ap is None or (ap["decision"], ap["comment"]) != (d, c) or ap["applied_in"] > n:
            errors.append(f"{rid}: the decision {d} in auditor-comments.md is not applied in revision {n}; "
                          f"re-run the risk-assessor to build revision {n + 1}")
    for rid in decisions:
        if rid not in built["rated"] and decisions[rid][0]:
            errors.append(f"{rid} has a decision in auditor-comments.md but is not in the register")
    if errors:
        return None, {}, None

    sc_errors, sc_warn = [], []
    scoring = Scoring(history, choices, sc_errors, sc_warn)
    ctx = Ctx(analytics, history, rules, scoring)
    scope = {"revision": n, "in": [], "out": [], "decisions": {}}
    views = {}
    for rid in built["rated"]:
        d, c = decisions[rid]
        scope["decisions"][rid] = {"decision": d, "comment": c}
        v = rate_risk(risks[rid], ctx)
        if v["dropped"] or v["errors"]:
            errors.append(f"{rid} no longer rates cleanly: " + "; ".join(v["dropped"] + v["errors"]))
            continue
        views[rid] = v
        (scope["in"] if d in ("APPROVE", "AMEND") else scope["out"]).append(rid)
    errors.extend(sc_errors)
    if not scope["in"] and not errors:
        errors.append("no risk is in scope (every risk rejected)")
    return scope, views, scoring


# ---------------------------------------------------------------- sampling


class SizeTable:
    def __init__(self, cfg, errors):
        self.rows = []
        for i, r in enumerate(cfg.get("size_by_score") or []):
            rng = parse_range(r.get("scores"))
            u = r.get("units")
            if rng is None or not isinstance(u, int) or isinstance(u, bool) or u < 1:
                errors.append(f"sampling.json size_by_score[{i}] needs scores 'a-b' and units ≥ 1")
                continue
            self.rows.append((rng[0], rng[1], u, r.get("band")))
        for s in range(1, 26):
            hits = [x for x in self.rows if x[0] <= s <= x[1]]
            if len(hits) != 1:
                errors.append(f"sampling.json: score {s} falls in {len(hits)} size ranges, expected 1")
                break

    def size(self, score):
        for lo, hi, u, band in self.rows:
            if lo <= score <= hi:
                return u, f"{lo}-{hi}"
        return None, None


def filter_value(v, rules, where, errors):
    if isinstance(v, dict):
        rid, field = v.get("rule"), v.get("field")
        r = rules.get(rid)
        if r is None or field not in ("threshold_low", "threshold_high"):
            errors.append(f"{where}: value {v} needs a rule_id in rules.json and field threshold_low or threshold_high")
            return None, None
        val = r.get(field)
        if val is None:
            errors.append(f"{where}: {rid} {field} is null in rules.json")
            return None, None
        return val, f"{rid} {field} ({gbp(val)})"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        typed = {x.get(k) for x in rules.values() for k in ("threshold_low", "threshold_high")} - {None}
        if v in typed:
            errors.append(f"{where}: value {v} is a rules.json threshold typed by hand; write "
                          "{\"rule\": \"CPR-..\", \"field\": \"threshold_low\"} so it traces to the rule")
    return v, json.dumps(v)


def match(cell, op, val):
    cell = (cell or "").strip()
    if op == "is_blank":
        return cell == ""
    if op == "not_blank":
        return cell != ""
    if op in ("in", "not_in"):
        hit = any(match(cell, "eq", x) for x in val)
        return hit if op == "in" else not hit
    if op == "contains":
        return str(val).lower() in cell.lower()
    if isinstance(val, bool):
        res = cell.lower() == str(val).lower()
        return res if op == "eq" else (not res if op == "ne" else False)
    nv, nc = num(val), num(cell)
    if isinstance(val, (int, float)) and nc is not None:
        return {"eq": nc == nv, "ne": nc != nv, "gt": nc > nv, "gte": nc >= nv,
                "lt": nc < nv, "lte": nc <= nv}[op]
    if op in ("eq", "ne"):
        res = cell.lower() == str(val).strip().lower()
        return res if op == "eq" else not res
    return False


def unit_rows(row, fields):
    if "row_ids" in fields:
        return [x.strip() for x in (row.get("row_ids") or "").split(";") if x.strip()]
    return [row["row_id"].strip()] if row.get("row_id", "").strip() else []


def draw(tid, rec, size, a, rules, spend, cache, errors):
    """Deterministic draw. Returns (population, units [(line, row, [row_ids])], description) or None."""
    where = f"{tid}.sample"
    src = rec.get("source")
    if src not in SOURCES:
        errors.append(f"{where}.source {src!r} is not one of {sorted(SOURCES)} in analytics-full")
        return None
    path = os.path.join(a.analytics_full, src)
    if not os.path.exists(path):
        errors.append(f"{where}.source: {path} not found")
        return None
    if src not in cache:
        cache[src] = read_csv(path)
    fields, rows = cache[src]
    if "row_ids" not in fields and "row_id" not in fields:
        errors.append(f"{where}: {src} has no row_id or row_ids column")
        return None
    rows = [(i + 2, r) for i, r in enumerate(rows)]  # CSV line number, header is line 1
    desc = []
    for j, f in enumerate(rec.get("filter") or []):
        w = f"{where}.filter[{j}]"
        col, op = f.get("column"), f.get("op")
        if col not in fields:
            errors.append(f"{w}: column {col!r} is not in {src} (columns: {', '.join(fields)})")
            return None
        if op not in OPS:
            errors.append(f"{w}: op {op!r} is not one of {', '.join(OPS)}")
            return None
        val, shown = None, ""
        if op not in ("is_blank", "not_blank"):
            if "value" not in f:
                errors.append(f"{w}: op {op} needs a value")
                return None
            raw = f["value"]
            if op in ("in", "not_in"):
                if not isinstance(raw, list) or not raw:
                    errors.append(f"{w}: op {op} needs a non-empty list")
                    return None
                pairs = [filter_value(x, rules, w, errors) for x in raw]
                val, shown = [p[0] for p in pairs], "[" + ", ".join(str(p[1]) for p in pairs) + "]"
            else:
                val, shown = filter_value(raw, rules, w, errors)
            if val is None:
                return None
        rows = [(ln, r) for ln, r in rows if match(r.get(col), op, val)]
        desc.append(f"`{col}` {op} {shown}".rstrip())
    population = len(rows)
    if population == 0:
        errors.append(f"{where}: the filter leaves no rows in {src}; nothing to sample")
        return None
    sort = rec.get("sort") or []
    for k in reversed(sort):
        col = k.get("column")
        if col not in fields:
            errors.append(f"{where}.sort: column {col!r} is not in {src}")
            return None
        full = [x for x in rows if x[1].get(col, "").strip()]
        blank = [x for x in rows if not x[1].get(col, "").strip()]
        numeric = all(num(x[1][col]) is not None for x in full)
        full.sort(key=lambda x, col=col, numeric=numeric: num(x[1][col]) if numeric else x[1][col].strip().lower(),
                  reverse=bool(k.get("descending")))
        rows = full + blank  # blanks last either way
    # Python's sort is stable and the source is read in file order, so ties keep file order.
    one = rec.get("one_per")
    if one is not None:
        if one not in fields:
            errors.append(f"{where}.one_per: column {one!r} is not in {src}")
            return None
        seen, kept = set(), []
        for ln, r in rows:
            if r.get(one) not in seen:
                seen.add(r.get(one))
                kept.append((ln, r))
        rows = kept
    method = rec.get("method", "top")
    if method not in ("top", "systematic"):
        errors.append(f"{where}.method {method!r} is not top or systematic")
        return None
    N = len(rows)
    n = N if size is None else min(size, N)
    idx = list(range(n)) if method == "top" else [math.floor(i * N / n) for i in range(n)]
    units = []
    for i in idx:
        ln, r = rows[i]
        ids = unit_rows(r, fields)
        if not ids:
            errors.append(f"{where}: {src} line {ln} has no row ids")
            continue
        units.append((ln, r, ids))
    sort_txt = ", ".join(f"`{k.get('column')}` {'descending' if k.get('descending') else 'ascending'}" for k in sort)
    d = (f"`analytics-full/{src}`" + (f" where {' and '.join(desc)}" if desc else "")
         + (f"; one per `{one}`" if one else "") + (f"; sorted by {sort_txt}" if sort else "; file order")
         + f"; {'first' if method == 'top' else 'evenly spaced'} units taken")
    return population, N, units, d


def verify_units(tid, src, units, fields, spend, mode, errors):
    """Each transaction exists in spend_clean.csv and agrees with the source row. Returns sample rows."""
    out = []
    for k, (ln, r, ids) in enumerate(units, 1):
        found = []
        for rid in ids:
            s = spend.get(rid)
            if s is None:
                errors.append(f"{tid}: {src} line {ln} row_id {rid!r} is not in spend_clean.csv")
                continue
            found.append(s)
        if len(found) != len(ids):
            continue
        if "row_id" in fields and "row_ids" not in fields:
            s = found[0]
            if "amount" in fields and abs((num(r.get("amount")) or 0) - (num(s["amount"]) or 0)) > 0.005:
                errors.append(f"{tid}: {src} line {ln} amount {r.get('amount')} ≠ spend_clean.csv {s['amount']}")
            if "supplier_norm" in fields and r.get("supplier_norm") != s["supplier_norm"]:
                errors.append(f"{tid}: {src} line {ln} supplier differs from spend_clean.csv")
        for col in TOTAL_COLUMNS:
            if col in fields and num(r.get(col)) is not None:
                tot = sum(num(s["amount"]) for s in found)
                if abs(tot - num(r[col])) > 0.01:
                    errors.append(f"{tid}: {src} line {ln} {col} {r[col]} ≠ sum of its transactions "
                                  f"in spend_clean.csv ({tot:.2f})")
        if "supplier_norm" in fields and any(s["supplier_norm"] != r.get("supplier_norm") for s in found):
            errors.append(f"{tid}: {src} line {ln} lists a transaction of another supplier")
        if mode == "largest":
            found = [sorted(found, key=lambda s: (-num(s["amount"]), s["row_id"]))[0]]
        label = " · ".join(f"{c}={r[c]}" for c in LABEL_COLUMNS if c in fields and r.get(c, "") != "")
        for s in found:
            out.append({"test_id": tid, "unit_no": k, "unit_source": f"{src}:{ln}", "unit_label": label,
                        "row_id": s["row_id"], "date": s["date"], "supplier": s["supplier"],
                        "supplier_norm": s["supplier_norm"], "service": s["service"], "category": s["category"],
                        "narrative": s["narrative"], "tag": s["tag"], "amount": s["amount"]})
    return out


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    out_default = os.path.join(ROOT, "outputs")
    ap.add_argument("--gate", action="store_true", help="run only the approved-scope check")
    ap.add_argument("--plan", default=os.path.join(out_default, "audit-plan.json"))
    ap.add_argument("--ratings", default=os.path.join(out_default, "risk-ratings.json"))
    ap.add_argument("--comments", default=os.path.join(out_default, "auditor-comments.md"))
    ap.add_argument("--state", default=os.path.join(out_default, "risk-register.state.json"))
    ap.add_argument("--analytics", default=os.path.join(out_default, "analytics.json"))
    ap.add_argument("--history", default=os.path.join(out_default, "history.json"))
    ap.add_argument("--rules", default=os.path.join(out_default, "rules.json"))
    ap.add_argument("--choices", default=os.path.join(RA, "scoring_choices.json"))
    ap.add_argument("--sampling", default=os.path.join(HERE, "sampling.json"))
    ap.add_argument("--analytics-full", default=os.path.join(out_default, "analytics-full"))
    ap.add_argument("--out-dir", default=out_default)
    a = ap.parse_args()

    ratings = load_json(a.ratings, "risk-ratings.json")
    analytics = load_json(a.analytics, "analytics.json")
    history = load_json(a.history, "history.json")
    rules_doc = load_json(a.rules, "rules.json")
    choices = load_json(a.choices, "scoring_choices.json")
    errors = []
    sc = (analytics.get("self_check") or {}).get("status")
    if sc != "PASS":
        errors.append(f"analytics.json self_check status is {sc!r}, not PASS; re-run spend-analyst first")
    scope, views, scoring = gate(a, ratings, analytics, history, rules_doc, choices, errors)
    if a.gate or errors:
        for e in errors:
            print(f"ERROR {e}")
        if errors:
            print(f"GATE CLOSED: {len(errors)} error(s)" + ("" if a.gate else "; nothing written"))
            return 1
        print(f"GATE OPEN: register revision {scope['revision']}; in scope {', '.join(scope['in'])}; "
              f"out of scope {', '.join(scope['out']) or 'none'}")
        return 0

    plan = load_json(a.plan, "audit-plan.json")
    sampling = load_json(a.sampling, "sampling.json")
    sizes = SizeTable(sampling, errors)
    rules = {r["rule_id"]: r for r in rules_doc.get("rules", []) if "rule_id" in r}
    if "pack" in analytics:
        errors.append("analytics.json has a top-level 'pack' key, which clashes with $.pack placeholders")
    spend_path = os.path.join(a.analytics_full, "spend_clean.csv")
    if not os.path.exists(spend_path):
        print(f"STOP: spend_clean.csv not found at {spend_path}")
        return 2
    _, spend_rows = read_csv(spend_path)
    spend = {r["row_id"]: r for r in spend_rows}
    if plan.get("register_revision") != scope["revision"]:
        errors.append(f"audit-plan.json register_revision is {plan.get('register_revision')!r}; "
                      f"the approved register is revision {scope['revision']}")
    risks_by_id = {r["risk_id"]: r for r in ratings["risks"]}

    # -------- structure and traceability (before any text is resolved)
    entries = {}
    for i, e in enumerate(plan.get("risks") or []):
        rid = e.get("risk_id") if isinstance(e, dict) else None
        if rid in entries:
            errors.append(f"audit-plan.json lists {rid} twice")
        elif rid in scope["out"]:
            errors.append(f"audit-plan.json has {rid}, which the auditor put out of scope (REJECT)")
        elif rid not in scope["in"]:
            errors.append(f"audit-plan.json risks[{i}]: {rid!r} is not an approved risk in the register")
        else:
            entries[rid] = e
            extra = sorted(set(e) - RISK_KEYS)
            if extra:
                errors.append(f"{rid}: fields the builder does not take: {extra}")
    for rid in scope["in"]:
        if rid not in entries:
            errors.append(f"{rid} is approved (in scope) but missing from audit-plan.json")
    pbc = {}
    for i, p in enumerate(plan.get("pbc") or []):
        pid = p.get("pbc_id")
        if not isinstance(pid, str) or not PBC_RE.match(pid) or pid in pbc:
            errors.append(f"pbc[{i}]: pbc_id {pid!r} must be unique and of the form PBC-01")
            continue
        pbc[pid] = p
    controls, tests, pbc_used = {}, {}, {}
    for rid, e in entries.items():
        rnum = rid[2:]
        if not e.get("controls"):
            errors.append(f"{rid} has no expected control")
        if not e.get("tests"):
            errors.append(f"{rid} has no test step")
        for c in e.get("controls") or []:
            cid = c.get("control_id")
            m = CONTROL_RE.match(cid or "")
            if not m or m.group(1) != rnum or cid in controls:
                errors.append(f"{rid}: control_id {cid!r} must be unique and of the form C-{rnum}.1")
                continue
            extra = sorted(set(c) - CONTROL_KEYS)
            if extra:
                errors.append(f"{cid}: fields the builder does not take: {extra}")
            controls[cid] = (rid, c)
        for t in e.get("tests") or []:
            tid = t.get("test_id")
            m = TEST_RE.match(tid or "")
            if not m or m.group(1) != rnum or tid in tests:
                errors.append(f"{rid}: test_id {tid!r} must be unique and of the form T-{rnum}.1")
                continue
            extra = sorted(set(t) - TEST_KEYS)
            if extra:
                errors.append(f"{tid}: fields the builder does not take: {extra}")
            tests[tid] = (rid, t)
            if not t.get("controls"):
                errors.append(f"{tid} tests no control (list the control_ids it tests)")
            if not t.get("pbc"):
                errors.append(f"{tid} names no PBC item")
            for p in t.get("pbc") or []:
                if p not in pbc:
                    errors.append(f"{tid}: PBC item {p!r} is not in the pbc list")
                pbc_used.setdefault(p, []).append(tid)
    tested = {}
    for tid, (rid, t) in tests.items():
        for cid in t.get("controls") or []:
            if cid not in controls:
                errors.append(f"{tid}: control {cid!r} does not exist")
            elif controls[cid][0] != rid:
                errors.append(f"{tid}: control {cid} belongs to {controls[cid][0]}, not {rid}")
            else:
                tested.setdefault(cid, []).append(tid)
    for cid in controls:
        if cid not in tested:
            errors.append(f"{cid} has no test: every expected control needs at least one test step")
    for pid in pbc:
        if pid not in pbc_used:
            errors.append(f"{pid} is not needed by any test; remove it or name it in a test")

    # -------- ratings and sample sizes (computed here, never typed by the planner)
    pack = {"scope": {}, "risks": {}, "tests": {}}
    for rid in scope["in"] + scope["out"]:
        v = views[rid]
        r = v["rating"]
        size, rng = sizes.size(r["score"])
        pack["risks"][rid] = {"likelihood": v["L"], "impact": v["I"], "score": r["score"],
                              "band": r.get("band") or "n/a (fallback)", "sample_size": size,
                              "sample_size_range": rng}

    # -------- samples
    cache, sample_rows, test_info = {}, {}, {}
    for tid, (rid, t) in sorted(tests.items()):
        rec = t.get("sample")
        kind = rec.get("kind") if isinstance(rec, dict) else None
        if kind not in SAMPLE_KEYS:
            errors.append(f"{tid}.sample needs kind draw, external or none")
            continue
        extra = sorted(set(rec) - SAMPLE_KEYS[kind])
        if extra:
            errors.append(f"{tid}.sample ({kind}) has fields the builder does not take: {extra}")
        size_mode = rec.get("size", "by_score")
        allowed = {"draw": ("by_score", "all"), "external": ("by_score",), "none": (size_mode,)}[kind]
        if size_mode not in allowed:
            errors.append(f"{tid}.sample.size must be by_score" + (" or all" if kind == "draw" else ""))
            continue
        target = pack["risks"][rid]["sample_size"]
        info = {"kind": kind, "risk": rid}
        if kind == "none":
            if not isinstance(rec.get("reason"), str) or not rec["reason"].strip():
                errors.append(f"{tid}.sample kind none needs a reason (e.g. walkthrough of the process)")
            test_info[tid] = info
            continue
        if kind == "external":
            if not isinstance(rec.get("population"), str) or not rec["population"].strip():
                errors.append(f"{tid}.sample kind external needs population: what the client provides")
            info["size"] = target
            pack["tests"][tid] = {"sample_units_required": target}
            test_info[tid] = info
            continue
        tr = rec.get("transactions", "all")
        if tr not in ("all", "largest"):
            errors.append(f"{tid}.sample.transactions must be all or largest")
            continue
        n_err = len(errors)
        res = draw(tid, rec, None if size_mode == "all" else target, a, rules, spend, cache, errors)
        if res is None or len(errors) > n_err:
            continue
        population, after_one, units, desc = res
        fields = cache[rec["source"]][0]
        rows = verify_units(tid, rec["source"], units, fields, spend, tr, errors)
        sample_rows[tid] = rows
        value = round(sum(num(r["amount"]) for r in rows), 2)
        info.update({"source": rec["source"], "desc": desc, "size_mode": size_mode, "transactions": tr})
        test_info[tid] = info
        pack["tests"][tid] = {"population_units": population, "eligible_units": after_one,
                              "sample_units": len(units), "transactions": len(rows), "sampled_value_gbp": value,
                              "size_by_score": target, "takes_all": len(units) == after_one}

    in_scope_scores = [pack["risks"][r]["score"] for r in scope["in"]]
    pack["scope"] = {
        "register_revision": scope["revision"], "risks_in_register": len(scope["in"]) + len(scope["out"]),
        "in_scope": len(scope["in"]), "out_of_scope": len(scope["out"]),
        "amended": sum(1 for r in scope["in"] if scope["decisions"][r]["decision"] == "AMEND"),
        "controls": len(controls), "tests": len(tests),
        "samples_drawn": len(sample_rows),
        "sample_units": sum(x.get("sample_units", 0) for x in pack["tests"].values()),
        "transactions_sampled": sum(len(v) for v in sample_rows.values()),
        "sampled_value_gbp": round(sum(x.get("sampled_value_gbp", 0) for x in pack["tests"].values()), 2),
        "pbc_items": len(pbc), "rules_total": len(rules),
        "highest_score_in_scope": max(in_scope_scores) if in_scope_scores else None,
    }

    # -------- prose: citations, placeholders, language
    merged = dict(analytics)
    merged["pack"] = pack
    ctx = Ctx(merged, history, rules_doc, scoring)
    T = Text(ctx, errors)
    rendered = {"controls": {}, "tests": {}, "pbc": {}, "memo": [], "not_tested": []}
    for cid, (rid, c) in controls.items():
        rendered["controls"][cid] = {"description": T(c.get("description"), f"{cid}.description", need="rule"),
                                     "owner": T(c["owner"], f"{cid}.owner") if c.get("owner") else ""}
    for tid, (rid, t) in tests.items():
        rec = t.get("sample") or {}
        rendered["tests"][tid] = {
            "title": T(t.get("title"), f"{tid}.title"),
            "step": T(t.get("step"), f"{tid}.step", need="rule_or_metric"),
            "why": (T(rec["rationale"], f"{tid}.sample.rationale") if rec.get("rationale") else ""),
            "population": (T(rec["population"], f"{tid}.sample.population") if rec.get("population") else ""),
            "reason": (T(rec["reason"], f"{tid}.sample.reason") if rec.get("reason") else ""),
        }
    for pid, p in pbc.items():
        rendered["pbc"][pid] = {"item": T(p.get("item"), f"{pid}.item"),
                                "owner": T(p["owner"], f"{pid}.owner") if p.get("owner") else ""}
    memo = (plan.get("memo") or {}).get("sections") or []
    if not memo:
        errors.append("audit-plan.json memo.sections is empty")
    for i, s in enumerate(memo):
        rendered["memo"].append((T(s.get("heading"), f"memo.sections[{i}].heading"),
                                 T(s.get("text"), f"memo.sections[{i}].text")))
    if isinstance(plan.get("title"), str):
        title = T(plan["title"], "title")
    else:
        title = "Procurement audit"

    # -------- rule coverage
    risk_rules = set()
    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for v in o.values():
                yield from strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from strings(v)
    for rid in scope["in"]:
        for txt in strings(risks_by_id[rid]):
            risk_rules |= {ref for _, _, kind, ref in find_tags(txt) if kind == "rule"}
    risk_rules &= set(rules)
    cited = risk_rules | T.rules
    not_tested = {}
    for i, x in enumerate(plan.get("rules_not_tested") or []):
        ids = x.get("rule_ids") or ([x["rule_id"]] if x.get("rule_id") else [])
        reason = T(x.get("reason"), f"rules_not_tested[{i}].reason")
        for r in ids:
            if r not in rules:
                errors.append(f"rules_not_tested[{i}]: {r!r} is not a rule_id in rules.json")
            elif r in not_tested:
                errors.append(f"rules_not_tested lists {r} twice")
            elif r in T.rules:
                errors.append(f"{r} is listed as not tested but a control or test cites it")
            else:
                not_tested[r] = reason
        rendered["not_tested"].append((ids, reason))
    unaccounted = [r for r in rules if r not in cited and r not in not_tested]
    if unaccounted:
        errors.append(f"rule(s) not cited by any in-scope risk, control or test and not listed in rules_not_tested "
                      f"with a reason: {', '.join(unaccounted)}")
    pack["scope"]["rules_cited"] = len(cited)
    pack["scope"]["rules_not_tested"] = len(not_tested)

    if errors:
        for e in errors:
            print(f"ERROR {e}")
        print(f"FAILED: {len(errors)} error(s); nothing written")
        return 1

    # -------- caveats that travel with the analytics used
    used_tests = set(T.tests)
    for rid in scope["in"]:
        used_tests |= {t for t in views[rid]["tests"] if not t.startswith("__")}
    for info in test_info.values():
        if SOURCES.get(info.get("source")):
            used_tests.add(SOURCES[info["source"]])
    caveats = {t: analytics["tests"][t].get("caveats") or [] for t in sorted(used_tests) if t in analytics.get("tests", {})}

    date = datetime.date.today().isoformat()
    rev = scope["revision"]
    head = (f"_Built by `build_pack.py` on {date} from risk register revision {rev} and "
            f"`outputs/audit-plan.json`. {LANGUAGE}_\n")

    def rating(rid):
        p = pack["risks"][rid]
        return f"L{p['likelihood']} × I{p['impact']} → {p['score']}, {p['band']}"

    def title_of(rid):
        return views[rid]["title_r"]

    # planning memo
    M = [f"# Planning memo: {md_cell(title)}", "", head]
    for h, txt in rendered["memo"]:
        M += [f"## {h}", "", txt, ""]
    M += ["## Scope approved by the auditor", "",
          f"Register revision {rev}: {len(scope['in'])} risk(s) in scope, {len(scope['out'])} out of scope. "
          "Ratings are re-read from the council matrix by the builder; sample sizes follow the score "
          f"(`sampling.json`: {sampling.get('source', '')}).", "",
          "| Risk | Title | Rating | Decision | Auditor comment | Sample size per test |", "| --- | --- | --- | --- | --- | --- |"]
    for rid in scope["in"]:
        d = scope["decisions"][rid]
        M.append(f"| {rid} | {md_cell(title_of(rid))} | {md_cell(rating(rid))} | {d['decision']} | "
                 f"{md_cell(d['comment'])} | {pack['risks'][rid]['sample_size']} |")
    if scope["out"]:
        M += ["", "Out of scope (auditor REJECT):", "", "| Risk | Title | Rating | Reason given |", "| --- | --- | --- | --- |"]
        for rid in scope["out"]:
            M.append(f"| {rid} | {md_cell(title_of(rid))} | {md_cell(rating(rid))} | "
                     f"{md_cell(scope['decisions'][rid]['comment'])} |")
    M += ["", "## Sampling summary", "",
          "| Test | Risk | Basis | Population | Sample | Transactions | Value | File |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for tid in sorted(tests):
        info, p = test_info[tid], pack["tests"].get(tid, {})
        if info["kind"] == "draw":
            M.append(f"| {tid} | {info['risk']} | `{info['source']}` | {p['population_units']:,} | "
                     f"{p['sample_units']}{' (all)' if p['takes_all'] else ''} | {p['transactions']:,} | "
                     f"{gbp(p['sampled_value_gbp'])} | `samples/{tid}.csv` |")
        elif info["kind"] == "external":
            M.append(f"| {tid} | {info['risk']} | client population | n/a | {p['sample_units_required']} to select | "
                     "n/a | n/a | n/a |")
        else:
            M.append(f"| {tid} | {info['risk']} | no sample (walkthrough) | n/a | n/a | n/a | n/a | n/a |")
    M += ["", f"Totals: {pack['scope']['sample_units']:,} units, {pack['scope']['transactions_sampled']:,} "
          f"transactions, {gbp(pack['scope']['sampled_value_gbp'])} drawn from the analytics. "
          "Every sampled transaction was checked against `analytics-full/spend_clean.csv`.", ""]
    if caveats:
        M += ["## Caveats carried from the analytics", ""]
        for t, cs in caveats.items():
            for c in cs:
                M.append(f"- ({t}) {c}")
        M.append("")
    M += ["## Rules coverage", "",
          f"{pack['scope']['rules_cited']} of {len(rules)} rules are cited by an in-scope risk, control or test; "
          f"{len(not_tested)} are listed as not tested with a reason (see the end of `audit-program.md`).", ""]

    # risk-control matrix
    X = ["# Risk-control matrix", "", head,
         "| Risk | Rating | Expected control | Owner | Tested by |", "| --- | --- | --- | --- | --- |"]
    for rid in scope["in"]:
        for c in entries[rid]["controls"]:
            cid = c["control_id"]
            rc = rendered["controls"][cid]
            X.append(f"| {rid} {md_cell(title_of(rid))} | {md_cell(rating(rid))} | **{cid}** {md_cell(rc['description'])} | "
                     f"{md_cell(rc['owner'])} | {', '.join(tested[cid])} |")
    X.append("")

    # audit program
    P = [f"# Audit program: {md_cell(title)}", "", head]
    for rid in scope["in"]:
        P += [f"## {rid} {title_of(rid)}", "", f"Rating {rating(rid)}; sample size by score: "
              f"{pack['risks'][rid]['sample_size']} unit(s) per test.", ""]
        for t in entries[rid]["tests"]:
            tid = t["test_id"]
            rt, info, p = rendered["tests"][tid], test_info[tid], pack["tests"].get(tid, {})
            P += [f"### {tid} {rt['title']}", "",
                  f"- **Controls tested:** " + "; ".join(f"{c} {rendered['controls'][c]['description']}" for c in t["controls"]),
                  f"- **Test step:** {rt['step']}"]
            if info["kind"] == "draw":
                sz = "all eligible units" if info["size_mode"] == "all" else f"{p['size_by_score']} by score"
                P.append(f"- **Sample:** {info['desc']}; size {sz}. Population {p['population_units']:,} unit(s); "
                         f"drawn {p['sample_units']}{' (all eligible)' if p['takes_all'] else ''}, "
                         f"{p['transactions']:,} transaction(s) "
                         f"({'largest per unit' if info['transactions'] == 'largest' else 'every transaction of each unit'}), "
                         f"{gbp(p['sampled_value_gbp'])}. Pull list: `samples/{tid}.csv`.")
            elif info["kind"] == "external":
                P.append(f"- **Sample:** select {p['sample_units_required']} item(s) (size by score) from "
                         f"{rt['population']}.")
            else:
                P.append(f"- **Sample:** none. {rt['reason']}")
            if rt["why"]:
                P.append(f"- **Why this sample:** {rt['why']}")
            P.append("- **PBC:** " + ", ".join(t["pbc"]))
            src_test = SOURCES.get(info.get("source"))
            for c in (caveats.get(src_test) or []):
                P.append(f"- **Caveat ({src_test}):** {c}")
            P.append("")
    P += ["## Rules not tested", "", "| Rule(s) | Reason |", "| --- | --- |"]
    for ids, reason in rendered["not_tested"]:
        P.append(f"| {', '.join(ids)} | {md_cell(reason)} |")
    P += ["", "## PBC list", "", "| PBC | Item | Owner | Needed by |", "| --- | --- | --- | --- |"]
    for pid in sorted(pbc):
        rp = rendered["pbc"][pid]
        P.append(f"| {pid} | {md_cell(rp['item'])} | {md_cell(rp['owner'])} | {', '.join(sorted(pbc_used[pid]))} |")
    P.append("")

    # -------- write
    docs = {"planning-memo.md": "\n".join(M), "risk-control-matrix.md": "\n".join(X), "audit-program.md": "\n".join(P)}
    for name, txt in docs.items():
        if BANNED_RE.search(txt):
            hits = sorted(set(m.group(1).lower() for m in BANNED_RE.finditer(txt)))
            print(f"ERROR {name}: accusatory wording {hits} (from an input text?); nothing written")
            return 1
    os.makedirs(a.out_dir, exist_ok=True)
    sdir = os.path.join(a.out_dir, "samples")
    os.makedirs(sdir, exist_ok=True)
    for old in glob.glob(os.path.join(sdir, "T-*.csv")):
        os.remove(old)
    cols = ["test_id", "unit_no", "unit_source", "unit_label", "row_id", "date", "supplier", "supplier_norm",
            "service", "category", "narrative", "tag", "amount"]
    for tid, rows in sample_rows.items():
        with open(os.path.join(sdir, f"{tid}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    for name, txt in docs.items():
        with open(os.path.join(a.out_dir, name), "w") as f:
            f.write(txt)
    figures = {
        "generated_on": date, "generated_by": ".claude/skills/audit-program/build_pack.py",
        "register_revision": rev,
        "inputs": {k: sha256(v) for k, v in (("audit-plan.json", a.plan), ("risk-ratings.json", a.ratings),
                                             ("analytics.json", a.analytics), ("rules.json", a.rules),
                                             ("history.json", a.history), ("spend_clean.csv", spend_path),
                                             ("sampling.json", a.sampling))},
        "sampling": {"source": sampling.get("source"), "size_by_score": sampling.get("size_by_score")},
        "pack": pack,
        "placeholders": T.figures,
        "about": "pack: every figure build_pack.py computed itself (ratings re-read from the council matrix, "
                 "sample sizes, populations, sample counts and values, scope counts). placeholders: every "
                 "{{$.path}} filled in the planner's text, with its value; paths under $.pack come from pack, "
                 "all others from analytics.json.",
    }
    with open(os.path.join(a.out_dir, "pack-figures.json"), "w") as f:
        json.dump(figures, f, indent=1, ensure_ascii=False)
    print(f"BUILT pack for register revision {rev}: {len(scope['in'])} risk(s) in scope, {len(controls)} control(s), "
          f"{len(tests)} test(s), {len(sample_rows)} sample file(s), {pack['scope']['transactions_sampled']} "
          f"transaction(s), {len(pbc)} PBC item(s); rules {len(cited)} cited, {len(not_tested)} not tested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
