from subprocess import CompletedProcess, TimeoutExpired

import pytest

from training.runpod_guard import guard, validate


@pytest.mark.parametrize('identity,environment,deadline',[
    ('pilot123','other456',120),('pilot;stop','pilot;stop',120),
    ('pilot123','pilot123',99),('pilot123','pilot123',7400),
    ('pilot123','pilot123',float('nan')),
])
def test_invalid_or_unowned_pod_cannot_be_stopped(identity,environment,deadline):
    with pytest.raises(ValueError):
        validate(identity,environment,deadline,100)


def test_deadline_stops_exact_owned_pod_without_logging_credentials(tmp_path,monkeypatch):
    monkeypatch.setenv('RUNPOD_POD_ID','pilot123')
    now=[100.]
    calls=[]
    def sleep(seconds):
        now[0]+=seconds
    def run(argv,**kwargs):
        assert now[0]>=131.
        assert kwargs['timeout']==30 and not kwargs['check']
        calls.append(argv)
        return CompletedProcess(argv,0)
    journal=tmp_path/'guard.jsonl'
    assert guard('pilot123',131.,journal,clock=lambda:now[0],sleep=sleep,run=run)
    assert calls==[['runpodctl','pod','stop','pilot123']]
    assert 'armed' in journal.read_text() and 'stop_requested' in journal.read_text()


def test_failed_provider_stop_retries_and_remains_an_explicit_failure(tmp_path,monkeypatch):
    monkeypatch.setenv('RUNPOD_POD_ID','pilot123')
    now=[100.]
    attempts=[]
    def sleep(seconds):
        now[0]+=seconds
    def run(argv,**kwargs):
        attempts.append(argv)
        raise TimeoutExpired(argv,30)
    journal=tmp_path/'guard.jsonl'
    assert not guard('pilot123',101.,journal,clock=lambda:now[0],sleep=sleep,run=run)
    assert len(attempts)==5
    assert 'STOP_FAILED_OPERATOR_ACTION_REQUIRED' in journal.read_text()
