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
- [ ] Flagged-chunk review
- [ ] Run / Run (streaming)
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
