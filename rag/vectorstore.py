"""NexusSupply AI — ChromaDB Vector Store.

Manages document embedding storage and retrieval
using ChromaDB with OpenAI embeddings.
"""

import chromadb
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, OPENAI_API_KEY
from validation.schemas import DocumentChunk

COLLECTION_NAME = "nexus_supply_docs"


def get_embedding_function() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )


def get_vectorstore() -> Chroma:
    """Get or create the ChromaDB vector store."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


def index_chunks(vectorstore: Chroma, chunks: list[DocumentChunk]) -> int:
    """Index document chunks into the vector store.

    Each chunk is stored with its content as the document text
    and full metadata for retrieval lineage.
    """
    if not chunks:
        return 0

    texts = [c.content for c in chunks]
    metadatas = [
        {
            "chunk_id": c.chunk_id,
            "document_name": c.document_name,
            "document_type": c.document_type.value,
            "chunk_index": c.chunk_index,
            "total_chunks": c.total_chunks,
            "dataset_version": c.dataset_version,
        }
        for c in chunks
    ]
    ids = [c.chunk_id for c in chunks]

    vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    return len(chunks)


def similarity_search(
    vectorstore: Chroma,
    query: str,
    k: int = 10,
    filter_dict: dict | None = None,
) -> list[dict]:
    """Search for similar documents, returning results with scores.

    Returns list of dicts with keys: content, metadata, similarity_score.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        results = vectorstore.similarity_search_with_relevance_scores(
            query=query,
            k=k,
            filter=filter_dict,
        )

    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "similarity_score": round(max(0.0, min(1.0, score)), 4),
        }
        for doc, score in results
    ]


def clear_vectorstore() -> None:
    """Delete all documents from the vector store."""
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except ValueError:
        pass  # Collection doesn't exist
