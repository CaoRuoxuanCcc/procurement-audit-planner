"""The two human gates, done in the browser instead of by editing files.

Gate 1 reads the decision table the builder wrote (outputs/auditor-comments.md)
and writes the auditor's Decision and Comment cells back into it, leaving
every other cell and line as the builder wrote it. Gate 2 fills the sign-off
table at the end of outputs/review.md.
"""
import re
import time
from pathlib import Path

DECISIONS = ("APPROVE", "AMEND", "REJECT")
ROW = re.compile(r"^\|\s*(R-\d{2})\s*\|")


def split_row(line: str) -> list:
    """Cells of a markdown table row; `\\|` is a pipe inside a cell."""
    inner = line.strip()[1:-1] if line.strip().endswith("|") else line.strip()[1:]
    cells, cur, i = [], "", 0
    while i < len(inner):
        if inner[i] == "\\" and i + 1 < len(inner) and inner[i + 1] == "|":
            cur += "\\|"
            i += 2
            continue
        if inner[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += inner[i]
        i += 1
    cells.append(cur.strip())
    return cells


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def read_risks(outputs: Path) -> list:
    path = outputs / "auditor-comments.md"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if ROW.match(line):
            c = split_row(line)
            if len(c) >= 6:
                out.append({"risk_id": c[0], "title": c[1].replace("\\|", "|"), "rating": c[2],
                            "decision": c[3], "comment": c[4].replace("\\|", "|"), "status": c[5]})
    return out


def write_decisions(outputs: Path, auditor: str, decisions: dict) -> None:
    """decisions: {risk_id: (decision, comment)}. Every risk row must be decided."""
    auditor = " ".join(auditor.split())
    if not auditor:
        raise ValueError("enter the auditor's name")
    path = outputs / "auditor-comments.md"
    lines = path.read_text().split("\n")
    ids = [ROW.match(line).group(1) for line in lines if ROW.match(line)]
    missing = [r for r in ids if r not in decisions]
    if missing:
        raise ValueError(f"decide every risk; missing: {', '.join(missing)}")
    date = time.strftime("%Y-%m-%d")
    for i, line in enumerate(lines):
        m = ROW.match(line)
        if not m:
            continue
        decision, comment = decisions[m.group(1)]
        decision = decision.strip().upper()
        if decision not in DECISIONS:
            raise ValueError(f"{m.group(1)}: decision must be one of {', '.join(DECISIONS)}")
        comment = comment.strip()
        if decision in ("AMEND", "REJECT") and not comment:
            raise ValueError(f"{m.group(1)}: {decision} needs a comment saying what to change or why")
        c = split_row(line)
        c[3] = decision
        c[4] = _cell(f"{auditor}, {date}: {comment}" if comment else f"{auditor}, {date}.")
        lines[i] = "| " + " | ".join(c) + " |"
    path.write_text("\n".join(lines))


SIGNOFF_ROWS = ("Auditor", "Decision (SIGNED OFF / RETURNED)", "Date", "Comments")


def write_signoff(outputs: Path, auditor: str, decision: str, comments: str, verdict: str) -> dict:
    auditor = " ".join(auditor.split())
    decision = decision.strip().upper()
    if not auditor:
        raise ValueError("enter the auditor's name")
    if decision not in ("SIGNED OFF", "RETURNED"):
        raise ValueError("decision must be SIGNED OFF or RETURNED")
    if decision == "SIGNED OFF" and verdict != "READY FOR SIGN-OFF":
        raise ValueError("the QA verdict is BLOCKED: the pack can only be returned to the team")
    path = outputs / "review.md"
    if not path.exists():
        raise ValueError("outputs/review.md is missing; the pack cannot be signed off")
    text = path.read_text()
    head, sep, block = text.rpartition("## Auditor sign-off")
    if not sep:
        raise ValueError("review.md has no '## Auditor sign-off' section")
    values = {"Auditor": auditor, "Decision (SIGNED OFF / RETURNED)": decision,
              "Date": time.strftime("%Y-%m-%d"), "Comments": comments.strip() or "None."}
    lines = block.split("\n")
    found = set()
    for i, line in enumerate(lines):
        if line.startswith("|"):
            c = split_row(line)
            if c and c[0] in values:
                lines[i] = f"| {c[0]} | {_cell(values[c[0]])} |"
                found.add(c[0])
    if found != set(SIGNOFF_ROWS):
        raise ValueError(f"review.md sign-off table is missing rows: {sorted(set(SIGNOFF_ROWS) - found)}")
    path.write_text(head + sep + "\n".join(lines))
    return values
