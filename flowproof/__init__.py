"""FlowProof — verify & certify n8n workflow templates import cleanly."""
from __future__ import annotations

from .diagnostics import diagnose
from .repair import repair
from .certify import certify, render_markdown
from .loader import load_file, load_text, extract_workflows, sha256_of, WorkflowLoadError

__version__ = "1.0.0"
__all__ = [
    "diagnose", "repair", "certify", "render_markdown",
    "load_file", "load_text", "extract_workflows", "sha256_of",
    "WorkflowLoadError", "verify", "__version__",
]


def verify(wf: dict) -> dict:
    """Convenience: is this workflow structurally import-clean? (no auto-repair)

    Returns {"importable": bool, "blockers": [...], "manual_steps": int,
             "fidelity_score": int}.
    """
    rep = diagnose(wf)
    return {
        "importable": rep["importable"],
        "blockers": [
            {"id": i["id"], "node": i["node"], "msg": i["msg"]}
            for i in rep["issues"]
            if i["kind"] == "blocker" and i["sev"] in ("critical", "high")
        ],
        "manual_steps": rep["manual_step_count"],
        "fidelity_score": rep["fidelity_score"],
    }


# --------------------------------------------------------------------------- #
# Self-test fixtures + runner
# --------------------------------------------------------------------------- #

# A deliberately BROKEN export: dangling edge, duplicate name, hard-coded secret,
# embedded credential data, deprecated node, version drift, community node, pinData.
_BROKEN = {
    "name": "Broken Demo",
    "active": True,
    "versionId": "abc-123",
    "nodes": [
        {"name": "Start", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
         "position": [0, 0], "parameters": {}},
        {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "typeVersion": 2,
         "position": [200, 0],
         "parameters": {"url": "https://api.example.com", "apiKey": "sk-live-9f8a7b6c5d4e3f2a1b0c"},
         "credentials": {"httpHeaderAuth": {"id": "7", "name": "My Header Auth", "data": {"value": "topsecret"}}}},
        {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "typeVersion": 2,
         "position": [200, 0], "parameters": {}},  # duplicate name
        {"name": "OldCode", "type": "n8n-nodes-base.function", "typeVersion": 1,
         "position": [400, 0], "parameters": {"functionCode": "return items;"}},
        {"name": "Discord", "type": "n8n-nodes-discord.discord", "typeVersion": 1,
         "position": [600, 0], "parameters": {}},
    ],
    "connections": {
        "Start": {"main": [[{"node": "HTTP", "type": "main", "index": 0}]]},
        "HTTP": {"main": [[{"node": "GhostNode", "type": "main", "index": 0}]]},  # dangling
    },
    "pinData": {"HTTP": [{"json": {"sample": "leaked test data"}}]},
}

# A CLEAN, well-built export: unique names, no secrets, current versions, edges valid.
_CLEAN = {
    "name": "Clean Demo",
    "active": False,
    "nodes": [
        {"name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
         "position": [0, 0], "parameters": {}},
        {"name": "Fetch", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
         "position": [280, 0], "parameters": {"url": "https://api.example.com/items"}},
        {"name": "Shape", "type": "n8n-nodes-base.set", "typeVersion": 3.4,
         "position": [560, 0], "parameters": {"assignments": {"assignments": []}}},
    ],
    "connections": {
        "Schedule": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
        "Fetch": {"main": [[{"node": "Shape", "type": "main", "index": 0}]]},
    },
    "pinData": {},
    "settings": {},
}


def selftest() -> int:
    print("=== FlowProof self-test ===")
    fails = 0

    def check(label, cond):
        nonlocal fails
        ok = bool(cond)
        fails += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")

    # 1. broken workflow is detected as NOT importable
    d = diagnose(_BROKEN)
    ids = {i["id"] for i in d["issues"]}
    check("broken: flagged not importable", d["importable"] is False)
    check("broken: detects dangling_target", "dangling_target" in ids)
    check("broken: detects duplicate_name", "duplicate_name" in ids)
    check("broken: detects hardcoded_secret", "hardcoded_secret" in ids)
    check("broken: detects embedded_credential", "embedded_credential" in ids)
    check("broken: detects deprecated_node (function)", "deprecated_node" in ids)
    check("broken: detects version_ahead (httpRequest v2<-? )" , "deprecated_syntax" in ids)
    check("broken: detects community_node (discord)", "community_node" in ids)
    check("broken: lists discord community package",
          "n8n-nodes-discord" in d["community_packages"])

    # 2. clean workflow passes
    c = diagnose(_CLEAN)
    check("clean: importable", c["importable"] is True)
    check("clean: no blockers", c["blocker_count"] == 0)
    check("clean: high fidelity score", c["fidelity_score"] >= 90)

    # 3. repair makes the broken workflow importable + secret-free
    fixed, changes = repair(_BROKEN)
    rd = diagnose(fixed)
    rids = {i["id"] for i in rd["issues"]}
    check("repair: broken becomes importable", rd["importable"] is True)
    check("repair: secret removed", "hardcoded_secret" not in rids)
    check("repair: embedded credential removed", "embedded_credential" not in rids)
    check("repair: dangling edge removed", "dangling_target" not in rids)
    check("repair: duplicate name resolved", "duplicate_name" not in rids)
    check("repair: pinData stripped", not fixed.get("pinData"))
    check("repair: recorded changes", len(changes) >= 5)

    # 4. certificate reflects the verdict
    cert = certify(_BROKEN, timestamp="2026-01-01T00:00:00Z")
    check("certify: broken -> PASS_WITH_SETUP after repair",
          cert["verdict"] in ("PASS_WITH_SETUP", "PASS"))
    check("certify: lists manual setup steps", len(cert["manual_steps"]) >= 1)
    check("certify: has content hash", len(cert["certified_sha256"]) == 64)
    check("certify: markdown renders", "VERIFIED" in render_markdown(cert))

    cert_clean = certify(_CLEAN, timestamp="2026-01-01T00:00:00Z")
    check("certify: clean -> PASS", cert_clean["verdict"] == "PASS")

    print(f"--- self-test complete: {fails} failure(s) ---")
    return 1 if fails else 0
