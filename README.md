# Supplier Onboarding Agent

Prototype for the ALDI Developer Challenge: a conversational assistant that helps Buying and Supplier Administration teams run duplicate checks, create onboarding packages, and query cross-system status.

Repository: [github.com/szatmari-ivett/supplieronboardingagent](https://github.com/szatmari-ivett/supplieronboardingagent)

Enterprise backends are mocked. Assumptions and trade-offs are documented here and in [`slides/index.html`](slides/index.html).

## Core capabilities

| Capability | Implementation |
|------------|----------------|
| Duplicate check | Seed master data + ERP lookup + fuzzy name/address matching (`rapidfuzz`) |
| Onboarding flow | Procurement package → ERP sync → cloud compliance workflow |
| Status aggregation | Canonical phases with `healthy` / `degraded` / `stale` health |

## Requirements

- Python 3.11+
- Windows, macOS, or Linux

## Setup

```bash
git clone https://github.com/szatmari-ivett/supplieronboardingagent.git
cd supplieronboardingagent
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

Optional dev tooling:

```bash
pip install -r requirements-dev.txt
```

## Run

Windows:

```bat
run.bat
```

Manual:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Default LLM mode is **MockLLM** (deterministic, no API key required).

### Optional LLM providers

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
```

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
```

If a provider is selected but the API key is missing, the app falls back to MockLLM and logs a warning.

## Demo script

For a clean first run, delete `data/process_state.db` and `data/checkpoints.db`.

1. **Duplicate check**
   ```
   Does supplier FreshFarm GmbH already exist? VAT DE123456789
   ```

2. **Start onboarding**
   ```
   Start onboarding for NewOrganic Ltd, UK, VAT GB987654321
   ```

3. **Status**
   ```
   What is the status of onboarding ONB-001?
   ```

4. **Degraded mode** — set `FAULT_ERP=1` in `.env`, restart, then create or query onboarding again.

Architecture deck: [`slides/index.html`](slides/index.html)

## Architecture

```text
Web UI
  -> POST /chat (SSE: progress + message events)
  -> LangGraph (router -> act? -> respond)
  -> Tools -> resilient connectors -> mock ERP / procurement / cloud
  -> MockLLM (default) or OpenAI / Anthropic function calling
  -> SQLite process store + LangGraph SQLite checkpointer
```

### Design rationale

This prototype prioritises **correctness and observability over AI spectacle**. The LLM handles natural-language understanding; deterministic backend code owns business facts.

| Decision | Rationale |
|----------|-----------|
| **LangGraph orchestration** (`router → act → respond`) | Multi-step onboarding needs explicit, testable flow control. Help intents skip tools via conditional routing. |
| **LLM as planner, tools as source of truth** | Onboarding IDs, match scores, and statuses come from tool output — not free-form generation — to reduce hallucination risk. |
| **MockLLM as default** | Deterministic, offline-friendly demos and CI without API keys. OpenAI / Anthropic available via function calling with graceful fallback. |
| **Duplicate detection pipeline** | Exact VAT/DUNS match, ERP lookup, and RapidFuzz fuzzy scoring with thresholds (≥95 auto, 80–95 review, below 80 new supplier). |
| **Cross-system status aggregation** | Canonical phases plus `healthy` / `degraded` / `stale` health give one answer across ERP, procurement, and cloud. |
| **Connector resilience** | Timeout, exponential backoff, and idempotency keys — ready to swap mocks for MCP-backed integrations in production. |
| **Two-tier memory** | LangGraph checkpointer for conversation context; SQLite process store for long-running onboarding state. |

**Rejected alternatives:** single prompt chains (weak tool control), direct UI over APIs (no conversational guidance), real integrations in the prototype (outside challenge scope).

**Prototype boundaries:** template-formatted responses (not LLM-generated prose), auth/RBAC out of scope, `active` phase defined but not reached automatically. Full trade-off discussion: [`slides/index.html`](slides/index.html).

### Canonical phases

`initiated` → `duplicate_check` → `package_created` → `erp_sync` → `cloud_compliance` → `active`

The `active` phase is defined but not reached automatically in this prototype.

## Development

```bash
ruff check app tests scripts
pytest
python scripts/smoke_test.py
```

## Project layout

```text
app/
  agent/         LangGraph graph, nodes, prompts
  llm/           Mock / OpenAI / Anthropic providers
  tools/         duplicate_check, create_onboarding, aggregate_status
  connectors/    mock ERP, procurement, cloud integrations
  domain/        models, matching, time helpers
  memory/        SQLite process store
  observability/ structured logging
web/             chat UI
slides/          architecture deck
tests/           unit and API tests
scripts/         smoke test
data/            local SQLite files (gitignored)
```

## Assumptions

- Procurement, ERP, and cloud systems are mocked in-memory / SQLite.
- Authentication and RBAC are out of scope for the prototype.
