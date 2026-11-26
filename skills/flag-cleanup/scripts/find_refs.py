#!/usr/bin/env python3
"""Find references to feature flags in source code.

Supported languages: JavaScript, TypeScript, Python (provisional).
Reports three things per flag:
  sdk_call       the flag name is the literal argument of a known SDK call
  other_literal  the flag name appears as a string literal anywhere else (config, tests, docs)
And repo-wide:
  dynamic_call_sites  SDK calls whose argument is not a string literal, so they may read any flag
  unsearched          files in languages this script does not search

  python find_refs.py --repo . --flag new_checkout --flag old_banner
"""
import argparse
import json
import os
import re
import sys

SUPPORTED = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py"}
UNSUPPORTED = {".go", ".java", ".kt", ".rb", ".php", ".cs", ".swift", ".dart", ".rs", ".scala", ".ex", ".exs"}
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__", ".next", ".fsops", "vendor"}
MAX_BYTES = 1_000_000

CALL_RE = re.compile(
    r"\b(hasFeature|isFeatureEnabled|getValue|getFeatureValue|getFlag|useFlags|"
    r"has_feature|is_feature_enabled|get_feature_value|get_flag|get_value)\s*\(\s*(?P<arg>[^\n]*)"
)
LIT_RE = re.compile(r"""(["'`])((?:(?!\1).)*)\1""")


def _call_names(arg):
    """Return (literal_names, is_dynamic) for the text after an SDK call's '('."""
    text = arg.lstrip()
    if text.startswith("["):
        inner = text[1:].split("]", 1)[0]
        lits = [m.group(2) for m in LIT_RE.finditer(inner)]
        return lits, not lits
    match = LIT_RE.match(text)
    if match and "${" not in match.group(2):
        return [match.group(2)], False
    return [], True


def _walk(repo):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            yield os.path.join(root, name), os.path.splitext(name)[1].lower()


def scan(repos, flags):
    result = {
        "repos": [os.path.abspath(r) for r in repos],
        "files_searched": 0,
        "flags": {f: {"references": [], "summary": {"sdk_calls": 0, "other_literals": 0}} for f in flags},
        "dynamic_call_sites": [],
        "unsearched": {},
    }
    for repo in repos:
        for path, ext in _walk(repo):
            rel = os.path.relpath(path, repo).replace("\\", "/")
            label = "%s:%s" % (os.path.basename(os.path.abspath(repo)), rel)
            if ext in UNSUPPORTED:
                result["unsearched"][ext] = result["unsearched"].get(ext, 0) + 1
                continue
            if ext not in SUPPORTED or os.path.getsize(path) > MAX_BYTES:
                continue
            result["files_searched"] += 1
            with open(path, encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    sdk_names = set()
                    for call in CALL_RE.finditer(line):
                        names, dynamic = _call_names(call.group("arg"))
                        sdk_names.update(names)
                        if dynamic:
                            result["dynamic_call_sites"].append(
                                {"file": label, "line": number, "text": line.strip()[:120]}
                            )
                    seen = set()
                    for lit in LIT_RE.finditer(line):
                        name = lit.group(2)
                        if name in result["flags"] and name not in seen:
                            seen.add(name)
                            kind = "sdk_call" if name in sdk_names else "other_literal"
                            result["flags"][name]["references"].append(
                                {"file": label, "line": number, "kind": kind, "text": line.strip()[:120]}
                            )
                            key = "sdk_calls" if kind == "sdk_call" else "other_literals"
                            result["flags"][name]["summary"][key] += 1
    result["dynamic_call_sites_count"] = len(result["dynamic_call_sites"])
    result["unsearched_languages"] = sorted(result["unsearched"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", action="append", required=True, help="repository path (repeatable)")
    parser.add_argument("--flag", action="append", required=True, help="flag name (repeatable)")
    parser.add_argument("--summary", action="store_true", help="compact text: counts and the first references")
    ns = parser.parse_args(argv)
    for repo in ns.repo:
        if not os.path.isdir(repo):
            sys.stderr.write("not a directory: %s\n" % repo)
            return 2
    result = scan(ns.repo, ns.flag)
    if ns.summary:
        print(summary_text(result))
    else:
        print(json.dumps(result, indent=2))
    return 0


def summary_text(result, limit=5):
    lines = ["files searched: %d" % result["files_searched"]]
    for name, info in result["flags"].items():
        s = info["summary"]
        lines.append("%s: sdk_calls=%d other_literals=%d" % (name, s["sdk_calls"], s["other_literals"]))
        for ref in info["references"][:limit]:
            lines.append("  %s:%d [%s]" % (ref["file"], ref["line"], ref["kind"]))
        if len(info["references"]) > limit:
            lines.append("  ... %d more" % (len(info["references"]) - limit))
    lines.append("dynamic call sites: %d" % result["dynamic_call_sites_count"])
    for site in result["dynamic_call_sites"][:limit]:
        lines.append("  %s:%d" % (site["file"], site["line"]))
    lines.append("unsearched languages: %s" % (", ".join(result["unsearched_languages"]) or "none"))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())