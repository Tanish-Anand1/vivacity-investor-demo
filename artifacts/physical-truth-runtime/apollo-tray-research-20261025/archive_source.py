"""Archive measured failures without relabeling them as task acceptance."""
import gzip
import hashlib
import json
from pathlib import Path

root = Path(__file__).parent
dest = root.parents[1] / 'artifacts/physical-truth-runtime/apollo-tray-research-20261025'
dest.mkdir(parents=True, exist_ok=True)
sha = lambda data: hashlib.sha256(data).hexdigest()
index = {'scope': 'Development evidence only; no full cabinet-service successes.',
         'verified_application_commit': 'b49552c64aced96b972ee8eba4d410e29fc8a8a1',
         'model_binaries_included': False, 'trials': [], 'files': {}}

def save(name, data):
    (dest/name).write_bytes(data)
    index['files'][name] = {'sha256':sha(data), 'bytes':len(data)}

def packed(name, data):
    save(name, gzip.compress(data, mtime=0))

sources = {}
for p in root.glob('probe_*.py'):
    sources[sha(p.read_bytes())] = (p.name,p.read_bytes())
for directory in ('lower-tray-swing', 'old-tray-swing'):
    folder = root/directory
    initial = json.loads((folder/'report.json').read_bytes())
    overrides = (folder/'probe_source.py').read_bytes()
    sources[sha(overrides)] = (directory+'-source.py',overrides)
    with (folder/'model.mjb').open('rb') as handle:
        model_sha = hashlib.file_digest(handle,'sha256').hexdigest()
    assert model_sha == initial['model_sha256']
    source_files = {}
    for name, expected in initial['source_hashes'].items():
        raw = (folder/'sources'/name).read_bytes()
        assert sha(raw) == expected, name
        source_files[name] = raw.decode()
    packed(directory+'-runtime-sources.json.gz', json.dumps(source_files,sort_keys=True).encode())
    checkpoints = {p.name:p.read_text() for p in folder.glob('0*.json')}
    packed(directory+'-checkpoints.json.gz', json.dumps(checkpoints,sort_keys=True).encode())
    checkpoint_hashes = {sha(text.encode()):json.loads(text) for text in checkpoints.values()}
    for report_file in sorted(folder.glob('*.json')):
        if report_file.name[0].isdigit():
            continue
        raw = report_file.read_bytes()
        report = json.loads(raw)
        assert report['model_sha256'] == model_sha
        source_sha = report['research_source_sha256']
        source_name, source = sources[source_sha]
        save(source_name,source)
        parent = report.get('parent_checkpoint_sha256')
        # Independent continuations are not fresh nominal trials.
        if parent:
            assert parent in checkpoint_hashes
            start_step = checkpoint_hashes[parent]['steps_completed']
        else:
            assert report_file.name == 'report.json'
            start_step = 0
        name = directory+'-'+report_file.stem+'.json.gz'
        packed(name,raw)
        frames = report['frames']
        assert all(b['seq'] > a['seq'] and b['frame']['time_s'] > a['frame']['time_s']
                   for a,b in zip(frames,frames[1:])),name
        state, observation = report['state'],report['measurements']
        assert not state['success'] and state['status']=='failed',name
        assert report['equality_constraints']==0 and report['mocap_bodies']==0
        index['trials'].append({
            'name':directory+'/'+report_file.stem, 'kind':'continuation' if parent else 'fresh',
            'report_file':name, 'report_sha256':sha(raw),
            'research_source_file':source_name, 'research_source_sha256':source_sha,
            'runtime_sources_file':directory+'-runtime-sources.json.gz',
            'checkpoint_archive':directory+'-checkpoints.json.gz',
            'parent_checkpoint_sha256':parent, 'model_sha256':model_sha,
            'status':state['status'], 'success':state['success'],
            'failure':state['failure'], 'failure_detail':state.get('failure_detail'),
            'steps_completed':state['steps_completed'],
            'steps_executed_in_this_trial':state['steps_completed']-start_step,
            'simulator_time_s':observation['time_s'], 'wall_s':report['wall_s'],
            'planning_s':report.get('planning_s'),
            'door_angle_rad':observation['door_angle_rad'],
            'grip_forces_n':observation['grip_forces_n'],
            'root_tilt_rad':observation['root_tilt_rad'],
            'recorded_frames':len(frames),
            'full_cabinet_service':False,
            'equality_constraints':0, 'mocap_bodies':0})

save('archive_source.py', Path(__file__).read_bytes())
(dest/'index.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({'trials':len(index['trials']),
    'fresh':sum(t['kind']=='fresh' for t in index['trials']),
    'all_failed':all(not t['success'] for t in index['trials']),
    'steps_executed':sum(t['steps_executed_in_this_trial'] for t in index['trials']),
    'bytes':sum(p.stat().st_size for p in dest.iterdir())}))
