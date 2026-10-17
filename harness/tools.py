"""The tools agents call, named after the Claude Code tools the agent files list.

Everything is scoped to the run's workspace: paths outside it are rejected,
the file tools write only to outputs/, tmp/ and .claude/agent-memory/, and
Bash runs in the workspace with a clean environment (no server secrets) and a
time limit. The protected folders are also checked by hash after each stage.
"""
import asyncio
import json
import os
import re
import signal
from pathlib import Path

from .workspace import WRITABLE, is_writable, resolve

MAX_RESULT = 30_000
BASH_TIMEOUT = 300
BASH_MAX_TIMEOUT = 600


def _s(desc):
    return {"type": "string", "description": desc}


def _i(desc):
    return {"type": "integer", "description": desc}


def _b(desc):
    return {"type": "boolean", "description": desc}


SCHEMAS = {
    "Read": ("Read a text file. Returns numbered lines. For PDFs use Bash with pdftotext.",
             {"file_path": _s("path relative to the project root"),
              "offset": _i("first line to read, 1-based (optional)"),
              "limit": _i("number of lines to read (optional, default 2000)")}, ["file_path"]),
    "Write": ("Write a file under outputs/, tmp/ or .claude/agent-memory/. Overwrites unless append is true.",
              {"file_path": _s("path relative to the project root"),
               "content": _s("the full file content (or the part to append)"),
               "append": _b("append to the file instead of overwriting (optional)")}, ["file_path", "content"]),
    "Edit": ("Replace an exact string in a file you may write. old_string must occur exactly once unless replace_all.",
             {"file_path": _s("path relative to the project root"),
              "old_string": _s("exact text to replace"),
              "new_string": _s("replacement text"),
              "replace_all": _b("replace every occurrence (optional)")}, ["file_path", "old_string", "new_string"]),
    "Bash": ("Run a shell command (bash -c) in the project root. Output is truncated.",
             {"command": _s("the command"),
              "timeout": _i(f"seconds, default {BASH_TIMEOUT}, max {BASH_MAX_TIMEOUT} (optional)")}, ["command"]),
    "Glob": ("List files matching a glob pattern such as outputs/**/*.csv, newest first.",
             {"pattern": _s("glob pattern relative to the project root")}, ["pattern"]),
    "Grep": ("Search file contents with an extended regular expression (grep -rnE).",
             {"pattern": _s("regular expression"),
              "path": _s("file or folder to search (optional, default the project root)"),
              "glob": _s("only files matching this name pattern, e.g. *.md (optional)"),
              "ignore_case": _b("case-insensitive (optional)"),
              "files_only": _b("list matching files only (optional)")}, ["pattern"]),
    "SendMessage": ("Send a message to a teammate or the lead, by name. Several names may be separated by commas.",
                    {"to": _s("recipient name(s), e.g. planner or challenger,qa-reviewer or lead"),
                     "message": _s("the message; put the keyword line first")}, ["to", "message"]),
}


def schemas(names):
    out = []
    for n in names:
        desc, props, req = SCHEMAS[n]
        out.append({"type": "function", "function": {
            "name": n, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}})
    return out


