# Fresh deployment · Vercel + Render + Clerk + Supabase

These instructions create new services. Do not repoint or modify an older Gochalo/Shobuj Potro deployment. All credentials are supplied independently through the relevant dashboards. No AI request is needed to prepare, build or smoke-test this release.

## 1. Choose the first-release account mode

Use a fresh **Clerk development instance** with real Google sign-in on your free `*.vercel.app` address. It is not mocked or account-disabled. Clerk production instances require a domain you own; the development-instance setup has Clerk's development limits and branding. A future production-domain migration is separate. [Clerk environments](https://clerk.com/docs/guides/development/managing-environments).

## 2. Create Clerk and Supabase

1. In Clerk, create your application, select its Development instance and enable **Google** under social connections. Development instances use Clerk's shared OAuth credentials unless you choose to configure your own.
2. Keep the instance's **publishable `pk_test_...` key** and issuer/domain ready. Do not put the Clerk secret key in the frontend or Render.
3. Create a fresh free Supabase project. Keep its project URL and **publishable key** ready; never use service-role/secret credentials in the browser.
4. Enable Clerk's Supabase integration/session-token `role: authenticated` support, then register the same Clerk issuer in Supabase **Authentication → Third-Party Auth → Clerk**. Follow the current dashboard's native integration, not a legacy custom JWT template. [Official integration guide](https://supabase.com/docs/guides/auth/third-party/clerk).
5. Apply `supabase/migrations/20261024_workspace.sql` once in the new Supabase SQL editor (or your normal migration workflow). This creates tables, row-level security and the revision-checked write function. It uses `auth.jwt()->>'sub'`, not a UUID assumption about Clerk user IDs. Do not turn off RLS or grant browser clients direct write access.

## 3. Reserve the Vercel project

Import `mahmudhasan-k/gochalo` as a new Vercel project so you know its assigned production origin. Do not assume the requested project name is available. You can finish environment configuration before the first useful deployment.

| Setting | Exact choice |
|---|---|
| Production branch | `main` |
| Framework preset | Vite |
| **Root Directory** | **Repository root (`.` / leave empty), NOT `frontend`** |
| Install command | `npm ci --prefix frontend` |
| Build command | `npm run build --prefix frontend` |
| Output directory | `frontend/dist` |
| Node.js | 22.x |

The root `vercel.json` is authoritative. There is no second `frontend/vercel.json`. Its SPA rewrite serves `/sso-callback` and client routes through `index.html`. No old branch-deployment guards are carried into this fresh repository.

## 4. Create the Render API

Create a **new Web Service**, connect the same GitHub repository and use:

| Setting | Exact choice |
|---|---|
| Service name | `gochalo-api` if available; otherwise your chosen new name |
| Branch | `main` |
| Runtime / Language | Docker |
| Root Directory | Repository root / empty |
| Dockerfile path | `./Dockerfile` |
| Docker build context | `.` |
| Docker command override | Leave empty; use Dockerfile CMD |
| Instance | Free |
| Region | Singapore when offered on Free; otherwise an offered Free region |
| Health check | `/api/health` |

`render.yaml` is an equivalent new-service Blueprint; choose either manual Web Service creation or the Blueprint, not both. Docker ships only the API, uses one worker and runs as a non-root user. It installs dependencies at build time, then removes pip from the final runtime. Render supplies `PORT`. No frontend keys belong in its image build.

Enter these **Render Environment** values before a useful launch:

```dotenv
GEMINI_API_KEY=YOUR_NEW_PRIMARY_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
APP_ENV=production
FRONTEND_ORIGINS=https://YOUR-ACTUAL-VERCEL-PROJECT.vercel.app
DETERMINISTIC_REVIEW_FALLBACK=true
LOCAL_EVALUATION_CAPTURE=false
RESEARCH_FREE_ACCESS_CONFIRMED=false
```

Optionally add `GEMINI_BACKUP_API_KEY_1` and `GEMINI_BACKUP_API_KEY_2`, each as a separate secret. Leave `GEMINI_FALLBACK_MODEL`, `OPENROUTER_API_KEY` and `GROQ_API_KEY` unset for the initial Gemini-only launch. Never copy model credentials to Vercel. See [configuration reference](CONFIGURATION.md) before enabling optional providers or experimental grounding.

Once deployed, visit `https://YOUR-ACTUAL-API.onrender.com/api/health`. Expect `status: ok`, `analysis_enabled: true`, `research_enabled: false`. Health checks do not invoke Gemini. They check boot and feature flags, not whether a key is configured, works or has remaining quota. The API-only root `/` need not serve the website.

## 5. Finish Vercel configuration and deploy

Set these in **Vercel → Settings → Environment Variables → Production**:

```dotenv
VITE_API_BASE=https://YOUR-ACTUAL-API.onrender.com
VITE_CLOUD_ENABLED=true
VITE_CLERK_PUBLISHABLE_KEY=YOUR_PUBLIC_PK_TEST_KEY
VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_SUPABASE_PUBLISHABLE_KEY
```

These are public browser settings. Use the exact variable names: `VITE_SUPABASE_ANON_KEY` is not read. Rebuild/redeploy after changing them. Do not promote a guest-only build and assume environment changes will modify its already-built JavaScript.

Use the final Vercel origin consistently in Render's `FRONTEND_ORIGINS` and Clerk's allowed/redirect settings where the development dashboard exposes them. The app requests an OAuth callback at **`https://YOUR-FRONTEND/sso-callback`**, then returns to **`https://YOUR-FRONTEND/#home`**. If you configure a Google OAuth client yourself, Google's authorized callback is the exact URI Clerk displays—not a guessed `/sso-callback` URL. No Clerk/Supabase signing secret is required by this app.

Keep Preview deployments guest-only unless you intentionally configure their public SDK keys and exact allowed origins. Do not add `*` to Render CORS to make arbitrary preview domains work.

## 6. Check the hosted app without AI calls

- Open the production URL, not a Vercel login-protected preview. Check English/Bangla, themes, mobile layout and navigation.
- Open a labelled demo; it should not send an analysis request or add itself to History. Copy/share text and checkboxes can be tested without AI.
- Sign in with Google, confirm return from `/sso-callback`, then sign out. Check for Clerk/Supabase browser errors. Do not claim cross-device save is accepted until you have actually saved and reopened an account result.
- Confirm `/api/health`, CORS from the exact frontend origin, and the absence of private keys in browser bundles. Test account isolation with two accounts before relying on a public launch.
- A real generated-plan/cloud-save check needs a separately authorized AI call or a clearly labelled non-production fixture. This preparation does not perform one.

Free Render services may sleep after **15 minutes** without incoming traffic, causing a cold start. Process-local jobs/rate counters reset on restart; saved guest data and Supabase records are separate. Keep one API worker and configure trusted proxy handling carefully; arbitrary forwarded headers must not identify clients. [Render free-service limits](https://render.com/docs/free).

Before hackathon submission, add the actual organizer-provided artwork if the rules require it; the built-in event watermark text is not proof of using that official asset. General Ask and model-reviewed source plans still need their limitations; do not market the output as independently verified or exhaustive.
