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

### Design notes

- **LangGraph** models explicit orchestration. Help intents skip tool execution via conditional routing; session memory uses the SQLite checkpointer.
- **MockLLM** keeps demos deterministic and CI offline-friendly.
- **Connectors** use timeout, exponential backoff retry, and idempotency keys.
- **Duplicate detection**: exact VAT/DUNS, ERP lookup, fuzzy scoring with thresholds (≥95 auto-match, 80–95 review, <80 new supplier).

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
