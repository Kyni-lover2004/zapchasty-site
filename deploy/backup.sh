#!/bin/sh
# Запускать с переменными PG* и каталогом назначения на отдельном диске.
set -eu
: "${BACKUP_ROOT:?Укажите BACKUP_ROOT на другом диске}"
umask 077
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 - "$BACKUP_ROOT" "$project_dir" <<'PY'
from pathlib import Path
import sys
destination = Path(sys.argv[1]).resolve()
project = Path(sys.argv[2]).resolve()
if not Path(sys.argv[1]).is_absolute() or destination == project or project in destination.parents:
    raise SystemExit('BACKUP_ROOT должен быть абсолютным путём вне проекта.')
PY
backup_dir="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)-$$.incomplete"
mkdir -p "$backup_dir"
pg_dump -Fc -f "$backup_dir/catalog.dump"
tar -czf "$backup_dir/media.tar.gz" -C "${SHOP_MEDIA_ROOT:-/srv/z62/media}" .
python3 - "$backup_dir" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
directory = Path(sys.argv[1])
files = {}
for name in ['catalog.dump', 'media.tar.gz']:
    digest = hashlib.sha256()
    with (directory / name).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    files[name] = {'sha256': digest.hexdigest(), 'size': (directory / name).stat().st_size}
(directory / 'manifest.json').write_text(json.dumps(files, indent=2) + '\n')
PY
completed_dir=${backup_dir%.incomplete}
mv "$backup_dir" "$completed_dir"
printf '%s\n' "Резервная копия: $completed_dir"
