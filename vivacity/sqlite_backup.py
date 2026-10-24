"""SQLite online backups and checked restore, without copying a live WAL file."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing


def _readonly(path: Path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=30.)


def _digest(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_database(path):
    target = Path(path).resolve(strict=True)
    with closing(_readonly(target)) as db:
        integrity = [row[0] for row in db.execute('PRAGMA integrity_check')]
        if integrity != ['ok']:
            raise ValueError('SQLite integrity check failed')
        schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall()
        return {'integrity': 'ok', 'page_count': db.execute('PRAGMA page_count').fetchone()[0],
                'schema_sha256': hashlib.sha256(repr(schema).encode()).hexdigest(),
                'tables': [row[1] for row in schema if row[0] == 'table']}


def consistent_backup(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if source == destination or destination.exists():
        raise FileExistsError('backup destination must be new')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.sqlite-backup-', suffix='.tmp', dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary)
    try:
        with closing(_readonly(source)) as origin, closing(sqlite3.connect(temporary)) as copied:
            origin.backup(copied, pages=128, sleep=.01)
            # A standalone backup must not depend on a transient WAL sidecar.
            copied.execute('PRAGMA journal_mode=DELETE')
        metadata = inspect_database(temporary)
        metadata.update(sha256=_digest(temporary), size_bytes=temporary.stat().st_size)
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        # Same-directory link is atomic and fails if another writer created the
        # destination. Never replace an existing backup or live database.
        os.link(temporary, destination)
        return metadata
    finally:
        temporary.unlink(missing_ok=True)


def restore_backup(source, destination, *, expected_sha256: str):
    source = Path(source).resolve(strict=True)
    if _digest(source) != expected_sha256:
        raise ValueError('backup checksum mismatch')
    destination = Path(destination).resolve()
    if any(Path(str(destination)+suffix).exists() for suffix in ('', '-wal', '-shm')):
        raise FileExistsError('restore requires a new database path without WAL sidecars')
    inspect_database(source)
    return consistent_backup(source, destination)
