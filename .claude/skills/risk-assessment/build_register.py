#!/usr/bin/env python3
"""Render the procurement risk register from the risk-assessor's judgments.

Reads:  outputs/risk-ratings.json         judgments: citations and {{$.path}} placeholders, no typed numbers
        outputs/analytics.json            every figure and every [metric:...] citation
        outputs/history.json              the council's scoring method and [history:...] citations
        outputs/rules.json                [rule:...] citations
        .claude/skills/risk-assessment/scoring_choices.json   which reading wins where the method conflicts
        outputs/auditor-comments.md       (if present) the auditor's decisions
        outputs/risk-register.state.json  (if present) earlier revisions and the decisions applied in them
Writes: outputs/risk-register.md, outputs/auditor-comments.md, outputs/risk-register.state.json.
        Nothing is written when there is an error.

The builder, not the agent, looks up every figure, the score, the matrix label
and the band. A risk whose likelihood or impact justification has no
resolvable evidence citation is dropped and listed as excluded.

Run:  .venv/bin/python -I .claude/skills/risk-assessment/build_register.py
      [--ratings P] [--analytics P] [--history P] [--rules P] [--choices P]
      [--out-dir D] [--strict]
Exit: 0 built (drops and warnings are printed); 1 errors, nothing written
      (with --strict, warnings also give 1); 2 an input is missing or unreadable.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from common import BANNED_RE  # noqa: E402

# Rubric (source: SKILL.md). Step -> base likelihood before any uplift.
RUBRIC = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
PERVASIVE_SHARE = 0.5  # rubric step L4: flagged share of the scoped population, a fraction
# Tests whose results may miss recent notices (source: CLAUDE.md); they cannot carry step L4.
INCOMPLETE_TESTS = ("off_contract", "expired_notice_spend")
# Adverse prior opinions for the repeat-finding uplift. The papers define no
# opinion level (GAP-05); this is the builder's reading, stated in the register.
ADVERSE_OPINIONS = ("limited", "weak")
ADVERSE_PROGRESS = ("unsatisfactory",)
# history.json sections that count as evidence. Scoring-method items (IMP, LIK,
# MTX, BND, ...) and gaps/discrepancies resolve but are not evidence.
EVIDENCE_SECTIONS = ("audits_completed", "follow_ups", "advisory_reviews",
                     "agreed_actions", "risk_themes")
UPLIFT_SECTIONS = ("audits_completed", "follow_ups")
CRITERIA = ("financial_loss", "personal", "assets", "reputation", "compliance")
DECISIONS = ("APPROVE", "AMEND", "REJECT")
FALLBACK_LABELS = {1: "Very low", 2: "Low", 3: "Medium", 4: "High", 5: "Very high"}
RISK_ID_RE = re.compile(r"^R-\d{2}$")
# Fields the agent may write. Anything else (a typed score, a band) is an error.
ALLOWED = {"": {"risk_id", "title", "theme", "description", "likelihood", "impact", "evidence", "proposed_focus"},
           "likelihood": {"rubric", "justification", "share", "uplift", "override"},
           "impact": {"score", "criterion", "exposure", "justification", "override"}}
LANGUAGE = ("All entries are risk indicators to investigate, not findings about "
            "the council, any department or any supplier.")


# ---------------------------------------------------------------- paths

_SEG = re.compile(r"""\.([A-Za-z0-9_]+)|\[(\d+)\]|\["([^"]*)"\]|\['([^']*)'\]""")


def parse_path(path):
    """'$.a.b[0]["k"]' -> [('key','a'),('key','b'),('idx',0),('key','k')], or None."""
    if not isinstance(path, str) or not path.startswith("$") or len(path) < 2:
        return None
    segs, i = [], 1
    while i < len(path):
        m = _SEG.match(path, i)
        if not m:
            return None
        if m.group(1) is not None:
            segs.append(("key", m.group(1)))
        elif m.group(2) is not None:
            segs.append(("idx", int(m.group(2))))
        else:
            segs.append(("key", m.group(3) if m.group(3) is not None else m.group(4)))
        i = m.end()
    return segs


def resolve(doc, path):
    """(True, value) or (False, reason)."""
    segs = parse_path(path)
    if not segs:
        return False, "not a $.path"
    node = doc
    for kind, s in segs:
        if isinstance(node, dict) and kind == "key" and s in node:
            node = node[s]
        elif isinstance(node, list) and (kind == "idx" or str(s).isdigit()):
            k = int(s)
            if k >= len(node):
                return False, f"no index {k}"
            node = node[k]
        else:
            return False, f"no key {s!r}"
    return True, node


def test_of(path):
    segs = parse_path(path) or []
    if len(segs) >= 2 and segs[0] == ("key", "tests"):
        return segs[1][1]
    return None


def metric(analytics, path):
    """Resolve an analytics path for use as evidence: non-null, from a test that ran."""
    ok, v = resolve(analytics, path)
    if not ok:
        return ok, v
    if v is None:
        return False, "value is null"
    t = test_of(path)
    if t is not None:
        st = analytics.get("tests", {}).get(t, {}).get("status")
        if st != "ran":
            return False, f"test {t} has status {st!r}"
    return True, v


# ---------------------------------------------------------------- text

_TAG_START = re.compile(r"\[(rule|metric|history):")
PH_RE = re.compile(r"\{\{\s*(\$[^{}|]*?)\s*(?:\|\s*([a-z]+)\s*)?\}\}")


def find_tags(text):
    """[(start, end, kind, ref)] for every [rule:..], [metric:..], [history:..] tag.

    Brackets inside a metric path (["25000"], [0]) are balanced, so the tag ends
    at the matching ']'. An unterminated tag runs to the end of the text."""
    out, pos = [], 0
    while True:
        m = _TAG_START.search(text, pos)
        if not m:
            return out
        depth, j, quote = 1, m.end(), None
        while j < len(text) and depth:
            c = text[j]
            if quote:
                if c == quote:
                    quote = None
            elif c in "\"'":
                quote = c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
            j += 1
        ref = text[m.end():j - 1 if depth == 0 else j].strip()
        out.append((m.start(), j, m.group(1), ref))
        pos = j


_REF_RE = re.compile(r"\b(?:clauses?|paras?|paragraphs?|sections?|rows?|tables?|figures?|"
                     r"appendix|app|part|phase)\.?\s+[A-Z]?\d+(?:\.\d+)*[a-z]?\b", re.I)
_ID_RE = re.compile(r"\b[A-Z]{1,4}-\d+\b|\b[LI][1-5]\b")
_YEAR_RE = re.compile(r"\b(?:19|20)\d\d(?:\s?[/–-]\s?\d{2,4})?\b")
_NUM_RE = re.compile(r"£\s?\d[\d,.]*\s?[km]?\b|\d[\d,]*(?:\.\d+)?\s?%|\b\d[\d,]*\.\d+\b|"
                     r"\b\d{1,3}(?:,\d{3})+\b|\b\d{2,}\b", re.I)


def typed_figures(text):
    """Numbers typed into prose, outside placeholders, citations, references and years."""
    t = PH_RE.sub(" ", text)
    for s, e, _, _ in reversed(find_tags(t)):
        t = t[:s] + " " + t[e:]
    for rx in (_REF_RE, _ID_RE, _YEAR_RE):
        t = rx.sub(" ", t)
    return [m.group(0).strip() for m in _NUM_RE.finditer(t)]


