"""Tests for NexusSupply AI — Governance Rules Engine.

Tests all 5 deterministic governance checks:
- AVL status verification
- Contract validity check
- MOQ feasibility
- Allocation cap enforcement
- Headroom capacity check
"""

import pytest
from datetime import date, timedelta

from governance.rules_engine import (
    validate_supplier_recommendation,
    _check_avl_status,
    _check_contract_validity,
    _check_moq_feasibility,
    _check_allocation_cap,
    _check_headroom_capacity,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def valid_supplier():
    """A supplier that passes all governance checks."""
    return {
        "supplier_id": "SUP-017",
        "supplier_name": "Thai Electronics Solutions",
        "component_name": "OLED Driver ICs",
        "approved_vendor_status": "AVL",
        "lead_time_days": 32,
        "contract_end_date": (date.today() + timedelta(days=365)).isoformat(),
        "moq": 6000,
        "sourcing_allocation_cap": 0.20,
        "headroom_capacity_units": 70000,
        "historical_reliability_score": 0.82,
        "risk_score": 0.42,
    }


@pytest.fixture
def non_avl_supplier(valid_supplier):
    """A supplier that fails AVL check."""
    return {**valid_supplier, "approved_vendor_status": "Non-AVL"}


@pytest.fixture
def expired_contract_supplier(valid_supplier):
    """A supplier with an expired contract."""
    return {
        **valid_supplier,
        "contract_end_date": (date.today() - timedelta(days=90)).isoformat(),
    }


@pytest.fixture
def high_moq_supplier(valid_supplier):
    """A supplier with MOQ exceeding emergency threshold."""
    return {**valid_supplier, "moq": 100000}


@pytest.fixture
def low_allocation_supplier(valid_supplier):
    """A supplier with allocation cap below viable threshold."""
    return {**valid_supplier, "sourcing_allocation_cap": 0.05}


@pytest.fixture
def low_headroom_supplier(valid_supplier):
    """A supplier with insufficient headroom capacity."""
    return {**valid_supplier, "headroom_capacity_units": 500}


# ── AVL Status Tests ──────────────────────────────────────────────────


class TestAVLStatus:
    def test_avl_approved_passes(self, valid_supplier):
        result = _check_avl_status(valid_supplier)
        assert result.passed is True
        assert result.check_name == "AVL Status"
        assert "Approved for production sourcing" in result.details

    def test_non_avl_fails(self, non_avl_supplier):
        result = _check_avl_status(non_avl_supplier)
        assert result.passed is False
        assert "exception approval" in result.details.lower()

    def test_missing_status_fails(self, valid_supplier):
        valid_supplier["approved_vendor_status"] = ""
        result = _check_avl_status(valid_supplier)
        assert result.passed is False

    def test_supplier_id_tracked(self, valid_supplier):
        result = _check_avl_status(valid_supplier)
        assert result.supplier_id == "SUP-017"


# ── Contract Validity Tests ───────────────────────────────────────────


class TestContractValidity:
    def test_valid_contract_passes(self, valid_supplier):
        result = _check_contract_validity(valid_supplier)
        assert result.passed is True
        assert "days remaining" in result.details

    def test_expired_contract_fails(self, expired_contract_supplier):
        result = _check_contract_validity(expired_contract_supplier)
        assert result.passed is False
        assert "expired" in result.details.lower()

    def test_contract_expiring_today_passes(self, valid_supplier):
        valid_supplier["contract_end_date"] = date.today().isoformat()
        result = _check_contract_validity(valid_supplier)
        assert result.passed is True

    def test_contract_expired_yesterday_fails(self, valid_supplier):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        valid_supplier["contract_end_date"] = yesterday
        result = _check_contract_validity(valid_supplier)
        assert result.passed is False

    def test_invalid_date_format_fails(self, valid_supplier):
        valid_supplier["contract_end_date"] = "not-a-date"
        result = _check_contract_validity(valid_supplier)
        assert result.passed is False
        assert "Invalid" in result.details

    def test_far_future_contract_passes(self, valid_supplier):
        valid_supplier["contract_end_date"] = "2030-12-31"
        result = _check_contract_validity(valid_supplier)
        assert result.passed is True


# ── MOQ Feasibility Tests ─────────────────────────────────────────────


class TestMOQFeasibility:
    def test_normal_moq_passes(self, valid_supplier):
        result = _check_moq_feasibility(valid_supplier)
        assert result.passed is True
        assert "within acceptable range" in result.details

    def test_moq_at_threshold_passes(self, valid_supplier):
        valid_supplier["moq"] = 50000
        result = _check_moq_feasibility(valid_supplier)
        assert result.passed is True

    def test_moq_above_threshold_fails(self, high_moq_supplier):
        result = _check_moq_feasibility(high_moq_supplier)
        assert result.passed is False
        assert "exceeds" in result.details.lower()

    def test_moq_just_above_threshold_fails(self, valid_supplier):
        valid_supplier["moq"] = 50001
        result = _check_moq_feasibility(valid_supplier)
        assert result.passed is False

    def test_moq_of_one_passes(self, valid_supplier):
        valid_supplier["moq"] = 1
        result = _check_moq_feasibility(valid_supplier)
        assert result.passed is True

    def test_zero_moq_fails(self, valid_supplier):
        valid_supplier["moq"] = 0
        result = _check_moq_feasibility(valid_supplier)
        assert result.passed is False


# ── Allocation Cap Tests ──────────────────────────────────────────────


class TestAllocationCap:
    def test_sufficient_cap_passes(self, valid_supplier):
        result = _check_allocation_cap(valid_supplier)
        assert result.passed is True
        assert "Sufficient headroom" in result.details

    def test_cap_at_threshold_passes(self, valid_supplier):
        valid_supplier["sourcing_allocation_cap"] = 0.10
        result = _check_allocation_cap(valid_supplier)
        assert result.passed is True

    def test_cap_below_threshold_fails(self, low_allocation_supplier):
        result = _check_allocation_cap(low_allocation_supplier)
        assert result.passed is False
        assert "Below minimum" in result.details

    def test_zero_cap_fails(self, valid_supplier):
        valid_supplier["sourcing_allocation_cap"] = 0.0
        result = _check_allocation_cap(valid_supplier)
        assert result.passed is False

    def test_full_cap_passes(self, valid_supplier):
        valid_supplier["sourcing_allocation_cap"] = 1.0
        result = _check_allocation_cap(valid_supplier)
        assert result.passed is True


# ── Headroom Capacity Tests ───────────────────────────────────────────


class TestHeadroomCapacity:
    def test_sufficient_headroom_passes(self, valid_supplier):
        result = _check_headroom_capacity(valid_supplier)
        assert result.passed is True
        assert "Sufficient for surge demand" in result.details

    def test_headroom_at_threshold_passes(self, valid_supplier):
        valid_supplier["headroom_capacity_units"] = 1000
        result = _check_headroom_capacity(valid_supplier)
        assert result.passed is True

    def test_headroom_below_threshold_fails(self, low_headroom_supplier):
        result = _check_headroom_capacity(low_headroom_supplier)
        assert result.passed is False
        assert "Below minimum" in result.details

    def test_zero_headroom_fails(self, valid_supplier):
        valid_supplier["headroom_capacity_units"] = 0
        result = _check_headroom_capacity(valid_supplier)
        assert result.passed is False


# ── Full Validation Pipeline Tests ────────────────────────────────────


class TestFullValidation:
    def test_valid_supplier_passes_all_checks(self, valid_supplier):
        results = validate_supplier_recommendation(valid_supplier)
        assert len(results) == 5
        assert all(r.passed for r in results)

    def test_non_avl_supplier_fails_one_check(self, non_avl_supplier):
        results = validate_supplier_recommendation(non_avl_supplier)
        assert len(results) == 5
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert failed[0].check_name == "AVL Status"

    def test_multiple_failures(self, valid_supplier):
        """Supplier with expired contract AND insufficient headroom."""
        valid_supplier["contract_end_date"] = "2020-01-01"
        valid_supplier["headroom_capacity_units"] = 100
        results = validate_supplier_recommendation(valid_supplier)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 2
        failed_names = {r.check_name for r in failed}
        assert "Contract Validity" in failed_names
        assert "Headroom Capacity" in failed_names

    def test_all_checks_fail(self, valid_supplier):
        """Supplier that fails every single check."""
        bad_supplier = {
            **valid_supplier,
            "approved_vendor_status": "Non-AVL",
            "contract_end_date": "2020-01-01",
            "moq": 100000,
            "sourcing_allocation_cap": 0.01,
            "headroom_capacity_units": 0,
        }
        results = validate_supplier_recommendation(bad_supplier)
        assert all(not r.passed for r in results)
