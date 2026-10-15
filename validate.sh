#!/usr/bin/env bash
# Static checks. Installs nothing. Extends the Blackshield validate.sh pattern.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
fail=0
bad() { echo "FAIL: $*"; fail=1; }
ok() { echo "ok: $*"; }

"$PY" "$ROOT/scripts/check.py" || bad "python checks (layout, palettes, contrast, syntax)"

for f in "$ROOT/install.sh" "$ROOT/validate.sh"; do
  bash -n "$f" || bad "bash syntax $f"
done
ok "bash syntax"

if command -v shellcheck >/dev/null; then
  if shellcheck "$ROOT/install.sh" "$ROOT/validate.sh"; then ok "shellcheck"; else bad "shellcheck"; fi
else
  echo "notice: shellcheck not found, skipping"
fi

if command -v luac >/dev/null; then
  while IFS= read -r -d '' f; do luac -p "$f" || bad "lua syntax $f"; done \
    < <(find "$ROOT/themes" -name '*.lua' -print0)
  ok "lua syntax"
else
  echo "notice: luac not found, skipping lua syntax check"
fi

[[ "$fail" -eq 0 ]] || exit 1
echo "validate: clean"
