"""Research-only comparison of a second QP solver on the same G1 task.

Optional development dependency: clarabel==0.11.1. This script never changes the
production controller selection or substitutes a successful animation. The report
explicitly records the runtime solver override and preserves physical failures.
"""
import hashlib
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import clarabel
import numpy as np
from scipy import sparse

from vivacity import inverse_dynamics
from vivacity.bimanual import BimanualConfig, run_bimanual
from vivacity.contact_evidence import descendants

CURRENT = {}


class ClarabelQP:
    def setup(self, *, P, q, A, l, u, **_):
        if CURRENT.get('grip_load_n',0):
            model, data = CURRENT['model'], CURRENT['data']
            contacts = [c for c in data.contact[:data.ncon] if c.dist<=.001 and c.efc_address>=0]
            parcel = model.body('parcel').id
            matrix = P.toarray()
            q = q.copy()
            for side in ('left','right'):
                group = descendants(model,f'{side}_wrist_yaw_link')
                indices = [i for i,c in enumerate(contacts)
                           if parcel in (model.geom_bodyid[c.geom1],model.geom_bodyid[c.geom2])
                           and (model.geom_bodyid[c.geom1] in group or model.geom_bodyid[c.geom2] in group)]
                for i in indices:
                    index = model.nv+model.nu+i*3
                    matrix[index,index] += .2
                    q[index] -= .2*CURRENT['grip_load_n']/len(indices)
            P = sparse.csc_matrix(matrix)
        A = A.toarray()
        equality = np.isfinite(l) & np.isfinite(u) & (l == u)
        lo, hi = ~equality & np.isfinite(l), ~equality & np.isfinite(u)
        constraint = sparse.csc_matrix(np.vstack([A[equality], -A[lo], A[hi]]))
        rhs = np.r_[l[equality], -l[lo], u[hi]]
        settings = clarabel.DefaultSettings()
        settings.verbose = False
        settings.max_iter = 150
        settings.time_limit = .25
        self.solver = clarabel.DefaultSolver(sparse.triu(P).tocsc(), q, constraint, rhs,
            [clarabel.ZeroConeT(int(equality.sum())), clarabel.NonnegativeConeT(int(lo.sum()+hi.sum()))], settings)

    def solve(self, **_):
        solution = self.solver.solve()
        valid = str(solution.status) in ('Solved','AlmostSolved')
        return SimpleNamespace(x=np.asarray(solution.x), info=SimpleNamespace(
            status='clarabel:'+str(solution.status), status_val=1 if valid else 7,
            prim_res=float(solution.r_prim), dual_res=float(solution.r_dual)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--grip-load-n',type=float,default=0.)
    parser.add_argument('--torque-weight',type=float,default=.01)
    args=parser.parse_args()
    if not 0<=args.grip_load_n<=40:parser.error('Research grip load must lie in [0,40] N per hand')
    if not .0001<=args.torque_weight<=10:parser.error('Research torque objective weight must lie in [.0001,10]')
    original = inverse_dynamics.osqp.OSQP
    original_compute = inverse_dynamics.ConstrainedInverseDynamics.compute
    def compute(controller,data,*arguments,**kwargs):
        CURRENT.update(model=controller.model,data=data,grip_load_n=args.grip_load_n)
        kwargs['torque_weight'] = args.torque_weight
        return original_compute(controller,data,*arguments,**kwargs)
    try:
        inverse_dynamics.osqp.OSQP = ClarabelQP
        inverse_dynamics.ConstrainedInverseDynamics.compute = compute
        result = run_bimanual(BimanualConfig(controller='inverse_dynamics_experimental'))
        result['research_override'] = {'solver':'clarabel','version':clarabel.__version__, 'requested_normal_load_per_hand_n':args.grip_load_n,
            'torque_objective_weight':args.torque_weight,
            'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Research comparison; production controller implementation unchanged.'}
        target=Path(f'artifacts/physical-truth-runtime/g1-clarabel-load-{args.grip_load_n:g}-torque-{args.torque_weight:g}-research.json')
        target.write_text(json.dumps(result,allow_nan=False),encoding='utf8')
        print(json.dumps({k:result[k] for k in ('status','task_success','failure_reason','compute_wall_s','research_override')}),flush=True)
        print(result['measurements'].get('controller_error'),flush=True)
    finally:
        inverse_dynamics.osqp.OSQP = original
        inverse_dynamics.ConstrainedInverseDynamics.compute = original_compute


if __name__=='__main__':main()
