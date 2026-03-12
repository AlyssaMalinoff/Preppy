from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class PlannerRecipe:
    recipe_id: int
    title: str
    difficulty_level: str
    dish_category: str
    seasonality_tags: list[str]
    repeat_policy: str
    popularity_score: float
    ingredient_names: list[str]


@dataclass(slots=True)
class DayPlan:
    day: date
    recipe_id: int
    title: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WeeklyPlan:
    start_day: date
    days: list[DayPlan]

