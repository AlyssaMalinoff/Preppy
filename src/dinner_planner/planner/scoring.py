from __future__ import annotations

from collections import Counter
from datetime import date

from dinner_planner.planner.constraints import is_weekday
from dinner_planner.planner.models import PlannerRecipe


SEASON_BY_MONTH = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "fall",
    10: "fall",
    11: "fall",
}


def _current_season(day: date) -> str:
    return SEASON_BY_MONTH[day.month]


def score_recipe(
    candidate: PlannerRecipe,
    *,
    day: date,
    day_index: int,
    selected_recipes: list[PlannerRecipe],
    ingredient_counter: Counter[str],
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    season = _current_season(day)
    if "all" in candidate.seasonality_tags or season in candidate.seasonality_tags:
        score += 1.5
        reasons.append("seasonality match")

    score += candidate.popularity_score
    reasons.append("popularity weighted")

    if is_weekday(day_index):
        if candidate.difficulty_level == "easy":
            score += 1.4
            reasons.append("weekday easy bias")
        elif candidate.difficulty_level == "medium":
            score += 0.4
        else:
            score -= 0.8

    overlap = sum(ingredient_counter[name] for name in candidate.ingredient_names)
    if overlap > 0:
        score += min(overlap * 0.25, 1.5)
        reasons.append("ingredient overlap efficiency")

    category_count = sum(1 for recipe in selected_recipes if recipe.dish_category == candidate.dish_category)
    if category_count >= 2:
        score -= 0.8
        reasons.append("category diversity penalty")

    if candidate.repeat_policy == "avoid-repeat":
        score -= 0.4
    elif candidate.repeat_policy == "flexible":
        score += 0.2

    return score, reasons

