#!/usr/bin/env python3
"""Check a skill folder against the Agent Skills format (https://agentskills.io/specification).

  python shared/validate_skill.py skills/flag-cleanup
"""
import os
import re
import sys


def validate(path):
    errors = []
    skill_md = os.path.join(path, "SKILL.md")
    if not os.path.isfile(skill_md):
        return ["SKILL.md is missing"]
    with open(skill_md, encoding="utf-8") as handle:
        text = handle.read()
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not match:
        return ["SKILL.md has no YAML frontmatter"]
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    name = fields.get("name", "")
    if not name:
        errors.append("name is required")
    else:
        if len(name) > 64:
            errors.append("name is longer than 64 characters")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            errors.append("name must be lowercase letters, numbers and single hyphens")
        if name != os.path.basename(os.path.abspath(path)):
            errors.append("name must match the folder name")
    desc = fields.get("description", "")
    if not desc:
        errors.append("description is required")
    elif len(desc) > 1024:
        errors.append("description is longer than 1024 characters")
    if len(fields.get("compatibility", "")) > 500:
        errors.append("compatibility is longer than 500 characters")
    unknown = set(fields) - {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    if unknown:
        errors.append("unknown frontmatter fields: " + ", ".join(sorted(unknown)))
    return errors


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    errors = validate(sys.argv[1])
    for e in errors:
        print("ERROR: " + e)
    print("valid" if not errors else "invalid")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())