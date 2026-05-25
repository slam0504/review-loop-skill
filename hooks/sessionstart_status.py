"""SessionStart hook: inject EXACTLY ONE status line. Coexists with context-checkpoint."""
import json
import os
import sys

import review_loop_common as c


def status_line(root):
    if not c.is_enabled(root):
        return None
    d = c.rl_dir(root)
    state = c.read_state(root)
    it = f"{state.get('iteration', 0)}/{state.get('max_iterations', 5)}"
    if state.get("done"):
        return f"review-loop: idle (iteration {it})"
    fb_path = os.path.join(d, "codex-feedback.md")
    if os.path.exists(fb_path):
        try:
            with open(fb_path) as f:
                header, _ = c.parse_feedback_header(f.read())
        except OSError:
            header = {}
        reviewed_fp = header.get("reviewed_worktree_fp", "")
        fresh = (not reviewed_fp) or reviewed_fp == c.cheap_worktree_fp(root)
        return ("review-loop: fresh Codex feedback available" if fresh
                else "review-loop: stale Codex feedback present")
    if os.path.exists(os.path.join(d, "pending.json")):
        return "review-loop: pending review"
    return f"review-loop: active (iteration {it})"


def run(raw_stdin):
    data = c.read_hook_input(raw_stdin)
    root = c.resolve_project_root(data)
    line = status_line(root)
    if line:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": line}}))


def main():
    raw = sys.stdin.read()
    try:
        run(raw)
    except Exception as e:
        if os.environ.get("RL_STRICT") == "1":
            raise
        try:
            c.log(c.resolve_project_root(c.read_hook_input(raw)), f"status error: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
