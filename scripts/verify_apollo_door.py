"""Run a real, explicitly incomplete Apollo cabinet door primitive."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from vivacity.apollo_door import CabinetDoorPrimitive
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
    args=parser.parse_args()
    started=time.perf_counter()
    task=CabinetDoorPrimitive(CabinetConfig(front_x_m=args.front_x,latch_stiffness_n_m=args.latch_stiffness),
        ParallelGripperConfig(finger_force_n=args.finger_force,
            position_stiffness_n_m=args.finger_stiffness),opening_angle_rad=args.opening_angle)
    frames=[]
    previous=None
    while task.state['status']=='running' and task.data.time<55.:
        task.step()
        if task.state['steps_completed']%50==0 or task.state['phase']!=previous:
            frame=task.frame()
            frames.append({'seq':frame['seq'],**frame['frame'],'phase':frame['phase'],
                'ctrl':task.data.ctrl.tolist(),'measurements':frame['measurements']})
        if task.state['phase']!=previous:
            print(json.dumps({'phase':task.state['phase'],'time':float(task.data.time)}),flush=True)
            previous=task.state['phase']
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
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # Revisions of the controller often share an identical compiled model.
    # Store that large mesh artifact once, without losing report provenance.
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
    report['model_file']=model_path.relative_to(args.output.parent).as_posix()
    report['compiled_model_sha256']=task.artifact.sha256
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('frames','state','controller_checkpoint')}))
    print(json.dumps({k:task.state[k] for k in ('status','success','failure','phase','steps_completed')}))
    raise SystemExit(0 if task.state['success'] else 1)


if __name__=='__main__':
    main()