def fmt_value(path, v, fmt):
    """(text, None) or (None, reason). The default format follows the key name."""
    segs = parse_path(path) or [("key", "")]
    last = str(segs[-1][1]).lower()
    if fmt is None:
        if isinstance(v, (bool, str)):
            fmt = "raw"
        elif isinstance(v, (int, float)):
            if any(w in last for w in ("gbp", "total", "amount", "estimate")):
                fmt = "gbp"
            elif last.startswith("share"):
                fmt = "pct"
            elif "ratio" in last:
                fmt = "ratio"
            else:
                fmt = "int" if isinstance(v, int) else "num"
        else:
            return None, "points at a list or object, not a value"
    if fmt == "raw":
        return str(v), None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None, f"format {fmt} needs a number, got {type(v).__name__}"
    if fmt == "gbp":
        return f"£{v:,.0f}", None
    if fmt == "int":
        if v != int(v):
            return None, f"format int on a non-integer value {v}"
        return f"{int(v):,}", None
    if fmt == "pct":
        return f"{v * 100:.0f}%", None
    if fmt == "ratio":
        return f"{v:.2f}", None
    if fmt == "num":
        s = f"{v:,.2f}"
        return (s.rstrip("0").rstrip(".") if "." in s else s), None
    return None, f"unknown format {fmt!r} (use gbp, int, pct, ratio, num or raw)"


def md_cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------- inputs


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path, label):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"STOP: {label} not found at {path}")
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"STOP: {label} at {path} is not valid JSON: {e}")
        sys.exit(2)


def index_history(history):
    """id -> (object, section) for every object with an id, at any depth."""
    idx = {}

    def walk(o, section):
        if isinstance(o, dict):
            if isinstance(o.get("id"), str):
                idx.setdefault(o["id"], (o, section))
            for k, v in o.items():
                walk(v, section if section != "risk_scoring_method" else f"{section}.{k}")
        elif isinstance(o, list):
            for x in o:
                walk(x, section)

    for k, v in history.items():
        walk(v, k)
    return idx


def history_summary(obj, section):
    if section == "audits_completed":
        s = f"{obj.get('audit_title')}: {obj.get('opinion')} ({obj.get('period')})"
    elif section == "follow_ups":
        s = (f"Follow-up of {obj.get('audit_title')}: report opinion {obj.get('opinion_report')}, "
             f"implementation progress {obj.get('implementation_progress')} ({obj.get('period')})")
    elif section == "advisory_reviews":
        s = f"Advisory review: {obj.get('review_title')}"
    elif section == "risk_themes":
        s = f"Risk theme: {obj.get('theme')}"
    elif section.endswith("impact_scale"):
        s = f"Impact {obj.get('score')} {obj.get('label')} (Table 1)"
    elif section.endswith("likelihood_scale"):
        s = f"Likelihood {obj.get('score')} {obj.get('label')}"
    else:
        s = obj.get("item") or obj.get("band") or obj.get("register") or obj.get("description") or ""
    src = (obj.get("sources") or [{}])[0]
    where = f"{src.get('file')} p{src.get('pdf_page')}" if src.get("file") else section
    return str(s)[:200], where


# ---------------------------------------------------------------- scoring method


def parse_range(s):
    s = str(s).strip()
    m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"(?i)up\s+to\s+(\d+)", s)
    if m:
        return 0, int(m.group(1))
    return None


