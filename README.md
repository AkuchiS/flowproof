# FlowProof

**Check, repair and certify n8n workflow exports — before you buy, sell or ship them.**

Offline CLI. No API keys. Nothing leaves your machine.

```bash
python3 flowproof_cli.py check    workflow.json   # diagnose
python3 flowproof_cli.py fix      workflow.json   # auto-repair what's safe
python3 flowproof_cli.py certify  workflow.json   # content-hashed certificate
python3 flowproof_cli.py selftest                 # prove it works
```

## What it catches
Leaked credential secrets - dangling credential references (the "No credentials yet"
empty-dropdown pain) - missing community nodes - version drift (typeVersion newer
than your instance) - deprecated syntax - broken connections and structural damage.

## Receipts, not promises
Tested against **20 real workflows** from 3 sources (production instances, n8n.io
community templates, GitHub exports) and arbitrated against a **live n8n import
API**: certification verdicts matched live import results with **0 mismatches**.
`FAIL_IMPORT` is only ever claimed when a real n8n actually rejected the workflow.
Verdicts: `PASS` / `PASS_WITH_SETUP` / `NEEDS_SETUP` / `FAIL_IMPORT` - and the
certificate ships the exact one-time setup steps a receiver needs.

Optional ground-truth mode: point `FLOWPROOF_N8N_URL` + `FLOWPROOF_N8N_API_KEY` at
your own instance and certify will arbitrate import claims against it (creates the
workflow inactive, deletes it immediately, never executes anything).

## Why
A large slice of shared and sold n8n templates arrive broken - and nobody ships
proof their template imports. FlowProof is the missing verification layer: run it
before you trust an export, or ship its certificate alongside the templates you sell.

**Want a maintained version, or have an objection?** Tell us what would stop you
using it: https://fp.akuchis.com/?src=github

MIT licensed. Built by [AkuchiS](https://fp.akuchis.com/?src=github).
