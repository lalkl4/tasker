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

# Отметка для мониторинга: node-exporter подбирает файлы .prom из своего
# текстового каталога и отдаёт их Prometheus как обычные метрики. Так
# алерт о протухшем бэкапе опирается на факт, а не на предположение.
TEXTFILE_DIR=/textfile
if [ -d "${TEXTFILE_DIR}" ]; then
	# Пишем во временный файл и переименовываем: node-exporter может
	# прочитать файл ровно в момент записи и увидеть половину
	cat > "${TEXTFILE_DIR}/tasker_backup.prom.tmp" <<PROM
# HELP tasker_backup_last_success_timestamp_seconds Время последнего успешного дампа
# TYPE tasker_backup_last_success_timestamp_seconds gauge
tasker_backup_last_success_timestamp_seconds $(date +%s)
# HELP tasker_backup_count Сколько дампов лежит на хранении
# TYPE tasker_backup_count gauge
tasker_backup_count $(list_backups | wc -l)
PROM
	mv "${TEXTFILE_DIR}/tasker_backup.prom.tmp" "${TEXTFILE_DIR}/tasker_backup.prom"
	echo "Метрика для мониторинга обновлена"
fi
