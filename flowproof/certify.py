"""
FlowProof — certify
==================
Turn a diagnosis + repair into a portable *verification certificate*: the
proof-of-run artifact a seller ships alongside a template so a buyer can trust it
imports cleanly. This is the thing un-vetted reseller bundles never include.

    from flowproof.certify import certify, render_markdown
    cert = certify(workflow_dict)
    print(render_markdown(cert))

The certificate records what was checked, the verdict, the content hash of the
cleaned workflow, and the exact manual setup steps (credentials to re-link,
community packages to install). Offline and deterministic by default.

IMPROVE CYCLE 2026-06-12 (Jay-bounded, QC pack 1):
  * Verdicts split: PASS / PASS_WITH_SETUP / NEEDS_SETUP / FAIL_IMPORT.
    "FAIL" no longer exists — it conflated import-breaking with runtime setup
    (proven against a live n8n: one FAIL was import-rejected, another imported
    fine). Marketing may cite ONLY FAIL_IMPORT for "breaks on import" claims.
  * Live n8n import check wired in as the ARBITER for import claims. Opt-in via
    env (FLOWPROOF_N8N_URL + FLOWPROOF_N8N_API_KEY); without it, certify stays
    fully offline and marks import verdicts as statically-derived (unarbitrated).
"""
from __future__ import annotations
import json as _json
import os as _os
import urllib.error as _uerr
import urllib.request as _ureq
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .diagnostics import diagnose
from .repair import repair
from .loader import sha256_of, workflow_name

TOOL = "FlowProof"
VERSION = "1.1.0"

# Verification dimensions and the issue ids that, if present (as blockers),
# fail that dimension.
CHECKS = [
    ("structure", "Graph integrity (no broken edges, unique node names, valid fields)",
     {"dangling_target", "dangling_source", "duplicate_name", "missing_name",
      "missing_type", "missing_position", "no_nodes", "bad_node"}),
    ("security", "No embedded credentials or hard-coded secrets",
     {"embedded_credential", "hardcoded_secret"}),
    ("version_integrity", "No version drift or deprecated nodes/syntax",
     {"version_ahead", "deprecated_node", "deprecated_syntax", "no_typeversion"}),
    ("node_availability", "All nodes resolvable (bundled, or community deps listed)",
     {"unknown_node"}),
]

