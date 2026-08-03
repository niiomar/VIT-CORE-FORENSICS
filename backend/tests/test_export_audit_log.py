import csv
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import export_audit_log  # noqa: E402


def _make_db(rows):
    """Builds a throwaway audit_log.db with the same schema as audit.py,
    independent of the real audit module so this test doesn't depend on
    import side effects (audit.py's module-level _init_db() call)."""
    import sqlite3
    path = os.path.join(tempfile.mkdtemp(prefix="export_test_"), "audit_log.db")
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE audit_log (
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
    for r in rows:
        conn.execute(
            """INSERT INTO audit_log
               (timestamp, file_sha256, filename, media_type, verdict, confidence,
                probability, frames_analyzed, model_version, processing_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            r,
        )
    conn.commit()
    conn.close()
    return path


ROWS = [
    (1717200000.0, "hash1", "a.jpg", "jpg", "REAL", 91.0, 0.09, 1, "2.1.0", 0.4),
    (1719878400.0, "hash2", "b.mp4", "mp4", "FAKE", 88.0, 0.88, 8, "2.1.0", 1.8),
    (1722556800.0, "hash1", "a.jpg", "jpg", "REAL", 91.0, 0.09, 1, "2.1.0", 0.4),
]


def test_fetch_rows_returns_everything_by_default():
    db = _make_db(ROWS)
    rows = export_audit_log.fetch_rows(db, since=None, until=None, file_hash=None)
    assert len(rows) == 3


def test_fetch_rows_filters_by_date_range():
    db = _make_db(ROWS)
    # 1719878400 = 2024-07-02T00:00:00Z; window excludes the first and third rows
    rows = export_audit_log.fetch_rows(db, since="2024-07-01", until="2024-07-03", file_hash=None)
    assert len(rows) == 1
    assert rows[0]["file_sha256"] == "hash2"


def test_fetch_rows_filters_by_file_hash():
    db = _make_db(ROWS)
    rows = export_audit_log.fetch_rows(db, since=None, until=None, file_hash="hash1")
    assert len(rows) == 2
    assert all(r["file_sha256"] == "hash1" for r in rows)


def test_write_csv_round_trips_all_columns():
    db = _make_db(ROWS)
    rows = export_audit_log.fetch_rows(db, None, None, None)
    buf = io.StringIO()
    export_audit_log.write_csv(rows, buf)
    buf.seek(0)
    reader = list(csv.DictReader(buf))
    assert len(reader) == 3
    assert set(reader[0].keys()) == set(export_audit_log.COLUMNS)
    assert reader[1]["filename"] == "b.mp4"


def test_write_json_produces_valid_json():
    db = _make_db(ROWS)
    rows = export_audit_log.fetch_rows(db, None, None, None)
    buf = io.StringIO()
    export_audit_log.write_json(rows, buf)
    parsed = json.loads(buf.getvalue())
    assert len(parsed) == 3
    assert parsed[0]["verdict"] == "REAL"
