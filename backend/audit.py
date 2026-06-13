"""
Append-only audit log for forensic chain-of-custody purposes.

Every analysis request is recorded with: file hash (SHA-256), filename,
timestamp, verdict, confidence, model version, and processing time.
The file hash means the same input file always produces a traceable record
even if uploaded under a different filename.

Storage: SQLite at AUDIT_DB_PATH (default ./audit_log.db). For higher-volume
deployments this could be swapped for Postgres without changing the calling
code, since only `log_analysis` and `get_recent` are used externally.
"""

import os
import sqlite3
import hashlib
import time
from contextlib import contextmanager

AUDIT_DB_PATH = os.getenv("AUDIT_DB_PATH", "audit_log.db")


def _init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL    NOT NULL,
                file_sha256     TEXT    NOT NULL,
                filename        TEXT    NOT NULL,
                media_type      TEXT    NOT NULL,
                verdict         TEXT    NOT NULL,
                confidence      REAL    NOT NULL,
                probability     REAL    NOT NULL,
                frames_analyzed INTEGER NOT NULL,
                model_version   TEXT    NOT NULL,
                processing_sec  REAL    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_hash ON audit_log(file_sha256)")
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(AUDIT_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


_init_db()


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def log_analysis(file_bytes: bytes, filename: str, result: dict, model_version: str = "2.0.0"):
    """Record one analysis result. Best-effort — logging failures must never
    block the API response, so errors are swallowed and printed."""
    try:
        file_hash = sha256_of_bytes(file_bytes)
        with _connect() as conn:
            conn.execute(
                """INSERT INTO audit_log
                   (timestamp, file_sha256, filename, media_type, verdict,
                    confidence, probability, frames_analyzed, model_version, processing_sec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    time.time(),
                    file_hash,
                    filename,
                    result.get("type", "unknown"),
                    result.get("verdict", "UNKNOWN"),
                    result.get("confidence", 0.0),
                    result.get("probability", 0.0),
                    result.get("frames_analyzed", 0),
                    model_version,
                    result.get("processing_time_sec", 0.0),
                ),
            )
            conn.commit()
        return file_hash
    except Exception as e:
        print(f"[Audit] Failed to log analysis: {e}")
        return None


def get_recent(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_by_hash(file_hash: str) -> list[dict]:
    """Return all past analyses for a given file hash — useful for
    'has this exact file been analysed before' checks."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE file_sha256 = ? ORDER BY id DESC", (file_hash,)
        ).fetchall()
        return [dict(r) for r in rows]
