"""Stage runner and state machine.

Stage 1  extract-rules skill (main session)       → verify_quotes.py
Stage 2  spend-analyst ‖ findings-analyst          → self_check.py, verify_history.py
         then risk-assessor (first build)          → build_register.py --strict
Gate 1   awaiting_review: the auditor decides each risk in the UI
Stage 4  risk-assessor (revision)                  → build_register.py --strict, build_pack.py --gate
         then the agent team                       → scripts/checks/run_checks.py
Gate 2   awaiting_signoff: the auditor signs off review.md in the UI

The model judges; the committed Part A scripts check every stage. Stages read
and write files only, so a failed or interrupted stage is resumed by running
it again. The API key is held by the job for one stage and then dropped.
"""
import asyncio
import json
import os
import sys
import time

from . import loaders, runs
from .agent_loop import Limits, Meter, StageError, run_agent, run_parallel
from .providers import LLMConfig, LLMError, redact
from .team import MEMBERS, Team, spawn_message
from .workspace import diff_hashes, protected_hashes, restore_protected

STAGE_TIMEOUT = int(os.environ.get("STAGE_TIMEOUT_MIN", "90")) * 60
STAGE_MAX_COST = float(os.environ.get("STAGE_MAX_COST_USD", "0") or 0)
MAX_ACTIVE = int(os.environ.get("MAX_ACTIVE_RUNS", "2"))
TURNS = {"main": 60, "spend-analyst": 50, "findings-analyst": 90, "risk-assessor": 80,
         "planner": 150, "challenger": 120, "qa-reviewer": 100}

ACTIVE: dict = {}  # run_id -> asyncio.Task

TASKS = {
    "main": (
        "/extract-rules\n\nRun the extract-rules skill now: turn data/contract-rules.pdf into "
        "outputs/rules.json and verify it. outputs/rules.json does not exist yet. Follow every step of "
        "the skill, including Step 8 (verify until ALL CHECKS PASSED) and Step 9 (report)."),
    "spend-analyst": (
        "Run your procedure: analyse the spend workbooks against outputs/rules.json and write "
        "outputs/analytics.json and outputs/analytics-full/.\n\nHarness note: the scripts your definition "
        "describes (common, clean, contracts, tests, self_check, run_all) were written by you in an earlier "
        "run, reviewed, and are committed in scripts/, which is read-only here. Do not rewrite them: check "
        "the inputs, run `.venv/bin/python -I scripts/run_all.py`, inspect the printed summaries and "
        "analytics.json, and report. If a script fails or the self-check fails, stop and report the exact "
        "message."),
    "findings-analyst": (
        "Run your procedure: read the committee papers in data/committee/ and write outputs/history.json, "
        "then run the verifier until it prints ALL CHECKS PASSED, and report."),
    "risk-assessor-first": (
        "Build the first risk register (first-build mode): outputs/auditor-comments.md does not exist yet. "
        "Follow your procedure and the risk-assessment skill, and report."),
    "risk-assessor-revision": (
        "The auditor has recorded a decision for every risk in outputs/auditor-comments.md. Build the "
        "revision that applies them (revision mode, skill Step 6), following your procedure, and report. "
        "If an AMEND comment is unclear, stop and report the question word for word."),
}


def _py():
    return sys.executable


