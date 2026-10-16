#!/usr/bin/env python3
"""Verify outputs/history.json against the committee PDFs.

Usage: verify_history.py <history.json> [<committee-dir>]
       (committee-dir defaults to data/committee next to this script's parent)

Checks:
  - JSON parses and has the required top-level keys and types.
  - sources_read lists every PDF in the committee dir with its sha256 and
    page count, and nothing else.
  - Every quote reference (any object with a `quote` key) names a file from
    sources_read, a pdf_page inside that file, a text_mode of "plain" or
    "layout", and a quote found on THAT page in THAT mode's text. When it is
    not, the failure says where the quote does occur, if anywhere.
  - Every object with an `id` (outside `gaps`) has a non-empty `sources` list;
    ids are unique; every discrepancy cites at least two sources.
  - Records, never scores: no likelihood/impact/score/rating keys anywhere
    outside risk_scoring_method.
  - risk_scoring_method.status is "extracted" or "not_found"; "not_found"
    needs a gap that names risk_scoring_method.
  - No e-mail address or phone number anywhere in the file.

Quote matching ignores only whitespace differences, bullet glyphs and
curly-vs-straight quote characters. Nothing else is normalised.

Exit 0 and print ALL CHECKS PASSED only when every check passes; 1 on any
failure; 2 when the inputs cannot be read.
Standard library plus the pdftotext binary (poppler).
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

TOP_LEVEL = {
    "generated_on": str,
    "generated_by": str,
    "extraction": dict,
    "sources_read": list,
    "audits_completed": list,
    "follow_ups": list,
    "advisory_reviews": list,
    "agreed_actions": list,
    "risk_themes": list,
    "risk_scoring_method": dict,
    "discrepancies": list,
    "gaps": list,
    "notes": list,
}
MODES = ("plain", "layout")
SCORING_KEYS = {"likelihood", "impact", "score", "rating", "risk_score",
                "risk_rating", "likelihood_score", "impact_score"}
BULLETS = "•▪●◦‣⁃"
QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+44\s?|0)\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\d)")


def norm(text):
    text = text.translate(QUOTE_MAP).replace("\f", " ")
    text = re.sub("[" + BULLETS + "]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def pdf_pages(pdf, mode):
    args = ["pdftotext"] + (["-layout"] if mode == "layout" else []) + [pdf, "-"]
    out = subprocess.run(args, capture_output=True, check=True)
    pages = out.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return [norm(p) for p in pages]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(node, path="$"):
    """Yield (path, dict) for every object in the document."""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    hist_path = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cdir = sys.argv[2] if len(sys.argv) == 3 else os.path.join(root, "data", "committee")
    if not shutil.which("pdftotext"):
        print("STOP: pdftotext not found (brew install poppler)")
        return 2
    pdfs = {os.path.basename(p): p for p in sorted(glob.glob(os.path.join(cdir, "*.pdf")))}
    if not pdfs:
        print(f"STOP: no PDFs in {cdir}")
        return 2
    try:
        with open(hist_path, encoding="utf-8") as f:
            raw = f.read()
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL: cannot read/parse {hist_path}: {e}")
        return 1

    errors = []
    for key, typ in TOP_LEVEL.items():
        if not isinstance(doc.get(key), typ):
            errors.append(f"top-level `{key}` missing or not a {typ.__name__}")
    if errors:
        print("\n".join("FAIL: " + e for e in errors))
        return 1

    texts = {}  # (file, mode) -> list of normalised page texts

    def pages_of(fname, mode):
        if (fname, mode) not in texts:
            texts[(fname, mode)] = pdf_pages(pdfs[fname], mode)
        return texts[(fname, mode)]

    # sources_read: exactly the committee PDFs, with hash and page count
    listed = {}
    for i, s in enumerate(doc["sources_read"]):
        if not isinstance(s, dict) or not isinstance(s.get("file"), str):
            errors.append(f"sources_read[{i}]: needs a `file`")
            continue
        listed[s["file"]] = s
    for fname in sorted(set(pdfs) - set(listed)):
        errors.append(f"sources_read: {fname} is in the committee dir but not listed")
    for fname, s in sorted(listed.items()):
        if fname not in pdfs:
            errors.append(f"sources_read: {fname} is not in the committee dir")
            continue
        if s.get("sha256") != sha256(pdfs[fname]):
            errors.append(f"sources_read: {fname} sha256 does not match the file")
        n = len(pages_of(fname, "plain"))
        if s.get("pdf_pages") != n:
            errors.append(f"sources_read: {fname} pdf_pages is {s.get('pdf_pages')} but the PDF has {n}")

    # quote references
    n_quotes = 0
    for path, obj in walk(doc):
        if "quote" not in obj:
            continue
        n_quotes += 1
        fname, page, mode, q = obj.get("file"), obj.get("pdf_page"), obj.get("text_mode"), obj.get("quote")
        if fname not in pdfs:
            errors.append(f"{path}: file {fname!r} is not a committee PDF")
            continue
        if fname not in listed:
            errors.append(f"{path}: file {fname} is not in sources_read")
        if mode not in MODES:
            errors.append(f"{path}: text_mode {mode!r} must be one of {MODES}")
            continue
        n = len(pages_of(fname, mode))
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= n:
            errors.append(f"{path}: pdf_page {page!r} outside 1..{n} for {fname}")
            continue
        if not isinstance(q, str) or not norm(q):
            errors.append(f"{path}: empty quote")
            continue
        nq = norm(q)
        if nq in pages_of(fname, mode)[page - 1]:
            continue
        where = [f"{m} p{i}" for m in MODES
                 for i, t in enumerate(pages_of(fname, m), 1) if nq in t]
        if where:
            errors.append(f"{path}: quote not on {fname} {mode} p{page}; found at {', '.join(where)}: {q[:70]!r}")
        else:
            errors.append(f"{path}: quote not found anywhere in {fname}: {q[:70]!r}")

    # ids, sources, discrepancies
    seen = {}
    for path, obj in walk(doc):
        if "id" not in obj or path.startswith("$.gaps"):
            continue
        oid = obj["id"]
        if oid in seen:
            errors.append(f"{path}: duplicate id {oid!r} (also at {seen[oid]})")
        seen[oid] = path
        src = obj.get("sources")
        if not isinstance(src, list) or not src:
            errors.append(f"{path} ({oid}): no sources")
        elif not all(isinstance(s, dict) and "quote" in s for s in src):
            errors.append(f"{path} ({oid}): every source must be a quote reference")
    for i, d in enumerate(doc["discrepancies"]):
        if not isinstance(d, dict) or len(d.get("sources") or []) < 2:
            errors.append(f"$.discrepancies[{i}]: a discrepancy needs at least two sources")
        if isinstance(d, dict) and not d.get("description"):
            errors.append(f"$.discrepancies[{i}]: missing description")
    for i, g in enumerate(doc["gaps"]):
        if not isinstance(g, dict) or not g.get("item") or not g.get("reason"):
            errors.append(f"$.gaps[{i}]: a gap needs `item` and `reason`")

    # records, never scores
    for path, obj in walk(doc):
        if path.startswith("$.risk_scoring_method"):
            continue
        bad = SCORING_KEYS & set(obj)
        if bad:
            errors.append(f"{path}: scoring key(s) {sorted(bad)} outside risk_scoring_method")

    rsm = doc["risk_scoring_method"]
    if rsm.get("status") not in ("extracted", "not_found"):
        errors.append(f"risk_scoring_method.status {rsm.get('status')!r} must be extracted or not_found")
    elif rsm["status"] == "not_found" and not any(
            "risk_scoring_method" in json.dumps(g) for g in doc["gaps"]):
        errors.append("risk_scoring_method is not_found but no gap names it")

    # personal contact details
    for m in EMAIL_RE.finditer(raw):
        errors.append(f"e-mail address in output: {m.group(0)}")
    for m in PHONE_RE.finditer(raw):
        errors.append(f"phone number in output: {m.group(0)}")

    for e in errors:
        print("FAIL: " + e)
    print(f"{len(seen)} ids, {n_quotes} quotes, {len(doc['discrepancies'])} discrepancies, "
          f"{len(doc['gaps'])} gaps; {len(errors)} failure(s)")
    if errors:
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
