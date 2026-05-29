"""Tests for NexusSupply AI — Pydantic Validation Schemas.

Tests data validation for:
- SupplierRecord (CSV ingestion)
- DocumentChunk (document ingestion)
- DisruptionQuery (user input)
- EvidenceItem, GovernanceCheckResult, SupplierRecommendation
- AnalysisResponse, IngestionAuditEntry
"""

import pytest
from datetime import date, datetime

from pydantic import ValidationError

from validation.schemas import (
    ApprovedVendorStatus,
    DisruptionQuery,
    DisruptionSeverity,
    DocumentChunk,
    DocumentType,
    EvidenceItem,
    GovernanceCheckResult,
    IngestionAuditEntry,
    SourcingTier,
    SupplierRecord,
    SupplierRecommendation,
)


# ── SupplierRecord Tests ──────────────────────────────────────────────


class TestSupplierRecord:
    @pytest.fixture
    def valid_data(self):
        return {
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
        }

    def test_valid_record_passes(self, valid_data):
        record = SupplierRecord(**valid_data)
        assert record.supplier_id == "SUP-001"
        assert record.approved_vendor_status == ApprovedVendorStatus.AVL
        assert record.sourcing_tier == SourcingTier.TIER_1

    def test_invalid_supplier_id_pattern(self, valid_data):
        valid_data["supplier_id"] = "SUPPLIER-001"
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_supplier_id_must_be_3_digits(self, valid_data):
        valid_data["supplier_id"] = "SUP-01"
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_empty_supplier_name_fails(self, valid_data):
        valid_data["supplier_name"] = ""
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_single_char_supplier_name_fails(self, valid_data):
        valid_data["supplier_name"] = "A"
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_lead_time_zero_fails(self, valid_data):
        valid_data["lead_time_days"] = 0
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_lead_time_negative_fails(self, valid_data):
        valid_data["lead_time_days"] = -5
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_lead_time_exceeds_365_fails(self, valid_data):
        valid_data["lead_time_days"] = 400
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_invalid_avl_status_fails(self, valid_data):
        valid_data["approved_vendor_status"] = "Maybe"
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_non_avl_status_passes(self, valid_data):
        valid_data["approved_vendor_status"] = "Non-AVL"
        record = SupplierRecord(**valid_data)
        assert record.approved_vendor_status == ApprovedVendorStatus.NON_AVL

    def test_invalid_sourcing_tier_fails(self, valid_data):
        valid_data["sourcing_tier"] = "Tier 4"
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_allocation_cap_above_1_fails(self, valid_data):
        valid_data["sourcing_allocation_cap"] = 1.5
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_allocation_cap_negative_fails(self, valid_data):
        valid_data["sourcing_allocation_cap"] = -0.1
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_risk_score_above_1_fails(self, valid_data):
        valid_data["risk_score"] = 1.1
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_reliability_score_negative_fails(self, valid_data):
        valid_data["historical_reliability_score"] = -0.5
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_moq_zero_fails(self, valid_data):
        valid_data["moq"] = 0
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_negative_headroom_fails(self, valid_data):
        valid_data["headroom_capacity_units"] = -100
        with pytest.raises(ValidationError):
            SupplierRecord(**valid_data)

    def test_date_parsing_from_string(self, valid_data):
        record = SupplierRecord(**valid_data)
        assert record.contract_end_date == date(2027, 3, 31)

    def test_date_object_accepted(self, valid_data):
        valid_data["contract_end_date"] = date(2027, 3, 31)
        record = SupplierRecord(**valid_data)
        assert record.contract_end_date == date(2027, 3, 31)

    def test_boundary_scores_pass(self, valid_data):
        valid_data["risk_score"] = 0.0
        valid_data["historical_reliability_score"] = 1.0
        record = SupplierRecord(**valid_data)
        assert record.risk_score == 0.0
        assert record.historical_reliability_score == 1.0


# ── DocumentChunk Tests ───────────────────────────────────────────────


class TestDocumentChunk:
    def test_valid_chunk(self):
        chunk = DocumentChunk(
            chunk_id="abc123",
            document_name="contract_sup001.txt",
            document_type=DocumentType.CONTRACT,
            content="Force majeure clause allows...",
            chunk_index=0,
            total_chunks=5,
            dataset_version="v1.0",
        )
        assert chunk.document_type == DocumentType.CONTRACT
        assert chunk.chunk_index == 0

    def test_empty_content_fails(self):
        with pytest.raises(ValidationError):
            DocumentChunk(
                chunk_id="abc123",
                document_name="test.txt",
                document_type=DocumentType.POLICY,
                content="",
                chunk_index=0,
                total_chunks=1,
                dataset_version="v1.0",
            )

    def test_negative_chunk_index_fails(self):
        with pytest.raises(ValidationError):
            DocumentChunk(
                chunk_id="abc123",
                document_name="test.txt",
                document_type=DocumentType.INCIDENT,
                content="Some content",
                chunk_index=-1,
                total_chunks=5,
                dataset_version="v1.0",
            )

    def test_zero_total_chunks_fails(self):
        with pytest.raises(ValidationError):
            DocumentChunk(
                chunk_id="abc123",
                document_name="test.txt",
                document_type=DocumentType.CONTRACT,
                content="Some content",
                chunk_index=0,
                total_chunks=0,
                dataset_version="v1.0",
            )

    def test_ingested_at_auto_set(self):
        chunk = DocumentChunk(
            chunk_id="abc123",
            document_name="test.txt",
            document_type=DocumentType.POLICY,
            content="Policy content here",
            chunk_index=0,
            total_chunks=1,
            dataset_version="v1.0",
        )
        assert isinstance(chunk.ingested_at, datetime)


