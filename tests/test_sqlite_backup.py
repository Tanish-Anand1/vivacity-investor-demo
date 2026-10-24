import sqlite3
from threading import Event, Thread
from contextlib import closing
import time

import pytest

from vivacity.sqlite_backup import consistent_backup, restore_backup


def test_online_wal_backup_is_consistent_and_restore_is_independent(tmp_path):
    source, backup, restored = (tmp_path/name for name in ('live.sqlite3', 'backup.sqlite3', 'restored.sqlite3'))
    with closing(sqlite3.connect(source)) as db, db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE values_pair(id INTEGER PRIMARY KEY,x INTEGER,y INTEGER)')
        db.execute('INSERT INTO values_pair VALUES(1,0,0)')
    started, finish = Event(), Event()
    def write():
        with closing(sqlite3.connect(source)) as db:
            for count in range(1, 1001):
                with db:
                    db.execute('UPDATE values_pair SET x=?,y=?', (count, count*2))
                started.set()
                if finish.wait(.001):
                    break
    worker = Thread(target=write)
    worker.start()
    try:
        assert started.wait(5)
        metadata = consistent_backup(source, backup)
        finish.set()
        worker.join(5)
        assert metadata['integrity'] == 'ok'
        assert metadata['size_bytes'] > 0
        assert metadata['tables'] == ['values_pair']
        with closing(sqlite3.connect(backup)) as db:
            x, y = db.execute('SELECT x,y FROM values_pair').fetchone()
            assert x >= 1 and y == 2*x
        restore_backup(backup, restored, expected_sha256=metadata['sha256'])
        with closing(sqlite3.connect(source)) as db:
            live_value = db.execute('SELECT x FROM values_pair').fetchone()[0]
        with closing(sqlite3.connect(restored)) as db, db:
            assert db.execute('SELECT x,y FROM values_pair').fetchone() == (x, y)
            db.execute('UPDATE values_pair SET x=999')
        with closing(sqlite3.connect(source)) as db:
            assert db.execute('SELECT x FROM values_pair').fetchone()[0] == live_value
    finally:
        finish.set()
        worker.join(5)


def test_backup_and_restore_never_overwrite_and_reject_corruption(tmp_path):
    source, target = tmp_path/'source.sqlite3', tmp_path/'target.sqlite3'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE evidence(id INTEGER)')
    metadata = consistent_backup(source, target)
    with pytest.raises(FileExistsError):
        consistent_backup(source, target)
    with pytest.raises(FileExistsError):
        restore_backup(target, source, expected_sha256=metadata['sha256'])
    with pytest.raises(ValueError, match='checksum'):
        restore_backup(target, tmp_path/'restored.sqlite3', expected_sha256='0'*64)
    assert not (tmp_path/'restored.sqlite3').exists()
