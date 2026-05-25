import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import merge_settings


def cmds(settings, event):
    out = []
    for entry in settings.get("hooks", {}).get(event, []):
        for h in entry.get("hooks", []):
            out.append(h.get("command"))
    return out


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "settings.json")

    def test_creates_three_hooks(self):
        merge_settings.main(self.path)
        with open(self.path) as f:
            s = json.load(f)
        self.assertEqual(len(cmds(s, "Stop")), 1)
        self.assertEqual(len(cmds(s, "UserPromptSubmit")), 1)
        self.assertEqual(len(cmds(s, "SessionStart")), 1)

    def test_preserves_existing_hooks(self):  # acceptance 6
        existing = {"hooks": {
            "PreCompact": [{"hooks": [{"type": "command",
                "command": 'bash "$HOME/.claude/hooks/precompact-checkpoint.sh"'}]}],
            "SessionStart": [{"hooks": [{"type": "command",
                "command": 'bash "$HOME/.claude/hooks/sessionstart-restore.sh"'}]}],
        }}
        with open(self.path, "w") as f:
            json.dump(existing, f)
        merge_settings.main(self.path)
        with open(self.path) as f:
            s = json.load(f)
        self.assertEqual(len(cmds(s, "PreCompact")), 1)
        self.assertIn('precompact-checkpoint.sh', " ".join(cmds(s, "PreCompact")))
        ss = cmds(s, "SessionStart")
        self.assertEqual(len(ss), 2)
        self.assertIn('sessionstart-restore.sh', " ".join(ss))
        self.assertIn('review-loop-status.sh', " ".join(ss))

    def test_idempotent(self):  # acceptance 6
        merge_settings.main(self.path)
        merge_settings.main(self.path)
        merge_settings.main(self.path)
        with open(self.path) as f:
            s = json.load(f)
        self.assertEqual(len(cmds(s, "Stop")), 1)
        self.assertEqual(len(cmds(s, "SessionStart")), 1)

    def test_backup_created_when_existing(self):
        with open(self.path, "w") as f:
            json.dump({"hooks": {}}, f)
        merge_settings.main(self.path)
        self.assertTrue(os.path.exists(self.path + ".bak"))


if __name__ == "__main__":
    unittest.main()
