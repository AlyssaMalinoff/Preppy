from __future__ import annotations

from collections import Counter

from dinner_planner.planner.models import PlannerRecipe


def is_weekday(day_index: int) -> bool:
    return day_index < 5


def passes_no_back_to_back(candidate: PlannerRecipe, previous_recipe_id: int | None) -> bool:
    if previous_recipe_id is None:
        return True
    return candidate.recipe_id != previous_recipe_id


def passes_weekday_difficulty(candidate: PlannerRecipe, day_index: int, candidate_pool: list[PlannerRecipe]) -> bool:
    if not is_weekday(day_index):
        return True
    easy_exists = any(recipe.difficulty_level == "easy" for recipe in candidate_pool)
    if easy_exists and candidate.difficulty_level != "easy":
        return False
    return True


def passes_category_diversity(candidate: PlannerRecipe, chosen_recipes: list[PlannerRecipe], max_per_category: int = 3) -> bool:
    counts = Counter(recipe.dish_category for recipe in chosen_recipes)
    return counts[candidate.dish_category] < max_per_category

