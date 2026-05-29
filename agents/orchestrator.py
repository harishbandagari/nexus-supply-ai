"""NexusSupply AI — Orchestrator Agent.

Coordinates the multi-agent workflow:
    1. Retrieval Agent → hybrid evidence gathering
    2. Risk Analysis Agent → disruption assessment
    3. Recommendation Agent → alternate supplier suggestions
    4. Explainability Agent → evidence lineage report
"""

from datetime import datetime

from agents.retrieval_agent import run_retrieval
from agents.risk_agent import analyze_risk
from agents.recommendation_agent import generate_recommendations
from agents.explainability_agent import build_explainability_report
from config import CURRENT_DATASET_VERSION
from validation.schemas import AnalysisResponse, DisruptionQuery, EvidenceItem


def run_analysis(query: DisruptionQuery) -> AnalysisResponse:
    """Execute the full multi-agent analysis pipeline.

    Steps:
        1. Retrieval Agent gathers semantic + structured evidence
        2. Risk Agent analyzes disruption impact
        3. Recommendation Agent generates grounded alternates
        4. Everything assembled into a traceable response
    """
    # Step 1: Retrieval
    retrieval_results = run_retrieval(query)

    # Step 2: Risk Analysis
    risk_analysis = analyze_risk(retrieval_results)

    # Step 3: Recommendations
    recommendations = generate_recommendations(retrieval_results, risk_analysis)

    # Build evidence items from retrieval results
    evidence_summary = [
        EvidenceItem(**e) if isinstance(e, dict) else e
        for e in retrieval_results.get("semantic_evidence", [])
    ]

    # Step 4: Assemble response
    response = AnalysisResponse(
        query=query,
        disruption_summary=risk_analysis["disruption_summary"],
        impacted_suppliers=retrieval_results.get("impacted_suppliers", []),
        recommendations=recommendations,
        risk_assessment=risk_analysis["risk_assessment"],
        evidence_summary=evidence_summary,
        governance_status=[
            gc
            for rec in recommendations
            for gc in rec.governance_checks
        ],
        dataset_version=CURRENT_DATASET_VERSION,
        generated_at=datetime.utcnow(),
    )

    return response
