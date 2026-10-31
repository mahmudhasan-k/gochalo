<div align="center">
  <img src="frontend/public/brand/logo-lookup-flow.svg" width="80" height="80" alt="Gochalo Logo" />
  <h1>Gochalo · গোছালো</h1>
  <p><strong>A little order for everyday life.</strong></p>
  <p>
    An AI-powered bilingual execution workspace that turns messy notices, bureaucratic procedures, photos, and public links into verified, step-by-step action plans in <strong>English</strong> and <strong>বাংলা</strong>.
  </p>

  <p>
    <a href="#-the-problem--why-gochalo-exists"><img alt="Built for Real Life" src="https://img.shields.io/badge/Focus-Civic%20%26%20Everyday%20Productivity-0d9488?style=for-the-badge" /></a>
    <img alt="React 19 + TypeScript" src="https://img.shields.io/badge/Frontend-React%2019%20%2B%20TS-149eca?style=for-the-badge&logo=react" />
    <img alt="FastAPI Python 3.12" src="https://img.shields.io/badge/Backend-FastAPI%203.12-009688?style=for-the-badge&logo=fastapi" />
    <img alt="Google Gemini" src="https://img.shields.io/badge/AI-Google%20Gemini%20SDK-4285F4?style=for-the-badge&logo=google" />
    <img alt="Tests Passing" src="https://img.shields.io/badge/Tests-630%2B%20Passing-22a06b?style=for-the-badge" />
    <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-6258ca?style=for-the-badge" /></a>
  </p>

  <p>
    <a href="#-key-features">Key Features</a> ·
    <a href="#-system-architecture">System Architecture</a> ·
    <a href="#-engineering-highlights--reliability">Engineering Highlights</a> ·
    <a href="#-quick-start-local-setup">Quick Start</a> ·
    <a href="#-api-reference">API Reference</a> ·
    <a href="#-deployment">Deployment</a>
  </p>
</div>

---

## 💡 The Problem & Why Gochalo Exists

Whether you are decoding a university scholarship circular, applying for a passport or visa, opening a bank account, or booking intercity train tickets in Bangladesh, critical details are rarely in one clean place. They are buried inside:
- Dense multi-page **Bangla and English government or campus notices**,
- Blurry **JPEG/PNG flyers** shared in WhatsApp or Facebook groups,
- Long **public web pages** filled with exceptions and fine print, or
- Conflicting third-party blog posts with outdated rules.

Standard AI chatbots respond with walls of conversational text, silently guess missing fees or dates, and give you no way to track your progress.

**Gochalo (গোছালো)** — *meaning "organized" or "orderly" in Bangla* — is **not a chatbot wrapper**. It is a structured, bilingual execution workspace that transforms questions, photos, links, and pasted text into an interactive **6-category action plan**, complete with live checklists, source-quote verification, conflict & gotcha warnings, and one-click `.ics` calendar exports.

