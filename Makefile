.DEFAULT_GOAL := help
SHELL := /bin/sh

COMPOSE     := docker compose
COMPOSE_DEV := docker compose -f compose.yaml -f compose.dev.yaml
ENV_FILE    := .env

.PHONY: help up down restart ps logs config version update rollback backup restore dev dev-down obs-up obs-down obs-logs full-up

help: ## Показать список команд
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---------- повседневное ----------

up: ## Поднять стек
	$(COMPOSE) up -d --wait

down: ## Остановить стек (тома и данные остаются на месте)
	$(COMPOSE) down

restart: ## Перезапустить сервисы приложения, не трогая базу
	$(COMPOSE) restart api web caddy

ps: ## Состояние сервисов
	$(COMPOSE) ps

logs: ## Логи всех сервисов
	$(COMPOSE) logs -f --tail=100

config: ## Проверить, что compose-файлы валидны
	$(COMPOSE) config --quiet && echo "compose корректен"

version: ## Какая версия развёрнута
	@grep '^TASKER_VERSION=' $(ENV_FILE) || echo "TASKER_VERSION не задан"
	@echo "--- что реально отвечает ---"
	@curl -fsS http://localhost:$${TASKER_HTTP_PORT:-80}/.well-known/tasker 2>/dev/null \
		|| echo "сервер не отвечает"

# ---------- обновление и откат ----------

update: ## Обновиться до версии: make update VERSION=1.4.3
ifndef VERSION
	$(error Укажите версию: make update VERSION=1.4.3)
endif
	@echo "==> 1/5 дамп базы (до миграций, иначе восстанавливаться будет не из чего)"
	$(COMPOSE) --profile tools run --rm backup
	@echo "==> 2/5 запоминаю текущую версию для отката"
	@grep '^TASKER_VERSION=' $(ENV_FILE) > .env.previous
	@echo "==> 3/5 переключаю на $(VERSION)"
	@sed -i.bak 's/^TASKER_VERSION=.*/TASKER_VERSION=$(VERSION)/' $(ENV_FILE) && rm -f $(ENV_FILE).bak
	$(COMPOSE) pull
	@echo "==> 4/5 поднимаю; --wait дождётся healthcheck и упадёт, если не взлетело"
	$(COMPOSE) up -d --wait
	@echo "==> 5/5 проверяю"
	@$(MAKE) --no-print-directory version
	@echo "Готово. Логи: make logs"

rollback: ## Вернуться на предыдущую версию
	@test -f .env.previous || { echo "Нет .env.previous — откатываться некуда"; exit 1; }
	@echo "==> возвращаю $$(cat .env.previous)"
	@grep '^TASKER_VERSION=' $(ENV_FILE) > .env.rolled-back-from
	@sed -i.bak "s|^TASKER_VERSION=.*|$$(cat .env.previous)|" $(ENV_FILE) && rm -f $(ENV_FILE).bak
	$(COMPOSE) pull
	$(COMPOSE) up -d --wait
	@$(MAKE) --no-print-directory version
	@echo
	@echo "ВАЖНО: откатился только код. Схема базы осталась новой."
	@echo "Это штатно, если миграция была совместимой (expand/contract)."
	@echo "Если нет — восстанавливайте из дампа: make restore"

# ---------- данные ----------

backup: ## Снять дамп базы прямо сейчас
	$(COMPOSE) --profile tools run --rm backup

restore: ## Восстановить из дампа: make restore FILE=tasker-20260821-030000.sql.gz
	$(COMPOSE) --profile tools run --rm $(if $(FILE),-e BACKUP_FILE=$(FILE),) restore

# ---------- наблюдаемость ----------

COMPOSE_OBS := docker compose -f compose.yaml -f compose.observability.yaml

obs-up: ## Поднять стек вместе с мониторингом
	$(COMPOSE_OBS) up -d --wait
	@echo
	@echo "Grafana и Prometheus слушают только 127.0.0.1. С удалённого сервера:"
	@echo "  ssh -L 3000:localhost:3000 -L 9090:localhost:9090 user@server"
	@echo "Дальше: http://localhost:3000 (дашборд «Tasker — обзор»)"

obs-down: ## Погасить мониторинг вместе со стеком
	$(COMPOSE_OBS) down

obs-logs: ## Логи сервисов мониторинга
	$(COMPOSE_OBS) logs -f --tail=100 prometheus grafana loki alloy

# ---------- разработка ----------

dev: ## Локальная разработка: сборка из соседних репозиториев, автоперезагрузка
	$(COMPOSE_DEV) up --build

dev-down: ## Погасить окружение разработки
	$(COMPOSE_DEV) down
