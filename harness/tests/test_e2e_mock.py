"""End-to-end run of the harness with a scripted mock model (no API key, no cost).

The mock "agents" call the same tools a real model would (Bash, Write,
SendMessage), reusing Part A's golden judgments (rules.json, history.json,
risk-ratings.json, audit-plan.json, challenges.md) where a model would write
its own. Everything else is real: the workspace copy, the committed scripts
(run_all.py and self_check.py really run), every stage check, both gates
through the HTTP API, the team mailbox with the lead's relay, and the final
QA run. Run:  .venv/bin/python -m pytest harness/tests -q
"""
import json
import os
import re
import tempfile
import time
from pathlib import Path

os.environ.setdefault("RUNS_DIR", tempfile.mkdtemp(prefix="harness-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from harness import providers  # noqa: E402
from harness.app import app  # noqa: E402
from harness.workspace import REPO  # noqa: E402

GOLD = REPO / "outputs"
_ids = iter(range(1, 10_000))


def call(name, **args):
    return providers.ToolCall(id=f"call_{next(_ids)}", name=name, arguments=json.dumps(args))


def reply(text="", calls=()):
    calls = list(calls)
    msg = {"role": "assistant", "content": text}
    if calls:
        msg["tool_calls"] = [{"id": c.id, "type": "function",
                              "function": {"name": c.name, "arguments": c.arguments}} for c in calls]
    return providers.Reply(text=text, tool_calls=calls, finish_reason="tool_calls" if calls else "stop",
                           message=msg, input_tokens=100, output_tokens=10, cost=0.001)


def bash(cmd):
    return call("Bash", command=cmd)


def first_build_ratings():
    state = json.loads((GOLD / "risk-register.state.json").read_text())
    gold = json.loads((GOLD / "risk-ratings.json").read_text())
    return json.dumps({"generated_on": gold["generated_on"], "risks": list(state["revisions"]["0"]["risks"].values()),
                       "not_rated": gold["not_rated"]}, indent=2)


def blank_signoff(text):
    head, sep, block = text.rpartition("## Auditor sign-off")
    block = re.sub(r"^\| (Auditor|Decision \(SIGNED OFF / RETURNED\)|Date|Comments) \|.*\|$",
                   lambda m: f"| {m.group(1)} | |", block, flags=re.M)
    return head + sep + block


TEAM_STATE = {}


def team_step(agent, st, inbox):
    """Each teammate does its next protocol step once its trigger has arrived."""
    if agent == "planner":
        if "built" not in st:
            st["built"] = 1
            return reply(calls=[bash(f"cp {GOLD}/audit-plan.json outputs/ && "
                                     ".venv/bin/python -I .claude/skills/audit-program/build_pack.py | tail -2")])
        if "announced" not in st:
            st["announced"] = 1
            return reply(calls=[call("SendMessage", to="challenger,qa-reviewer", message="PACK READY v1\nFirst build.")])
        if "CHALLENGER DONE" in inbox and "done" not in st:
            st["done"] = 1
            return reply(calls=[call("SendMessage", to="lead,challenger,qa-reviewer",
                                     message="PLANNER DONE v1\nChallenges: none open.")])
    elif agent == "challenger" and "PACK READY v1" in inbox:
        if "wrote" not in st:
            st["wrote"] = 1
            return reply(calls=[bash(f"cp {GOLD}/challenges.md outputs/")])
        if "done" not in st:
            st["done"] = 1
            return reply(calls=[call("SendMessage", to="planner,lead", message="CHALLENGER DONE v1\nChallenges 9.")])
    elif agent == "qa-reviewer" and "PACK READY v1" in inbox:
        if "ran" not in st:
            st["ran"] = 1
            return reply(calls=[bash(".venv/bin/python -I scripts/checks/run_checks.py --label v1 | tail -1")])
        if "PLANNER DONE" in inbox and "CHALLENGER DONE" in inbox:
            if "wrote" not in st:
                st["wrote"] = 1
                review = blank_signoff((GOLD / "review.md").read_text())
                return reply(calls=[call("Write", file_path="outputs/review.md", content=review)])
            if "done" not in st:
                st["done"] = 1
                return reply(calls=[call("SendMessage", to="lead,planner,challenger",
                                         message="QA DONE v1: READY FOR SIGN-OFF")])
    return reply(f"{agent}: waiting")


def script(agent, messages, tools):
    n = sum(1 for m in messages if m["role"] == "assistant")
    task = messages[1]["content"]
    inbox = "\n".join(m["content"] for m in messages if m["role"] == "user" and m["content"].startswith("Message from"))
    assert messages[0]["role"] == "system" and "CLAUDE.md" in messages[0]["content"]
    steps = []
    if agent == "main":
        assert "# Skill: extract-rules" in messages[0]["content"]
        steps = [[bash(f"cp {GOLD}/rules.json outputs/rules.json")],
                 [bash(".venv/bin/python -I .claude/skills/extract-rules/verify_quotes.py outputs/rules.json "
                       "data/contract-rules.pdf | tail -1")]]
    elif agent == "spend-analyst":
        steps = [[bash(".venv/bin/python -I scripts/run_all.py | tail -3")]]
    elif agent == "findings-analyst":
        steps = [[bash(f"cp {GOLD}/history.json outputs/")],
                 [bash(".venv/bin/python -I scripts/verify_history.py outputs/history.json | tail -1")]]
    elif agent == "risk-assessor" and "first-build" in task:
        steps = [[call("Write", file_path="outputs/risk-ratings.json", content=first_build_ratings())],
                 [bash(".venv/bin/python -I .claude/skills/risk-assessment/build_register.py --strict | tail -2")]]
    elif agent == "risk-assessor":
        steps = [[bash(f"cp {GOLD}/risk-ratings.json outputs/")],
                 [bash(".venv/bin/python -I .claude/skills/risk-assessment/build_register.py --strict | tail -2")]]
    elif agent in TEAM_STATE:
        return team_step(agent, TEAM_STATE[agent], inbox)
    return reply(calls=steps[n]) if n < len(steps) else reply(f"{agent} report: done.")


def wait_for(client, run_id, statuses, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in statuses and not run["active"]:
            return run
        time.sleep(0.5)
    raise AssertionError(f"timed out; run is {run['status']}")


def test_full_run_with_mock_model():
    providers.MOCK["fn"] = script
    TEAM_STATE.update({m: {} for m in ("planner", "challenger", "qa-reviewer")})
    with TestClient(app) as client:
        run = client.post("/api/runs", json={"seed": "full", "label": "mock"}).json()
        rid = run["id"]
        r = client.post(f"/api/runs/{rid}/start", json={"provider": "mock", "model": "scripted"})
        assert r.status_code == 200, r.text
        run = wait_for(client, rid, {"awaiting_review", "failed"})
        assert run["status"] == "awaiting_review", run["error"]

        risks = client.get(f"/api/runs/{rid}/risks").json()["risks"]
        assert len(risks) == 9 and all(not r["decision"] for r in risks)
        # Starting stage 4 before deciding is refused.
        assert client.post(f"/api/runs/{rid}/start", json={"provider": "mock", "model": "x"}).status_code == 409

        gold = {r["risk_id"]: r for r in [
            {"risk_id": "R-06", "decision": "AMEND", "comment": "Lower impact to 4: the loss figure is a ceiling "
             "and most repeated amounts are care and education placements, which often recur legitimately."},
            {"risk_id": "R-08", "decision": "REJECT", "comment": "Grants will be covered by a separate review."}]}
        decisions = [gold.get(r["risk_id"], {"risk_id": r["risk_id"], "decision": "APPROVE", "comment": ""})
                     for r in risks]
        bad = client.post(f"/api/runs/{rid}/decisions", json={"auditor": "Test Auditor", "decisions": [
            {"risk_id": "R-01", "decision": "REJECT", "comment": ""}]})
        assert bad.status_code == 400
        ok = client.post(f"/api/runs/{rid}/decisions", json={"auditor": "Test Auditor", "decisions": decisions})
        assert ok.status_code == 200, ok.text

        r = client.post(f"/api/runs/{rid}/start", json={"provider": "mock", "model": "scripted"})
        assert r.status_code == 200, r.text
        run = wait_for(client, rid, {"awaiting_signoff", "failed"})
        assert run["status"] == "awaiting_signoff", run["error"]
        assert run["qa"]["verdict"] == "READY FOR SIGN-OFF", run["qa"]
        assert set(run["qa"]["team_done"]) == {"planner", "challenger", "qa-reviewer"}

        mailbox = (Path(os.environ["RUNS_DIR"]) / rid / "mailbox.jsonl").read_text()
        assert '"relay": true' in mailbox  # CHALLENGER DONE relayed to the qa-reviewer

        r = client.post(f"/api/runs/{rid}/signoff", json={"auditor": "Test Auditor", "decision": "SIGNED OFF",
                                                           "comments": "Mock run."})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "complete"
        review = client.get(f"/api/runs/{rid}/file", params={"path": "review.md"}).text
        assert "| Auditor | Test Auditor |" in review

        z = client.get(f"/api/runs/{rid}/download")
        assert z.status_code == 200 and z.content[:2] == b"PK"
        events = (Path(os.environ["RUNS_DIR"]) / rid / "events.jsonl").read_text()
        assert "verify_quotes.py" in events and "run_checks.py (final QA)" in events


def test_protected_files_are_restored():
    def vandal(agent, messages, tools):
        n = sum(1 for m in messages if m["role"] == "assistant")
        if n == 0:
            return reply(calls=[bash("echo x >> data/contracts.csv"),
                                call("Write", file_path="scripts/evil.py", content="x")])
        return reply("done")

    providers.MOCK["fn"] = vandal
    with TestClient(app) as client:
        rid = client.post("/api/runs", json={"seed": "full"}).json()["id"]
        client.post(f"/api/runs/{rid}/start", json={"provider": "mock", "model": "x"})
        run = wait_for(client, rid, {"failed", "ready", "awaiting_review"})
        assert run["status"] == "failed"
        assert "data/contracts.csv" in run["error"]
        ws = Path(os.environ["RUNS_DIR"]) / rid / "workspace"
        assert (ws / "data/contracts.csv").read_bytes() == (REPO / "data/contracts.csv").read_bytes()
        assert not (ws / "scripts/evil.py").exists()
        events = (Path(os.environ["RUNS_DIR"]) / rid / "events.jsonl").read_text()
        assert "is read-only" in events  # the Write tool refused scripts/


def test_key_never_stored():
    key = "sk-ant-api03-" + "Z" * 40

    def leaky(agent, messages, tools):
        raise providers.LLMError(f"AuthenticationError: invalid x-api-key {key}")

    providers.MOCK["fn"] = leaky
    with TestClient(app) as client:
        rid = client.post("/api/runs", json={"seed": "full"}).json()["id"]
        # mock provider ignores the key, but the job must still scrub it everywhere
        cfg_key_holder = {"provider": "mock", "model": "x"}
        client.post(f"/api/runs/{rid}/start", json=cfg_key_holder, headers={"X-LLM-Key": key})
        wait_for(client, rid, {"failed"})
        run_dir = Path(os.environ["RUNS_DIR"]) / rid
        for p in run_dir.glob("*.json*"):
            assert key not in p.read_text(), p
        assert "[redacted]" in (run_dir / "run.json").read_text()
