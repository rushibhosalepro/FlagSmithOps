#!/usr/bin/env python3
"""Copy shared scripts into each skill so every skill installs on its own.

  python shared/sync.py          copy
  python shared/sync.py --check  fail if a copy is out of date
"""
import filecmp
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHARED = os.path.join(ROOT, "shared", "scripts")
SKILLS = {
    "flag-cleanup": ["cli.py", "snapshot.py", "find_refs.py", "verdict.py", "evidence.py"],
}


def main():
    check = "--check" in sys.argv
    stale = []
    for skill, files in SKILLS.items():
        dest_dir = os.path.join(ROOT, "skills", skill, "scripts")
        os.makedirs(dest_dir, exist_ok=True)
        for name in files:
            src, dst = os.path.join(SHARED, name), os.path.join(dest_dir, name)
            if not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
                stale.append(os.path.relpath(dst, ROOT))
                if not check:
                    shutil.copyfile(src, dst)
    if check and stale:
        print("out of date:\n  " + "\n  ".join(stale))
        return 1
    print("copied %d file(s)" % len(stale) if not check else "all copies up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())