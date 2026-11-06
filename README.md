# Gauntlet

**One coding task. Several AI agents. Evidence decides what's worth shipping, and a human approves it.**

Teams using AI coding agents need a better answer to "which one do we trust with this?" than instinct. Gauntlet turns a team chat room into a bake-off: agents work on the same task in parallel, a referee scores their branches against the original tests, and a person decides what ships.

Built for the Flip the Switch Hackathon (Track 01: Best Business Workflow).

**Demo video:** VIDEO_LINK

## How it works

1. A teammate mentions `@gauntlet` with a task in a Mattermost channel.
2. `@gauntlet` creates one Git worktree and branch per agent, then assigns the task in the room.
3. Each agent fixes the code, runs the tests, commits, and reports back to `@gauntlet`.
4. The referee re-runs the original tests on each branch and posts a scoreboard.
5. Changed test files or test configuration lead to disqualification, with the diff as evidence.
6. A person types `ship it`, and Gauntlet opens a GitHub PR for that branch.

```text
Team room <-> Switch <-> @gauntlet, @codex-agent, @claude-agent, @opencode-agent
                              |
                     one Git worktree per agent
                              |
                     Referee -> scoreboard in the room
                              |
                     Human "ship it" -> GitHub PR
```

## How Switch is used

Switch is the collaboration layer. People and agents share one Mattermost room, and agents are managed through Switch Console. `@gauntlet` assigns work by mentioning the other agents, and they report back the same way. Gauntlet has no custom message broker: its own code only handles worktrees, scoring, and opening the PR.

## What the referee checks

- Runs the tests from the branch's merge base, so edited tests can't change the score
- Restores changed test files and removes added test configuration before running
- Flags deleted test files, removed or changed assertions, skipped tests, and changed test configuration
- Reports tests passed, diff size, files touched, and test time

The smallest passing diff is highlighted as a suggestion. It's not proof of the best fix, so the decision stays with a person.

## Try it

**Replay mode:** scores a recorded race with no agent logins, API keys, or Switch.

```bash
git clone https://github.com/ShivVIT2019/gauntlet.git
cd gauntlet
git clone https://github.com/ShivVIT2019/gauntlet-demo.git demo-repo
python3 -m venv demo-repo/.venv
demo-repo/.venv/bin/pip install pytest
demo-repo/.venv/bin/python gauntlet.py replay
```

**Full live setup:** see [SETUP.md](SETUP.md).

## Demo disclosures

- `agent-cheat` is a **prepared** branch included to show cheat detection reliably. The live agents did not write it.
- `replay-codex-agent` and `replay-codex-b` are saved results from an earlier real race between two Codex agents.
- The demo races three agent vendors against each other: OpenAI Codex, Anthropic Claude Code, and a free OpenCode model.

## Known limitations

- Cheat detection uses pattern matching, so it can miss subtle changes and flag legitimate test edits.
- Tests run on the local machine without container isolation, so use this only with code you trust.
- It has only been tested on a small Python demo repo using pytest.

## Built during the hackathon

The Switch setup, agents, referee, race script, demo repo, and workflow were built during the hackathon, using AI coding tools.

**Team:** [ShivVIT2019](https://github.com/ShivVIT2019), [Vbj1808](https://github.com/Vbj1808)
