import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import review_loop_common as c


class TestState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_read_state_defaults(self):
        s = c.read_state(self.tmp)
        self.assertEqual(s["iteration"], 0)
        self.assertEqual(s["max_iterations"], 5)
        self.assertFalse(s["done"])

    def test_max_iterations_from_env(self):
        os.environ["RL_MAX_ITERATIONS"] = "3"
        try:
            self.assertEqual(c.read_state(self.tmp)["max_iterations"], 3)
        finally:
            del os.environ["RL_MAX_ITERATIONS"]

    def test_write_then_read_state(self):
        s = c.read_state(self.tmp)
        s["iteration"] = 2
        s["last_verdict"] = "needs_changes"
        c.write_state(self.tmp, s)
        self.assertEqual(c.read_state(self.tmp)["iteration"], 2)
        self.assertEqual(c.read_state(self.tmp)["last_verdict"], "needs_changes")

    def test_parse_feedback_header(self):
        md = ("---\n"
              "reviewed_worktree_fp: abc123\n"
              "verdict: needs_changes\n"
              "iteration: 2\n"
              "---\n\nbody text here\n")
        header, body = c.parse_feedback_header(md)
        self.assertEqual(header["reviewed_worktree_fp"], "abc123")
        self.assertEqual(header["verdict"], "needs_changes")
        self.assertEqual(body.strip(), "body text here")

    def test_parse_feedback_header_missing(self):
        header, body = c.parse_feedback_header("no header at all")
        self.assertEqual(header, {})
        self.assertEqual(body, "no header at all")


if __name__ == "__main__":
    unittest.main()
