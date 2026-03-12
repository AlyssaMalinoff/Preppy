from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from dinner_planner.planner.constraints import (
    passes_category_diversity,
    passes_no_back_to_back,
    passes_weekday_difficulty,
)
from dinner_planner.planner.models import DayPlan, PlannerRecipe, WeeklyPlan
from dinner_planner.planner.scoring import score_recipe


def generate_weekly_plan(recipes: list[PlannerRecipe], start_day: date) -> WeeklyPlan:
    if not recipes:
        raise ValueError("No recipes available for planning.")

    selected_recipes: list[PlannerRecipe] = []
    day_plans: list[DayPlan] = []
    ingredient_counter: Counter[str] = Counter()
    previous_recipe_id: int | None = None

    for day_index in range(7):
        current_day = start_day + timedelta(days=day_index)
        eligible = [
            recipe
            for recipe in recipes
            if passes_no_back_to_back(recipe, previous_recipe_id)
            and passes_weekday_difficulty(recipe, day_index, recipes)
            and passes_category_diversity(recipe, selected_recipes)
        ]
        if not eligible:
            eligible = [recipe for recipe in recipes if passes_no_back_to_back(recipe, previous_recipe_id)] or recipes

        scored = []
        for candidate in eligible:
            score, reasons = score_recipe(
                candidate,
                day=current_day,
                day_index=day_index,
                selected_recipes=selected_recipes,
                ingredient_counter=ingredient_counter,
            )
            scored.append((score, candidate, reasons))
        scored.sort(key=lambda entry: (entry[0], entry[1].popularity_score), reverse=True)
        best_score, best_recipe, reasons = scored[0]

        selected_recipes.append(best_recipe)
        previous_recipe_id = best_recipe.recipe_id
        ingredient_counter.update(best_recipe.ingredient_names)
        day_plans.append(
            DayPlan(
                day=current_day,
                recipe_id=best_recipe.recipe_id,
                title=best_recipe.title,
                score=best_score,
                reasons=reasons,
            )
        )

    return WeeklyPlan(start_day=start_day, days=day_plans)

