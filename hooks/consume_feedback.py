"""UserPromptSubmit hook: inject capped fresh feedback / short stale notice. No full diff."""
import json
import os
import sys

import review_loop_common as c

FEEDBACK_DEFAULT_CAP = 8192


def _emit(additional_context):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": additional_context,
    }}))


def run(raw_stdin):
    data = c.read_hook_input(raw_stdin)
    root = c.resolve_project_root(data)
    if not c.is_enabled(root):
        return
    fb_path = os.path.join(c.rl_dir(root), "codex-feedback.md")
    try:
        with open(fb_path) as f:
            md = f.read()
    except OSError:
        return

    feedback_hash = c.sha12(md)
    state = c.read_state(root)
    if feedback_hash == state.get("last_consumed_feedback_hash"):
        return  # already consumed this feedback version

    header, body = c.parse_feedback_header(md)
    current_fp = c.cheap_worktree_fp(root)
    reviewed_fp = header.get("reviewed_worktree_fp", "")

    if reviewed_fp and reviewed_fp != current_fp:
        _emit(f"Codex review-loop: feedback is STALE (reviewed {reviewed_fp}, "
              f"current tree {current_fp}). Read .agent/review-loop/codex-feedback.md "
              f"only if still relevant.")
    else:
        cap = c.get_int("RL_FEEDBACK_MAXCHARS", FEEDBACK_DEFAULT_CAP)
        head = (f"Codex review-loop feedback "
                f"(verdict={header.get('verdict', 'needs_changes')}, "
                f"iteration={header.get('iteration', '?')}):\n\n")
        _emit(c.truncate(head + body, cap))

    state["last_consumed_feedback_hash"] = feedback_hash
    c.write_state(root, state)


def main():
    raw = sys.stdin.read()
    try:
        run(raw)
    except Exception as e:
        if os.environ.get("RL_STRICT") == "1":
            raise
        try:
            c.log(c.resolve_project_root(c.read_hook_input(raw)), f"consume error: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
