"""Local operator utility; stop/drain workers before switching to a restore.

python -m scripts.sqlite_backup backup data/vivacity.sqlite3 backups/runtime-001.sqlite3
python -m scripts.sqlite_backup restore backups/runtime-001.sqlite3 data/restored.sqlite3 --sha256 HASH
"""
import argparse
import json

from vivacity.sqlite_backup import consistent_backup, restore_backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['backup', 'restore'])
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if args.operation == 'backup':
        result = consistent_backup(args.source, args.destination)
    else:
        if not args.sha256:
            parser.error('restore requires the recorded --sha256')
        result = restore_backup(args.source, args.destination, expected_sha256=args.sha256)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