def parse_gbp_band(s):
    """Table 1 financial-loss cell -> (low, high) in £ from its £ figures (CH-4)."""
    vals = [float(n) * (1_000 if u.lower() == "k" else 1_000_000)
            for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*([km])\b", str(s), re.I)]
    if len(vals) == 2:
        return min(vals), max(vals)
    if len(vals) == 1 and ">" in s:
        return vals[0], float("inf")
    if len(vals) == 1 and "less than" in s.lower():
        return 0.0, vals[0]
    return None


class Scoring:
    def __init__(self, history, choices, errors, warnings):
        self.errors, self.warnings = errors, warnings
        m = history.get("risk_scoring_method") or {}
        self.status = m.get("status")
        need = ("likelihood_scale", "impact_scale", "matrix", "bands")
        self.fallback = self.status != "extracted" or not all(m.get(k) for k in need)
        self.choices = {c.get("detect"): c for c in choices.get("choices", []) if c.get("detect")}
        self.conflicts = {}
        if self.fallback:
            return
        self.lik = {x["score"]: x for x in m["likelihood_scale"]}
        self.imp = {x["score"]: x for x in m["impact_scale"]}
        for name, scale in (("likelihood_scale", self.lik), ("impact_scale", self.imp)):
            if sorted(scale) != [1, 2, 3, 4, 5]:
                errors.append(f"history.json {name} does not have scores 1-5")
        self.cells = {}
        for row in m["matrix"]:
            for c in row.get("cells", []):
                self.cells[(c["likelihood_score"], row["impact_score"])] = (c["score"], c["band"], row["id"])
        if len(self.cells) != 25:
            errors.append(f"history.json matrix has {len(self.cells)} cells, expected 25")
        self.bands = []
        for b in m["bands"]:
            r = parse_range(b.get("score_range"))
            if r is None:
                errors.append(f"cannot read score_range {b.get('score_range')!r} of {b.get('id')}")
                continue
            self.bands.append((r[0], r[1], b))
        for (L, I), (score, _, _) in self.cells.items():
            hits = [b for lo, hi, b in self.bands if lo <= score <= hi]
            if len(hits) != 1:
                errors.append(f"matrix score {score} (L{L} x I{I}) falls in {len(hits)} bands, expected 1")
        self.esc = m.get("escalation") or []
        self._detect()

    def band_of(self, score):
        for lo, hi, b in self.bands:
            if lo <= score <= hi:
                return b
        return None

    def _detect(self):
        pairs = sorted({(lab, self.band_of(s)["band"]) for s, lab, _ in self.cells.values()
                        if self.band_of(s) and lab != self.band_of(s)["band"]})
        if pairs:
            self.conflicts["band_label"] = {"pairs": pairs}
        fig4 = None
        for e in self.esc:
            reg = str(e.get("register", "")).lower()
            if "corporate" in reg and not re.search(r"\bor\b", reg):
                for crit in e.get("criteria", []):
                    mm = re.search(r"(?i)score\s+(\d+)\s+or\s+above", crit)
                    if mm:
                        fig4 = (int(mm.group(1)), e["id"])
        t4 = None
        for lo, hi, b in self.bands:
            if "corporate risk register" in str(b.get("escalation", "")).lower():
                t4 = (lo, b["id"])
        if fig4 and t4 and fig4[0] != t4[0]:
            self.conflicts["crr_threshold"] = {"figure4": fig4, "table4": t4}

    def rate(self, L, I):
        """Score, matrix label, band text, escalation and markers for a cell."""
        if self.fallback:
            return {"score": L * I, "matrix_label": None, "band": None, "rag": None,
                    "escalation": None, "response": None, "markers": [], "cell": None}
        score, label, row_id = self.cells[(L, I)]
        b = self.band_of(score)
        markers = []
        ch_label = self.choices.get("band_label")
        band_name = b["band"]
        if "band_label" in self.conflicts and label != b["band"]:
            if ch_label and ch_label.get("use") == "figure1":
                band_name = label
            markers.append((ch_label or {}).get("marker") or "†")
        crr = self.conflicts.get("crr_threshold")
        escalation = b.get("escalation")
        if crr:
            ch = self.choices.get("crr_threshold") or {}
            fig4_on = score >= crr["figure4"][0]
            t4_on = score >= crr["table4"][0]
            if ch.get("use") == "figure4":
                escalation = "Corporate Risk Register (Figure 4: score 9 or above)" if fig4_on else escalation
            if fig4_on != t4_on:
                markers.append(ch.get("marker") or "‡")
        return {"score": score, "matrix_label": label, "band": band_name, "table4_band": b["band"],
                "rag": b.get("rag"), "escalation": escalation, "response": b.get("response"),
                "markers": markers, "cell": row_id, "band_id": b["id"]}

    def lik_label(self, L):
        return FALLBACK_LABELS[L] if self.fallback else self.lik[L]["label"]

    def imp_label(self, I):
        return FALLBACK_LABELS[I] if self.fallback else self.imp[I]["label"]


def check_choices(history, choices, scoring, errors, warnings):
    dis = {d["id"] for d in history.get("discrepancies", [])}
    listed = {c.get("discrepancy") for c in choices.get("choices", [])} | set(choices.get("not_scoring", {}))
    for d in sorted(listed - dis):
        errors.append(f"scoring_choices.json names {d}, which is not in history.json discrepancies "
                      "(history was re-extracted? review the choices)")
    unaddressed = sorted(dis - listed)
    if unaddressed:
        msg = (f"history.json discrepancies not addressed in scoring_choices.json: {', '.join(unaddressed)}. "
               "Add each to choices or not_scoring; a conflict is never resolved silently")
        (warnings if scoring.fallback else errors).append(msg)
    for c in choices.get("choices", []):
        if c.get("use") not in (c.get("options") or {}):
            errors.append(f"scoring_choices.json {c.get('id')}: use {c.get('use')!r} is not one of its options")
    if scoring.fallback:
        return
    for kind in scoring.conflicts:
        if kind not in scoring.choices:
            errors.append(f"conflict {kind} detected in the scoring method but no choice has detect={kind!r}")
    for kind, c in scoring.choices.items():
        if kind not in scoring.conflicts:
            warnings.append(f"scoring_choices.json {c.get('id')}: conflict {kind} is no longer detected; "
                            "the choice is not used")
    rl = (choices.get("rated_level") or {}).get("id")
    levels = {x.get("id") for x in (history.get("risk_scoring_method") or {}).get("evaluation_levels", [])}
    if rl not in levels:
        errors.append(f"scoring_choices.json rated_level {rl!r} is not an evaluation level in history.json")


# ---------------------------------------------------------------- one risk


class Ctx:
    def __init__(self, analytics, history, rules, scoring):
        self.analytics, self.history, self.scoring = analytics, history, scoring
        self.hidx = index_history(history)
        self.rules = {r["rule_id"]: r for r in rules.get("rules", []) if "rule_id" in r}


def process_text(text, field, ctx, out):
    """Resolve the citations and placeholders in one prose field; record what was found."""
    cites, problems = [], []
    pieces, pos = [], 0
    tags = find_tags(text)
    for s, e, kind, ref in tags:
        pieces.append(text[pos:s])
        ok, info, support = False, None, False
        if kind == "rule":
            ok = ref in ctx.rules
            info = ctx.rules.get(ref) if ok else f"no rule_id {ref!r} in rules.json"
            support = ok
            label = ref
        elif kind == "metric":
            ok, info = metric(ctx.analytics, ref)
            support = ok
            label = f"`{ref[2:] if ref.startswith('$.') else ref}`"
            if ok:
                t = test_of(ref)
                if t:
                    out["tests"].add(t)
                elif (parse_path(ref) or [("", "")])[0][1] == "contracts":
                    out["tests"].add("__contracts__")
        else:
            hit = ctx.hidx.get(ref)
            ok = hit is not None
            info = hit if ok else f"no id {ref!r} in history.json"
            support = ok and hit[1] in EVIDENCE_SECTIONS
            label = ref
        cites.append({"kind": kind, "ref": ref, "ok": ok, "support": support, "info": info})
        if ok:
            out["cited"][(kind, ref)] = info
            pieces.append(f"[{label}]")
        else:
            problems.append(f"{field}: [{kind}:{ref}] does not resolve ({info})")
            pieces.append(f"[⚠ unresolved {kind}:{ref}]")
        pos = e
    pieces.append(text[pos:])
    rendered = "".join(pieces)

    def sub(m):
        path, fmt = m.group(1), m.group(2)
        ok, v = resolve(ctx.analytics, path)
        if not ok or v is None:
            out["bad_placeholders"].append(f"{field}: {{{{{path}}}}} does not resolve ({v if not ok else 'null'})")
            return "⚠"
        t = test_of(path)
        if t:
            st = ctx.analytics.get("tests", {}).get(t, {}).get("status")
            if st != "ran":
                out["bad_placeholders"].append(f"{field}: {{{{{path}}}}} is from test {t} with status {st!r}")
                return "⚠"
            out["tests"].add(t)
        txt, err = fmt_value(path, v, fmt)
        if err:
            out["bad_placeholders"].append(f"{field}: {{{{{path}}}}} {err}")
            return "⚠"
        out["figures"].append((path, v, txt))
        return txt

    rendered = PH_RE.sub(sub, rendered)
    leftover = re.findall(r"\{\{[^}]*\}\}?", rendered)
    for x in leftover:
        out["bad_placeholders"].append(f"{field}: malformed placeholder {x!r}")
    for n in typed_figures(text):
        out["warnings"].append(f"{field}: figure typed in prose {n!r}; use a {{{{$.path}}}} placeholder")
    if BANNED_RE.search(PH_RE.sub(" ", text)):
        out["banned"].append(f"{field}: {sorted(set(m.group(1).lower() for m in BANNED_RE.finditer(text)))}")
    out["problems"].extend(problems)
    return rendered, cites


def rate_risk(risk, ctx):
    rid = risk.get("risk_id")
    out = {"risk_id": rid, "title": risk.get("title", ""), "dropped": [], "errors": [], "warnings": [],
           "problems": [], "bad_placeholders": [], "banned": [], "figures": [], "tests": set(), "cited": {}}
    sc = ctx.scoring
    lik = risk.get("likelihood") if isinstance(risk.get("likelihood"), dict) else {}
    imp = risk.get("impact") if isinstance(risk.get("impact"), dict) else {}

    def text(v, field):
        if not isinstance(v, str) or not v.strip():
            return "", []
        return process_text(v, field, ctx, out)

    out["title_r"], _ = text(risk.get("title"), "title")
    out["theme"], _ = text(risk.get("theme"), "theme")
    out["description"], _ = text(risk.get("description"), "description")
    out["lik_just"], lcites = text(lik.get("justification"), "likelihood.justification")
    out["imp_just"], icites = text(imp.get("justification"), "impact.justification")
    ev = risk.get("evidence") or []
    out["evidence"] = [text(e, f"evidence[{i}]")[0] for i, e in enumerate(ev if isinstance(ev, list) else [ev])]
    out["focus"], _ = text(risk.get("proposed_focus"), "proposed_focus")
    upl = lik.get("uplift") if isinstance(lik.get("uplift"), dict) else None
    if upl:
        out["uplift_reason"], _ = text(upl.get("reason"), "likelihood.uplift.reason")

    # Hard rule: each justification cites at least one piece of evidence that resolves.
    if not any(c["support"] for c in lcites):
        out["dropped"].append("likelihood justification has no resolvable evidence citation "
                              "(rule, analytics metric, or audit/theme item from history.json)")
    if not any(c["support"] for c in icites):
        out["dropped"].append("impact justification has no resolvable evidence citation "
                              "(the Table 1 IMP item is the scale, not evidence)")
    if out["bad_placeholders"]:
        out["dropped"].append("figures cannot be filled: " + "; ".join(out["bad_placeholders"]))
    for k in ("title", "description", "proposed_focus"):
        if not isinstance(risk.get(k), str) or not risk.get(k).strip():
            out["dropped"].append(f"{k} is missing")
    out["warnings"].extend(out["problems"])
    if out["dropped"]:
        return out

    E = out["errors"]
    for where, keys in ALLOWED.items():
        blk = risk if not where else (risk.get(where) or {})
        extra = sorted(set(blk) - keys) if isinstance(blk, dict) else []
        if extra:
            E.append(f"{where or 'risk'} has fields the builder does not take: {extra} "
                     "(the builder computes scores and bands; remove them)")
    # likelihood
    step = lik.get("rubric")
    if step not in RUBRIC:
        E.append(f"likelihood.rubric {step!r} is not one of {sorted(RUBRIC)}")
        return out
    base = RUBRIC[step]
    mvals = [c["info"] for c in lcites if c["kind"] == "metric" and c["ok"]]
    if step == "L1" and not any(isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0
                                for v in mvals):
        E.append("rubric L1 needs a cited metric equal to 0 (the test ran and flagged nothing in scope)")
    if step in ("L3", "L4") and not mvals:
        E.append(f"rubric {step} needs at least one [metric:...] citation in the likelihood justification")
    if step == "L4":
        share = lik.get("share")
        paths = ([share] if isinstance(share, str) else
                 [share.get("numerator"), share.get("denominator")] if isinstance(share, dict) else [])
        vals = []
        for p in paths:
            ok, v = metric(ctx.analytics, p)
            if not ok or isinstance(v, bool) or not isinstance(v, (int, float)):
                E.append(f"likelihood.share {p!r} does not resolve to a number ({v if not ok else type(v).__name__})")
            elif test_of(p) in INCOMPLETE_TESTS:
                E.append(f"likelihood.share {p!r} is from {test_of(p)}, whose notices may be incomplete; "
                         "it cannot carry rubric L4")
            else:
                vals.append(v)
        if not paths:
            E.append("rubric L4 needs likelihood.share: a $.path to a share, or {numerator, denominator}")
        elif len(vals) == len(paths):
            frac = vals[0] if len(vals) == 1 else (vals[0] / vals[1] if vals[1] else None)
            if frac is None or not (0 <= frac <= 1):
                E.append(f"likelihood.share gives {frac}, not a fraction between 0 and 1")
            elif frac < PERVASIVE_SHARE:
                E.append(f"rubric L4 needs a share of at least {PERVASIVE_SHARE:g}; the cited share is {frac:.2f}")
            else:
                out["share"] = frac
    L = base
    out["uplift"] = None
    if upl:
        aid = upl.get("audit")
        hit = ctx.hidx.get(aid)
        if not hit or hit[1] not in UPLIFT_SECTIONS:
            E.append(f"likelihood.uplift.audit {aid!r} is not an audit or follow-up in history.json")
        else:
            obj, sect = hit
            ops = [obj.get("opinion")] if sect == "audits_completed" else [obj.get("opinion_report")]
            adverse = any(str(o or "").strip().lower().split(" ")[0] in ADVERSE_OPINIONS for o in ops)
            if sect == "follow_ups" and str(obj.get("implementation_progress", "")).strip().lower() in ADVERSE_PROGRESS:
                adverse = True
            if not adverse:
                E.append(f"likelihood.uplift cites {aid} ({history_summary(obj, sect)[0]}), which is not an "
                         "adverse opinion (Limited or Weak, or Unsatisfactory progress); no uplift")
            elif not isinstance(upl.get("reason"), str) or not upl["reason"].strip():
                E.append("likelihood.uplift.reason is missing: say why the theme is the same")
            else:
                L = min(base + 1, 5)
                out["uplift"] = {"audit": aid, "summary": history_summary(obj, sect)[0]}
                out["cited"][("history", aid)] = hit
    out["lik_step"], out["lik_base"], out["lik_computed"] = step, base, L

    # impact
    I = imp.get("score")
    if not isinstance(I, int) or isinstance(I, bool) or not 1 <= I <= 5:
        E.append(f"impact.score {I!r} is not an integer 1-5")
        return out
    crit = imp.get("criterion")
    if crit not in CRITERIA:
        E.append(f"impact.criterion {crit!r} is not one of {list(CRITERIA)}")
    out["criterion"] = crit
    if not sc.fallback:
        want = sc.imp[I]["id"]
        imp_ids = [c["ref"] for c in icites if c["kind"] == "history" and c["ok"]
                   and str(c["ref"]).startswith("IMP-")]
        if want not in imp_ids:
            E.append(f"impact justification must cite [history:{want}], the Table 1 level for score {I}")
        wrong = [x for x in imp_ids if x != want]
        if wrong:
            E.append(f"impact justification cites {wrong}, which do not match score {I} ({want})")
        if crit in CRITERIA:
            out["criterion_text"] = (sc.imp[I].get("criteria") or {}).get(crit)
        exp = imp.get("exposure")
        if crit == "financial_loss":
            m = PH_RE.fullmatch(exp.strip()) if isinstance(exp, str) else None
            if not m:
                E.append("impact.criterion financial_loss needs impact.exposure as one {{$.path}} placeholder")
            else:
                ok, v = metric(ctx.analytics, m.group(1))
                band = parse_gbp_band((sc.imp[I].get("criteria") or {}).get("financial_loss", ""))
                if not ok or isinstance(v, bool) or not isinstance(v, (int, float)):
                    E.append(f"impact.exposure {m.group(1)} does not resolve to a number")
                elif band is None:
                    E.append(f"cannot read the £ band of {want} in history.json")
                elif not band[0] <= v <= band[1]:
                    fits = [s for s in range(1, 6) if (lambda b: b and b[0] <= v <= b[1])(
                        parse_gbp_band((sc.imp[s].get("criteria") or {}).get("financial_loss", "")))]
                    E.append(f"impact.exposure {fmt_value(m.group(1), v, 'gbp')[0]} is outside the £ band of "
                             f"{want}; Table 1 £ figures give impact {fits} (choice CH-4)")
                else:
                    out["exposure"] = fmt_value(m.group(1), v, "gbp")[0]
                    out["figures"].append((m.group(1), v, out["exposure"]))
                    if test_of(m.group(1)):
                        out["tests"].add(test_of(m.group(1)))
    out["imp_score"] = I

    # overrides (validated against decisions later)
    out["overrides"] = {}
    for k, blk in (("likelihood", lik), ("impact", imp)):
        ov = blk.get("override")
        if ov is None:
            continue
        s = ov.get("score") if isinstance(ov, dict) else None
        if not isinstance(s, int) or isinstance(s, bool) or not 1 <= s <= 5:
            E.append(f"{k}.override.score {s!r} is not an integer 1-5")
            continue
        if ov.get("decision_ref") != rid:
            E.append(f"{k}.override.decision_ref must be {rid}, the auditor's AMEND on this risk")
        out["overrides"][k] = {"score": s, "note": ov.get("note", "")}
    Lf = out["overrides"].get("likelihood", {}).get("score", L)
    If = out["overrides"].get("impact", {}).get("score", I)
    out["L"], out["I"] = Lf, If
    out["rating"] = sc.rate(Lf, If)
    if out["banned"]:
        E.append("accusatory wording (use indicator language): " + "; ".join(out["banned"]))
    return out


# ---------------------------------------------------------------- decisions and state

COMMENTS_MARK = re.compile(r"<!--\s*build_register:\s*revision=(\d+)\s*-->")


def split_row(line):
    cells, cur, i = [], "", 0
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += s[i]
        i += 1
    cells.append(cur.strip())
    return cells


def read_comments(path, errors):
    """(revision or None, {risk_id: (decision, comment)})"""
    if not os.path.exists(path):
        return None, {}
    with open(path) as f:
        txt = f.read()
    m = COMMENTS_MARK.search(txt)
    rev = int(m.group(1)) if m else None
    if m is None:
        errors.append(f"{path} has no build_register revision marker; it was not written by this builder")
    out = {}
    for line in txt.splitlines():
        if not re.match(r"^\|\s*R-\d{2}\s*\|", line):
            continue
        c = split_row(line)
        if len(c) < 5:
            errors.append(f"{path}: row {c[0]} has {len(c)} cells, expected 6")
            continue
        d = c[3].strip().upper()
        if d and d not in DECISIONS:
            errors.append(f"{path}: {c[0]} decision {c[3]!r} is not one of {', '.join(DECISIONS)}")
        if c[0] in out:
            errors.append(f"{path}: {c[0]} appears twice")
        out[c[0]] = (d, c[4].strip())
    return rev, out


def flatten(risk):
    f = {}
    for k, v in risk.items():
        if k == "risk_id":
            continue
        if isinstance(v, dict):
            for kk, vv in v.items():
                f[f"{k}.{kk}"] = json.dumps(vv, sort_keys=True)
        else:
            f[k] = json.dumps(v, sort_keys=True)
    return f


def changed_fields(a, b):
    fa, fb = flatten(a), flatten(b)
    return sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))


