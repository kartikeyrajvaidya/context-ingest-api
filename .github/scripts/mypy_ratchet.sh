#!/usr/bin/env bash
# Mypy ratchet: fail on any mypy error that is not in the committed baseline.
#
# The codebase predates running mypy in CI, so existing errors are recorded in
# .github/mypy-baseline.txt. New code must not add to that list. Line numbers
# are stripped so unrelated edits that shift lines do not trip the check.
#
#   bash .github/scripts/mypy_ratchet.sh            # check
#   bash .github/scripts/mypy_ratchet.sh --update   # rewrite the baseline
#
# Only run --update to shrink the baseline after fixing errors.

set -euo pipefail

cd "$(dirname "$0")/../.."
BASELINE=".github/mypy-baseline.txt"
MYPY="${MYPY:-mypy}"

current="$(mktemp)"
trap 'rm -f "$current"' EXIT

# mypy exits 0 (clean) or 1 (type errors). Anything else, or a missing
# binary, means it did not check the code: fail rather than pass silently.
set +e
out="$("$MYPY" . --no-error-summary --hide-error-context --no-pretty 2>&1)"
rc=$?
set -e
if ((rc > 1)); then
    echo "$out"
    echo "mypy failed to run (exit $rc)."
    exit 1
fi

printf '%s\n' "$out" \
    | grep -E '^[^ ]+:[0-9]+: error:' \
    | sed -E 's/^([^:]+):[0-9]+: /\1: /' \
    | LC_ALL=C sort >"$current" || true

if ((rc == 1)) && [[ ! -s "$current" ]]; then
    echo "$out"
    echo "mypy reported errors that could not be parsed."
    exit 1
fi

if [[ "${1:-}" == "--update" ]]; then
    cp "$current" "$BASELINE"
    echo "Baseline updated: $(wc -l <"$BASELINE" | tr -d ' ') errors."
    exit 0
fi

new_errors="$(LC_ALL=C comm -13 "$BASELINE" "$current")"
fixed_errors="$(LC_ALL=C comm -23 "$BASELINE" "$current")"

if [[ -n "$fixed_errors" ]]; then
    # Fail so the baseline only ever shrinks: a fixed entry left in place
    # would let a later PR add an identical error for free.
    echo "These baseline errors are fixed. Run with --update to shrink the baseline:"
    echo "$fixed_errors"
    exit 1
fi

if [[ -n "$new_errors" ]]; then
    echo "New mypy errors (not in $BASELINE):"
    echo "$new_errors"
    exit 1
fi

echo "mypy: no new errors ($(wc -l <"$current" | tr -d ' ') baselined)."
