"""Load CLAUDE.md, skills and agent definitions into system prompts.

Mirrors what Claude Code does with the same files:
- CLAUDE.md goes into every agent's system prompt;
- an agent file's body is its system prompt, its frontmatter `tools:` its
  tool allow-list, `skills:` the skills preloaded into its context, and
  `memory: project` its memory folder under .claude/agent-memory/<name>/;
- a skill's SKILL.md body is injected when the stage that uses it runs.
"""
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

PREAMBLE = """\
# Harness environment

You are running inside the Procurement Audit Planner web harness: an
independent re-implementation of the Claude Code setup this project was built
with. The project files below (CLAUDE.md, your agent definition, skills) are
the same ones Claude Code used. Differences from Claude Code:

- Working directory: the project root of this run, a fresh copy of the
  project. Use paths relative to it (e.g. `outputs/rules.json`).
- Your tools: {tools}. `Bash` runs `bash -c` in the project root with a
  time limit and truncated output. Do not install packages or use the network.
- `<scratchpad>` in your instructions means the folder `tmp/`.
- Python is `.venv/bin/python` (pandas and openpyxl installed). `pdftotext`,
  `pdfinfo`, `shasum`, `grep` and `find` are on PATH.
- No one answers questions during a stage. Where your instructions say to ask
  the user or the auditor, or to stop and report, stop and put the question or
  problem in your final report; the harness shows it to the auditor.
- Read-only: `data/`, `scripts/`, `CLAUDE.md`, `.claude/agents/`,
  `.claude/skills/`. The harness hashes them after the stage and fails it if
  any changed. Write only under `outputs/`, `tmp/` and
  `.claude/agent-memory/{name}/`.
- Never print a whole dataset or a whole large file: use head, grep, counts
  and short Python one-liners. Large tool results are truncated.
- Write large files in parts if needed (`Write` with `append: true`).
- When you are finished, reply with your report and no tool calls; that
  ends your turn.
"""


@dataclass
class Definition:
    name: str
    body: str
    tools: list = field(default_factory=lambda: list(DEFAULT_TOOLS))
    skills: list = field(default_factory=list)
    memory: bool = False


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 4 :].lstrip("\n")


def _list(value):
    return [t.strip() for t in value.split(",") if t.strip()] if value else []


def load_agent(ws: Path, name: str) -> Definition:
    path = ws / ".claude" / "agents" / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"agent definition {path.name} is missing")
    meta, body = parse_frontmatter(path.read_text())
    return Definition(
        name=meta.get("name", name),
        body=body,
        tools=_list(meta.get("tools")) or list(DEFAULT_TOOLS),
        skills=_list(meta.get("skills")),
        memory=meta.get("memory") == "project",
    )


def load_skill(ws: Path, name: str) -> str:
    path = ws / ".claude" / "skills" / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"skill {name}/SKILL.md is missing")
    return parse_frontmatter(path.read_text())[1]


def skill_session(ws: Path, skill: str) -> Definition:
    """The main session running a human-invoked skill (no agent file)."""
    return Definition(name="main", body="", skills=[skill])


def _memory(ws: Path, name: str) -> str:
    folder = ws / ".claude" / "agent-memory" / name
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / "MEMORY.md"
    text = "\n".join(index.read_text().splitlines()[:200]) if index.exists() else "(empty)"
    return (
        f"# Agent memory\n\nYour memory folder is `.claude/agent-memory/{name}/`. "
        "Its index MEMORY.md is below; read a linked file when it is relevant.\n\n" + text
    )


def system_prompt(ws: Path, d: Definition, tool_names: list) -> str:
    parts = [PREAMBLE.format(tools=", ".join(tool_names), name=d.name)]
    parts.append("# CLAUDE.md (project instructions)\n\n" + (ws / "CLAUDE.md").read_text())
    if d.body:
        parts.append(f"# Your agent definition: {d.name}\n\n" + d.body)
    for s in d.skills:
        parts.append(f"# Skill: {s} (already loaded; do not re-read it)\n\n" + load_skill(ws, s))
    if d.memory:
        parts.append(_memory(ws, d.name))
    return "\n\n---\n\n".join(parts)
