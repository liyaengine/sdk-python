# liyaengine

Official Python client for the [Liya Engine](https://liyaengine.ai) public API.

> **Status: early access.** This SDK currently covers Domains, Intents, Collections, Agents, Workflows, and Evaluations. More resources (Run, Guardrail Policies) ship incrementally — see [Roadmap](#roadmap).

## Install

```bash
pip install liyaengine
```

## Quickstart

```python
from liyaengine import LiyaEngine

client = LiyaEngine(api_key="liya_...")

collection = client.collections.create(
    slug="contracts",
    label="Contracts",
    domain_keys=["legal-ops"],
)

collections = client.collections.list()
```

Or as a context manager (closes the underlying HTTP connection pool automatically):

```python
with LiyaEngine(api_key="liya_...") as client:
    collections = client.collections.list()
```

Get an API key from your [Liya Engine dashboard](https://app.liyaengine.ai) under Settings → API Keys.

## Domains & Intents

A Domain is the top-level container most tenants configure first; Intents live under it.

```python
domain = client.domains.create(domain_key="billing", display_name="Billing")

intent = client.domains.intents.create(
    "billing", intent_key="refund-status", display_name="Refund Status",
    description="Answer refund-status questions.",
    prompt_template="You are a billing assistant. Question: {{message}}",
    # Agent mode, per-intent execution/retrieval/cache overrides — optional:
    agent_config={"enabled": True, "max_steps": 3},
)

one_intent = client.domains.intents.get("billing", "refund-status")

# Every update creates a restorable version snapshot automatically.
versions = client.domains.intents.versions.list("billing", "refund-status")
client.domains.intents.versions.restore("billing", "refund-status", versions[0].version_number)

# Direct retrieval — no LLM call, useful for testing knowledge scoping.
result = client.domains.query("billing", query="refund timeline")
```

> `domains.update()`/`domains.intents.update()` return `{"updated": 1}`, not the updated object — call `get()`/`list()` again for the fresh state. Guardrail policy attachment is still dashboard-only (a separate resource with no `/v1` route yet). To bind an intent's prompt to a Prompt Studio library version instead of inline text, pass `prompt_binding={"kind": "library_version", "prompt_id": ..., "version_id": ..., "content_hash": ...}` in place of `prompt_template` — editing `prompt_template` directly afterward without also passing `prompt_binding` silently detaches the binding.

## Domain Tools

The custom webhook tools an agent-mode intent (`agent_config={"enabled": True, ...}`) can call mid-conversation — e.g. a real order-status lookup against your own backend. Every custom tool is dispatched by one generic platform tool, `webhook_sender`; the LLM calls `webhook_sender({tool_name, payload})`, and `webhook_sender` looks up `tool_name` in the domain's `custom_tools` to find the real endpoint.

```python
# 1. Define the tool on the domain.
client.domains.tools.update(
    "shipping-support",
    # webhook_sender must be explicitly enabled here — defining custom_tools
    # alone does nothing, since it's webhook_sender that actually dispatches them.
    enabled_platform_tools=["webhook_sender"],
    custom_tools=[{
        "name": "lookup_order",
        "display_name": "Order Lookup",
        "description": 'Looks up a real order by number and returns its current status. Call with {"order_number": "..."}.',
        "endpoint_url": "https://fernbankoutdoor.com/api/liya-tools/lookup-order",
        "auth_type": "api_key",
        "auth_value": os.environ["LIYA_TOOL_SHARED_SECRET"],  # write-only — never returned by get()
    }],
)

# 2. Verify the endpoint actually works before wiring it into a live intent.
test_result = client.domains.tools.test("shipping-support", "lookup_order", {"order_number": "A1092"})

# 3. Point the intent at "webhook_sender" — NOT "lookup_order". agent_config["tools"]
# is a platform-tool allowlist; "lookup_order" is only ever an *argument* the
# model passes to webhook_sender at call time, never an entry in this array.
client.domains.intents.update(
    "shipping-support", "track-order",
    agent_config={"enabled": True, "tools": ["webhook_sender"], "max_steps": 3},
)

config = client.domains.tools.get("shipping-support")
# config.custom_tools[0].auth_configured is True — the real credential is never returned, only whether one is set.
```

> **Two real footguns, easy to hit on the first try — both now rejected server-side instead of failing silently:** (1) `enabled_platform_tools` must include `"webhook_sender"` — the API rejects `tools.update()` with `400 WEBHOOK_SENDER_NOT_ENABLED` if you set `custom_tools` without it, since a domain with only `custom_tools` defined and no platform tool enabled would otherwise register *zero* tools and the model would just apologize (or worse, quietly fabricate a plausible-looking answer if your prompt insists it report a result). (2) `agent_config["tools"]` takes platform tool names, so it's `["webhook_sender"]`, never `["lookup_order"]` — the API rejects `intents.create()`/`intents.update()` with `400 INVALID_AGENT_TOOL` if a custom tool's own name appears there, since it's an argument passed to `webhook_sender` at call time, not an allowlist entry. Beyond that: there's no JSON-schema parameter definition for a custom tool today — `description` is the *only* thing the model sees to decide when and how to call it, so be explicit about the fields you expect. `custom_tools` in `update()` REPLACES the entire array, not a per-tool patch. Omit `auth_value` on an update to preserve the existing stored credential; it's encrypted separately and never round-trips back to a reader.

## Run

The primary way to actually invoke an intent — built-in pack or custom domain — and get a real, LLM-generated response back. `agents.run()` and a domain's public `/v1/{domain}/{intent}` route both reach this same endpoint under the hood; call it directly when you don't need an Agent's multi-turn orchestration on top.

```python
result = client.intents.run(
    domain="billing",
    intent="refund-status",
    message="How long do refunds take?",
)

print(result.data)      # shape depends on domain — see docstring
print(result.metadata)  # {"model_used": ..., "tokens_used": ..., "cost_usd": ..., "latency_ms": ..., "cached": ..., ...}
print(result.usage)     # {"requests_remaining": ..., "tokens_remaining": ..., ...}
```

Or stream it token by token:

```python
for event in client.intents.stream(domain="billing", intent="refund-status", message="How long do refunds take?"):
    if event["type"] == "token":
        print(event["delta"], end="", flush=True)
    if event["type"] == "done":
        print("\n", event["session_id"], event["cost_usd"])
    if event["type"] == "error":
        raise RuntimeError(event["message"])
```

> **Streaming is built-in-packs only** (`chat`, `hiring`, `fintech`, `healthcare`, `ehs`, `compliance`) — a custom-domain intent raises a `LiyaEngineAPIError` (`STREAMING_NOT_SUPPORTED`) immediately, before the stream opens; use `run()` instead for those. Once a stream *has* opened, every other failure (quota exceeded, provider error) arrives as an in-band `{"type": "error"}` event, not a raised error — always check `event["type"]` in your loop, not just try/except. Neither method defaults `domain` sensibly if you omit both `domain` and `pack` — it falls back to `"hiring"`, a historical default carried over from the API itself — pass one explicitly.

## Collections

```python
client.collections.list()
client.collections.get(id)
client.collections.create(slug=..., label=..., domain_keys=[...])
client.collections.update(id, label=..., tags=[...], visibility=...)
client.collections.delete(id)

# Reference documents into a collection — never copies them, never touches embeddings.
client.collections.documents.attach(collection_id, document_id)
client.collections.documents.list(collection_id)  # returns CollectionDocumentSummary, a narrower shape than Document — see below
client.collections.documents.detach(collection_id, document_id)

# Scope a collection's knowledge to a domain.
client.collections.domains.attach(collection_id, "legal-ops")
client.collections.domains.detach(collection_id, "legal-ops")

# Live aggregation — no rollup table, always reflects current state.
stats = client.collections.analytics(collection_id)

# What references this collection — domains, intents, agents (indirect via
# domain). "workflows" is always None: no workflow-to-collection link exists.
refs = client.collections.connections(collection_id)
```

Full field reference: [Collections API](/docs/api-reference/collections).

## Documents

The tenant-wide knowledge pool collections reference (a document can belong to zero, one, or many collections — attaching never copies it or touches its embeddings).

```python
client.documents.list()
doc = client.documents.get(id)  # includes the full chunk_list
client.documents.delete(id)

# Synchronous — blocks until extraction/chunking/embedding finishes. If
# collection_ids names exactly one collection, that collection's own
# chunking/embedding defaults pre-fill the upload.
uploaded = client.documents.upload(
    file_base64="...",
    file_name="refund-policy.pdf",
    category="policy",
    collection_ids=[collection_id],
)

# Push a URL or inline content — upserts by a deterministic source_id.
client.documents.push(url="https://example.com/faq", title="FAQ")
```

> Unlike `list()`/`get()`, `upload()`'s response has no `uploaded_by` — a real, pre-existing API asymmetry, not an SDK gap. Call `get(id)` afterward if you need it. Similarly, `collections.documents.list()` returns `CollectionDocumentSummary` (`id`/`name`/`chunks`/`size_kb`/`embedding_model`/`uploaded_at` only) rather than a full `Document` — no `category`, `uploaded_by`, or `collections` field; call `documents.get(id)` for the complete record.

For large files or a multi-page crawl, use the async job queue instead — it returns immediately and you poll for completion:

```python
job = client.documents.jobs.create_url_job(url="https://example.com", depth=2)
# ...or: client.documents.jobs.create_file_job(file_base64=..., file_name=...)

status = client.documents.jobs.get(job["jobId"])  # pending | running | completed | failed | cancelled
client.documents.jobs.list(status="running")
client.documents.jobs.cancel(job["jobId"])
```

> Cancellation is cooperative (checked between page fetches / chunk embeds), not instant, and there is no crash-recovery sweep — if the process running a job restarts mid-run, the job is left "running" indefinitely rather than auto-retried. Poll `get(job_id)` for terminal status; don't assume `cancel()` stops it immediately.

## Agents

```python
agent = client.agents.create(
    agent_key="support-triage",
    name="Support Triage",
    goal="Triage incoming support tickets and route them to the right team.",
)

# Agents are created in draft status — deploy to activate for execution.
client.agents.deploy(agent.agent_key)

result = client.agents.run(agent.agent_key, input={"message": "My order hasn't arrived yet."})

history = client.agents.list_runs(agent.agent_key)
```

## Workflows

```python
workflow = client.workflows.create(
    name="Lead Intake",
    steps=[{"step_type": "trigger", "config": {"trigger_subtype": "webhook"}}],
)

# Workflows are created in draft status — deploy to publish and make them
# callable. Deploying a webhook-triggered workflow for the first time mints
# its webhook secret; capture it immediately, it is never returned again.
deployed = client.workflows.deploy(workflow.workflow_key)
webhook_url, webhook_secret = deployed["webhook_url"], deployed["webhook_secret"]

# Roll the secret with a grace window so in-flight senders don't break.
client.workflows.rotate_webhook_secret(workflow.workflow_key, grace_period_seconds=300)

# Flip a deployed workflow on/off without touching its definition.
client.workflows.toggle(workflow.workflow_key)

result = client.workflows.run(workflow.workflow_key, input={"email": "ada@example.com"})

history = client.workflows.list_runs(workflow.workflow_key)
```

> `deploy()` and `rotate_webhook_secret()` return the plaintext webhook secret exactly once. Store it immediately — subsequent reads (`get`, `list`) only ever expose `trigger_config["has_secret"]`.

## Evaluations

A Suite binds a Dataset to one specific intent; `suites.run()` calls that intent for real and scores what it produces. `runs.submit()`/`evaluations.score()` score a response you already generated yourself — no intent execution involved.

```python
dataset = client.evaluations.datasets.create(
    name="Support Replies",
    cases=[{"input": {"message": "Where is my order?"}}],
)

suite = client.evaluations.suites.create(
    name="Order Status Suite",
    domain_key="support",
    intent_key="order-status",
    dataset_id=dataset.id,
)

# Runs are always async — poll for status/results.
run = client.evaluations.suites.run(suite.id)
result = client.evaluations.runs.get(run.id)

# A failed run can be resumed — already-scored cases are skipped.
client.evaluations.runs.resume(run.id)

# Score a response you already generated, no dataset/suite required.
scored = client.evaluations.score(
    input={"message": "Where is my order?"},
    output="Your order shipped yesterday and should arrive by Friday.",
)
```

> `custom_scorer_webhook_secret` on a Suite is write-only — it's never returned; only a `custom_scorer_webhook_secret_set` boolean comes back on reads.

## Error handling

Every failed request raises `LiyaEngineAPIError`, carrying the API's `code`, `message`, and HTTP `status`:

```python
from liyaengine import LiyaEngineAPIError

try:
    client.collections.create(slug="contracts", label="Contracts", domain_keys=["legal-ops"])
except LiyaEngineAPIError as err:
    if err.code == "SLUG_CONFLICT":
        # handle the conflict
        pass
    raise
```

Network failures and timeouts raise `LiyaEngineNetworkError` instead. Requests are retried automatically on `429`/`5xx` responses and transient network errors (2 retries by default).

## Configuration

```python
LiyaEngine(
    api_key="liya_...",
    base_url="https://api.liyaengine.ai",  # override for local/staging
    timeout_s=30.0,
    max_retries=2,
)
```

## Roadmap

- [x] Domains & Intents (full CRUD parity with the dashboard, prompt binding, agent/execution/retrieval/cache config, versioning, direct retrieval query, narrow document upload — guardrail policy attachment still dashboard-only)
- [x] Collections
- [x] Agents (full CRUD, deploy, run, run/session history)
- [x] Workflows (full CRUD, toggle, deploy, webhook secret rotate, run, run history)
- [x] Evaluations (Datasets/Cases/Suites/Runs/Reviews CRUD, suite execution, cancel/resume, statistical + pairwise compare, standalone scoring)
- [x] Full KBaaS (document list/get/delete/upload/push, async ingestion jobs + URL crawl, collection↔document/domain attach-detach, analytics/connections)
- [x] Run / Run (streaming) — built-in packs only for streaming; custom domains use non-streaming `run()`
- [x] Domain agentic tool configuration (previously dashboard-only)
- [ ] Flagged-chunk review
- [ ] Guardrail Policies
- [ ] Prompt Studio (holding until the feature itself is committed/merged upstream)
- [ ] Async client

Full docs: https://liyaengine.ai/docs/sdks/python

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mypy src
pytest
```

## License

MIT
