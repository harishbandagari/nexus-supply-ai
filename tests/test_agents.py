"""Tests for NexusSupply AI — Agent Integration Tests.

Tests the multi-agent pipeline with mocked LLM calls:
- Orchestrator end-to-end flow
- Risk Agent (deterministic fallback + mocked LLM)
- Recommendation Agent (governance blocking, grounding)
- Explainability Agent (lineage reporting)
- Retrieval Agent (hybrid retrieval assembly)
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from validation.schemas import (
    AnalysisResponse,
    DisruptionQuery,
    EvidenceItem,
    SupplierRecommendation,
    GovernanceCheckResult,
    DocumentType,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_query():
    return DisruptionQuery(
        query_text="Shenzhen factory lockdown affecting flexible printed circuits",
        component_name="Flexible Printed Circuits",
        affected_region="Shenzhen",
    )


@pytest.fixture
def sample_retrieval_results():
    """Mocked output from the retrieval agent."""
    return {
        "query": {
            "query_text": "Shenzhen factory lockdown affecting flexible printed circuits",
            "component_name": "Flexible Printed Circuits",
            "affected_region": "Shenzhen",
        },
        "semantic_evidence": [
            {
                "content_excerpt": "Manufacturing lockdown imposed on Shenzhen electronics facilities.",
                "source_document": "disruption_alert_shenzhen.txt",
                "document_type": "incident",
                "chunk_index": 0,
                "total_chunks": 2,
                "chunk_id": "abc123",
                "similarity_score": 0.42,
                "dataset_version": "v1.0",
            },
            {
                "content_excerpt": "Force majeure clause in MSA-2024-FPC-001.",
                "source_document": "contract_flexcircuit.txt",
                "document_type": "contract",
                "chunk_index": 1,
                "total_chunks": 4,
                "chunk_id": "def456",
                "similarity_score": 0.38,
                "dataset_version": "v1.0",
            },
        ],
        "impacted_suppliers": [
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
            }
        ],
        "alternate_candidates": [
            {
                "supplier_id": "SUP-010",
                "supplier_name": "Malaysia FlexTech Sdn Bhd",
                "component_name": "Flexible Printed Circuits",
                "component_category": "Interconnect",
                "supplier_region": "Penang",
                "country": "Malaysia",
                "approved_vendor_status": "AVL",
                "lead_time_days": 25,
                "sourcing_tier": "Tier 1",
                "contract_end_date": "2027-06-30",
                "moq": 6000,
                "sourcing_allocation_cap": 0.30,
                "headroom_capacity_units": 80000,
                "historical_reliability_score": 0.89,
                "risk_score": 0.42,
            }
        ],
        "evidence_count": 2,
        "impacted_count": 1,
        "alternate_count": 1,
    }


@pytest.fixture
def sample_risk_analysis():
    """Mocked risk analysis output."""
    return {
        "disruption_summary": "Shenzhen lockdown affecting 1 FPC supplier (SUP-001).",
        "risk_assessment": "HIGH: Single-source dependency on Shenzhen region.",
        "full_analysis": "Complete analysis text.",
    }


@pytest.fixture
def sample_evidence_items():
    return [
        EvidenceItem(
            content_excerpt="Manufacturing lockdown imposed.",
            source_document="disruption_alert.txt",
            document_type=DocumentType.INCIDENT,
            chunk_index=0,
            total_chunks=2,
            chunk_id="abc123",
            similarity_score=0.42,
            dataset_version="v1.0",
        ),
    ]


@pytest.fixture
def sample_analysis_response(sample_query, sample_evidence_items):
    rec = SupplierRecommendation(
        supplier_id="SUP-010",
        supplier_name="Malaysia FlexTech Sdn Bhd",
        component_name="Flexible Printed Circuits",
        recommendation_rationale="Regional diversification away from affected Shenzhen.",
        confidence_score=0.85,
        is_grounded=True,
        blocked=False,
        block_reason=None,
        evidence=sample_evidence_items,
        governance_checks=[
            GovernanceCheckResult(
                check_name="avl_status",
                passed=True,
                details="AVL approved",
            ),
            GovernanceCheckResult(
                check_name="contract_validity",
                passed=True,
                details="Contract valid until 2027-06-30",
            ),
        ],
    )
    return AnalysisResponse(
        query=sample_query,
        disruption_summary="Lockdown affecting Shenzhen FPC suppliers.",
        impacted_suppliers=[{"supplier_id": "SUP-001", "supplier_name": "Shenzhen FlexCircuit Co."}],
        recommendations=[rec],
        risk_assessment="HIGH risk: single-source dependency.",
        evidence_summary=sample_evidence_items,
        governance_status=[GovernanceCheckResult(check_name="avl_status", passed=True, details="OK")],
        dataset_version="v1.0",
        generated_at=datetime.utcnow(),
    )


# ── Risk Agent Tests ──────────────────────────────────────────────────


class TestRiskAgent:
    def test_deterministic_fallback_without_api_key(self, sample_retrieval_results):
        """When OPENAI_API_KEY is empty, risk agent uses deterministic fallback."""
        with patch("config.OPENAI_API_KEY", ""):
            from agents.risk_agent import analyze_risk
            result = analyze_risk(sample_retrieval_results)

        assert "disruption_summary" in result
        assert "risk_assessment" in result
        assert "SUP-001" in result["disruption_summary"]

    def test_deterministic_identifies_high_risk(self, sample_retrieval_results):
        """Deterministic fallback identifies high-risk suppliers."""
        with patch("config.OPENAI_API_KEY", ""):
            from agents.risk_agent import analyze_risk
            result = analyze_risk(sample_retrieval_results)

        # SUP-001 has risk_score 0.68 >= 0.6
        assert "risk score" in result["risk_assessment"].lower() or "Risk Score" in result["risk_assessment"]

    def test_deterministic_counts_alternates(self, sample_retrieval_results):
        """Deterministic fallback reports available alternates."""
        with patch("config.OPENAI_API_KEY", ""):
            from agents.risk_agent import analyze_risk
            result = analyze_risk(sample_retrieval_results)

        assert "alternate" in result["disruption_summary"].lower()

    def test_empty_retrieval_results(self):
        """Risk agent handles empty retrieval results gracefully."""
        empty_results = {
            "query": {"query_text": "test query"},
            "semantic_evidence": [],
            "impacted_suppliers": [],
            "alternate_candidates": [],
        }
        with patch("config.OPENAI_API_KEY", ""):
            from agents.risk_agent import analyze_risk
            result = analyze_risk(empty_results)

        assert "disruption_summary" in result
        assert "risk_assessment" in result

    def test_llm_called_with_api_key(self, sample_retrieval_results):
        """With API key, risk agent calls the LLM."""
        mock_response = MagicMock()
        mock_response.content = (
            "DISRUPTION SUMMARY\n"
            "Factory lockdown in Shenzhen affects SUP-001.\n\n"
            "RISK ASSESSMENT\n"
            "High severity: single-source dependency."
        )
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        with patch("config.OPENAI_API_KEY", "sk-test-key"):
            with patch("agents.risk_agent.get_llm", return_value=mock_llm):
                from agents.risk_agent import analyze_risk
                result = analyze_risk(sample_retrieval_results)

        mock_llm.invoke.assert_called_once()
        assert "disruption_summary" in result
        assert "risk_assessment" in result


# ── Recommendation Agent Tests ────────────────────────────────────────


class TestRecommendationAgent:
    def test_no_alternates_returns_empty(self, sample_risk_analysis):
        """No alternate candidates means no recommendations."""
        results_no_alternates = {
            "query": {"query_text": "test"},
            "semantic_evidence": [],
            "impacted_suppliers": [],
            "alternate_candidates": [],
        }
        with patch("config.OPENAI_API_KEY", ""):
            from agents.recommendation_agent import generate_recommendations
            recs = generate_recommendations(results_no_alternates, sample_risk_analysis)

        assert recs == []

    def test_deterministic_mode_generates_recs(self, sample_retrieval_results, sample_risk_analysis):
        """Without API key, deterministic mode generates recommendations from structured data."""
        with patch("config.OPENAI_API_KEY", ""):
            from agents.recommendation_agent import generate_recommendations
            recs = generate_recommendations(sample_retrieval_results, sample_risk_analysis)

        assert len(recs) >= 1
        for rec in recs:
            assert isinstance(rec, SupplierRecommendation)
            assert rec.supplier_id == "SUP-010"

    def test_governance_checks_applied(self, sample_retrieval_results, sample_risk_analysis):
        """Every recommendation has governance checks attached."""
        with patch("config.OPENAI_API_KEY", ""):
            from agents.recommendation_agent import generate_recommendations
            recs = generate_recommendations(sample_retrieval_results, sample_risk_analysis)

        for rec in recs:
            assert len(rec.governance_checks) > 0
            for gc in rec.governance_checks:
                assert isinstance(gc, GovernanceCheckResult)
                assert gc.check_name != ""

    def test_non_avl_supplier_blocked(self, sample_risk_analysis):
        """Non-AVL supplier should be blocked by governance."""
        results_with_non_avl = {
            "query": {"query_text": "test"},
            "semantic_evidence": [],
            "impacted_suppliers": [],
            "alternate_candidates": [
                {
                    "supplier_id": "SUP-099",
                    "supplier_name": "Unapproved Corp",
                    "component_name": "FPC",
                    "component_category": "Interconnect",
                    "supplier_region": "Test",
                    "country": "Test",
                    "approved_vendor_status": "Non-AVL",
                    "lead_time_days": 30,
                    "sourcing_tier": "Tier 2",
                    "contract_end_date": "2027-01-01",
                    "moq": 5000,
                    "sourcing_allocation_cap": 0.20,
                    "headroom_capacity_units": 50000,
                    "historical_reliability_score": 0.80,
                    "risk_score": 0.50,
                }
            ],
        }
        with patch("config.OPENAI_API_KEY", ""):
            from agents.recommendation_agent import generate_recommendations
            recs = generate_recommendations(results_with_non_avl, sample_risk_analysis)

        for rec in recs:
            avl_check = next((g for g in rec.governance_checks if g.check_name == "avl_status"), None)
            if avl_check:
                assert avl_check.passed is False
            assert rec.blocked is True


# ── Explainability Agent Tests ────────────────────────────────────────


class TestExplainabilityAgent:
    def test_builds_report_structure(self, sample_analysis_response):
        from agents.explainability_agent import build_explainability_report
        report = build_explainability_report(sample_analysis_response)

        assert "query" in report
        assert "dataset_version" in report
        assert "total_evidence_items" in report
        assert "unique_source_documents" in report
        assert "recommendations_total" in report
        assert "recommendations_approved" in report

    def test_evidence_lineage_traced(self, sample_analysis_response):
        from agents.explainability_agent import build_explainability_report
        report = build_explainability_report(sample_analysis_response)

        # Check that recommendation details have lineage
        details = report.get("recommendation_details", [])
        assert len(details) >= 1
        assert details[0]["supplier_id"] == "SUP-010"
        assert len(details[0]["evidence_lineage"]) > 0

    def test_governance_checks_in_report(self, sample_analysis_response):
        from agents.explainability_agent import build_explainability_report
        report = build_explainability_report(sample_analysis_response)

        details = report.get("recommendation_details", [])
        if details:
            assert len(details[0]["governance_checks"]) > 0
            assert details[0]["governance_checks"][0]["check"] == "avl_status"

    def test_empty_recommendations(self, sample_query, sample_evidence_items):
        """Report handles zero recommendations gracefully."""
        response = AnalysisResponse(
            query=sample_query,
            disruption_summary="No action needed.",
            impacted_suppliers=[],
            recommendations=[],
            risk_assessment="Low risk.",
            evidence_summary=sample_evidence_items,
            governance_status=[],
            dataset_version="v1.0",
            generated_at=datetime.utcnow(),
        )
        from agents.explainability_agent import build_explainability_report
        report = build_explainability_report(response)
        assert report["recommendations_total"] == 0
        assert report["recommendations_approved"] == 0


# ── Orchestrator Integration Tests ────────────────────────────────────


class TestOrchestrator:
    def test_end_to_end_with_mocked_agents(self, sample_query, sample_retrieval_results, sample_risk_analysis):
        """Full pipeline with all sub-agents mocked."""
        mock_recs = [
            SupplierRecommendation(
                supplier_id="SUP-010",
                supplier_name="Malaysia FlexTech",
                component_name="Flexible Printed Circuits",
                recommendation_rationale="Diversification.",
                confidence_score=0.85,
                is_grounded=True,
                blocked=False,
                evidence=[],
                governance_checks=[
                    GovernanceCheckResult(check_name="avl_status", passed=True, details="OK")
                ],
            )
        ]

        with patch("agents.orchestrator.run_retrieval", return_value=sample_retrieval_results):
            with patch("agents.orchestrator.analyze_risk", return_value=sample_risk_analysis):
                with patch("agents.orchestrator.generate_recommendations", return_value=mock_recs):
                    from agents.orchestrator import run_analysis
                    result = run_analysis(sample_query)

        assert isinstance(result, AnalysisResponse)
        assert result.query == sample_query
        assert len(result.recommendations) == 1
        assert result.recommendations[0].supplier_id == "SUP-010"
        assert result.dataset_version is not None
        assert result.generated_at is not None

    def test_orchestrator_propagates_evidence(self, sample_query, sample_retrieval_results, sample_risk_analysis):
        """Evidence from retrieval flows into the final response."""
        with patch("agents.orchestrator.run_retrieval", return_value=sample_retrieval_results):
            with patch("agents.orchestrator.analyze_risk", return_value=sample_risk_analysis):
                with patch("agents.orchestrator.generate_recommendations", return_value=[]):
                    from agents.orchestrator import run_analysis
                    result = run_analysis(sample_query)

        assert len(result.evidence_summary) == 2
        assert result.evidence_summary[0].source_document == "disruption_alert_shenzhen.txt"

    def test_orchestrator_propagates_impacted_suppliers(self, sample_query, sample_retrieval_results, sample_risk_analysis):
        """Impacted suppliers from retrieval appear in final response."""
        with patch("agents.orchestrator.run_retrieval", return_value=sample_retrieval_results):
            with patch("agents.orchestrator.analyze_risk", return_value=sample_risk_analysis):
                with patch("agents.orchestrator.generate_recommendations", return_value=[]):
                    from agents.orchestrator import run_analysis
                    result = run_analysis(sample_query)

        assert len(result.impacted_suppliers) == 1
        assert result.impacted_suppliers[0]["supplier_id"] == "SUP-001"