def revision_logic(ratings, raw, state, comments, inputs, overrides, errors):
    """Work out the revision number, the pending decisions and what changed.

    raw: {risk_id: risk dict as the agent wrote it};
    overrides: {risk_id: [likelihood|impact]}. Returns info for rendering."""
    revs = state.get("revisions", {})
    cur = max((int(k) for k in revs), default=None)
    file_rev, decisions = comments
    blk = ratings.get("revision")
    info = {"number": 0, "base": None, "changes": [], "pending": {}, "applied": {},
            "decisions": decisions, "summary": None}
    if blk is None:
        if cur is not None and cur >= 1:
            errors.append(f"the register is at revision {cur}; changes after the auditor's decisions need a "
                          f"\"revision\" block in risk-ratings.json (number {cur + 1})")
            return info
        decided = any(d for d, _ in decisions.values())
        if cur == 0 and decided:
            base = revs["0"]
            if base["risks"] != raw:
                errors.append("the auditor has recorded decisions on revision 0 and the ratings have changed since; "
                              "put the changes in a \"revision\" block (number 1) that answers those decisions")
            if base["inputs"] != inputs:
                errors.append("an input changed since revision 0 was built and the auditor has started deciding on it: "
                              + ", ".join(k for k in inputs if inputs[k] != base["inputs"].get(k)))
        for rid, ov in overrides.items():
            errors.append(f"{rid}: {', '.join(ov)} override in a draft; overrides come only from an auditor "
                          "AMEND decision, in a revision")
        info["pending"] = {r: d for r, d in decisions.items() if d[0]}
        return info

    n = blk.get("number")
    info["number"] = n if isinstance(n, int) else 0
    info["summary"] = blk.get("summary")
    if cur is None:
        errors.append("revision block present but no earlier revision is recorded; build revision 0 first "
                      "(remove the revision block)")
        return info
    if not isinstance(n, int) or n < 1 or n not in (cur, cur + 1):
        errors.append(f"revision.number is {n!r}; the last built revision is {cur}, so use {cur + 1} "
                      f"(or {cur} to rebuild it)")
        return info
    base = revs[str(n - 1)]
    info["base"] = n - 1
    applied = {r: a for r, a in state.get("applied", {}).items() if a["applied_in"] < n}
    # A rebuild of revision n finds the comments file already relabelled n.
    if file_rev not in ((n - 1, n) if n == cur else (n - 1,)):
        errors.append(f"auditor-comments.md holds decisions on revision {file_rev}; revision {n} must answer "
                      f"decisions on revision {n - 1}")
    if base["inputs"] != inputs:
        errors.append(f"an input changed since revision {n - 1}, so figures changed that the auditor did not ask "
                      "to change: " + ", ".join(k for k in inputs if inputs[k] != base["inputs"].get(k))
                      + ". Start a new rating cycle with the auditor's agreement")
    for rid in base["rated"]:
        if not decisions.get(rid, ("", ""))[0]:
            errors.append(f"{rid} has no auditor decision in auditor-comments.md (undecided)")
    pending = {}
    for rid, (d, c) in decisions.items():
        if rid in base["risks"] and d:
            a = applied.get(rid)
            if a is None or (a["decision"], a["comment"]) != (d, c):
                pending[rid] = (d, c)
    info["pending"] = pending
    for rid, (d, c) in pending.items():
        if d in ("AMEND", "REJECT") and not c:
            errors.append(f"{rid}: {d} needs a comment saying what to change or why")

    old, new = base["risks"], raw
    actual = {}
    for rid in sorted(set(old) | set(new)):
        if rid not in old:
            actual[rid] = ["added"]
        elif rid not in new:
            actual[rid] = ["removed"]
        else:
            f = changed_fields(old[rid], new[rid])
            if f:
                actual[rid] = f
    declared, refs, notes = {}, {}, {}
    for i, ch in enumerate(blk.get("changes") or []):
        rid, fields, ref = ch.get("risk_id"), ch.get("fields"), ch.get("decision_ref")
        if not isinstance(fields, list) or not fields or not ch.get("note"):
            errors.append(f"revision.changes[{i}] needs risk_id, a non-empty fields list, decision_ref and note")
            continue
        if rid in declared:
            errors.append(f"revision.changes lists {rid} twice; put all its fields in one entry")
        declared[rid], refs[rid], notes[rid] = sorted(fields), ref, ch["note"]
    for rid in sorted(set(actual) | set(declared)):
        act, dec = actual.get(rid, []), declared.get(rid)
        if dec is None:
            errors.append(f"{rid} changed ({', '.join(act)}) but the revision block does not list it: "
                          "the auditor did not ask for this change")
            continue
        if act != dec:
            extra, missing = sorted(set(act) - set(dec)), sorted(set(dec) - set(act))
            if extra:
                errors.append(f"{rid}: {', '.join(extra)} changed but not declared; the auditor did not ask for it")
            if missing:
                errors.append(f"{rid}: {', '.join(missing)} declared as changed but unchanged")
        ref = refs[rid]
        if act == ["removed"] and pending.get(rid, ("",))[0] == "REJECT":
            errors.append(f"{rid}: keep rejected risks in risk-ratings.json; the register lists them as out of scope")
        need_ref = ref if act == ["added"] else rid
        if ref != need_ref:
            errors.append(f"{rid}: decision_ref must be {rid}, the auditor's decision on this risk")
        elif pending.get(ref, ("",))[0] != "AMEND":
            errors.append(f"{rid}: change is not backed by a pending AMEND decision on {ref} "
                          f"(decision there: {decisions.get(ref, ('none',))[0] or 'blank'})")
        info["changes"].append({"risk_id": rid, "fields": act, "decision_ref": ref, "note": notes[rid]})
    used = {c["decision_ref"] for c in info["changes"]}
    for rid, (d, c) in pending.items():
        if d == "AMEND" and rid not in used:
            errors.append(f"{rid}: the auditor's AMEND ({c!r}) is not applied; change the risk and list it in "
                          "revision.changes with decision_ref")
    for rid, ov in overrides.items():
        amend_now = pending.get(rid, ("",))[0] == "AMEND"
        amend_before = applied.get(rid, {}).get("decision") == "AMEND"
        if not (amend_now or amend_before):
            errors.append(f"{rid}: {', '.join(ov)} override has no auditor AMEND decision behind it")
    new_applied = dict(applied)
    for rid, (d, c) in pending.items():
        new_applied[rid] = {"decision": d, "comment": c, "applied_in": n}
    info["applied"] = new_applied
    return info


