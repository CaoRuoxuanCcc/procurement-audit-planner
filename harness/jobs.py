"""Stage runner and state machine.

Stage 1  extract-rules skill (main session)       → verify_quotes.py
Stage 2  spend-analyst ‖ findings-analyst          → self_check.py, verify_history.py
         then risk-assessor (first build)          → build_register.py --strict
Gate 1   awaiting_review: the auditor decides each risk in the UI
Stage 4  risk-assessor (revision)                  → build_register.py --strict, build_pack.py --gate
         then the agent team                       → scripts/checks/run_checks.py
Gate 2   awaiting_signoff: the auditor signs off review.md in the UI
QA rerun qa-reviewer alone on the final pack, when Gate 2 is BLOCKED → run_checks.py

The model judges; the committed Part A scripts check every stage. Stages read
and write files only, so a failed or interrupted stage is resumed by running
it again. The API key is held by the job for one stage and then dropped.
"""
import asyncio
import hashlib
import json
import os
import shutil
import sys
import time

from . import loaders, runs
from .agent_loop import Limits, Meter, StageError, run_agent, run_parallel
from .providers import LLMConfig, LLMError, redact
from .team import MEMBERS, Team, spawn_message
from .workspace import REPO, diff_hashes, protected_hashes, restore_protected

STAGE_TIMEOUT = int(os.environ.get("STAGE_TIMEOUT_MIN", "90")) * 60
STAGE_MAX_COST = float(os.environ.get("STAGE_MAX_COST_USD", "0") or 0)
MAX_ACTIVE = int(os.environ.get("MAX_ACTIVE_RUNS", "2"))
TURNS = {"main": 60, "spend-analyst": 50, "findings-analyst": 90, "risk-assessor": 80,
         "planner": 150, "challenger": 120, "qa-reviewer": 100}

ACTIVE: dict = {}  # run_id -> asyncio.Task
PACK = ("outputs/planning-memo.md", "outputs/risk-control-matrix.md", "outputs/audit-program.md",
        "outputs/challenges.md")

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


def findings_retry_task(gap):
    listed = "\n".join(f"- {k}: {v}" for k, v in gap.items())
    return (
        "Targeted rerun. outputs/history.json from the previous attempt passes the verifier but lacks "
        "discrepancies that the auditor's scoring choices (.claude/skills/risk-assessment/scoring_choices.json, "
        f"read-only) refer to by id:\n{listed}\n\nStart from the existing outputs/history.json: keep every item "
        "and id it has. Re-read the strategy for each listed discrepancy and add it under that exact id only if "
        "you can quote both sides from the papers, then run the verifier until it prints ALL CHECKS PASSED. If "
        "the papers do not support one, do not add it; say so in your report. Never invent an item.")


def qa_rerun_task(replay):
    msgs = "\n\n".join(f"Message from {frm} (replayed from the mailbox):\n{body}" for frm, body in replay)
    return (
        "You are `qa-reviewer` in a QA-only rerun of the audit-planning agent team; the lead is `lead`. The "
        "planner and challenger finished in this run's earlier team stage and are not running now: messages "
        "to them are recorded but not delivered. scripts/checks/ is the current committed version. The pack "
        "in outputs/ is final and you change nothing in it. The team's final messages from that stage follow, "
        "replayed word for word by the lead. Follow your agent definition from step 1: run test_checks.py, "
        "record the hashes, treat the replayed PACK READY as the current version, do the final run (both DONE "
        "messages are below), write outputs/review.md from it and send QA DONE to the lead. Do not wait for "
        f"further messages from the planner or challenger.\n\n{msgs}")


def _hash_tree(root, skip=()):
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and str(p.relative_to(root)) not in skip}


def review_verdict(text):
    """The verdict written in review.md's '## Verdict' section, or None."""
    sec = text.split("## Verdict", 1)[1].split("\n## ", 1)[0] if "## Verdict" in text else ""
    if "BLOCKED" in sec:
        return "BLOCKED"
    return "READY FOR SIGN-OFF" if "READY FOR SIGN-OFF" in sec else None


