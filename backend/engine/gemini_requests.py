"""Bounded server-only Gemini quota/service failover; no SDK retries."""
from contextvars import ContextVar
from hashlib import sha256
import json
import logging
import math
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
from time import monotonic

from google.genai import errors, types
from evaluation_trace import record

attempt_log = ContextVar("gemini_attempt_log", default=None)
job_deadline = ContextVar("gemini_job_deadline", default=None)
_cooldowns = {}
_lock = Lock()
_logger = logging.getLogger(__name__)


def reset_cooldowns():
    with _lock:
        _cooldowns.clear()


def _remaining():
    deadline = job_deadline.get()
    return None if deadline is None else deadline - monotonic()


def _check_deadline(delay=0):
    import ai_service as ai
    remaining = _remaining()
    if remaining is not None and remaining <= float(delay):
        raise ai.AnalysisError("job_timeout", "The operation reached its time limit.")


def _cooldown(error):
    """Read RetryInfo only; never log provider messages or arbitrary details."""
    headers = getattr(getattr(error, "response", None), "headers", {})
    retry = headers.get("Retry-After")
    if retry:
        try:
            seconds = float(retry)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 60
        if math.isfinite(seconds):
            return max(1, seconds)
    details = error.details if isinstance(error.details, dict) else {}
    payload = details.get("error", details)
    for item in payload.get("details", []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and str(item.get("@type", "")).endswith("RetryInfo"):
            value = item.get("retryDelay", "")
            try:
                seconds = float(str(value).removesuffix("s"))
                if math.isfinite(seconds):
                    return max(1, seconds)
            except ValueError:
                pass
    return 60


def generate(settings, *, contents, config, stage, tokens, timeout_ms=60_000, session=None):
    # Import at dispatch time so existing offline SDK transports remain effective.
    import ai_service as ai
    keys = [("primary", settings.api_key.get_secret_value())]
    keys += [(f"backup_{i}", os.environ.get(f"GEMINI_BACKUP_API_KEY_{i}", "").strip()) for i in (1, 2)]
    backups_configured = any(key for _, key in keys[1:])
    unique, seen = [], set()
    for slot, key in keys:
        if key and key not in seen:
            unique.append((slot, key)); seen.add(key)
    # A conservative shared pool budget does not multiply local allowance by key count.
    scope = ("gemini-key-pool" if len(unique) > 1 else sha256(unique[0][1].encode()).hexdigest(), settings.model)
    last_error = None
    attempt = 0
    for slot, key in unique:
        _check_deadline()
        identity = sha256(key.encode()).digest()
        if len(unique) > 1:
            with _lock:
                if _cooldowns.get(identity, 0) > monotonic():
                    continue
        delay = ai.REQUEST_BUDGET.wait_seconds(scope)
        if last_error is not None and last_error.code != 429:
            delay = max(delay, 1.5)
        _check_deadline(delay)
        if delay:
            ai.sleep(delay)
        ai.REQUEST_BUDGET.reserve(scope, tokens, session=session)
        remaining = _remaining()
        timeout = timeout_ms if remaining is None else min(timeout_ms, max(1, int(remaining * 1000)))
        started = monotonic()
        attempt += 1
        event = dict(stage=stage, slot=slot, attempt=attempt, outcome="failed", duration_ms=0)
        ledger = attempt_log.get()
        if ledger is not None:
            event["attempt"] = 1 + sum(e["stage"] == stage for e in ledger)
        try:
            record(stage, event="dispatch", slot=slot, model=settings.model, input=contents)
            with ai.genai.Client(vertexai=False, api_key=key,
                    http_options=types.HttpOptions(api_version=ai.API_VERSION, timeout=timeout,
                        retry_options=types.HttpRetryOptions(attempts=1))) as client:
                response = client.models.generate_content(model=settings.model, contents=contents, config=config)
            _check_deadline()
            event["outcome"] = "completed"
            record(stage, event="response", slot=slot, output=response.text or "")
            return response
        except errors.APIError as error:
            if error.code not in {429, 500, 502, 503, 504}:
                # Diagnostic capture contains only the allowlisted fixed
                # provider summary. Never store the raw message/body/details.
                record(stage, event="provider_error",
                       diagnostics=ai.provider_diagnostics(error, model=settings.model).model_dump())
                raise
            event["outcome"] = "usage_limit" if error.code == 429 else "timeout" if error.code == 504 else "service_busy"
            record(stage, event="provider_error",
                   diagnostics=ai.provider_diagnostics(error, model=settings.model).model_dump())
            last_error = error
            if len(unique) > 1:
                with _lock:
                    _cooldowns[identity] = monotonic() + (_cooldown(error) if error.code == 429 else 1.5)
        finally:
            event["duration_ms"] = round((monotonic() - started) * 1000)
            if ledger is not None:
                ledger.append(event)
            _logger.info("Gemini attempt %s", json.dumps(event))
            record(stage, event="attempt", **{k:v for k,v in event.items() if k != "stage"})
    if last_error is not None:
        if backups_configured:
            code = "rate_limit_or_quota" if last_error.code == 429 else "timeout" if last_error.code == 504 else "service_busy"
            raise ai.AnalysisError(code, "Configured credentials could not complete this stage.",
                diagnostics=ai.provider_diagnostics(last_error, model=settings.model), quota_pool_exhausted=True) from None
        raise last_error
    raise ai.AnalysisError("rate_limit_or_quota", "Configured credentials are temporarily unavailable.", quota_pool_exhausted=True)
