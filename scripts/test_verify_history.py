#!/usr/bin/env python3
"""Test scripts/verify_history.py against its two fixtures.

  fixtures/history-good.json  must pass (exit 0, ALL CHECKS PASSED).
  fixtures/history-bad.json   must fail (exit 1) with exactly one FAIL line per
                              expected pattern below, and no other FAIL lines.
                              Its two `_control` items must not fail.

Run: .venv/bin/python -I scripts/test_verify_history.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, "verify_history.py")
GOOD = os.path.join(HERE, "fixtures", "history-good.json")
BAD = os.path.join(HERE, "fixtures", "history-bad.json")

EXPECTED_BAD = {
    "P1 altered quote": r"audits_completed\[0\]\.sources\[0\]: quote not found anywhere",
    "P2 wrong page": r"likelihood_scale\[0\]\.sources\[0\]: quote not on \S+ layout p14; found at layout p15",
    "P3 wrong mode": r"matrix\[0\]\.sources\[0\]: quote not on \S+ plain p18; found at layout p18",
    "P4 page out of range": r"follow_ups\[0\]\.sources\[0\]: pdf_page 3 outside 1\.\.2",
    "P5 quote from non-committee file": r"advisory_reviews\[0\]\.sources\[0\]: file 'strategic-risk-register\.pdf' is not a committee PDF",
    "P6 no sources": r"audits_completed\[2\] \(AUD-03\): no sources",
    "P7 duplicate id": r"audits_completed\[3\]: duplicate id 'AUD-01'",
    "P8 single-source discrepancy": r"discrepancies\[0\]: a discrepancy needs at least two sources",
    "P9 scoring key": r"audits_completed\[1\]: scoring key\(s\) \['likelihood'\]",
    "P10 e-mail": r"e-mail address in output",
    "P11 sha256": r"audit-completed-work-2025-26-q3\.pdf sha256 does not match",
    "P12 page count": r"risk-management-strategy-2024-27\.pdf pdf_pages is 34",
    "P13a file unlisted": r"internal-audit-plan-2025-28\.pdf is in the committee dir but not listed",
    "P13b quoted file unlisted": r"plan_reference\[0\]\.sources\[0\]: file internal-audit-plan-2025-28\.pdf is not in sources_read",
    "P14 listed file absent": r"strategic-risk-register\.pdf is not in the committee dir",
    "P15 bad text_mode": r"risk_themes\[0\]\.sources\[0\]: text_mode 'ocr'",
    "P16 gap without reason": r"gaps\[1\]: a gap needs",
    "P17 phone": r"phone number in output",
}


def run(path):
    r = subprocess.run([sys.executable, "-I", VERIFY, path], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    failures = []

    code, out = run(GOOD)
    if code != 0 or "ALL CHECKS PASSED" not in out:
        failures.append(f"good fixture should pass (exit {code}):\n{out}")

    code, out = run(BAD)
    if code != 1:
        failures.append(f"bad fixture should exit 1, got {code}")
    fail_lines = [l for l in out.splitlines() if l.startswith("FAIL: ")]
    matched = set()
    for name, pat in EXPECTED_BAD.items():
        hits = [l for l in fail_lines if re.search(pat, l)]
        if len(hits) != 1:
            failures.append(f"{name}: expected exactly 1 FAIL line, got {len(hits)}")
        matched.update(hits)
    for l in fail_lines:
        if l not in matched:
            failures.append(f"unexpected FAIL line (a control failed, or a new false positive): {l}")

    for f in failures:
        print("TEST FAIL: " + f)
    if failures:
        return 1
    print(f"TESTS PASSED: good fixture passes; bad fixture fails with exactly the "
          f"{len(EXPECTED_BAD)} expected FAIL lines (17 plants) and no others")
    return 0


if __name__ == "__main__":
    sys.exit(main())
