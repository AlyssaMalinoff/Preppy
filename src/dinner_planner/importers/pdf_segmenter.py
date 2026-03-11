from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class SegmentedLine:
    index: int
    text: str


def _replace_unicode_fractions(text: str) -> str:
    return (
        text.replace("½", " 1/2")
        .replace("¼", " 1/4")
        .replace("¾", " 3/4")
        .replace("⅓", " 1/3")
        .replace("⅔", " 2/3")
        .replace("⅛", " 1/8")
    )


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text)


def segment_lines(raw_text: str) -> list[SegmentedLine]:
    cleaned_text = _normalize_whitespace(_replace_unicode_fractions(raw_text))
    lines: list[SegmentedLine] = []
    for idx, raw_line in enumerate(cleaned_text.splitlines()):
        stripped = raw_line.strip()
        if not stripped:
            continue
        lines.append(SegmentedLine(index=idx, text=stripped))
    return lines

