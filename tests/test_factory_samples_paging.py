"""Live replay pages stay contiguous across the durable/in-memory boundary."""
from fastapi.testclient import TestClient

from vivacity.api import create_app
from vivacity.workspace import owner


def test_live_sample_pages_cross_sqlite_tail_without_skips_or_duplicates(tmp_path):
    token = 'factory-pagination-owner-1234567890'
    run_id = 'pagination-run'
    with TestClient(create_app(tmp_path / 'factory.sqlite3')) as client:
        service = client.app.state.factory
        row = {
            'id': run_id, 'status': 'running', 'trace': [
                {'time': float(index), 'sample': index} for index in range(4)
            ],
        }
        service._save_run(row, owner(token))
        row['trace'] = [{'time': float(index), 'sample': index} for index in range(4, 7)]
        service.live[run_id] = row
        try:
            seen = []
            after = -1
            for expected_cursor in (2, 5, 6):
                page = service.samples(run_id, token, after=after, limit=3)
                assert len(page['frames']) <= 3
                assert page['next_index'] == expected_cursor
                assert page['total_samples'] == 7
                seen.extend(frame['sample'] for frame in page['frames'])
                after = page['next_index']
            assert seen == list(range(7))
        finally:
            service.live.pop(run_id, None)