# Issue ids that STRUCTURALLY break an n8n import (vs. issues a live n8n will
# accept on import but that need setup/attention before the workflow runs).
# Ground-truthed 2026-06-12 against a live n8n import API.
IMPORT_BREAKING_IDS = {
    "dangling_target", "dangling_source", "duplicate_name", "missing_name",
    "missing_type", "no_nodes", "bad_node", "unknown_node",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _live_import_check(clean_wf: dict, timeout: int = 20) -> Optional[bool]:
    """ARBITER: attempt a real import into a live n8n instance, then delete it.
    Returns True (imports), False (rejected), or None (arbiter not configured /
    unreachable — stay offline). Creates the workflow INACTIVE and deletes it
    immediately; never executes anything."""
    url = _os.environ.get("FLOWPROOF_N8N_URL", "").rstrip("/")
    key = _os.environ.get("FLOWPROOF_N8N_API_KEY", "")
    if not url or not key:
        return None
    body = {"name": "FLOWPROOF-CERTIFY-GROUNDTRUTH-DELETE-ME",
            "nodes": clean_wf.get("nodes") or [],
            "connections": clean_wf.get("connections") or {},
            "settings": {}}
    req = _ureq.Request(url + "/api/v1/workflows",
                        data=_json.dumps(body).encode(),
                        headers={"X-N8N-API-KEY": key,
                                 "Content-Type": "application/json"})
    try:
        with _ureq.urlopen(req, timeout=timeout) as r:
            wid = _json.loads(r.read().decode()).get("id")
        if wid:  # clean up immediately
            dreq = _ureq.Request("%s/api/v1/workflows/%s" % (url, wid),
                                 method="DELETE",
                                 headers={"X-N8N-API-KEY": key})
            try:
                _ureq.urlopen(dreq, timeout=timeout).read()
            except Exception:
                pass
        return True
    except _uerr.HTTPError as e:
        if 400 <= e.code < 500:
            return False  # the instance REJECTED the import
        return None  # server-side problem — not evidence about the workflow
    except Exception:
        return None  # unreachable — not evidence


def certify(wf: dict, *, timestamp: str = None) -> Dict:
    """Diagnose -> repair -> re-diagnose -> emit a verification certificate."""
    before = diagnose(wf)
    clean, changes = repair(wf)
    after = diagnose(clean)

    after_blockers = [i for i in after["issues"]
                      if i["kind"] == "blocker" and i["sev"] in ("critical", "high")]

    checks: List[Dict] = []
    for key, desc, ids in CHECKS:
        failing = [i for i in after_blockers if i["id"] in ids]
        checks.append({
            "check": key,
            "description": desc,
            "passed": len(failing) == 0,
            "findings": len(failing),
        })

    # Manual setup steps the buyer must perform (expected, not failures).
    creds = [i for i in after["issues"] if i["id"] == "dangling_credential"]
    drift = [i for i in after["issues"] if i["id"] == "unknown_version"]
    manual_steps = []
    if after["community_packages"]:
        for pkg in after["community_packages"]:
            manual_steps.append(f"Install community package: npm i {pkg} "
                                f"(or via n8n Settings > Community Nodes)")
    if creds:
        manual_steps.append(f"Re-select {len(creds)} credential(s) after import "
                            f"(template ships credential *names*, not secrets)")
    if drift:
        manual_steps.append(f"Review {len(drift)} node(s) with versions unknown to the "
                            f"knowledge base (may be newer than your n8n)")

    import_breakers = [i for i in after_blockers if i["id"] in IMPORT_BREAKING_IDS]
    setup_blockers = [i for i in after_blockers if i["id"] not in IMPORT_BREAKING_IDS]

    # ---- verdict (4-way split, 2026-06-12) --------------------------------
    # When the live arbiter is configured it arbitrates EVERY certificate, so
    # FAIL_IMPORT is definitionally identical to "a live n8n rejected it".
    # Without the arbiter, FAIL_IMPORT can only come from structural breakers
    # and is marked statically-derived.
    live = _live_import_check(clean)
    ground_truth = {"arbitrated": live is not None, "import_ok": live}
    if live is False:
        verdict = "FAIL_IMPORT"
        summary = ("A live n8n instance REJECTED this import (ground-truth "
                   f"arbitrated). {len(after_blockers)} blocking issue(s) remain "
                   "after auto-repair.")
    elif import_breakers:
        if live is True:
            # The live instance accepted it — static analysis was too strict.
            verdict = "NEEDS_SETUP"
            summary = ("Live n8n ACCEPTED the import (ground-truth arbitrated), but "
                       f"{len(after_blockers)} issue(s) need attention before this "
                       "template can be certified runnable.")
        else:
            verdict = "FAIL_IMPORT"
            summary = (f"{len(import_breakers)} import-breaking issue(s) remain after "
                       "auto-repair (statically derived; no live arbiter configured).")
    elif setup_blockers:
        verdict = "NEEDS_SETUP"
        summary = (f"Imports, but {len(setup_blockers)} issue(s) need attention before "
                   "this template can be certified runnable.")
    elif manual_steps:
        verdict = "PASS_WITH_SETUP"
        summary = ("Imports cleanly. Runs after the listed one-time setup "
                   "(credentials / community nodes).")
    else:
        verdict = "PASS"
        summary = "Imports cleanly and is ready to run. No setup required."

    return {
        "tool": TOOL,
        "version": VERSION,
        "certified_at": timestamp or _utc_now(),
        "workflow": workflow_name(wf),
        "node_count": after["node_count"],
        "verdict": verdict,
        "summary": summary,
        "ground_truth": ground_truth,
        "fidelity_score": after["fidelity_score"],
        "importable": after["importable"],
        "source_sha256": sha256_of(wf),
        "certified_sha256": sha256_of(clean),
        "checks": checks,
        "manual_steps": manual_steps,
        "repairs_applied": changes,
        "residual_blockers": [
            {"id": i["id"], "node": i["node"], "msg": i["msg"]} for i in after_blockers
        ],
        "issues_before": before["counts"],
        "issues_after": after["counts"],
    }


def render_markdown(cert: Dict) -> str:
    badge = {"PASS": "✅ VERIFIED",
             "PASS_WITH_SETUP": "✅ VERIFIED (setup required)",
             "NEEDS_SETUP": "⚠️ IMPORTS — NEEDS SETUP (not yet certified runnable)",
             "FAIL_IMPORT": "❌ FAILS IMPORT",
             "FAIL": "❌ NOT VERIFIED"}.get(cert["verdict"], cert["verdict"])
    lines = [
        f"# {badge} — {cert['workflow']}",
        "",
        f"> {cert['summary']}",
        "",
        f"- **Tool:** {cert['tool']} v{cert['version']}",
        f"- **Certified at:** {cert['certified_at']}",
        f"- **Nodes:** {cert['node_count']}",
        f"- **Fidelity score:** {cert['fidelity_score']}/100",
        f"- **Imports cleanly:** {'yes' if cert['importable'] else 'no'}",
        f"- **Verified content hash (sha256):** `{cert['certified_sha256'][:16]}…`",
    ]
    gt = cert.get("ground_truth") or {}
    if gt.get("arbitrated"):
        lines.append(f"- **Ground truth (live n8n import):** "
                     f"{'ACCEPTED' if gt.get('import_ok') else 'REJECTED'}")
    lines += ["", "## Verification checks"]
    for c in cert["checks"]:
        mark = "✅" if c["passed"] else "❌"
        extra = "" if c["passed"] else f" ({c['findings']} finding(s))"
        lines.append(f"- {mark} **{c['check']}** — {c['description']}{extra}")
    if cert["manual_steps"]:
        lines += ["", "## One-time setup (buyer)"]
        lines += [f"{i}. {s}" for i, s in enumerate(cert["manual_steps"], 1)]
    if cert["residual_blockers"]:
        lines += ["", "## Issues to fix"]
        for b in cert["residual_blockers"]:
            where = f" [{b['node']}]" if b["node"] else ""
            lines.append(f"- **{b['id']}**{where}: {b['msg']}")
    lines += ["", f"*Generated by {cert['tool']} — n8n template import certification.*"]
    return "\n".join(lines)
