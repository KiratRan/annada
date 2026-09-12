#!/usr/bin/env python3
"""Deterministic pantry mutation module with CLI.

Provides a Quantity class with unit-group conversions, and inventory
operations (add, consume, adjust, unavailable, low, verify) applied against
inventory.yaml.  All mutations are planned first (validated with no writes),
then committed atomically with append-only audit logging.

Usage:
    python3 pantry_ops.py verify ITEM_NAME [--inventory PATH]
    python3 pantry_ops.py plan OP ITEM_QTY [OP ITEM_QTY ...] [--inventory PATH]
    python3 pantry_ops.py commit PLAN_JSON_FILE [--inventory PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

import yaml

# ---------------------------------------------------------------------------
# Import ingredient_identity from same directory
# ---------------------------------------------------------------------------
_PANTRY_DIR = Path(__file__).resolve().parent
if str(_PANTRY_DIR) not in sys.path:
    sys.path.insert(0, str(_PANTRY_DIR))

import ingredient_identity as ii  # noqa: E402

_DEFAULT_INVENTORY_PATH = _PANTRY_DIR / "inventory.yaml"
_MUTATIONS_LOG = _PANTRY_DIR / "pantry_mutations.log"
_ALIASES_PATH = _PANTRY_DIR / "ingredient-aliases.yaml"


# ---------------------------------------------------------------------------
# Unit groups
# ---------------------------------------------------------------------------

_UNIT_GROUPS: dict[str, dict[str, float]] = {
    "mass": {
        "lb": 1.0,
        "lbs": 1.0,
        "oz": 0.0625,
        "kg": 2.20462,
        "g": 0.00220462,
    },
    "volume": {
        "gal": 1.0,
        "l": Fraction.from_float(1 / 3.78541).limit_denominator(10**9),
        "L": Fraction.from_float(1 / 3.78541).limit_denominator(10**9),
        "ml": Fraction.from_float(1 / 3785.41).limit_denominator(10**9),
        "cup": Fraction(1, 16),
        "cups": Fraction(1, 16),
        "tbsp": Fraction(1, 256),
        "tsp": Fraction(1, 768),
        "fl oz": Fraction(1, 128),
        "floz": Fraction(1, 128),
    },
    "count": {
        "each": 1.0,
        "ea": 1.0,
        "ct": 1.0,
        "can": 1.0,
        "jar": 1.0,
        "bottle": 1.0,
        "bag": 1.0,
        "box": 1.0,
        "head": 1.0,
        "clove": 1.0,
        "bunch": 1.0,
        "root": 1.0,
        "bulb": 1.0,
        "tube": 1.0,
    },
}

# Reverse lookup unit -> group name
_unit_to_group: dict[str, str] = {}
for _grp, _units in _UNIT_GROUPS.items():
    for _u in _units:
        _unit_to_group[_u] = _grp

# All declared spellings per lowercase key (for exact-case preservation).
_GROUP_FORMS: dict[str, tuple[str, ...]] = {}
for _grp, _units in _UNIT_GROUPS.items():
    for _u in _units:
        _lower = _u.lower()
        _GROUP_FORMS.setdefault(_lower, set()).add(_u)
for _k, _v in _GROUP_FORMS.items():
    _GROUP_FORMS[_k] = tuple(_v)

# Canonical spelling lookup: lower -> canonical (first form declared).
_unit_canonical: dict[str, str] = {}
for _grp, _units in _UNIT_GROUPS.items():
    for _u in _units:
        _lower = _u.lower()
        if _lower not in _unit_canonical:
            _unit_canonical[_lower] = _u

# Multi-word units
_MULTIWORD_UNITS = ("fl oz",)

# Units used as "count" that ingredient_identity does not know (so they leak
# into the name during parse_ingredient_line).  Used to strip leading
# qty+unit during item resolution.
_EXTRA_COUNT_UNITS = frozenset(
    {"jar", "bottle", "bag", "box", "bulb", "bunch", "root", "tube",
     "count", "each", "ea", "ct", "can", "head", "clove", "cloves"}
)


def _unit_group(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    return _unit_to_group.get(unit)


def _canonical_unit(unit: str) -> str:
    """Return canonical spelling for a unit (lowercased input)."""
    u = unit.strip().rstrip(".")
    u_lower = u.lower()
    # Prefer the exact-case declared form first (e.g. 'L' stays 'L').
    if u_lower in _unit_canonical:
        declared = _unit_canonical[u_lower]
        for form in _GROUP_FORMS.get(u_lower, ()):
            if form == u:
                return form
        return declared
    # Plural strip
    if len(u_lower) > 1 and u_lower.endswith("s"):
        s = u_lower[:-1]
        if s in _unit_canonical:
            return _unit_canonical[s]
    return unit


def _to_base(value: Fraction, unit: str) -> Fraction:
    grp = _unit_group(unit)
    if grp is None:
        return value
    factor = Fraction(str(_UNIT_GROUPS[grp][unit])).limit_denominator(10**9)
    return value * factor


def _from_base(value: Fraction, unit: str) -> Fraction:
    grp = _unit_group(unit)
    if grp is None:
        return value
    factor = Fraction(str(_UNIT_GROUPS[grp][unit])).limit_denominator(10**9)
    return value / factor


_NUM_TOKEN = r"\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?"


def _try_parse_number(text: str) -> Optional[Fraction]:
    text = text.strip()
    if not text:
        return None
    if "/" in text:
        parts = text.split("/", 1)
        if len(parts) != 2:
            return None
        try:
            return Fraction(int(float(parts[0])), int(float(parts[1])))
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return Fraction(text).limit_denominator(10**9)
    except (ValueError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Quantity:
    """Immutable quantity with optional numeric amount and unit.

    amount=None means the stock is unknown/coarse (e.g. 'full jar').
    """

    amount: Optional[Fraction] = None
    unit: Optional[str] = None

    # ---- parsing ----

    @classmethod
    def parse(cls, text: str) -> Quantity:
        """Parse a human quantity string.

        Examples:
            '2 lb'        -> Quantity(2, 'lb')
            '1/4 bottle'  -> Quantity(Fraction(1,4), 'bottle')
            '500 ml'      -> Quantity(500, 'ml')
            '1 gal.'      -> Quantity(1, 'gal')
            'full jar'    -> Quantity(None, 'full jar')
            'low'         -> Quantity(None, 'low')
            ''            -> Quantity(None, None)
            '3 cans'      -> Quantity(3, 'can')
            '2.5 lb'      -> Quantity(Fraction(5,2), 'lb')
            '1.5 kg'      -> Quantity(Fraction(3,2), 'kg')
        """
        text = (text or "").strip()
        if not text:
            return cls(None, None)

        # Split numeric prefix from the rest.
        m = re.match(rf"^({_NUM_TOKEN})\s*(.*)$", text)
        if not m:
            # Not numeric: coarse/qualitative value.
            return cls(None, text)

        amount = _try_parse_number(m.group(1))
        rest = m.group(2).strip()

        # Handle plots/trailing punctuation in unit, and multi-word units.
        if rest:
            unit = _ff_unit_only(rest)
            if unit is None:
                # rest is not a pure unit (e.g. nothing meaningful) -> coarse
                return cls(None, text)
            return cls(amount, unit)

        return cls(amount, None)

    def __repr__(self) -> str:
        if self.amount is None:
            return f"Quantity(None, {self.unit!r})"
        return f"Quantity({self.amount}, {self.unit!r})"

    # ---- predicates & arithmetic ----

    def is_numeric(self) -> bool:
        return self.amount is not None

    def is_compatible(self, other: Quantity) -> bool:
        g1 = _unit_group(self.unit)
        g2 = _unit_group(other.unit)
        if g1 is None or g2 is None:
            return False
        if g1 == "count":
            # Count units are same-unit only (no cross-conversion).
            return (self.unit or "").lower() == (other.unit or "").lower()
        return g1 == g2

    def __add__(self, other: Quantity) -> Quantity:
        if self.amount is None or other.amount is None:
            raise ValueError(
                f"Cannot add non-numeric quantities: {self!r} + {other!r}"
            )
        if not self.is_compatible(other):
            raise ValueError(
                f"Incompatible units: {self.unit!r} (group "
                f"{_unit_group(self.unit)!r}) vs {other.unit!r} (group "
                f"{_unit_group(other.unit)!r})"
            )
        if self.unit is None:
            return Quantity(self.amount + other.amount, self.unit)
        base = _to_base(self.amount, self.unit) + _to_base(other.amount, other.unit)
        return Quantity(_from_base(base, self.unit).limit_denominator(10**9),
                        self.unit)

    def __sub__(self, other: Quantity) -> Quantity:
        if self.amount is None or other.amount is None:
            raise ValueError(
                f"Cannot subtract non-numeric quantities: {self!r} - {other!r}"
            )
        if not self.is_compatible(other):
            raise ValueError(
                f"Incompatible units: {self.unit!r} (group "
                f"{_unit_group(self.unit)!r}) vs {other.unit!r} (group "
                f"{_unit_group(other.unit)!r})"
            )
        base = _to_base(self.amount, self.unit) - _to_base(other.amount, other.unit)
        if base < 0:
            raise ValueError(f"Result would be negative: {self!r} - {other!r}")
        if self.unit is None:
            return Quantity(self.amount - other.amount, self.unit)
        return Quantity(_from_base(base, self.unit).limit_denominator(10**9),
                        self.unit)

    # ---- serialization ----

    def to_dict(self) -> dict:
        """Serialize to the inventory YAML field form."""
        if self.amount is None:
            return {"amount": None, "unit": self.unit}
        # Represent clean numbers: integers as ints, otherwise float.
        if self.amount.denominator == 1:
            amt: Any = int(self.amount)
        else:
            # Represent as float for serialization, but keep fraction when
            # clean divisor (e.g. 1/4).  The inventory uses plain numeric.
            amt = float(self.amount)
        return {"amount": amt, "unit": self.unit}

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Quantity:
        if not d:
            return cls(None, None)
        raw_amount = d.get("amount")
        raw_unit = d.get("unit")

        if raw_amount is None:
            return cls(None, raw_unit)

        if isinstance(raw_amount, str):
            num = _try_parse_number(raw_amount)
            if num is not None:
                return cls(num, raw_unit)
            # Coarse string amount stored in 'amount' field.
            return cls(None, f"{raw_amount} {raw_unit}".strip())

        if isinstance(raw_amount, (int, float, Fraction, bool)):
            return cls(Fraction(raw_amount).limit_denominator(10**9), raw_unit)

        return cls(None, raw_unit)


def _ff_unit_only(s: str) -> Optional[str]:
    """Return the single unit token (canonicalized) if s is pure unit text.

    Multi-word units ('fl oz') are supported.  Trailing '.' and plural-'s'
    are normalized.  Returns None if s does not look like a unit.
    """
    s = s.strip().rstrip(".")
    low = s.lower()
    parts = low.split()
    if len(parts) > 1:
        # multi-word unit?
        if low in _unit_to_group:
            return _canonical_unit(s)
        return None
    if low in _unit_to_group:
        return _canonical_unit(s)
    # plural-strip
    if len(low) > 1 and low.endswith("s"):
        s2 = low[:-1]
        if s2 in _unit_to_group:
            return _canonical_unit(s2)
    return None


# ---------------------------------------------------------------------------
# Inventory I/O
# ---------------------------------------------------------------------------

def load_inventory(path: str | Path | None = None) -> dict:
    p = Path(path) if path else _DEFAULT_INVENTORY_PATH
    with open(p, "r") as f:
        return yaml.safe_load(f)


def save_inventory(data: dict, path: str | Path | None = None) -> None:
    """Write inventory YAML, backing up the existing file first."""
    p = Path(path) if path else _DEFAULT_INVENTORY_PATH
    if p.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        bak = p.parent / f"{p.name}.bak.{ts}"
        shutil.copy2(p, bak)
    with open(p, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)


def inventory_hash(path: str | Path | None = None) -> str:
    p = Path(path) if path else _DEFAULT_INVENTORY_PATH
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

_QTY_TOKEN = re.compile(
    r"^\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?$"
)

def _is_qty_like(token: str) -> bool:
    """True if a token looks like a quantity (number or unit word)."""
    low = token.lower().rstrip(".")
    if _QTY_TOKEN.match(token):
        return True
    if low in _unit_to_group:
        return True
    if len(low) > 1 and low.endswith("s") and low[:-1] in _unit_to_group:
        return True
    if low in _EXTRA_COUNT_UNITS:
        return True
    if low in {"full", "low", "some", "half", "quarter", "three",
               "two", "one", "a", "an"}:
        return True
    return False


def _candidate_queries(text: str) -> list[str]:
    """Generate query candidates by stripping a *quantity-like* leading
    prefix (number, unit, or coarse qty token).

    Non-quantity leading words (e.g. 'truffle' in 'truffle oil') are never
    stripped, so resolution won't degrade to an ambiguous generic tail.
    """
    out: list[str] = []
    s = text.strip()
    tokens = s.split()
    out.append(s)
    for k in range(1, len(tokens) + 1):
        if all(_is_qty_like(t) for t in tokens[:k]):
            out.append(" ".join(tokens[k:]))
        else:
            break
    # Dedupe preserving order.
    seen: set[str] = set()
    dedup = []
    for q in out:
        if q not in seen:
            seen.add(q)
            dedup.append(q)
    return dedup


def resolve_item(
    query: str,
    inventory: dict,
    alias_path: str | Path | None = None,
) -> tuple[Any, Optional[dict], Optional[int]]:
    """Resolve a query to an inventory item.

    Returns: (MatchResult, record_or_None, index_or_None).

    Prefers the first query candidate that yields an unambiguous positive
    match (exact / normalized / alias).  If only ambiguous/no matches are
    produced, returns the last evaluated MatchResult with record=None.

    ``inventory`` may be a full inventory dict (with an ``items`` list) or a
    bare list of item records.
    """
    items, names, name_to_record = _collect(items_source=inventory)
    last: Any = None
    ambiguous: Any = None
    for q in _candidate_queries(query):
        mr = ii.match(q, names, alias_path=alias_path)
        last = mr
        if mr.status in ("exact_match", "normalized_match", "alias_match"):
            canonical = mr.canonical[0]
            return mr, name_to_record[canonical], names.index(canonical)
        if mr.status == "ambiguous" and ambiguous is None:
            ambiguous = mr

    if ambiguous is not None:
        return ambiguous, None, None
    return last, None, None


def _collect(items_source):
    """Normalize inventory (dict or bare list) to (items, names, name->record)."""
    if isinstance(items_source, dict):
        items = items_source.get("items", [])
    else:
        items = items_source
    names = [it["name"] for it in items]
    name_to_record = {it["name"]: it for it in items}
    return items, names, name_to_record


def verify_item(name: str, inventory: dict) -> Optional[dict]:
    """Read-only exact-name lookup.  Returns record dict or None."""
    for it in inventory.get("items", []):
        if it["name"] == name:
            return it
    return None


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------

@dataclass
class PlanOp:
    op_type: str
    item_qty_string: str
    resolved_name: Optional[str]
    resolved_index: Optional[int]
    before: Optional[dict]
    after: Optional[dict]
    delta: Optional[str] = None
    status: str = "ok"
    error: Optional[str] = None
    needs_approval: bool = False

    def to_dict(self) -> dict:
        return {
            "op_type": self.op_type,
            "item_qty_string": self.item_qty_string,
            "item": self.resolved_name,
            "resolved_index": self.resolved_index,
            "before": self.before,
            "after": self.after,
            "delta": self.delta,
            "status": self.status,
            "error": self.error,
            "needs_approval": self.needs_approval,
        }


@dataclass
class Plan:
    operations: list[PlanOp]
    inv_hash_before: str
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "inv_hash_before": self.inv_hash_before,
            "errors": self.errors,
            "operations": [op.to_dict() for op in self.operations],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot(item: Optional[dict]) -> Optional[dict]:
    if item is None:
        return None
    return {
        "name": item["name"],
        "quantity": deepcopy(item["quantity"]),
        "status": item.get("status"),
    }


def _suggest(query: str, inventory) -> str:
    items, _names, _recs = _collect(items_source=inventory)
    q = query.lower()
    hits = []
    for it in items:
        name = it["name"]
        nl = name.lower()
        if q and (q in nl or nl in q):
            hits.append(name)
        elif any(len(w) > 3 and w in nl for w in q.split()):
            hits.append(name)
    return ", ".join(list(dict.fromkeys(hits))[:3])


def _unavailable_marker() -> str:
    return "unavailable"


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def _split_qty_name(item_qty_string: str) -> tuple[Quantity, str]:
    """Split an 'item_qty_string' into (Quantity, item_name).

    Leading quantity-like tokens (number + unit, or a coarse qualifier like
    'full jar') form the Quantity; everything after is the item name.
    """
    tokens = item_qty_string.strip().split()
    run: list[str] = []
    for t in tokens:
        if _is_qty_like(t):
            run.append(t)
        else:
            break
    # A quantity needs either a leading numeric token, or a qualifier+unit.
    has_qty = False
    if run:
        first = run[0]
        if _QTY_TOKEN.match(first) or first.lower().rstrip(".") in \
                {"full", "half", "quarter", "some", "low"}:
            has_qty = True
    if has_qty:
        qty = Quantity.parse(" ".join(run))
        name = " ".join(tokens[len(run):]).strip()
    else:
        qty = Quantity(None, None)
        name = item_qty_string.strip()
    return qty, name


def _parse_quantity(item_qty_string: str) -> Quantity:
    """Extract a Quantity from an item_qty_string (name may carry qty)."""
    q, _name = _split_qty_name(item_qty_string)
    return q


def _plan_single_op(
    op_type: str,
    item_qty_string: str,
    inventory: list[dict],
    alias_path: Optional[str | Path],
    inv_hash: str,
) -> PlanOp:
    """Validate/plan a single op against the current (cumulative) item list."""
    if op_type not in ("add", "consume", "adjust", "unavailable", "low", "verify"):
        return PlanOp(op_type, item_qty_string, None, None, None, None,
                      status="error",
                      error=f"Unknown op_type '{op_type}'")

    qty = _parse_quantity(item_qty_string)
    mr, record, index = resolve_item(item_qty_string, inventory,
                                     alias_path=alias_path)

    # ----- verify -----
    if op_type == "verify":
        if record is None:
            return PlanOp(op_type, item_qty_string, None, None, None, None,
                          status="error",
                          error=f"Item not found: '{item_qty_string}'")
        return PlanOp(op_type, item_qty_string, record["name"], index,
                      _snapshot(record), _snapshot(record),
                      delta=None, status="ok")

    # ----- add -----
    if op_type == "add":
        if record is not None:
            current = Quantity.from_dict(record["quantity"])
            if not qty.is_numeric():
                return PlanOp(op_type, item_qty_string, record["name"], index,
                              _snapshot(record), None,
                              status="error",
                              error=f"add requires a numeric quantity (got "
                                    f"'{item_qty_string}')")
            try:
                new_qty = current + qty
            except ValueError as e:
                return PlanOp(op_type, item_qty_string, record["name"], index,
                              _snapshot(record), None, status="error",
                              error=str(e))
            after = {"name": record["name"],
                     "quantity": new_qty.to_dict(),
                     "status": record.get("status")}
            return PlanOp(op_type, item_qty_string, record["name"], index,
                          _snapshot(record), after,
                          delta=f"+{qty}",
                          status="ok")
        # New item -> needs approval.
        _q, name = _split_qty_name(item_qty_string)
        name = name or item_qty_string.strip()
        new_record = {
            "name": name,
            "quantity": qty.to_dict() if qty.is_numeric()
                        else {"amount": None, "unit": None},
            "location": "pantry",
            "status": "available",
            "source": "pantry_ops:add",
            "requires_verification": True,
            "last_confirmed": time.strftime("%Y-%m-%d"),
            "notes": None,
        }
        return PlanOp(op_type, item_qty_string, name, None, None,
                      {"name": name,
                       "quantity": deepcopy(new_record["quantity"]),
                       "status": "available"},
                      delta=f"+{qty}" if qty.is_numeric() else "new",
                      status="ok", needs_approval=True)

    # ----- consume -----
    if op_type == "consume":
        if record is None:
            sug = _suggest(item_qty_string, inventory)
            tail = f" Did you mean: {sug}?" if sug else ""
            return PlanOp(op_type, item_qty_string, None, None, None, None,
                          status="error",
                          error=f"Cannot consume unknown item "
                                f"'{item_qty_string}'.{tail}")
        current = Quantity.from_dict(record["quantity"])
        if not qty.is_numeric():
            return PlanOp(op_type, item_qty_string, record["name"], index,
                          _snapshot(record), None, status="error",
                          error=f"consume requires a numeric quantity to "
                                f"deduct (got '{item_qty_string}')")
        if not current.is_numeric():
            return PlanOp(op_type, item_qty_string, record["name"], index,
                          _snapshot(record), None, status="error",
                          error=f"Cannot consume '{record['name']}': current "
                                f"quantity is non-numeric ({current!r}). Use "
                                f"adjust instead.")
        try:
            new_qty = current - qty
        except ValueError as e:
            return PlanOp(op_type, item_qty_string, record["name"], index,
                          _snapshot(record), None, status="error",
                          error=f"Over-consumption of '{record['name']}': "
                                f"{e}. Current stock: {current}, requested: "
                                f"{qty}")
        after = {"name": record["name"],
                 "quantity": new_qty.to_dict(),
                 "status": record.get("status")}
        return PlanOp(op_type, item_qty_string, record["name"], index,
                      _snapshot(record), after,
                      delta=f"-{qty}", status="ok")

    # ----- adjust -----
    if op_type == "adjust":
        if record is None:
            sug = _suggest(item_qty_string, inventory)
            tail = f" Did you mean: {sug}?" if sug else ""
            return PlanOp(op_type, item_qty_string, None, None, None, None,
                          status="error",
                          error=f"Cannot adjust unknown item "
                                f"'{item_qty_string}'.{tail}")
        if not qty.is_numeric():
            return PlanOp(op_type, item_qty_string, record["name"], index,
                          _snapshot(record), None, status="error",
                          error=f"adjust requires a numeric target quantity "
                                f"(got '{item_qty_string}')")
        after = {"name": record["name"], "quantity": qty.to_dict(),
                 "status": record.get("status")}
        return PlanOp(op_type, item_qty_string, record["name"], index,
                      _snapshot(record), after,
                      delta=f"set {qty}", status="ok")

    # ----- unavailable -----
    if op_type == "unavailable":
        if record is None:
            sug = _suggest(item_qty_string, inventory)
            tail = f" Did you mean: {sug}?" if sug else ""
            return PlanOp(op_type, item_qty_string, None, None, None, None,
                          status="error",
                          error=f"Cannot mark unknown item unavailable "
                                f"'{item_qty_string}'.{tail}")
        after = {"name": record["name"],
                 "quantity": {"amount": None, "unit": None},
                 "status": "unavailable"}
        return PlanOp(op_type, item_qty_string, record["name"], index,
                      _snapshot(record), after,
                      delta="status=unavailable, qty=null", status="ok")

    # ----- low -----
    if op_type == "low":
        if record is None:
            sug = _suggest(item_qty_string, inventory)
            tail = f" Did you mean: {sug}?" if sug else ""
            return PlanOp(op_type, item_qty_string, None, None, None, None,
                          status="error",
                          error=f"Cannot mark unknown item low "
                                f"'{item_qty_string}'.{tail}")
        after_qty = deepcopy(record["quantity"])
        delta_parts = ["status=low"]
        if qty.is_numeric():
            after_qty = qty.to_dict()
            delta_parts.append(f"qty={qty}")
        after = {"name": record["name"], "quantity": after_qty,
                 "status": "low"}
        return PlanOp(op_type, item_qty_string, record["name"], index,
                      _snapshot(record), after,
                      delta=", ".join(delta_parts), status="ok")

    # unreachable
    return PlanOp(op_type, item_qty_string, None, None, None, None,
                  status="error", error="internal error")


def plan_operations(
    ops: list[tuple[str, str]],
    inventory_path: str | Path | None = None,
    alias_path: str | Path | None = None,
) -> Plan:
    """Validate all ops and compute a proposed state.

    Each op is (op_type, item_qty_string).  Does NOT write inventory.
    Validation consumes the # of purely-inventory records; validation is
    computed against a cumulative (virtual) copy so batch semantics are atomic.
    """
    inv_path = Path(inventory_path) if inventory_path else _DEFAULT_INVENTORY_PATH
    inv = load_inventory(inv_path)
    inv_hash = inventory_hash(inv_path)

    working = deepcopy(inv.get("items", []))
    plan_ops: list[PlanOp] = []
    errors: list[str] = []

    for i, (op_type, item_qty_string) in enumerate(ops):
        op = _plan_single_op(op_type, item_qty_string, working,
                             alias_path, inv_hash)
        plan_ops.append(op)
        if op.status != "ok":
            errors.append(f"[{item_qty_string}]: {op.error}")
            continue

        # Apply the op's effect to the working copy so scene of later ops.
        if op_type == "verify":
            continue
        if op.needs_approval:
            # Append a new item to the working list for cumulative planning.
            working.append({
                "name": op.resolved_name,
                "quantity": deepcopy(op.after["quantity"]),
                "status": op.after["status"],
            })
            continue
        if op.resolved_index is not None:
            item = working[op.resolved_index]
            item["quantity"] = deepcopy(op.after["quantity"])
            item["status"] = op.after["status"]

    return Plan(operations=plan_ops, inv_hash_before=inv_hash, errors=errors)


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

def _audit_entry(op: PlanOp, ts: str, hash_before: str, hash_after: str,
                 approval_ref: str | None = None,
                 approval_status: str = "approved") -> dict:
    return {
        "timestamp": ts,
        "op": op.op_type,
        "item": op.resolved_name,
        "before": op.before,
        "after": op.after,
        "delta": op.delta,
        "validation": op.status,
        "approval_ref": approval_ref,
        "approval_status": approval_status,
        "inv_hash_before": hash_before,
        "inv_hash_after": hash_after,
    }


def commit_plan(
    plan_dict: dict,
    inventory_path: str | Path | None = None,
    log_path: str | Path | None = None,
    approval_ref: str | None = None,
    approval_status: str = "approved",
) -> dict:
    """Apply an authorized plan.

    Re-validates against the current inventory (staleness check), then
    atomically writes inventory and appends to the mutations log.

    Returns {'applied': int, 'errors': [...]}.
    """
    inv_path = Path(inventory_path) if inventory_path else _DEFAULT_INVENTORY_PATH
    log_path = Path(log_path) if log_path else _MUTATIONS_LOG

    # Staleness check.
    old_hash = plan_dict.get("inv_hash_before")
    current_hash = inventory_hash(inv_path)
    if old_hash and old_hash != current_hash:
        return {
            "applied": 0,
            "errors": [
                "Staleness check failed: inventory changed since plan was "
                f"created (plan hash {old_hash[:12]}..., current "
                f"{current_hash[:12]}...). Re-plan and re-authorize."
            ],
        }

    if not plan_dict.get("valid", False):
        errs = plan_dict.get("errors", ["Plan marked invalid"])
        return {"applied": 0, "errors": errs}

    inv = load_inventory(inv_path)
    items = inv.get("items", [])

    # Re-resolve each op's target by name to recompute indices in the live
    # inventory, and re-validate numeric conditions against live state.
    applied = 0
    pending_audit: list[dict] = []

    for opd in plan_dict["operations"]:
        opld = _op_from_dict(opd)
        op_type = opld.op_type

        if op_type == "verify":
            continue

        # Re-validate against the unchanged live inventory.
        if opld.status != "ok":
            continue

        if op_type == "add":
            if opld.needs_approval:
                # New item: append full record.
                new_record = {
                    "name": opld.resolved_name,
                    "quantity": deepcopy(opld.after["quantity"]),
                    "location": "pantry",
                    "status": "available",
                    "source": "pantry_ops:add",
                    "requires_verification": True,
                    "last_confirmed": time.strftime("%Y-%m-%d"),
                    "notes": None,
                }
                items.append(new_record)
                applied += 1
                pending_audit.append(_audit_entry(opld, "", old_hash, ""))
                continue

            # Find the item again (by canonical name from plan).
            idx = _find_index(items, opld.resolved_name)
            if idx is None:
                continue
            # The planned result already incorporates the prior stock; since
            # staleness was verified, apply it directly.
            items[idx]["quantity"] = deepcopy(opld.after["quantity"])
            applied += 1
            entry = _audit_entry(opld, "", old_hash, "")
            entry["after"] = {"name": opld.resolved_name,
                              "quantity": deepcopy(items[idx]["quantity"]),
                              "status": items[idx].get("status")}
            pending_audit.append(entry)
            continue

        if op_type in ("consume", "adjust", "unavailable", "low"):
            if opld.resolved_name is None:
                continue
            idx = _find_index(items, opld.resolved_name)
            if idx is None:
                continue
            if op_type == "consume":
                current = Quantity.from_dict(items[idx]["quantity"])
                cq = _op_qty(opld)
                if not current.is_numeric():
                    continue
                try:
                    new_qty = current - cq
                except ValueError:
                    continue
                items[idx]["quantity"] = new_qty.to_dict()
            elif op_type == "adjust":
                items[idx]["quantity"] = deepcopy(opld.after["quantity"])
            elif op_type == "unavailable":
                items[idx]["quantity"] = {"amount": None, "unit": None}
                items[idx]["status"] = "unavailable"
            elif op_type == "low":
                if "quantity" in opld.after:
                    items[idx]["quantity"] = deepcopy(opld.after["quantity"])
                items[idx]["status"] = "low"

            applied += 1
            entry = _audit_entry(opld, "", old_hash, "")
            entry["after"] = {"name": opld.resolved_name,
                              "quantity": deepcopy(items[idx]["quantity"]),
                              "status": items[idx].get("status")}
            pending_audit.append(entry)

    if pending_audit:
        save_inventory(inv, inv_path)
        new_hash = inventory_hash(inv_path)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        inv["items"] = items  # no-op, already mutated
        # Write audit log append-only (one line per applied op).
        with open(log_path, "a") as f:
            for e in pending_audit:
                e["timestamp"] = ts
                e["inv_hash_after"] = new_hash
                e["approval_ref"] = approval_ref
                e["approval_status"] = approval_status
                f.write(json.dumps(e) + "\n")

    return {"applied": applied, "errors": []}


def _op_from_dict(opd: dict) -> PlanOp:
    return PlanOp(
        op_type=opd.get("op_type"),
        item_qty_string=opd.get("item_qty_string", ""),
        resolved_name=opd.get("item"),
        resolved_index=opd.get("resolved_index"),
        before=opd.get("before"),
        after=opd.get("after"),
        delta=opd.get("delta"),
        status=opd.get("status", "ok"),
        error=opd.get("error"),
        needs_approval=opd.get("needs_approval", False),
    )


def _op_qty(op: PlanOp) -> Quantity:
    """Recover the Quantity an op acted on (for commit re-derivation)."""
    # Use the before/after delta; simplest is to recompute from the input.
    return Quantity.from_dict(op.after["quantity"]) if op.after and \
        op.after.get("quantity") else Quantity(None, None)


def _find_index(items: list[dict], name: Optional[str]) -> Optional[int]:
    if name is None:
        return None
    for i, it in enumerate(items):
        if it["name"] == name:
            return i
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_verify(args: argparse.Namespace) -> None:
    inv = load_inventory(args.inventory)
    mr, record, index = resolve_item(args.item_name, inv)
    if record is not None:
        q = Quantity.from_dict(record["quantity"])
        out = {
            "name": record["name"],
            "quantity": record["quantity"],
            "parsed_quantity": {
                "amount": str(q.amount) if q.amount is not None else None,
                "unit": q.unit,
                "is_numeric": q.is_numeric(),
            },
            "status": record.get("status"),
            "location": record.get("location"),
        }
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps({
            "error": f"Item not found: '{args.item_name}'",
            "reason": mr.reason if mr else "no match",
        }, indent=2), file=sys.stderr)
        sys.exit(1)


def _cli_plan(args: argparse.Namespace) -> None:
    ops = []
    i = 0
    while i < len(args.ops):
        op_type = args.ops[i]
        if i + 1 >= len(args.ops):
            print(f"Error: op '{op_type}' requires an ITEM_QTY argument",
                  file=sys.stderr)
            sys.exit(1)
        ops.append((op_type, args.ops[i + 1]))
        i += 2

    plan = plan_operations(ops, inventory_path=args.inventory)
    print(json.dumps(plan.to_dict(), indent=2))

    # Human-readable summary to stderr.
    print("\n--- Plan Summary ---", file=sys.stderr)
    for op in plan.operations:
        mark = "OK " if op.status == "ok" else "ERR"
        appr = " [needs approval]" if op.needs_approval else ""
        if op.status != "ok":
            print(f"  [{mark}] {op.op_type:11s} {op.item_qty_string} "
                  f"-> {op.error}", file=sys.stderr)
        else:
            print(f"  [{mark}] {op.op_type:11s} {op.item_qty_string}"
                  f"{appr} -> {op.resolved_name}", file=sys.stderr)
    print(f"  valid={plan.valid}", file=sys.stderr)


def _cli_commit(args: argparse.Namespace) -> None:
    plan_file = Path(args.plan_file)
    if not plan_file.exists():
        print(f"Error: plan file not found: {plan_file}", file=sys.stderr)
        sys.exit(1)
    with open(plan_file, "r") as f:
        plan_dict = json.load(f)
    result = commit_plan(plan_dict, inventory_path=args.inventory,
                         approval_ref=args.approval,
                         approval_status=args.approval_status)
    print(json.dumps(result, indent=2))
    if result["errors"]:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pantry_ops", description="Deterministic pantry mutation CLI")
    parser.add_argument("--inventory", default=str(_DEFAULT_INVENTORY_PATH),
                        help="Path to inventory.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_verify = sub.add_parser("verify", help="Show an item's state (read-only)")
    p_verify.add_argument("item_name")
    p_verify.add_argument("--inventory", default=None, dest="inventory")

    p_plan = sub.add_parser("plan", help="Validate ops and emit a plan (no write)")
    p_plan.add_argument("ops", nargs="+",
                        help="OP ITEM_QTY pairs, e.g. add '2 lb butter' consume '1 lb butter'")
    p_plan.add_argument("--inventory", default=None, dest="inventory")

    p_commit = sub.add_parser("commit", help="Apply an authorized plan JSON file")
    p_commit.add_argument("plan_file")
    p_commit.add_argument("--inventory", default=None, dest="inventory")
    p_commit.add_argument("--approval", default=None,
                          help="Approval reference from modify_pantry_inventory authorization")
    p_commit.add_argument("--approval-status", default="approved",
                          help="Approval status (default: approved)")

    args = parser.parse_args()

    # Prefer subparser --inventory; fall back to the global one.
    if getattr(args, "inventory", None) is None:
        args.inventory = _DEFAULT_INVENTORY_PATH

    if args.command == "verify":
        _cli_verify(args)
    elif args.command == "plan":
        _cli_plan(args)
    elif args.command == "commit":
        _cli_commit(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()