"""Сводка по задачам текущего пользователя."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from deps import current_user
from models import Project, Task, User
from schemas import StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    mine = select(Project.id).where(Project.user_id == user.id).scalar_subquery()

    by_status = dict(
        db.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.project_id.in_(mine))
            .group_by(Task.status)
        ).all()
    )

    overdue = db.scalar(
        select(func.count(Task.id)).where(
            Task.project_id.in_(mine),
            Task.status != "done",
            Task.due_date.is_not(None),
            Task.due_date < date.today(),
        )
    )

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    done_week = db.scalar(
        select(func.count(Task.id)).where(
            Task.project_id.in_(mine),
            Task.done_at.is_not(None),
            Task.done_at >= week_ago,
        )
    )

    return StatsOut(
        total=sum(by_status.values()),
        todo=by_status.get("todo", 0),
        doing=by_status.get("doing", 0),
        done=by_status.get("done", 0),
        overdue=overdue or 0,
        done_last_7d=done_week or 0,
    )
