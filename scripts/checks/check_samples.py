#!/usr/bin/env python3
"""QA check: sampled transactions exist in the source data.

Every transaction in outputs/samples/*.csv, and every row id written in
audit-program.md, must:
- exist in outputs/analytics-full/spend_clean.csv, with the same supplier and
  amount as the sample file says (for sample rows);
- exist at its sheet row in the council's workbook (data/spend/<file>, sheet
  "Data to publish", the Excel row in the row id), with the same supplier name
  and net amount as spend_clean.csv.
Every `samples/T-*.csv` that audit-program.md names must exist, and every
sample file must be named there.

Run: .venv/bin/python -I scripts/checks/check_samples.py [--out-dir D] [--data-dir D]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_common import ROW_ID_RE, SHEET, Stop, args, cents, load_workbooks, read_csv, read_text, run  # noqa: E402


def main():
    a = args(__doc__.split("\n")[0])

    def body():
        spend = {r["row_id"]: r for r in read_csv(os.path.join(a.out_dir, "analytics-full", "spend_clean.csv"))}
        prog = read_text(os.path.join(a.out_dir, "audit-program.md"))
        files = sorted(glob.glob(os.path.join(a.out_dir, "samples", "T-*.csv")))
        named = set(re.findall(r"samples/(T-[\w.]+?)\.csv", prog))
        have = {os.path.basename(p)[:-4] for p in files}
        failures, checked = [], 0
        for t in sorted(named - have):
            failures.append(f"audit-program.md names samples/{t}.csv, which does not exist")
        for t in sorted(have - named):
            failures.append(f"samples/{t}.csv is not named in audit-program.md")
        wb = load_workbooks(a.data_dir)

        def in_source(where, rid, supplier=None, amount=None):
            s = spend.get(rid)
            if s is None:
                failures.append(f"{where}: {rid} is not in spend_clean.csv")
                return
            if supplier is not None and supplier != s["supplier"]:
                failures.append(f"{where}: {rid} supplier {supplier!r} ≠ spend_clean.csv {s['supplier']!r}")
            if amount is not None and cents(amount) != cents(s["amount"]):
                failures.append(f"{where}: {rid} amount {amount} ≠ spend_clean.csv {s['amount']}")
            fn, sheet, r = rid.split("|")
            if sheet != SHEET or fn not in wb:
                failures.append(f"{where}: {rid} names a workbook or sheet not in data/spend")
                return
            raw = wb[fn].get(int(r[1:]))
            if raw is None:
                failures.append(f"{where}: {rid}: sheet row {r[1:]} of {fn} is empty or missing")
                return
            sup, amt = raw
            if sup != s["supplier"]:
                failures.append(f"{where}: {rid} workbook supplier {sup!r} ≠ spend_clean.csv {s['supplier']!r}")
            if isinstance(amt, bool) or not isinstance(amt, (int, float)) or cents(amt) != cents(s["amount"]):
                failures.append(f"{where}: {rid} workbook amount {amt!r} ≠ spend_clean.csv {s['amount']}")

        n_rows = 0
        for p in files:
            name = os.path.basename(p)
            rows = read_csv(p)
            if not rows:
                failures.append(f"samples/{name} has no transactions")
            for i, row in enumerate(rows, 2):
                if "row_id" not in row:
                    raise Stop(f"samples/{name} has no row_id column")
                checked += 1
                n_rows += 1
                in_source(f"samples/{name}:{i}", row["row_id"], row.get("supplier"), row.get("amount"))
        ids = ROW_ID_RE.findall(prog)
        for rid in ids:
            checked += 1
            in_source("audit-program.md", rid)
        return checked, failures, (f"{n_rows} sampled transaction(s) in {len(files)} file(s); "
                                   f"{len(ids)} row id(s) in audit-program.md")

    return run("check_samples", body)


if __name__ == "__main__":
    sys.exit(main())
