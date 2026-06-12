"""
FlowProof — workflow loader
===========================
Robustly load an n8n workflow export from a file/stdin/dict. Handles the three
shapes sellers actually have:

  1. A single workflow object: {"name", "nodes", "connections", ...}
  2. An n8n "export all" array: [{workflow}, {workflow}, ...]
  3. A wrapped export: {"workflows": [ ... ]}  /  {"data": {workflow}}

Pure standard library.
"""
from __future__ import annotations
import hashlib
import json
from typing import Dict, List, Union


class WorkflowLoadError(ValueError):
    pass


def _looks_like_workflow(obj) -> bool:
    return isinstance(obj, dict) and "nodes" in obj and isinstance(obj.get("nodes"), list)


def extract_workflows(data: Union[dict, list]) -> List[dict]:
    """Normalize any supported export shape into a list of workflow dicts."""
    if _looks_like_workflow(data):
        return [data]
    if isinstance(data, list):
        wfs = [w for w in data if _looks_like_workflow(w)]
        if wfs:
            return wfs
        raise WorkflowLoadError("JSON array contained no objects with a 'nodes' list")
    if isinstance(data, dict):
        for key in ("workflows", "data"):
            if key in data:
                return extract_workflows(data[key])
    raise WorkflowLoadError(
        "could not find an n8n workflow (need an object with a 'nodes' array, "
        "or an array/`workflows`/`data` wrapper around one)"
    )


def load_text(text: str) -> List[dict]:
    """Parse raw JSON text into a list of workflow dicts."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise WorkflowLoadError(f"file is not valid JSON: {e}") from e
    return extract_workflows(data)


def load_file(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return load_text(fh.read())


def sha256_of(obj: Union[dict, list]) -> str:
    """Deterministic content hash of a workflow (canonical JSON)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def workflow_name(wf: dict) -> str:
    return str(wf.get("name") or wf.get("id") or "<unnamed workflow>")
