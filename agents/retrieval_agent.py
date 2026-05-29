"""NexusSupply AI — Retrieval Agent.

Responsible for executing hybrid retrieval (semantic + structured)
and assembling grounded evidence for downstream agents.
"""

from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from rag.hybrid_retriever import hybrid_retrieve
from validation.schemas import DisruptionQuery


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )


def run_retrieval(query: DisruptionQuery) -> dict:
    """Execute hybrid retrieval and return structured results.

    This agent does NOT generate text — it assembles evidence
    from semantic and structured retrieval systems.
    """
    results = hybrid_retrieve(query)

    return {
        "query": query.model_dump(),
        "semantic_evidence": [e.model_dump() for e in results["semantic_evidence"]],
        "impacted_suppliers": results["structured_suppliers"],
        "alternate_candidates": results["alternate_candidates"],
        "evidence_count": len(results["semantic_evidence"]),
        "impacted_count": len(results["structured_suppliers"]),
        "alternate_count": len(results["alternate_candidates"]),
    }
