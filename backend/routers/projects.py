"""Проекты текущего пользователя."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from database import get_db
from deps import current_user, owned_project
from models import Project, Task, User
from schemas import ProjectIn, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    done_sum = func.sum(case((Task.status == "done", 1), else_=0))
    rows = db.execute(
        select(Project, func.count(Task.id), done_sum)
        .outerjoin(Task, Task.project_id == Project.id)
        .where(Project.user_id == user.id)
        .group_by(Project.id)
        .order_by(Project.id)
    ).all()
    return [
        ProjectOut(
            **ProjectOut.model_validate(p).model_dump(exclude={"total", "done"}),
            total=total or 0,
            done=int(done or 0),
        )
        for p, total, done in rows
    ]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    exists = db.scalar(
        select(Project).where(Project.user_id == user.id, Project.name == payload.name)
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Проект с таким именем уже есть")

    project = Project(user_id=user.id, name=payload.name, color=payload.color)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    project = owned_project(project_id, db, user)
    db.delete(project)
    db.commit()
