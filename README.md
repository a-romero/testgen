# TestGen — Enterprise QA Test Case Generation Platform

TestGen turns **requirements / context documents** into **unique BDD (Gherkin)
test cases** for an Enterprise QA team, on a **per‑project** basis. It stores and
reuses **generation templates**, supports **human annotation & an approval
workflow**, and exports to external tools (CSV / JSON / Gherkin / Jira‑ADO).

```
Scenario: Successful user login
  Given the user is on the login page
  When the user enters valid credentials and clicks submit
  Then the user should be redirected to the dashboard
```

The generation engine is inspired by the **Gym data‑designer** in the companion
`qstudio` repo: a test case is built from independently‑generated *field
variables* (enums, sampling lists, numbers, dates, booleans, LLM‑generated
values, and expressions computed from other fields), which are then synthesised
into a Given/When/Then scenario by an LLM (or a deterministic template engine
when no LLM key is configured, so the platform always runs).

## Architecture

| Layer | Stack |
|-------|-------|
| Backend | Python · FastAPI · Pydantic · SQLite (dependency‑free KV store) |
| Frontend | TypeScript · Next.js 14 · React 18 · Tailwind CSS |
| LLM | OpenAI / Anthropic / LiteLLM (any OpenAI-compatible gateway), optional, with a deterministic offline fallback |

```
testgen/
├── backend/                 FastAPI service
│   ├── app/
│   │   ├── main.py          app + router wiring
│   │   ├── config.py        env-driven settings
│   │   ├── storage.py       JSON-on-SQLite collections
│   │   ├── models.py        domain models (projects, docs, templates, cases)
│   │   ├── llm.py           LLM client w/ offline fallback
│   │   ├── generation.py    field-variable generation + BDD synthesis + dedup
│   │   ├── export.py        CSV / JSON / Gherkin / Jira export
│   │   └── routers/         projects, documents, templates, testcases, dashboard
│   └── tests/               generation & uniqueness tests
└── frontend/                Next.js app (Dashboard, Projects, Requirements,
                             Templates, Generate, Review & Approve)
```

## Running locally

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (/docs for OpenAPI)
```

### Frontend
```bash
cd frontend
npm install
npm run dev                            # http://localhost:3000
```

### Docker
```bash
docker compose up --build              # frontend :3000, backend :8000
```

### Configuration (environment variables)
| Variable | Default | Purpose |
|----------|---------|---------|
| `TESTGEN_API_KEY` | `changeme-local-dev` | Shared API key (`X-API-Key` header) |
| `TESTGEN_LLM_PROVIDER` | `auto` | `auto` \| `openai` \| `anthropic` \| `litellm` \| `none` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | – | Enable direct OpenAI/Anthropic generation |
| `LITELLM_BASE_URL` / `LITELLM_API_KEY` | – | Route via a LiteLLM proxy / any OpenAI-compatible gateway |
| `TESTGEN_LITELLM_MODEL` | `gpt-4o` | Default model when using the `litellm` provider |
| `TESTGEN_DB_DIR` | `backend/data` | SQLite storage location |

With `auto`, the provider resolves to LiteLLM if a gateway is configured, else
OpenAI, else Anthropic, else the offline engine. To centralise model access
behind one gateway, set `TESTGEN_LLM_PROVIDER=litellm` with `LITELLM_BASE_URL`
(and `LITELLM_API_KEY`); the model is routed through the OpenAI-compatible path
(an `openai/` prefix is added automatically when needed).

Without an LLM key the platform uses the deterministic template engine — useful
for demos, CI and offline development.

## Core capabilities

- **Per‑project organisation** with market / platform scoping.
- **Requirements management** — upload (file or text), **version**, **approve**,
  filter and retrieve context documents.
- **Templates** — independent field variables + a Gherkin skeleton + a
  **versioned** LLM prompt template, stored and reused per project.
- **BDD generation** that is **unique within a project** — every scenario is
  hashed (normalised) and duplicates are discarded and regenerated.
- **Human validation** — annotations (valid / invalid / needs‑changes + 1‑5
  quality rating) and an **approve / reject** workflow.
- **Feedback‑driven regeneration** with full revision history.
- **Export / integrate** to CSV, JSON, Gherkin `.feature` and Jira/ADO CSV with
  a configurable column mapping.
- **Dashboards** — input quality, generation trends, approval/adoption, and a
  governance grid filtered by market & platform.

## How requirements map to the build

| Req | Capability | Where |
|-----|------------|-------|
| HLR1 | Standardised, reusable template framework with consistent metadata | `routers/templates.py`, `models.py` |
| HLR2 | Collate / upload / version / approve / store / retrieve context docs with filters & access control | `routers/documents.py`, `deps.py` |
| HLR3 | Capture user story, acceptance criteria, context, test phase, techniques & output detail to drive generation | `models.py` (Template), `generation.py` |
| HLR4 | View/review cases and export to external formats (CSV/Jira/ADO) with configurable mappings | `routers/testcases.py`, `export.py`, `pages/testcases.tsx` |
| HLR5 | Dashboards: input quality, context completeness, generation trends, response quality, adoption | `routers/dashboard.py`, `pages/index.tsx` |
| HLR6 | Filtered governance view by market & platform | `routers/dashboard.py` (`/governance`) |
| HLR7 | Create, version & maintain backend prompt templates per platform | `routers/templates.py` (versioning), Template.`prompt_template` |
| HLR8 | Market/platform drop‑downs and dynamic context retrieval | project context + document filters, `Layout.tsx` |
| HLR9 | Multi‑round conversational regeneration with stored history & feedback APIs | `routers/testcases.py` (`/regenerate`) |
| HLR10 | Approval workflow before export/integration | document & test‑case approval endpoints |
| HLR11 | Capture user/project feedback & ratings to improve future generation | annotations + ratings feeding the dashboard |

## Tests
```bash
cd backend && source .venv/bin/activate
TESTGEN_LLM_PROVIDER=none pytest -q
```

## Uniqueness guarantee

Each generated scenario is reduced to a normalised hash of its title and
Given/When/Then steps. The generator tracks hashes already present for the
project (plus those produced in the current run) and keeps regenerating until it
reaches the requested count of genuinely distinct cases (or attempts are
exhausted), so a project never accumulates duplicate test cases.
