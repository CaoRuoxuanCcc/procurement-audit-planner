"""Per-run workspaces: a fresh copy of the Part A project for every run.

Every run gets runs/<id>/workspace/, a copy of CLAUDE.md, .claude/, scripts/
and data/ with an empty outputs/ and a tmp/ scratchpad. The Part A scripts
resolve their paths from __file__, so they work unchanged inside the copy.
"""
import hashlib
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("RUNS_DIR", REPO / ".runs")).resolve()

COPY = ["CLAUDE.md", ".claude", "scripts", "data"]
# Agents may read these but never change them; checked by hash after every stage.
PROTECTED = ["CLAUDE.md", ".claude/agents", ".claude/skills", "scripts", "data"]
# The only places the file tools write to.
WRITABLE = ["outputs", "tmp", ".claude/agent-memory"]

IGNORE = shutil.ignore_patterns("__pycache__", ".DS_Store", "settings.local.json", "*.pyc")

# Inputs that can be reused from the Part A golden run instead of being
# re-derived, keyed by the stage a run starts from.
SEEDS = {
    "full": [],
    "stage2": ["rules.json"],
    "risk": ["rules.json", "analytics.json", "analytics-full", "history.json"],
}


def create_workspace(run_dir: Path, seed: str = "full") -> Path:
    ws = run_dir / "workspace"
    ws.mkdir(parents=True)
    for name in COPY:
        src = REPO / name
        if src.is_dir():
            shutil.copytree(src, ws / name, ignore=IGNORE)
        else:
            shutil.copy2(src, ws / name)
    (ws / "outputs").mkdir()
    (ws / "tmp").mkdir()
    # The agent prompts call `.venv/bin/python -I`; point it at this interpreter.
    (ws / ".venv" / "bin").mkdir(parents=True)
    os.symlink(sys.executable, ws / ".venv" / "bin" / "python")
    for name in SEEDS[seed]:
        src = REPO / "outputs" / name
        if src.is_dir():
            shutil.copytree(src, ws / "outputs" / name, ignore=IGNORE)
        else:
            shutil.copy2(src, ws / "outputs" / name)
    return ws


def _files(root: Path):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".pyc"):
                yield Path(dirpath) / fn


def protected_hashes(ws: Path) -> dict:
    out = {}
    for name in PROTECTED:
        for p in _files(ws / name):
            out[str(p.relative_to(ws))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def diff_hashes(before: dict, after: dict) -> list:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def restore_protected(ws: Path) -> None:
    """Put the protected files back exactly as they are in the repo."""
    for name in PROTECTED:
        dst, src = ws / name, REPO / name
        if dst.is_dir():
            shutil.rmtree(dst)
        elif dst.exists():
            dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst, ignore=IGNORE)
        else:
            shutil.copy2(src, dst)


def resolve(ws: Path, path: str) -> Path:
    """Resolve a tool path inside the workspace; reject anything outside it."""
    p = Path(path)
    if not p.is_absolute():
        p = ws / p
    p = Path(os.path.normpath(p))
    root = Path(os.path.normpath(ws))
    if p != root and root not in p.parents:
        raise PermissionError(f"{path} is outside the project folder")
    return p


def is_writable(ws: Path, p: Path) -> bool:
    rel = p.relative_to(Path(os.path.normpath(ws)))
    return any(rel.parts[: len(Path(w).parts)] == Path(w).parts for w in WRITABLE)
