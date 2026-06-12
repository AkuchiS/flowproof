"""
FlowProof — repair
==================
Produce a clean, import-ready copy of a workflow. Every transform is *safe*
(removes corruption / leaks, never invents behaviour) and is recorded so the
seller can see exactly what changed.

    from flowproof.repair import repair
    clean_wf, changes = repair(workflow_dict)

What it does:
  * strips embedded credential data and hard-coded secrets (security)
  * blanks credential ids while keeping the credential *name* as a stable
    re-link label (the buyer selects their own credential after import)
  * removes connections that point at non-existent nodes (graph corruption)
  * removes connection entries whose source node doesn't exist
  * de-duplicates node names so n8n can't silently merge edges
  * removes pinned test data and source-instance metadata
  * sets active=false and back-fills missing positions

Pure standard library. Deterministic.
"""
from __future__ import annotations
import copy
import re
from typing import Dict, List, Tuple

from .diagnostics import _SECRET_KEY, _SECRET_VALUE, _looks_like_real_secret  # reuse rules

_REDACTION = ""  # blank value — forces the buyer to wire a credential / $env


def _redact_secrets_in_params(params, changes: List[str], node_label: str) -> int:
    """Recursively blank values whose key looks like a secret. Returns count."""
    n = 0
    if isinstance(params, dict):
        for k, v in list(params.items()):
            if isinstance(v, (dict, list)):
                n += _redact_secrets_in_params(v, changes, node_label)
            elif (_SECRET_KEY.match(str(k)) and _looks_like_real_secret(v)) or \
                 (isinstance(v, str) and _SECRET_VALUE.search(v)):
                params[k] = _REDACTION
                changes.append(f"[{node_label}] redacted hard-coded secret in '{k}'")
                n += 1
    elif isinstance(params, list):
        for item in params:
            if isinstance(item, (dict, list)):
                n += _redact_secrets_in_params(item, changes, node_label)
    return n


def repair(wf: dict) -> Tuple[dict, List[str]]:
    wf = copy.deepcopy(wf)
    changes: List[str] = []
    nodes = wf.get("nodes")
    if not isinstance(nodes, list):
        return wf, ["could not repair: no 'nodes' array"]

    # --- per-node fixes ---
    used_names = set()
    x = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        label = node.get("name") or node.get("type") or "node"

        # de-duplicate names
        name = node.get("name")
        if isinstance(name, str):
            if name in used_names:
                base, suffix = name, 2
                while f"{base} ({suffix})" in used_names:
                    suffix += 1
                new_name = f"{base} ({suffix})"
                node["name"] = new_name
                changes.append(f"renamed duplicate node {name!r} -> {new_name!r} "
                               f"(edges to it may need manual review)")
                name = new_name
            used_names.add(name)

        # back-fill position
        pos = node.get("position")
        if not (isinstance(pos, list) and len(pos) == 2):
            node["position"] = [x, 300]
            changes.append(f"[{label}] set missing position -> {node['position']}")
        x += 280

        # credentials: strip embedded data, blank ids, keep names
        creds = node.get("credentials")
        if isinstance(creds, dict):
            for ctype, ref in creds.items():
                if isinstance(ref, dict):
                    extra = set(ref) - {"id", "name"}
                    if extra:
                        for k in extra:
                            ref.pop(k, None)
                        changes.append(f"[{label}] stripped embedded credential data "
                                       f"{sorted(extra)} from '{ctype}' (security)")
                    if ref.get("id"):
                        ref["id"] = ""
                        changes.append(f"[{label}] blanked credential id for '{ctype}' "
                                       f"(buyer re-selects by name "
                                       f"{ref.get('name', '?')!r})")

        # hard-coded secrets in parameters
        _redact_secrets_in_params(node.get("parameters", {}), changes, label)

    # --- connections: prune dangling sources/targets ---
    name_set = {n.get("name") for n in nodes if isinstance(n, dict)}
    connections = wf.get("connections")
    if isinstance(connections, dict):
        for source in list(connections.keys()):
            if source not in name_set:
                del connections[source]
                changes.append(f"removed connections from non-existent source {source!r}")
                continue
            outputs = connections[source]
            if not isinstance(outputs, dict):
                continue
            for out_type, branches in list(outputs.items()):
                if not isinstance(branches, list):
                    continue
                for branch in branches:
                    if not isinstance(branch, list):
                        continue
                    kept = []
                    for link in branch:
                        if isinstance(link, dict) and link.get("node") in name_set:
                            kept.append(link)
                        elif isinstance(link, dict):
                            changes.append(f"removed dangling edge {source!r} -> "
                                           f"{link.get('node')!r} (target missing)")
                    branch[:] = kept
    else:
        wf["connections"] = {}
        changes.append("added missing 'connections' object")

    # --- top-level hygiene ---
    if isinstance(wf.get("pinData"), dict) and wf["pinData"]:
        cnt = len(wf["pinData"])
        wf["pinData"] = {}
        changes.append(f"removed pinData for {cnt} node(s)")
    if wf.get("active"):
        wf["active"] = False
        changes.append("set active=false (don't auto-run on import)")
    if "settings" not in wf or not isinstance(wf.get("settings"), dict):
        wf["settings"] = wf.get("settings") if isinstance(wf.get("settings"), dict) else {}
    for meta_key in ("versionId", "instanceId", "meta", "staticData"):
        if meta_key in wf:
            wf.pop(meta_key, None)
            changes.append(f"stripped source-instance metadata '{meta_key}'")

    if not changes:
        changes.append("no changes needed — workflow was already clean")
    return wf, changes
