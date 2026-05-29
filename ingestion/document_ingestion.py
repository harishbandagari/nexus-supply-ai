"""NexusSupply AI — Document Ingestion (Contracts, Policies, Incidents).

Reads TXT/PDF files, chunks them for vector embedding,
and returns DocumentChunk objects with full metadata.
"""

import hashlib
from pathlib import Path

from validation.schemas import DocumentChunk, DocumentType
from config import CHUNK_SIZE, CHUNK_OVERLAP, CURRENT_DATASET_VERSION


def _detect_document_type(file_path: Path) -> DocumentType:
    """Infer document type from directory name."""
    parent = file_path.parent.name.lower()
    if "contract" in parent:
        return DocumentType.CONTRACT
    elif "polic" in parent:
        return DocumentType.POLICY
    elif "incident" in parent:
        return DocumentType.INCIDENT
    raise ValueError(f"Cannot determine document type from path: {file_path}")


def _read_file(file_path: Path) -> str:
    """Read text content from a file. Supports .txt and .pdf."""
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def ingest_document(
    file_path: Path,
    version: str = CURRENT_DATASET_VERSION,
) -> list[DocumentChunk]:
    """Ingest a single document, returning validated chunks with metadata."""
    doc_type = _detect_document_type(file_path)
    content = _read_file(file_path)
    chunks_text = _chunk_text(content)

    doc_name = file_path.name
    chunks = []
    for i, chunk_content in enumerate(chunks_text):
        chunk_id = hashlib.sha256(
            f"{doc_name}:{i}:{version}".encode()
        ).hexdigest()[:16]

        chunk = DocumentChunk(
            chunk_id=chunk_id,
            document_name=doc_name,
            document_type=doc_type,
            content=chunk_content,
            chunk_index=i,
            total_chunks=len(chunks_text),
            dataset_version=version,
        )
        chunks.append(chunk)

    return chunks


def ingest_directory(
    directory: Path,
    version: str = CURRENT_DATASET_VERSION,
) -> list[DocumentChunk]:
    """Ingest all supported documents in a directory."""
    all_chunks = []
    supported = {".txt", ".pdf"}

    for file_path in sorted(directory.rglob("*")):
        if file_path.suffix.lower() in supported and file_path.is_file():
            chunks = ingest_document(file_path, version)
            all_chunks.extend(chunks)

    return all_chunks
