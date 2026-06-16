# FlowProof

**Check n8n workflow exports import cleanly — before you buy, sell or ship them.**

Free, offline CLI. No API keys. Nothing leaves your machine.

```bash
python3 flowproof_cli.py check    workflow.json   # diagnose import-breakers
python3 flowproof_cli.py verify   workflow.json   # pass/fail import-fidelity verdict
python3 flowproof_cli.py selftest                 # prove it works
```

## What it catches
Leaked credential secrets · dangling credential references (the "No credentials yet"
empty-dropdown pain) · missing community nodes · version drift (typeVersion newer
than your instance) · deprecated syntax · broken connections and structural damage.

## Receipts, not promises
The checker was tested against **20 real workflows** from 3 sources (production
instances, n8n.io community templates, GitHub exports) and arbitrated against a
**live n8n import API**: its import verdicts matched the live import result with
**0 mismatches**. A `FAIL` is only ever reported when a real n8n actually rejected
the workflow.

## Why
A large slice of shared and sold n8n templates arrive broken — and nobody ships
proof their template imports. FlowProof is the missing verification layer: run it
before you trust an export you're about to import, buy, or hand to a client.

## FlowProof Pro — repair, certificate & handover
The free CLI above **diagnoses**. When you need to actually fix and ship a workflow,
FlowProof Pro delivers the paid deliverable:

- **Repaired, import-ready JSON** — secrets redacted, dangling edges and duplicate
  names resolved, deprecated nodes flagged, ready to import.
- **A content-hashed "FlowProof Checked" certificate** (+ a badge for client delivery)
  — proof the workflow imports, with the exact one-time setup steps a receiver needs.
- **A plain-English handover** — repair list + credential/setup checklist so you can
  hand it to a client with confidence.

→ **https://fp.akuchis.com**

---

Free CLI is MIT licensed. Built by [AkuchiS](https://fp.akuchis.com/?src=github).
Want a maintained version, or have an objection? Tell us what would stop you using
it: https://fp.akuchis.com/?src=github

