#!/usr/bin/env python3
"""Comprehensive tests for pantry_ops.py.

Run:  cd "$HOUSEHOLD_ROOT/pantry" && python3 -m pytest test_pantry_ops.py -v
"""

import copy
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pantry_ops as po
import ingredient_identity as ii

REAL_INVENTORY = Path(__file__).resolve().parent / "inventory.yaml"
REAL_ALIASES = Path(__file__).resolve().parent / "ingredient-aliases.yaml"


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _sample_inventory() -> dict:
    """A small deterministic inventory with known quantities."""
    return {
        "metadata": {
            "version": 1,
            "schema": "pantry-inventory/v1",
            "last_updated": "2026-09-10",
            "source": "test",
        },
        "items": [
            {"name": "butter", "quantity": {"amount": 2, "unit": "lb"},
             "location": "refrigerator", "status": "available"},
            {"name": "flour", "quantity": {"amount": 5, "unit": "lb"},
             "location": "pantry", "status": "available"},
            {"name": "olive oil", "quantity": {"amount": 1, "unit": "gal"},
             "location": "pantry", "status": "available"},
            {"name": "soy sauce", "quantity": {"amount": 500, "unit": "ml"},
             "location": "pantry", "status": "available"},
            {"name": "cumin seeds", "quantity": {"amount": None, "unit": "jar"},
             "location": "pantry", "status": "available"},
            {"name": "garlic", "quantity": {"amount": 3, "unit": "bulb"},
             "location": "pantry", "status": "available"},
            {"name": "diced tomatoes", "quantity": {"amount": 3, "unit": "can"},
             "location": "pantry", "status": "available"},
        ],
    }


def _write_inventory(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "inventory.yaml"
    with open(p, "w") as f:
        import yaml
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)
    return p


@pytest.fixture
def sample_inv_path(tmp_path):
    """Point pantry_ops at a temp inventory and log, and reset after."""
    p = _write_inventory(tmp_path, _sample_inventory())
    log = tmp_path / "pantry_mutations.log"
    return p, log


@pytest.fixture(autouse=True)
def _no_default_write():
    """Guard: never write to the real inventory."""
    before = REAL_INVENTORY.read_bytes()
    yield
    assert REAL_INVENTORY.read_bytes() == before, "Real inventory was modified!"


# ---------------------------------------------------------------------------
# Quantity parsing
# ---------------------------------------------------------------------------

class TestQuantityParse:
    def test_two_lb(self):
        q = po.Quantity.parse("2 lb")
        assert q.amount == Fraction(2)
        assert q.unit == "lb"

    def test_quarter_bottle(self):
        q = po.Quantity.parse("1/4 bottle")
        assert q.amount == Fraction(1, 4)
        assert q.unit == "bottle"

    def test_500_ml(self):
        q = po.Quantity.parse("500 ml")
        assert q.amount == 500
        assert q.unit == "ml"

    def test_gal_dot(self):
        q = po.Quantity.parse("1 gal.")
        assert q.amount == Fraction(1)
        assert q.unit == "gal"

    def test_full_jar(self):
        q = po.Quantity.parse("full jar")
        assert q.amount is None
        assert q.unit == "full jar"

    def test_low(self):
        q = po.Quantity.parse("low")
        assert q.amount is None
        assert q.unit == "low"

    def test_empty(self):
        q = po.Quantity.parse("")
        assert q.amount is None
        assert q.unit is None

    def test_cans(self):
        q = po.Quantity.parse("3 cans")
        assert q.amount == Fraction(3)
        assert q.unit == "can"

    def test_decimal_lb(self):
        q = po.Quantity.parse("2.5 lb")
        assert q.amount == Fraction(5, 2)
        assert q.unit == "lb"

    def test_decimal_kg(self):
        q = po.Quantity.parse("1.5 kg")
        assert q.amount == Fraction(3, 2)
        assert q.unit == "kg"


# ---------------------------------------------------------------------------
# Unit compatibility
# ---------------------------------------------------------------------------

