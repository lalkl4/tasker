#!/bin/sh
# Дамп базы перед миграцией. Запускается как `docker compose run --rm backup`.
set -eu

BACKUP_DIR=/backups
PATTERN='tasker-*.sql.gz'

# Имя содержит метку времени в сортируемом виде, поэтому лексикографический
# порядок совпадает с хронологическим — можно обойтись find и sort,
# не разбирая вывод ls
list_backups() {
	find "${BACKUP_DIR}" -maxdepth 1 -type f -name "${PATTERN}" | sort -r
}

STAMP=$(date +%Y%m%d-%H%M%S)
FILE="${BACKUP_DIR}/tasker-${STAMP}.sql.gz"

echo "Снимаю дамп в ${FILE}"
pg_dump --host=db --username=tasker --dbname=tasker --no-owner --no-acl \
	| gzip -9 > "${FILE}"

echo "Готово: ${FILE} ($(du -h "${FILE}" | cut -f1))"

# Ротация: держим последние KEEP штук. Без неё диск однажды кончится
# в самый неподходящий момент.
KEEP="${KEEP_BACKUPS:-14}"
list_backups | tail -n "+$((KEEP + 1))" | while read -r old; do
	echo "Удаляю старый дамп: ${old}"
	rm -f "${old}"
done

echo "Дампов на хранении: $(list_backups | wc -l)"
