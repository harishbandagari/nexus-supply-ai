"""NexusSupply AI — Explainability Agent.

Builds evidence lineage, confidence summaries, and
retrieval traceability for every recommendation.
"""

from validation.schemas import AnalysisResponse, EvidenceItem, SupplierRecommendation


def build_explainability_report(response: AnalysisResponse) -> dict:
    """Generate a structured explainability report for the analysis.

    Ensures every recommendation has full evidence lineage
    including source documents, chunk indices, similarity scores,
    and dataset versions.
    """
    recommendation_explanations = []

    for rec in response.recommendations:
        explanation = {
            "supplier_id": rec.supplier_id,
            "supplier_name": rec.supplier_name,
            "component": rec.component_name,
            "confidence_score": rec.confidence_score,
            "is_grounded": rec.is_grounded,
            "blocked": rec.blocked,
            "block_reason": rec.block_reason,
            "evidence_lineage": [
                {
                    "source": e.source_document,
                    "chunk_index": e.chunk_index,
                    "similarity_score": e.similarity_score,
                    "document_type": e.document_type.value,
                    "dataset_version": e.dataset_version,
                    "excerpt": e.content_excerpt[:150],
                }
                for e in rec.evidence
            ],
            "governance_checks": [
                {
                    "check": g.check_name,
                    "passed": g.passed,
                    "details": g.details,
                }
                for g in rec.governance_checks
            ],
        }
        recommendation_explanations.append(explanation)

    # Overall evidence summary
    all_evidence = response.evidence_summary
    unique_sources = list({e.source_document for e in all_evidence})

    return {
        "query": response.query.query_text,
        "dataset_version": response.dataset_version,
        "total_evidence_items": len(all_evidence),
        "unique_source_documents": unique_sources,
        "recommendations_total": len(response.recommendations),
        "recommendations_approved": sum(
            1 for r in response.recommendations if not r.blocked
        ),
        "recommendations_blocked": sum(
            1 for r in response.recommendations if r.blocked
        ),
        "recommendation_details": recommendation_explanations,
        "governance_summary": {
            "total_checks": sum(
                len(r.governance_checks) for r in response.recommendations
            ),
            "passed": sum(
                sum(1 for g in r.governance_checks if g.passed)
                for r in response.recommendations
            ),
            "failed": sum(
                sum(1 for g in r.governance_checks if not g.passed)
                for r in response.recommendations
            ),
        },
    }
