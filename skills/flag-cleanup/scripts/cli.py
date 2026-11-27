#!/usr/bin/env python3
"""Run the Flagsmith CLI with output metering and secret redaction.

Standard library only. Used by both FlagSmithOps skills.

  python cli.py run -- feature list --jq '.[].name'
  python cli.py meter
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

DEFAULT_METER = os.path.join(".fsops", "meter.jsonl")

_SECRETS = [
    re.compile(r"(FLAGSMITH_[A-Z0-9_]*KEY[A-Za-z0-9_]*\s*[=:]\s*)\S+"),
    re.compile(r"((?:Api-Key|Token|Bearer)\s+)\S+", re.I),
]


def read_text(path):
    """Read a text file an agent may have written on Windows: UTF-8, UTF-8 with BOM, or UTF-16 (PowerShell 5 `>`)."""
    import codecs
    with open(path, "rb") as handle:
        data = handle.read()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8")
    return data.decode("utf-8")


def redact(text):
    """Mask anything that looks like a Flagsmith credential."""
    for pattern in _SECRETS:
        text = pattern.sub(lambda m: m.group(1) + "[REDACTED]", text)
    return text


class CliError(Exception):
    """A CLI call failed or returned an unexpected shape. Show the message as is."""

    def __init__(self, message, cmd_args=None, returncode=None):
        super().__init__(message)
        self.cmd_args = cmd_args
        self.returncode = returncode


def _meter(path, record):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


_VALUE_FLAGS = {"-e", "--environment", "-p", "--project", "--organisation", "--api-url", "-c",
                "--config-path", "--jq", "--sdk-api-url"}


def _command_words(args):
    """The subcommand words (for example ['feature', 'delete', 'x']), skipping flags and their values."""
    words, skip = [], False
    for arg in (str(a) for a in args):
        if skip:
            skip = False
        elif arg in _VALUE_FLAGS:
            skip = True
        elif not arg.startswith("-"):
            words.append(arg)
    return words


def blocked_reason(args):
    """Why this call is never allowed, or None. FlagSmithOps never deletes, and `api` is read-only.

    This guards calls made through this wrapper. It cannot stop an agent that runs `flagsmith` directly,
    so the skills tell the agent to use this wrapper for every CLI call.
    """
    args = [str(a) for a in args]
    words = _command_words(args)
    if len(words) >= 2 and words[1] == "delete":
        return "'%s delete' is not allowed. FlagSmithOps archives and never deletes." % words[0]
    if words and words[0] == "api":
        method = None
        for i, arg in enumerate(args):
            if arg in ("-X", "--method"):
                method = args[i + 1] if i + 1 < len(args) else ""
            elif arg.startswith("--method="):
                method = arg.split("=", 1)[1]
            elif arg.startswith("-X") and len(arg) > 2:
                method = arg[2:]
        if method is not None and method.upper() != "GET":
            return "'api' is read-only here. Method %s is not allowed." % (method or "(empty)")
        for arg in args:
            if arg in ("-F", "--field", "-f", "--raw-field", "--input") or arg.startswith(("--field=", "--raw-field=", "--input=")):
                return "'api' is read-only here. Sending a request body is not allowed."
    return None


def disable_reason(args):
    """Why the agent-facing wrapper refuses this call, or None. Disables go through disable_gate.py."""
    words = _command_words(args)
    args = [str(a) for a in args]
    if words[:2] == ["flag", "disable"] or (words[:2] == ["flag", "update"] and "--disable" in args):
        return "disables must go through scripts/disable_gate.py, which validates the snapshot first"
    return None


def run(args, binary=None, meter_file=None, expect_json=True, timeout=120, gate=False):
    """Run `flagsmith <args>`. Returns parsed JSON (or text when expect_json is False).

    Always adds --no-input. Adds --json when expect_json and neither --json nor --jq is given.
    Raises CliError on a non-zero exit, a timeout, or output that is not JSON.
    """
    reason = blocked_reason(args) or (None if gate else disable_reason(args))
    if reason:
        _meter(meter_file or os.environ.get("FSOPS_METER_FILE", DEFAULT_METER),
               {"args": [redact(str(a)) for a in args], "exit": -1, "bytes": 0, "ms": 0, "blocked": True})
        raise CliError("blocked by FlagSmithOps: " + reason, args)
    cmd = list(binary or ["flagsmith"]) + [str(a) for a in args]
    if "--no-input" not in cmd:
        cmd.append("--no-input")
    if expect_json and "--json" not in cmd and "--jq" not in cmd:
        cmd.append("--json")
    meter_file = meter_file or os.environ.get("FSOPS_METER_FILE", DEFAULT_METER)
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout
        )
    except FileNotFoundError:
        raise CliError("flagsmith CLI not found on PATH. Install it first.", args)
    except subprocess.TimeoutExpired:
        raise CliError("flagsmith CLI timed out after %ss" % timeout, args)
    out, err = proc.stdout or "", proc.stderr or ""
    _meter(
        meter_file,
        {
            "args": [redact(str(a)) for a in args],
            "exit": proc.returncode,
            "bytes": len(out.encode("utf-8")),
            "ms": int((time.time() - started) * 1000),
        },
    )
    if proc.returncode != 0:
        detail = redact((err or out).strip())
        raise CliError("flagsmith exited %d: %s" % (proc.returncode, detail), args, proc.returncode)
    if not expect_json:
        return out
    try:
        return json.loads(out)
    except ValueError:
        if "--jq" in cmd:
            return out.strip()  # jq may print bare strings
        raise CliError("expected JSON from flagsmith, got: " + redact(out.strip()[:200]), args)


def meter_summary(path=None):
    path = path or os.environ.get("FSOPS_METER_FILE", DEFAULT_METER)
    summary = {"calls": 0, "failed": 0, "output_bytes": 0, "total_ms": 0}
    if not os.path.exists(path):
        return summary
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rec = json.loads(line)
            summary["calls"] += 1
            summary["failed"] += 1 if rec.get("exit") else 0
            summary["output_bytes"] += rec.get("bytes", 0)
            summary["total_ms"] += rec.get("ms", 0)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run a flagsmith command (put -- before its arguments)")
    run_p.add_argument("--text", action="store_true", help="do not add --json")
    run_p.add_argument("args", nargs=argparse.REMAINDER)
    meter_p = sub.add_parser("meter", help="print call count and output bytes")
    meter_p.add_argument("--file")
    ns = parser.parse_args(argv)
    if ns.command == "meter":
        print(json.dumps(meter_summary(ns.file)))
        return 0
    args = [a for a in ns.args if a != "--"]
    if not ns.text and "--json" not in args and "--jq" not in args:
        args.append("--json")
    try:
        sys.stdout.write(redact(run(args, expect_json=False)))
    except CliError as err:
        sys.stderr.write(str(err) + "\n")
        return 2
    return 0

 
if __name__ == "__main__":
    sys.exit(main())