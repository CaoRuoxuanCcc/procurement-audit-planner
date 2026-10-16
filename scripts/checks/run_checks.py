#!/usr/bin/env python3
"""Run the four QA checks and print one results table and a verdict.

Checks: check_quotes, check_numbers, check_trace, check_samples (each in this
folder; each prints its own FAIL lines and a RESULT line). The verdict is
READY FOR SIGN-OFF only when all four PASS; any FAIL or STOP gives BLOCKED.

Run: .venv/bin/python -I scripts/checks/run_checks.py [--out-dir D] [--data-dir D] [--label vN]
Exit: 0 READY FOR SIGN-OFF, 1 BLOCKED.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHECKS = ("check_quotes", "check_numbers", "check_trace", "check_samples")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "outputs"))
    ap.add_argument("--data-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--label", default="", help="pack version shown in the header, e.g. v2")
    a = ap.parse_args()
    results = []
    for c in CHECKS:
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, f"{c}.py"),
                            "--out-dir", a.out_dir, "--data-dir", a.data_dir], capture_output=True, text=True)
        line = next((ln for ln in reversed(r.stdout.splitlines()) if ln.startswith("RESULT ")), None)
        if line is None:
            res = {"check": c, "status": "STOP", "checked": 0,
                   "failures": [f"no RESULT line (exit {r.returncode}): {(r.stdout + r.stderr).strip()[-300:]}"],
                   "note": ""}
        else:
            res = json.loads(line[7:])
        results.append(res)
    verdict = "READY FOR SIGN-OFF" if all(x["status"] == "PASS" for x in results) else "BLOCKED"
    print(f"QA checks{' on pack ' + a.label if a.label else ''}, run {datetime.datetime.now().isoformat(timespec='seconds')}")
    print()
    print("| Check | Result | Items checked | Failures | Note |")
    print("| --- | --- | --- | --- | --- |")
    for x in results:
        print(f"| {x['check']} | {x['status']} | {x['checked']} | {len(x['failures'])} | "
              f"{str(x.get('note', '')).replace('|', '/')} |")
    for x in results:
        if x["failures"]:
            print()
            print(f"{x['check']} failures:")
            for f in x["failures"]:
                print(f"- {f}")
    print()
    print(f"VERDICT: {verdict}")
    return 0 if verdict == "READY FOR SIGN-OFF" else 1


if __name__ == "__main__":
    sys.exit(main())
