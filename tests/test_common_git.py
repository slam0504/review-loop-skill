import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import review_loop_common as c


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True,
                   capture_output=True, text=True)


def make_repo():
    root = tempfile.mkdtemp()
    git(root, "init")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    with open(os.path.join(root, "a.txt"), "w") as f:
        f.write("line1\nline2\nline3\n")
    git(root, "add", "a.txt")
    git(root, "commit", "-m", "init")
    return root


class TestGit(unittest.TestCase):
    def test_is_git_repo(self):
        self.assertTrue(c.is_git_repo(make_repo()))
        self.assertFalse(c.is_git_repo(tempfile.mkdtemp()))

    def test_tree_dirty(self):
        root = make_repo()
        self.assertFalse(c.tree_dirty(root))
        with open(os.path.join(root, "a.txt"), "a") as f:
            f.write("line4\n")
        self.assertTrue(c.tree_dirty(root))

    def test_dirty_check_ignores_agent_dir(self):
        root = make_repo()
        os.makedirs(os.path.join(root, ".agent"))
        with open(os.path.join(root, ".agent", "session-checkpoint.md"), "w") as f:
            f.write("noise\n")
        git(root, "add", "-A")
        self.assertFalse(c.tree_dirty(root))  # .agent changes excluded

    def test_fingerprint_changes_on_real_edit(self):
        root = make_repo()
        fp0 = c.cheap_worktree_fp(root)
        with open(os.path.join(root, "a.txt"), "a") as f:
            f.write("new line added\n")
        self.assertNotEqual(fp0, c.cheap_worktree_fp(root))

    def test_cheap_fingerprint_known_blind_spot_same_numstat(self):
        # DOCUMENTS the intentional blind spot (spec §13): re-editing an
        # already-modified line without changing +/- counts is NOT detected.
        # This test is executable documentation of the trade-off, not a defect.
        root = make_repo()
        with open(os.path.join(root, "a.txt"), "w") as f:
            f.write("EDITED1\nline2\nline3\n")  # line1 -> EDITED1 (numstat 1/1)
        fp_a = c.cheap_worktree_fp(root)
        with open(os.path.join(root, "a.txt"), "w") as f:
            f.write("EDITED2\nline2\nline3\n")  # still numstat 1/1
        fp_b = c.cheap_worktree_fp(root)
        self.assertEqual(fp_a, fp_b)  # blind spot is real and intentional

    def test_base_sha(self):
        self.assertEqual(c.base_sha(tempfile.mkdtemp()), "none")
        self.assertEqual(len(c.base_sha(make_repo())), 40)


if __name__ == "__main__":
    unittest.main()
