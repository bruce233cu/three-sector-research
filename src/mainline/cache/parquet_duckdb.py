from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


@dataclass(frozen=True)
class CacheArtifact:
    dataset: str
    cache_key: str
    parquet_path: str
    metadata_path: str
    source_id: str
    source_version: str
    fetched_at: str
    checksum_sha256: str
    row_count: int


class ParquetDuckDBCache:
    """Disposable, checksummed Parquet cache queried through DuckDB.

    The cache is deliberately outside Supabase.  Every artifact has a sidecar
    manifest so a calculation can prove exactly which bytes it consumed.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        dataset: str,
        cache_key: str,
        frame: pd.DataFrame,
        *,
        source_id: str,
        source_version: str,
        fetched_at: datetime | None = None,
    ) -> CacheArtifact:
        if not source_version:
            raise ValueError("source_version is required")
        fetched = (fetched_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        folder = self.root / dataset
        folder.mkdir(parents=True, exist_ok=True)
        safe_key = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]
        parquet_path = folder / f"{safe_key}.parquet"
        metadata_path = folder / f"{safe_key}.json"

        fd, temp_name = tempfile.mkstemp(prefix=f".{safe_key}.", suffix=".parquet", dir=folder)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            frame.to_parquet(temp_path, index=False)
            checksum = hashlib.sha256(temp_path.read_bytes()).hexdigest()
            temp_path.replace(parquet_path)
        finally:
            temp_path.unlink(missing_ok=True)

        artifact = CacheArtifact(
            dataset=dataset,
            cache_key=cache_key,
            parquet_path=str(parquet_path),
            metadata_path=str(metadata_path),
            source_id=source_id,
            source_version=source_version,
            fetched_at=fetched.isoformat().replace("+00:00", "Z"),
            checksum_sha256=checksum,
            row_count=len(frame),
        )
        payload = asdict(artifact)
        payload["columns"] = list(frame.columns)
        temp_meta = metadata_path.with_suffix(".json.tmp")
        temp_meta.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temp_meta.replace(metadata_path)
        return artifact

    def read(self, artifact: CacheArtifact) -> pd.DataFrame:
        path = Path(artifact.parquet_path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != artifact.checksum_sha256:
            raise ValueError(f"cache checksum mismatch: {artifact.cache_key}")
        with duckdb.connect(database=":memory:") as con:
            return con.execute("select * from read_parquet(?)", [str(path)]).fetch_df()

    def delete(self, artifact: CacheArtifact) -> None:
        Path(artifact.parquet_path).unlink(missing_ok=True)
        Path(artifact.metadata_path).unlink(missing_ok=True)
