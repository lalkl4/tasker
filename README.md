# Tasker

Самохостимый трекер задач. Поднимаете сервер у себя, указываете его адрес в
клиенте — и работаете с одними и теми же задачами из браузера и с телефона.

```
Веб-клиент ─┐
            ├─HTTP─▶ Tasker API (FastAPI) ──SQLAlchemy──▶ PostgreSQL или SQLite
Мобильный ──┘                │
   клиент                    └── статика веб-клиента
```

Готовый образ: [`lalkl4/tasker`](https://hub.docker.com/r/lalkl4/tasker) —
публичный, авторизация для загрузки не нужна.

## Стек

| Слой    | Технология                                       |
|---------|--------------------------------------------------|
| Веб     | HTML + CSS + vanilla JS, без сборки              |
| Мобайл  | Flutter                                          |
| Сервер  | Python 3 + FastAPI + SQLAlchemy 2                 |
| БД      | PostgreSQL, либо SQLite для запуска в один контейнер |
| Вход    | Учётные записи, пароли на Argon2, токены JWT      |

## Запуск

### Полный вариант: сервер + PostgreSQL

```bash
cp .env.example .env   # и обязательно смените TASKER_DB_PASSWORD
docker compose up -d
```

### Простой вариант: один контейнер на SQLite

Годится для домашнего сервера и небольшой команды — база лежит файлом в томе.

```bash
docker run -d -p 8000:8000 -v tasker-data:/app/data --name tasker lalkl4/tasker:latest
```

В обоих случаях:

- Приложение: http://localhost:8000
- Swagger-документация API: http://localhost:8000/docs

Первый зашедший регистрируется сам. Чтобы больше никого не пускать, поставьте
`TASKER_ALLOW_REGISTRATION=false` и перезапустите.

## Настройки

Все читаются из переменных окружения, менять файлы не нужно.

| Переменная                  | По умолчанию          | Зачем                                                     |
|-----------------------------|-----------------------|-----------------------------------------------------------|
| `TASKER_DATABASE_URL`       | SQLite в `/app/data`  | `postgresql+psycopg://user:pass@host/db` для PostgreSQL    |
| `TASKER_JWT_SECRET`         | генерируется сам      | Задайте явно, если реплик несколько                        |
| `TASKER_JWT_TTL_HOURS`      | `336` (14 суток)      | Сколько живёт токен                                        |
| `TASKER_CORS_ORIGINS`       | `*`                   | Домены через запятую для публичного инстанса               |
| `TASKER_ALLOW_REGISTRATION` | `true`                | `false` закрывает создание новых учётных записей           |

Пустой `TASKER_JWT_SECRET` сервер генерирует при первом старте и сохраняет в
`/app/data/.jwt_secret`, чтобы рестарт не разлогинивал всех подряд.

## Как клиент подключается к серверу

Клиент не зашит под конкретную версию. При подключении он спрашивает у сервера,
что тот умеет:

```
GET /.well-known/tasker

{
  "product": "tasker",
  "server_version": "2.0.0",
  "api_versions": ["v1"],
  "capabilities": ["auth.password", "projects", "tasks", "tasks.search",
                   "stats", "sync.updated_at"],
  "min_client": "1.0.0",
  "registration_open": true
}
```

Дальше клиент выбирает старшую версию API из тех, что понимает сам, и включает
функции по списку `capabilities`, а не по номеру версии. Так сделано намеренно:
исходники открыты, форки неизбежны, и номер чужой сборки ничего не говорит о её
возможностях — а список умений говорит.

## API

Все пути живут под `/api/v1` и требуют заголовок `Authorization: Bearer <токен>`,
кроме регистрации и входа.

| Метод  | Путь                    | Описание                                             |
|--------|-------------------------|------------------------------------------------------|
| POST   | `/auth/register`        | Регистрация, сразу возвращает токен                  |
| POST   | `/auth/login`           | Вход                                                 |
| GET    | `/auth/me`              | Кто я                                                |
| GET    | `/projects`             | Проекты со счётчиками задач                          |
| POST   | `/projects`             | Создать проект                                       |
| DELETE | `/projects/{id}`        | Удалить проект вместе с задачами                     |
| GET    | `/tasks`                | Фильтры `project_id`, `status`, `q`, `since`         |
| POST   | `/tasks`                | Создать задачу                                       |
| PATCH  | `/tasks/{id}`           | Частично обновить                                    |
| DELETE | `/tasks/{id}`           | Удалить                                              |
| GET    | `/stats`                | Сводка: статусы, просрочка, закрыто за 7 дней        |

Параметр `since` отдаёт только задачи, изменённые после указанного момента —
на нём строится докачка изменений на клиенте.

Чужие проекты и задачи отдают **404**, а не 403: иначе по кодам ответа можно
было бы выяснять, что у соседа вообще есть.

## Схема БД

```sql
users(id, email UNIQUE, password_hash, display_name, created_at)
projects(id, user_id → users.id ON DELETE CASCADE, name, color, created_at,
         UNIQUE(user_id, name))
tasks(id, project_id → projects.id ON DELETE CASCADE,
      title, notes, status, priority, due_date,
      created_at, updated_at, done_at)
```

Таблицы создаются при старте. Схема одинакова для PostgreSQL и SQLite.

## Возможности веб-клиента

- Сайдбар проектов с цветовыми метками и прогрессом `выполнено/всего`
- Доска «К выполнению» → «В работе» → «Готово» со стрелками перевода
- Приоритет цветной полосой на карточке, срок с подсветкой просрочки
- Поиск по названию и заметкам, редактирование и удаление задач

## Структура

```
backend/main.py       приложение, CORS, дискавери, раздача статики
backend/config.py     настройки из окружения
backend/database.py   подключение к БД, одинаковое для обеих СУБД
backend/models.py     User, Project, Task
backend/security.py   Argon2 и JWT
backend/routers/      auth, projects, tasks, stats
frontend/             веб-клиент
mobile/               клиент на Flutter
Dockerfile            python:3.13-slim, непривилегированный пользователь
docker-compose.yml    сервер + PostgreSQL
```

## Совместимость

Версия 2.0.0 ломает обратную совместимость: API переехал с `/api/` на
`/api/v1/` и требует авторизации. Старые пути отвечают `410 Gone` с указанием,
куда переехало. Клиенты версии 1.x работать не будут.

## Лицензия

MIT — см. [LICENSE](LICENSE).