> *Note on Naming:* Previously prototyped under the working title **Lookup Flow** (evolved from Shobuj Potro's Bangla-first notice reader), the project is unified as **Gochalo · গোছালো** (`ss-merge-alpha`).

---

## ✨ Key Features

### 1. Four Flexible Input Paths
- **🔍 Ask & Plan (`kind="ask"`):** Ask any procedural or everyday question (e.g., *"How to buy train tickets from Bangladesh?"* or *"Indonesia e-VOA application procedure"*). Receives structured steps, required documents, standard benchmark fees/timelines to verify, and real-world portal warnings.
- **🖼️ Notice Photo / Flyer OCR (`PNG` / `JPEG`):** Upload a photo of a printed notice, event poster, or circular. Powered by **Gemini Vision** transcription with strict MIME, size, and image-decoding guards.
- **🔗 Public Web Link Extraction:** Paste any public notice or article URL. Extracted via an SSRF-guarded **Jina Reader** pipeline with special handling for `.gov.bd` portals.
- **📋 Paste Raw Text:** Drop messy Bangla or English text directly from emails, PDFs, or announcements.

### 2. Deterministic 6+1 Category Action Workspace
Every analysis is projected into a consistent, scannable layout:
1. **Overview (`overview`):** Clear summary of the procedure, notice, or event.
2. **Actionable Steps (`actionable_steps`):** Sequential verb-driven tasks rendered as **interactive checkboxes** with a live completion progress bar.
3. **Required Documents (`required_documents`):** Concise item/file prep checklist (e.g., *NID Original + Photocopy*, *Passport photo < 200 KB*) tracked independently from action steps.
4. **Deadlines & Important Dates (`deadlines`):** Extracted dates and time windows with inline **Add to Calendar (`.ics`)** export anchored to `Asia/Dhaka` time.
5. **Fees & Payment Rules (`fees`):** Exact fee breakdowns, supported payment gateways (e.g., bKash, Nagad, Visa/Mastercard), or benchmark estimates.
6. **Others & Missing Information (`others`):** Important operational rules (such as ticket quotas) plus explicit transparency on any categories absent from the supplied source.
7. **Heads-Up: Contradictions, Confusions & Warnings (`unknowns`):** Dedicated epistemic callouts grouping **`contradiction`** (e.g., *5-day vs. 10-day railway booking windows* or *90-day visa validity vs. 30-day stay limit*), **`unverified`** interpretations, and **`missing`** source details.

### 3. Built for Follow-Through (Not Just Reading)
- **Interactive Task Manager:** Check off steps and documents as you complete them, inject your own **custom personal tasks and due dates**, or manage tasks across all saved plans from the dedicated **Tasks** tab.
- **Inspectable Source Evidence:** Expand source-backed plans to inspect the original input, extracted text, supporting verbatim quotations, and review disclosures.
- **Local-First Guest Mode + Optional Cloud Sync:** Works immediately with zero sign-up using browser **IndexedDB** storage. Users who sign in via **Clerk (Google OAuth)** get automatic cross-device sync backed by **Supabase PostgreSQL** with Row-Level Security (RLS).
- **True Bilingual Experience (`en` / `bn-BD`):** Authored English and বাংলা interfaces, localized numerals (`bn-BD` / `en-GB`), System/Light/Dark themes, print-ready stylesheet (`print-only`), and formatted one-click clipboard summaries.

---

## 🏗️ System Architecture

```text
                       Browser · React 19 + TypeScript (Vite)
                 English / বাংলা UI · Local IndexedDB · Print / .ics
                         │                                  │
           Vercel Static Frontend                           ├──► Clerk Google OAuth
                         │                                  │            │
                         ▼                                  ▼            ▼
               FastAPI (:8000) on Render               Supabase PostgreSQL (RLS)
          Session Tokens · Owned Jobs · SSE          Cross-Device Workspace Sync
                         │
        ┌────────────────┼───────────────────┐
        ▼                ▼                   ▼
  [Ask & Plan]     [Photo / Link / Text]  [Grounded Research]
  Single-Pass      Gemini Vision / Jina   2-Stage Search +
  Structured Plan  Source Extraction      Schema Extraction
        │                │                   │
        │                ▼                   │
        │       Quote-First Generation       │
        │                │                   │
        │                ▼                   │
        │      Deterministic Local Gate      │
        │    (Quote, Number & Scope Check)   │
        │                │                   │
        │                ▼                   │
        │      Semantic Review + Fallback    │
        └────────────────┼───────────────────┘
                         ▼
          Public DTO (6 Categories + Unknowns)
       Interactive Checklists · Tasks · Calendar
```

### Dual-Path Verification Pipeline

| Input Path | Processing Pipeline | Verification & Trust Model |
| :--- | :--- | :--- |
| **Ask & Plan** (`kind="ask"`) | Single-pass structured Gemini planning with domain benchmark guidance and conflict awareness. | Provides actionable general guidance, standard benchmark fees/windows (clearly marked to verify on official portals), and common procedural pitfalls (`review_mode="general_ask"`). |
| **Supplied Source** (`Photo`, `Link`, `Text`) | **Stage 1:** Vision OCR or SSRF-guarded Jina extraction.<br>**Stage 2:** Quote-first structured generation.<br>**Stage 3:** Local deterministic quote, number, and scope admission checks.<br>**Stage 4:** Independent semantic review pass (with resilient fallback). | Every extracted claim must anchor to verbatim quotes in the supplied source. Unmatched or ambiguous items are routed transparently to **Others / Unknowns** rather than hallucinated. |
| **Web Research** (`/api/research`) | **Stage 1:** Grounded web retrieval.<br>**Stage 2:** Decoupled JSON schema extraction preserving verified source URIs. | Separates live search grounding from strict JSON schema decoding to prevent citation stripping and URL fabrication (`review_mode="web_research"`). |

---

## 🛡️ Engineering Highlights & Reliability

During development and live stress-testing across real Bangladeshi and international bureaucratic workflows, we engineered several production safeguards:

1. **Grammar-Safe Constrained Decoding (`strip_grammar_bounds`):**
   Deeply nested Pydantic schemas with bounded array/string constraints (`maxItems`, `minItems`, `maxLength`, `default`, `title`) can overflow Gemini's finite-state grammar compiler and trigger `HTTP 400 INVALID_ARGUMENT` errors during structured generation and semantic review. Gochalo recursively strips grammar-expanding metadata before dispatching `response_json_schema` while enforcing full Pydantic validation on the returned payload.
2. **Zero-Data-Loss Review Resilience (`deterministic_review_fallback`):**
   If the secondary semantic review pass encounters a transient provider hiccup, rate limit, or schema error, Gochalo never discards a valid, locally verified draft. Instead, it degrades gracefully to `review_mode="deterministic_only"`, preserving all claims that passed local quotation and number checks alongside a transparent review-status disclosure.
3. **Multi-Key Pool Failover & Transient Backoff:**
   The Gemini transport layer (`gemini_requests.py`) supports a primary key plus backup keys (`GEMINI_BACKUP_API_KEY_1`, `GEMINI_BACKUP_API_KEY_2`). It automatically rotates keys with a short backoff on both quota exhaustion (`HTTP 429`) and transient upstream server errors (`HTTP 500`, `502`, `503`, `504`) while preserving the active job stage.
4. **Hardened URL & Image Ingestion:**
   Public URL extraction validates schemes, strips URL fragments cleanly, blocks private/loopback IP ranges against SSRF, enforces response-size and timeout ceilings, and tolerates non-fatal Jina metadata warnings so valid notices are never dropped. Image uploads verify MIME headers, byte size, and Pillow image decoding before touching the Vision API.
5. **Real-Time SSE Progress + Idempotent Job Recovery:**
   Long-running OCR and multi-stage analyses stream live stage transitions over Server-Sent Events (`/api/jobs/{job_id}/stream`) with automatic polling fallback, owned session tokens (`X-Session-Token`), and idempotent `request_id` recovery if a user refreshes mid-flight.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, Lucide Icons, Custom Responsive CSS, Bundled `Plus Jakarta Sans` & `Noto Sans Bengali` |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, HTTPX, Pillow |
| **AI & Extraction** | Google GenAI SDK (`google-genai`), Gemini Vision OCR, Jina Reader API, Portal-aware `.gov.bd` parser |
| **Storage & Auth** | Browser `IndexedDB` (Guest workspaces & tasks), `localStorage` (preferences), Clerk Google OAuth, Supabase PostgreSQL with RLS |
| **Testing & QA** | `pytest` (470+ backend tests + 405 subtests), `Vitest` & React Testing Library (160 frontend tests), `PGlite` (SQL RLS contract tests) |
| **Deployment** | Vercel (Static Frontend CDN), Render (Dockerized Non-Root FastAPI Runtime), UptimeRobot (Keep-Alive Health Monitoring) |

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- **Python 3.12+**
- **Node.js 22+** and `npm`
- A **Google Gemini API Key** (`GEMINI_API_KEY`) — *Note: Curated built-in demo examples work offline without an API key!*

### 1. Clone & Install Dependencies

**Windows (PowerShell):**
```powershell
git clone https://github.com/mahmudhasan-k/ss-merge-alpha.git
cd ss-merge-alpha

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
```

**macOS / Linux (Bash/Zsh):**
```bash
git clone https://github.com/mahmudhasan-k/ss-merge-alpha.git
cd ss-merge-alpha

python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
```

### 2. Configure Environment Variables

```powershell
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env.local
```

Open the root `.env` file and add your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
# Optional backup keys for automatic 429/503 failover:
GEMINI_BACKUP_API_KEY_1=
GEMINI_BACKUP_API_KEY_2=
DETERMINISTIC_REVIEW_FALLBACK=true
```

For local guest-mode development (no Clerk/Supabase account setup required), set in `frontend/.env.local`:
```env
VITE_CLOUD_ENABLED=false
```
*(Never place private API keys inside `VITE_*` variables, as `VITE_*` values are bundled into the browser build.)*

### 3. Start the Application

You can run the full stack in development mode across two terminals:

**Terminal 1 — FastAPI Backend (`http://127.0.0.1:8000`):**
```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```
*(Important: Always run `--workers 1` when using in-memory session/job state.)*

**Terminal 2 — Vite Frontend (`http://127.0.0.1:5173`):**
```powershell
npm run dev --prefix frontend
```

Open **[http://127.0.0.1:5173](http://127.0.0.1:5173)** in your browser. Vite automatically proxies `/api/*` requests to `http://127.0.0.1:8000`.

---

## 🧪 Running the Verification Suite (630+ Automated Checks)

Gochalo includes a comprehensive offline verification suite that mocks external providers, blocks accidental outbound network calls, and validates schema contracts, fallback transitions, session ownership, checklist state persistence, calendar `.ics` generation, and PostgreSQL Row-Level Security policies.

```powershell
# Run the complete verification pipeline (Dependencies + Backend Pytest + Frontend Vitest + Production Build)
.\scripts\verify.ps1
```

Or run individual suites:
```powershell
.\.venv\Scripts\python.exe scripts/check_dependencies.py
.\.venv\Scripts\python.exe scripts/verify.py
npm test --prefix frontend
npm run build --prefix frontend
```

---

## 📡 API Reference

| Method & Endpoint | Auth / Guard | Description |
| :--- | :--- | :--- |
| `GET /api/health` | Public (Zero-Quota) | Lightweight health and feature-availability probe (safe for UptimeRobot). |
| `GET /api/example` | Public | Loads curated pre-computed bilingual demo plans without calling external AI providers. |
| `POST /api/session` | Public | Issues an anonymous `X-Session-Token` used to own and isolate queued jobs. |
| `POST /api/extract/link` | `X-Session-Token` | Queues SSRF-guarded Jina web page extraction for a public URL. |
| `POST /api/extract/image` | `X-Session-Token` | Queues Gemini Vision transcription for a validated PNG/JPEG notice. |
| `POST /api/analysis` | `X-Session-Token` | Queues `Ask & Plan` (`kind="ask"`) or supplied-source (`kind="source"`) 6-category analysis. |
| `GET /api/jobs/{job_id}` | `X-Session-Token` | Polls current status and final structured DTO for an owned job. |
| `GET /api/jobs/{job_id}/stream` | `X-Session-Token` | Server-Sent Events (SSE) stream emitting real-time job stage updates. |
| `GET /api/requests/{request_id}` | `X-Session-Token` | Recovers an in-flight or completed job by client `request_id` after page reload. |

---

## 📂 Repository Structure

```text
ss-merge-alpha/
├── frontend/
│   ├── src/
│   │   ├── WorkspaceApp.tsx      # Main workspace shell, History & Tasks views, Cloud/Local sync
│   │   ├── PlanView.tsx          # 6-category plan renderer, interactive checklists, .ics export
│   │   ├── migrationCopy.ts      # Authored English & বাংলা UI copy and category labels
│   │   ├── productTypes.ts       # Core TypeScript contracts and task origin mapping
│   │   └── *.test.tsx            # 160 Vitest + React Testing Library suites
│   └── public/                   # Brand assets, bundled fonts (OFL), prepared demo payloads
├── backend/
│   ├── main.py                   # FastAPI app, session/job lifecycle, SSE streaming, admission gates
│   ├── result_contract.py        # 6-category state projection and has_guidance resolution
│   ├── result_metadata.py        # Bilingual disclosure notices and uncertainty grouping
│   ├── research.py               # 2-stage grounded web research pipeline
│   ├── engine/
│   │   ├── ai_service.py         # Gemini structured generation, grammar stripping, semantic review
│   │   ├── prompts.py            # Grounded source prompts & benchmark-aware Ask prompts
│   │   ├── gemini_requests.py    # Multi-key rotation and 429/5xx transient failover
│   │   ├── url_input.py          # SSRF-guarded Jina link extraction & .gov.bd portal support
│   │   ├── ocr_service.py        # Gemini Vision OCR transcription
│   │   └── request_control.py    # Local rate-limit & budget guards
│   └── test_*.py                 # 470+ pytest unit, regression, and contract tests
├── supabase/migrations/          # PostgreSQL schema & Row-Level Security (RLS) policies
├── scripts/                      # Startup, offline verification (verify.ps1), and acceptance scripts
├── vercel.json                   # Vercel static frontend build configuration
├── render.yaml                   # Render Docker API service blueprint
└── Dockerfile                    # Hardened non-root Python 3.12 container image
```

---

## ☁️ Deployment

Gochalo is architected for zero-cost/low-cost cloud hosting using **Vercel** (Frontend) and **Render** (Backend API), with optional **Clerk** + **Supabase** for cross-device accounts:

1. **Backend on Render (`Dockerfile` / `render.yaml`):**
   - Deployed as a Dockerized Python 3.12 FastAPI web service running with a single worker (`--workers 1`).
   - Configure `GEMINI_API_KEY`, `GEMINI_BACKUP_API_KEY_1`, `GEMINI_BACKUP_API_KEY_2`, `DETERMINISTIC_REVIEW_FALLBACK=true`, and `CORS_ORIGINS` (set to your Vercel production domain) in the Render dashboard.
   - **Keep-Alive Tip:** Point an UptimeRobot HTTP monitor at `GET /api/health` every 10 minutes to prevent free-tier cold starts without consuming Gemini API quota.
2. **Frontend on Vercel (`vercel.json`):**
   - Set the Vercel **Root Directory** to the repository root (`.`). `vercel.json` builds `frontend/` and serves `frontend/dist`.
   - Set `VITE_API_BASE` to your live Render backend URL (e.g., `https://your-service.onrender.com`).
   - Set `VITE_CLOUD_ENABLED=true` along with public `VITE_CLERK_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY` if enabling cloud sign-in, or `VITE_CLOUD_ENABLED=false` for standalone guest mode.

---

## ⚠️ Responsible Use & Trust Boundaries

- **Verification Aide, Not Legal Authority:** Gochalo helps organize complex notices and procedures into actionable steps. AI extraction and review can still miss conditional rules or recent policy changes. Always verify critical fees, eligibility, and deadlines against the official issuing institution. Missing fee information in a notice does not mean a service is free.
- **Privacy First:** Guest plans and tasks stay in your browser's local `IndexedDB`. When submitting a question, photo, link, or text, the content is sent to the configured AI/extraction providers for processing—never submit passwords, secret tokens, or sensitive personal identification numbers.

---

## 📄 License

Distributed under the **[MIT License](LICENSE)** · Copyright © 2026 **Mahmud Hasan**.  
Bundled fonts (`Plus Jakarta Sans` and `Noto Sans Bengali`) retain their respective Open Font License (OFL) notices in `frontend/public/fonts`.
