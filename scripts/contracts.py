"""Parse the Contracts Finder notice export.

Reads: data/contracts.csv (optional), outputs/analytics-full/clean_summary.json
       (window start).
Writes: outputs/analytics-full/contract_suppliers.csv (no addresses) and
        outputs/analytics-full/contracts_summary.json, or a skip record in
        contracts_summary.json when the file is absent or unusable.
"""
import json
import os
import sys
from collections import Counter
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd  # noqa: E402

from common import CONTRACTS_CSV, CONTRACTS_FINDER_EXPORT_ROW_CAP, FULL, normalise_supplier, sha256, write_json  # noqa: E402

SUPPLIER_COL = "Supplier [Name|Address|Ref type|Ref Number|Is SME|Is VCSE]"
REQUIRED = ["Notice Identifier", "Organisation Name", "Published Date", "Title",
            "Awarded Value", "Contract start date", "Contract end date", SUPPLIER_COL]
COUNCIL_NAMES = {"west berkshire council", "west berkshire"}
DMY_COLS = ["Start Date", "End Date", "Awarded Date", "Contract start date",
            "Contract end date"]
CAVEAT = ("Notices may be missing for recent contracts: late publication, a partial "
          "current year, or publication on the Central Digital Platform / Find a Tender "
          "rather than Contracts Finder after the Procurement Act 2023 went live "
          "(24 Feb 2025). Auditor to confirm. Results that rely on notices must not be "
          "read as evidence that no contract exists.")
SUMMARY = os.path.join(FULL, "contracts_summary.json")


def skip(reason):
    write_json(SUMMARY, {"present": os.path.exists(CONTRACTS_CSV), "status": "skipped",
                         "reason": reason})
    print(f"contracts: skipped ({reason})")


def parse_col(series, fmt):
    out, bad = [], 0
    for v in series:
        v = v.strip()
        if v == "":
            out.append(pd.NaT)
            continue
        try:
            out.append(pd.Timestamp(datetime.strptime(v, fmt)))
        except ValueError:
            out.append(pd.NaT)
            bad += 1
    return out, bad


