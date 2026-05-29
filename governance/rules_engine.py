"""NexusSupply AI — Deterministic Governance Rules Engine.

Handles all deterministic validation that MUST NOT be delegated to LLMs:
    - MOQ validation
    - Approved Vendor List (AVL) checks
    - Sourcing allocation cap enforcement
    - Temporal contract validity checks

These rules are deterministic Python logic — no AI involved.
"""

from datetime import date, datetime

from validation.schemas import GovernanceCheckResult


def validate_supplier_recommendation(supplier: dict) -> list[GovernanceCheckResult]:
    """Run all deterministic governance checks against a supplier.

    Returns a list of GovernanceCheckResult for each check.
    """
    checks = [
        _check_avl_status(supplier),
        _check_contract_validity(supplier),
        _check_moq_feasibility(supplier),
        _check_allocation_cap(supplier),
        _check_headroom_capacity(supplier),
    ]
    return checks


def _check_avl_status(supplier: dict) -> GovernanceCheckResult:
    """Verify supplier is on the Approved Vendor List."""
    status = supplier.get("approved_vendor_status", "")
    passed = status == "AVL"

    return GovernanceCheckResult(
        check_name="AVL Status",
        passed=passed,
        details=f"Supplier AVL status: {status}. "
                + ("Approved for production sourcing."
                   if passed else
                   "Non-AVL supplier requires VP Procurement exception approval."),
        supplier_id=supplier.get("supplier_id"),
    )


def _check_contract_validity(supplier: dict) -> GovernanceCheckResult:
    """Verify supplier contract has not expired."""
    contract_end = supplier.get("contract_end_date", "")
    supplier_id = supplier.get("supplier_id", "")

    try:
        if isinstance(contract_end, str):
            end_date = date.fromisoformat(contract_end)
        else:
            end_date = contract_end

        today = date.today()
        passed = end_date >= today
        days_remaining = (end_date - today).days

        details = (
            f"Contract valid until {end_date.isoformat()} ({days_remaining} days remaining)."
            if passed else
            f"Contract expired on {end_date.isoformat()} ({abs(days_remaining)} days ago). "
            "Contract renewal required before sourcing."
        )
    except (ValueError, TypeError):
        passed = False
        details = f"Invalid contract end date: {contract_end}"

    return GovernanceCheckResult(
        check_name="Contract Validity",
        passed=passed,
        details=details,
        supplier_id=supplier_id,
    )


def _check_moq_feasibility(supplier: dict) -> GovernanceCheckResult:
    """Validate MOQ is within operational range."""
    moq = supplier.get("moq", 0)
    supplier_id = supplier.get("supplier_id", "")

    # MOQ above 50,000 flagged as potential concern for emergency sourcing
    max_emergency_moq = 50000
    passed = 0 < moq <= max_emergency_moq

    if passed:
        details = f"MOQ of {moq:,} units is within acceptable range for emergency sourcing."
    elif moq > max_emergency_moq:
        details = (
            f"MOQ of {moq:,} units exceeds emergency sourcing threshold ({max_emergency_moq:,}). "
            "May require volume commitment review."
        )
    else:
        details = f"Invalid MOQ value: {moq}"

    return GovernanceCheckResult(
        check_name="MOQ Feasibility",
        passed=passed,
        details=details,
        supplier_id=supplier_id,
    )


def _check_allocation_cap(supplier: dict) -> GovernanceCheckResult:
    """Verify sourcing allocation cap allows additional volume."""
    cap = supplier.get("sourcing_allocation_cap", 0)
    supplier_id = supplier.get("supplier_id", "")

    # Allocation cap of at least 10% required for meaningful alternate sourcing
    min_viable_cap = 0.10
    passed = cap >= min_viable_cap

    details = (
        f"Allocation cap: {cap:.0%}. Sufficient headroom for alternate sourcing."
        if passed else
        f"Allocation cap: {cap:.0%}. Below minimum viable threshold ({min_viable_cap:.0%}). "
        "Allocation increase requires VP Procurement approval."
    )

    return GovernanceCheckResult(
        check_name="Allocation Cap",
        passed=passed,
        details=details,
        supplier_id=supplier_id,
    )


def _check_headroom_capacity(supplier: dict) -> GovernanceCheckResult:
    """Verify supplier has available headroom capacity."""
    headroom = supplier.get("headroom_capacity_units", 0)
    supplier_id = supplier.get("supplier_id", "")

    min_headroom = 1000
    passed = headroom >= min_headroom

    details = (
        f"Headroom capacity: {headroom:,} units. Sufficient for surge demand."
        if passed else
        f"Headroom capacity: {headroom:,} units. Below minimum threshold ({min_headroom:,}). "
        "Capacity confirmation required before sourcing."
    )

    return GovernanceCheckResult(
        check_name="Headroom Capacity",
        passed=passed,
        details=details,
        supplier_id=supplier_id,
    )
