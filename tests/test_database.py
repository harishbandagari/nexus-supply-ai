"""Tests for NexusSupply AI — SQLite Database Layer.

Tests database operations:
- Schema initialization
- Supplier CRUD operations
- Audit logging
- Dataset versioning
- Quarantine system
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import date

from database.sqlite_store import (
    get_connection,
    init_database,
    upsert_suppliers,
    get_suppliers_by_component,
    get_suppliers_by_region,
    get_avl_suppliers_for_component,
    get_all_suppliers,
    log_audit_event,
    save_dataset_version,
    quarantine_record,
    get_audit_log,
)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create a temporary test database and patch get_connection."""
    db_path = tmp_path / "test_nexus.db"
    init_database(db_path)

    def _patched_connection(path=None):
        return get_connection(db_path)

    monkeypatch.setattr("database.sqlite_store.get_connection", _patched_connection)
    return db_path


@pytest.fixture
def sample_suppliers():
    """Sample supplier records for testing."""
    return [
        {
            "supplier_id": "SUP-001",
            "supplier_name": "Shenzhen FlexCircuit Co.",
            "component_name": "Flexible Printed Circuits",
            "component_category": "Interconnect",
            "supplier_region": "Shenzhen",
            "country": "China",
            "approved_vendor_status": "AVL",
            "lead_time_days": 21,
            "sourcing_tier": "Tier 1",
            "contract_end_date": "2027-03-31",
            "moq": 5000,
            "sourcing_allocation_cap": 0.35,
            "headroom_capacity_units": 120000,
            "historical_reliability_score": 0.92,
            "risk_score": 0.68,
        },
        {
            "supplier_id": "SUP-004",
            "supplier_name": "Taiwan Semiconductor Materials",
            "component_name": "Gallium Arsenide Wafers",
            "component_category": "Semiconductor Materials",
            "supplier_region": "Hsinchu",
            "country": "Taiwan",
            "approved_vendor_status": "AVL",
            "lead_time_days": 42,
            "sourcing_tier": "Tier 1",
            "contract_end_date": "2028-01-31",
            "moq": 1000,
            "sourcing_allocation_cap": 0.25,
            "headroom_capacity_units": 30000,
            "historical_reliability_score": 0.95,
            "risk_score": 0.45,
        },
        {
            "supplier_id": "SUP-009",
            "supplier_name": "Vietnam Precision Electronics",
            "component_name": "Flexible Printed Circuits",
            "component_category": "Interconnect",
            "supplier_region": "Ho Chi Minh City",
            "country": "Vietnam",
            "approved_vendor_status": "Non-AVL",
            "lead_time_days": 28,
            "sourcing_tier": "Tier 2",
            "contract_end_date": "2025-12-31",
            "moq": 10000,
            "sourcing_allocation_cap": 0.15,
            "headroom_capacity_units": 50000,
            "historical_reliability_score": 0.78,
            "risk_score": 0.55,
        },
    ]


# ── Schema Initialization ─────────────────────────────────────────────


class TestDatabaseInit:
    def test_creates_tables(self, test_db):
        conn = sqlite3.connect(str(test_db))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        conn.close()

        assert "suppliers" in table_names
        assert "dataset_versions" in table_names
        assert "audit_log" in table_names
        assert "quarantined_records" in table_names

    def test_idempotent_init(self, test_db):
        """Calling init_database twice should not error."""
        init_database(test_db)
        init_database(test_db)

    def test_wal_mode_enabled(self, test_db):
        conn = get_connection(test_db)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"


# ── Supplier CRUD ─────────────────────────────────────────────────────


