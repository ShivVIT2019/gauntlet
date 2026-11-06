#!/usr/bin/env python3
"""Score agent branches using the tests from their merge base."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

TEST_FILE = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$)")
RUNNABLE_TEST = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py)$")
CONFIG_FILE = re.compile(r"(^|/)(conftest\.py|pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml)$")
REMOVED_RISK = re.compile(r"\bassert\b|\bdef test_")
ADDED_RISK = re.compile(r"pytest\.(mark\.)?(skip|xfail)|unittest\.skip|\bskipTest\b")


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def changed_lines(repo, merge_base, branch, path):
    diff = git(repo, "diff", "--no-renames", "--unified=0", merge_base, branch, "--", path)
    return [
        line
        for line in diff.splitlines()
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]


def find_cheats(repo, merge_base, branch, changes):
    flags = []
    for status, path in changes:
        is_test = bool(TEST_FILE.search(path))
        is_config = bool(CONFIG_FILE.search(path))
        if not is_test and not is_config:
            continue
        if status == "D":
            flags.append({"file": path, "reason": "Deleted a protected test file", "evidence": []})
            continue
        lines = changed_lines(repo, merge_base, branch, path)
        if is_config:
            flags.append({"file": path, "reason": "Changed test configuration", "evidence": lines[:8]})
        elif status != "A":
            removed = any(line[0] == "-" and REMOVED_RISK.search(line) for line in lines)
            skipped = any(line[0] == "+" and ADDED_RISK.search(line) for line in lines)
            if removed or skipped:
                reason = "Weakened or removed a test" if removed else "Skipped a test"
                flags.append({"file": path, "reason": reason, "evidence": lines[:8]})
    return flags


def run_tests(worktree, test_files, junit_path, timeout):
    command = [
        sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider",
        f"--junitxml={junit_path}", *test_files,
    ]
    started = time.monotonic()
    try:
        subprocess.run(command, cwd=worktree, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"total": 0, "passed": 0, "seconds": timeout, "timed_out": True}
    seconds = round(time.monotonic() - started, 2)
    root = ET.parse(junit_path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total = int(suite.get("tests", 0))
    failed = sum(int(suite.get(key, 0)) for key in ("failures", "errors", "skipped"))
    return {"total": total, "passed": total - failed, "seconds": seconds, "timed_out": False}


def score_branch(repo, base, branch, timeout):
    merge_base = git(repo, "merge-base", base, branch).strip()
    base_files = git(repo, "ls-tree", "-r", "--name-only", merge_base).splitlines()
    test_files = [path for path in base_files if RUNNABLE_TEST.search(path)]
    if not test_files:
        raise SystemExit(f"No test files found at {base}")

    changes = []
    for line in git(repo, "diff", "--no-renames", "--name-status", merge_base, branch).splitlines():
        status, path = line.split("\t", 1)
        changes.append((status[0], path))

    added = deleted = 0
    for line in git(repo, "diff", "--no-renames", "--numstat", merge_base, branch).splitlines():
        plus, minus, _ = line.split("\t", 2)
        added += int(plus) if plus != "-" else 0
        deleted += int(minus) if minus != "-" else 0

    flags = find_cheats(repo, merge_base, branch, changes)

    with tempfile.TemporaryDirectory(prefix="gauntlet-") as temp_dir:
        worktree = Path(temp_dir) / "worktree"
        git(repo, "worktree", "add", "--quiet", "--detach", str(worktree), branch)
        try:
            for status, path in changes:
                if TEST_FILE.search(path) or CONFIG_FILE.search(path):
                    if path in base_files:
                        git(worktree, "checkout", "--quiet", merge_base, "--", path)
                    elif CONFIG_FILE.search(path):
                        (worktree / path).unlink(missing_ok=True)
            tests = run_tests(worktree, test_files, Path(temp_dir) / "junit.xml", timeout)
        finally:
            git(repo, "worktree", "remove", "--force", str(worktree))

    all_passed = tests["total"] > 0 and tests["passed"] == tests["total"]
    verdict = "DISQUALIFIED" if flags else "PASS" if all_passed else "FAIL"
    return {
        "branch": branch,
        "verdict": verdict,
        "tests_passed": tests["passed"],
        "tests_total": tests["total"],
        "timed_out": tests["timed_out"],
        "lines_added": added,
        "lines_deleted": deleted,
        "files_touched": len(changes),
        "test_seconds": tests["seconds"],
        "flags": flags,
    }


def scoreboard(results):
    lines = [
        "**Gauntlet scoreboard**",
        "",
        "| Agent | Verdict | Tests | Diff | Files | Test time |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        tests = "timed out" if r["timed_out"] else f"{r['tests_passed']}/{r['tests_total']}"
        lines.append(
            f"| {r['branch']} | {r['verdict']} | {tests} | "
            f"+{r['lines_added']} -{r['lines_deleted']} | {r['files_touched']} | {r['test_seconds']}s |"
        )
    for r in results:
        for flag in r["flags"]:
            lines += ["", f"**{r['branch']}: {flag['reason']}** (`{flag['file']}`)"]
            if flag["evidence"]:
                lines += ["```diff", *flag["evidence"], "```"]
    passing = [r for r in results if r["verdict"] == "PASS"]
    lines.append("")
    if passing:
        size = lambda r: r["lines_added"] + r["lines_deleted"]
        smallest = min(size(r) for r in passing)
        best = [r["branch"] for r in passing if size(r) == smallest]
        if len(best) == 1:
            lines.append(f"Smallest passing diff: **{best[0]}**. Type `ship it` to approve it.")
        else:
            lines.append(f"Tied for smallest passing diff: **{', '.join(best)}**. Type `ship it <agent>` to choose.")
    else:
        lines.append("No branch passed.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", default="main")
    parser.add_argument("--branches", nargs="+", required=True)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    results = [score_branch(repo, args.base, branch, args.timeout) for branch in args.branches]
    print(json.dumps(results, indent=2) if args.json else scoreboard(results))


if __name__ == "__main__":
    main()