class Job:
    def __init__(self, run_id: str, cfg: LLMConfig):
        self.run_id, self.cfg = run_id, cfg
        self.ws = runs.run_dir(run_id) / "workspace"
        self.meter = Meter()

    def emit(self, kind, agent, payload):
        runs.append_event(self.run_id, kind, agent, payload)

    def limits(self, name, deadline):
        return Limits(max_turns=TURNS.get(name, 80), deadline=deadline, max_cost=STAGE_MAX_COST)

    async def agent(self, name, task, deadline, team=None, definition=None):
        d = definition or loaders.load_agent(self.ws, name)
        tool_names = list(d.tools)
        if team is None and "SendMessage" in tool_names:
            tool_names.remove("SendMessage")
        system = loaders.system_prompt(self.ws, d, tool_names)
        return await run_agent(name=d.name, system=system, task=task, tool_names=tool_names, cfg=self.cfg,
                               ws=self.ws, emit=self.emit, meter=self.meter,
                               limits=self.limits(d.name, deadline), team=team)

    async def check(self, label, args, ok_codes=(0,), timeout=600):
        """Run a committed Part A script as a stage check. Returns (passed, output)."""
        proc = await asyncio.create_subprocess_exec(
            _py(), "-I", *args, cwd=self.ws, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"})
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            out, code = b"timed out", -9
        else:
            code = proc.returncode
        text = out.decode("utf-8", "replace")
        passed = code in ok_codes
        self.emit("check", "harness", {"check": label, "passed": passed, "exit": code, "output": text[-6000:]})
        return passed, text

    def need(self, *paths):
        missing = [p for p in paths if not (self.ws / p).exists()]
        if missing:
            raise StageError(f"expected output missing: {', '.join(missing)}")
        for p in paths:
            if p.endswith(".json"):
                try:
                    json.loads((self.ws / p).read_text())
                except json.JSONDecodeError as e:
                    raise StageError(f"{p} does not parse as JSON: {e}") from None

    async def require(self, label, args):
        passed, out = await self.check(label, args)
        if not passed:
            raise StageError(f"{label} failed:\n{out[-1500:]}")

    # ---- stages -------------------------------------------------------------

    async def stage1(self, deadline):
        rules = self.ws / "outputs" / "rules.json"
        if rules.exists():
            rules.unlink()  # a rerun starts clean
        await self.agent("main", TASKS["main"], deadline,
                         definition=loaders.skill_session(self.ws, "extract-rules"))
        self.need("outputs/rules.json")
        await self.require("verify_quotes.py", [".claude/skills/extract-rules/verify_quotes.py",
                                                "outputs/rules.json", "data/contract-rules.pdf"])
        return "stage2"

    async def stage2(self, deadline, seed):
        self.need("outputs/rules.json")
        if seed != "risk":
            await run_parallel([self.agent("spend-analyst", TASKS["spend-analyst"], deadline),
                                self.agent("findings-analyst", TASKS["findings-analyst"], deadline)])
        self.need("outputs/analytics.json", "outputs/history.json")
        await self.require("self_check.py", ["scripts/self_check.py"])
        await self.require("verify_history.py", ["scripts/verify_history.py", "outputs/history.json"])
        await self.agent("risk-assessor", TASKS["risk-assessor-first"], deadline)
        self.need("outputs/risk-ratings.json", "outputs/risk-register.md", "outputs/auditor-comments.md")
        await self.require("build_register.py --strict",
                           [".claude/skills/risk-assessment/build_register.py", "--strict"])
        return "awaiting_review"

    async def stage4(self, deadline):
        await self.agent("risk-assessor", TASKS["risk-assessor-revision"], deadline)
        await self.require("build_register.py --strict",
                           [".claude/skills/risk-assessment/build_register.py", "--strict"])
        await self.require("build_pack.py --gate", [".claude/skills/audit-program/build_pack.py", "--gate"])
        team = Team(runs.run_dir(self.run_id) / "mailbox.jsonl", self.emit)
        self.emit("team_start", "lead", {"members": MEMBERS})

        async def member(name):
            try:
                return await self.agent(name, spawn_message(name), deadline, team=team)
            except BaseException:
                team.stop(f"{name} stopped with an error")
                raise

        remaining = max(deadline - time.monotonic(), 60)
        try:
            await asyncio.wait_for(run_parallel([member(m) for m in MEMBERS]), remaining)
        except asyncio.TimeoutError:
            raise StageError("the agent team reached the stage time limit") from None
        if len(team.done) < len(MEMBERS):
            missing = [m for m in MEMBERS if m not in team.done]
            self.emit("warning", "lead", {"text": f"team ended ({team.stop_reason}) without DONE from {missing}"})
        self.need("outputs/planning-memo.md", "outputs/risk-control-matrix.md", "outputs/audit-program.md",
                  "outputs/challenges.md")
        _, out = await self.check("run_checks.py (final QA)", ["scripts/checks/run_checks.py", "--label", "final"],
                                  ok_codes=(0, 1))
        verdict = "READY FOR SIGN-OFF" if "VERDICT: READY FOR SIGN-OFF" in out else "BLOCKED"
        if not (self.ws / "outputs" / "review.md").exists():
            verdict = "BLOCKED"
            self.emit("warning", "harness", {"text": "the qa-reviewer did not write outputs/review.md"})
        runs.update(self.run_id, qa={"verdict": verdict, "output": out[-6000:], "team_done": team.done,
                                     "team_stop": team.stop_reason})
        return "awaiting_signoff"

    # ---- driver -------------------------------------------------------------

    async def run(self, stage):
        run = runs.update(self.run_id, status=stage, error=None,
                          provider=self.cfg.provider, model=self.cfg.model)
        self.emit("stage", "harness", {"stage": stage, "state": "started", "model": self.cfg.model,
                                       "provider": self.cfg.provider})
        started = time.time()
        deadline = time.monotonic() + STAGE_TIMEOUT
        before = protected_hashes(self.ws)
        state, error, nxt = "done", None, None
        try:
            if stage == "stage1":
                nxt = await self.stage1(deadline)
            elif stage == "stage2":
                nxt = await self.stage2(deadline, run["seed"])
            elif stage == "stage4":
                nxt = await self.stage4(deadline)
            else:
                raise StageError(f"unknown stage {stage}")
        except (StageError, LLMError, FileNotFoundError) as e:
            state, error = "failed", redact(e)
        except asyncio.CancelledError:
            self._protect(before)
            self._finish(stage, started, "interrupted", "stopped by the user")
            raise
        except Exception as e:  # noqa: BLE001 - a harness bug must still end the stage cleanly
            state, error = "failed", f"internal error: {type(e).__name__}: {redact(e)}"
        changed = self._protect(before)
        if changed:
            note = "protected files were changed and have been restored: " + ", ".join(changed[:20])
            state, error = "failed", f"{note}\n{error}" if error else note
        self._finish(stage, started, state, error, nxt)

    def _protect(self, before):
        """Any change to data/, scripts/, CLAUDE.md or the agent/skill files fails the stage and is undone."""
        changed = diff_hashes(before, protected_hashes(self.ws))
        if changed:
            restore_protected(self.ws)
        return changed

    def _finish(self, stage, started, state, error, nxt=None):
        run = runs.load(self.run_id)
        run["stages"].append({"stage": stage, "state": state, "started": started, "ended": time.time(),
                              "model": self.cfg.model, "provider": self.cfg.provider,
                              "cost_usd": round(self.meter.cost, 4), "cost_known": self.meter.cost_known,
                              "input_tokens": self.meter.input_tokens, "output_tokens": self.meter.output_tokens,
                              "error": error})
        run["cost_usd"] = round(run["cost_usd"] + self.meter.cost, 4)
        run["cost_known"] = run["cost_known"] and self.meter.cost_known
        run["input_tokens"] += self.meter.input_tokens
        run["output_tokens"] += self.meter.output_tokens
        if state == "done":
            run["status"] = nxt if nxt in ("awaiting_review", "awaiting_signoff") else "ready"
            run["next_stage"] = nxt if nxt.startswith("stage") else None
            run["error"] = None
        else:
            run["status"], run["next_stage"], run["error"] = state, stage, error
        runs.save(run)
        self.emit("stage", "harness", {"stage": stage, "state": state, "error": error,
                                       "cost_usd": round(self.meter.cost, 4)})


async def _drive(run_id, cfg, stage, chain):
    """Run a stage, and keep going through the stages that need no human."""
    with cfg:
        try:
            while stage:
                await Job(run_id, cfg).run(stage)
                run = runs.load(run_id)
                stage = run["next_stage"] if chain and run["status"] == "ready" else None
        finally:
            ACTIVE.pop(run_id, None)


def start(run_id: str, cfg: LLMConfig, stage: str, chain: bool = True) -> None:
    if run_id in ACTIVE:
        raise RuntimeError("this run already has a stage running")
    if len(ACTIVE) >= MAX_ACTIVE:
        raise RuntimeError(f"the server is already running {MAX_ACTIVE} runs; try again later")
    ACTIVE[run_id] = asyncio.get_running_loop().create_task(_drive(run_id, cfg, stage, chain))


def stop(run_id: str) -> bool:
    task = ACTIVE.get(run_id)
    if task:
        task.cancel()
        return True
    return False