class TestUnitCompatibility:
    def test_lb_with_oz(self):
        assert po.Quantity(2, "lb").is_compatible(po.Quantity(8, "oz"))

    def test_lb_with_kg(self):
        assert po.Quantity(2, "lb").is_compatible(po.Quantity(1, "kg"))

    def test_lb_with_g(self):
        assert po.Quantity(2, "lb").is_compatible(po.Quantity(500, "g"))

    def test_lb_incompatible_ml(self):
        assert not po.Quantity(2, "lb").is_compatible(po.Quantity(500, "ml"))

    def test_lb_incompatible_cup(self):
        assert not po.Quantity(2, "lb").is_compatible(po.Quantity(1, "cup"))

    def test_gal_with_L(self):
        assert po.Quantity(1, "gal").is_compatible(po.Quantity(1, "L"))

    def test_gal_with_ml(self):
        assert po.Quantity(1, "gal").is_compatible(po.Quantity(500, "ml"))

    def test_can_with_can(self):
        assert po.Quantity(3, "can").is_compatible(po.Quantity(1, "can"))

    def test_can_incompatible_jar(self):
        assert not po.Quantity(3, "can").is_compatible(po.Quantity(1, "jar"))

    def test_lb_incompatible_can(self):
        assert not po.Quantity(2, "lb").is_compatible(po.Quantity(1, "can"))


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

class TestArithmetic:
    def test_add_same_unit(self):
        assert po.Quantity(2, "lb") + po.Quantity(1, "lb") == \
            po.Quantity(3, "lb")

    def test_add_mixed_units(self):
        assert po.Quantity(1, "lb") + po.Quantity(16, "oz") == \
            po.Quantity(2, "lb")

    def test_add_gal_ml(self):
        # 1 gal + 500 ml
        result = po.Quantity(1, "gal") + po.Quantity(500, "ml")
        # 500 ml = 0.132086 gal, so 1.132086
        assert abs(float(result.amount) - 1.132086) < 1e-4

    def test_add_coarse_rejected(self):
        with pytest.raises(ValueError):
            po.Quantity(None, "jar") + po.Quantity(1, "jar")

    def test_add_unknown_rejected(self):
        with pytest.raises(ValueError):
            po.Quantity(1, "lb") + po.Quantity(1, "flour")

    def test_sub_same_unit(self):
        assert po.Quantity(3, "lb") - po.Quantity(1, "lb") == \
            po.Quantity(2, "lb")

    def test_sub_negative_rejected(self):
        with pytest.raises(ValueError):
            po.Quantity(1, "lb") - po.Quantity(2, "lb")

    def test_sub_mixed_units(self):
        assert po.Quantity(2, "lb") - po.Quantity(16, "oz") == \
            po.Quantity(1, "lb")


# ---------------------------------------------------------------------------
# Identity resolution (real inventory)
# ---------------------------------------------------------------------------

class TestIdentityResolution:
    @pytest.fixture
    def real_inv(self):
        with open(REAL_INVENTORY) as f:
            import yaml
            return yaml.safe_load(f)

    def test_known_item(self, real_inv):
        mr, record, index = po.resolve_item("garlic", real_inv)
        assert record is not None
        assert record["name"] == "garlic"
        assert index is not None

    def test_alias(self, real_inv):
        # 'kashmiri red chilli' resolves via alias to the powder or chillies
        mr, record, index = po.resolve_item("kashmiri red chilli", real_inv)
        assert record is not None
        assert "Kashmiri red chilli" in record["name"]

    def test_no_match(self, real_inv):
        mr, record, index = po.resolve_item("truffle oil", real_inv)
        assert record is None
        assert index is None
        assert mr.status == "no_match"


# ---------------------------------------------------------------------------
# Operation tests: add / consume / adjust / unavailable / low / verify
# ---------------------------------------------------------------------------

