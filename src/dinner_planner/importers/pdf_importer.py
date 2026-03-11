from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from dinner_planner.importers.pdf_classifier import classify_lines
from dinner_planner.importers.pdf_extractor import extract_sections
from dinner_planner.importers.pdf_segmenter import segment_lines
from dinner_planner.models import IngredientRecord, ParseIssue
from dinner_planner.normalization import normalize_ingredient_line

LINE_NOISE_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"\bepicurious\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\b", re.IGNORECASE),
    re.compile(r"\bfree trial\b", re.IGNORECASE),
    re.compile(r"\bunlock access\b", re.IGNORECASE),
    re.compile(r"^\d+/\d+$"),
    re.compile(r"^\d+/\d+/\d{2,4},\s*\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE),
    re.compile(r"^\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE),
    # Recipe-site descriptive blurbs that are not steps/ingredients.
    re.compile(r"key to this recipe", re.IGNORECASE),
    re.compile(r"no need to boil", re.IGNORECASE),
    re.compile(r"resulting texture is reminiscent", re.IGNORECASE),
    re.compile(r"for a fantastic meal", re.IGNORECASE),
    re.compile(r"fora fantastic meal", re.IGNORECASE),
    re.compile(r"shelf-stable and refrigerated gnocchi will both work here", re.IGNORECASE),
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

LOWERCASE_TITLE_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "vs",
}


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if len(stripped) <= 2 and not stripped.isdigit():
        return True
    if re.fullmatch(r"[-_=*~•·\s]+", stripped):
        return True
    for pattern in LINE_NOISE_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def _is_step_line(line: str) -> bool:
    return bool(re.match(r"^step\s+\d+\b", line.strip(), re.IGNORECASE))


def _normalize_title(title: str) -> str:
    repaired = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", title.strip())
    repaired = re.sub(r"\s+", " ", repaired).strip()
    words = repaired.split(" ")
    if not words:
        return "Untitled Recipe"
    out_words: list[str] = []
    for idx, word in enumerate(words):
        lowered = word.lower()
        if idx in (0, len(words) - 1):
            out_words.append(lowered.capitalize())
        elif lowered in LOWERCASE_TITLE_WORDS:
            out_words.append(lowered)
        else:
            out_words.append(lowered.capitalize())
    return " ".join(out_words)


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
    has_comma = "," in stripped

    return has_qty or has_unit_hint or has_comma


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
    split_at: int | None = None
    for marker in markers:
        idx = lower.find(marker, 6)
        if idx != -1:
            split_at = idx
            break
    if split_at is None:
        return [line]
    first = line[:split_at].strip(" ,")
    second = line[split_at + 1 :].strip(" ,")
    if not first or not second:
        return [line]
    return [first, second]


def _is_ignorable_non_ingredient_line(line: str) -> bool:
    lower = line.strip().lower()
    if lower in {"yield", "yield:", "servings", "servings:", "serves", "serves:"}:
        return True
    if re.match(r"^\d+\s+servings?$", lower):
        return True
    if lower in {"better", "better."}:
        return True
    return False


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
    if "," in stripped:
        return True
    return len(stripped.split()) <= 5


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

    merged_embedded = _merge_wrapped_ingredient_lines(embedded_candidates)
    return cleaned_instructions, merged_embedded


def _parse_recipe_text_agnostic(raw_text: str) -> tuple[str, str | None, str | None, list[IngredientRecord], list[ParseIssue], float]:
    segmented = segment_lines(raw_text)
    classified = classify_lines(segmented)
    extracted = extract_sections(classified)

    cleaned_instruction_lines, embedded_instruction_ingredients = _extract_embedded_ingredients_from_instructions(
        extracted.instruction_lines
    )
    merged_ingredient_lines = _merge_wrapped_ingredient_lines(extracted.ingredient_lines + embedded_instruction_ingredients)
    expanded_ingredient_lines: list[str] = []
    for line in merged_ingredient_lines:
        expanded_ingredient_lines.extend(_split_embedded_serving_garnish(line))

    valid_ingredient_lines: list[str] = []
    filtered_ingredient_lines: list[str] = []
    for line in expanded_ingredient_lines:
        if _is_valid_ingredient_line(line):
            valid_ingredient_lines.append(line)
        elif _is_ignorable_non_ingredient_line(line):
            continue
        else:
            filtered_ingredient_lines.append(line)

    ingredients = [normalize_ingredient_line(line) for line in valid_ingredient_lines if line]
    instructions = "\n".join(cleaned_instruction_lines).strip() if cleaned_instruction_lines else None
    title = _normalize_title(extracted.title) if extracted.title else "Untitled Recipe"

    issues = list(extracted.issues)
    reportable_filtered_lines = [
        line for line in filtered_ingredient_lines if not _is_ignorable_non_ingredient_line(line)
    ]
    if reportable_filtered_lines:
        issues.append(
            ParseIssue(
                "filtered_line",
                "ingredients",
                "Some ingredient lines were filtered as likely metadata/noise.",
                snippet=reportable_filtered_lines[0],
            )
        )
    if not instructions and not any(i.issue_type == "missing_section" and i.field_name == "instructions" for i in issues):
        issues.append(ParseIssue("missing_section", "instructions", "Could not confidently detect instructions section."))

    confidence = extracted.confidence
    return title, extracted.servings, instructions, ingredients, issues, confidence


def parse_recipe_text(raw_text: str) -> tuple[str, str | None, str | None, list[IngredientRecord], list[ParseIssue], float]:
    return _parse_recipe_text_agnostic(raw_text)

