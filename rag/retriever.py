"""NexusSupply AI — Semantic Retriever.

Handles semantic search against the ChromaDB vector store
with similarity threshold enforcement and evidence formatting.
"""

from config import OPENAI_API_KEY, SIMILARITY_THRESHOLD, TOP_K_RESULTS
from rag.vectorstore import get_vectorstore, similarity_search
from validation.schemas import DocumentType, EvidenceItem


def retrieve_relevant_documents(
    query: str,
    document_type: DocumentType | None = None,
    top_k: int = TOP_K_RESULTS,
    min_score: float = SIMILARITY_THRESHOLD,
) -> list[EvidenceItem]:
    """Retrieve semantically relevant documents with evidence metadata.

    Only returns results above the similarity threshold to prevent
    ungrounded information from reaching downstream agents.
    """
    if not OPENAI_API_KEY:
        return []  # Skip semantic retrieval when no API key configured

    vectorstore = get_vectorstore()

    filter_dict = None
    if document_type:
        filter_dict = {"document_type": document_type.value}

    raw_results = similarity_search(
        vectorstore=vectorstore,
        query=query,
        k=top_k,
        filter_dict=filter_dict,
    )

    evidence_items = []
    for result in raw_results:
        score = result["similarity_score"]
        if score < min_score:
            continue

        meta = result["metadata"]
        evidence = EvidenceItem(
            source_document=meta.get("document_name", "unknown"),
            chunk_index=meta.get("chunk_index", 0),
            content_excerpt=result["content"][:300],
            similarity_score=score,
            document_type=DocumentType(meta.get("document_type", "contract")),
            dataset_version=meta.get("dataset_version", "unknown"),
        )
        evidence_items.append(evidence)

    return evidence_items
