"""
FlowProof — n8n node knowledge base
===================================
A curated, *maintained* map of common n8n nodes used to detect version drift,
deprecated nodes, deprecated parameter syntax, and missing/community nodes when
a workflow JSON is imported onto a different instance.

This is the part that goes stale on un-vetted reseller bundles. Keep it current:
bump ``MAX_TYPE_VERSION`` when n8n ships a new node version, and add new
``DEPRECATED_NODES`` entries as nodes are retired.

Data current as of the n8n 1.9x line (mid-2026). Pure data — no dependencies.
"""
from __future__ import annotations
from typing import Optional, Tuple

# Bundled node-package prefixes. Anything whose type does NOT start with one of
# these is a *community* node that must be installed on the target instance, or
# the workflow will fail to import ("Unrecognized node type").
BUNDLED_PREFIXES = (
    "n8n-nodes-base.",
    "@n8n/n8n-nodes-langchain.",
)

# type -> highest typeVersion this knowledge base knows about.
# A node whose typeVersion is GREATER than this was exported from a newer n8n
# than the importer may run (forward version drift -> import/run failure).
MAX_TYPE_VERSION = {
    "n8n-nodes-base.httpRequest": 4.2,
    "n8n-nodes-base.webhook": 2.0,
    "n8n-nodes-base.respondToWebhook": 1.1,
    "n8n-nodes-base.set": 3.4,
    "n8n-nodes-base.code": 2.0,
    "n8n-nodes-base.if": 2.2,
    "n8n-nodes-base.switch": 3.2,
    "n8n-nodes-base.merge": 3.1,
    "n8n-nodes-base.filter": 2.2,
    "n8n-nodes-base.noOp": 1.0,
    "n8n-nodes-base.stopAndError": 1.0,
    "n8n-nodes-base.wait": 1.1,
    "n8n-nodes-base.splitInBatches": 3.0,
    "n8n-nodes-base.aggregate": 1.0,
    "n8n-nodes-base.removeDuplicates": 2.0,
    "n8n-nodes-base.itemLists": 3.1,
    "n8n-nodes-base.splitOut": 1.0,
    "n8n-nodes-base.limit": 1.0,
    "n8n-nodes-base.sort": 1.0,
    "n8n-nodes-base.dateTime": 2.0,
    "n8n-nodes-base.html": 1.2,
    "n8n-nodes-base.xml": 1.0,
    "n8n-nodes-base.crypto": 1.0,
    "n8n-nodes-base.manualTrigger": 1.0,
    "n8n-nodes-base.scheduleTrigger": 1.2,
    "n8n-nodes-base.executeWorkflow": 1.1,
    "n8n-nodes-base.executeWorkflowTrigger": 1.0,
    "n8n-nodes-base.errorTrigger": 1.0,
    "n8n-nodes-base.readWriteFile": 1.0,
    "n8n-nodes-base.editImage": 1.0,
    "n8n-nodes-base.compression": 1.1,
    "n8n-nodes-base.emailSend": 2.1,
    "n8n-nodes-base.emailReadImap": 2.0,
    "n8n-nodes-base.gmail": 2.1,
    "n8n-nodes-base.googleSheets": 4.5,
    "n8n-nodes-base.googleDrive": 3.0,
    "n8n-nodes-base.googleCalendar": 1.2,
    "n8n-nodes-base.slack": 2.3,
    "n8n-nodes-base.telegram": 1.2,
    "n8n-nodes-base.discord": 2.0,
    "n8n-nodes-base.notion": 2.2,
    "n8n-nodes-base.airtable": 2.1,
    "n8n-nodes-base.github": 1.0,
    "n8n-nodes-base.postgres": 2.5,
    "n8n-nodes-base.mySql": 2.4,
    "n8n-nodes-base.mongoDb": 1.1,
    "n8n-nodes-base.redis": 1.0,
    "n8n-nodes-base.rssFeedRead": 1.1,
    "n8n-nodes-base.ftp": 1.0,
    "n8n-nodes-base.ssh": 1.0,
    "n8n-nodes-base.x": 2.0,
    "n8n-nodes-base.openAi": 1.8,
    "@n8n/n8n-nodes-langchain.agent": 1.7,
    "@n8n/n8n-nodes-langchain.chatTrigger": 1.1,
    "@n8n/n8n-nodes-langchain.lmChatOpenAi": 1.0,
    "@n8n/n8n-nodes-langchain.openAi": 1.4,
    "@n8n/n8n-nodes-langchain.memoryBufferWindow": 1.3,
    "@n8n/n8n-nodes-langchain.outputParserStructured": 1.2,
    "@n8n/n8n-nodes-langchain.toolWorkflow": 1.2,
    "@n8n/n8n-nodes-langchain.vectorStoreInMemory": 1.0,
}

