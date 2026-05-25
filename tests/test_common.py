import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import review_loop_common as c


class TestCommon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_read_hook_input_handles_garbage(self):
        self.assertEqual(c.read_hook_input(""), {})
        self.assertEqual(c.read_hook_input("not json"), {})
        self.assertEqual(c.read_hook_input('{"cwd":"/x"}'), {"cwd": "/x"})

    def test_get_int_falls_back(self):
        self.assertEqual(c.get_int("RL_NOPE", 7), 7)
        os.environ["RL_TMP_INT"] = "bad"
        self.assertEqual(c.get_int("RL_TMP_INT", 5), 5)
        os.environ["RL_TMP_INT"] = "9"
        self.assertEqual(c.get_int("RL_TMP_INT", 5), 9)
        del os.environ["RL_TMP_INT"]

    def test_resolve_project_root_prefers_cwd(self):
        self.assertEqual(c.resolve_project_root({"cwd": "/a"}), "/a")

    def test_rl_dir_and_enabled(self):
        self.assertEqual(c.rl_dir("/a"), os.path.join("/a", ".agent", "review-loop"))
        self.assertFalse(c.is_enabled(self.tmp))
        os.makedirs(c.rl_dir(self.tmp))
        open(os.path.join(c.rl_dir(self.tmp), "enabled"), "w").close()
        self.assertTrue(c.is_enabled(self.tmp))

    def test_truncate(self):
        self.assertEqual(c.truncate("abc", 10), "abc")
        out = c.truncate("x" * 100, 20)
        self.assertLessEqual(len(out), 20)
        self.assertIn("truncated", out)

    def test_sha12_stable(self):
        self.assertEqual(c.sha12("abc"), c.sha12("abc"))
        self.assertEqual(len(c.sha12("abc")), 12)
        self.assertNotEqual(c.sha12("abc"), c.sha12("abd"))

    def test_atomic_write_and_json_roundtrip(self):
        p = os.path.join(self.tmp, "sub", "x.json")
        c.write_json(p, {"k": 1})
        self.assertEqual(c.read_json(p, {}), {"k": 1})
        self.assertFalse(os.path.exists(p + ".tmp"))
        self.assertEqual(c.read_json(os.path.join(self.tmp, "missing.json"), {"d": 2}), {"d": 2})


if __name__ == "__main__":
    unittest.main()
