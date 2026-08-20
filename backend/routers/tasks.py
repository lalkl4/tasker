"""Задачи текущего пользователя. Поддерживает докачку изменений по updated_at."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import get_db
from deps import current_user, owned_project
from models import Project, Task, User
from schemas import Status, TaskIn, TaskOut, TaskPatch

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _out(task: Task) -> TaskOut:
    data = TaskOut.model_validate(task).model_dump(
        exclude={"project_name", "project_color"}
    )
    return TaskOut(
        **data, project_name=task.project.name, project_color=task.project.color
    )


@router.get("", response_model=list[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    project_id: Optional[int] = None,
    status_: Optional[Status] = Query(default=None, alias="status"),
    q: Optional[str] = None,
    since: Optional[datetime] = Query(
        default=None,
        description="Вернуть только изменённые после этого момента — для докачки на клиенте",
    ),
):
    stmt = (
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .options(joinedload(Task.project))
        .where(Project.user_id == user.id)
    )
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if status_ is not None:
        stmt = stmt.where(Task.status == status_)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Task.title.ilike(like) | Task.notes.ilike(like))
    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        stmt = stmt.where(Task.updated_at > since)

    stmt = stmt.order_by(Task.priority.desc(), Task.id.desc())
    return [_out(t) for t in db.scalars(stmt).unique()]


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    owned_project(payload.project_id, db, user)
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return _out(task)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskPatch,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    task = db.get(Task, task_id)
    if task is None or task.project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нечего обновлять")

    # Переносить задачу можно только в свой же проект
    if "project_id" in fields:
        owned_project(fields["project_id"], db, user)

    for key, value in fields.items():
        setattr(task, key, value)
    if "status" in fields:
        task.done_at = datetime.now(timezone.utc) if fields["status"] == "done" else None

    db.commit()
    db.refresh(task)
    return _out(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    task = db.get(Task, task_id)
    if task is None or task.project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    db.delete(task)
    db.commit()
