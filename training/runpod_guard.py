"""Stop only this pilot Pod at a fixed deadline, including during setup.

This is a best-effort operational limit, not a provider-enforced dollar cap.
An operator must also monitor the Pod and export evidence before shutdown.
Credentials remain in Runpod's own scoped CLI environment and are not logged.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time


def validate(pod_id, environment_id, deadline, now):
    if not re.fullmatch(r'[a-zA-Z0-9]{5,40}', pod_id) or pod_id != environment_id:
        raise ValueError('guard may stop only the current RUNPOD_POD_ID')
    if not 1 <= deadline-now <= 7200:
        raise ValueError('a deadline within the next two hours is required')


def record(journal, event):
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, allow_nan=False)+'\n')
        handle.flush()
        os.fsync(handle.fileno())


def guard(pod_id, deadline, journal, *, clock=time.time, sleep=time.sleep,
          run=subprocess.run):
    validate(pod_id, os.environ.get('RUNPOD_POD_ID'), deadline, clock())
    record(journal, {'event':'armed','pod_id':pod_id,'deadline_unix_s':deadline})
    while clock() < deadline:
        sleep(min(10., max(0., deadline-clock())))
    for attempt in range(1, 6):
        try:
            result=run(['runpodctl','pod','stop',pod_id], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            code=result.returncode
        except (OSError, subprocess.TimeoutExpired):
            code=-1
        record(journal, {'event':'stop_requested','attempt':attempt,
                        'time_unix_s':clock(),'exit_code':code})
        if code==0:
            # The CLI acknowledgement is not proof the provider stopped billing.
            # Verify the provider state externally before declaring shutdown.
            return True
        sleep(10.)
    record(journal, {'event':'STOP_FAILED_OPERATOR_ACTION_REQUIRED','time_unix_s':clock()})
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pod-id',required=True)
    parser.add_argument('--deadline',type=float,required=True)
    parser.add_argument('--journal',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(0 if guard(args.pod_id,args.deadline,args.journal) else 1)


if __name__=='__main__':
    main()