# ---------------------------------------------------------------- rendering


def rating_text(v):
    r = v["rating"]
    s = f"L{v['L']} × I{v['I']} → {r['score']}"
    return s


def band_text(r, scoring):
    if scoring.fallback:
        return "n/a (fallback)"
    rag = f" ({r['rag']})" if r.get("rag") else " (no colour stated, GAP-07)"
    return f"{r['band']}{rag}{''.join(r['markers'])}"


def scope_of(rid, info):
    a = info["applied"].get(rid)
    if a and a["decision"] == "REJECT":
        return "out of scope (auditor)"
    if a and a["decision"] in ("APPROVE", "AMEND"):
        return "in scope"
    return "proposed"


def status_of(rid, info):
    d = info["decisions"].get(rid, ("", ""))
    a = info["applied"].get(rid)
    if not d[0]:
        return "awaiting decision"
    if a and (a["decision"], a["comment"]) == d:
        return f"applied in revision {a['applied_in']}"
    return f"to apply in revision {info['number'] + 1}"


def render_register(ctx, views, dropped, info, choices, inputs, ratings, not_rated, date):
    sc = ctx.scoring
    L = []
    w = L.append
    n = info["number"]
    w("# Procurement risk register: West Berkshire Council")
    w("")
    kind = "draft for auditor review" if n == 0 else f"revised after the auditor's decisions on revision {info['base']}"
    w(f"**Revision {n}** ({kind}). Built {date} by `.claude/skills/risk-assessment/build_register.py` "
      "from `outputs/risk-ratings.json`; every figure, score and band below was filled in by the builder.")
    w("")
    w(f"> {LANGUAGE}")
    w("")
    decided = sum(1 for v in views if info["decisions"].get(v["risk_id"], ("",))[0])
    w(f"**Status:** {len(views)} risk{'s' if len(views) != 1 else ''} rated; {len(dropped)} excluded for missing citations or figures; "
      f"auditor decisions recorded for {decided} of {len(views)}. Decisions go in `outputs/auditor-comments.md`.")
    w("")
    if n >= 1:
        w(f"## Revision {n}: changes since revision {info['base']}")
        w("")
        if info.get("summary"):
            w(info["summary"])
            w("")
        cnt = {d: sum(1 for x in info["pending"].values() if x[0] == d) for d in DECISIONS}
        w(f"Decisions answered in this revision: {cnt['APPROVE']} APPROVE, {cnt['AMEND']} AMEND, "
          f"{cnt['REJECT']} REJECT.")
        w("")
        if info["changes"]:
            w("| Risk | What changed | Auditor decision | Note |")
            w("| --- | --- | --- | --- |")
            for c in info["changes"]:
                d = info["decisions"].get(c["decision_ref"], ("", ""))
                w(f"| {c['risk_id']} | {md_cell(', '.join(c['fields']))} | {d[0]} on {c['decision_ref']}: "
                  f"{md_cell(d[1])} | {md_cell(c['note'])} |")
        else:
            w("No risk changed.")
        w("")
        ovs = [(v["risk_id"], k, o) for v in views for k, o in v.get("overrides", {}).items()]
        if ovs:
            w("**Auditor overrides** (the score differs from the evidence rubric because the auditor asked):")
            for rid, k, o in ovs:
                v = next(x for x in views if x["risk_id"] == rid)
                base = v["lik_computed"] if k == "likelihood" else v["imp_score"]
                w(f"- {rid} {k}: **{o['score']}** (the rubric gives {base}). {o['note']}")
            w("")
        rej = [r for r, (d, _) in info["pending"].items() if d == "REJECT"]
        if rej:
            w("**Moved out of scope by the auditor:** " + ", ".join(rej) + ".")
            w("")
        unchanged = [v["risk_id"] for v in views if v["risk_id"] not in {c["risk_id"] for c in info["changes"]}]
        if unchanged:
            w("Unchanged since revision " + str(info["base"]) + ": " + ", ".join(unchanged) + ".")
            w("")

    w("## Inputs")
    w("")
    w("| File | sha256 |")
    w("| --- | --- |")
    for k, v in inputs.items():
        w(f"| `{k}` | `{v[:16]}…` |")
    w("")
    w("## Scoring method")
    w("")
    hm = ctx.history.get("risk_scoring_method") or {}
    if sc.fallback:
        w(f"**Fallback.** history.json reports no usable council scoring method (status {sc.status!r}). "
          "Likelihood and impact use 1–5 Very low…Very high; the score is likelihood × impact, a fallback "
          "convention and not the council's; no bands are given.")
    else:
        w(f"- **Council method:** {hm.get('document')}, as extracted into `outputs/history.json` "
          "(`risk_scoring_method`). Likelihood LIK-1…LIK-5 (" +
          ", ".join(f"{s} {sc.lik[s]['label']}" for s in range(1, 6)) + "); impact IMP-1…IMP-5 (" +
          ", ".join(f"{s} {sc.imp[s]['label']}" for s in range(1, 6)) + ").")
        w("- **Score:** read from the Figure 1 matrix cell for the likelihood and impact (MTX-I1…MTX-I5). "
          "The strategy states no formula (GAP-06), so the builder looks the cell up rather than multiplying. "
          "The matrix was rebuilt from the PDF layout by findings-analyst.")
        w("- **Band, colour, escalation and response:** Table 4 (BND-1…BND-4), matched on the cell's score. "
          "Table 4 prints no colour for Moderate (GAP-07).")
        rl = choices.get("rated_level") or {}
        lvl = ctx.hidx.get(rl.get("id"), ({}, ""))[0]
        w(f"- **Level rated:** {lvl.get('level')} ({rl.get('id')}): {rl.get('why')}")
    w("- **Likelihood rubric** (SKILL.md): L1 test ran and flagged nothing in scope = 1; L2 inherent risk "
      "only, or a weak or explained signal = 2; L3 signal in a procurement-relevant scope = 3; L4 the same "
      f"and pervasive (share at least {PERVASIVE_SHARE:.0%}, from a test without the missing-notices caveat) = 4. "
      "Likelihood 5 only through the uplift or an auditor override.")
    w("- **Repeat-finding uplift:** +1 when a prior audit on the same theme had an adverse opinion. The "
      "papers do not define the opinion levels (GAP-05); the builder reads Limited and Weak (and Unsatisfactory "
      "follow-up progress) as adverse.")
    w("- **Hard rule:** each likelihood and impact justification cites at least one rule, analytics metric or "
      "audit/theme item that resolves. A risk without one is excluded and listed at the end.")
    w("")
    if not sc.fallback:
        w("### Conflicts in the scoring method")
        w("")
        w("The strategy contradicts itself in places. Each conflict below uses one reading and marks the other; "
          "the choices are in `.claude/skills/risk-assessment/scoring_choices.json` for the auditor to change.")
        w("")
        w("| Choice | Discrepancy | Topic | Used | Other reading (marked) |")
        w("| --- | --- | --- | --- | --- |")
        for c in choices.get("choices", []):
            used = c["options"][c["use"]]
            others = "; ".join(v for k, v in c["options"].items() if k != c["use"])
            mk = f" — marked **{c['marker']}** where it gives a different result" if c.get("marker") else ""
            detected = ""
            if c.get("detect") in sc.conflicts:
                det = sc.conflicts[c["detect"]]
                if c["detect"] == "crr_threshold":
                    detected = (f" (detected: {det['figure4'][1]} score {det['figure4'][0]} or above vs "
                                f"{det['table4'][1]} from {det['table4'][0]})")
                else:
                    detected = " (detected: " + ", ".join(f"Figure 1 '{a}' vs Table 4 '{b}'"
                                                         for a, b in det["pairs"]) + ")"
            w(f"| {c['id']} | {c['discrepancy']} | {md_cell(c['topic'])} | {md_cell(used)}{md_cell(detected)} | "
              f"{md_cell(others)}{mk} |")
        ns = choices.get("not_scoring", {})
        if ns:
            w("")
            w("Discrepancies that do not affect scoring: " +
              "; ".join(f"{k} ({v})" for k, v in ns.items()))
        w("")

    w("## Summary")
    w("")
    w("| Risk | Title | Likelihood | Impact | Score | Matrix label | Band | Escalation (used reading) | Scope |")
    w("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    order = sorted(views, key=lambda v: (scope_of(v["risk_id"], info) == "out of scope (auditor)",
                                         -v["rating"]["score"], -v["L"], v["risk_id"]))
    for v in order:
        r = v["rating"]
        lo = " (override)" if "likelihood" in v["overrides"] else ""
        io = " (override)" if "impact" in v["overrides"] else ""
        w(f"| {v['risk_id']} | {md_cell(v['title_r'])} | {v['L']} {sc.lik_label(v['L'])}{lo} | "
          f"{v['I']} {sc.imp_label(v['I'])}{io} | {r['score']} | {r['matrix_label'] or 'n/a'} | "
          f"{md_cell(band_text(r, sc))} | {md_cell(r['escalation'] or 'n/a')} | {scope_of(v['risk_id'], info)} |")
    w("")
    shown = {mk for v in views for mk in v["rating"]["markers"]}
    marks = [c for c in choices.get("choices", []) if c.get("marker") in shown]
    for c in marks:
        w(f"{c['marker']} {c['topic']}: the other reading ({'; '.join(v for k, v in c['options'].items() if k != c['use'])}) "
          f"gives a different result for this risk ({c['id']}, {c['discrepancy']}).  ")
    w("")

    w("## Risks")
    w("")
    for v in order:
        r = v["rating"]
        w(f"### {v['risk_id']} · {v['title_r']}")
        w("")
        w(f"**Rating:** likelihood {v['L']} × impact {v['I']} → score **{r['score']}**"
          + ("" if sc.fallback else f" (cell {r['cell']}); matrix label {r['matrix_label']}; "
             f"band **{band_text(r, sc)}**; escalation: {str(r['escalation']).rstrip('.')}; "
             f"response: {str(r['response']).rstrip('.')}")
          + f". Scope: {scope_of(v['risk_id'], info)}.")
        w("")
        w(f"**Risk.** {v['description']}" + (f" *Theme: {v['theme']}.*" if v.get("theme") else ""))
        w("")
        lo = v["overrides"].get("likelihood")
        head = f"**Likelihood {v['L']} {sc.lik_label(v['L'])}**"
        if lo:
            head += (f" — **auditor override**; the rubric gives {v['lik_computed']} (step {v['lik_step']}"
                     f"{', +1 uplift' if v['uplift'] else ''}). {lo['note']}")
        else:
            head += f" (rubric step {v['lik_step']}: {v['lik_base']}" + (", +1 repeat-finding uplift" if v["uplift"] else "") + ")"
        w(f"{head}. {v['lik_just']}")
        if v["uplift"]:
            w("")
            w(f"*Repeat-finding uplift +1:* [{v['uplift']['audit']}] {v['uplift']['summary']}. {v.get('uplift_reason', '')}")
        if v.get("share") is not None:
            w("")
            w(f"*Pervasiveness (rubric L4):* flagged share {v['share']:.0%} of the scoped population.")
        w("")
        io = v["overrides"].get("impact")
        crit = (v.get("criterion") or "").replace("_", " ")
        ct = f" Table 1, {crit}: \"{v['criterion_text'].rstrip('.')}\"." if v.get("criterion_text") else ""
        exp = f" Value exposed: {v['exposure']}." if v.get("exposure") else ""
        head = f"**Impact {v['I']} {sc.imp_label(v['I'])}**"
        if io:
            head += f" — **auditor override**; the agent rated {v['imp_score']}. {io['note']}"
        w(f"{head}.{ct}{exp} {v['imp_just']}")
        w("")
        if v["evidence"]:
            w("**Evidence.**")
            for e in v["evidence"]:
                w(f"- {e}")
            w("")
        w(f"**Proposed focus.** {v['focus']}")
        w("")
        cav = []
        for t in sorted(v["tests"]):
            src = ctx.analytics.get("contracts", {}) if t == "__contracts__" else ctx.analytics["tests"].get(t, {})
            for c in src.get("caveats") or []:
                cav.append((t if t != "__contracts__" else "contracts", c))
        if cav:
            w("**Caveats carried from analytics.json.**")
            for t, c in cav:
                w(f"- ({t}) {c}")
            w("")
        d = info["decisions"].get(v["risk_id"], ("", ""))
        w(f"**Auditor decision:** {d[0] + (': ' + d[1] if d[1] else '') + ' (' + status_of(v['risk_id'], info) + ')' if d[0] else 'none yet'}.")
        w("")

    if not_rated:
        w("## Considered and not rated")
        w("")
        for x in not_rated:
            w(f"- **{x['topic']}**: {x['rendered']}")
        w("")
    if dropped:
        w("## Excluded risks")
        w("")
        w("Excluded by the hard rule or because a figure could not be filled. Fix the citations in "
          "`outputs/risk-ratings.json` and rebuild.")
        w("")
        for v in dropped:
            w(f"- **{v['risk_id']} · {v['title']}**: " + "; ".join(v["dropped"]))
        w("")

    w("## Citations")
    w("")
    w("| Citation | Resolves to | Source |")
    w("| --- | --- | --- |")
    cited = {}
    for v in views:
        cited.update(v["cited"])
    for x in not_rated:
        cited.update(x["cited"])
    for (kind, ref) in sorted(cited, key=lambda k: (k[0], str(k[1]))):
        info_ = cited[(kind, ref)]
        if kind == "rule":
            w(f"| {ref} | {md_cell(info_.get('clause'))}: \"{md_cell(info_.get('verbatim_quote'))}\" | "
              f"contract-rules.pdf p{info_.get('page')} |")
        elif kind == "metric":
            val = info_ if not isinstance(info_, (dict, list)) else f"({type(info_).__name__} of {len(info_)})"
            w(f"| `{ref}` | {md_cell(val)} | analytics.json |")
        else:
            s, where = history_summary(*info_)
            w(f"| {ref} | {md_cell(s)} | {md_cell(where)} |")
    w("")
    w("## Figures")
    w("")
    w("Every figure in this register, with its path in `outputs/analytics.json` and the value before rounding.")
    w("")
    w("| Shown | Path | Value |")
    w("| --- | --- | --- |")
    seen = set()
    for v in views + not_rated:
        for p, val, txt in v["figures"]:
            if (p, txt) not in seen:
                seen.add((p, txt))
                w(f"| {txt} | `{md_cell(p)}` | {val} |")
    w("")
    w("## Auditor decisions")
    w("")
    w("Record decisions in `outputs/auditor-comments.md` (APPROVE, AMEND or REJECT, with a comment for AMEND "
      "and REJECT), then have the risk-assessor re-run. This table is a copy and is rewritten on every build.")
    w("")
    w("| Risk | Rating | Decision | Comment | Status |")
    w("| --- | --- | --- | --- | --- |")
    for v in sorted(views, key=lambda x: x["risk_id"]):
        d = info["decisions"].get(v["risk_id"], ("", ""))
        w(f"| {v['risk_id']} | {rating_text(v)}, {md_cell(band_text(v['rating'], sc))} | {d[0]} | "
          f"{md_cell(d[1])} | {status_of(v['risk_id'], info)} |")
    w("")
    return "\n".join(L)


