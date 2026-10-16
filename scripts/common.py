"""Shared helpers for the spend-analyst pipeline.

Reads: outputs/rules.json (via load_rules / load_tiers, when called).
Writes: nothing.

Provides paths, supplier-name normalisation, trading-name splitting, tier
loading from rules.json (looked up by clause, never by number), the single
inclusivity helper used by every test, method constants from CLAUDE.md and
the banned-word list for the language scan.
"""
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SPEND_DIR = os.path.join(DATA, "spend")
CONTRACTS_CSV = os.path.join(DATA, "contracts.csv")
OUT = os.path.join(ROOT, "outputs")
FULL = os.path.join(OUT, "analytics-full")
RULES_JSON = os.path.join(OUT, "rules.json")
ANALYTICS_JSON = os.path.join(OUT, "analytics.json")
SHEET = "Data to publish"
SPEND_COLUMNS = ["Service", "Expenditure category", "Narrative", "Date",
                 "Net amount", "Supplier name"]

# Method constants (source: CLAUDE.md). Not monetary thresholds.
METHOD_PARAMETERS = {
    "clustering_band_low_factor": 0.9,
    "comparison_band_low_factor": 0.8,
    "split_window_days": 30,
    "duplicate_window_days": 7,
    "spend_vs_award_flag_ratio": 1.25,
}

# Contracts Finder download row cap (source: CLAUDE.md). A row count, not money.
# Its value equals the lowest App B tier, so self_check.py exempts this one line by name.
CONTRACTS_FINDER_EXPORT_ROW_CAP = 1000

LANGUAGE = ("All results are risk indicators to investigate, not findings about "
            "the council, any department or any supplier.")

BANNED_WORDS = ["fraud", "fraudulent", "corrupt", "corruption", "breach",
                "breached", "non-compliant", "noncompliant", "violation",
                "violated", "illegal", "unlawful", "wrongdoing", "misconduct",
                "abuse", "suspicious", "theft", "rogue"]
BANNED_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(w) for w in
                       sorted(BANNED_WORDS, key=len, reverse=True)) + r")(?![a-z])",
                       re.IGNORECASE)

TAGS = ["care_or_education_placement", "grant", "agency_staff", "premises",
        "general_procurement"]

_SUFFIX_RE = re.compile(r"\b(LTD|LIMITED|PLC|LLP)\b")
_TRADING_RE = re.compile(r"\b(?:T A|T AS|TRADING AS|FORMERLY)\b")


