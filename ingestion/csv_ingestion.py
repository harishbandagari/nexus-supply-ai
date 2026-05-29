"""NexusSupply AI — CSV Ingestion with Pydantic Validation.

Ingests supplier registry CSV files, validates each record
against the SupplierRecord schema, quarantines invalid records,
and loads valid records into SQLite.
"""

import json
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from config import CURRENT_DATASET_VERSION, RAW_DATA_DIR
from database.sqlite_store import (
    log_audit_event,
    quarantine_record,
    save_dataset_version,
    upsert_suppliers,
)
from validation.schemas import IngestionAuditEntry, SupplierRecord


def ingest_supplier_csv(
    file_path: Path | None = None,
    version: str = CURRENT_DATASET_VERSION,
) -> IngestionAuditEntry:
    """Ingest a supplier CSV file with full validation and governance.

    Returns an audit entry summarizing the ingestion results.
    """
    if file_path is None:
        file_path = RAW_DATA_DIR / "suppliers.csv"

    df = pd.read_csv(file_path)

    valid_records: list[dict] = []
    errors: list[str] = []
    quarantined = 0

    for idx, row in df.iterrows():
        raw = row.to_dict()
        try:
            record = SupplierRecord(**raw)
            valid_records.append(record.model_dump(mode="json"))
        except ValidationError as e:
            error_msg = f"Row {idx}: {e.error_count()} validation error(s) — {e.errors()[0]['msg']}"
            errors.append(error_msg)
            quarantine_record(
                dataset_name="suppliers",
                version=version,
                raw_data=json.dumps(raw, default=str),
                error=str(e),
            )
            quarantined += 1

    # Load valid records into SQLite
    if valid_records:
        upsert_suppliers(valid_records, version)

    # Record dataset version
    save_dataset_version(
        version_id=f"suppliers_{version}",
        dataset_name="suppliers",
        record_count=len(valid_records),
    )

    # Audit log
    audit = IngestionAuditEntry(
        dataset_name="suppliers",
        dataset_version=version,
        record_count=len(df),
        valid_count=len(valid_records),
        quarantined_count=quarantined,
        errors=errors,
    )

    log_audit_event(
        event_type="csv_ingestion",
        dataset_name=audit.dataset_name,
        dataset_version=audit.dataset_version,
        details=f"Valid: {audit.valid_count}, Quarantined: {audit.quarantined_count}",
        record_count=audit.record_count,
        valid_count=audit.valid_count,
        quarantined_count=audit.quarantined_count,
    )

    return audit
