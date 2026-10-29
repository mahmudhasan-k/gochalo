"""Thread-safe, process-local rolling admission controls; stores no source text or keys."""

from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Callable


@dataclass(frozen=True)
class FreeTierLimits:
    requests_per_minute: int = 15
    input_tokens_per_minute: int = 250_000
    minimum_spacing_seconds: float = 2.0

    def __post_init__(self) -> None:
        if min(self.requests_per_minute, self.input_tokens_per_minute) < 1 or self.minimum_spacing_seconds <= 0:
            raise ValueError("Quota limits must be positive")


class BudgetExceeded(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class _Usage:
    recent: deque[tuple[float, int]] = field(default_factory=deque)


class RequestBudget:
    """Conservative admission guard across sessions in this Python process.

    Scope is a one-way credential fingerprint plus model, never a raw API key.
    Reserve BEFORE network access; failed/uncertain attempts are not refunded.
    These counts are not the provider's remaining quota and reset on restart.
    """

    def __init__(
        self,
        limits: FreeTierLimits = FreeTierLimits(),
        *,
        clock: Callable[[], float] = monotonic,
    ):
        self.limits = limits
        self._clock = clock
        self._lock = Lock()
        self._usage: dict[tuple[str, str], _Usage] = {}

    def wait_seconds(self, scope: tuple[str, str]) -> float:
        """Read the admission delay; reserve still rechecks every limit afterward."""
        with self._lock:
            now = self._clock()
            usage = self._usage.get(scope)
            recent = [stamp for stamp, _ in usage.recent if stamp > now - 60] if usage else []
            if not recent:
                return 0.0
            delay = recent[-1] + self.limits.minimum_spacing_seconds - now
            if len(recent) >= self.limits.requests_per_minute:
                delay = max(delay, recent[0] + 60 - now)
            return max(0.0, delay)

    def reserve(self, scope: tuple[str, str], estimated_input_tokens: int, *, session: "SessionSubmission | None" = None) -> None:
        if estimated_input_tokens < 1:
            raise ValueError("Input token reservation must be positive")
        with self._lock:
            now = self._clock()
            usage = self._usage.setdefault(scope, _Usage())
            while usage.recent and usage.recent[0][0] <= now - 60:
                usage.recent.popleft()
            # Space requests as well as enforcing a rolling minute count.
            if usage.recent and (
                len(usage.recent) >= self.limits.requests_per_minute
                or now - usage.recent[-1][0] < self.limits.minimum_spacing_seconds
            ):
                raise BudgetExceeded("local_rate_limit", "অনুরোধ পাঠানোর সীমা মেনে চলতে একটু অপেক্ষা করতে হবে। পরে চেষ্টা করুন বা প্রস্তুত উদাহরণটি দেখুন।")
            if sum(tokens for _, tokens in usage.recent) + estimated_input_tokens > self.limits.input_tokens_per_minute:
                raise BudgetExceeded("local_token_limit", "এই মিনিটে আনুমানিক ইনপুট টোকেনের সীমা শেষ হয়েছে। পরে চেষ্টা করুন বা প্রস্তুত উদাহরণটি দেখুন।")
            # Failed dispatches remain in the rolling window.
            usage.recent.append((now, estimated_input_tokens))


class SessionSubmission:
    """One pending/in-flight analysis per browser session, including reruns."""

    def __init__(self):
        self._lock = Lock()
        self._busy = False
        self._pending = False

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def queue(self) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = self._pending = True
            return True

    def take_pending(self) -> bool:
        with self._lock:
            pending, self._pending = self._pending, False
            return pending

    def finish(self) -> None:
        with self._lock:
            self._busy = self._pending = False