class TestOperations:
    def _ops_inventory(self, tmp_path, data=None):
        return _write_inventory(tmp_path, data or _sample_inventory())

    def _commit_result(self, tmp_path, inv_path, log, ops):
        plan = po.plan_operations(ops, inventory_path=inv_path)
        assert plan.valid, f"plan errors: {plan.errors}"
        return po.commit_plan(plan.to_dict(), inventory_path=inv_path,
                              log_path=log)

    def test_add_existing_numeric(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("add", "1 lb butter")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "butter"][0]
        assert rec["quantity"]["amount"] == 3
        assert rec["quantity"]["unit"] == "lb"

    def test_add_new_item_flagged(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        plan = po.plan_operations([("add", "2 bag spinach")],
                                  inventory_path=inv_path)
        assert plan.valid
        op = plan.operations[0]
        assert op.needs_approval is True
        assert op.after["name"] == "spinach"
        # record not in inventory until commit
        inv = po.load_inventory(inv_path)
        assert len(inv["items"]) == 7
        # but plan does not write
        op2 = plan.operations[0]
        assert op2.resolved_index is None

    def test_consume(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("consume", "1 lb butter")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "butter"][0]
        assert rec["quantity"]["amount"] == 1
        assert rec["quantity"]["unit"] == "lb"

    def test_consume_units(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("consume", "16 oz butter")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "butter"][0]
        assert rec["quantity"]["amount"] == 1
        assert rec["quantity"]["unit"] == "lb"

    def test_consume_over_rejected(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        plan = po.plan_operations([("consume", "5 lb butter")],
                                  inventory_path=inv_path)
        assert not plan.valid
        assert any("Over-consumption" in e for e in plan.errors)
        # nothing written
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "butter"][0]
        assert rec["quantity"]["amount"] == 2

    def test_consume_coarse_rejected(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        plan = po.plan_operations([("consume", "1 jar cumin seeds")],
                                  inventory_path=inv_path)
        assert not plan.valid
        assert any("non-numeric" in e.lower() or "adjust" in e.lower()
                   for e in plan.errors)

    def test_adjust_replaces(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("adjust", "10 lb flour")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "flour"][0]
        assert rec["quantity"]["amount"] == 10
        assert rec["quantity"]["unit"] == "lb"

    def test_unavailable(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("unavailable", "garlic")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "garlic"][0]
        assert rec["status"] == "unavailable"
        assert rec["quantity"]["amount"] is None
        assert rec["quantity"]["unit"] is None

    def test_low(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("low", "olive oil")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "olive oil"][0]
        assert rec["status"] == "low"
        # quantity preserved (coarse/null ok)
        assert rec["quantity"]["amount"] == 1

    def test_low_with_qty(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit_result(tmp_path, inv_path, log,
                                  [("low", "1 cup olive oil")])
        assert res["applied"] == 1
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "olive oil"][0]
        assert rec["status"] == "low"
        assert rec["quantity"]["amount"] == 1
        assert rec["quantity"]["unit"] == "cup"

    def test_verify_no_mutation(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        plan = po.plan_operations([("verify", "flour")],
                                  inventory_path=inv_path)
        assert plan.valid
        assert len(plan.operations) == 1
        assert plan.operations[0].after is not None
        assert plan.operations[0].resolved_name == "flour"
        res = po.commit_plan(plan.to_dict(), inventory_path=inv_path,
                             log_path=log)
        assert res["applied"] == 0  # verify does not mutate
        inv = po.load_inventory(inv_path)
        rec = [i for i in inv["items"] if i["name"] == "flour"][0]
        assert rec["quantity"]["amount"] == 5


# ---------------------------------------------------------------------------
# Batch tests
# ---------------------------------------------------------------------------

class TestBatch:
    def test_mixed_valid_ops(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        ops = [
            ("consume", "1 lb butter"),
            ("add", "1 lb flour"),
            ("adjust", "2 L olive oil"),
            ("unavailable", "garlic"),
        ]
        plan = po.plan_operations(ops, inventory_path=inv_path)
        assert plan.valid, plan.errors
        res = po.commit_plan(plan.to_dict(), inventory_path=inv_path,
                             log_path=log)
        assert res["applied"] == 4
        inv = po.load_inventory(inv_path)
        by_name = {i["name"]: i for i in inv["items"]}
        assert by_name["butter"]["quantity"]["amount"] == 1
        assert by_name["flour"]["quantity"]["amount"] == 6
        assert by_name["olive oil"]["quantity"]["unit"] == "L"
        assert abs(float(by_name["olive oil"]["quantity"]["amount"]) - 2.0) < 1e-6
        assert by_name["garlic"]["status"] == "unavailable"

    def test_one_invalid_rejects_batch(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        ops = [
            ("consume", "1 lb butter"),        # valid
            ("consume", "50 lb flour"),        # invalid (over)
        ]
        plan = po.plan_operations(ops, inventory_path=inv_path)
        assert not plan.valid
        # Batch atomicity: committing fails entirely.
        res = po.commit_plan(plan.to_dict(), inventory_path=inv_path,
                             log_path=log)
        assert res["applied"] == 0
        inv = po.load_inventory(inv_path)
        by_name = {i["name"]: i for i in inv["items"]}
        assert by_name["butter"]["quantity"]["amount"] == 2  # unchanged
        assert by_name["flour"]["quantity"]["amount"] == 5   # unchanged


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

class TestAudit:
    def test_log_entries(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        res = self._commit(tmp_path, inv_path, log,
                           [("consume", "1 lb butter"),
                            ("add", "1 lb flour")])
        assert res["applied"] == 2
        lines = [l for l in log.read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 2
        e1 = json.loads(lines[0])
        e2 = json.loads(lines[1])
        assert e1["op"] == "consume"
        assert e1["item"] == "butter"
        assert e1["before"]["quantity"]["amount"] == 2
        assert e1["after"]["quantity"]["amount"] == 1
        assert e1["delta"].startswith("-")
        assert e1["validation"] == "ok"
        assert "inv_hash_before" in e1 and "inv_hash_after" in e1
        assert e2["op"] == "add"
        assert e2["item"] == "flour"
        assert e2["before"]["quantity"]["amount"] == 5
        assert e2["after"]["quantity"]["amount"] == 6

    def _commit(self, tmp_path, inv_path, log, ops):
        plan = po.plan_operations(ops, inventory_path=inv_path)
        assert plan.valid, plan.errors
        return po.commit_plan(plan.to_dict(), inventory_path=inv_path,
                              log_path=log)


# ---------------------------------------------------------------------------
# No side effects
# ---------------------------------------------------------------------------

class TestNoSideEffects:
    def test_aliases_unchanged(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        before = REAL_ALIASES.read_bytes()
        plan = po.plan_operations([("consume", "1 lb butter")],
                                  inventory_path=inv_path)
        po.commit_plan(plan.to_dict(), inventory_path=inv_path, log_path=log)
        assert REAL_ALIASES.read_bytes() == before

    def test_inventory_unchanged_on_plan_fail(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        before = inv_path.read_bytes()
        plan = po.plan_operations([("consume", "50 lb flour")],
                                  inventory_path=inv_path)
        assert not plan.valid
        po.commit_plan(plan.to_dict(), inventory_path=inv_path, log_path=log)
        assert inv_path.read_bytes() == before


# ---------------------------------------------------------------------------
# Approval boundary
# ---------------------------------------------------------------------------

class TestApprovalBoundary:
    def test_plan_does_not_write(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        before = inv_path.read_bytes()
        po.plan_operations([("consume", "1 lb butter"),
                            ("add", "2 bag spinach")],
                           inventory_path=inv_path)
        assert inv_path.read_bytes() == before

    def test_commit_staleness_check(self, tmp_path, sample_inv_path):
        inv_path, log = sample_inv_path
        plan = po.plan_operations([("consume", "1 lb butter")],
                                  inventory_path=inv_path)
        plan_dict = plan.to_dict()
        # Tamper with the inventory between plan and commit.
        with open(inv_path, "a") as f:
            f.write("# tampered\n")
        before = inv_path.read_bytes()
        res = po.commit_plan(plan_dict, inventory_path=inv_path, log_path=log)
        assert res["applied"] == 0
        assert any("Staleness" in e or "staleness" in e for e in res["errors"])
        assert inv_path.read_bytes() == before


# ---------------------------------------------------------------------------
# Quantity to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_numeric(self):
        assert po.Quantity(2, "lb").to_dict() == {"amount": 2, "unit": "lb"}

    def test_to_dict_fraction(self):
        d = po.Quantity(Fraction(1, 4), "cup").to_dict()
        assert d["unit"] == "cup"
        assert abs(float(d["amount"]) - 0.25) < 1e-6

    def test_from_dict_null(self):
        q = po.Quantity.from_dict({"amount": None, "unit": None})
        assert q.amount is None
        assert q.unit is None

    def test_from_dict_coarse(self):
        q = po.Quantity.from_dict({"amount": "full jar", "unit": "jar"})
        assert q.amount is None
        assert "jar" in (q.unit or "")

    def test_from_dict_numeric(self):
        q = po.Quantity.from_dict({"amount": 3, "unit": "lb"})
        assert q.amount == Fraction(3)
        assert q.unit == "lb"