class Job:
    def __init__(self, run_id: str, cfg: LLMConfig):
        self.run_id, self.cfg = run_id, cfg
        self.ws = runs.run_dir(run_id) / "workspace"
        self.meter = Meter()
        self.archived = None

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

    def choices_gap(self):
        """Discrepancy ids the auditor's scoring_choices.json relies on that history.json lacks.

        build_register.py refuses to build when any is missing, so this is checked
        before the risk-assessor runs. Returns {id: what the choices file says about it}.
        """
        choices = json.loads((self.ws / ".claude/skills/risk-assessment/scoring_choices.json").read_text())
        hist = json.loads((self.ws / "outputs/history.json").read_text())
        have = {d.get("id") for d in hist.get("discrepancies", [])}
        need = {c["discrepancy"]: c.get("topic", "") for c in choices.get("choices", []) if c.get("discrepancy")}
        need.update({k: v for k, v in choices.get("not_scoring", {}).items() if k not in need})
        return {k: v for k, v in sorted(need.items()) if k not in have}

    async def existing_ok(self, label, path, args):
        """Whether an output left by an earlier attempt still passes its deterministic check."""
        if not (self.ws / path).exists():
            return False
        passed, _ = await self.check(f"{label} (existing output)", args)
        return passed

    async def stage2(self, deadline, seed):
        self.need("outputs/rules.json")
        if seed != "risk":
            # On a resume, keep any sub-agent output that still passes its check; rerun only the rest.
            agents = []
            if await self.existing_ok("self_check.py", "outputs/analytics.json", ["scripts/self_check.py"]):
                self.emit("note", "harness", {"text": "spend-analyst skipped: analytics.json from the earlier attempt passes self_check.py"})
            else:
                agents.append(self.agent("spend-analyst", TASKS["spend-analyst"], deadline))
            if await self.existing_ok("verify_history.py", "outputs/history.json",
                                      ["scripts/verify_history.py", "outputs/history.json"]):
                gap = self.choices_gap()
                if gap:
                    agents.append(self.agent("findings-analyst", findings_retry_task(gap), deadline))
                else:
                    self.emit("note", "harness", {"text": "findings-analyst skipped: history.json from the earlier attempt passes verify_history.py"})
            else:
                agents.append(self.agent("findings-analyst", TASKS["findings-analyst"], deadline))
            if agents:
                await run_parallel(agents)
        self.need("outputs/analytics.json", "outputs/history.json")
        await self.require("self_check.py", ["scripts/self_check.py"])
        await self.require("verify_history.py", ["scripts/verify_history.py", "outputs/history.json"])
        gap = self.choices_gap()
        self.emit("check", "harness", {"check": "history.json covers scoring_choices.json", "passed": not gap, "exit": 0 if not gap else 1,
                                       "output": "all discrepancy ids present" if not gap else "missing: " + ", ".join(gap)})
        if gap:
            raise StageError(
                "history.json lacks discrepancies that the auditor's scoring_choices.json relies on, so "
                "build_register.py would refuse to build: " + "; ".join(f"{k} ({v})" for k, v in gap.items())
                + ". Resume to rerun the findings-analyst with this gap (the spend analysis is kept), or the "
                "auditor updates scoring_choices.json.")
        await self.agent("risk-assessor", TASKS["risk-assessor-first"], deadline)
        self.need("outputs/risk-ratings.json")
        # Run the builder before checking for its outputs, so a refusal reports the builder's own errors.
        await self.require("build_register.py --strict",
                           [".claude/skills/risk-assessment/build_register.py", "--strict"])
        self.need("outputs/risk-register.md", "outputs/auditor-comments.md")
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
        self.need(*PACK)
        return await self.final_qa(team.done, team.stop_reason)

    async def final_qa(self, team_done, team_stop, **extra):
        """Re-run the QA scripts; READY only if they print it and review.md says the same."""
        _, out = await self.check("run_checks.py (final QA)", ["scripts/checks/run_checks.py", "--label", "final"],
                                  ok_codes=(0, 1))
        verdict = "READY FOR SIGN-OFF" if "VERDICT: READY FOR SIGN-OFF" in out else "BLOCKED"
        review = self.ws / "outputs" / "review.md"
        if not review.exists():
            verdict = "BLOCKED"
            self.emit("warning", "harness", {"text": "the qa-reviewer did not write outputs/review.md"})
        elif review_verdict(review.read_text()) != verdict:
            self.emit("warning", "harness", {"text": f"review.md's verdict does not match run_checks.py ({verdict}); "
                                                     "the verdict is BLOCKED"})
            verdict = "BLOCKED"
        runs.update(self.run_id, qa={"verdict": verdict, "output": out[-6000:], "team_done": team_done,
                                     "team_stop": team_stop, **extra})
        return "awaiting_signoff"

    def qa_replay(self):
        """The team's final PACK READY, PLANNER DONE and relayed CHALLENGER DONE, from the mailbox."""
        last = {}
        mailbox = runs.run_dir(self.run_id) / "mailbox.jsonl"
        for line in (mailbox.read_text().splitlines() if mailbox.exists() else []):
            m = json.loads(line)
            first = m["body"].strip().splitlines()[0] if m["body"].strip() else ""
            for key, frm in (("PACK READY", "planner"), ("PLANNER DONE", "planner"), ("CHALLENGER DONE", "lead")):
                if m["from"] == frm and "qa-reviewer" in m["to"] and (first.startswith(key) or
                                                                       (frm == "lead" and key in m["body"][:200])):
                    last[key] = (m["from"], m["body"])
        missing = [k for k in ("PACK READY", "PLANNER DONE", "CHALLENGER DONE") if k not in last]
        if missing:
            raise StageError(f"cannot rerun QA alone: the mailbox has no {', '.join(missing)} from the team stage")
        return [last["PACK READY"], last["PLANNER DONE"], last["CHALLENGER DONE"]]

    def sync_checks(self):
        """Bring the run's scripts/checks/ up to the committed version; keep the old copies."""
        src, dst = REPO / "scripts" / "checks", self.ws / "scripts" / "checks"
        new, old = _hash_tree(src), _hash_tree(dst)
        changed = sorted(k for k in set(new) | set(old) if new.get(k) != old.get(k) and "__pycache__" not in k)
        if not changed:
            return
        if dst.exists() and self.archived:
            shutil.copytree(dst, self.archived.parent / "checks-before", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.emit("note", "harness", {"text": "scripts/checks/ updated to the committed version: " + ", ".join(changed)
                                      + (f" (earlier copies kept in attempts/{self.archived.parent.name}/checks-before/)"
                                         if self.archived else "")})

    async def qa(self, deadline):
        """QA-only rerun: the qa-reviewer alone on the final pack; nothing else may change."""
        self.need(*PACK)
        replay = self.qa_replay()
        await self.require("test_checks.py", ["scripts/checks/test_checks.py"])
        out = self.ws / "outputs"
        (out / "review.md").unlink(missing_ok=True)  # the earlier one is kept in the attempt archive
        before = _hash_tree(out, skip={"review.md"})
        team = Team(runs.run_dir(self.run_id) / "mailbox.jsonl", self.emit, members=["qa-reviewer"])
        self.emit("team_start", "lead", {"members": ["qa-reviewer"], "mode": "QA-only rerun"})
        try:
            await asyncio.wait_for(self.agent("qa-reviewer", qa_rerun_task(replay), deadline, team=team),
                                   max(deadline - time.monotonic(), 60))
        except asyncio.TimeoutError:
            raise StageError("the QA-only rerun reached the stage time limit") from None
        finally:
            changed = diff_hashes(before, _hash_tree(out, skip={"review.md"}))
            if changed:
                for rel in changed:
                    (out / rel).unlink(missing_ok=True)
                    if self.archived and (self.archived / rel).exists():
                        shutil.copy2(self.archived / rel, out / rel)
        if changed:
            raise StageError("the qa-reviewer changed pack files, which have been restored: " + ", ".join(changed[:20]))
        earlier = (runs.load(self.run_id).get("qa") or {}).get("team_done") or {}
        done = {k: v for k, v in earlier.items() if k != "qa-reviewer"} | team.done
        return await self.final_qa(done, team.stop_reason or "qa-reviewer ended", rerun="qa-only")

    # ---- driver -------------------------------------------------------------

    def archive_attempt(self, run, stage):
        """Before rerunning a stage, keep a copy of what the earlier attempt left in outputs/."""
        n = sum(1 for s in run["stages"] if s["stage"] == stage)
        if stage == "qa":
            n += 1  # a QA rerun always keeps the pack it starts from
        out = self.ws / "outputs"
        if n and out.exists() and any(out.iterdir()):
            dst = runs.run_dir(self.run_id) / "attempts" / f"{stage}-{n}" / "outputs"
            if not dst.exists():
                shutil.copytree(out, dst)
                self.emit("note", "harness", {"text": f"earlier attempt's outputs kept in attempts/{stage}-{n}/"})
            self.archived = dst

    async def run(self, stage):
        self.archive_attempt(runs.load(self.run_id), stage)
        run = runs.update(self.run_id, status=stage, error=None,
                          provider=self.cfg.provider, model=self.cfg.model)
        self.emit("stage", "harness", {"stage": stage, "state": "started", "model": self.cfg.model,
                                       "provider": self.cfg.provider})
        started = time.time()
        deadline = time.monotonic() + STAGE_TIMEOUT
        if stage == "qa":
            self.sync_checks()
        before = protected_hashes(self.ws)
        state, error, nxt = "done", None, None
        try:
            if stage == "stage1":
                nxt = await self.stage1(deadline)
            elif stage == "stage2":
                nxt = await self.stage2(deadline, run["seed"])
            elif stage == "stage4":
                nxt = await self.stage4(deadline)
            elif stage == "qa":
                nxt = await self.qa(deadline)
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
