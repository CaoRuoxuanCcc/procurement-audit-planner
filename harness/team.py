"""The agent team: planner, challenger and qa-reviewer as concurrent loops.

Teammates message each other by name through in-memory inboxes, exactly as
the agent files describe (PACK READY vN, CHALLENGE #n, RESPONSE #n, QA vN,
... DONE). A teammate that ends its turn goes idle and is woken by its next
message. The lead is this module, not a model: it records the DONE lines,
relays CHALLENGER DONE to the qa-reviewer word for word (the qa-reviewer's
memory expects that relay), answers any question with a fixed reply, and
stops the team when all three DONE lines are in, when everyone is idle with
nothing to read (stalled), or at the stage's time limit.
"""
import asyncio
import json
import re
import time

LEAD = "lead"
MEMBERS = ["planner", "challenger", "qa-reviewer"]
DONE_KEYS = {"planner": "PLANNER DONE", "challenger": "CHALLENGER DONE", "qa-reviewer": "QA DONE"}

LEAD_REPLY = (
    "lead: I have no information beyond my spawn message and the project files, and I pass on "
    "nothing I was not asked. Follow your instructions. Anything only the auditor can decide is "
    "recorded \"for the auditor\". If you are blocked, say so with the exact message and end with "
    "your DONE line."
)


def spawn_message(name):
    others = [m for m in MEMBERS if m != name]
    wait = ("Start now." if name == "planner"
            else "Wait for the planner's `PACK READY v1` before reviewing anything.")
    return (
        f"You are `{name}` in the audit-planning agent team. Your teammates are "
        f"`{others[0]}` and `{others[1]}`; the lead is `{LEAD}`. Message them with SendMessage by "
        f"those names. The lead has run `build_pack.py --gate` and it passed: the auditor's decisions "
        f"are applied in a register revision. {wait} Follow your agent definition and its message "
        f"protocol exactly; end with your DONE message as it describes."
    )


class Team:
    def __init__(self, mailbox_path, emit):
        self.inbox = {m: asyncio.Queue() for m in MEMBERS}
        self.idle = {m: False for m in MEMBERS}
        self.done = {}
        self.stopped = asyncio.Event()
        self.stop_reason = ""
        self.mailbox_path = mailbox_path
        self.emit = emit

    def _log(self, frm, to, body, relay=False):
        rec = {"ts": time.time(), "from": frm, "to": to, "body": body, "relay": relay}
        with open(self.mailbox_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        self.emit("team_message", frm, {"to": to, "body": body[:4000], "relay": relay})

    def send(self, frm, names, body):
        bad = [n for n in names if n not in MEMBERS and n != LEAD]
        if bad or not names:
            return f"Error: unknown recipient(s) {bad or names}; use {', '.join(MEMBERS + [LEAD])}"
        self._log(frm, ", ".join(names), body)
        for to in names:
            if to == LEAD:
                self._to_lead(frm, body)
            elif to != frm:
                self.inbox[to].put_nowait((frm, body))
        return f"Sent to {', '.join(names)}."

    def _to_lead(self, frm, body):
        first = body.strip().splitlines()[0] if body.strip() else ""
        key = DONE_KEYS.get(frm)
        if key and first.startswith(key):
            self.done[frm] = first
            if frm == "challenger":
                relayed = f"Relayed word for word by the lead from challenger:\n\n{body}"
                self._log(LEAD, "qa-reviewer", relayed, relay=True)
                self.inbox["qa-reviewer"].put_nowait((LEAD, relayed))
            if len(self.done) == len(MEMBERS):
                self.stop("all three DONE messages received")
            return
        if re.match(r"^(PACK READY|RESPONSE|CHALLENGE|QA v)", first):
            return  # a copy for the lead's record
        self._log(LEAD, frm, LEAD_REPLY)
        self.inbox[frm].put_nowait((LEAD, LEAD_REPLY))

    def stop(self, reason):
        if not self.stopped.is_set():
            self.stop_reason = reason
            self.stopped.set()
            self.emit("team_stop", LEAD, {"reason": reason, "done": self.done})

    def _stalled(self):
        return all(self.idle.values()) and all(q.empty() for q in self.inbox.values())

    async def wait(self, name):
        """Block until messages arrive; return them as one user message, or None when the team stops."""
        q = self.inbox[name]
        if self.stopped.is_set():
            return None
        if q.empty():
            self.idle[name] = True
            if self._stalled():
                self.stop("stalled: every teammate idle with no messages to read")
            getter = asyncio.ensure_future(q.get())
            stopper = asyncio.ensure_future(self.stopped.wait())
            await asyncio.wait([getter, stopper], return_when=asyncio.FIRST_COMPLETED)
            stopper.cancel()
            if not getter.done():
                getter.cancel()
                self.idle[name] = False
                return None
            items = [getter.result()]
        else:
            items = []
        self.idle[name] = False
        while not q.empty():
            items.append(q.get_nowait())
        return "\n\n".join(f"Message from {frm}:\n{body}" for frm, body in items)
