# Configuration reference

All names below are taken from the application code. Environment names are case-sensitive. Empty credentials disable that optional provider; primary Gemini is required for new AI analysis. `APP_ENV=production` stops local `.env` loading, so Render must supply the values. Process settings take precedence over local files.

## Render backend

| Variable | Required? | Default when omitted | Exact purpose / format |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes, for live analysis | Empty; analysis requests fail safely | One server-only Google AI Studio API key; no commas. |
| `GEMINI_BACKUP_API_KEY_1` | Optional | Empty | First distinct backup key, server-only. |
| `GEMINI_BACKUP_API_KEY_2` | Optional | Empty | Second distinct backup key, server-only. |
| `GEMINI_MODEL` | Optional | `gemini-3.5-flash-lite` | Model ID used by Ask, image transcription, source generation, inventory and review. Verify access in your own provider account. |
| `GEMINI_FALLBACK_MODEL` | Optional | Empty | At most one alternate-model source-analysis attempt after an eligible failure; not an additional backup key. |
| `OPENROUTER_API_KEY` | Optional | Empty | Opts into secondary source analysis if no alternate Gemini model is selected. |
| `OPENROUTER_MODEL` | Optional | `openai/gpt-oss-120b:free` | Must end in `:free`; Qwen is rejected. The request enforces a zero-price ceiling and disables provider routing fallbacks. |
| `GROQ_API_KEY` | Optional | Empty | Secondary source analysis only when neither a distinct fallback Gemini model nor OpenRouter key is selected. |
| `GROQ_MODEL` | Optional | `openai/gpt-oss-120b` | Groq model ID. Qwen is rejected. Unlike OpenRouter, no per-request zero-price ceiling is available; leave unset unless authorized for your account. |
| `DETERMINISTIC_REVIEW_FALLBACK` | Optional | `true` | Any review-stage failure may return only locally admitted claims with `deterministic_only` and an incomplete-review warning. `false`, `0`, `off`, `no` disable this recovery; blank inherits enabled behavior. Does not expose an arbitrary failed-generation draft. |
| `FRONTEND_ORIGINS` | Required for split hosting | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact frontend origins, no paths; use the actual Vercel production origin. Do not use wildcard previews. |
| `APP_ENV` | Set on Render | `development` in code; Docker sets `production` | Use `production`; disables local `.env` loading and local evaluation traces. |
| `LOCAL_EVALUATION_CAPTURE` | Optional, development only | Disabled | Only exact `true` enables bounded owned-job traces outside production. Set `false` on Render. |
| `RESEARCH_FREE_ACCESS_CONFIRMED` | Optional | Disabled / empty | `true` enables the explicit experimental research route if primary analysis is available. Keep `false` until free access is independently confirmed. Does not change main Search into research. |
| `GEMINI_RESEARCH_MODEL` | Optional | `gemini-2.5-flash` | Model for the separate experimental grounding request. |
| `PORT` | Platform supplied | Docker: `8000` | Render supplies the listening port; the Docker command binds it on `0.0.0.0`. Not an application budget setting. |
| `PYTHONUNBUFFERED` | Container setting | Docker: `1` | Unbuffered server output. |
| `PYTHONDONTWRITEBYTECODE` | Container setting | Docker: `1` | Avoid runtime bytecode files. |

## Vercel frontend · public build-time values

| Variable | Required? | Default when omitted | Exact purpose / format |
|---|---|---|---|
| `VITE_API_BASE` | Yes for split hosting | Empty = same-origin `/api` | Actual HTTPS Render service origin, e.g. `https://YOUR-API.onrender.com`; trailing slashes are removed. |
| `VITE_CLOUD_ENABLED` | Yes, for account-enabled release | Not enabled | Exact string `true` enables account integration when all three SDK settings below exist. `false` intentionally gives guest-only mode. |
| `VITE_CLERK_PUBLISHABLE_KEY` | Yes for accounts | Unset | Public `pk_test_...` key for the chosen Clerk development instance. Never a Clerk secret key. |
| `VITE_SUPABASE_URL` | Yes for accounts | Unset | Public Supabase project URL, `https://PROJECT.supabase.co`. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Yes for accounts | Unset | Public `sb_publishable_...` key. A legacy public anon key may be placed under this exact variable name; **the app does not read `VITE_SUPABASE_ANON_KEY`**. Never use a service-role or secret key. |

