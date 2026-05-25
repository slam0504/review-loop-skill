#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.claude/hooks"
mkdir -p "$DEST"
cp "$SRC/hooks/review_loop_common.py" \
   "$SRC/hooks/stop_enqueue.py" \
   "$SRC/hooks/consume_feedback.py" \
   "$SRC/hooks/sessionstart_status.py" \
   "$SRC/hooks/reviewer.py" \
   "$SRC/hooks/review-loop-stop.sh" \
   "$SRC/hooks/review-loop-consume.sh" \
   "$SRC/hooks/review-loop-status.sh" \
   "$DEST/"
chmod +x "$DEST/review-loop-stop.sh" "$DEST/review-loop-consume.sh" "$DEST/review-loop-status.sh"
python3 "$SRC/hooks/merge_settings.py"
echo "review-loop installed to $DEST"
