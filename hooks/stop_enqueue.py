"""Stop hook: enqueue a review marker. Cheap, enqueue-only — no Codex/tests/full-diff."""
import os
import sys

import review_loop_common as c


def run(raw_stdin):
    data = c.read_hook_input(raw_stdin)
    root = c.resolve_project_root(data)
    if not c.is_enabled(root):
        return
    if not c.is_git_repo(root):
        return
    if not c.tree_dirty(root):
        return
    fp = c.cheap_worktree_fp(root)
    pending_path = os.path.join(c.rl_dir(root), "pending.json")
    if c.read_json(pending_path, {}).get("cheap_worktree_fp") == fp:
        return  # dedup: nothing changed since last marker
    c.write_json(pending_path, {
        "status": "pending",
        "created_at": c.now_iso(),
        "cwd": root,
        "base_sha": c.base_sha(root),
        "cheap_worktree_fp": fp,
        "dirty": True,
        "reason": "claude_stop",
    })
    c.log(root, f"enqueue pending fp={fp}")


def main():
    raw = sys.stdin.read()
    try:
        run(raw)
    except Exception as e:  # hook must never block the session
        if os.environ.get("RL_STRICT") == "1":
            raise
        try:
            c.log(c.resolve_project_root(c.read_hook_input(raw)), f"stop error: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
