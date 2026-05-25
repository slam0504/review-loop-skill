import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestInstall(unittest.TestCase):
    def test_install_copies_and_merges(self):
        fake_home = tempfile.mkdtemp()
        env = dict(os.environ, HOME=fake_home)
        p = subprocess.run(["bash", os.path.join(ROOT, "install.sh")],
                           env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        dest = os.path.join(fake_home, ".claude", "hooks")
        for f in ["review_loop_common.py", "stop_enqueue.py", "consume_feedback.py",
                  "sessionstart_status.py", "reviewer.py",
                  "review-loop-stop.sh", "review-loop-consume.sh", "review-loop-status.sh"]:
            self.assertTrue(os.path.exists(os.path.join(dest, f)), f)
        self.assertTrue(os.access(os.path.join(dest, "review-loop-stop.sh"), os.X_OK))
        with open(os.path.join(fake_home, ".claude", "settings.json")) as f:
            s = json.load(f)
        self.assertIn("Stop", s["hooks"])


if __name__ == "__main__":
    unittest.main()
