"""TaskFlow — маленький трекер задач: FastAPI + SQLite + статический фронт."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db import get_conn, init_db

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

Status = Literal["todo", "doing", "done"]


# ---------- схемы запросов ----------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")


class TaskIn(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=200)
    notes: str = ""
    status: Status = "todo"
    priority: int = Field(default=2, ge=1, le=3)
    due_date: Optional[str] = None


class TaskPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    notes: Optional[str] = None
    status: Optional[Status] = None
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    due_date: Optional[str] = None
    project_id: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="TaskFlow API",
    description="Пет-проект: трекер задач на FastAPI + SQLite.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------- проекты ----------

@app.get("/api/projects", tags=["projects"])
def list_projects():
    """Список проектов со счётчиками задач."""
    sql = """
        SELECT p.id, p.name, p.color, p.created_at,
               COUNT(t.id)                                        AS total,
               SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done
        FROM projects p
        LEFT JOIN tasks t ON t.project_id = p.id
        GROUP BY p.id
        ORDER BY p.id
    """
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [{**dict(r), "done": r["done"] or 0} for r in rows]


@app.post("/api/projects", status_code=201, tags=["projects"])
def create_project(payload: ProjectIn):
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM projects WHERE name = ?", (payload.name,)
        ).fetchone()
        if exists:
            raise HTTPException(409, "Проект с таким именем уже есть")
        cur = conn.execute(
            "INSERT INTO projects (name, color) VALUES (?, ?)",
            (payload.name, payload.color),
        )
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.delete("/api/projects/{project_id}", status_code=204, tags=["projects"])
def delete_project(project_id: int):
    """Удаляет проект вместе с его задачами (ON DELETE CASCADE)."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Проект не найден")


# ---------- задачи ----------

@app.get("/api/tasks", tags=["tasks"])
def list_tasks(
    project_id: Optional[int] = None,
    status: Optional[Status] = None,
    q: Optional[str] = None,
):
    """Задачи с фильтрами по проекту, статусу и подстроке в названии/заметках."""
    sql = """
        SELECT t.*, p.name AS project_name, p.color AS project_color
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE 1 = 1
    """
    params: list = []
    if project_id is not None:
        sql += " AND t.project_id = ?"
        params.append(project_id)
    if status is not None:
        sql += " AND t.status = ?"
        params.append(status)
    if q:
        sql += " AND (t.title LIKE ? OR t.notes LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY t.priority DESC, t.id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/tasks", status_code=201, tags=["tasks"])
def create_task(payload: TaskIn):
    with get_conn() as conn:
        project = conn.execute(
            "SELECT 1 FROM projects WHERE id = ?", (payload.project_id,)
        ).fetchone()
        if not project:
            raise HTTPException(404, "Проект не найден")
        cur = conn.execute(
            """INSERT INTO tasks (project_id, title, notes, status, priority, due_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload.project_id,
                payload.title,
                payload.notes,
                payload.status,
                payload.priority,
                payload.due_date or None,
            ),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.patch("/api/tasks/{task_id}", tags=["tasks"])
def update_task(task_id: int, payload: TaskPatch):
    """Частичное обновление; при переходе в done проставляется done_at."""
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(400, "Нечего обновлять")

    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            raise HTTPException(404, "Задача не найдена")

        assignments = [f"{k} = ?" for k in fields]
        params = list(fields.values())
        if "status" in fields:
            assignments.append(
                "done_at = CASE WHEN ? = 'done' THEN datetime('now') ELSE NULL END"
            )
            params.append(fields["status"])

        conn.execute(
            f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?", [*params, task_id]
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row)


@app.delete("/api/tasks/{task_id}", status_code=204, tags=["tasks"])
def delete_task(task_id: int):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Задача не найдена")


# ---------- статистика ----------

@app.get("/api/stats", tags=["stats"])
def stats():
    """Сводка по статусам, просрочке и активности за неделю."""
    with get_conn() as conn:
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
            )
        }
        overdue = conn.execute(
            """SELECT COUNT(*) AS n FROM tasks
               WHERE status != 'done' AND due_date IS NOT NULL
                 AND date(due_date) < date('now')"""
        ).fetchone()["n"]
        done_week = conn.execute(
            """SELECT COUNT(*) AS n FROM tasks
               WHERE done_at IS NOT NULL AND done_at >= datetime('now', '-7 days')"""
        ).fetchone()["n"]

    total = sum(by_status.values())
    return {
        "total": total,
        "todo": by_status.get("todo", 0),
        "doing": by_status.get("doing", 0),
        "done": by_status.get("done", 0),
        "overdue": overdue,
        "done_last_7d": done_week,
    }


# ---------- фронтенд ----------

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
