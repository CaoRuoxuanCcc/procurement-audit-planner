# Deployment handoff: Procurement Audit Planner (web harness)

This document explains how to deploy the Part B web harness: one container
with the FastAPI app, the frontend and the Part A project baked in. Users bring
their own model key in the browser, so the server holds **no LLM secrets**.

## 1. What you are deploying

- **Image:** `Dockerfile` at the repo root. It is based on python:3.13-slim
  with poppler-utils and perl, runs as non-root uid 10001, and listens on
  `$PORT` (default 8000).
- **Process:** a single `uvicorn harness.app:app` process. Stages run as
  asyncio tasks inside it.
- **State:** files only, under `$RUNS_DIR`, one folder per run (`run.json`,
  `events.jsonl`, `mailbox.jsonl`, `workspace/`, `attempts/`). There is no
  database.

### Platform requirements

- **A long-running container, not serverless.** A stage can run for up to 90
  minutes and streams progress over Server-Sent Events. This rules out Vercel
  functions; `vercel.json` there serves only the read-only Part A pack viewer
  (`scripts/serve.py`).
- **Exactly one instance.** Running stages are tracked in memory and state is
  on local disk, so do not scale out or autoscale above 1. A restart marks any
  running stage as *interrupted*; the user resumes it from the UI.
- **A persistent volume mounted at `/data/runs`.** Without it, every run,
  decision and sign-off is lost on redeploy.
- **Storage:** about 15–40 MB per run. Start with 5 GB or more.
- **Memory:** at least 1 GB RAM, 2 GB recommended. The spend scripts load
  three workbooks with pandas.
- **Outbound HTTPS** to api.anthropic.com, api.openai.com and
  generativelanguage.googleapis.com.
- **No response buffering** on the proxy for `/api/runs/*/events` (SSE), and
  an idle timeout of at least 120 s.

## 2. Environment variables

None are required. Set these only to change the defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8000` | Listen port (most platforms inject it) |
| `RUNS_DIR` | `/data/runs` in the image | Where run records live. **Must be on the persistent volume** |
| `MAX_RUNS` | `100` | Total runs the server will create (HTTP 429 after) |
| `MAX_ACTIVE_RUNS` | `2` | Stages running at the same time |
| `STAGE_TIMEOUT_MIN` | `90` | Wall-clock limit per stage |
| `STAGE_MAX_COST_USD` | `0` (no cap) | Stops a stage once its metered model cost passes this |

Do **not** set provider keys (`ANTHROPIC_API_KEY` etc.) on the server. They
are not used, and the agents' shell tool runs with a clean environment anyway.

## 3. Build and run

Local Docker smoke test:

```bash
docker build -t audit-planner .
docker volume create audit-runs
docker run --rm -p 8000:8000 -v audit-runs:/data/runs audit-planner
curl -s localhost:8000/healthz          # {"ok":true}
```

On a container platform (Render, Railway, Fly.io, Cloud Run with min=max=1
instance, etc.):

1. **Source:** this repository; build from the `Dockerfile`. Leave the start
   command empty, because the image's `CMD` already runs uvicorn on `$PORT`.
2. **Disk:** mount a persistent volume at `/data/runs`.
3. **Health check path:** `/healthz`.
4. **Instances:** 1. Turn off autoscaling and zero-downtime overlap if the
   platform would run two containers on the same disk.

Without Docker, for a VM:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r harness/requirements.txt
sudo apt-get install -y poppler-utils
RUNS_DIR=/srv/audit-runs .venv/bin/python -m uvicorn harness.app:app --host 0.0.0.0 --port 8000 --proxy-headers
```

## 4. Access control (decide before sharing the URL)

The app has **no login**. Anyone with the URL can see every run, record risk
decisions and sign off a pack. Model calls are billed to the key each visitor
pastes, but server CPU and disk are yours. For anything beyond a demo, put the
app behind one of these:

- the platform's access protection (password or SSO),
- a reverse proxy with basic auth,
- a private network or VPN.

Serve the app over HTTPS only, because the key travels in a request header
when a stage starts.

## 5. Live testing after deploy

Free checks first:

1. `GET /healthz` returns `{"ok":true}`.
2. Open the URL. The Overview loads and the sample Part A pack opens under
   **Reports**.
3. Click **No model connected**, paste a key and click **Test key**. This
   lists the provider's models and uses no tokens.

Then one paid run, cheapest first:

4. **New audit → Reuse rules, analytics and history · start at risk
   rating**. The risk-assessor runs; expect a few minutes and roughly $0.30–1
   on Claude Sonnet.
5. In **Risk review**, decide every risk and submit. Audit planning runs: the
   risk-assessor revision, then the three-agent team. This is the long, costly
   stage: about 30–60 minutes and roughly $3–5 on Claude Sonnet.
6. In **QA & sign-off**, check the verdict.
   - **READY FOR SIGN-OFF:** sign off.
   - **BLOCKED:** read the reason. Use **Re-run QA only** if the fault was in
     QA rather than the pack.
7. Download the pack (.zip) from the run page.
8. **Restart test:** redeploy, then confirm the run, its decisions and its
   sign-off are still there. This proves the volume is mounted.

A full run (the **Full pipeline** start point) re-extracts the rules and re-runs the spend
analysis. It costs about $7–8 on Claude Sonnet; only do it once the cheaper
path works.

## 6. Operations

- **Logs:** uvicorn stdout. Keys are redacted by a log filter. Each run's own
  log is `events.jsonl`, also visible in the UI under **Log**.
- **Backups:** snapshot the `/data/runs` volume. Each run folder is
  self-contained.
- **Cleanup:** delete old run folders from the volume. There is no delete
  endpoint, and runs count towards `MAX_RUNS`.
- **Model list:** edit `harness/config/models.json`. Any other model id can
  also be typed in the UI.
- **Tests before each deploy** need no key and no cost:
  `.venv/bin/python -m pytest -q harness/tests`.

## 7. Data note

All inputs in `data/` are public council publications: Contract Procedure
Rules, Expenditure over £500, a Contracts Finder export and Governance
Committee papers. Outputs name suppliers and describe **risk indicators to
investigate**, not findings of wrongdoing. Keep that framing in any
demonstration.
