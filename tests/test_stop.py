import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(__file__), "..", "hooks")
sys.path.insert(0, HOOKS)
import review_loop_common as c
import stop_enqueue


def git(root, *a):
    subprocess.run(["git", "-C", root, *a], check=True, capture_output=True, text=True)


def enabled_repo(dirty=True):
    root = tempfile.mkdtemp()
    git(root, "init"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    with open(os.path.join(root, "a.txt"), "w") as f:
        f.write("x\n")
    git(root, "add", "a.txt"); git(root, "commit", "-m", "init")
    os.makedirs(c.rl_dir(root)); open(os.path.join(c.rl_dir(root), "enabled"), "w").close()
    if dirty:
        with open(os.path.join(root, "a.txt"), "a") as f:
            f.write("change\n")
    return root


def pending(root):
    return os.path.join(c.rl_dir(root), "pending.json")


class TestStop(unittest.TestCase):
    def test_not_enabled_no_enqueue(self):
        root = enabled_repo()
        os.remove(os.path.join(c.rl_dir(root), "enabled"))
        stop_enqueue.run(json.dumps({"cwd": root}))
        self.assertFalse(os.path.exists(pending(root)))

    def test_non_git_repo_no_enqueue(self):  # acceptance 7
        root = tempfile.mkdtemp()
        os.makedirs(c.rl_dir(root)); open(os.path.join(c.rl_dir(root), "enabled"), "w").close()
        stop_enqueue.run(json.dumps({"cwd": root}))
        self.assertFalse(os.path.exists(pending(root)))

    def test_clean_tree_no_enqueue(self):  # acceptance 2
        root = enabled_repo(dirty=False)
        stop_enqueue.run(json.dumps({"cwd": root}))
        self.assertFalse(os.path.exists(pending(root)))

    def test_dirty_enqueues(self):
        root = enabled_repo()
        stop_enqueue.run(json.dumps({"cwd": root}))
        p = c.read_json(pending(root), {})
        self.assertEqual(p["status"], "pending")
        self.assertEqual(len(p["cheap_worktree_fp"]), 12)

    def test_dedup_same_fingerprint(self):  # acceptance 3
        root = enabled_repo()
        stop_enqueue.run(json.dumps({"cwd": root}))
        first = os.path.getmtime(pending(root))
        stop_enqueue.run(json.dumps({"cwd": root}))  # nothing changed
        self.assertEqual(first, os.path.getmtime(pending(root)))

    def test_re_enqueues_after_change(self):
        root = enabled_repo()
        stop_enqueue.run(json.dumps({"cwd": root}))
        fp1 = c.read_json(pending(root), {})["cheap_worktree_fp"]
        with open(os.path.join(root, "a.txt"), "a") as f:
            f.write("more\n")
        stop_enqueue.run(json.dumps({"cwd": root}))
        self.assertNotEqual(fp1, c.read_json(pending(root), {})["cheap_worktree_fp"])

    def test_stop_uses_only_cheap_git(self):  # acceptance 1
        root = enabled_repo()
        calls = []
        real = c.subprocess.run

        def spy(args, *a, **k):
            calls.append(args)
            return real(args, *a, **k)

        c.subprocess.run = spy
        try:
            stop_enqueue.run(json.dumps({"cwd": root}))
        finally:
            c.subprocess.run = real
        flat = [" ".join(x) for x in calls]
        self.assertFalse(any("codex" in x for x in flat))
        self.assertFalse(any("pytest" in x or "unittest" in x for x in flat))
        for x in flat:
            if "diff" in x:
                self.assertTrue(any(flag in x for flag in
                                    ("--quiet", "--numstat", "--stat", "--name-only")),
                                f"full diff leaked into Stop hook: {x}")

    def test_wrapper_exit_zero_on_error(self):  # acceptance 8
        p = subprocess.run(["bash", os.path.join(HOOKS, "review-loop-stop.sh")],
                           input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
