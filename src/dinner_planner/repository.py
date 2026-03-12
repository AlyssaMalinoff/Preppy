from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from dinner_planner.models import IngredientRecord, ParseIssue


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            servings TEXT,
            instructions TEXT,
            source_type TEXT NOT NULL,
            source_path TEXT,
            raw_text TEXT NOT NULL,
            parse_confidence REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'active',
            season_tag TEXT,
            day_priority INTEGER,
            difficulty_level TEXT,
            dish_category TEXT,
            seasonality_tags TEXT,
            repeat_policy TEXT,
            popularity_score REAL,
            classification_updated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            raw_text TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            quantity_value REAL,
            quantity_unit TEXT,
            preparation TEXT,
            is_optional INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS pending_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            issue_type TEXT NOT NULL,
            field_name TEXT NOT NULL,
            message TEXT NOT NULL,
            snippet TEXT,
            resolved INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    _ensure_recipe_metadata_columns(conn)
    conn.commit()


def _ensure_recipe_metadata_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(recipes)").fetchall()
    }
    required = {
        "difficulty_level": "TEXT",
        "dish_category": "TEXT",
        "seasonality_tags": "TEXT",
        "repeat_policy": "TEXT",
        "popularity_score": "REAL",
        "classification_updated_at": "TEXT",
    }
    for column, dtype in required.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE recipes ADD COLUMN {column} {dtype}")


def insert_recipe(
    conn: sqlite3.Connection,
    *,
    title: str,
    servings: str | None,
    instructions: str | None,
    source_type: str,
    source_path: str | None,
    raw_text: str,
    parse_confidence: float,
    ingredients: Iterable[IngredientRecord],
    issues: Iterable[ParseIssue],
) -> int:
    ingredient_list = list(ingredients)
    issue_list = list(issues)

    cursor = conn.execute(
        """
        INSERT INTO recipes (
            title, servings, instructions, source_type, source_path, raw_text, parse_confidence, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            servings,
            instructions,
            source_type,
            source_path,
            raw_text,
            parse_confidence,
            "pending_review" if issue_list else "active",
        ),
    )
    recipe_id = cursor.lastrowid

    for ingredient in ingredient_list:
        conn.execute(
            """
            INSERT INTO ingredients (
                recipe_id, raw_text, name_normalized, quantity_value, quantity_unit, preparation, is_optional
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recipe_id,
                ingredient.raw_text,
                ingredient.name_normalized,
                ingredient.quantity_value,
                ingredient.quantity_unit,
                ingredient.preparation,
                1 if ingredient.is_optional else 0,
            ),
        )

    for issue in issue_list:
        conn.execute(
            """
            INSERT INTO pending_issues (recipe_id, issue_type, field_name, message, snippet)
            VALUES (?, ?, ?, ?, ?)
            """,
            (recipe_id, issue.issue_type, issue.field_name, issue.message, issue.snippet),
        )

    conn.commit()
    return int(recipe_id)


def list_recipes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT id, title, parse_confidence, status, source_type, source_path, created_at
        FROM recipes
        ORDER BY id DESC
        """
    )
    return list(cursor.fetchall())


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()


def get_ingredients(conn: sqlite3.Connection, recipe_id: int) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT raw_text, name_normalized, quantity_value, quantity_unit, is_optional
        FROM ingredients
        WHERE recipe_id = ?
        ORDER BY id
        """,
        (recipe_id,),
    )
    return list(cursor.fetchall())


def list_pending_issues(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT pi.id, pi.recipe_id, r.title, pi.issue_type, pi.field_name, pi.message, pi.snippet
        FROM pending_issues pi
        JOIN recipes r ON r.id = pi.recipe_id
        WHERE pi.resolved = 0
        ORDER BY pi.id
        """
    )
    return list(cursor.fetchall())


def list_recipes_for_classification(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT id, title, instructions
        FROM recipes
        ORDER BY id
        """
    )
    return list(cursor.fetchall())


def get_ingredient_names(conn: sqlite3.Connection, recipe_id: int) -> list[str]:
    cursor = conn.execute(
        """
        SELECT name_normalized
        FROM ingredients
        WHERE recipe_id = ?
        ORDER BY id
        """,
        (recipe_id,),
    )
    return [row["name_normalized"] for row in cursor.fetchall()]


def update_recipe_classification(
    conn: sqlite3.Connection,
    *,
    recipe_id: int,
    difficulty_level: str,
    dish_category: str,
    seasonality_tags: list[str],
    repeat_policy: str,
    popularity_score: float,
) -> None:
    conn.execute(
        """
        UPDATE recipes
        SET difficulty_level = ?,
            dish_category = ?,
            seasonality_tags = ?,
            repeat_policy = ?,
            popularity_score = ?,
            classification_updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            difficulty_level,
            dish_category,
            json.dumps(seasonality_tags),
            repeat_policy,
            popularity_score,
            recipe_id,
        ),
    )
    conn.commit()


def list_planner_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT id, title, difficulty_level, dish_category, seasonality_tags, repeat_policy, popularity_score
        FROM recipes
        ORDER BY id
        """
    )
    return list(cursor.fetchall())

