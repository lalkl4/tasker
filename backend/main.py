"""Tasker — сервер трекера задач. FastAPI + SQLAlchemy, SQLite или PostgreSQL."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import API_VERSIONS, MIN_CLIENT_VERSION, SERVER_VERSION, get_settings
from database import Base, engine
from routers import auth, projects, stats, tasks
from schemas import Discovery

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
settings = get_settings()

# Что этот сервер умеет. Клиент включает функции по этому списку, а не по номеру
# версии: при открытых исходниках форк может отличаться от любого известного номера.
CAPABILITIES = [
    "auth.password",
    "projects",
    "tasks",
    "tasks.search",
    "stats",
    "sync.updated_at",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Tasker API",
    description="Самохостимый трекер задач. Клиенты подключаются по URL инстанса.",
    version=SERVER_VERSION,
    lifespan=lifespan,
)

# Мобильный клиент и сторонние фронты ходят с другого источника
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/.well-known/tasker", response_model=Discovery, tags=["discovery"])
def discovery():
    """Точка входа для клиента: с чем он имеет дело и что здесь поддерживается."""
    return Discovery(
        product="tasker",
        server_version=SERVER_VERSION,
        api_versions=API_VERSIONS,
        capabilities=CAPABILITIES,
        min_client=MIN_CLIENT_VERSION,
        registration_open=settings.allow_registration,
    )


v1 = APIRouter(prefix="/api/v1")
for module in (auth, projects, tasks, stats):
    v1.include_router(module.router)
app.include_router(v1)


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    include_in_schema=False,
)
def legacy_api(path: str):
    """Понятный ответ клиентам версии 1.x вместо голого 404."""
    return JSONResponse(
        status_code=410,
        content={
            "detail": (
                "API без версии убран в 2.0.0. Используйте /api/v1/ — теперь "
                "требуется авторизация. Список возможностей: /.well-known/tasker"
            ),
            "moved_to": f"/api/v1/{path}",
        },
    )


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
