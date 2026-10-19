#!/usr/bin/env bash
# One entry point for local work on the audit planner.
#
#   scripts/dev.sh setup      create .venv and install requirements.txt
#   scripts/dev.sh serve      browse outputs/ at http://localhost:8000 (PORT=9000 to change)
#   scripts/dev.sh test       run every test suite (fixtures only; outputs are not modified)
#   scripts/dev.sh check      run the four QA checks on the current outputs
#   scripts/dev.sh verify     check rules.json and history.json against the source PDFs
#   scripts/dev.sh gate       run the approved-scope gate (build_pack.py --gate)
#   scripts/dev.sh pipeline   REGENERATE analytics from data/ (clean, contracts, tests, self_check)
#   scripts/dev.sh all        setup, test, check, verify, then serve
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY=".venv/bin/python"
PORT="${PORT:-8000}"

setup() {
  [ -x "$PY" ] || python3 -m venv .venv
  $PY -m pip install --quiet --upgrade pip
  $PY -m pip install --quiet -r requirements.txt
  echo "setup ok: $($PY --version)"
}

need_venv() { [ -x "$PY" ] || { echo "No .venv yet; run: scripts/dev.sh setup" >&2; exit 1; }; }

run_tests() {
  need_venv
  local failed=0
  for t in scripts/test_verify_history.py \
           scripts/checks/test_checks.py \
           .claude/skills/risk-assessment/test_build_register.py \
           .claude/skills/audit-program/test_build_pack.py; do
    echo "== $t"
    $PY -I "$t" || { echo "FAILED: $t" >&2; failed=1; }
  done
  return $failed
}

verify() {
  need_venv
  $PY -I scripts/verify_history.py outputs/history.json data/committee
  $PY -I .claude/skills/extract-rules/verify_quotes.py outputs/rules.json data/contract-rules.pdf
}

case "${1:-serve}" in
  setup)    setup ;;
  serve)    need_venv; exec $PY -I scripts/serve.py --port "$PORT" ;;
  test)     run_tests ;;
  check)    need_venv; $PY -I scripts/checks/run_checks.py ;;
  verify)   verify ;;
  gate)     need_venv; $PY -I .claude/skills/audit-program/build_pack.py --gate ;;
  pipeline) need_venv; $PY -I scripts/run_all.py ;;
  all)      setup; run_tests; $PY -I scripts/checks/run_checks.py; verify; exec $PY -I scripts/serve.py --port "$PORT" ;;
  *)        sed -n '2,13p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
