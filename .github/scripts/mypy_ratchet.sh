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

# mypy exits 1 when it finds errors; that is expected here.
"$MYPY" . --no-error-summary --hide-error-context --no-pretty \
    | grep -E '^[^ ]+:[0-9]+: error:' \
    | sed -E 's/^([^:]+):[0-9]+: /\1: /' \
    | LC_ALL=C sort >"$current" || true

if [[ "${1:-}" == "--update" ]]; then
    cp "$current" "$BASELINE"
    echo "Baseline updated: $(wc -l <"$BASELINE" | tr -d ' ') errors."
    exit 0
fi

new_errors="$(LC_ALL=C comm -13 "$BASELINE" "$current")"
fixed_errors="$(LC_ALL=C comm -23 "$BASELINE" "$current")"

if [[ -n "$fixed_errors" ]]; then
    echo "These baseline errors are fixed. Run with --update to shrink the baseline:"
    echo "$fixed_errors"
    echo
fi

if [[ -n "$new_errors" ]]; then
    echo "New mypy errors (not in $BASELINE):"
    echo "$new_errors"
    exit 1
fi

echo "mypy: no new errors ($(wc -l <"$current" | tr -d ' ') baselined)."