class StopError(Exception):
    """Missing or malformed input: stop and report."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def normalise_supplier(s):
    """Normalise a supplier name; the same steps for spend and contracts."""
    if s is None:
        return ""
    n = str(s).upper()
    n = n.replace("&", " AND ")
    n = n.replace("'", "").replace("’", "")
    n = re.sub(r"[^A-Z0-9]", " ", n)
    n = _SUFFIX_RE.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def trading_parts(n):
    """Split a normalised name on trading markers; parts of >= 4 chars.

    Used only to generate candidates, never matches.
    """
    parts = [p.strip() for p in _TRADING_RE.split(n or "")]
    return [p for p in parts if len(p) >= 4]


def load_rules():
    if not os.path.exists(RULES_JSON):
        raise StopError("outputs/rules.json is missing")
    try:
        with open(RULES_JSON) as f:
            rules = json.load(f)
    except Exception as e:  # noqa: BLE001
        raise StopError(f"outputs/rules.json failed to parse: {e}")
    if not isinstance(rules, dict) or "rules" not in rules:
        raise StopError("outputs/rules.json has no 'rules' array")
    return rules


def _by_clause(rules, clause):
    hits = [r for r in rules["rules"] if r.get("clause") == clause]
    if len(hits) != 1:
        raise StopError(f"rules.json: expected exactly one rule with clause "
                        f"'{clause}', found {len(hits)}")
    return hits[0]


def _param(rules, ref):
    params = rules.get("parameters") or {}
    if ref not in params:
        raise StopError(f"rules.json: parameter '{ref}' referenced but not defined")
    return params[ref].get("value")


def load_tiers(rules):
    """Return (tiers, skipped) built from rules.json, looked up by clause."""
    a = _by_clause(rules, "App B row A")
    b1 = _by_clause(rules, "App B row B1")
    b2 = _by_clause(rules, "App B row B2")
    b1adv = _by_clause(rules, "App B row B1 (advertising)")
    c = _by_clause(rules, "App B row C")
    d = _by_clause(rules, "App B row D")
    b2adv = None
    try:
        b2adv = _by_clause(rules, "App B row B2 (advertising)")
    except StopError:
        b2adv = None
    if b1.get("threshold_low") != b2.get("threshold_low"):
        raise StopError("rules.json: App B row B1 and row B2 threshold_low differ")
    if b1.get("threshold_low_inclusive") != b2.get("threshold_low_inclusive"):
        raise StopError("rules.json: App B row B1 and row B2 inclusivity differ")

    tiers, skipped = [], []

    def add(tier, value, inclusive, rule_ids, tests, parameter=None):
        if value is None:
            skipped.append({"tier": tier, "parameter": parameter,
                            "rule_ids": rule_ids,
                            "reason": "parameter value is null in rules.json; "
                                      "auditor to supply with citation"})
            return
        if inclusive is None:
            raise StopError(f"rules.json: tier {tier} has no inclusivity flag")
        tiers.append({"tier": tier, "value": value,
                      "lower_edge_inclusive": bool(inclusive),
                      "rule_ids": rule_ids, "tests": tests})

    add("one_quote", a.get("threshold_low"), a.get("threshold_low_inclusive"),
        [a["rule_id"]], ["threshold_clustering", "split_purchases"])
    add("three_quotes_and_notice", b1.get("threshold_low"),
        b1.get("threshold_low_inclusive"), [b1["rule_id"], b2["rule_id"]],
        ["threshold_clustering", "split_purchases", "high_value_suppliers"])
    notice_ids = [b1adv["rule_id"]] + ([b2adv["rule_id"]] if b2adv else [])
    add("notice_publication", b1adv.get("threshold_low"),
        b1adv.get("threshold_low_inclusive"), notice_ids,
        ["threshold_clustering", "split_purchases", "off_contract"])
    if b2.get("threshold_high") != c.get("threshold_low"):
        raise StopError("rules.json: App B row B2 upper bound and row C lower "
                        "bound differ")
    add("works_tender", c.get("threshold_low"), c.get("threshold_low_inclusive"),
        [b2["rule_id"], c["rule_id"]],
        ["threshold_clustering", "split_purchases"])
    ref = b1.get("threshold_high_ref")
    add("statutory_goods_services", _param(rules, ref) if ref else None,
        not b1.get("threshold_high_inclusive", False), [b1["rule_id"]],
        ["threshold_clustering", "split_purchases"], parameter=ref)
    ref_c = c.get("threshold_high_ref")
    ref_d = d.get("threshold_low_ref")
    val = _param(rules, ref_c) if ref_c else None
    add("statutory_relevant", val, d.get("threshold_low_inclusive"),
        [c["rule_id"], d["rule_id"]],
        ["threshold_clustering", "split_purchases"],
        parameter=ref_c if ref_c == ref_d else f"{ref_c} / {ref_d}")
    return tiers, skipped


def testing_thresholds(tiers):
    """Distinct non-null T values, each with its merged roles and rule_ids."""
    out = {}
    for t in tiers:
        v = t["value"]
        e = out.setdefault(v, {"T": v, "roles": [], "rule_ids": [],
                               "lower_edge_inclusive": t["lower_edge_inclusive"]})
        if e["lower_edge_inclusive"] != t["lower_edge_inclusive"]:
            raise StopError(f"tiers sharing value {v} disagree on inclusivity")
        e["roles"].append(t["tier"])
        for r in t["rule_ids"]:
            if r not in e["rule_ids"]:
                e["rule_ids"].append(r)
    return [out[k] for k in sorted(out)]


# ---- the single inclusivity helper -------------------------------------
def enters_tier(amount, T, inclusive):
    """True when amount enters the tier: >= T if inclusive, > T otherwise."""
    return amount >= T if inclusive else amount > T


def just_under(amount, T, inclusive):
    """True when amount stays under the tier (complement of enters_tier)."""
    return not enters_tier(amount, T, inclusive)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
