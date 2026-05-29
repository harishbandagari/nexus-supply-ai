"""Tests for NexusSupply AI — Data Ingestion Pipeline.

Tests:
- CSV ingestion with validation and quarantine
- Document ingestion (chunking, metadata, type detection)
- Full pipeline orchestration
"""

import pytest
import csv
from pathlib import Path
from datetime import date

from ingestion.csv_ingestion import ingest_supplier_csv
from ingestion.document_ingestion import (
    ingest_document,
    ingest_directory,
    _chunk_text,
    _detect_document_type,
    _read_file,
)
from validation.schemas import DocumentType


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def valid_csv(tmp_path):
    """Create a valid supplier CSV file."""
    csv_path = tmp_path / "suppliers.csv"
    headers = [
        "supplier_id", "supplier_name", "component_name", "component_category",
        "supplier_region", "country", "approved_vendor_status", "lead_time_days",
        "sourcing_tier", "contract_end_date", "moq", "sourcing_allocation_cap",
        "headroom_capacity_units", "historical_reliability_score", "risk_score",
    ]
    rows = [
        ["SUP-001", "Test Supplier A", "Flexible Printed Circuits", "Interconnect",
         "Shenzhen", "China", "AVL", "21", "Tier 1", "2027-03-31",
         "5000", "0.35", "120000", "0.92", "0.68"],
        ["SUP-002", "Test Supplier B", "OLED Driver ICs", "Display Components",
         "Guangzhou", "China", "AVL", "28", "Tier 1", "2027-06-30",
         "8000", "0.30", "85000", "0.88", "0.65"],
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def invalid_csv(tmp_path):
    """CSV with some invalid records."""
    csv_path = tmp_path / "suppliers_bad.csv"
    headers = [
        "supplier_id", "supplier_name", "component_name", "component_category",
        "supplier_region", "country", "approved_vendor_status", "lead_time_days",
        "sourcing_tier", "contract_end_date", "moq", "sourcing_allocation_cap",
        "headroom_capacity_units", "historical_reliability_score", "risk_score",
    ]
    rows = [
        # Valid
        ["SUP-001", "Good Supplier", "FPC", "Interconnect",
         "Shenzhen", "China", "AVL", "21", "Tier 1", "2027-03-31",
         "5000", "0.35", "120000", "0.92", "0.68"],
        # Invalid: bad supplier_id pattern
        ["INVALID-ID", "Bad Supplier", "FPC", "Interconnect",
         "Shenzhen", "China", "AVL", "21", "Tier 1", "2027-03-31",
         "5000", "0.35", "120000", "0.92", "0.68"],
        # Invalid: lead_time_days = 0
        ["SUP-003", "Zero Lead", "FPC", "Interconnect",
         "Shenzhen", "China", "AVL", "0", "Tier 1", "2027-03-31",
         "5000", "0.35", "120000", "0.92", "0.68"],
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def contract_file(tmp_path):
    """Create a test contract file."""
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    file_path = contracts_dir / "contract_sup001.txt"
    file_path.write_text(
        "MASTER SUPPLY AGREEMENT — TEST SUPPLIER\n"
        "Contract Reference: MSA-2024-TEST-001\n\n"
        "ARTICLE 1 — FORCE MAJEURE\n"
        "Neither party shall be liable for delays caused by events beyond "
        "reasonable control including natural disasters, government actions, "
        "pandemics, or war.\n\n"
        "ARTICLE 2 — SOURCING ALLOCATION\n"
        "Maximum sourcing allocation of 35% of total procurement volume."
    )
    return file_path


@pytest.fixture
def incident_file(tmp_path):
    """Create a test incident alert file."""
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()
    file_path = incidents_dir / "test_disruption.txt"
    file_path.write_text(
        "SUPPLY CHAIN DISRUPTION ALERT\n"
        "Severity: CRITICAL\n"
        "Region: Shenzhen, China\n\n"
        "A manufacturing lockdown has been imposed on electronics facilities. "
        "Estimated duration: 21-45 days."
    )
    return file_path


@pytest.fixture
def data_dir(tmp_path, contract_file, incident_file):
    """Create a complete data directory structure."""
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    (policies_dir / "approved_vendor_policy.txt").write_text(
        "APPROVED VENDOR LIST POLICY\n"
        "Only AVL-approved suppliers may be used for production sourcing."
    )
    # CSV
    csv_path = tmp_path / "suppliers.csv"
    headers = [
        "supplier_id", "supplier_name", "component_name", "component_category",
        "supplier_region", "country", "approved_vendor_status", "lead_time_days",
        "sourcing_tier", "contract_end_date", "moq", "sourcing_allocation_cap",
        "headroom_capacity_units", "historical_reliability_score", "risk_score",
    ]
    rows = [
        ["SUP-001", "Test Supplier", "FPC", "Interconnect",
         "Shenzhen", "China", "AVL", "21", "Tier 1", "2027-03-31",
         "5000", "0.35", "120000", "0.92", "0.68"],
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return tmp_path


# ── CSV Ingestion Tests ───────────────────────────────────────────────


class TestCSVIngestion:
    def test_valid_csv_all_records_loaded(self, valid_csv, tmp_path, monkeypatch):
        monkeypatch.setattr("database.sqlite_store.DB_PATH", tmp_path / "test.db")
        from database.sqlite_store import init_database
        init_database(tmp_path / "test.db")

        audit = ingest_supplier_csv(valid_csv, "v1.0")
        assert audit.record_count == 2
        assert audit.valid_count == 2
        assert audit.quarantined_count == 0
        assert audit.errors == []

    def test_invalid_records_quarantined(self, invalid_csv, tmp_path, monkeypatch):
        monkeypatch.setattr("database.sqlite_store.DB_PATH", tmp_path / "test.db")
        from database.sqlite_store import init_database
        init_database(tmp_path / "test.db")

        audit = ingest_supplier_csv(invalid_csv, "v1.0")
        assert audit.record_count == 3
        assert audit.valid_count == 1
        assert audit.quarantined_count == 2
        assert len(audit.errors) == 2

    def test_version_tracked(self, valid_csv, tmp_path, monkeypatch):
        monkeypatch.setattr("database.sqlite_store.DB_PATH", tmp_path / "test.db")
        from database.sqlite_store import init_database
        init_database(tmp_path / "test.db")

        audit = ingest_supplier_csv(valid_csv, "v2.0")
        assert audit.dataset_version == "v2.0"


# ── Text Chunking Tests ───────────────────────────────────────────────


class TestTextChunking:
    def test_short_text_single_chunk(self):
        chunks = _chunk_text("Hello world", chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_long_text_multiple_chunks(self):
        text = "A" * 1200
        chunks = _chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 3

    def test_overlap_applied(self):
        text = "ABCDE" * 200  # 1000 chars
        chunks = _chunk_text(text, chunk_size=500, overlap=100)
        # With overlap, chunks should share content
        assert len(chunks) >= 2
        # End of chunk 1 should overlap with start of chunk 2
        if len(chunks) >= 2:
            end_of_first = chunks[0][-100:]
            start_of_second = chunks[1][:100]
            assert end_of_first == start_of_second

    def test_empty_text_no_chunks(self):
        chunks = _chunk_text("", chunk_size=500, overlap=50)
        assert chunks == []

    def test_whitespace_only_no_chunks(self):
        chunks = _chunk_text("   \n\n   ", chunk_size=500, overlap=50)
        assert chunks == []


# ── Document Type Detection Tests ─────────────────────────────────────


class TestDocumentTypeDetection:
    def test_contract_directory(self, tmp_path):
        contracts = tmp_path / "contracts"
        contracts.mkdir()
        f = contracts / "test.txt"
        f.touch()
        assert _detect_document_type(f) == DocumentType.CONTRACT

    def test_policy_directory(self, tmp_path):
        policies = tmp_path / "policies"
        policies.mkdir()
        f = policies / "test.txt"
        f.touch()
        assert _detect_document_type(f) == DocumentType.POLICY

    def test_incident_directory(self, tmp_path):
        incidents = tmp_path / "incidents"
        incidents.mkdir()
        f = incidents / "test.txt"
        f.touch()
        assert _detect_document_type(f) == DocumentType.INCIDENT

    def test_unknown_directory_raises(self, tmp_path):
        other = tmp_path / "random"
        other.mkdir()
        f = other / "test.txt"
        f.touch()
        with pytest.raises(ValueError):
            _detect_document_type(f)


# ── Document Ingestion Tests ──────────────────────────────────────────


class TestDocumentIngestion:
    def test_ingest_contract_file(self, contract_file):
        chunks = ingest_document(contract_file, "v1.0")
        assert len(chunks) >= 1
        assert all(c.document_type == DocumentType.CONTRACT for c in chunks)
        assert all(c.document_name == "contract_sup001.txt" for c in chunks)
        assert all(c.dataset_version == "v1.0" for c in chunks)

    def test_ingest_incident_file(self, incident_file):
        chunks = ingest_document(incident_file, "v1.0")
        assert len(chunks) >= 1
        assert all(c.document_type == DocumentType.INCIDENT for c in chunks)

    def test_chunk_ids_are_unique(self, contract_file):
        chunks = ingest_document(contract_file, "v1.0")
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_indices_sequential(self, contract_file):
        chunks = ingest_document(contract_file, "v1.0")
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_total_chunks_consistent(self, contract_file):
        chunks = ingest_document(contract_file, "v1.0")
        for chunk in chunks:
            assert chunk.total_chunks == len(chunks)

    def test_ingest_directory(self, tmp_path, contract_file):
        contracts_dir = contract_file.parent
        chunks = ingest_directory(contracts_dir, "v1.0")
        assert len(chunks) >= 1

    def test_version_changes_chunk_ids(self, contract_file):
        chunks_v1 = ingest_document(contract_file, "v1.0")
        chunks_v2 = ingest_document(contract_file, "v2.0")
        # Different versions should produce different chunk IDs
        ids_v1 = {c.chunk_id for c in chunks_v1}
        ids_v2 = {c.chunk_id for c in chunks_v2}
        assert ids_v1.isdisjoint(ids_v2)

    def test_unsupported_file_type_raises(self, tmp_path):
        incidents = tmp_path / "incidents"
        incidents.mkdir()
        bad_file = incidents / "test.xlsx"
        bad_file.write_text("fake excel")
        with pytest.raises(ValueError, match="Unsupported"):
            ingest_document(bad_file)
