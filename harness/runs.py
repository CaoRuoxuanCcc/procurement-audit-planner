"""Run state on disk: runs/<id>/run.json (status) and events.jsonl (log).

No database: a run is its folder. Files stay on the volume; run.json holds the
status and pointers, events.jsonl the append-only event log the UI streams.
"""
import json
import os
import secrets
import shutil
import threading
import time
from pathlib import Path

from .workspace import REPO, RUNS_DIR, create_workspace

# created → stage1 → stage2 → awaiting_review → stage4 → awaiting_signoff → complete
# plus failed / interrupted (resumable) at any running stage, and ready
# (between two automatic stages: next_stage says which runs next).
RUNNING = {"stage1", "stage2", "stage4", "qa"}
STAGE_AFTER_SEED = {"full": "stage1", "stage2": "stage2", "risk": "stage2"}

SAMPLE_ID = "sample"
SAMPLE_DIR = Path(__file__).parent / "sample_run"

_lock = threading.Lock()


def run_dir(run_id: str) -> Path:
    if run_id == SAMPLE_ID:
        return SAMPLE_DIR
    if not run_id.isalnum() or len(run_id) > 32:
        raise KeyError(run_id)
    return RUNS_DIR / run_id


def outputs_dir(run_id: str) -> Path:
    d = run_dir(run_id)
    if run_id == SAMPLE_ID and not (d / "workspace" / "outputs").exists():
        return REPO / "outputs"  # Part A golden run
    return d / "workspace" / "outputs"


def create(seed: str, label: str = "") -> dict:
    run_id = time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)
    d = RUNS_DIR / run_id
    d.mkdir(parents=True)
    try:
        create_workspace(d, seed)
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    now = time.time()
    run = {
        "id": run_id, "label": label[:80], "seed": seed, "status": "created",
        "next_stage": STAGE_AFTER_SEED[seed], "provider": None, "model": None,
        "created": now, "updated": now, "error": None,
        "cost_usd": 0.0, "cost_known": True, "input_tokens": 0, "output_tokens": 0,
        "stages": [], "qa": None, "signoff": None,
    }
    save(run)
    append_event(run_id, "run", "harness", {"status": "created", "seed": seed})
    return run


def load(run_id: str) -> dict:
    p = run_dir(run_id) / "run.json"
    if not p.exists():
        if run_id == SAMPLE_ID:
            return _sample_stub()
        raise KeyError(run_id)
    return json.loads(p.read_text())


def save(run: dict) -> None:
    if run["id"] == SAMPLE_ID:
        raise PermissionError("the sample run is read-only")
    run["updated"] = time.time()
    p = run_dir(run["id"]) / "run.json"
    tmp = p.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(run, indent=2))
        os.replace(tmp, p)


def update(run_id: str, **changes) -> dict:
    with _lock:
        run = json.loads((run_dir(run_id) / "run.json").read_text())
    run.update(changes)
    save(run)
    return run


def all_runs() -> list:
    out = []
    if RUNS_DIR.exists():
        for p in RUNS_DIR.glob("*/run.json"):
            try:
                out.append(json.loads(p.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
    return sorted(out, key=lambda r: r["created"], reverse=True)


def append_event(run_id: str, kind: str, agent: str, payload: dict) -> None:
    rec = {"ts": time.time(), "kind": kind, "agent": agent, **payload}
    with _lock:
        with open(run_dir(run_id) / "events.jsonl", "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def mark_interrupted() -> None:
    """On server start: any run left in a running stage was cut off."""
    for run in all_runs():
        if run["status"] in RUNNING:
            update(run["id"], status="interrupted",
                   error=f"the server restarted during {run['status']}; resume to rerun that stage")


def _sample_stub() -> dict:
    return {
        "id": SAMPLE_ID, "label": "Sample run (Part A, made with Claude Code)", "seed": "full",
        "status": "complete", "next_stage": None, "provider": "anthropic", "model": "Claude Code (Part A)",
        "created": 0, "updated": 0, "error": None, "cost_usd": 0.0, "cost_known": False,
        "input_tokens": 0, "output_tokens": 0, "stages": [], "qa": None, "signoff": None,
        "read_only": True,
        "note": ("These are the outputs of the Part A run made in Claude Code with the same CLAUDE.md, "
                 "skills and agents. Claude Code did not record an event log in this app's format, so "
                 "there is no live log here; runs started in this app record one."),
    }
