"""Export numerical evidence from recorded real jobs; never export capabilities."""
import argparse
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default='data/master-verify.sqlite3')
    parser.add_argument('--proof', default='artifacts/master-live-verification.json')
    parser.add_argument('--output', default='artifacts/master-measurements.json')
    args = parser.parse_args()
    proof = json.loads(Path(args.proof).read_text(encoding='utf-8'))
    result = {'scope': 'measured persisted jobs referenced by the browser proof',
              'proof': args.proof, 'experiments': []}
    with sqlite3.connect(f'file:{Path(args.database).resolve().as_posix()}?mode=ro', uri=True) as db:
        for session in proof['sessions']:
            for eid in session['experiments']:
                row = db.execute('SELECT payload FROM experiments WHERE id=?', (eid,)).fetchone()
                if row is None:
                    raise ValueError(f'missing recorded experiment {eid}')
                experiment = json.loads(row[0])
                world = json.loads(db.execute('SELECT payload FROM worlds WHERE id=?',
                                              (experiment['world_id'],)).fetchone()[0])
                branches = [json.loads(row[0]) for row in db.execute(
                    'SELECT payload FROM branches WHERE experiment_id=?', (eid,))]
                # Deliberate allowlist: no session tokens, private requests or raw
                # generating configurations are read or exported.
                result['experiments'].append({'backend': session['backend'], 'id': eid,
                    'world_initialization': world['performance'],
                    'status': experiment['status'], 'selected_branch_id': experiment['selected_branch_id'],
                    'result': experiment['result'], 'performance': experiment['performance'],
                    'branches': [{'id': b['id'], 'hypothesis': b['action'].get('hypothesis'),
                        'execution_role': b['action'].get('execution_role'),
                        'evaluation': b['evaluation'], 'performance': b['performance']} for b in branches]})
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(f"Exported {len(result['experiments'])} actual experiments to {args.output}")


if __name__ == '__main__':
    main()
