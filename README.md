# review-loop

A hook-gated, human-driven **Codex review loop** for Claude Code. Claude Code hooks only do
cheap, instant work — *enqueue* a "needs review" marker and *consume* bounded feedback — while the
actual Codex review runs **out-of-band**. No hook ever calls Codex, runs tests, or reads a full
diff, so no hook can time out.

The flow stays: Claude works → Codex reviews → Claude fixes → Codex re-reviews → … but nothing
blocks on a hook.

> Why it exists: an earlier attempt ran the Codex review *inside* a hook (Codex + tests + full
> diff). Hooks block the turn and have a per-command timeout, so an interactive, minutes-long
> review inside a hook is a guaranteed timeout. This inverts that: hooks enqueue/consume only.

## How it works

Three global Claude Code hooks (zero API cost, stdlib Python only) plus one out-of-band reviewer:

| Actor | Fires on | What it does |
|-------|----------|--------------|
| `Stop` hook | Claude finishes a turn | If enabled **and** the tree changed since the last marker, atomically writes `pending.json`. Cheap, enqueue-only. |
| `UserPromptSubmit` hook | next user prompt | Injects **capped, fresh** Codex feedback — or a **one-line stale notice** — via `additionalContext`. |
| `SessionStart` hook | session start / resume | Injects **exactly one** status line (coexists with other SessionStart hooks). |
| `reviewer` (you) | manual, out-of-band | `prepare` lazily builds a review packet (full diff allowed), you run Codex on it, `finalize` writes bounded feedback. |

- State is **per project**, under `<project>/.agent/review-loop/`.
- **Everything is gated by an `enabled` file.** Every hook is a no-op unless
  `<project>/.agent/review-loop/enabled` exists — so installing globally is safe; the loop only runs
  where you opt in.
- Writes are **atomic** (`.tmp` + `os.replace`).
- Hooks are **non-blocking by default**: any error is logged to
  `<project>/.agent/review-loop/review-loop.log` and the hook still exits 0. Set `RL_STRICT=1` to
  make errors surface (non-zero exit) for debugging.

## Staleness — the hybrid hash model

To know whether code changed since Codex last reviewed it, the loop uses **two** hashes so that
hooks stay cheap while the reviewer can be exact:

- **`cheap_worktree_fp`** — used by the **hooks** (Stop dedup + enqueue, consume staleness). Built
  from `git rev-parse HEAD` + `git status --porcelain` + `git diff --numstat` (and `--cached`),
  all excluding `.agent/`. **Never runs a full `git diff`.**
- **`review_packet_hash`** — used by the **reviewer only** (out-of-band). Byte-exact over the
  generated packet, which includes the full diff. Recorded in the feedback header for audit; **no
  hook reads it.**

The consume hook compares the current `cheap_worktree_fp` against the `reviewed_worktree_fp`
recorded in the feedback header: match → inject capped feedback; mismatch → one-line stale notice.

> **Intentional, documented blind spot:** the cheap fingerprint is line-count-granular. Re-editing
> an already-modified line *without* changing its added/deleted counts won't register as a change,
> so feedback may look fresh when it's marginally stale. This trade-off keeps hooks free of
> full-diff work and timeouts. The test `test_cheap_fingerprint_known_blind_spot_same_numstat`
> asserts the blind spot on purpose — it's executable documentation, not a defect.

## State files

`<project>/.agent/review-loop/`:

```
enabled            # presence = loop active (you create/remove this)
pending.json       # the enqueue marker + cheap_worktree_fp (also the dedup key)
codex-feedback.md  # latest feedback the consume hook injects
state.json         # iteration / max_iterations / last_verdict / last_consumed / done
review-loop.log    # append-only debug log
iterations/
  001-packet.md    # archived review packet per round
  001-feedback.md  # archived feedback per round
```

## Install

Requires `python3` and `git`. The installer copies the hook files to `~/.claude/hooks/` and
**merges** (never overwrites) `~/.claude/settings.json`, backing the current file up to
`~/.claude/settings.json.bak` first.

