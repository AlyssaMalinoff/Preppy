from __future__ import annotations

import re
from dataclasses import dataclass

from dinner_planner.importers.pdf_extractor import ExtractedSections
from dinner_planner.models import ParseIssue

LINE_NOISE_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"\bsubscribe\b", re.IGNORECASE),
    re.compile(r"\bfree trial\b", re.IGNORECASE),
    re.compile(r"\bunlock access\b", re.IGNORECASE),
    re.compile(r"^\d+/\d+$"),
    re.compile(r"^\d+/\d+/\d{2,4},\s*\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE),
    re.compile(r"^\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE),
]

INSTRUCTION_VERB_PREFIX = (
    "add",
    "bring",
    "cook",
    "divide",
    "drizzle",
    "heat",
    "reduce",
    "return",
    "simmer",
    "stir",
    "top",
    "whisk",
)

KNOWN_UNIT_HINTS = (
    "tbsp",
    "tablespoon",
    "tsp",
    "teaspoon",
    "cup",
    "cups",
    "lb",
    "pound",
    "oz",
    "ounce",
    "g",
    "gram",
    "kg",
    "clove",
    "can",
    "cans",
)


@dataclass(slots=True)
class RecipeBuckets:
    title: str
    servings: str | None
    instruction_lines: list[str]
    main_ingredient_lines: list[str]
    garnish_lines: list[str]
    confidence: float
    issues: list[ParseIssue]
    nutrition_meta_lines: list[str]
    macro_hint_lines: list[str]


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if len(stripped) <= 2 and not stripped.isdigit():
        return True
    if re.fullmatch(r"[-_=*~•·\s]+", stripped):
        return True
    return any(pattern.search(stripped) for pattern in LINE_NOISE_PATTERNS)


def _is_step_line(line: str) -> bool:
    return bool(re.match(r"^step\s+\d+\b", line.strip(), re.IGNORECASE))


def _is_ingredient_continuation(previous: str, current: str) -> bool:
    lower = current.lower().lstrip()
    if re.match(r"^\d+([./]\d+)?(\s+\d+/\d+)?", current):
        return False
    if previous.rstrip().endswith(("(", ",", "-", "or")):
        return True
    if "for serving" in lower or "to serve" in lower:
        return False
    if current and current[0].islower():
        return True
    return lower.startswith(
        (
            "or ",
            "and ",
            "plus ",
            "for ",
            "to ",
            "more ",
            "shelf-stable",
            "refrigerated",
            "fresh ",
            "freshly ",
            "finely ",
            "thinly ",
            "coarsely ",
            "grated ",
            "chopped ",
        )
    )


def _merge_wrapped_ingredient_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        cleaned = line.strip(" -*\t")
        if not cleaned:
            continue
        if merged and _is_ingredient_continuation(merged[-1], cleaned):
            merged[-1] = f"{merged[-1]} {cleaned}".strip()
        else:
            merged.append(cleaned)
    return merged


def _split_embedded_serving_garnish(line: str) -> list[str]:
    lower = line.lower()
    for_serving_idx = lower.find("for serving")
    if for_serving_idx != -1:
        tail = line[for_serving_idx + len("for serving") :].strip(" ,;")
        if tail:
            return [line[: for_serving_idx + len("for serving")].strip(" ,"), tail]
    if ", for serving" not in lower:
        return [line]
    if not re.match(r"^\d+([./]\d+)?(\s+\d+/\d+)?", line):
        return [line]
    markers = (" freshly ", " finely ", " coarsely ", " grated ", " chopped ")
    for marker in markers:
        split_at = lower.find(marker, 6)
        if split_at != -1:
            first = line[:split_at].strip(" ,")
            second = line[split_at + 1 :].strip(" ,")
            if first and second:
                return [first, second]
    return [line]


def _is_ignorable_non_ingredient_line(line: str) -> bool:
    lower = line.strip().lower()
    if lower in {"yield", "yield:", "servings", "servings:", "serves", "serves:"}:
        return True
    if re.match(r"^\d+\s+servings?$", lower):
        return True
    if lower in {"better", "better."}:
        return True
    return False


def _extract_macro_hint_lines(nutrition_lines: list[str]) -> list[str]:
    macro_lines: list[str] = []
    for line in nutrition_lines:
        lower = line.lower()
        if (
            re.search(r"\b\d+\s*(calories?|kcal)\b", lower)
            or re.search(r"\b\d+\s*g\s*(fat|protein|fiber|carb|carbohydrates?)\b", lower)
            or re.search(r"\b\d+\s*mg\s*(sodium|cholesterol)\b", lower)
        ):
            macro_lines.append(line)
    return macro_lines


def _is_valid_ingredient_line(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    if _is_noise_line(stripped):
        return False
    if lower.startswith(("yield", "servings", "serves")):
        return False
    if lower.startswith("step "):
        return False
    if any(lower.startswith(f"{verb} ") for verb in INSTRUCTION_VERB_PREFIX):
        return False
    if len(stripped.split()) > 25:
        return False
    if "for serving" in lower or "to serve" in lower:
        return True
    has_qty = bool(re.match(r"^\d+([./]\d+)?(\s+\d+/\d+)?", stripped))
    has_unit_hint = any(f" {hint}" in f" {lower}" for hint in KNOWN_UNIT_HINTS)
    return has_qty or has_unit_hint or "," in stripped


def _looks_like_embedded_ingredient_line(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    if _is_step_line(stripped):
        return False
    if lower.startswith(("tip", "for increased flavor")):
        return False
    if re.search(r"\b(minutes?|hours?|degrees?)\b", lower):
        return False
    if not re.match(r"^\d+([./]\d+)?(\s+\d+/\d+)?", stripped):
        return False
    if any(f" {hint}" in f" {lower}" for hint in KNOWN_UNIT_HINTS):
        return True
    return "," in stripped or len(stripped.split()) <= 5


def _extract_embedded_ingredients_from_instructions(instruction_lines: list[str]) -> tuple[list[str], list[str]]:
    cleaned_instructions: list[str] = []
    embedded_candidates: list[str] = []
    in_embedded_block = False
    for line in instruction_lines:
        stripped = line.strip()
        if not stripped:
            continue
        starts_embedded = _looks_like_embedded_ingredient_line(stripped)
        continues_embedded = bool(embedded_candidates) and _is_ingredient_continuation(embedded_candidates[-1], stripped)
        if starts_embedded:
            embedded_candidates.append(stripped)
            in_embedded_block = True
            continue
        if in_embedded_block and continues_embedded:
            embedded_candidates.append(stripped)
            continue
        if in_embedded_block and _is_step_line(stripped):
            cleaned_instructions.append(stripped)
            in_embedded_block = False
            continue
        if in_embedded_block and _is_ignorable_non_ingredient_line(stripped):
            continue
        in_embedded_block = False
        cleaned_instructions.append(stripped)
    return cleaned_instructions, _merge_wrapped_ingredient_lines(embedded_candidates)


def _split_main_vs_garnish(lines: list[str]) -> tuple[list[str], list[str]]:
    main: list[str] = []
    garnish: list[str] = []
    for line in lines:
        lowered = line.lower()
        if "for serving" in lowered or "to serve" in lowered:
            garnish.append(line)
        else:
            main.append(line)
    return main, garnish


def build_recipe_buckets(extracted: ExtractedSections) -> RecipeBuckets:
    cleaned_instruction_lines, embedded = _extract_embedded_ingredients_from_instructions(extracted.instruction_lines)
    merged_ingredients = _merge_wrapped_ingredient_lines(extracted.ingredient_lines + embedded)

    expanded: list[str] = []
    for line in merged_ingredients:
        expanded.extend(_split_embedded_serving_garnish(line))

    valid: list[str] = []
    filtered: list[str] = []
    for line in expanded:
        if _is_valid_ingredient_line(line):
            valid.append(line)
        elif _is_ignorable_non_ingredient_line(line):
            continue
        else:
            filtered.append(line)

    main, garnish = _split_main_vs_garnish(valid)
    issues = list(extracted.issues)
    nutrition_meta_lines = list(extracted.nutrition_meta_lines)
    macro_hint_lines = _extract_macro_hint_lines(nutrition_meta_lines)
    if filtered:
        issues.append(
            ParseIssue(
                "filtered_line",
                "ingredients",
                "Some ingredient lines were filtered as likely metadata/noise.",
                snippet=filtered[0],
            )
        )
    if nutrition_meta_lines:
        issues.append(
            ParseIssue(
                "omitted_meta",
                "nutrition_meta",
                "Nutrition/meta lines were omitted from parsed recipe content and queued for review.",
                snippet=nutrition_meta_lines[0],
            )
        )
    if not cleaned_instruction_lines and not any(
        i.issue_type == "missing_section" and i.field_name == "instructions" for i in issues
    ):
        issues.append(ParseIssue("missing_section", "instructions", "Could not confidently detect instructions section."))

    return RecipeBuckets(
        title=extracted.title,
        servings=extracted.servings,
        instruction_lines=cleaned_instruction_lines,
        main_ingredient_lines=main,
        garnish_lines=garnish,
        confidence=extracted.confidence,
        issues=issues,
        nutrition_meta_lines=nutrition_meta_lines,
        macro_hint_lines=macro_hint_lines,
    )


def flatten_ingredient_lines_for_storage(buckets: RecipeBuckets) -> list[str]:
    return buckets.main_ingredient_lines + buckets.garnish_lines