# Nodes n8n has deprecated/retired -> recommended replacement. Importing still
# works on older instances but breaks on current ones; sellers should migrate.
DEPRECATED_NODES = {
    "n8n-nodes-base.function": "n8n-nodes-base.code",
    "n8n-nodes-base.functionItem": "n8n-nodes-base.code",
    "n8n-nodes-base.start": "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.cron": "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.interval": "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.htmlExtract": "n8n-nodes-base.html",
    "n8n-nodes-base.renameKeys": "n8n-nodes-base.set",
    "n8n-nodes-base.twitter": "n8n-nodes-base.x",
    "n8n-nodes-base.moveBinaryData": "n8n-nodes-base.code",
}

# Nodes whose *parameter schema* changed across a major typeVersion. A node
# below the listed version uses the OLD (deprecated) parameter syntax — it
# imports, but the old syntax silently mis-maps on a current instance.
DEPRECATED_SYNTAX_BELOW = {
    "n8n-nodes-base.httpRequest": 4.0,   # pre-v4 used a different options schema
    "n8n-nodes-base.set": 2.0,           # pre-v2 used "values", not "assignments"
    "n8n-nodes-base.if": 2.0,            # pre-v2 used "conditions" v1 schema
    "n8n-nodes-base.switch": 2.0,
    "n8n-nodes-base.merge": 2.0,
    "n8n-nodes-base.itemLists": 3.0,
}


def is_bundled(node_type: str) -> bool:
    """True if the node ships with n8n (no community install required)."""
    return bool(node_type) and node_type.startswith(BUNDLED_PREFIXES)


def community_package(node_type: str) -> Optional[str]:
    """Return the npm package a community node belongs to, or None if bundled.

    'n8n-nodes-discord.discord'      -> 'n8n-nodes-discord'
    '@acme/n8n-nodes-foo.fooTrigger' -> '@acme/n8n-nodes-foo'
    """
    if not node_type or is_bundled(node_type):
        return None
    if node_type.startswith("@"):
        # @scope/package.nodeName
        head = node_type.rsplit(".", 1)[0]
        return head
    return node_type.split(".", 1)[0]


def known_max_version(node_type: str) -> Optional[float]:
    return MAX_TYPE_VERSION.get(node_type)


def version_status(node_type: str, type_version) -> Tuple[str, str]:
    """Classify a node's typeVersion.

    Returns (status, message) where status is one of:
      ok | ahead | deprecated_syntax | unknown_version | missing
    """
    if type_version is None:
        return ("missing", "node has no typeVersion (older export; may import at v1)")
    try:
        tv = float(type_version)
    except (TypeError, ValueError):
        return ("missing", f"typeVersion is not numeric: {type_version!r}")

    known = MAX_TYPE_VERSION.get(node_type)
    if known is None:
        return ("unknown_version", "version not in knowledge base (cannot vet drift)")
    if tv > known:
        return ("ahead", f"typeVersion {tv} is newer than known max {known} "
                          f"(exported from a newer n8n; will fail on older instances)")
    floor = DEPRECATED_SYNTAX_BELOW.get(node_type)
    if floor is not None and tv < floor:
        return ("deprecated_syntax", f"typeVersion {tv} uses the pre-{floor} parameter "
                                     f"schema (silently mis-maps on current n8n)")
    return ("ok", f"typeVersion {tv} within supported range (<= {known})")


# --- Corpus-grown 2026-06-12 (improve cycle 1, Jay-bounded): versions OBSERVED
# in the 20-real-workflow QC corpus. Observed-in-the-wild = at least this
# version exists; refine upward as newer exports are seen.
MAX_TYPE_VERSION.update({
  '@n8n/n8n-nodes-langchain.googleGemini': 1.0,
  '@n8n/n8n-nodes-langchain.lmChatGoogleGemini': 1.0,
  '@n8n/n8n-nodes-langchain.lmChatGroq': 1.0,
  '@n8n/n8n-nodes-langchain.memoryMongoDbChat': 1.0,
  '@n8n/n8n-nodes-langchain.toolCode': 1.3,
  '@n8n/n8n-nodes-langchain.toolWikipedia': 1.0,
  'n8n-nodes-base.activeCampaignTrigger': 1.0,
  'n8n-nodes-base.acuitySchedulingTrigger': 1.0,
  'n8n-nodes-base.affinityTrigger': 1.0,
  'n8n-nodes-base.cryptoTool': 1.0,
  'n8n-nodes-base.dateTimeTool': 2.0,
  'n8n-nodes-base.gmailTrigger': 1.2,
  'n8n-nodes-base.httpRequestTool': 4.2,
  'n8n-nodes-base.perplexity': 1.0,
  'n8n-nodes-base.rssFeedReadTool': 1.2,
  'n8n-nodes-base.stickyNote': 1.0,
  'n8n-nodes-base.telegramTrigger': 1.2,
  'n8n-nodes-base.writeBinaryFile': 1.0
})
