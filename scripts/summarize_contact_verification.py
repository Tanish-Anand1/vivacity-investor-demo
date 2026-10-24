"""Summarize executed evidence; keep failed research and open release gates."""
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


def main():
    folder=Path('artifacts/physical-truth-runtime')
    acceptance=json.loads((folder/'bimanual-final-acceptance.json').read_text())
    assert acceptance['nominal']['trials']==20 and acceptance['held_out']['trials']==100, 'Acceptance run is still incomplete'
    for trial in acceptance['trials']:
        for name,digest in trial['source_sha256'].items():
            assert hashlib.sha256((Path('vivacity')/name).read_bytes()).hexdigest()==digest, f'Stale source evidence: {name}'
    failures=json.loads((folder/'failure-fixtures.json').read_text())
    http=json.loads((folder/'http-journey.json').read_text())
    test_results={}
    reports=['foundation-tests.xml','task-regression.xml','durable-final-tests.xml',
             'contact-api-tests.xml','baseline-final-tests.xml']
    for filename in sorted(reports,key=lambda name:(folder/name).stat().st_mtime):
        root=ET.parse(folder/filename)
        for test in root.findall('.//testcase'):
            test_results[test.attrib['classname']+'::'+test.attrib['name']]={
                'report':filename,'passed':test.find('failure') is None and test.find('error') is None,
                'skipped':test.find('skipped') is not None}
    raw=['bimanual-final-acceptance.json','http-journey.json','g1-whole-body-task.json',
         'g1-clarabel-research.json','g1-clarabel-load-25-research.json',
         'g1-clarabel-load-25-torque-1-research.json']
    artifacts={}
    for filename in raw:
        content=(folder/filename).read_bytes()
        (folder/(filename+'.gz')).write_bytes(gzip.compress(content,mtime=0))
        artifacts[filename]={'sha256':hashlib.sha256(content).hexdigest(),'uncompressed_bytes':len(content),
                             'archive':filename+'.gz'}
    trials=acceptance['trials']
    measurements=[t['measurements'] for t in trials]
    summary={
        'schema_version':'vivacity.physical-truth-checkpoint-evidence/1',
        'full_physical_truth_complete':False,'production_deployed':False,'opening_changed':False,
        'nominal':acceptance['nominal'],'held_out':acceptance['held_out'],
        'supported_sampled_envelope':acceptance['envelope'],
        'statistical_scope':acceptance['statistical_scope'],
        'native_g1':{'equality_constraints':sorted({t['equality_constraints'] for t in trials}),
            'minimum_steady_hand_share':min(m['minimum_hold_share'] for m in measurements),
            'maximum_placement_error_m':max(m['last_measurement']['destination_error_m'] for m in measurements),
            'all_transport_samples_retained':all(m['retained_transport_samples']==m['unsupported_transport_samples'] for m in measurements),
            'maximum_hold_force_balance_error_n':max(m['maximum_hold_force_balance_error_n'] for m in measurements),
            'compute_wall_s_p50':float(np.median([t['compute_wall_s'] for t in trials])),
            'compute_wall_s_max':max(t['compute_wall_s'] for t in trials),
            'simulation_steps_per_trial':sorted({m['steps'] for m in measurements}),
            'source_sha256':trials[0]['source_sha256']},
        'failure_fixtures':[{'fixture':t['fixture'],'success':t['task_success'],'reason':t['failure_reason']} for t in failures['trials']],
        'real_http_checks':http['checks'],
        'backup_restore':json.loads((folder/'backup-restore-verification.json').read_text()),
        'tests':{'unique_cases':len(test_results),'passed':sum(t['passed'] and not t['skipped'] for t in test_results.values()),
                 'failed':sum(not t['passed'] for t in test_results.values()),'skipped':sum(t['skipped'] for t in test_results.values()),'reports':reports},
        'artifacts':artifacts,
        'open_gates':['constrained whole-body manipulation and complete stabilization suite',
            'model-matched G1/Apollo/H1 locomotion, carrying and H1 running',
            'Apollo cabinet/latch/cartridge cycle','one shared physical warehouse through dispatch',
            'every exposed parameter and required-scenario coverage',
            'RGB-D-driven control and complete hardware-transfer package',
            'contact-scene frontend integration and cross-browser journeys',
            'paid hosting capacity, all-service queue draining, production release and 24-hour soak',
            'Break the Frame opening release (ordered after Physical Truth)']}
    (folder/'verification-summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
