#!/bin/sh
# Запускать отдельной ролью с CREATEDB; рабочая база не изменяется.
set -eu
umask 077
backup_dir=${1:?Укажите каталог завершённой резервной копии}
: "${PGDATABASE:?Укажите рабочую базу для подключения служебных команд}"
python3 - "$backup_dir" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
directory = Path(sys.argv[1])
if directory.name.endswith('.incomplete'):
    raise SystemExit('Копия не завершена.')
manifest = json.loads((directory / 'manifest.json').read_text())
if set(manifest) != {'catalog.dump', 'media.tar.gz'}:
    raise SystemExit('Некорректный состав копии.')
for name, expected in manifest.items():
    digest = hashlib.sha256()
    with (directory / name).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected['sha256'] or (directory / name).stat().st_size != expected['size']:
        raise SystemExit('Контрольная сумма не совпала: ' + name)
PY
tar -tzf "$backup_dir/media.tar.gz" >/dev/null
verify_database=$(python3 -c 'import secrets; print("z62_verify_" + secrets.token_hex(8))')
created=0
cleanup() {
    if [ "$created" = 1 ]; then
        dropdb --maintenance-db="$PGDATABASE" --if-exists "$verify_database"
    fi
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM
createdb --maintenance-db="$PGDATABASE" "$verify_database"
created=1
pg_restore --no-owner --no-acl --exit-on-error --dbname="$verify_database" "$backup_dir/catalog.dump"
psql --dbname="$verify_database" -X -v ON_ERROR_STOP=1 -Atc 'SELECT count(*) FROM django_migrations; SELECT count(*) FROM shop_product;'
printf '%s\n' 'Контрольные суммы, архив фотографий и восстановление PostgreSQL проверены.'