def render_comments(views, info, sc, orphans):
    n = info["number"]
    L = [f"# Auditor decisions: risk register revision {n}", "",
         f"<!-- build_register: revision={n} -->", "",
         "Fill in **Decision** and **Comment** for every risk in `outputs/risk-register.md`, then ask for the "
         "risk-assessor to be re-run. The next revision must answer every decision, and may change only what "
         "you ask for.", "",
         "- **APPROVE**: in scope as rated.",
         "- **AMEND**: in scope once changed. Say in Comment what to change (a rating, wording, evidence, focus, "
         "or a risk to add). A rating you set yourself is shown in the register as an auditor override.",
         "- **REJECT**: out of scope. Say why in Comment.", "",
         "Edit only the Decision and Comment cells; the builder writes the other columns and keeps your entries "
         "when it rewrites this file. Write `\\|` for a pipe inside a comment.", "",
         "| Risk | Title | Rating | Decision | Comment | Status |",
         "| --- | --- | --- | --- | --- | --- |"]
    for v in sorted(views, key=lambda x: x["risk_id"]):
        d = info["decisions"].get(v["risk_id"], ("", ""))
        L.append(f"| {v['risk_id']} | {md_cell(v['title'])} | {rating_text(v)}, {md_cell(band_text(v['rating'], sc))} "
                 f"| {d[0]} | {md_cell(d[1])} | {status_of(v['risk_id'], info)} |")
    if orphans:
        L += ["", "## Decisions on risks no longer rated", "",
              "Kept so nothing you wrote is lost. These risks were excluded or removed.", "",
              "| Risk | Title | Rating | Decision | Comment | Status |",
              "| --- | --- | --- | --- | --- | --- |"]
        for rid, (d, c) in sorted(orphans.items()):
            L.append(f"| {rid} | | | {d} | {md_cell(c)} | not in this revision |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    out_default = os.path.join(ROOT, "outputs")
    ap.add_argument("--ratings", default=os.path.join(out_default, "risk-ratings.json"))
    ap.add_argument("--analytics", default=os.path.join(out_default, "analytics.json"))
    ap.add_argument("--history", default=os.path.join(out_default, "history.json"))
    ap.add_argument("--rules", default=os.path.join(out_default, "rules.json"))
    ap.add_argument("--choices", default=os.path.join(HERE, "scoring_choices.json"))
    ap.add_argument("--out-dir", default=out_default)
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    a = ap.parse_args()

    ratings = load_json(a.ratings, "risk-ratings.json")
    analytics = load_json(a.analytics, "analytics.json")
    history = load_json(a.history, "history.json")
    rules = load_json(a.rules, "rules.json")
    choices = load_json(a.choices, "scoring_choices.json")
    inputs = {"outputs/analytics.json": sha256(a.analytics), "outputs/history.json": sha256(a.history),
              "outputs/rules.json": sha256(a.rules), "scoring_choices.json": sha256(a.choices)}
    errors, warnings = [], []
    sc_status = (analytics.get("self_check") or {}).get("status")
    if sc_status != "PASS":
        errors.append(f"analytics.json self_check status is {sc_status!r}, not PASS; re-run spend-analyst first")

    scoring = Scoring(history, choices, errors, warnings)
    check_choices(history, choices, scoring, errors, warnings)
    if scoring.fallback:
        warnings.append(f"history.json scoring method not usable (status {scoring.status!r}); fallback scale used")
    ctx = Ctx(analytics, history, rules, scoring)

    risks = ratings.get("risks")
    if not isinstance(risks, list) or not risks:
        errors.append("risk-ratings.json has no \"risks\" list")
        risks = []
    raw, views, dropped, ids = {}, [], [], set()
    for i, r in enumerate(risks):
        rid = r.get("risk_id") if isinstance(r, dict) else None
        if not isinstance(rid, str) or not RISK_ID_RE.match(rid):
            errors.append(f"risks[{i}]: risk_id {rid!r} is not of the form R-01")
            continue
        if rid in ids:
            errors.append(f"{rid} appears twice")
            continue
        ids.add(rid)
        raw[rid] = r
        v = rate_risk(r, ctx)
        for wmsg in v["warnings"]:
            warnings.append(f"{rid} {wmsg}")
        if v["dropped"]:
            dropped.append(v)
            continue
        for e in v["errors"]:
            errors.append(f"{rid} {e}")
        if not v["errors"]:
            views.append(v)

    not_rated = []
    for i, x in enumerate(ratings.get("not_rated") or []):
        out = {"risk_id": f"not_rated[{i}]", "dropped": [], "errors": [], "warnings": [], "problems": [],
               "bad_placeholders": [], "banned": [], "figures": [], "tests": set(), "cited": {}}
        txt, cites = process_text(x.get("reason", ""), f"not_rated[{i}].reason", ctx, out)
        for p in out["problems"] + out["bad_placeholders"]:
            errors.append(p)
        if out["banned"]:
            errors.append(f"not_rated[{i}]: accusatory wording {out['banned']}")
        warnings.extend(out["warnings"])
        if not any(c["ok"] for c in cites):
            errors.append(f"not_rated[{i}] ({x.get('topic')}): the reason must cite what was considered")
        not_rated.append({"topic": x.get("topic", ""), "rendered": txt, "cited": out["cited"],
                          "figures": out["figures"], "tests": out["tests"]})

    covered = set().union(*(v["tests"] for v in views), *(x["tests"] for x in not_rated)) if (views or not_rated) else set()
    for t, body in analytics.get("tests", {}).items():
        if body.get("status") == "ran" and t not in covered:
            warnings.append(f"test {t} ran but no rated risk or not_rated entry cites it")

    state_path = os.path.join(a.out_dir, "risk-register.state.json")
    comments_path = os.path.join(a.out_dir, "auditor-comments.md")
    state = load_json(state_path, "state") if os.path.exists(state_path) else {"revisions": {}, "applied": {}}
    comments = read_comments(comments_path, errors)
    overrides = {v["risk_id"]: sorted(v["overrides"]) for v in views if v.get("overrides")}
    info = revision_logic(ratings, raw, state, comments, inputs, overrides, errors)

    for wmsg in warnings:
        print(f"WARN  {wmsg}")
    for v in dropped:
        print(f"DROP  {v['risk_id']} ({v['title']}): " + "; ".join(v["dropped"]))
    if errors or (a.strict and warnings):
        for e in errors:
            print(f"ERROR {e}")
        if a.strict and warnings and not errors:
            print("ERROR warnings present and --strict given")
        print(f"FAILED: {len(errors)} error(s); nothing written")
        return 1

    date = datetime.date.today().isoformat()
    os.makedirs(a.out_dir, exist_ok=True)
    reg = render_register(ctx, views, dropped, info, choices, inputs, ratings, not_rated, date)
    with open(os.path.join(a.out_dir, "risk-register.md"), "w") as f:
        f.write(reg)
    rated = {v["risk_id"] for v in views}
    orphans = {r: d for r, d in info["decisions"].items() if r not in rated and (d[0] or d[1])}
    with open(comments_path, "w") as f:
        f.write(render_comments(views, info, scoring, orphans))
    n = info["number"]
    state.setdefault("revisions", {})
    for k in [k for k in state["revisions"] if int(k) > n]:
        del state["revisions"][k]
    state["revisions"][str(n)] = {"risks": raw, "rated": sorted(rated), "inputs": inputs, "built_on": date}
    state["applied"] = info["applied"]
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    reg_path = os.path.abspath(os.path.join(a.out_dir, "risk-register.md"))
    shown = os.path.relpath(reg_path, ROOT) if reg_path.startswith(ROOT + os.sep) else reg_path
    print(f"BUILT revision {n}: {len(views)} rated, {len(dropped)} excluded, {len(warnings)} warning(s) -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