# ── DisruptionQuery Tests ─────────────────────────────────────────────


class TestDisruptionQuery:
    def test_valid_query(self):
        query = DisruptionQuery(
            query_text="Shenzhen manufacturing lockdown impacting FPC suppliers",
            affected_region="Shenzhen",
            affected_components=["Flexible Printed Circuits"],
            severity=DisruptionSeverity.CRITICAL,
        )
        assert query.severity == DisruptionSeverity.CRITICAL
        assert query.affected_region == "Shenzhen"

    def test_query_text_too_short_fails(self):
        with pytest.raises(ValidationError):
            DisruptionQuery(query_text="short")

    def test_query_with_no_region(self):
        query = DisruptionQuery(
            query_text="General supply chain disruption analysis needed",
        )
        assert query.affected_region is None
        assert query.affected_components == []
        assert query.severity == DisruptionSeverity.MEDIUM

    def test_all_severity_levels(self):
        for level in ["low", "medium", "high", "critical"]:
            query = DisruptionQuery(
                query_text="Test disruption query for severity levels",
                severity=DisruptionSeverity(level),
            )
            assert query.severity.value == level


# ── EvidenceItem Tests ────────────────────────────────────────────────


class TestEvidenceItem:
    def test_valid_evidence(self):
        item = EvidenceItem(
            source_document="contract_sup001.txt",
            chunk_index=2,
            content_excerpt="Force majeure clause...",
            similarity_score=0.85,
            document_type=DocumentType.CONTRACT,
            dataset_version="v1.0",
        )
        assert item.similarity_score == 0.85

    def test_score_above_1_fails(self):
        with pytest.raises(ValidationError):
            EvidenceItem(
                source_document="test.txt",
                chunk_index=0,
                content_excerpt="content",
                similarity_score=1.5,
                document_type=DocumentType.INCIDENT,
                dataset_version="v1.0",
            )

    def test_negative_score_fails(self):
        with pytest.raises(ValidationError):
            EvidenceItem(
                source_document="test.txt",
                chunk_index=0,
                content_excerpt="content",
                similarity_score=-0.1,
                document_type=DocumentType.POLICY,
                dataset_version="v1.0",
            )


# ── GovernanceCheckResult Tests ───────────────────────────────────────


class TestGovernanceCheckResult:
    def test_passed_check(self):
        result = GovernanceCheckResult(
            check_name="AVL Status",
            passed=True,
            details="Approved for production.",
            supplier_id="SUP-001",
        )
        assert result.passed is True

    def test_failed_check(self):
        result = GovernanceCheckResult(
            check_name="Contract Validity",
            passed=False,
            details="Contract expired.",
            supplier_id="SUP-009",
        )
        assert result.passed is False

    def test_no_supplier_id(self):
        result = GovernanceCheckResult(
            check_name="MOQ Feasibility",
            passed=True,
            details="Within range.",
        )
        assert result.supplier_id is None


# ── SupplierRecommendation Tests ──────────────────────────────────────


class TestSupplierRecommendation:
    def test_approved_recommendation(self):
        rec = SupplierRecommendation(
            supplier_id="SUP-017",
            supplier_name="Thai Electronics",
            component_name="OLED Driver ICs",
            recommendation_rationale="Regional diversification from China.",
            confidence_score=0.88,
            evidence=[
                EvidenceItem(
                    source_document="incident.txt",
                    chunk_index=0,
                    content_excerpt="disruption...",
                    similarity_score=0.55,
                    document_type=DocumentType.INCIDENT,
                    dataset_version="v1.0",
                )
            ],
            governance_checks=[
                GovernanceCheckResult(
                    check_name="AVL Status",
                    passed=True,
                    details="Approved.",
                )
            ],
            is_grounded=True,
            blocked=False,
        )
        assert rec.blocked is False
        assert rec.confidence_score == 0.88

    def test_blocked_recommendation(self):
        rec = SupplierRecommendation(
            supplier_id="SUP-009",
            supplier_name="Vietnam Precision",
            component_name="FPC",
            recommendation_rationale="Available.",
            confidence_score=0.3,
            evidence=[],
            governance_checks=[],
            is_grounded=False,
            blocked=True,
            block_reason="Insufficient grounding",
        )
        assert rec.blocked is True
        assert rec.block_reason == "Insufficient grounding"

    def test_confidence_above_1_fails(self):
        with pytest.raises(ValidationError):
            SupplierRecommendation(
                supplier_id="SUP-001",
                supplier_name="Test",
                component_name="Test",
                recommendation_rationale="Test",
                confidence_score=1.5,
                evidence=[],
                governance_checks=[],
                is_grounded=False,
            )


# ── IngestionAuditEntry Tests ─────────────────────────────────────────


class TestIngestionAuditEntry:
    def test_valid_audit_entry(self):
        entry = IngestionAuditEntry(
            dataset_name="suppliers",
            dataset_version="v1.0",
            record_count=30,
            valid_count=28,
            quarantined_count=2,
            errors=["Row 5: invalid lead_time", "Row 12: missing country"],
        )
        assert entry.status == "completed"
        assert len(entry.errors) == 2

    def test_negative_count_fails(self):
        with pytest.raises(ValidationError):
            IngestionAuditEntry(
                dataset_name="suppliers",
                dataset_version="v1.0",
                record_count=-1,
                valid_count=0,
                quarantined_count=0,
            )

    def test_defaults(self):
        entry = IngestionAuditEntry(
            dataset_name="test",
            dataset_version="v1.0",
            record_count=10,
            valid_count=10,
            quarantined_count=0,
        )
        assert entry.status == "completed"
        assert entry.errors == []
        assert isinstance(entry.ingested_at, datetime)
