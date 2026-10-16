#!/usr/bin/env python3
"""Verify outputs/rules.json against the Contract Rules PDF.

Usage: python3 verify_quotes.py <rules.json> <contract-rules.pdf>

Checks: JSON parses; top-level structure; required rule fields and types;
rule_ids unique and sequential (CPR-01, CPR-02, ...); every threshold_*_ref
declared in `parameters`; every verbatim_quote found in the PDF text; the
`page` field matches the page where the quote was found; excluded entries
well-formed.

Quote matching ignores only: whitespace differences, bullet glyphs, page
footers (a `.docx` filename line plus the page-number line after it) and
curly-vs-straight quote characters. Nothing else is normalised.

Exit 0 and print ALL CHECKS PASSED only when every check passes.
Standard library only (pypdf used as a fallback if pdftotext is missing).
"""
import json
import re
import shutil
import subprocess
import sys

RULE_FIELDS = {
    "rule_id": str,
    "clause": str,
    "page": int,
    "type": str,
    "scope": str,
    "condition": str,
    "threshold_low": (int, type(None)),
    "threshold_low_inclusive": (bool, type(None)),
    "threshold_high": (int, type(None)),
    "threshold_high_inclusive": (bool, type(None)),
    "threshold_high_ref": (str, type(None)),
    "required_action": str,
    "approver": (str, type(None)),
    "evidence_source": str,
    "verbatim_quote": str,
}
OPTIONAL_RULE_FIELDS = {"threshold_low_ref": (str, type(None))}
ENUMS = {
    "type": {"threshold", "required-action", "approver", "anti-avoidance"},
    "scope": {"goods-services", "works-concession-light-touch", "all"},
    "evidence_source": {"spend-data", "contracts-register", "council-records"},
}
TOP_LEVEL = {"source": dict, "parameters": dict, "notes": list, "rules": list, "excluded": list}

BULLETS = "•▪●◦‣⁃"
QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
FOOTER_RE = re.compile(r"^\s*\S+\.docx\s*$")


def pdf_pages(pdf):
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, check=True)
        pages = out.stdout.decode("utf-8").split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return pages
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("STOP: neither pdftotext (brew install poppler) nor pypdf (pip install pypdf) is available")
    return [p.extract_text() or "" for p in PdfReader(pdf).pages]


def strip_footers(page):
    lines = page.split("\n")
    keep, skip_number = [], False
    for line in lines:
        if FOOTER_RE.match(line):
            skip_number = True
            continue
        if skip_number:
            if not line.strip():
                continue
            skip_number = False
            if line.strip().isdigit():
                continue
        keep.append(line)
    return "\n".join(keep)


def norm(text):
    text = text.translate(QUOTE_MAP)
    text = re.sub("[" + BULLETS + "]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    rules_path, pdf = sys.argv[1], sys.argv[2]
    errors, warnings = [], []

    try:
        with open(rules_path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("FAIL: cannot read/parse %s: %s" % (rules_path, e))
        return 1

    for key, typ in TOP_LEVEL.items():
        if not isinstance(doc.get(key), typ):
            errors.append("top-level `%s` missing or not a %s" % (key, typ.__name__))
    if errors:
        print("\n".join("FAIL: " + e for e in errors))
        return 1

    params = doc["parameters"]
    for name, p in params.items():
        if not isinstance(p, dict) or "value" not in p:
            errors.append("parameter %s: must be an object with a `value` key" % name)
        elif p["value"] is not None:
            warnings.append("parameter %s has a value; confirm the auditor supplied it with a citation" % name)

    pages = [norm(strip_footers(p)) for p in pdf_pages(pdf)]
    n_pages = len(pages)
    if doc["source"].get("pages") not in (None, n_pages):
        errors.append("source.pages is %s but the PDF has %d pages" % (doc["source"].get("pages"), n_pages))

    seen = set()
    for i, r in enumerate(doc["rules"], 1):
        rid = r.get("rule_id", "#%d" % i) if isinstance(r, dict) else "#%d" % i
        if not isinstance(r, dict):
            errors.append("%s: not an object" % rid)
            continue
        for field, typ in RULE_FIELDS.items():
            if field not in r:
                errors.append("%s: missing field `%s`" % (rid, field))
            elif not isinstance(r[field], typ) or (typ is int and isinstance(r[field], bool)):
                errors.append("%s: `%s` has wrong type %s" % (rid, field, type(r[field]).__name__))
        for field, typ in OPTIONAL_RULE_FIELDS.items():
            if field in r and not isinstance(r[field], typ):
                errors.append("%s: `%s` has wrong type %s" % (rid, field, type(r[field]).__name__))
        for field in ("threshold_low", "threshold_high"):
            if isinstance(r.get(field), bool):
                errors.append("%s: `%s` must be an integer, not a boolean" % (rid, field))
        for field, allowed in ENUMS.items():
            if field in r and r[field] not in allowed:
                errors.append("%s: `%s` = %r not one of %s" % (rid, field, r[field], sorted(allowed)))

        expected = "CPR-%02d" % i
        if rid in seen:
            errors.append("%s: duplicate rule_id" % rid)
        seen.add(rid)
        if rid != expected:
            errors.append("%s: rule_id out of sequence, expected %s" % (rid, expected))

        for ref in ("threshold_low_ref", "threshold_high_ref"):
            name = r.get(ref)
            if name is not None and name not in params:
                errors.append("%s: `%s` %r not declared in parameters" % (rid, ref, name))

        q = r.get("verbatim_quote")
        if isinstance(q, str):
            nq = norm(q)
            if not nq:
                errors.append("%s: empty verbatim_quote" % rid)
                continue
            found = [n + 1 for n, text in enumerate(pages) if nq in text]
            if not found:
                errors.append("%s: verbatim_quote not found in PDF text: %r" % (rid, q[:90]))
            elif isinstance(r.get("page"), int) and r["page"] not in found:
                errors.append("%s: page is %s but quote found on page(s) %s" % (rid, r["page"], found))

    for i, x in enumerate(doc["excluded"], 1):
        if not isinstance(x, dict):
            errors.append("excluded #%d: not an object" % i)
            continue
        for field, typ in (("clause", str), ("page", int), ("reason", str)):
            if not isinstance(x.get(field), typ):
                errors.append("excluded #%d (%s): `%s` missing or wrong type" % (i, x.get("clause"), field))
        if isinstance(x.get("page"), int) and not 1 <= x["page"] <= n_pages:
            errors.append("excluded #%d (%s): page %s outside 1..%d" % (i, x.get("clause"), x["page"], n_pages))

    for w in warnings:
        print("WARN: " + w)
    for e in errors:
        print("FAIL: " + e)
    print("%d rules, %d excluded, %d parameters; %d failure(s)"
          % (len(doc["rules"]), len(doc["excluded"]), len(params), len(errors)))
    if errors:
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
