"""FastAPI app: REST + server-sent events + the static frontend.

Run locally:  .venv/bin/python -m uvicorn harness.app:app --port 8000
"""
import asyncio
import io
import json
import os
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gates, jobs, providers, runs
from .workspace import SEEDS

STATIC = Path(__file__).parent / "static"
MAX_RUNS = int(os.environ.get("MAX_RUNS", "100"))
MAX_FILE = 2_000_000
STARTABLE = {"created", "ready", "failed", "interrupted", "awaiting_review"}


@asynccontextmanager
async def lifespan(app):
    providers.install_log_redaction()
    runs.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs.mark_interrupted()
    yield


app = FastAPI(title="Procurement Audit Planner", lifespan=lifespan, docs_url=None, redoc_url=None)


def _run(run_id):
    try:
        return runs.load(run_id)
    except KeyError:
        raise HTTPException(404, "no such run") from None


def _writable(run_id):
    if run_id == runs.SAMPLE_ID:
        raise HTTPException(403, "the sample run is read-only; start a new run")
    return _run(run_id)


def _public(run):
    r = dict(run)
    r["active"] = run["id"] in jobs.ACTIVE
    return r


# ---- config and keys ---------------------------------------------------------

@app.get("/api/config")
def config():
    return {"providers": providers.CONFIG["providers"], "seeds": list(SEEDS),
            "stage_timeout_min": jobs.STAGE_TIMEOUT // 60, "max_cost_usd": jobs.STAGE_MAX_COST}


class KeyTest(BaseModel):
    provider: str
    model: str = ""


@app.post("/api/keys/test")
async def test_key(body: KeyTest, x_llm_key: str = Header(default="")):
    if body.provider not in providers.CONFIG["providers"]:
        raise HTTPException(400, "unknown provider")
    if not x_llm_key:
        raise HTTPException(400, "enter an API key")
    try:
        ids = await providers.list_models(body.provider, x_llm_key.strip())
    except providers.LLMError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)
    except Exception as e:  # noqa: BLE001 - network trouble reaching the provider
        return JSONResponse({"ok": False, "error": f"could not reach the provider: {providers.redact(e)}"})
    return {"ok": True, "model_found": (body.model in ids) if body.model else None, "models": ids[:500]}


# ---- runs --------------------------------------------------------------------

class NewRun(BaseModel):
    seed: str = "full"
    label: str = ""


@app.get("/api/runs")
def list_runs():
    return {"runs": [_public(r) for r in runs.all_runs()], "sample": runs.load(runs.SAMPLE_ID)}


@app.post("/api/runs")
def create_run(body: NewRun):
    if body.seed not in SEEDS:
        raise HTTPException(400, "unknown start point")
    if len(runs.all_runs()) >= MAX_RUNS:
        raise HTTPException(429, "this server has reached its run limit")
    return _public(runs.create(body.seed, body.label))


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return _public(_run(run_id))


class Start(BaseModel):
    provider: str
    model: str


@app.post("/api/runs/{run_id}/start")
async def start_run(run_id: str, body: Start, x_llm_key: str = Header(default="")):
    run = _writable(run_id)
    if run["status"] not in STARTABLE:
        raise HTTPException(409, f"the run is {run['status']}; nothing to start")
    stage = run["next_stage"]
    if run["status"] == "awaiting_review":
        risks = gates.read_risks(runs.outputs_dir(run_id))
        undecided = [r["risk_id"] for r in risks if not r["decision"]]
        if not risks or undecided:
            raise HTTPException(409, "record a decision for every risk first: " + ", ".join(undecided))
        stage = "stage4"
    if not stage:
        raise HTTPException(409, "no stage to run")
    try:
        cfg = providers.LLMConfig(body.provider, body.model.strip(), x_llm_key.strip())
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        jobs.start(run_id, cfg, stage)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None
    return {"started": stage}


@app.post("/api/runs/{run_id}/qa-rerun")
async def qa_rerun(run_id: str, body: Start, x_llm_key: str = Header(default="")):
    """Rerun only the qa-reviewer on the final pack, when sign-off is BLOCKED."""
    run = _writable(run_id)
    retry = run["status"] in ("failed", "interrupted") and run["next_stage"] == "qa"
    if not retry and (run["status"] != "awaiting_signoff" or run.get("signoff")):
        raise HTTPException(409, f"the run is {run['status']}; a QA-only rerun needs a run awaiting sign-off")
    if not retry and (run.get("qa") or {}).get("verdict") == "READY FOR SIGN-OFF":
        raise HTTPException(409, "the QA verdict is already READY FOR SIGN-OFF")
    try:
        cfg = providers.LLMConfig(body.provider, body.model.strip(), x_llm_key.strip())
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        jobs.start(run_id, cfg, "qa", chain=False)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None
    return {"started": "qa"}


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str):
    _writable(run_id)
    return {"stopped": jobs.stop(run_id)}


