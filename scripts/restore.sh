#!/bin/sh
# Восстановление из дампа.
#   docker compose run --rm -e BACKUP_FILE=tasker-20260821-030000.sql.gz restore
# Без BACKUP_FILE показывает, что вообще есть.
set -eu

BACKUP_DIR=/backups

if [ -z "${BACKUP_FILE:-}" ]; then
	echo "Не задан BACKUP_FILE. Доступные дампы:"
	find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'tasker-*.sql.gz' | sort -r || true
	echo
	echo "Запуск: docker compose run --rm -e BACKUP_FILE=<имя> restore"
	exit 1
fi

FILE="${BACKUP_DIR}/${BACKUP_FILE}"
[ -f "${FILE}" ] || { echo "Нет такого файла: ${FILE}"; exit 1; }

echo "ВНИМАНИЕ: содержимое базы tasker будет заменено на ${BACKUP_FILE}"
echo "Восстанавливаю..."

# Пересоздаём схему целиком: иначе остатки старых таблиц смешаются с дампом
psql --host=db --username=tasker --dbname=tasker --quiet \
	-c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

gunzip -c "${FILE}" | psql --host=db --username=tasker --dbname=tasker --quiet

echo "Готово. Перезапустите приложение: docker compose restart api"
echo "Если версия схемы в дампе старее образа, накатите миграции:"
echo "  docker compose run --rm migrate"
