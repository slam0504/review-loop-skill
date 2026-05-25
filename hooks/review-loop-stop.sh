#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if python3 "$DIR/stop_enqueue.py"; then
  exit 0
fi
rc=$?
[ "${RL_STRICT:-}" = "1" ] && exit "$rc"
exit 0
