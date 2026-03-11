from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ClassificationResult:
    difficulty_level: str
    dish_category: str
    seasonality_tags: list[str]
    repeat_policy: str
    popularity_score: float


SEASON_KEYWORDS = {
    "spring": {"asparagus", "peas", "radish", "artichoke", "leek"},
    "summer": {"zucchini", "tomato", "corn", "basil", "cucumber", "pepper"},
    "fall": {"squash", "pumpkin", "mushroom", "brussels", "cauliflower"},
    "winter": {"stew", "braise", "cabbage", "potato", "carrot", "short rib"},
}


def _infer_difficulty(text: str) -> str:
    lower = text.lower()
    step_count = lower.count("step ")
    if any(token in lower for token in ("braise", "short rib", "overnight", "marinate")):
        return "hard"
    if any(token in lower for token in ("simmer 1", "hours", "hour")):
        return "hard"
    if step_count >= 7:
        return "hard"
    if step_count >= 4:
        return "medium"
    return "easy"


def _infer_category(text: str) -> str:
    # v1 behavior: category taxonomy is deferred; everything is general.
    return "general"


def _infer_seasonality(text: str) -> list[str]:
    lower = text.lower()
    tags = [season for season, words in SEASON_KEYWORDS.items() if any(word in lower for word in words)]
    return sorted(set(tags)) if tags else ["all"]


def _infer_repeat_policy(category: str, difficulty: str) -> str:
    if difficulty == "hard":
        return "avoid-repeat"
    if category in {"soup_stew", "roast_braise"}:
        return "flexible"
    return "normal"


def _default_popularity(category: str, difficulty: str) -> float:
    # Popularity is user-managed later; use fixed baseline for now.
    return 0.5


def classify_recipe(title: str, ingredient_names: list[str], instructions: str | None) -> ClassificationResult:
    text = " ".join([title, " ".join(ingredient_names), instructions or ""]).strip()
    difficulty = _infer_difficulty(text)
    category = _infer_category(text)
    seasons = _infer_seasonality(text)
    repeat_policy = _infer_repeat_policy(category, difficulty)
    popularity = _default_popularity(category, difficulty)
    return ClassificationResult(
        difficulty_level=difficulty,
        dish_category=category,
        seasonality_tags=seasons,
        repeat_policy=repeat_policy,
        popularity_score=popularity,
    )

