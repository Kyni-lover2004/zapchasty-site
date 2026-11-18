#!/bin/sh
# Запускать с переменными PG* и каталогом назначения на отдельном диске.
set -eu
: "${BACKUP_ROOT:?Укажите BACKUP_ROOT на другом диске}"
umask 077
backup_dir="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
pg_dump -Fc -f "$backup_dir/catalog.dump"
tar -czf "$backup_dir/media.tar.gz" -C "${SHOP_MEDIA_ROOT:-/srv/z62/media}" .
printf '%s\n' "Резервная копия: $backup_dir"
