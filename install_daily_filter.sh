#!/usr/bin/env bash
set -eu

# Install an idempotent cron entry for the filtered legal crawl.
PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_EXECUTABLE:-}"
if [ -z "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
fi
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
    echo "Unable to find an executable Python (set PYTHON_EXECUTABLE)." >&2
    exit 1
fi

LOG_DIR="$PROJECT_ROOT/.run"
LOG_FILE="$LOG_DIR/law_filter_schedule.log"
mkdir -p "$LOG_DIR"

# Cron has a small, predictable environment.  Use absolute paths and run from
# the project directory so imports and output files resolve consistently.
CRON_MARKER="# Law-Push filtered crawl"
CRON_LINE="0 8 * * * cd '$PROJECT_ROOT' && '$PYTHON_BIN' -u '$PROJECT_ROOT/run_filter.py' 30 >> '$LOG_FILE' 2>&1 $CRON_MARKER"

CURRENT_CRONTAB="$(mktemp)"
trap 'rm -f "$CURRENT_CRONTAB"' EXIT
if crontab -l >"$CURRENT_CRONTAB" 2>/dev/null; then
    :
else
    : >"$CURRENT_CRONTAB"
fi

if grep -Fq "$CRON_MARKER" "$CURRENT_CRONTAB"; then
    sed "s|^.*$CRON_MARKER.*$|$CRON_LINE|" "$CURRENT_CRONTAB" >"${CURRENT_CRONTAB}.new"
    mv "${CURRENT_CRONTAB}.new" "$CURRENT_CRONTAB"
else
    printf '\n%s\n' "$CRON_LINE" >>"$CURRENT_CRONTAB"
fi
crontab "$CURRENT_CRONTAB"

echo "Installed daily filtered legal crawl at 08:00."
echo "Command: $PYTHON_BIN $PROJECT_ROOT/run_filter.py 30"
echo "Log: $LOG_FILE"
