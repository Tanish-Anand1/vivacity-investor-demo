"""Serialize current persisted responses and captured WS messages without secrets."""
import argparse
import json
from pathlib import Path
import sqlite3

from vivacity.schemas import ExperimentResponse, SessionResponse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default='data/master-verify.sqlite3')
    parser.add_argument('--proof', default='artifacts/master-live-verification.json')
    parser.add_argument('--output', default='docs/master-frontend-examples.json')
    args = parser.parse_args()
    proof = json.loads(Path(args.proof).read_text(encoding='utf-8'))
    examples = {'source': 'persisted measured response fields and captured browser WebSocket messages',
                'proof': args.proof, 'responses': [],
                'websocket_live': proof.get('live_message_example'),
                'websocket_events': proof.get('event_message_examples', {})}
    with sqlite3.connect(f'file:{Path(args.database).resolve().as_posix()}?mode=ro', uri=True) as db:
        for session in proof['sessions']:
            examples['responses'].append({'method': 'GET', 'path': f"/v1/sessions/{session['id']}",
                                         'body': SessionResponse.model_validate(session).model_dump()})
            for eid in session['experiments']:
                stored = json.loads(db.execute('SELECT payload FROM experiments WHERE id=?', (eid,)).fetchone()[0])
                world = json.loads(db.execute('SELECT payload FROM worlds WHERE id=?', (stored['world_id'],)).fetchone()[0])
                stored['stale'] = world['revision'] != stored['result'].get('executed_world_revision', stored['revision'])
                body = ExperimentResponse.model_validate({k: stored[k] for k in ExperimentResponse.model_fields}).model_dump()
                examples['responses'].append({'method': 'GET', 'path': f'/v1/experiments/{eid}', 'body': body})
    encoded = json.dumps(examples, indent=2, allow_nan=False)
    if 'hidden_mass' in encoded or 'token_hash' in encoded:
        raise ValueError('private fields must not appear in frontend examples')
    Path(args.output).write_text(encoded, encoding='utf-8')
    print(f"Exported {len(examples['responses'])} measured response examples")


if __name__ == '__main__':
    main()
