"""
Export audit log entries for compliance handoff, backup-before-purge, or
external review — operates directly on the SQLite file, no running server
required, so it works against a backed-up copy per the evidence-handling
policy referenced in README's Security & Deployment Notes.

Deliberately read-only: this is an export tool, not a retention/redaction
tool. Deciding what to purge or redact and when is an organizational policy
question this project can't answer for you: adding automatic deletion
speculatively is more likely to delete evidence you needed than to save you
work. Reach for the audit_log.db backup + this export if you need to hand
records to a downstream system that does that job.

Usage:
    python export_audit_log.py --format csv --output export.csv
    python export_audit_log.py --format json --since 2026-01-01 --until 2026-06-30
    python export_audit_log.py --file-hash <sha256>
"""

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone

DEFAULT_DB_PATH = "audit_log.db"

COLUMNS = [
    "id", "timestamp", "file_sha256", "filename", "media_type", "verdict",
    "confidence", "probability", "frames_analyzed", "model_version", "processing_sec",
]


def _parse_date(value: str) -> float:
    """Accepts YYYY-MM-DD, treated as UTC midnight."""
    dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt.timestamp()


def fetch_rows(db_path: str, since: str | None, until: str | None, file_hash: str | None) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []
        if since:
            query += " AND timestamp >= ?"
            params.append(_parse_date(since))
        if until:
            query += " AND timestamp < ?"
            params.append(_parse_date(until))
        if file_hash:
            query += " AND file_sha256 = ?"
            params.append(file_hash)
        query += " ORDER BY id ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def write_csv(rows: list[dict], out) -> None:
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in COLUMNS})


def write_json(rows: list[dict], out) -> None:
    json.dump(rows, out, indent=2)
    out.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"Path to the audit log SQLite file (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--format", choices=["csv", "json"], default="csv")
    parser.add_argument("--since", help="Only entries on/after this date (YYYY-MM-DD, UTC)")
    parser.add_argument("--until", help="Only entries before this date (YYYY-MM-DD, UTC)")
    parser.add_argument("--file-hash", help="Only entries for this exact SHA-256 file hash")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    rows = fetch_rows(args.db, args.since, args.until, args.file_hash)

    out = open(args.output, "w", newline="" if args.format == "csv" else None, encoding="utf-8") if args.output else sys.stdout
    try:
        if args.format == "csv":
            write_csv(rows, out)
        else:
            write_json(rows, out)
    finally:
        if args.output:
            out.close()

    print(f"Exported {len(rows)} entries.", file=sys.stderr)


if __name__ == "__main__":
    main()
