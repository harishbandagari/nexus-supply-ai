"""NexusSupply AI — Pydantic Schemas for Enterprise Data Validation.

All enterprise data flows through these schemas before entering
the system. Invalid records are quarantined with audit trails.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ──────────────────────────────────────────────────────────────


class ApprovedVendorStatus(str, Enum):
    AVL = "AVL"
    NON_AVL = "Non-AVL"


class SourcingTier(str, Enum):
    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2"
    TIER_3 = "Tier 3"


class DocumentType(str, Enum):
    CONTRACT = "contract"
    POLICY = "policy"
    INCIDENT = "incident"


class DisruptionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Supplier Registry ─────────────────────────────────────────────────


class SupplierRecord(BaseModel):
    """Validated supplier record from CSV ingestion."""

    supplier_id: str = Field(..., pattern=r"^SUP-\d{3}$")
    supplier_name: str = Field(..., min_length=2, max_length=200)
    component_name: str = Field(..., min_length=2)
    component_category: str = Field(..., min_length=2)
    supplier_region: str
    country: str
    approved_vendor_status: ApprovedVendorStatus
    lead_time_days: int = Field(..., ge=1, le=365)
    sourcing_tier: SourcingTier
    contract_end_date: date
    moq: int = Field(..., ge=1, description="Minimum Order Quantity")
    sourcing_allocation_cap: float = Field(
        ..., ge=0.0, le=1.0, description="Max allocation as fraction (0.0–1.0)"
    )
    headroom_capacity_units: int = Field(..., ge=0)
    historical_reliability_score: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)

    @field_validator("contract_end_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v


# ── Document Models ────────────────────────────────────────────────────


class DocumentChunk(BaseModel):
    """A chunk of an ingested document with metadata."""

    chunk_id: str
    document_name: str
    document_type: DocumentType
    content: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=1)
    dataset_version: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# ── Query & Response Models ────────────────────────────────────────────


class DisruptionQuery(BaseModel):
    """Structured query representing a supply chain disruption scenario."""

    query_text: str = Field(..., min_length=10)
    affected_region: Optional[str] = None
    affected_components: list[str] = Field(default_factory=list)
    severity: DisruptionSeverity = DisruptionSeverity.MEDIUM


class EvidenceItem(BaseModel):
    """A single piece of evidence backing a recommendation."""

    source_document: str
    chunk_index: int
    content_excerpt: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    document_type: DocumentType
    dataset_version: str


class GovernanceCheckResult(BaseModel):
    """Result of a deterministic governance validation."""

    check_name: str
    passed: bool
    details: str
    supplier_id: Optional[str] = None


class SupplierRecommendation(BaseModel):
    """An AI-generated alternate supplier recommendation with full lineage."""

    supplier_id: str
    supplier_name: str
    component_name: str
    recommendation_rationale: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence: list[EvidenceItem]
    governance_checks: list[GovernanceCheckResult]
    is_grounded: bool = Field(
        ..., description="Whether recommendation meets grounding threshold"
    )
    blocked: bool = Field(
        default=False,
        description="Blocked if governance checks fail or ungrounded",
    )
    block_reason: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Complete analysis response from the orchestrator."""

    query: DisruptionQuery
    disruption_summary: str
    impacted_suppliers: list[dict]
    recommendations: list[SupplierRecommendation]
    risk_assessment: str
    evidence_summary: list[EvidenceItem]
    governance_status: list[GovernanceCheckResult]
    dataset_version: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Ingestion Audit ───────────────────────────────────────────────────


class IngestionAuditEntry(BaseModel):
    """Audit log entry for data ingestion events."""

    dataset_name: str
    dataset_version: str
    record_count: int = Field(..., ge=0)
    valid_count: int = Field(..., ge=0)
    quarantined_count: int = Field(..., ge=0)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "completed"
    errors: list[str] = Field(default_factory=list)