class TestSupplierOperations:
    def test_upsert_suppliers(self, test_db, sample_suppliers):
        count = upsert_suppliers(sample_suppliers, "v1.0")
        assert count == 3

    def test_get_all_suppliers(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_all_suppliers()
        assert len(results) == 3

    def test_get_suppliers_by_component(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_suppliers_by_component("Flexible Printed Circuits")
        assert len(results) == 2
        assert all(r["component_name"] == "Flexible Printed Circuits" for r in results)

    def test_get_suppliers_by_region(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_suppliers_by_region("Shenzhen")
        assert len(results) >= 1
        assert any(r["supplier_id"] == "SUP-001" for r in results)

    def test_get_avl_suppliers_for_component(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_avl_suppliers_for_component("Flexible Printed Circuits")
        # Only AVL suppliers with valid contracts
        for r in results:
            assert r["approved_vendor_status"] == "AVL"

    def test_non_avl_excluded_from_avl_query(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_avl_suppliers_for_component("Flexible Printed Circuits")
        supplier_ids = [r["supplier_id"] for r in results]
        # SUP-009 is Non-AVL, should not appear
        assert "SUP-009" not in supplier_ids

    def test_empty_component_returns_empty(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_suppliers_by_component("Nonexistent Component")
        assert results == []

    def test_sorted_by_risk_score(self, test_db, sample_suppliers):
        upsert_suppliers(sample_suppliers, "v1.0")
        results = get_suppliers_by_component("Flexible Printed Circuits")
        if len(results) > 1:
            assert results[0]["risk_score"] <= results[1]["risk_score"]


# ── Audit Logging ─────────────────────────────────────────────────────


class TestAuditLogging:
    def test_log_audit_event(self, test_db):
        log_audit_event(
            event_type="csv_ingestion",
            dataset_name="suppliers",
            dataset_version="v1.0",
            details="Loaded 30 records",
            record_count=30,
            valid_count=28,
            quarantined_count=2,
        )
        logs = get_audit_log()
        assert len(logs) == 1
        assert logs[0]["event_type"] == "csv_ingestion"
        assert logs[0]["record_count"] == 30

    def test_multiple_audit_events(self, test_db):
        log_audit_event(event_type="first", dataset_name="test")
        log_audit_event(event_type="second", dataset_name="test")
        log_audit_event(event_type="third", dataset_name="test")
        logs = get_audit_log()
        assert len(logs) == 3

    def test_audit_log_ordered_by_latest(self, test_db):
        log_audit_event(event_type="first", dataset_name="test")
        log_audit_event(event_type="second", dataset_name="test")
        logs = get_audit_log()
        # Most recent first
        assert logs[0]["event_type"] == "second"


# ── Dataset Versioning ────────────────────────────────────────────────


class TestDatasetVersioning:
    def test_save_dataset_version(self, test_db):
        save_dataset_version("suppliers_v1.0", "suppliers", 30)
        conn = get_connection(test_db)
        row = conn.execute(
            "SELECT * FROM dataset_versions WHERE version_id = ?",
            ("suppliers_v1.0",),
        ).fetchone()
        conn.close()
        assert dict(row)["record_count"] == 30
        assert dict(row)["status"] == "active"

    def test_new_version_supersedes_old(self, test_db):
        save_dataset_version("suppliers_v1.0", "suppliers", 30)
        save_dataset_version("suppliers_v2.0", "suppliers", 35)

        conn = get_connection(test_db)
        v1 = dict(conn.execute(
            "SELECT * FROM dataset_versions WHERE version_id = ?",
            ("suppliers_v1.0",),
        ).fetchone())
        v2 = dict(conn.execute(
            "SELECT * FROM dataset_versions WHERE version_id = ?",
            ("suppliers_v2.0",),
        ).fetchone())
        conn.close()

        assert v1["status"] == "superseded"
        assert v2["status"] == "active"


# ── Quarantine System ─────────────────────────────────────────────────


class TestQuarantine:
    def test_quarantine_record(self, test_db):
        quarantine_record(
            dataset_name="suppliers",
            version="v1.0",
            raw_data='{"supplier_id": "BAD", "lead_time_days": -5}',
            error="lead_time_days must be >= 1",
        )
        conn = get_connection(test_db)
        rows = conn.execute("SELECT * FROM quarantined_records").fetchall()
        conn.close()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["dataset_name"] == "suppliers"
        assert "lead_time_days" in row["error_message"]
