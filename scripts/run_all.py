"""Run the spend-analyst pipeline in order, stopping at the first failure.

Reads/writes: whatever clean.py, contracts.py, tests.py and self_check.py
read and write (see their docstrings).
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

for name in ["clean.py", "contracts.py", "tests.py", "self_check.py"]:
    print(f"== {name}", flush=True)
    rc = subprocess.call([sys.executable, "-I", os.path.join(HERE, name)], cwd=ROOT)
    if rc != 0:
        print(f"STOPPED: {name} exited {rc}", file=sys.stderr)
        sys.exit(rc)
print("== all steps completed")
