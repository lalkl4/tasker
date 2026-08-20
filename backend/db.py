"""Слой работы с SQLite: подключение, схема, сиды."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    color      TEXT    NOT NULL DEFAULT '#6366f1',
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title      TEXT    NOT NULL,
    notes      TEXT    NOT NULL DEFAULT '',
    status     TEXT    NOT NULL DEFAULT 'todo'
               CHECK (status IN ('todo', 'doing', 'done')),
    priority   INTEGER NOT NULL DEFAULT 2
               CHECK (priority BETWEEN 1 AND 3),
    due_date   TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    done_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status);
"""

SEED_PROJECTS = [
    ("Личное", "#22c55e"),
    ("Работа", "#6366f1"),
    ("Учёба", "#f59e0b"),
]

SEED_TASKS = [
    (1, "Полить кактус", "Он держится, но недолго", "todo", 2, None),
    (1, "Записаться к врачу", "", "doing", 3, "2026-08-25"),
    (1, "Разобрать фотки с отпуска", "", "done", 1, None),
    (2, "Дописать отчёт по камерам", "Секция про ребуты", "doing", 3, "2026-08-22"),
    (2, "Ревью PR #431", "", "todo", 2, None),
    (2, "Обновить дашборд в Grafana", "Добавить панель uptime", "todo", 1, None),
    (3, "Глава 4 по SQL", "Оконные функции", "todo", 2, "2026-08-28"),
    (3, "Задачи по алгоритмам", "5 штук на графы", "done", 2, None),
]


def get_conn() -> sqlite3.Connection:
    """Новое соединение с включёнными внешними ключами и dict-строками."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Создаёт схему и, если база пустая, наливает демо-данные."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        empty = conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"] == 0
        if empty:
            conn.executemany(
                "INSERT INTO projects (name, color) VALUES (?, ?)", SEED_PROJECTS
            )
            conn.executemany(
                """INSERT INTO tasks (project_id, title, notes, status, priority, due_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                SEED_TASKS,
            )
            conn.execute(
                "UPDATE tasks SET done_at = datetime('now') WHERE status = 'done'"
            )
