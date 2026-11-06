#!/usr/bin/env python3
"""Start, score, and ship Gauntlet races."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "demo-repo"
WORKTREES = ROOT / "worktrees"
REFEREE = ROOT / "referee" / "referee.py"
PYTHON = REPO / ".venv" / "bin" / "python"
AGENTS = ["codex-agent", "codex-b"]


def branch_name(race, agent):
    return f"race-{race}-{agent}"


def run(*command, cwd=REPO):
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True).stdout


def start(_args):
    race = time.strftime("%H%M%S")
    print(f"Race ID: {race}")
    for agent in AGENTS:
        path = WORKTREES / race / agent
        run("git", "worktree", "add", "-q", "-b", branch_name(race, agent), str(path), "main")
        print(f"{agent}: {path}")
    print(f"Test command: {PYTHON} -m pytest -q")


def score(args):
    branches = [branch_name(args.race, agent) for agent in AGENTS] + args.include
    print(run(str(PYTHON), str(REFEREE), "--repo", str(REPO), "--base", "main", "--branches", *branches), end="")


def ship(args):
    branch = branch_name(args.race, args.agent)
    output = run(str(PYTHON), str(REFEREE), "--repo", str(REPO), "--base", "main", "--branches", branch, "--json")
    result = json.loads(output)[0]
    if result["verdict"] != "PASS":
        sys.exit(f"Refusing to ship {branch}: verdict is {result['verdict']}")
    run("git", "push", "-u", "origin", branch)
    body = f"Selected in a Gauntlet race. Referee result: {result['tests_passed']}/{result['tests_total']} tests passed."
    print(run("gh", "pr", "create", "--base", "main", "--head", branch, "--title", f"Gauntlet: ship {args.agent} fix", "--body", body), end="")


def replay(_args):
    run("git", "fetch", "-q", "origin")
    branches = ["origin/replay-codex-agent", "origin/replay-codex-b", "origin/agent-cheat"]
    print(run(str(PYTHON), str(REFEREE), "--repo", str(REPO), "--base", "origin/main", "--branches", *branches), end="")


parser = argparse.ArgumentParser(description=__doc__)
commands = parser.add_subparsers(required=True)
commands.add_parser("start").set_defaults(func=start)
commands.add_parser("replay").set_defaults(func=replay)
score_parser = commands.add_parser("score")
score_parser.add_argument("race")
score_parser.add_argument("--include", nargs="*", default=[])
score_parser.set_defaults(func=score)
ship_parser = commands.add_parser("ship")
ship_parser.add_argument("race")
ship_parser.add_argument("agent", choices=AGENTS)
ship_parser.set_defaults(func=ship)
args = parser.parse_args()
args.func(args)
