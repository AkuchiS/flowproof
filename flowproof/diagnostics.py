"""
FlowProof — diagnostics
=======================
Static analysis of an n8n workflow export that detects the *exact* failure modes
that make shared/sold templates break on import:

  * embedded credential secrets (security leak — must never ship)
  * dangling credential references (the "lost my credentials on import" pain)
  * missing / community nodes that aren't installed on the buyer's instance
  * version drift (typeVersion exported from a newer n8n than the importer runs)
  * deprecated nodes & deprecated parameter syntax (silent mis-mapping)
  * structural corruption (dangling connections, duplicate node names,
    missing required fields) that n8n imports but runs wrong

Heuristic, offline, zero-dependency. No network calls, no API keys.

    from flowproof.diagnostics import diagnose
    report = diagnose(workflow_dict)
"""
from __future__ import annotations
import re
from typing import Dict, List

from .known_nodes import (
    community_package,
    is_bundled,
    version_status,
    DEPRECATED_NODES,
)

# Severity weighting for the fidelity score.
SEV_WEIGHT = {"critical": 40, "high": 18, "med": 7, "low": 2, "info": 0}

# Severities that prevent a clean, correct import on a current n8n instance.
BLOCKING_SEV = ("critical", "high")

# Issue ids that are EXPECTED setup steps for any real template (n8n still
# imports them) — surfaced as "manual steps", never counted as import blockers.
MANUAL_IDS = {"community_node", "dangling_credential", "unknown_version"}  # improve1 2026-06-12: unknown_version downgraded to setup/manual unless live import fails

