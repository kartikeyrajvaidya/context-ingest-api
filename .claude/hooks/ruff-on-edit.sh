#!/usr/bin/env bash
# PostToolUse hook: lint and format a Python file right after Claude edits it.
#
# Runs `ruff check --fix` then `ruff format` on the edited file. Exits 2 when
# lint errors remain, which feeds them back to Claude to fix. Skips quietly for
# non-Python files and when ruff is not installed.

set -uo pipefail

input="$(cat)"
file_path="$(
    printf '%s' "$input" | python3 -c \
        'import json, sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))' \
        2>/dev/null
)"

[[ "$file_path" == *.py ]] || exit 0
[[ -f "$file_path" ]] || exit 0

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

ruff_bin=""
for candidate in "$project_dir/.venv/bin/ruff" "$project_dir/venv/bin/ruff" "$(command -v ruff 2>/dev/null)"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
        ruff_bin="$candidate"
        break
    fi
done

if [[ -z "$ruff_bin" ]]; then
    echo "ruff not found; skipping lint for $file_path (pip install -r requirements-dev.txt)" >&2
    exit 0
fi

cd "$project_dir" || exit 0

# --force-exclude keeps pyproject's exclude list in effect for explicit paths.
"$ruff_bin" check --fix --force-exclude --quiet "$file_path" >/dev/null 2>&1
"$ruff_bin" format --force-exclude --quiet "$file_path" >/dev/null 2>&1

if ! output="$("$ruff_bin" check --force-exclude "$file_path" 2>&1)"; then
    echo "ruff found errors in $file_path that need a manual fix:" >&2
    echo "$output" >&2
    exit 2
fi

exit 0
