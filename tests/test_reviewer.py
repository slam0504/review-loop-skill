import os
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(__file__), "..", "hooks")
sys.path.insert(0, HOOKS)
import review_loop_common as c
import reviewer


def git(root, *a):
    subprocess.run(["git", "-C", root, *a], check=True, capture_output=True, text=True)


def pending_repo():
    root = tempfile.mkdtemp()
    git(root, "init"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    with open(os.path.join(root, "a.txt"), "w") as f:
        f.write("x\n")
    git(root, "add", "a.txt"); git(root, "commit", "-m", "init")
    with open(os.path.join(root, "a.txt"), "a") as f:
        f.write("CHANGED LINE\n")
    os.makedirs(c.rl_dir(root))
    c.write_json(os.path.join(c.rl_dir(root), "pending.json"),
                 {"status": "pending", "cheap_worktree_fp": c.cheap_worktree_fp(root)})
    return root


class TestPrepare(unittest.TestCase):
    def test_prepare_no_pending(self):
        root = tempfile.mkdtemp(); os.makedirs(c.rl_dir(root))
        self.assertEqual(reviewer.cmd_prepare(root), 1)

    def test_prepare_builds_packet_with_diff(self):
        root = pending_repo()
        self.assertEqual(reviewer.cmd_prepare(root), 0)
        path = os.path.join(c.rl_dir(root), "iterations", "001-packet.md")
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            content = f.read()
        self.assertIn("CHANGED LINE", content)  # full diff present
        self.assertIn("git diff", content)


if __name__ == "__main__":
    unittest.main()