```bash
git clone git@github.com:slam0504/review-loop-skill.git
cd review-loop-skill
bash install.sh
```

The merge is additive and idempotent — it adds `Stop`, `UserPromptSubmit`, and `SessionStart`
entries, never duplicates them on re-run, and coexists with other hooks (e.g. the companion
[`context-checkpoint`](https://github.com/slam0504/context-checkpoint-skill) hooks: its `PreCompact`
is untouched and its `SessionStart` keeps running ahead of this one).

To revert:

```bash
cp ~/.claude/settings.json.bak ~/.claude/settings.json
rm ~/.claude/hooks/{review_loop_common,stop_enqueue,consume_feedback,sessionstart_status,reviewer}.py \
   ~/.claude/hooks/review-loop-{stop,consume,status}.sh
```

## Enable & use

Installing does **not** start the loop anywhere. Turn it on per project:

```bash
mkdir -p .agent/review-loop && touch .agent/review-loop/enabled
```

Now, in that project:

1. Work in Claude Code as usual. When a turn ends with a dirty tree, the `Stop` hook writes
   `pending.json`.
2. Run a review round out-of-band:
   ```bash
   review-loop prepare                       # builds .agent/review-loop/iterations/NNN-packet.md, prints its path
   # ...run Codex as a reviewer on that packet, save its output to a file, e.g. out.md...
   review-loop finalize out.md --verdict needs_changes --new-findings true
   ```
   (`review-loop` is `bin/review-loop`; add it to your PATH or call it by path. Use `--root <dir>`
   to target a project other than `$PWD`.)
3. On your next prompt in Claude Code, the `UserPromptSubmit` hook injects the (capped) feedback —
   or a short stale notice if you've since changed the code.
4. Repeat until it converges.

Suggested Codex prompt for the packet:

> Read this review packet and act as a reviewer/advisor. **Do not edit any files.** List findings
> ordered by severity.

### Convergence

The loop is done when **any** of:

- `--verdict pass`, or
- `iteration >= max_iterations` (default 5), or
- `--new-findings false` (reviewer-asserted — prose findings can't be reliably auto-diffed), or
- you remove `.agent/review-loop/enabled`.

When done, `SessionStart` reports `review-loop: idle`.

## Configuration

All optional; defaults baked in. Override via environment variables:

| Var | Default | Meaning |
|-----|---------|---------|
| `RL_FEEDBACK_MAXCHARS` | 8192 | hard cap of the feedback injected by the consume hook |
| `RL_MAX_ITERATIONS` | 5 | iteration cap for convergence |
| `RL_STRICT` | unset | hooks exit non-zero on error when `=1` (default: log + exit 0) |

## Known limitations

- **Human-gated.** The Codex call itself is manual; there is no background worker (deliberately —
  Codex CLI is interactive, and a detached worker would need locking/concurrency handling).
- Fresh feedback surfaces on the **next user prompt**, not instantly.
- `--new-findings` is reviewer-asserted, not machine-verified.
- Non-git projects are unsupported by design (the loop reviews diffs).
- Staleness is line-count-granular (see the blind spot above).

## Development

```bash
python3 -m unittest discover -s tests -v
```

Layout:

```
hooks/
  review_loop_common.py    # shared helpers (input, config, paths, hashing, git, state, header parse)
  stop_enqueue.py          # Stop hook logic (enqueue-only)
  consume_feedback.py      # UserPromptSubmit logic (capped fresh / short stale)
  sessionstart_status.py   # SessionStart logic (one status line)
  reviewer.py              # out-of-band reviewer: prepare + finalize
  review-loop-stop.sh      # non-blocking wrapper
  review-loop-consume.sh   # non-blocking wrapper
  review-loop-status.sh    # non-blocking wrapper
  merge_settings.py        # install-time settings merge (not copied as a hook)
bin/
  review-loop              # reviewer CLI dispatcher
install.sh
tests/                     # unittest, stdlib only
```

Design docs live in the companion playground under `docs/superpowers/specs/` and
`docs/superpowers/plans/`.
