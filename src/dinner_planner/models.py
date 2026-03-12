from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class IngredientRecord:
    raw_text: str
    name_normalized: str
    quantity_value: Optional[float]
    quantity_unit: Optional[str]
    preparation: Optional[str] = None
    is_optional: bool = False


@dataclass(slots=True)
class ParseIssue:
    issue_type: str
    field_name: str
    message: str
    snippet: Optional[str] = None


@dataclass(slots=True)
class RecipeClassification:
    difficulty_level: str
    dish_category: str
    seasonality_tags: list[str]
    repeat_policy: str
    popularity_score: float

