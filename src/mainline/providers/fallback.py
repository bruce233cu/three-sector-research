from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Callable

from .base import MarketDataProvider, ProviderBatch, ProviderError


@dataclass(frozen=True)
class Attempt:
    source_id: str
    attempt: int
    status: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class FallbackResult:
    batch: ProviderBatch
    source_used: str
    attempts: tuple[Attempt, ...]
    fallback_used: bool
    backup_unavailable: bool = False


class FallbackExecutor:
    def __init__(
        self,
        primary: MarketDataProvider,
        backup: MarketDataProvider | None,
        *,
        retry_backoff_seconds: tuple[float, ...] = (2, 5, 15),
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.primary = primary
        self.backup = backup
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleeper = sleeper

    def execute(self, method_name: str, *args, **kwargs) -> FallbackResult:
        attempts: list[Attempt] = []
        primary_method = getattr(self.primary, method_name)
        last_error: ProviderError | None = None
        delays = (0.0,) + self.retry_backoff_seconds
        for number, delay in enumerate(delays, start=1):
            if delay:
                self.sleeper(delay)
            try:
                batch = primary_method(*args, **kwargs).validate()
                attempts.append(Attempt(self.primary.source_id, number, "success"))
                return FallbackResult(batch, self.primary.source_id, tuple(attempts), False)
            except ProviderError as error:
                last_error = error
                attempts.append(Attempt(self.primary.source_id, number, "failed", error.code, str(error)))
                pass

        if self.backup is None:
            raise CapabilityErrorWithAttempts("backup_unavailable", attempts, last_error)
        backup_method = getattr(self.backup, method_name)
        try:
            batch = backup_method(*args, **kwargs).validate()
            attempts.append(Attempt(self.backup.source_id, 1, "success"))
            return FallbackResult(batch, self.backup.source_id, tuple(attempts), True)
        except ProviderError as error:
            attempts.append(Attempt(self.backup.source_id, 1, "failed", error.code, str(error)))
            raise CapabilityErrorWithAttempts("primary_and_backup_failed", attempts, error) from error


class CapabilityErrorWithAttempts(ProviderError):
    code = "FALLBACK_EXHAUSTED"

    def __init__(self, message: str, attempts: list[Attempt], cause: Exception | None) -> None:
        super().__init__(message)
        self.attempts = tuple(attempts)
        self.cause = cause
