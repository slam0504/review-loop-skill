"""Idempotent, non-destructive merge of review-loop hooks into settings.json."""
import json
import os
import sys

HOOKS = {
    "Stop": "review-loop-stop.sh",
    "UserPromptSubmit": "review-loop-consume.sh",
    "SessionStart": "review-loop-status.sh",
}


def _command(script):
    return f'bash "$HOME/.claude/hooks/{script}"'


def _has(entries, command):
    return any(h.get("command") == command
               for entry in entries for h in entry.get("hooks", []))


def merge(settings):
    hooks = settings.setdefault("hooks", {})
    for event, script in HOOKS.items():
        command = _command(script)
        entries = hooks.setdefault(event, [])
        if not _has(entries, command):
            entries.append({"hooks": [{"type": "command", "command": command}]})
    return settings


def main(path=None):
    path = path or os.path.expanduser("~/.claude/settings.json")
    if os.path.exists(path):
        with open(path) as f:
            settings = json.load(f)
        with open(path + ".bak", "w") as b:
            json.dump(settings, b, indent=2)
    else:
        settings = {}
    merge(settings)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, path)
    print(f"merged review-loop hooks into {path}")


if __name__ == "__main__":
    main()
