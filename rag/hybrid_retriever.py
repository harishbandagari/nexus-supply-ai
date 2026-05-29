"""NexusSupply AI — Hybrid Retriever.

Combines semantic retrieval (ChromaDB) with deterministic
structured filtering (SQLite) to produce grounded, governance-aware
retrieval results.
"""

from database.sqlite_store import (
    get_avl_suppliers_for_component,
    get_suppliers_by_component,
    get_suppliers_by_region,
)
from rag.retriever import retrieve_relevant_documents
from validation.schemas import DisruptionQuery, DocumentType, EvidenceItem


def hybrid_retrieve(query: DisruptionQuery) -> dict:
    """Execute hybrid retrieval combining semantic + structured data.

    Returns:
        dict with keys:
            - semantic_evidence: list[EvidenceItem] from vector search
            - structured_suppliers: list[dict] from SQL filtering
            - alternate_candidates: list[dict] AVL-approved alternates
    """
    # ── Semantic retrieval ─────────────────────────────────────────
    # Search contracts for relevant clauses
    contract_evidence = retrieve_relevant_documents(
        query=query.query_text,
        document_type=DocumentType.CONTRACT,
    )

    # Search policies
    policy_evidence = retrieve_relevant_documents(
        query=query.query_text,
        document_type=DocumentType.POLICY,
    )

    # Search incident feeds
    incident_evidence = retrieve_relevant_documents(
        query=query.query_text,
        document_type=DocumentType.INCIDENT,
    )

    all_evidence = contract_evidence + policy_evidence + incident_evidence

    # ── Deterministic structured retrieval ─────────────────────────
    impacted_suppliers = []
    alternate_candidates = []

    # Get suppliers by affected region
    if query.affected_region:
        impacted_suppliers = get_suppliers_by_region(query.affected_region)

    # Get alternate AVL suppliers for each affected component
    for component in query.affected_components:
        component_suppliers = get_suppliers_by_component(component)
        avl_alternates = get_avl_suppliers_for_component(component)

        # Filter out impacted suppliers from alternates
        impacted_ids = {s["supplier_id"] for s in impacted_suppliers}
        for alt in avl_alternates:
            if alt["supplier_id"] not in impacted_ids:
                alternate_candidates.append(alt)

    return {
        "semantic_evidence": all_evidence,
        "structured_suppliers": impacted_suppliers,
        "alternate_candidates": alternate_candidates,
    }
