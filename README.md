# TaskFlow

Трекер задач с проектами и доской из трёх колонок. Пет-проект: фронтенд,
бэкенд и база SQLite в одном контейнере.

```
Браузер ──HTTP──▶ FastAPI (backend/main.py) ──sqlite3──▶ data/app.db
   ▲                       │
   └── статика из frontend/ ┘
```

## Стек

| Слой  | Технология                                              |
|-------|---------------------------------------------------------|
| Фронт | HTML + CSS + vanilla JS, без сборки                     |
| Бэк   | Python 3 + FastAPI + Uvicorn                            |
| БД    | SQLite через модуль `sqlite3` из стандартной библиотеки |

## Запуск в Docker

```bash
docker compose up --build
```

Или напрямую из готового образа:

```bash
docker run -d -p 8000:8000 -v taskflow-data:/app/data --name tasker <docker-hub-логин>/tasker:latest
```

- Приложение: http://localhost:8000
- Swagger-документация API: http://localhost:8000/docs

База лежит в томе `taskflow-data`, смонтированном в `/app/data`, и переживает
пересоздание контейнера. Чтобы начать с чистого листа — удалите том:
`docker volume rm taskflow-data`.

## Запуск без Docker

```bash
pip install -r requirements.txt
python -m uvicorn main:app --app-dir backend --port 8000 --reload
```

## Схема БД

```sql
projects(id, name UNIQUE, color, created_at)
tasks(id, project_id → projects.id ON DELETE CASCADE,
      title, notes, status, priority, due_date, created_at, done_at)
```

Схема создаётся автоматически при старте, пустая база наполняется демо-данными.

## API

| Метод  | Путь                 | Описание                                      |
|--------|----------------------|-----------------------------------------------|
| GET    | `/api/projects`      | Проекты со счётчиками задач                   |
| POST   | `/api/projects`      | Создать проект                                |
| DELETE | `/api/projects/{id}` | Удалить проект вместе с задачами              |
| GET    | `/api/tasks`         | Задачи; фильтры `project_id`, `status`, `q`   |
| POST   | `/api/tasks`         | Создать задачу                                |
| PATCH  | `/api/tasks/{id}`    | Частично обновить задачу                      |
| DELETE | `/api/tasks/{id}`    | Удалить задачу                                |
| GET    | `/api/stats`         | Сводка: статусы, просрочка, закрыто за 7 дней |

## Возможности интерфейса

- Сайдбар проектов с цветовыми метками и прогрессом `выполнено/всего`
- Доска «К выполнению» → «В работе» → «Готово» со стрелками перевода
- Приоритет цветной полосой на карточке, срок с подсветкой просрочки
- Поиск по названию и заметкам, редактирование и удаление задач

## Структура

```
backend/main.py   REST API и раздача статики
backend/db.py     схема, подключение, демо-данные
frontend/         index.html, style.css, app.js
Dockerfile        образ на python:3.13-slim, запуск от непривилегированного пользователя
docker-compose.yml
```