def truncate(text: str, limit: int = MAX_RESULT) -> str:
    if len(text) <= limit:
        return text
    head, tail = text[: limit * 2 // 3], text[-limit // 3 :]
    return f"{head}\n\n[... {len(text) - len(head) - len(tail)} characters truncated ...]\n\n{tail}"


class ToolError(Exception):
    pass


class Tools:
    def __init__(self, ws: Path, agent: str, allowed: list, team=None):
        self.ws, self.agent, self.allowed, self.team = ws, agent, allowed, team

    def _writable(self, path: str) -> Path:
        p = resolve(self.ws, path)
        if not is_writable(self.ws, p):
            raise ToolError(f"{path} is read-only; write only under {', '.join(w + '/' for w in WRITABLE)}")
        return p

    async def run(self, name: str, raw_args: str) -> str:
        if name not in self.allowed:
            return f"Error: tool {name} is not available to {self.agent}"
        try:
            args = json.loads(raw_args or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments are not an object")
        except (json.JSONDecodeError, ValueError) as e:
            return (f"Error: the tool arguments are not valid JSON ({e}). If the call was cut off by the "
                    "output limit, write the file in smaller parts with Write append=true.")
        try:
            return truncate(await getattr(self, "t_" + name)(**args))
        except TypeError as e:
            return f"Error: bad arguments for {name}: {e}"
        except (ToolError, PermissionError, FileNotFoundError, IsADirectoryError, UnicodeDecodeError) as e:
            return f"Error: {e}"

    async def t_Read(self, file_path, offset=None, limit=None):
        p = resolve(self.ws, file_path)
        if p.suffix.lower() == ".pdf":
            raise ToolError("Read does not open PDFs; use Bash: pdftotext -f N -l N file.pdf -")
        if p.is_dir():
            raise ToolError(f"{file_path} is a folder; use Glob or Bash ls")
        lines = p.read_text().splitlines()
        start = max(int(offset or 1), 1)
        chunk = lines[start - 1 : start - 1 + int(limit or 2000)]
        if not chunk:
            return f"(no lines from {start}; the file has {len(lines)} lines)"
        return "\n".join(f"{i:6}\t{line[:2000]}" for i, line in enumerate(chunk, start))

    async def t_Write(self, file_path, content, append=False):
        p = self._writable(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a" if append else "w") as f:
            f.write(content)
        return f"{'Appended to' if append else 'Wrote'} {file_path} ({len(content)} characters)"

    async def t_Edit(self, file_path, old_string, new_string, replace_all=False):
        p = self._writable(file_path)
        text = p.read_text()
        n = text.count(old_string)
        if n == 0:
            raise ToolError("old_string not found in the file")
        if n > 1 and not replace_all:
            raise ToolError(f"old_string occurs {n} times; add context or set replace_all")
        p.write_text(text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1))
        return f"Edited {file_path} ({n if replace_all else 1} replacement(s))"

    async def t_Glob(self, pattern):
        if pattern.startswith("/") or ".." in Path(pattern).parts:
            raise ToolError("use a pattern relative to the project root")
        hits = [p for p in self.ws.glob(pattern) if p.is_file() and ".venv" not in p.parts]
        hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        rel = [str(p.relative_to(self.ws)) for p in hits[:300]]
        return "\n".join(rel) + (f"\n[{len(hits) - 300} more]" if len(hits) > 300 else "") if rel else "(no matches)"

    async def t_Grep(self, pattern, path=".", glob=None, ignore_case=False, files_only=False):
        target = resolve(self.ws, path)
        cmd = ["grep", "-rnE", "--exclude-dir=.venv", "--exclude-dir=__pycache__"]
        if ignore_case:
            cmd.append("-i")
        if files_only:
            cmd.append("-l")
        if glob:
            cmd.append(f"--include={glob}")
        cmd += ["--", pattern, str(target)]
        out, _ = await self._exec(cmd, 60)
        return out.replace(str(self.ws) + "/", "") or "(no matches)"

    async def t_Bash(self, command, timeout=None):
        t = min(int(timeout or BASH_TIMEOUT), BASH_MAX_TIMEOUT)
        out, code = await self._exec(["bash", "-c", command], t)
        return f"{out}\n[exit code {code}]" if out else f"[exit code {code}, no output]"

    async def _exec(self, cmd, timeout):
        env = {
            "PATH": f"{self.ws / '.venv' / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": str(self.ws / "tmp"),
            "TMPDIR": str(self.ws / "tmp"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=self.ws, env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        try:
            data, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
            return f"Command timed out after {timeout}s and was killed.", -9
        except asyncio.CancelledError:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise
        return data.decode("utf-8", "replace"), proc.returncode

    async def t_SendMessage(self, to, message):
        if self.team is None:
            raise ToolError("SendMessage is only available in the agent team")
        names = [n.strip() for n in re.split(r"[,\s]+", to) if n.strip()]
        return self.team.send(self.agent, names, message)
