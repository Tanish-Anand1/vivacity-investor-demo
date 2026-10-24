"""Run a real, explicitly incomplete Apollo cabinet door primitive."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from vivacity.apollo_door import CabinetDoorPrimitive, SOURCE_HASHES
from vivacity.cabinet_mechanism import CabinetConfig
from vivacity.simulated_tooling import ParallelGripperConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--front-x',type=float,default=.75)
    parser.add_argument('--finger-force',type=float,default=40.)
    parser.add_argument('--finger-stiffness',type=float,default=800.)
    parser.add_argument('--latch-stiffness',type=float,default=300.)
    parser.add_argument('--opening-angle',type=float,default=.25)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checkpoints',action='store_true',
        help='Persist full integration/controller checkpoints at each measured phase transition and at termination.')
    args=parser.parse_args()
    # Retain exact uncommitted research source alongside failed trials too.
    # A hash without retrievable source cannot reproduce a development run.
    source_digest=hashlib.sha256(json.dumps(SOURCE_HASHES,sort_keys=True).encode()).hexdigest()
    source_dir=args.output.parent/'sources'/source_digest
    source_dir.mkdir(parents=True,exist_ok=True)
    for name,expected in SOURCE_HASHES.items():
        content=(Path(__file__).resolve().parents[1]/'vivacity'/name).read_bytes()
        if hashlib.sha256(content).hexdigest()!=expected:
            raise ValueError('source changed while constructing experiment provenance')
        (source_dir/name).write_bytes(content)
    started=time.perf_counter()
    task=CabinetDoorPrimitive(CabinetConfig(front_x_m=args.front_x,latch_stiffness_n_m=args.latch_stiffness),
        ParallelGripperConfig(finger_force_n=args.finger_force,
            position_stiffness_n_m=args.finger_stiffness),opening_angle_rad=args.opening_angle)
    # A checkpoint refers to this immutable compiled model. Persist it before
    # stepping so an interrupted diagnostic retains a usable initial state.
    model_path=args.output.parent/'models'/f'{task.artifact.sha256}.mjb'
    model_path.parent.mkdir(parents=True,exist_ok=True)
    if model_path.exists():
        with model_path.open('rb') as handle:
            existing=hashlib.file_digest(handle,'sha256').hexdigest()
        if existing!=task.artifact.sha256:
            raise ValueError('existing compiled-model artifact is corrupt')
    else:
        temporary=model_path.with_suffix('.mjb.tmp')
        temporary.write_bytes(task.artifact.binary)
        temporary.replace(model_path)
    checkpoints=[]

    def checkpoint(label):
        if not args.checkpoints:
            return
        bundle=task.snapshot()
        target=args.output.parent/'checkpoints'/f'{task.state["steps_completed"]:07d}-{label}.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        content=(bundle.checkpoint.model_dump_json()+'\n').encode()
        temporary=target.with_suffix('.json.tmp')
        temporary.write_bytes(content)
        temporary.replace(target)
        checkpoints.append({'file':target.relative_to(args.output.parent).as_posix(),
            'sha256':hashlib.sha256(content).hexdigest(),'model_sha256':task.artifact.sha256,
            'steps_completed':bundle.checkpoint.steps_completed,
            'next_frame_seq':bundle.checkpoint.next_frame_seq,'phase':task.state['phase']})

    checkpoint('initial')
    frames=[]
    previous=None
    next_log_s=1.
    while task.state['status']=='running' and task.data.time<90.:
        task.step()
        if task.state['steps_completed']%50==0 or task.state['phase']!=previous:
            frame=task.frame()
            frames.append({'seq':frame['seq'],**frame['frame'],'phase':frame['phase'],
                'ctrl':task.data.ctrl.tolist(),'measurements':frame['measurements']})
        if task.state['phase']!=previous:
            checkpoint(task.state['phase'])
            print(json.dumps({'phase':task.state['phase'],'time':float(task.data.time)}),flush=True)
            previous=task.state['phase']
        if task.data.time>=next_log_s:
            measured=task.observe()
            print(json.dumps({'kind':'measured_progress','phase':task.state['phase'],
                'steps':task.state['steps_completed'],'time_s':float(task.data.time),
                'door_angle_rad':measured['door_angle_rad'],
                'latch_retraction_m':measured['latch_retraction_m'],
                'grip_forces_n':measured['grip_forces_n'],
                'pose_errors':measured['pose_errors']}),flush=True)
            next_log_s+=1.
    if task.state['status']=='running':
        task.fail('overall_timeout')
    if not frames or frames[-1]['time_s']<float(task.data.time):
        frame=task.frame()
        frames.append({'seq':frame['seq'],**frame['frame'],'phase':frame['phase'],
            'ctrl':task.data.ctrl.tolist(),'measurements':frame['measurements']})
    report={'schema_version':'vivacity.apollo-door-development/1','state':task.state,
        'controller_checkpoint':task.controller.snapshot(),
        'measurements':task.observe(),'frames':frames,'compute_s':time.perf_counter()-started,
        'equality_constraints':int(task.model.neq),'mocap_bodies':int(task.model.nmocap),
        'scope':'Stationary contact-operated latch and requested door opening primitive. Not complete cabinet service.'}
    checkpoint('terminal')
    report['checkpoints']=checkpoints
    report['verifier_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report['model_file']=model_path.relative_to(args.output.parent).as_posix()
    report['source_directory']=source_dir.relative_to(args.output.parent).as_posix()
    report['compiled_model_sha256']=task.artifact.sha256
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('frames','state','controller_checkpoint')}))
    print(json.dumps({k:task.state[k] for k in ('status','success','failure','phase','steps_completed')}))
    raise SystemExit(0 if task.state['success'] else 1)


if __name__=='__main__':
    main()
