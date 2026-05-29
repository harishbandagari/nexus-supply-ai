"""NexusSupply AI — Ingestion Pipeline Orchestrator.

Coordinates CSV ingestion, document ingestion, vector store indexing,
and audit logging into a single pipeline.
"""

from pathlib import Path

from config import CURRENT_DATASET_VERSION, RAW_DATA_DIR
from database.sqlite_store import init_database, log_audit_event
from ingestion.csv_ingestion import ingest_supplier_csv
from ingestion.document_ingestion import ingest_directory
from rag.vectorstore import clear_vectorstore, get_vectorstore, index_chunks
from validation.schemas import IngestionAuditEntry


def run_full_ingestion(
    data_dir: Path = RAW_DATA_DIR,
    version: str = CURRENT_DATASET_VERSION,
) -> dict:
    """Run the complete ingestion pipeline.

    Steps:
        1. Initialize database
        2. Ingest supplier CSV → SQLite
        3. Ingest contracts, policies, incidents → chunks
        4. Index chunks → ChromaDB
        5. Log audit trail

    Returns a summary dict.
    """
    # 1. Initialize database
    init_database()

    # 2. Ingest structured data
    csv_path = data_dir / "suppliers.csv"
    csv_audit: IngestionAuditEntry | None = None
    if csv_path.exists():
        csv_audit = ingest_supplier_csv(csv_path, version)

    # 3. Ingest unstructured documents
    all_chunks = []
    for subdir in ["contracts", "policies", "incidents"]:
        dir_path = data_dir / subdir
        if dir_path.exists():
            chunks = ingest_directory(dir_path, version)
            all_chunks.extend(chunks)

    # 4. Index in vector store (requires OpenAI API key for embeddings)
    from config import OPENAI_API_KEY
    indexed_count = 0
    if all_chunks and OPENAI_API_KEY:
        clear_vectorstore()
        vectorstore = get_vectorstore()
        indexed_count = index_chunks(vectorstore, all_chunks)
    elif all_chunks:
        indexed_count = 0  # Chunks prepared but not indexed (no API key)

    # 5. Audit
    log_audit_event(
        event_type="full_ingestion",
        dataset_name="all",
        dataset_version=version,
        details=f"Suppliers: {csv_audit.valid_count if csv_audit else 0}, "
                f"Document chunks: {len(all_chunks)}, Indexed: {indexed_count}",
        record_count=(csv_audit.record_count if csv_audit else 0) + len(all_chunks),
        valid_count=(csv_audit.valid_count if csv_audit else 0) + len(all_chunks),
        quarantined_count=csv_audit.quarantined_count if csv_audit else 0,
    )

    return {
        "csv_audit": csv_audit.model_dump() if csv_audit else None,
        "document_chunks_indexed": indexed_count,
        "document_chunks_prepared": len(all_chunks),
        "dataset_version": version,
        "vectorstore_indexed": bool(OPENAI_API_KEY),
    }
