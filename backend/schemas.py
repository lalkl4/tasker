"""Схемы запросов и ответов API v1."""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Status = Literal["todo", "doing", "done"]


# ---------- пользователи ----------

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# ---------- проекты ----------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    created_at: datetime
    total: int = 0
    done: int = 0


# ---------- задачи ----------

class TaskIn(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=200)
    notes: str = ""
    status: Status = "todo"
    priority: int = Field(default=2, ge=1, le=3)
    due_date: Optional[date] = None


class TaskPatch(BaseModel):
    project_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    notes: Optional[str] = None
    status: Optional[Status] = None
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    due_date: Optional[date] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    notes: str
    status: Status
    priority: int
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    done_at: Optional[datetime]
    project_name: str = ""
    project_color: str = ""


# ---------- прочее ----------

class StatsOut(BaseModel):
    total: int
    todo: int
    doing: int
    done: int
    overdue: int
    done_last_7d: int


class Discovery(BaseModel):
    """Ответ /.well-known/tasker — по нему клиент понимает, с чем имеет дело."""

    product: str
    server_version: str
    api_versions: list[str]
    capabilities: list[str]
    min_client: str
    registration_open: bool
