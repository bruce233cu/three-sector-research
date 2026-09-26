from __future__ import annotations

from typing import Any, Protocol, Sequence


class SqlExecutor(Protocol):
    def fetch_all(self, sql: str, params: dict[str, Any]) -> Sequence[dict[str, Any]]: ...
    def execute(self, sql: str, params: dict[str, Any]) -> int: ...


class RepositoryError(RuntimeError):
    pass
