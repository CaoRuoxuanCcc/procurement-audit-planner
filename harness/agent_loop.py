"""The provider-agnostic agent loop: call the model, run its tool calls, repeat.

A turn ends when the model replies without tool calls. A sub-agent is then
finished and its reply is its report. A teammate goes idle instead and is
woken when a message arrives in its inbox (see team.py).
"""
import asyncio
import json
import time
from dataclasses import dataclass

from . import providers
from .tools import Tools, schemas

EVENT_TEXT = 4000  # characters of a message or tool result kept in the event log


class StageError(Exception):
    pass


@dataclass
class Limits:
    max_turns: int = 80
    deadline: float = 0.0  # time.monotonic() value; 0 = none
    max_cost: float = 0.0  # USD across the stage; 0 = none


class Meter:
    """Tokens and cost for one stage, shared by its agents."""

    def __init__(self):
        self.input_tokens = self.output_tokens = 0
        self.cost = 0.0
        self.cost_known = True

    def add(self, r: providers.Reply):
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens
        if r.cost is None:
            self.cost_known = False
        else:
            self.cost += r.cost


def _short(text, n=EVENT_TEXT):
    text = text or ""
    return text if len(text) <= n else text[:n] + f" … [{len(text) - n} more characters]"


async def run_agent(*, name, system, task, tool_names, cfg, ws, emit, meter, limits, team=None):
    tools = Tools(ws, name, tool_names, team)
    specs = schemas(tool_names)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    emit("agent_start", name, {"task": _short(task), "tools": tool_names})
    last_text = ""
    for turn in range(1, limits.max_turns + 1):
        if limits.deadline and time.monotonic() > limits.deadline:
            raise StageError(f"{name}: stage time limit reached")
        if limits.max_cost and meter.cost > limits.max_cost:
            raise StageError(f"{name}: stage cost limit (${limits.max_cost:.2f}) reached")
        reply = await providers.complete(cfg, messages, specs, agent=name)
        meter.add(reply)
        messages.append(reply.message)
        emit("message", name, {
            "turn": turn, "text": _short(reply.text), "tool_calls": len(reply.tool_calls),
            "finish": reply.finish_reason, "in": reply.input_tokens, "out": reply.output_tokens,
            "stage_cost": round(meter.cost, 4), "cost_known": meter.cost_known})
        if reply.text:
            last_text = reply.text
        if reply.tool_calls:
            for tc in reply.tool_calls:
                emit("tool_call", name, {"tool": tc.name, "args": _short(_pretty(tc.arguments), 1500)})
                result = await tools.run(tc.name, tc.arguments)
                emit("tool_result", name, {"tool": tc.name, "result": _short(result, 2000)})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result or "(empty)"})
            continue
        if reply.finish_reason == "length":
            messages.append({"role": "user", "content": (
                "Your reply was cut off by the output limit. Continue where you stopped; "
                "write large files in parts with Write append=true.")})
            continue
        if team is None:
            emit("agent_done", name, {"report": _short(reply.text, 8000), "turns": turn})
            return reply.text
        # Teammate: idle until a message arrives or the team stops.
        incoming = await team.wait(name)
        if incoming is None:
            emit("agent_done", name, {"report": _short(last_text, 8000), "turns": turn})
            return last_text
        messages.append({"role": "user", "content": incoming})
    raise StageError(f"{name}: reached the limit of {limits.max_turns} turns without finishing")


def _pretty(args):
    try:
        obj = json.loads(args)
    except (json.JSONDecodeError, TypeError):
        return args
    if isinstance(obj, dict) and "content" in obj and isinstance(obj["content"], str) and len(obj["content"]) > 600:
        obj = dict(obj, content=obj["content"][:600] + f" … [{len(obj['content'])} characters]")
    return json.dumps(obj, ensure_ascii=False)


async def run_parallel(coros):
    """Run sub-agents side by side; cancel the rest if one fails."""
    tasks = [asyncio.ensure_future(c) for c in coros]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
