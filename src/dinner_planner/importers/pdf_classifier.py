from __future__ import annotations

import re
from dataclasses import dataclass

from dinner_planner.importers.pdf_segmenter import SegmentedLine


SECTION_HEADERS = {"ingredients", "ingredient", "instructions", "method", "directions", "steps", "preparation"}
SERVINGS_HEADERS = {"yield", "servings", "serves"}
BOUNDARY_PREFIXES = ("tags", "private notes", "leave a private note", "see related", "tip")
UNIT_HINTS = ("tbsp", "tablespoon", "tsp", "teaspoon", "cup", "lb", "oz", "g", "kg", "clove", "can")
TITLE_NOISE = ("for the new york times", "total time", "prep time", "cook time", "subscribe")


@dataclass(slots=True)
class ClassifiedLine:
    line: SegmentedLine
    label: str
    score: float


def _is_ingredient_like(text: str) -> bool:
    lower = text.lower()
    if re.match(r"^\d+([./]\d+)?(\s+\d+/\d+)?", text):
        return True
    if any(f" {hint}" in f" {lower}" for hint in UNIT_HINTS) and "," in text:
        return True
    return False


def classify_lines(lines: list[SegmentedLine]) -> list[ClassifiedLine]:
    out: list[ClassifiedLine] = []
    for item in lines:
        text = item.text
        lower = text.lower()

        if re.search(r"https?://|\bwww\.", lower):
            out.append(ClassifiedLine(item, "noise", 1.0))
            continue
        if re.match(r"^step\s+\d+\b", lower):
            out.append(ClassifiedLine(item, "instructions", 0.98))
            continue
        if lower in SECTION_HEADERS:
            out.append(ClassifiedLine(item, f"header:{lower}", 1.0))
            continue
        if lower in SERVINGS_HEADERS or re.match(r"^(yield|serves?|servings?)\s*:?\s*\d+", lower):
            out.append(ClassifiedLine(item, "servings", 0.95))
            continue
        if any(lower.startswith(prefix) for prefix in BOUNDARY_PREFIXES):
            out.append(ClassifiedLine(item, "boundary", 0.95))
            continue
        if _is_ingredient_like(text):
            out.append(ClassifiedLine(item, "ingredient", 0.82))
            continue

        words = text.split()
        if (
            2 <= len(words) <= 16
            and not re.search(r"[.!?;]", text)
            and not any(noise in lower for noise in TITLE_NOISE)
        ):
            out.append(ClassifiedLine(item, "title_candidate", 0.7))
            continue

        out.append(ClassifiedLine(item, "other", 0.4))
    return out

