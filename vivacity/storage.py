from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
import time


def encode(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':'))


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS worlds(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS branches(id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS branch_experiment ON branches(experiment_id);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS event_experiment ON events(experiment_id, seq);
                CREATE TABLE IF NOT EXISTS submissions(
                    world_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    PRIMARY KEY(world_id, key)
                );
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS session_worlds(world_id TEXT PRIMARY KEY, session_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS trials(experiment_id TEXT NOT NULL, candidate_index INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(experiment_id,candidate_index));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, table, identifier, db=None):
        if table not in ('worlds', 'experiments', 'branches', 'sessions'):
            raise ValueError('invalid table')
        if db is None:
            with self.connect() as connection:
                return self.get(table, identifier, connection)
        row = db.execute(f'SELECT payload FROM {table} WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return json.loads(row[0])

    def put(self, table, record, db=None):
        if db is None:
            with self.connect() as connection:
                return self.put(table, record, connection)
        if table in ('worlds', 'experiments', 'sessions'):
            db.execute(f'INSERT INTO {table}(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (record['id'], encode(record)))
        elif table == 'branches':
            db.execute('INSERT INTO branches(id,experiment_id,payload) VALUES(?,?,?)', (record['id'], record['experiment_id'], encode(record)))
        else:
            raise ValueError('invalid table')

    def branches(self, experiment_id):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT payload FROM branches WHERE experiment_id=? ORDER BY rowid', (experiment_id,))]

    def trial(self, experiment_id, record):
        with self.connect() as db:
            db.execute('INSERT INTO trials VALUES(?,?,?)',(experiment_id,record['candidate_index'],encode(record)))

    def trials(self, experiment_id, after=-1, limit=50):
        with self.connect() as db:
            count=db.execute('SELECT COUNT(*) FROM trials WHERE experiment_id=?',(experiment_id,)).fetchone()[0]
            records=[json.loads(r[1])|{'completion_seq':r[0]} for r in db.execute('SELECT rowid,payload FROM trials WHERE experiment_id=? AND rowid>? ORDER BY rowid LIMIT ?',
                                                       (experiment_id,after,limit))]
        return {'schema_version':'vivacity.trials/1.0','completed':count,'items':records,
                'next_after':records[-1]['completion_seq'] if records else None}

    def event(self, experiment_id, kind, details=None, db=None):
        if db is None:
            with self.connect() as connection:
                return self.event(experiment_id, kind, details, connection)
        measured = {'timestamp_unix_s': time.time()} | (details or {})
        db.execute('INSERT INTO events(experiment_id,payload) VALUES(?,?)', (experiment_id, encode({'schema_version': '1.0', 'kind': kind, 'details': measured})))

    def events(self, experiment_id, after=0):
        with self.connect() as db:
            return [json.loads(payload) | {'seq': seq} for seq, payload in db.execute('SELECT seq,payload FROM events WHERE experiment_id=? AND seq>? ORDER BY seq LIMIT 100', (experiment_id, after))]
