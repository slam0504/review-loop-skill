import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HOOKS = os.path.join(os.path.dirname(__file__), "..", "hooks")
sys.path.insert(0, HOOKS)
import review_loop_common as c
import consume_feedback


def git(root, *a):
    subprocess.run(["git", "-C", root, *a], check=True, capture_output=True, text=True)


def repo_with_feedback(body, reviewed_fp=None):
    root = tempfile.mkdtemp()
    git(root, "init"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    with open(os.path.join(root, "a.txt"), "w") as f:
        f.write("x\n")
    git(root, "add", "a.txt"); git(root, "commit", "-m", "init")
    os.makedirs(c.rl_dir(root)); open(os.path.join(c.rl_dir(root), "enabled"), "w").close()
    fp = reviewed_fp if reviewed_fp is not None else c.cheap_worktree_fp(root)
    md = (f"---\nreviewed_worktree_fp: {fp}\nverdict: needs_changes\niteration: 1\n---\n\n{body}\n")
    c.atomic_write(os.path.join(c.rl_dir(root), "codex-feedback.md"), md)
    return root


def capture(root):
    buf = io.StringIO()
    with redirect_stdout(buf):
        consume_feedback.run(json.dumps({"cwd": root}))
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


class TestConsume(unittest.TestCase):
    def test_no_feedback_no_output(self):
        root = tempfile.mkdtemp()
        os.makedirs(c.rl_dir(root)); open(os.path.join(c.rl_dir(root), "enabled"), "w").close()
        self.assertIsNone(capture(root))

    def test_fresh_feedback_injected(self):
        root = repo_with_feedback("finding: fix X")
        out = capture(root)
        self.assertIn("finding: fix X", out["hookSpecificOutput"]["additionalContext"])

    def test_fresh_feedback_capped(self):  # acceptance 4
        os.environ["RL_FEEDBACK_MAXCHARS"] = "200"
        try:
            root = repo_with_feedback("Z" * 5000)
            out = capture(root)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertLessEqual(len(ctx), 200)
            self.assertIn("truncated", ctx)
        finally:
            del os.environ["RL_FEEDBACK_MAXCHARS"]

    def test_stale_feedback_short_notice(self):  # acceptance 5
        root = repo_with_feedback("LONG " * 1000, reviewed_fp="deadbeef0000")
        out = capture(root)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("STALE", ctx)
        self.assertNotIn("LONG LONG", ctx)  # body not injected
        self.assertLess(len(ctx), 300)

    def test_not_reinjected_when_already_consumed(self):
        root = repo_with_feedback("finding")
        self.assertIsNotNone(capture(root))
        self.assertIsNone(capture(root))  # second call: already consumed

    def test_wrapper_exit_zero_on_error(self):  # acceptance 8
        p = subprocess.run(["bash", os.path.join(HOOKS, "review-loop-consume.sh")],
                           input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
