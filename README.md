# liyaengine

Official Python client for the [Liya Engine](https://liyaengine.ai) public API.

> **Status: early access.** This SDK currently covers Collections, Agents, and Workflows. More resources (Domains, Run, Guardrail Policies, Evals) ship incrementally — see [Roadmap](#roadmap).

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

- [x] Collections
- [x] Agents (full CRUD, deploy, run, run/session history)
- [x] Workflows (full CRUD, toggle, deploy, webhook secret rotate, run, run history)
- [ ] Domains (custom domain + intent CRUD)
- [ ] Run / Run (streaming)
- [ ] Guardrail Policies
- [ ] Evaluations
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
