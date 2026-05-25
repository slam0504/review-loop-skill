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


class TestFinalize(unittest.TestCase):
    def _setup(self):
        root = pending_repo()
        reviewer.cmd_prepare(root)
        raw = os.path.join(root, "codex_out.md")
        with open(raw, "w") as f:
            f.write("finding 1: do X\nfinding 2: do Y\n")
        return root, raw

    def test_finalize_writes_header_and_feedback(self):
        root, raw = self._setup()
        reviewer.cmd_finalize(root, raw, "needs_changes", True)
        fb = os.path.join(c.rl_dir(root), "codex-feedback.md")
        with open(fb) as f:
            md = f.read()
        header, body = c.parse_feedback_header(md)
        self.assertEqual(header["verdict"], "needs_changes")
        self.assertEqual(header["iteration"], "1")
        self.assertEqual(header["reviewed_worktree_fp"], c.cheap_worktree_fp(root))
        self.assertEqual(len(header["review_packet_hash"]), 12)
        self.assertIn("finding 1", body)

    def test_finalize_flips_pending_and_archives(self):
        root, raw = self._setup()
        reviewer.cmd_finalize(root, raw, "needs_changes", True)
        pend = c.read_json(os.path.join(c.rl_dir(root), "pending.json"), {})
        self.assertEqual(pend["status"], "reviewed")
        self.assertTrue(os.path.exists(os.path.join(c.rl_dir(root), "iterations", "001-feedback.md")))

    def test_convergence_pass(self):
        root, raw = self._setup()
        reviewer.cmd_finalize(root, raw, "pass", True)
        self.assertTrue(c.read_state(root)["done"])

    def test_convergence_no_new_findings(self):
        root, raw = self._setup()
        reviewer.cmd_finalize(root, raw, "needs_changes", False)
        self.assertTrue(c.read_state(root)["done"])

    def test_convergence_max_iterations(self):
        root, raw = self._setup()
        s = c.read_state(root); s["iteration"] = 4; s["max_iterations"] = 5; c.write_state(root, s)
        reviewer.cmd_finalize(root, raw, "needs_changes", True)  # becomes iteration 5
        self.assertTrue(c.read_state(root)["done"])

    def test_not_done_midloop(self):
        root, raw = self._setup()
        reviewer.cmd_finalize(root, raw, "needs_changes", True)
        self.assertFalse(c.read_state(root)["done"])
        self.assertEqual(c.read_state(root)["iteration"], 1)


class TestCLI(unittest.TestCase):
    def test_cli_prepare_no_pending_exits_1(self):
        root = tempfile.mkdtemp(); os.makedirs(c.rl_dir(root))
        bin_path = os.path.join(os.path.dirname(__file__), "..", "bin", "review-loop")
        p = subprocess.run(["bash", bin_path, "--root", root, "prepare"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)

    def test_cli_prepare_then_finalize(self):
        root = pending_repo()
        bin_path = os.path.join(os.path.dirname(__file__), "..", "bin", "review-loop")
        subprocess.run(["bash", bin_path, "--root", root, "prepare"], check=True,
                       capture_output=True, text=True)
        raw = os.path.join(root, "out.md")
        with open(raw, "w") as f:
            f.write("ok\n")
        subprocess.run(["bash", bin_path, "--root", root, "finalize", raw,
                        "--verdict", "pass"], check=True, capture_output=True, text=True)
        self.assertTrue(c.read_state(root)["done"])


if __name__ == "__main__":
    unittest.main()
