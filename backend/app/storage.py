"""Lightweight persistence layer.

A tiny JSON-on-SQLite key/value store keeps the platform dependency-free while
still giving us durable, per-collection storage. Each "collection" is a single
SQLite table of ``(id TEXT PRIMARY KEY, data JSON, created_at, updated_at)``.

This intentionally mirrors the spirit of qstudio's SafeSqliteDict storage but
without the external ``sqlitedict`` dependency, so the repo runs out of the box.
Swap this module for Postgres/DocumentDB in production without touching routers.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import settings

os.makedirs(settings.DB_DIR, exist_ok=True)

_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Collection:
    """A durable, JSON-document keyed store backed by one SQLite table."""

    def __init__(self, name: str):
        self.name = name
        self.path = os.path.join(settings.DB_DIR, f"{name}.sqlite")
        with _LOCK:
            conn = self._connect()
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self.name} ("
                "id TEXT PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
            conn.commit()
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def put(self, doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with _LOCK:
            conn = self._connect()
            existing = conn.execute(
                f"SELECT created_at FROM {self.name} WHERE id = ?", (doc_id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else _now()
            updated_at = _now()
            record = dict(data)
            record["id"] = doc_id
            record.setdefault("created_at", created_at)
            record["updated_at"] = updated_at
            conn.execute(
                f"INSERT INTO {self.name} (id, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (doc_id, json.dumps(record), created_at, updated_at),
            )
            conn.commit()
            conn.close()
            return record

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with _LOCK:
            conn = self._connect()
            row = conn.execute(
                f"SELECT data FROM {self.name} WHERE id = ?", (doc_id,)
            ).fetchone()
            conn.close()
            return json.loads(row["data"]) if row else None

    def list(self) -> List[Dict[str, Any]]:
        with _LOCK:
            conn = self._connect()
            rows = conn.execute(
                f"SELECT data FROM {self.name} ORDER BY created_at DESC"
            ).fetchall()
            conn.close()
            return [json.loads(r["data"]) for r in rows]

    def find(self, **filters: Any) -> List[Dict[str, Any]]:
        """Return documents whose top-level fields match all given filters."""
        results = []
        for doc in self.list():
            if all(doc.get(k) == v for k, v in filters.items()):
                results.append(doc)
        return results

    def delete(self, doc_id: str) -> bool:
        with _LOCK:
            conn = self._connect()
            cur = conn.execute(f"DELETE FROM {self.name} WHERE id = ?", (doc_id,))
            conn.commit()
            deleted = cur.rowcount > 0
            conn.close()
            return deleted


# Collections used across the platform.
projects = Collection("projects")
documents = Collection("documents")          # requirements / context documents (versioned)
templates = Collection("templates")          # test case generation templates
testcases = Collection("testcases")          # generated test cases
generations = Collection("generations")      # generation run records (for trends/audit)
