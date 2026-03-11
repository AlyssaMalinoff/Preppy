from __future__ import annotations

from collections import Counter
from datetime import date

from dinner_planner.planner.generator import generate_weekly_plan
from dinner_planner.planner.models import PlannerRecipe
from dinner_planner.planner.scoring import score_recipe


def _recipe(
    recipe_id: int,
    title: str,
    *,
    difficulty: str = "easy",
    category: str = "general",
    ingredients: list[str] | None = None,
    popularity: float = 0.5,
) -> PlannerRecipe:
    return PlannerRecipe(
        recipe_id=recipe_id,
        title=title,
        difficulty_level=difficulty,
        dish_category=category,
        seasonality_tags=["all"],
        repeat_policy="normal",
        popularity_score=popularity,
        ingredient_names=ingredients or [],
    )


def test_week_plan_has_no_back_to_back_duplicates():
    recipes = [
        _recipe(1, "Recipe One", ingredients=["a"]),
        _recipe(2, "Recipe Two", ingredients=["b"]),
    ]
    plan = generate_weekly_plan(recipes, date(2026, 3, 9))
    ids = [day.recipe_id for day in plan.days]
    for i in range(1, len(ids)):
        assert ids[i] != ids[i - 1]


def test_weekday_easy_bias_when_easy_candidates_exist():
    recipes = [
        _recipe(1, "Easy Dish A", difficulty="easy", category="pasta", ingredients=["x"]),
        _recipe(2, "Easy Dish B", difficulty="easy", category="soup", ingredients=["y"]),
        _recipe(3, "Hard Weekend Dish", difficulty="hard", category="roast_braise", ingredients=["z"]),
    ]
    plan = generate_weekly_plan(recipes, date(2026, 3, 9))
    for i in range(5):
        assert any(
            recipe.recipe_id == plan.days[i].recipe_id and recipe.difficulty_level == "easy"
            for recipe in recipes
        )


def test_category_diversity_guard_prevents_single_category_domination():
    recipes = [
        _recipe(1, "Pasta A", category="pasta", ingredients=["p1"]),
        _recipe(2, "Pasta B", category="pasta", ingredients=["p2"]),
        _recipe(3, "Soup A", category="soup_stew", ingredients=["s1"]),
        _recipe(4, "Taco A", category="taco", ingredients=["t1"]),
    ]
    plan = generate_weekly_plan(recipes, date(2026, 3, 9))
    counts = Counter(day.title.split()[0].lower() for day in plan.days)
    assert counts["pasta"] <= 3


def test_overlap_scoring_rewards_shared_ingredients():
    selected = [_recipe(1, "A", ingredients=["broccoli", "garlic"])]
    ingredient_counter = Counter({"broccoli": 2, "garlic": 1})
    shared = _recipe(2, "Shared", ingredients=["broccoli", "onion"])
    isolated = _recipe(3, "Isolated", ingredients=["beef", "carrot"])

    shared_score, _ = score_recipe(
        shared,
        day=date(2026, 3, 10),
        day_index=1,
        selected_recipes=selected,
        ingredient_counter=ingredient_counter,
    )
    isolated_score, _ = score_recipe(
        isolated,
        day=date(2026, 3, 10),
        day_index=1,
        selected_recipes=selected,
        ingredient_counter=ingredient_counter,
    )
    assert shared_score > isolated_score