@app.get("/api/runs/{run_id}/log")
def log(run_id: str, after: int = 0):
    """The event log as JSON, for runs with no stage running."""
    _run(run_id)
    path = runs.run_dir(run_id) / "events.jsonl"
    lines = path.read_text().splitlines()[after:] if path.exists() else []
    return {"events": [json.loads(x) for x in lines]}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request, after: int = 0, last_event_id: str = Header(default="")):
    _run(run_id)
    if last_event_id.isdigit():  # the browser reconnecting: resume after the last event it saw
        after = max(after, int(last_event_id))
    path = runs.run_dir(run_id) / "events.jsonl"

    async def stream():
        sent, last_run, idle = after, None, 0
        while not await request.is_disconnected():
            lines = path.read_text().splitlines() if path.exists() else []
            for line in lines[sent:]:
                sent += 1
                yield f"id: {sent}\nevent: log\ndata: {line}\n\n"
            try:
                run = json.dumps(_public(runs.load(run_id)))
            except KeyError:
                break
            if run != last_run:
                last_run = run
                yield f"event: run\ndata: {run}\n\n"
            idle += 1
            if idle % 20 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.75)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- files -------------------------------------------------------------------

def _outputs(run_id):
    _run(run_id)
    return runs.outputs_dir(run_id)


@app.get("/api/runs/{run_id}/files")
def files(run_id: str):
    root = _outputs(run_id)
    out = []
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file() and not p.name.startswith(".") and "__pycache__" not in p.parts:
                out.append({"path": str(p.relative_to(root)), "size": p.stat().st_size, "mtime": p.stat().st_mtime})
    return {"files": out}


@app.get("/api/runs/{run_id}/file")
def file(run_id: str, path: str):
    root = _outputs(run_id).resolve()
    p = (root / path).resolve()
    if root not in p.parents or not p.is_file():
        raise HTTPException(404, "no such file")
    data = p.read_bytes()
    truncated = len(data) > MAX_FILE
    text = data[:MAX_FILE].decode("utf-8", "replace")
    if truncated:
        text += f"\n\n[truncated: showing {MAX_FILE:,} of {len(data):,} bytes; download the pack for the full file]"
    return Response(text, media_type="text/plain; charset=utf-8")


@app.get("/api/runs/{run_id}/download")
def download(run_id: str):
    root = _outputs(run_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, f"outputs/{p.relative_to(root)}")
        mailbox = runs.run_dir(run_id) / "mailbox.jsonl"
        if mailbox.exists():
            z.write(mailbox, "team-mailbox.jsonl")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="audit-pack-{run_id}.zip"'})


# ---- gates -------------------------------------------------------------------

@app.get("/api/runs/{run_id}/risks")
def risks(run_id: str):
    return {"risks": gates.read_risks(_outputs(run_id))}


class Decision(BaseModel):
    risk_id: str
    decision: str
    comment: str = ""


class Decisions(BaseModel):
    auditor: str
    decisions: list[Decision]


@app.post("/api/runs/{run_id}/decisions")
def decisions(run_id: str, body: Decisions):
    run = _writable(run_id)
    if run["status"] != "awaiting_review" or run["id"] in jobs.ACTIVE:
        raise HTTPException(409, "decisions are recorded at the risk review gate only")
    try:
        gates.write_decisions(runs.outputs_dir(run_id), body.auditor,
                              {d.risk_id: (d.decision, d.comment) for d in body.decisions})
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    runs.append_event(run_id, "gate", "auditor", {"gate": "risk review", "decisions": {
        d.risk_id: d.decision.upper() for d in body.decisions}})
    return {"risks": gates.read_risks(runs.outputs_dir(run_id))}


class Signoff(BaseModel):
    auditor: str
    decision: str
    comments: str = ""


@app.post("/api/runs/{run_id}/signoff")
def signoff(run_id: str, body: Signoff):
    run = _writable(run_id)
    if run["status"] != "awaiting_signoff":
        raise HTTPException(409, "the pack is not awaiting sign-off")
    verdict = (run.get("qa") or {}).get("verdict", "BLOCKED")
    try:
        values = gates.write_signoff(runs.outputs_dir(run_id), body.auditor, body.decision, body.comments, verdict)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    run = runs.update(run_id, status="complete", signoff=values)
    runs.append_event(run_id, "gate", "auditor", {"gate": "sign-off", **values})
    return _public(run)


# ---- frontend ----------------------------------------------------------------

@app.get("/healthz")
def healthz():
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    return FileResponse(STATIC / "index.html")
