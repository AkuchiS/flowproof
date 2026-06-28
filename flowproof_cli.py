#!/usr/bin/env python3
"""
FlowProof — verify that n8n workflow templates import cleanly (free, offline check).

  flowproof check    <file|->  [--json]   Diagnose import-breakers (exit 2 = not importable)
  flowproof verify   <file|->  [--json]   Pass/fail import-fidelity verdict (exit 2 = fail)
  flowproof selftest                       Run built-in self-tests (exit 0 = all pass)

Reads a file path or '-' for stdin. Handles a single workflow, an n8n "export
all" array, or a {workflows:[...]} wrapper. Pure Python 3.8+, offline, no deps,
no network, no API keys.

Need the repaired, import-ready file + a content-hashed "FlowProof Checked"
certificate + client handover? That's FlowProof Pro: https://fp.akuchis.com
"""
import argparse
import json
import sys

from flowproof import (
    diagnose, verify,
    load_text, WorkflowLoadError, __version__,
)
from flowproof.loader import workflow_name
import flowproof


def _read(arg):
    if arg in (None, "-"):
        return sys.stdin.read()
    with open(arg, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _load(arg):
    try:
        return load_text(_read(arg))
    except (WorkflowLoadError, FileNotFoundError) as e:
        sys.stderr.write(f"error: {e}\n")
        sys.exit(64)


SEV_ICON = {"critical": "✖", "high": "✖", "med": "▲", "low": "·", "info": "·"}

PRO_URL = "https://fp.akuchis.com"


def _pro_nudge(has_problems):
    """A short, contextual FlowProof Pro upsell, printed once after the human
    report. Never shown in --json mode or selftest, so machine output stays clean."""
    if has_problems:
        print(
            f"\n  ⚡ Don't fix these by hand — FlowProof Pro repairs the workflow into an"
            f"\n     import-ready file and hands you a content-hashed “FlowProof Checked”"
            f"\n     certificate + client handover.  →  {PRO_URL}")
    else:
        print(
            f"\n  ✓ Clean import. Selling or shipping this to a client? FlowProof Pro adds"
            f"\n     a “FlowProof Checked” certificate + handover so they trust it on sight."
            f"\n     →  {PRO_URL}")


def _print_report(rep, name):
    verdict = "IMPORTABLE" if rep["importable"] else "NOT IMPORTABLE"
    print(f"\n┌─ {name}")
    print(f"│  {verdict}  ·  fidelity {rep['fidelity_score']}/100  ·  "
          f"{rep['node_count']} nodes  ·  {rep['blocker_count']} blocker(s)  ·  "
          f"{rep['manual_step_count']} manual step(s)")
    if rep["community_packages"]:
        print(f"│  community packages required: {', '.join(rep['community_packages'])}")
    if not rep["issues"]:
        print("│  ✓ no issues found")
    for i in rep["issues"]:
        icon = SEV_ICON.get(i["sev"], "·")
        tag = "[SETUP]" if i["kind"] == "manual" else f"[{i['sev'].upper()}]"
        where = f" ({i['node']})" if i["node"] else ""
        print(f"│  {icon} {tag} {i['id']}{where}: {i['msg']}")
        if i.get("fix"):
            print(f"│        ↳ fix: {i['fix']}")
    print("└─")


def cmd_check(args):
    wfs = _load(args.file)
    worst = 0
    out = []
    for wf in wfs:
        rep = diagnose(wf)
        out.append(rep)
        if args.json is False:
            _print_report(rep, workflow_name(wf))
        worst = max(worst, 2 if not rep["importable"] else 0)
    if args.json:
        print(json.dumps(out if len(out) > 1 else out[0], indent=2))
    else:
        _pro_nudge(any((not r["importable"]) or r["blocker_count"] for r in out))
    return worst


def cmd_verify(args):
    wfs = _load(args.file)
    worst = 0
    out = []
    for wf in wfs:
        v = verify(wf)
        v["workflow"] = workflow_name(wf)
        out.append(v)
        if not args.json:
            mark = "PASS" if v["importable"] else "FAIL"
            print(f"[{mark}] {v['workflow']}  fidelity={v['fidelity_score']}/100  "
                  f"blockers={len(v['blockers'])}  manual_steps={v['manual_steps']}")
            for b in v["blockers"]:
                where = f" ({b['node']})" if b["node"] else ""
                print(f"    ✖ {b['id']}{where}: {b['msg']}")
        if not v["importable"]:
            worst = 2
    if args.json:
        print(json.dumps(out if len(out) > 1 else out[0], indent=2))
    else:
        _pro_nudge(any((not v["importable"]) or v["blockers"] for v in out))
    return worst


def build_parser():
    p = argparse.ArgumentParser(
        prog="flowproof", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"FlowProof {__version__}")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="diagnose import-breakers")
    c.add_argument("file", nargs="?", default="-")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)

    v = sub.add_parser("verify", help="pass/fail import-fidelity verdict")
    v.add_argument("file", nargs="?", default="-")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("selftest", help="run built-in self-tests")
    s.set_defaults(func=lambda a: flowproof.selftest())
    return p


def main(argv):
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

