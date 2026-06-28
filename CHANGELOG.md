# Changelog

Notable changes to this project. Newest first.

## [2.1.0] - 2026-06-28
- CLI now prints a short, contextual note about FlowProof Pro after a `check`/`verify` (only when relevant) — never in `--json` output or `selftest`, so machine use stays clean.

## [2.0.0] - 2026-06
- The offline diagnostic engine: `check`, `verify`, `selftest`. Detects leaked credential secrets, dangling credential references, missing community nodes, version drift, deprecated syntax, and broken connections. Verdicts arbitrated against a live n8n import API.
