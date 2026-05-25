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
import sessionstart_status


def enabled(root):
    os.makedirs(c.rl_dir(root), exist_ok=True)
    open(os.path.join(c.rl_dir(root), "enabled"), "w").close()


def capture(root):
    buf = io.StringIO()
    with redirect_stdout(buf):
        sessionstart_status.run(json.dumps({"cwd": root}))
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


class TestStatus(unittest.TestCase):
    def test_disabled_silent(self):
        self.assertIsNone(capture(tempfile.mkdtemp()))

    def test_pending_one_line(self):
        root = tempfile.mkdtemp(); enabled(root)
        c.write_json(os.path.join(c.rl_dir(root), "pending.json"), {"status": "pending"})
        out = capture(root)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pending", ctx)
        self.assertNotIn("\n", ctx)  # exactly one line

    def test_done_shows_idle(self):
        root = tempfile.mkdtemp(); enabled(root)
        s = c.read_state(root); s["done"] = True; c.write_state(root, s)
        ctx = capture(root)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("idle", ctx)
        self.assertNotIn("\n", ctx)

    def test_wrapper_exit_zero_on_error(self):  # acceptance 8
        p = subprocess.run(["bash", os.path.join(HOOKS, "review-loop-status.sh")],
                           input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
