"""Run a real, explicitly incomplete Apollo cabinet door primitive."""
import argparse
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
    parser.add_argument('--latch-stiffness',type=float,default=300.)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    started=time.perf_counter()
    task=CabinetDoorPrimitive(CabinetConfig(front_x_m=args.front_x,latch_stiffness_n_m=args.latch_stiffness),
        ParallelGripperConfig(finger_force_n=args.finger_force))
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
    report={'schema_version':'vivacity.apollo-door-development/1','state':task.state,
        'measurements':task.observe(),'frames':frames,'compute_s':time.perf_counter()-started,
        'equality_constraints':int(task.model.neq),'mocap_bodies':int(task.model.nmocap),
        'scope':'Stationary contact-operated latch and partial door opening primitive. Not complete cabinet service.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    model_path=args.output.with_suffix('.mjb')
    model_path.write_bytes(task.artifact.binary)
    report['model_file']=model_path.name
    report['compiled_model_sha256']=task.artifact.sha256
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('frames','state')}))
    print(json.dumps({k:task.state[k] for k in ('status','success','failure','phase','steps_completed')}))
    raise SystemExit(0 if task.state['success'] else 1)


if __name__=='__main__':
    main()
