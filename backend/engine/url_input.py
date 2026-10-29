"""Standalone, anonymous Jina extraction. No Streamlit/Gemini imports or persistence.

Only the fixed Jina endpoint receives HTTP traffic. DNS admission checks do not
control redirects/subresources inside Jina; returned URLs are attribution only.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from ipaddress import ip_address
import json
import math
import re
import socket
from threading import Lock
from time import monotonic
from typing import Awaitable, Callable
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

import httpx
from portal_content import portal_text
from evaluation_trace import record as record_trace

JINA_ENDPOINT = "https://r.jina.ai/"
MAX_URL_CHARACTERS = 4096
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 50_000
MAX_ANALYSIS_CHARACTERS = 50_000
TOTAL_TIMEOUT_SECONDS = 45
_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_SENSITIVE_PARAMETERS = frozenset({
    "token", "accesstoken", "refreshtoken", "authtoken", "idtoken", "apikey",
    "key", "password", "passwd", "secret", "signature", "sig", "authorization",
    "session", "sessionid", "jwt", "nid", "passport", "passportnumber",
    "birthregistration", "birthregistrationnumber", "brn",
})
_BLOCKED_PAGE = re.compile(
    r"access denied|verify (?:that )?you are human|checking your browser|"
    r"enable javascript and cookies|just a moment\.\.\.|captcha challenge",
    re.IGNORECASE,
)


class ExtractionError(Exception):
    """Fixed public code; no target URL, response body or underlying exception."""

    def __init__(self, code: str, *, retry_after: int | None = None):
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    text: str = field(repr=False)
    requested_url: str = field(repr=False)
    returned_url: str | None = field(repr=False)
    retrieved_at: datetime
    title: str = field(default="", repr=False)
    warnings: tuple[str, ...] = ("review_required",)


@dataclass(frozen=True, slots=True)
class ReviewedSource:
    """For later integration: pass ONLY text to the existing Gemini function."""

    text: str = field(repr=False)
    requested_url: str = field(repr=False)
    returned_url: str | None = field(repr=False)
    retrieved_at: datetime
    was_edited: bool


def prepare_source(result: ExtractionResult, text: str, *, reviewed: bool) -> ReviewedSource:
    if reviewed is not True:
        raise ExtractionError("review_required")
    if not isinstance(text, str) or not text.strip():
        raise ExtractionError("empty_content")
    if len(text) > MAX_ANALYSIS_CHARACTERS:
        raise ExtractionError("analysis_too_long")
    return ReviewedSource(text, result.requested_url, result.returned_url,
                          result.retrieved_at, text != result.text)


def normalize_url(value: str) -> str:
    """Public DNS-host admission; preserve path/query and strip page fragments."""
    if not isinstance(value, str) or len(value) > MAX_URL_CHARACTERS:
        raise ExtractionError("invalid_url")
    value = value.strip()
    if not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise ExtractionError("invalid_url")
    decoded = unquote(value)
    if "\\" in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise ExtractionError("invalid_url")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port = parts.port
        if (parts.scheme.lower() not in {"http", "https"} or not _HOST.fullmatch(host)
                or len(host) > 253 or parts.username is not None or parts.password is not None
                or parts.netloc.endswith(":")):
            raise ValueError
        if port is not None and port != (443 if parts.scheme.lower() == "https" else 80):
            raise ValueError
        parameters = parse_qsl(parts.query, keep_blank_values=True, max_num_fields=100)
    except (ValueError, UnicodeError):
        raise ExtractionError("invalid_url") from None
    for key, _ in parameters:
        key = re.sub(r"[^a-z0-9]", "", key.lower())
        if key in _SENSITIVE_PARAMETERS or key.startswith(("xamz", "xgoog")):
            raise ExtractionError("private_url")
    # httpx encodes Bangla paths without translating or modifying extracted text.
    normalized = urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))
    try:
        return str(httpx.URL(normalized))
    except httpx.InvalidURL:
        raise ExtractionError("invalid_url") from None


async def _resolve(host: str) -> tuple[str, ...]:
    entries = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return tuple({entry[4][0] for entry in entries})


Resolver = Callable[[str], Awaitable[tuple[str, ...]]]


async def _public_url(value: str, resolver: Resolver) -> str:
    normalized = normalize_url(value)
    try:
        addresses = await resolver(urlsplit(normalized).hostname or "")
    except (OSError, ValueError):
        raise ExtractionError("dns_error") from None
    if not addresses:
        raise ExtractionError("dns_error")
    for address in addresses:
        try:
            parsed = ip_address(address)
        except ValueError:
            raise ExtractionError("private_url") from None
        if not parsed.is_global or parsed.is_multicast:
            raise ExtractionError("private_url")
    return normalized


class ExtractionSession:
    """Separate from Gemini accounting; one in-flight extraction per session."""

    def __init__(self):
        self._lock = Lock()
        self._busy = False

    def begin(self) -> None:
        with self._lock:
            if self._busy:
                raise ExtractionError("busy")
            self._busy = True

    def finish(self) -> None:
        with self._lock:
            self._busy = False


class ExtractionBudget:
    """Anonymous, process-local rolling admission control. No URLs, source text or credentials stored."""

    def __init__(self, *, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._lock = Lock()
        self._recent: deque[float] = deque()
        self._blocked_until = 0.0

    def reserve(self, session: ExtractionSession) -> None:
        with self._lock:
            now = self._clock()
            if now < self._blocked_until:
                raise ExtractionError("rate_limit", retry_after=math.ceil(self._blocked_until - now))
            while self._recent and self._recent[0] <= now - 60:
                self._recent.popleft()
            if self._recent and (len(self._recent) >= 15 or now - self._recent[-1] < 2):
                delay = max(2 - (now - self._recent[-1]),
                            60 - (now - self._recent[0]) if len(self._recent) >= 15 else 0)
                raise ExtractionError("rate_limit", retry_after=max(1, math.ceil(delay)))
            self._recent.append(now)

    def defer(self, seconds: int) -> None:
        with self._lock:
            self._blocked_until = max(self._blocked_until, self._clock() + seconds)


DEFAULT_BUDGET = ExtractionBudget()


def _retry_after(value: str | None) -> int:
    try:
        if value and value.isascii() and value.isdigit():
            seconds = int(value)
        else:
            timestamp = parsedate_to_datetime(value or "")
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            seconds = math.ceil((timestamp - datetime.now(timezone.utc)).total_seconds())
        # Cap extreme values at a week; malformed values use a minute below.
        return max(1, seconds) if seconds <= 604_800 else 604_800
    except (ValueError, TypeError, OverflowError):
        return 60


def _http_error(status: int, retry: str | None, budget: ExtractionBudget) -> None:
    if status == 429:
        delay = _retry_after(retry)
        budget.defer(delay)
        raise ExtractionError("rate_limit", retry_after=delay)
    if status in {408, 504}:
        raise ExtractionError("timeout")
    if 500 <= status <= 599:
        raise ExtractionError("service_busy")
    if status in {401, 402, 403, 451}:
        raise ExtractionError("access_denied")
    raise ExtractionError("fetch_failed")


async def extract_url(value: str, *, session: ExtractionSession,
                      budget: ExtractionBudget = DEFAULT_BUDGET,
                      transport: httpx.AsyncBaseTransport | None = None,
                      resolver: Resolver = _resolve) -> ExtractionResult:
    """One anonymous request, bounded response and deadline; never retries.

    The injected transport/resolver exist for offline tests. Never supply a client
    with inherited authentication, cookies, proxy environment or credentials.
    """
    session.begin()
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
            url = await _public_url(value, resolver)
            budget.reserve(session)
            headers = {
                "Accept": "application/json", "Accept-Encoding": "identity",
                "DNT": "1", "X-No-Cache": "true", "X-Timeout": "20",
                "X-Respond-With": "markdown", "X-With-Generated-Alt": "false",
                "X-Retain-Images": "none", "X-Retain-Media": "none",
            }
            # Modern National Portal custom rt-renderer elements can disappear
            # from Reader's Markdown. Request source HTML once, then project the
            # known content widget locally; never fetch a second extraction.
            portal = urlsplit(url).hostname.endswith(".gov.bd") and urlsplit(url).path.startswith("/pages/")
            if portal:
                headers["X-Respond-With"] = "html"
                headers["X-Respond-Timing"] = "html"
            async with httpx.AsyncClient(
                transport=transport, trust_env=False, follow_redirects=False,
                timeout=httpx.Timeout(30, connect=5, pool=5, write=5),
            ) as client:
                record_trace("jina_retrieval",event="dispatch",url=url)
                async with client.stream("POST", JINA_ENDPOINT, json={"url": url}, headers=headers) as response:
                    record_trace("jina_retrieval",event="response",http_status=response.status_code)
                    if response.status_code != 200:
                        _http_error(response.status_code, response.headers.get("Retry-After"), budget)
                    if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        raise ExtractionError("malformed_response")
                    # Refuse compressed payloads: a decoded-byte check alone may
                    # allocate a decompression bomb before the first yielded chunk.
                    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise ExtractionError("malformed_response")
                    length = response.headers.get("Content-Length")
                    if length is not None:
                        try:
                            size = int(length)
                        except ValueError:
                            raise ExtractionError("malformed_response") from None
                        if size < 0:
                            raise ExtractionError("malformed_response")
                        if size > MAX_RESPONSE_BYTES:
                            raise ExtractionError("response_too_large")
                    body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ExtractionError("response_too_large")
                        body.extend(chunk)
            try:
                payload = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeError, RecursionError):
                raise ExtractionError("malformed_response") from None
            if not isinstance(payload, dict) or type(payload.get("code")) is not int:
                raise ExtractionError("malformed_response")
            if payload["code"] != 200:
                _http_error(payload["code"], None, budget)
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ExtractionError("malformed_response")
            raw = data.get("html", data.get("content")) if portal else data.get("content")
            if not isinstance(raw, str):
                raise ExtractionError("malformed_response")
            # A Reader warning is not proof the returned passage is unusable.
            # Continue to inspect the text itself; keep all network/size guards.
            text = portal_text(raw, url) if portal and re.search(r"<[a-zA-Z][^>]*>", raw) else raw
            if len(text) > MAX_EXTRACTED_CHARACTERS:
                raise ExtractionError("text_too_long")
            # Image/link syntax must not make an image-only scan look readable.
            # Keep this low: Bangla vowel marks are not counted by isalnum(), and
            # a short notice can still contain a useful deadline.
            substantive = re.sub(r"!\[[^\]]*\]\([^\n)]*\)", "", text)
            if not text.strip() or sum(c.isalnum() for c in substantive) < 10:
                raise ExtractionError("empty_content")
            title = data.get("title", "")
            if not isinstance(title, str):
                raise ExtractionError("malformed_response")
            if (_BLOCKED_PAGE.search(text[:500])
                    or text.count("\ufffd") > max(3, len(text) // 100)):
                raise ExtractionError("incomplete_content")
            returned = data.get("url")
            if returned is not None:
                if not isinstance(returned, str):
                    raise ExtractionError("malformed_response")
                returned = await _public_url(returned, resolver)
            warnings = ("review_required",) if returned else ("review_required", "destination_unknown")
            return ExtractionResult(text, url, returned, datetime.now(timezone.utc), title[:250], warnings)
    except ExtractionError:
        raise
    except (TimeoutError, httpx.TimeoutException):
        raise ExtractionError("timeout") from None
    except httpx.HTTPError:
        raise ExtractionError("network_error") from None
    finally:
        session.finish()
