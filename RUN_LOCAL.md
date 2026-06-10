# Running TestGen locally (without Docker)

Two processes: a Python **backend** (FastAPI on port 8000) and a Next.js
**frontend** (port 3000). Open two terminals.

## Prerequisites
- **Python 3.10+** (`python3 --version`)
- **Node.js 18+** and npm (`node --version`)
- No database or API keys required — TestGen runs offline with a deterministic
  generator. Add an LLM key later for richer output (see the end).

---

## 1. Backend (terminal 1)

```bash
cd backend

# create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# run the API (http://localhost:8000, interactive docs at /docs)
uvicorn app.main:app --reload --port 8000
```

Leave this running. Quick check in another shell:
```bash
curl -H "X-API-Key: changeme-local-dev" http://localhost:8000/healthz
# {"ok": true, "llm_available": false}
```

> `litellm` is a heavier dependency. If you only want to try it offline and
> prefer a faster install, you can install just the essentials:
> `pip install "fastapi" "uvicorn[standard]" "pydantic>=2.5" python-multipart`

---

## 2. Frontend (terminal 2)

```bash
cd frontend

# the .env.local file is already included and points at the backend:
#   NEXT_PUBLIC_API_BASE=http://localhost:8000
#   NEXT_PUBLIC_API_KEY=changeme-local-dev

npm install
npm run dev                        # http://localhost:3000
```

Open **http://localhost:3000**.

---

## 3. Try the workflow
1. **Projects** → create a project (set a Market and Platform, e.g. UK / Web).
2. **Requirements** → add a requirements document (paste text or upload a
   `.txt`/`.md`), then **Approve** it.
3. **Templates** → click **Load starter (BDD login)**, then **Create template**
   (or build your own field variables).
4. **Generate** → pick the template + document, choose how many cases, and
   generate. Duplicates are automatically suppressed.
5. **Review & Approve** → annotate, approve/reject, regenerate with feedback,
   and **Export** (Gherkin `.feature`, CSV, JSON, or Jira/ADO CSV).
6. **Dashboard** → see approval rates, trends and the market/platform grid.

---

## 4. Run the tests (optional)
```bash
cd backend
source .venv/bin/activate
pip install pytest
TESTGEN_LLM_PROVIDER=none pytest -q
```

---

## 5. Enable a real LLM (optional)
Generation works offline; to get natural BDD phrasing, set credentials before
starting the backend:

```bash
# OpenAI
export TESTGEN_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Anthropic
export TESTGEN_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# LiteLLM gateway / any OpenAI-compatible endpoint
export TESTGEN_LLM_PROVIDER=litellm
export LITELLM_BASE_URL=https://your-gateway/v1
export LITELLM_API_KEY=sk-...
export TESTGEN_LITELLM_MODEL=gpt-4o
```

Then restart `uvicorn`. `GET /healthz` should report `"llm_available": true`.

---

## Troubleshooting
- **Port already in use**: change the backend port with
  `uvicorn app.main:app --reload --port 8001` and update
  `frontend/.env.local` → `NEXT_PUBLIC_API_BASE=http://localhost:8001`.
- **Frontend can't reach the API / 401**: ensure the backend is running and the
  key in `frontend/.env.local` matches `TESTGEN_API_KEY` (default
  `changeme-local-dev`). Restart `npm run dev` after editing `.env.local`.
- **Data location**: state is stored in `backend/data/*.sqlite`. Delete that
  folder to reset.