def main():
    if not os.path.exists(CONTRACTS_CSV):
        return skip("data/contracts.csv not present")
    with open(os.path.join(FULL, "clean_summary.json")) as f:
        window_start = pd.Timestamp(json.load(f)["window"]["start"])
    df = pd.read_csv(CONTRACTS_CSV, dtype=str, keep_default_na=False)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return skip(f"data/contracts.csv missing required column(s): {missing}")
    org = df["Organisation Name"].str.strip().str.lower()
    keep = org.isin(COUNCIL_NAMES)
    kept, dropped = df[keep].copy(), df[~keep]
    if kept.empty:
        return skip("data/contracts.csv has zero council rows after filtering")

    parse_fail = {}
    pub, bad = [], 0
    for v in kept["Published Date"]:
        v = v.strip()
        if v == "":
            pub.append(pd.NaT)
            continue
        try:
            pub.append(datetime.strptime(v, "%Y-%m-%dT%H:%M:%S%z"))
        except ValueError:
            pub.append(pd.NaT)
            bad += 1
    kept["published"] = pub
    parse_fail["Published Date"] = bad
    for c in DMY_COLS:
        if c in kept.columns:
            kept[c + "__p"], parse_fail[c] = parse_col(kept[c], "%d/%m/%Y")
        else:
            parse_fail[c] = "column absent"
    value_fail = 0
    vals = []
    for v in kept["Awarded Value"]:
        v = v.replace(",", "").strip()
        try:
            vals.append(float(v) if v else None)
        except ValueError:
            vals.append(None)
            value_fail += 1
    kept["awarded_value"] = vals

    rows, bad_blocks, n_blocks = [], [], 0
    for _, r in kept.iterrows():
        raw = r[SUPPLIER_COL].strip()
        if raw.startswith("["):
            raw = raw[1:]
        if raw.endswith("]"):
            raw = raw[:-1]
        blocks = [b for b in raw.split("][")] if raw else []
        n_blocks += len(blocks)
        for b in blocks:
            fields = b.split("|")
            if len(fields) != 6:
                bad_blocks.append(r["Notice Identifier"])
            name = fields[0].strip()
            ref_type = fields[2].strip() if len(fields) > 2 else ""
            ch = fields[3].strip() if len(fields) > 3 and ref_type == "COMPANIES_HOUSE" else ""
            end = r["Contract end date__p"]
            rows.append({
                "notice_id": r["Notice Identifier"], "title": r["Title"],
                "published": r["published"].isoformat() if not pd.isna(r["published"]) else "",
                "contract_start": "" if pd.isna(r["Contract start date__p"]) else r["Contract start date__p"].date().isoformat(),
                "contract_end": "" if pd.isna(end) else end.date().isoformat(),
                "awarded_value": r["awarded_value"],
                "n_suppliers_on_notice": len(blocks),
                "supplier_name": name, "supplier_norm": normalise_supplier(name),
                "ref_type": ref_type, "ch_number": ch,
                "live_in_window": bool(pd.isna(end) or end >= window_start)})
    cs = pd.DataFrame(rows)
    cs.to_csv(os.path.join(FULL, "contract_suppliers.csv"), index=False)

    live_notice = kept["Contract end date__p"].isna() | (kept["Contract end date__p"] >= window_start)
    years = Counter(p.year for p in kept["published"] if not pd.isna(p))
    per_year = {str(y): years[y] for y in sorted(years)}
    today = pd.Timestamp(date.today())
    far = today + pd.DateOffset(years=20)
    awarded_future = int((kept["Awarded Date__p"] > today).sum()) if "Awarded Date__p" in kept else None
    end_far = int((kept["Contract end date__p"] > far).sum())
    warnings = []
    cur, prev = today.year, today.year - 1
    if years.get(prev, 0) and years.get(cur, 0) < 0.25 * years[prev]:
        warnings.append(f"coverage_warning: {years.get(cur, 0)} council notices published in "
                        f"{cur} against {years[prev]} in {prev} (under 25% of the previous "
                        f"full year)")
    if len(df) >= CONTRACTS_FINDER_EXPORT_ROW_CAP:
        warnings.append(f"coverage_warning: export has {len(df)} rows, at or above the "
                        f"Contracts Finder export cap")
    summary = {
        "present": True, "status": "ran", "sha256": sha256(CONTRACTS_CSV),
        "rows_in_file": len(df), "kept": len(kept), "dropped": len(dropped),
        "organisation_names_kept": dict(Counter(kept["Organisation Name"])),
        "organisation_names_dropped": dict(Counter(dropped["Organisation Name"])),
        "notice_types": dict(Counter(kept["Notice Type"])) if "Notice Type" in kept else None,
        "statuses": dict(Counter(kept["Status"])) if "Status" in kept else None,
        "per_publication_year": per_year,
        "live_in_window": int(live_notice.sum()),
        "window_start": window_start.date().isoformat(),
        "supplier_blocks": n_blocks,
        "notices_with_multiple_suppliers": int((kept[SUPPLIER_COL].str.count(r"\]\[") > 0).sum()),
        "blocks_not_6_fields_notice_ids": sorted(set(bad_blocks)),
        "distinct_supplier_norm": int(cs["supplier_norm"].nunique()),
        "distinct_supplier_norm_live": int(cs.loc[cs["live_in_window"], "supplier_norm"].nunique()),
        "companies_house_join": "not available: spend data has no Companies House number",
        "data_quality": {"awarded_date_after_today": awarded_future,
                         "contract_end_more_than_20_years_ahead": end_far,
                         "date_parse_failures": parse_fail,
                         "awarded_value_parse_failures": value_fail,
                         "awarded_value_zero": int(sum(1 for v in vals if v == 0)),
                         "note": "Counted and recorded; not corrected."},
        "warnings": warnings,
        "caveats": [CAVEAT],
    }
    write_json(SUMMARY, summary)
    print(f"contracts: rows={len(df)} kept={len(kept)} dropped={len(dropped)} "
          f"live={summary['live_in_window']} per_year={per_year}")
    print(f"  blocks={n_blocks} bad_blocks={len(bad_blocks)} multi={summary['notices_with_multiple_suppliers']} "
          f"dq={summary['data_quality']} warnings={len(warnings)}")


if __name__ == "__main__":
    main()
