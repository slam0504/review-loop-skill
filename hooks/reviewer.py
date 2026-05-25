"""Out-of-band reviewer CLI: prepare (lazy packet, full diff) + finalize. Human-gated."""
import argparse
import os
import sys

import review_loop_common as c


def _packet_path(root, n):
    return os.path.join(c.rl_dir(root), "iterations", f"{n:03d}-packet.md")


def _feedback_archive(root, n):
    return os.path.join(c.rl_dir(root), "iterations", f"{n:03d}-feedback.md")


def build_packet(root):
    parts = []
    cp = os.path.join(root, ".agent", "session-checkpoint.md")
    if os.path.exists(cp):
        with open(cp) as f:
            parts.append("## Current Goal / Checkpoint\n\n" + f.read())
    parts.append("## git status --short\n\n```\n" + c.run_git(root, ["status", "--short"])[1] + "\n```")
    parts.append("## git diff --stat\n\n```\n" + c.run_git(root, ["diff", "--stat", "HEAD"])[1] + "\n```")
    parts.append("## git diff (full)\n\n```diff\n" + c.run_git(root, ["diff", "HEAD"])[1] + "\n```")
    return "\n\n".join(parts) + "\n"


def cmd_prepare(root):
    pending = c.read_json(os.path.join(c.rl_dir(root), "pending.json"), {})
    if pending.get("status") != "pending":
        print("review-loop: no pending review", file=sys.stderr)
        return 1
    n = c.read_state(root).get("iteration", 0) + 1
    path = _packet_path(root, n)
    c.atomic_write(path, build_packet(root))
    print(path)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="review-loop")
    p.add_argument("--root", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    f = sub.add_parser("finalize")
    f.add_argument("raw_path")
    f.add_argument("--verdict", choices=["pass", "needs_changes", "blocked"], default="needs_changes")
    f.add_argument("--new-findings", choices=["true", "false"], default="true")
    args = p.parse_args(argv)
    root = args.root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if args.cmd == "prepare":
        return cmd_prepare(root)
    return cmd_finalize(root, args.raw_path, args.verdict, args.new_findings == "true")


if __name__ == "__main__":
    sys.exit(main())
