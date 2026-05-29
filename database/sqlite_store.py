"""NexusSupply AI — SQLite Database Layer.

Handles structured supplier data, dataset versioning,
audit logging, and governance check persistence.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DB_PATH, CURRENT_DATASET_VERSION


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path: Path = DB_PATH) -> None:
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id       TEXT PRIMARY KEY,
    supplier_name     TEXT NOT NULL,
    component_name    TEXT NOT NULL,
    component_category TEXT NOT NULL,
    supplier_region   TEXT NOT NULL,
    country           TEXT NOT NULL,
    approved_vendor_status TEXT NOT NULL CHECK(approved_vendor_status IN ('AVL', 'Non-AVL')),
    lead_time_days    INTEGER NOT NULL CHECK(lead_time_days > 0),
    sourcing_tier     TEXT NOT NULL CHECK(sourcing_tier IN ('Tier 1', 'Tier 2', 'Tier 3')),
    contract_end_date TEXT NOT NULL,
    moq               INTEGER NOT NULL CHECK(moq > 0),
    sourcing_allocation_cap REAL NOT NULL CHECK(sourcing_allocation_cap >= 0 AND sourcing_allocation_cap <= 1),
    headroom_capacity_units INTEGER NOT NULL CHECK(headroom_capacity_units >= 0),
    historical_reliability_score REAL NOT NULL CHECK(historical_reliability_score >= 0 AND historical_reliability_score <= 1),
    risk_score        REAL NOT NULL CHECK(risk_score >= 0 AND risk_score <= 1),
    dataset_version   TEXT NOT NULL DEFAULT 'v1.0',
    ingested_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    version_id    TEXT PRIMARY KEY,
    dataset_name  TEXT NOT NULL,
    record_count  INTEGER NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    status        TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'superseded', 'archived'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    dataset_name TEXT,
    dataset_version TEXT,
    details     TEXT,
    record_count INTEGER,
    valid_count  INTEGER,
    quarantined_count INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quarantined_records (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_name   TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    raw_data       TEXT NOT NULL,
    error_message  TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


# ── Supplier Operations ───────────────────────────────────────────────


def upsert_suppliers(records: list[dict], version: str = CURRENT_DATASET_VERSION) -> int:
    """Insert or replace supplier records. Returns count of rows written."""
    conn = get_connection()
    try:
        for rec in records:
            rec["dataset_version"] = version
            rec["ingested_at"] = datetime.utcnow().isoformat()
        df = pd.DataFrame(records)
        df.to_sql("suppliers", conn, if_exists="replace", index=False)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def get_suppliers_by_component(component_name: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM suppliers WHERE component_name = ? ORDER BY risk_score ASC",
            (component_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_suppliers_by_region(region: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM suppliers WHERE supplier_region LIKE ? OR country LIKE ?",
            (f"%{region}%", f"%{region}%"),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_avl_suppliers_for_component(component_name: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM suppliers
               WHERE component_name = ?
               AND approved_vendor_status = 'AVL'
               AND contract_end_date >= date('now')
               ORDER BY risk_score ASC, historical_reliability_score DESC""",
            (component_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_suppliers() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM suppliers ORDER BY supplier_id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Audit & Versioning ────────────────────────────────────────────────


def log_audit_event(
    event_type: str,
    dataset_name: str = "",
    dataset_version: str = "",
    details: str = "",
    record_count: int = 0,
    valid_count: int = 0,
    quarantined_count: int = 0,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO audit_log
               (event_type, dataset_name, dataset_version, details,
                record_count, valid_count, quarantined_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_type, dataset_name, dataset_version, details,
             record_count, valid_count, quarantined_count),
        )
        conn.commit()
    finally:
        conn.close()


def save_dataset_version(version_id: str, dataset_name: str, record_count: int) -> None:
    conn = get_connection()
    try:
        # Supersede previous versions
        conn.execute(
            "UPDATE dataset_versions SET status = 'superseded' WHERE dataset_name = ? AND status = 'active' AND version_id != ?",
            (dataset_name, version_id),
        )
        conn.execute(
            "INSERT OR REPLACE INTO dataset_versions (version_id, dataset_name, record_count, status) VALUES (?, ?, ?, 'active')",
            (version_id, dataset_name, record_count),
        )
        conn.commit()
    finally:
        conn.close()


def quarantine_record(dataset_name: str, version: str, raw_data: str, error: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO quarantined_records (dataset_name, dataset_version, raw_data, error_message) VALUES (?, ?, ?, ?)",
            (dataset_name, version, raw_data, error),
        )
        conn.commit()
    finally:
        conn.close()


def get_audit_log(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
