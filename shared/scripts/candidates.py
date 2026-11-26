#!/usr/bin/env python3
"""Rank the feature flags most likely behind an incident.

Evidence per flag (deterministic, no guessing):
  name match    an incident keyword appears in the flag name           +3
  code match    an incident keyword appears in a file path or line
                that references the flag                                +2
  recent change a git commit in the last N days added or removed
                the flag name                                           +1

`clear_winner` is true only when the top flag scores at least 3 and leads the next by at least 2.
Otherwise the agent must stop and ask a human to choose.

  python candidates.py --repo . --keyword checkout --keyword payment --flags-file .fsops/flags.txt
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_refs  # noqa: E402


def recent_commits(repo, flag, since_days):
    """Number of commits in the window that add or remove the flag name, or None if git cannot say."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo, "log", "--since=%d days ago" % since_days, "-S" + flag, "--oneline"],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def rank(repo, flags, keywords, since_days=30, git=recent_commits):
    kws = [k.lower() for k in keywords if k.strip()]
    refs = find_refs.scan([repo], flags)
    candidates = []
    for flag in flags:
        info = refs["flags"][flag]
        name_hits = [k for k in kws if k in flag.lower()]
        code_hits = set()
        for ref in info["references"]:
            haystack = (ref["file"] + " " + ref["text"]).lower()
            code_hits.update(k for k in kws if k in haystack)
        recent = git(repo, flag, since_days)
        if not (name_hits or code_hits):
            continue  # recent change alone does not tie a flag to this incident
        score = 3 * bool(name_hits) + 2 * bool(code_hits) + (1 if recent else 0)
        evidence = []
        if name_hits:
            evidence.append("name contains: " + ", ".join(name_hits))
        if code_hits:
            evidence.append("code mentions: %s (%d reference(s))" % (", ".join(sorted(code_hits)), len(info["references"])))
        if recent:
            evidence.append("%d commit(s) in the last %d days touch the flag name" % (recent, since_days))
        if recent is None:
            evidence.append("git history unavailable")
        candidates.append({"flag": flag, "score": score, "evidence": evidence})
    candidates.sort(key=lambda c: (-c["score"], c["flag"]))
    clear = bool(candidates) and candidates[0]["score"] >= 3 and (
        len(candidates) == 1 or candidates[0]["score"] - candidates[1]["score"] >= 2
    )
    return {
        "candidates": candidates,
        "clear_winner": clear,
        "winner": candidates[0]["flag"] if clear else None,
        "flags_checked": len(flags),
        "dynamic_call_sites": refs["dynamic_call_sites_count"],
        "unsearched_languages": refs["unsearched_languages"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--keyword", action="append", required=True)
    parser.add_argument("--flags-file", required=True, help="one flag name per line")
    parser.add_argument("--since-days", type=int, default=30)
    ns = parser.parse_args(argv)
    if not os.path.isdir(ns.repo):
        sys.stderr.write("not a directory: %s\n" % ns.repo)
        return 2
    with open(ns.flags_file, encoding="utf-8") as handle:
        flags = [line.strip() for line in handle if line.strip()]
    print(json.dumps(rank(ns.repo, flags, ns.keyword, ns.since_days), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())