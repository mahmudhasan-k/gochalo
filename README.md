<div align="center">
  <img src="frontend/public/brand/logo-lookup-flow.svg" width="64" height="64" alt="Gochalo logo" />
  <h1>Gochalo · গোছালো</h1>
  <p><strong>A little order for everyday life.</strong></p>
  <p>Turn questions, notices, photos and links into useful next steps.</p>
  <p>
    <img alt="React 19" src="https://img.shields.io/badge/React-19-149eca" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Python%203.12-009688" />
    <img alt="Bilingual" src="https://img.shields.io/badge/Language-English%20%2B%20বাংলা-6258ca" />
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/License-MIT-22a06b" /></a>
  </p>
</div>

## The problem

An application notice, scholarship announcement or event page can hide its next steps among long paragraphs, dates, fees and exceptions. People often need to understand it, prepare the right items and remember what comes next—sometimes in a different language.

Gochalo organizes that information into **Overview, Steps, Deadlines, Fees, Required Documents and Others**, then lets people keep and work through the plan.

## What you can do

- **Ask a question:** get a practical general plan in English or Bangla. General Ask does not browse the web by default.
- **Use your own material:** read a PNG/JPEG notice with Gemini vision, extract a public link through Jina, or paste text.
- **Keep the important conditions:** source checks match quotations and assess interpretation; missing or unresolved material remains visible in Others.
- **Act on the result:** check off steps, keep tasks grouped by session, add personal tasks and export explicit dates as `.ics` calendar entries.
- **Save your workspace:** guests save locally with IndexedDB; signed-in users can sync plans and tasks across devices through Clerk and Supabase.
- **Copy, share and print:** use the same plan text, with its relevant limitations.
- **Choose your view:** English/Bangla, System/Light/Dark, keyboard-accessible controls and responsive layouts.

The included examples are clearly marked demos. Opening one does not run AI or automatically add it to History. Generated plans follow the autosave preference.

## How it works

```text
                         Browser · React + TypeScript
                       English / Bangla · local IndexedDB
                         |                         |
          Vercel static frontend                  +--> Clerk Google sign-in
                         |                                  |
                  FastAPI · Render                 Supabase PostgreSQL
                  temporary owned jobs               account sync + RLS
                         |
          +--------------+-------------------+
          |                                  |
     General Ask                    Photo / Link / Text
     one planning pass              vision / Jina / supplied text
     unreviewed guidance                     |
          |                         schema + quotation checks
          |                         semantic review + coverage
          +----------------+-----------------+
                           |
                    Six-category plan
                    steps · tasks · calendar
```

The Gemini transport supports a primary key and two optional backup keys. It rotates only for documented quota/transient responses and preserves the failed stage. Local budgets remain shared across the key pool; adding keys does not multiply the local allowance.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 19, TypeScript, Vite, Lucide, bundled Plus Jakarta Sans and Noto Sans Bengali |
| API and validation | Python 3.12, FastAPI, Uvicorn, Pydantic, HTTPX, Pillow |
| AI and extraction | Google Gemini SDK; anonymous Jina Reader; optional configured secondary text providers |
| Local and cloud storage | IndexedDB, Supabase PostgreSQL with row-level security, Clerk Google OAuth |
| Verification | pytest, Vitest, Testing Library, mocked provider transports, PGlite SQL ownership checks |
| Deployment | Vercel static frontend; separate Render Docker API with a non-root runtime |

## Run locally

Requirements: **Python 3.12**, **Node.js 22**, npm and Git.

```powershell
git clone https://github.com/mahmudhasan-k/gochalo.git
cd gochalo
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade "pip>=26.2.0"
.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm.cmd ci --prefix frontend
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env.local
```

Put your own Gemini key in the ignored root `.env`. For accounts, put your public Clerk/Supabase configuration in `frontend/.env.local`; for guest-only development, set `VITE_CLOUD_ENABLED=false`. Never put private keys in a `VITE_` variable.

The commands above use Windows PowerShell. On macOS/Linux, use `python3.12`, `.venv/bin/python` and `npm` in place of the Windows executable names.

Run in two terminals:

```powershell
# Terminal 1 — API
.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1 --no-access-log

# Terminal 2 — UI
npm.cmd run dev --prefix frontend
```

Open the local Vite URL, normally `http://127.0.0.1:5173`. The frontend proxy can also reach `/api` on port 8000 when `VITE_API_BASE` is blank. Public configuration changes require restarting Vite or rebuilding the frontend.

## Run the test suite · 540+ checks

Tests are offline: no live Gemini/Jina calls are needed. Install development dependencies first.

```powershell
.venv\Scripts\python.exe scripts/check_dependencies.py
.venv\Scripts\python.exe scripts/verify.py
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
# Or use: .\scripts\verify.ps1
```

Verified clean release: **472 backend tests, 160 frontend tests and 405 backend subtests passed**, with one explicit historical expected failure.

The suite covers source constraints, provider failures, backup-key transitions, session ownership, drafts, autosave/reopen, checklist identities, tasks, calendar export and database ownership. Historical frontend regressions use `frontend/legacy`; it is not imported by the production app. One historical scope-contract test is an explicit expected failure; it is not a fresh live-quality pass.

## Deploy your own app

**Vercel Root Directory is the repository root (`.`), not `frontend`.** The single root `vercel.json` installs/builds the frontend and serves `frontend/dist`. Render uses the root Dockerfile for the API only.

1. Create your fresh Gemini, Clerk development and Supabase projects.
2. Follow [the deployment guide](docs/DEPLOYMENT.md) in order.
3. Use [the exact configuration reference](docs/CONFIGURATION.md) for keys, defaults and failover behavior.

API and account features require the documented host configuration. The repository intentionally contains no live credentials or personal environment files. The first free-domain setup uses a Clerk development instance with real sign-in; it does not claim Clerk production-instance status.

## Trust and limitations

AI output can be incomplete or wrong, including missed optional conditions. Quotation matching and model review are not independent factual verification. General Ask is unreviewed planning guidance; an incomplete source review carries a separate warning. Confirm important requirements, costs and dates with the relevant institution. Missing fee information never means a service is free.

Supplied sources are interpreted without silent web supplementation. Experimental grounded research is separate and disabled by default. Optional providers are disabled unless configured. Guests' saved content stays on the device; selected signed-in workflows use the account database. Processing sends supplied material to the configured providers and temporarily keeps recovery jobs in API memory. Do not submit passwords, ID numbers or other private details.

## License

[MIT](LICENSE) · Copyright © 2026 **Mahmud Hasan**. Bundled fonts retain their included Open Font License notices.
