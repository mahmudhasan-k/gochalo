<div align="center">
  <img src="frontend/public/brand/logo-lookup-flow.svg" width="72" height="72" alt="Gochalo logo" />
  <h1>Gochalo · গোছালো</h1>
  <p><strong>From scattered information to your next clear step.</strong></p>
  <p>An English–বাংলা workspace that organizes notices, photos, links and questions into plans you can follow.</p>

  <img alt="React 19" src="https://img.shields.io/badge/React-19-149eca" />
  <img alt="FastAPI · Python 3.12" src="https://img.shields.io/badge/FastAPI-Python%203.12-009688" />
  <img alt="Language · English + বাংলা" src="https://img.shields.io/badge/Language-English%20%2B%20বাংলা-6258ca" />
  <a href="LICENSE"><img alt="License · MIT" src="https://img.shields.io/badge/License-MIT-22a06b" /></a>

  <p>Built for <strong>Ostad Presents YUNet AIgnite Buildathon 2026</strong></p>
  <p><a href="#the-problem">Problem</a> · <a href="#the-product">Product</a> · <a href="#try-the-journey">Demo</a> · <a href="#ai--backend-architecture">Architecture</a> · <a href="#run-locally">Setup</a></p>
</div>

## The problem

A student finds an admission circular. A family member needs a passport. The information is available, but the next action, documents, fees and dates are buried across paragraphs, screenshots and fine print.

Gochalo helps people turn that reading into follow-through. Its starting audience is Bangladeshi students and families navigating everyday applications and notices, with English and Bangla interfaces built into the same workspace.

## The product

**Bring information → read a structured plan → track what comes next.**

| What users need | What Gochalo provides |
| --- | --- |
| Understand a notice or procedure | Six consistent sections: Overview, Tasks, Dates/ Deadlines, Fees, Required Documents and Others |
| Work with information they already have | Photo, public link and pasted-text inputs, plus a question-based planning path |
| Act on the result | Interactive steps, saved plans, searchable history, personal tasks and due dates |
| Keep useful context | Original input, extracted text, supporting quotations and review disclosures where available |
| Return later or share | Guest storage, optional account sync, copy, print and calendar export |

The product's value is the connection between **understanding and action**: a readable plan stays attached to the tasks the user follows. Guest access, bilingual copy and responsive layouts keep that journey approachable.

## Try the journey

1. Open a pre-made example: **Australian visitor visa**, **Bangladesh e-passport**, or **Dhaka University admission**. Inspect the overview, dates, fees and documents, then tick a step.
2. Try fresh input through **Paste Text**, **Snap Notice** or **Web Link** to see the AI processing path. Open the source details and compare the result with the original.
3. Add other tasks to the plan, choose **Save tasks**, then revisit **History** and **Tasks**. Try printing or exporting a date to your calendar.

The examples are explicitly labelled **Pre-made demo** and make no new AI request. The DU example uses an archived 2025–26 admission cycle. Fresh analysis requires the configured backend; prepared examples demonstrate the interface rather than model accuracy.

## AI & Backend Architecture

The browser manages the workspace; FastAPI coordinates AI processing, source extraction and review. Provider credentials stay on the server.

```text
                     React + TypeScript Workspace
                        English / বাংলা interface
                                  │
          ┌───────────────────────┼────────────────────────┐
          ▼                       ▼                        ▼
    Guest storage          FastAPI Backend          Optional account sync
      IndexedDB         Session ownership · Jobs     Clerk → Supabase RLS
                                  │
                  ┌───────────────┴────────────────┐
                  ▼                                ▼
              Question                      Photo / Link / Text
                  │                                │
                  ▼                                ▼
        Gemini single-pass plan          Gemini vision / Jina Reader
        General knowledge only             / Direct pasted text
        No browsing or source review               │
                  │                                ▼
                  │                      Structured generation
                  │                                │
                  │                                ▼
                  │                     Local quotation, number
                  │                         and scope checks
                  │                                │
                  │                                ▼
                  │                       Separate AI review
                  │                                │
                  │                      ┌─────────┴──────────┐
                  │                      ▼                    ▼
                  │                Review completes     Review incomplete*
                  │                Admitted claims      Locally admitted
                  │                + review status      claims + warning
                  │                      │                    │
                  └──────────────────────┴────────────────────┘
                                         │
                                         ▼
                            Six-section plan + disclosures
                            Checklist · History · Saved tasks
                              Copy · Print · Calendar
```

*Incomplete-review results require fallback to be enabled; they contain only claims admitted by local checks. Failed requests can still return an error rather than a plan.*

AI turns messy input into a consistent structure, while the two paths keep their different review guarantees visible. The frontend and API can be hosted separately on Vercel and Render.

**Review is an aid, not independent verification.** AI can miss conditions or misclassify details, including optional requirements. Important dates, fees and eligibility should be checked against the original source. Missing fees never mean a service is free. Experimental web research is separate from the main question box.

## Built with care

- **Evidence-aware output:** source claims retain supporting quotations and review limitations; general-knowledge plans do not pretend to have source evidence.
- **Guarded inputs:** public-link extraction uses URL/DNS, size and timeout checks; image uploads have format, size and decoding guards.
- **A practical workspace:** browser saving works without an account; configured Clerk/Supabase integration adds cross-device sync.
- **Automated testing:** offline provider mocks and frontend interaction tests cover response contracts, task persistence and failure handling.

## Run locally

Requires **Python 3.12**, **Node.js 22+**, and your own Gemini API key for fresh analysis. From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
npm ci --prefix frontend
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in the root `.env`, then run:

```powershell
$env:VITE_CLOUD_ENABLED = "false"
npm run build --prefix frontend
.\scripts\start.ps1
```

Open [localhost:8000](http://127.0.0.1:8000). For hot reload, keep the backend running and run `npm run dev --prefix frontend` separately. Use one API worker for shared in-memory job guards. Keep private keys out of `VITE_*` variables.

For prepared demos without analysis credentials, run `npm run build:alpha --prefix frontend`, then `npm run preview --prefix frontend` in the same shell.

## Privacy

Guest plans, source text and tasks are saved in this browser's IndexedDB; clearing browser data removes them. Submitted input reaches the configured processing providers. Optional account sync uploads saved plans. Avoid passwords, ID numbers and private documents.

## Development

Run `.\scripts\verify.ps1` for offline backend checks, frontend tests and a production build. External providers are mocked during offline verification.

Optional account sync uses Clerk and Supabase. Public frontend settings are listed in `frontend/.env.example`; API configuration belongs in the root `.env`.

Created by **Mahmud Hasan** · [MIT License](LICENSE). Bundled fonts retain their own license notices.
