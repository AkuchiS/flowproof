#!/usr/bin/env python3
"""
FlowProof — verify & certify that n8n workflow templates import cleanly.

  flowproof check    <file|->  [--json]        Diagnose import-breakers (exit 2 = not importable)
  flowproof verify   <file|->  [--json]        Pass/fail import-fidelity verdict (exit 2 = fail)
  flowproof fix      <file|->  [-o OUT] [--json] Write a clean, import-ready copy (+ change log)
  flowproof certify  <file|->  [--md] [-o OUT]   Emit a verification certificate (proof-of-run)
  flowproof selftest                            Run built-in self-tests (exit 0 = all pass)

Reads a file path or '-' for stdin. Handles a single workflow, an n8n "export
all" array, or a {workflows:[...]} wrapper. Pure Python 3.8+, offline, no deps,
no network, no API keys.
"""
import argparse
import json
import sys

from flowproof import (
    diagnose, repair, certify, render_markdown, verify,
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
    return worst


def cmd_fix(args):
    wfs = _load(args.file)
    cleaned = []
    for wf in wfs:
        clean, changes = repair(wf)
        cleaned.append(clean)
        if not args.json:
            sys.stderr.write(f"# {workflow_name(wf)} — {len(changes)} change(s):\n")
            for c in changes:
                sys.stderr.write(f"  - {c}\n")
    payload = cleaned if len(cleaned) > 1 else cleaned[0]
    text = json.dumps(payload, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        sys.stderr.write(f"# wrote clean workflow -> {args.out}\n")
    else:
        print(text)
    return 0


def cmd_certify(args):
    wfs = _load(args.file)
    certs = [certify(wf) for wf in wfs]
    worst = 0
    for c in certs:
        if c["verdict"] == "FAIL":
            worst = 2
    if args.md:
        rendered = "\n\n---\n\n".join(render_markdown(c) for c in certs)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(rendered + "\n")
            sys.stderr.write(f"# wrote certificate -> {args.out}\n")
        else:
            print(rendered)
    else:
        payload = certs if len(certs) > 1 else certs[0]
        text = json.dumps(payload, indent=2)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            sys.stderr.write(f"# wrote certificate -> {args.out}\n")
        else:
            print(text)
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

    f = sub.add_parser("fix", help="write a clean, import-ready copy")
    f.add_argument("file", nargs="?", default="-")
    f.add_argument("-o", "--out", default=None)
    f.add_argument("--json", action="store_true",
                   help="suppress the human change-log on stderr")
    f.set_defaults(func=cmd_fix)

    ce = sub.add_parser("certify", help="emit a verification certificate")
    ce.add_argument("file", nargs="?", default="-")
    ce.add_argument("--md", action="store_true", help="render Markdown instead of JSON")
    ce.add_argument("-o", "--out", default=None)
    ce.set_defaults(func=cmd_certify)

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