Vite's `MODE`, `DEV`, `PROD`, `BASE_URL` and `SSR` are framework-generated values, not custom settings to enter. Use the normal production build, not the provider-disabled `alpha` build mode. Missing account configuration currently falls back to guest mode; check the resulting deployment rather than assuming a build alone proves accounts are enabled.

## Multi-key format and behavior

```dotenv
GEMINI_API_KEY=YOUR_PRIMARY_KEY
GEMINI_BACKUP_API_KEY_1=YOUR_FIRST_BACKUP_KEY
GEMINI_BACKUP_API_KEY_2=YOUR_SECOND_BACKUP_KEY
```

There is no `GEMINI_API_KEYS`, `GEMINI_API_KEY_1` or comma-separated key setting. Empty keys are skipped, identical key values are deduplicated. Primary → backup 1 → backup 2 applies to Ask, image transcription, inventory, source generation and semantic review. Each distinct key is attempted at most once per stage, with SDK retries disabled.

Rotation occurs for provider HTTP **429, 500, 502, 503, 504**. A quota error reads Retry-After/RetryInfo, defaulting to 60 seconds; transient errors use at least 1.5 seconds of backoff, also respecting shared spacing. A cooling key may be skipped. Authentication/permission errors, validation failures, local admission limits and transport timeouts do **not** rotate keys. Existing stage output is reused when rotating a key; completed extraction/generation is not repeated by that transport step.

`request_control.py` reserves estimated input before dispatch: **15 requests/minute, 250,000 estimated input tokens/minute, 2-second minimum spacing**. Failures are not refunded. For a multi-key Gemini pool, this budget is shared per model across the pool, not multiplied per key. Single-key/provider scopes use a one-way key identity plus model; credentials are never logged. Budgets are process-local and reset on restart, so use one worker. They are conservative local admission controls, not a provider quota dashboard or a daily/project-wide quota tracker. Google quotas apply per project; several keys from one project share those quotas.

Optional alternate-model/OpenRouter/Groq routing is **separate** from key rotation. Source analysis permits one selected secondary analysis pair for an eligible service/timeout/network error, or a mapped provider 5xx. Priority: distinct `GEMINI_FALLBACK_MODEL` → OpenRouter → Groq. It does not try all three. A failed secondary is not routed onward. Exhaustion marked as a configured Gemini-key-pool failure explicitly blocks secondary routing. Generation with a secondary starts a fresh checked source-analysis pair; it is not just a repeat of one failed review call.

With review recovery enabled, a review failure normally returns locally admitted claims and its incomplete-review marker instead of invoking a secondary. General Ask and image transcription do not use the optional secondary-provider source-analysis wrapper. The job deadline is ten minutes; backups cannot remove local limits or extend that deadline. Slot/stage/attempt/timing/outcome are logged, never keys or authorization headers.

## Settings that do not exist here

No `JINA_API_KEY`, OCR/Tesseract configuration, `GEMINI_API_KEYS`, `ANALYSIS_ENABLED` environment flag, Clerk backend secret, Supabase service-role key or Supabase JWT signing secret is consumed by this app. Jina is anonymous and fixed-endpoint; image transcription uses the configured Gemini model. `RESEARCH_DISCOVERY` appeared in an older template but is not read by the current runtime; it has been removed from this template. Do not place provider or signing secrets in Vercel `VITE_` settings.

Clerk's issuer and Supabase's third-party JWT verification belong to their dashboards. The browser passes a Clerk token to Supabase; the API is not a Clerk JWT-verifying backend. Database policies use the token's text `sub` claim as the owner and require the `authenticated` role.

References: [Gemini quotas](https://ai.google.dev/gemini-api/docs/rate-limits), [Clerk + Supabase](https://supabase.com/docs/guides/auth/third-party/clerk).