_SECRET_KEY = re.compile(
    r"^(api[_-]?key|apikey|access[_-]?token|token|secret|password|passwd|"
    r"private[_-]?key|client[_-]?secret|authorization|auth[_-]?token|bearer|"
    r"x[_-]?api[_-]?key|app[_-]?secret)$",
    re.I,
)
# Well-known secret token shapes — flagged wherever they appear, regardless of
# the surrounding key name (catches secrets stuffed in generic name/value pairs).
_SECRET_VALUE = re.compile(
    r"(sk-(?:live|proj|test|ant)?-?[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|"
    r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AIza[0-9A-Za-z\-_]{30,}|ya29\.[A-Za-z0-9\-_]{20,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)

# Obvious placeholders that are SAFE to ship (not real secrets).
_PLACEHOLDER = re.compile(
    r"^(|x{2,}|y{3,}|your[_\- ]?.*|<.*>|\{\{.*\}\}|=.*|changeme|todo|none|null|"
    r"placeholder|insert[_\- ].*|\.\.\.|sk-xxx.*)$",
    re.I,
)


def _is_expression(val: str) -> bool:
    # n8n expressions start with '=' or contain {{ }} — they resolve at runtime.
    return val.startswith("=") or ("{{" in val and "}}" in val)


def _looks_like_real_secret(value) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    if len(v) < 8:
        return False
    if _is_expression(v) or _PLACEHOLDER.match(v):
        return False
    # entropy-ish: a real secret has mixed alnum and few spaces
    if " " in v:
        return False
    return bool(re.search(r"[A-Za-z]", v) and re.search(r"[0-9A-Za-z\-_/+=]{8,}", v))


def _walk_params(obj, path=""):
    """Yield (dotted_path, key, value) for every scalar leaf in a params tree."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                yield from _walk_params(v, p)
            else:
                yield (p, k, v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{path}[{i}]"
            if isinstance(v, (dict, list)):
                yield from _walk_params(v, p)
            else:
                yield (p, None, v)


def _iter_connection_targets(connections: dict):
    """Yield (source_name, output_type, target_node) over a connections map."""
    if not isinstance(connections, dict):
        return
    for source, outputs in connections.items():
        if not isinstance(outputs, dict):
            continue
        for out_type, branches in outputs.items():
            if not isinstance(branches, list):
                continue
            for branch in branches:
                if not isinstance(branch, list):
                    continue
                for link in branch:
                    if isinstance(link, dict) and "node" in link:
                        yield (source, out_type, link["node"])


def diagnose(wf: dict) -> Dict:
    """Run all checks against one workflow dict. Returns a structured report."""
    issues: List[Dict] = []

    def add(iid, sev, msg, node=None, fix=None):
        issues.append({"id": iid, "sev": sev, "msg": msg, "node": node, "fix": fix})

    nodes = wf.get("nodes")
    if not isinstance(nodes, list):
        add("no_nodes", "critical", "workflow has no 'nodes' array — not a valid n8n export")
        return _finalize(wf, issues, names=[], community=set())

    names: List[str] = []
    seen_names = set()
    community: set = set()

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            add("bad_node", "high", f"nodes[{idx}] is not an object")
            continue
        name = node.get("name")
        ntype = node.get("type")
        label = name or ntype or f"nodes[{idx}]"

        # --- required fields (import / run integrity) ---
        if not name or not isinstance(name, str):
            add("missing_name", "high", "node is missing a string 'name'", node=label,
                fix="give every node a unique name")
        else:
            if name in seen_names:
                add("duplicate_name", "critical",
                    f"duplicate node name {name!r} — n8n keys connections by name, "
                    f"so duplicates silently merge/drop edges on import", node=name,
                    fix="rename to make every node name unique")
            seen_names.add(name)
            names.append(name)
        if not ntype or not isinstance(ntype, str):
            add("missing_type", "critical", "node has no 'type'", node=label)
            continue
        pos = node.get("position")
        if not (isinstance(pos, list) and len(pos) == 2):
            add("missing_position", "med",
                "node has no valid 'position' [x,y] (renders stacked at 0,0)", node=label,
                fix="set a [x,y] position")

        # --- node availability (missing / community) ---
        if not is_bundled(ntype):
            pkg = community_package(ntype)
            if pkg:
                community.add(pkg)
                add("community_node", "med",
                    f"uses community node {ntype!r} from package '{pkg}' — buyer must "
                    f"`npm i {pkg}` / install it or the import shows a broken node",
                    node=label, fix=f"document & pin community package '{pkg}'")
            else:
                add("unknown_node", "high",
                    f"unrecognized node type {ntype!r} (not a bundled or community pattern)",
                    node=label)

        # --- deprecated node ---
        if ntype in DEPRECATED_NODES:
            add("deprecated_node", "med",
                f"node type {ntype!r} is deprecated — migrate to "
                f"{DEPRECATED_NODES[ntype]!r}", node=label,
                fix=f"replace with {DEPRECATED_NODES[ntype]}")

        # --- version drift / deprecated syntax ---
        status, vmsg = version_status(ntype, node.get("typeVersion"))
        if status == "ahead":
            add("version_ahead", "high", vmsg, node=label,
                fix="re-export from the n8n version you support, or pin a minimum n8n")
        elif status == "deprecated_syntax":
            add("deprecated_syntax", "med", vmsg, node=label)
        elif status == "missing":
            add("no_typeversion", "low", vmsg, node=label,
                fix="set typeVersion explicitly")
        elif status == "unknown_version":
            add("unknown_version", "info", vmsg + f" ({ntype})", node=label)

        # --- credentials: dangling refs + embedded secret leak ---
        creds = node.get("credentials")
        if isinstance(creds, dict):
            for ctype, ref in creds.items():
                if isinstance(ref, dict):
                    extra = set(ref) - {"id", "name"}
                    if extra:
                        add("embedded_credential", "critical",
                            f"credential {ctype!r} embeds raw fields {sorted(extra)} — "
                            f"this leaks secrets if shipped", node=label,
                            fix="strip embedded credential data; export only id+name")
                    add("dangling_credential", "med",
                        f"credential {ctype!r} (name="
                        f"{ref.get('name', '?')!r}) is referenced by id "
                        f"{ref.get('id', '?')!r} that won't exist on the buyer's "
                        f"instance — they must re-select it after import", node=label,
                        fix="ship a credential-setup step; keep the name as a stable label")
                else:
                    add("dangling_credential", "med",
                        f"credential {ctype!r} reference is malformed", node=label)

        # --- embedded secrets baked into parameters ---
        for ppath, key, value in _walk_params(node.get("parameters", {})):
            keyname = (key or ppath.split(".")[-1].split("[")[0])
            by_key = _SECRET_KEY.match(str(keyname)) and _looks_like_real_secret(value)
            by_shape = isinstance(value, str) and _SECRET_VALUE.search(value)
            if by_key or by_shape:
                add("hardcoded_secret", "critical",
                    f"parameter '{ppath}' looks like a hard-coded secret — never "
                    f"ship this; move it to a credential or $env", node=label,
                    fix=f"replace value with an n8n expression / credential")

    # --- structural integrity: connections ---
    name_set = set(names)
    connections = wf.get("connections", {})
    dangling_targets = 0
    for source, out_type, target in _iter_connection_targets(connections):
        if source not in name_set:
            add("dangling_source", "high",
                f"connections reference source node {source!r} that does not exist",
                node=source)
        if target not in name_set:
            dangling_targets += 1
            add("dangling_target", "critical",
                f"connection {source!r} -> {target!r} points to a node that does not "
                f"exist — edge is dropped on import (broken flow)", node=source,
                fix="remove the dangling connection or restore the missing node")

    # --- orphans (info only) ---
    connected = set()
    for source, _t, target in _iter_connection_targets(connections):
        connected.add(source)
        connected.add(target)
    for n in names:
        node_obj = next((x for x in nodes if isinstance(x, dict) and x.get("name") == n), {})
        ntype = node_obj.get("type", "")
        is_trigger = "trigger" in ntype.lower() or ntype.endswith((".start", ".manualTrigger", ".webhook"))
        if n not in connected and not is_trigger:
            add("orphan_node", "low",
                f"node {n!r} has no connections (dead/unused in the flow)", node=n)

    # --- pinned test data ---
    pin = wf.get("pinData")
    if isinstance(pin, dict) and pin:
        add("pinned_data", "low",
            f"pinData present for {len(pin)} node(s) — pinned test data bloats the "
            f"export and can leak sample/PII; strip before shipping",
            fix="remove pinData")

    # --- source-instance metadata that ties the file to its origin ---
    for meta_key in ("id", "versionId", "instanceId", "meta"):
        if meta_key in wf and meta_key != "id":
            add("source_metadata", "info",
                f"export carries source-instance metadata '{meta_key}' (cosmetic)")

    return _finalize(wf, issues, names, community)


def _finalize(wf, issues, names, community) -> Dict:
    counts = {s: 0 for s in SEV_WEIGHT}
    penalty = 0
    for i in issues:
        i["kind"] = "manual" if i["id"] in MANUAL_IDS else "blocker"
        counts[i["sev"]] = counts.get(i["sev"], 0) + 1
        penalty += SEV_WEIGHT.get(i["sev"], 0)
    score = max(0, 100 - penalty)
    blockers = [i for i in issues
                if i["sev"] in BLOCKING_SEV and i["kind"] != "manual"]
    manual = [i for i in issues if i["kind"] == "manual"]
    importable = len(blockers) == 0
    return {
        "name": wf.get("name", "<unnamed>"),
        "node_count": len(wf.get("nodes", []) or []),
        "fidelity_score": score,
        "importable": importable,
        "counts": counts,
        "blocker_count": len(blockers),
        "manual_step_count": len(manual),
        "community_packages": sorted(community),
        "issues": issues,
    }
