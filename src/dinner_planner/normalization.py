from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional

from dinner_planner.models import IngredientRecord


UNIT_ALIASES = {
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "cup": "cup",
    "cups": "cup",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "ounce": "oz",
    "ounces": "oz",
    "oz": "oz",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "clove": "clove",
    "cloves": "clove",
}

INGREDIENT_ALIASES = {
    "garbanzo beans": "chickpeas",
    "chick pea": "chickpeas",
    "chick peas": "chickpeas",
    "scallions": "green onion",
    "spring onion": "green onion",
    "bell peppers": "bell pepper",
    "capsicum": "bell pepper",
}

INGREDIENT_RE = re.compile(
    r"^\s*(?P<qty>\d+(?:\s+\d+/\d+|\.\d+|/\d+)?|\d+/\d+)?\s*"
    r"(?P<unit>[A-Za-z]+\.?)?\s*"
    r"(?P<name>.+?)\s*$"
)


def _parse_quantity(value: str) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    try:
        if " " in value and "/" in value:
            whole, frac = value.split(" ", 1)
            return float(int(whole) + Fraction(frac))
        if "/" in value:
            return float(Fraction(value))
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None


def _clean_name(raw_name: str) -> str:
    name = raw_name.strip().lower()
    name = re.sub(r"\(.*?\)", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    return INGREDIENT_ALIASES.get(name, name)


def _clean_unit(raw_unit: Optional[str]) -> Optional[str]:
    if not raw_unit:
        return None
    unit = raw_unit.lower().rstrip(".")
    return UNIT_ALIASES.get(unit, unit)


def normalize_ingredient_line(line: str) -> IngredientRecord:
    text = line.strip(" -*\t")
    lower_line = text.lower()
    optional = "optional" in lower_line
    match = INGREDIENT_RE.match(text)

    if not match:
        return IngredientRecord(
            raw_text=line,
            name_normalized=_clean_name(text),
            quantity_value=None,
            quantity_unit=None,
            is_optional=optional,
        )

    qty = _parse_quantity(match.group("qty") or "")
    unit = _clean_unit(match.group("unit"))
    name = _clean_name(match.group("name") or text)
    return IngredientRecord(
        raw_text=line,
        name_normalized=name,
        quantity_value=qty,
        quantity_unit=unit,
        is_optional=optional,
    )

