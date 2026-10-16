"""Bounded hierarchical search. Screening is kinematic, never a physics success claim."""
from copy import deepcopy
import hashlib
import time
import mujoco as mj
import numpy as np
from .robotics import RobotWorld


def search_reaches(backend, world, settings, emit):
    tic=time.perf_counter()
    total=settings['search_candidates']
    budget=settings['physics_budget']
    emit({'stage':'planning','message':'Computing seed paths with pose IK and collision-aware RRT.'})
    seeds,_=backend.candidates(world,5,settings['planner_iterations'])
    bases=[a for a in seeds if a['planning_feasible'] and a['waypoints']]
    if not bases:
        # Jittering an unusable seed thousands of times cannot repair failed IK
        # or an initially colliding world. Preserve one honest diagnostic rollout.
        reason = 'ik_failure' if not seeds[0]['ik']['converged'] else 'no_collision_free_seed_path'
        summary = {'generated':0,'distinct_generated':0,'screened':0,'rejected':0,
                   'screening_passed':0,'promoted_to_physics':1,'diagnostic_rollouts':1,
                   'rejection_reasons':{},'seed_failure':reason,'seed_ik':seeds[0]['ik'],
                   'sampling':'bulk generation skipped because no usable seed path exists',
                   'screening_scope':'seed IK and collision-aware planning; diagnostic physics may execute zero steps',
                   'ranking_objective':'successful execution first, then measured duration, joint path length and goal error'}
        emit(summary | {'stage':'screening_complete','message':f'No usable seed path: {reason}. Bulk sampling skipped; running one diagnostic.'})
        return [seeds[0]],time.perf_counter()-tic,summary
    rng=np.random.default_rng(world.seed)
    scratch=RobotWorld(world.model,mj.MjData(world.model),world.config,world.seed,world.model_hash)
    scratch.data.qpos[:]=world.data.qpos
    proposals=[];distinct=set();catalog_digest=hashlib.sha256()
    # Every variant changes one interior joint vector; continuous independent jitter
    # makes each path distinct. Endpoints and the persisted parent remain fixed.
    for i in range(total):
        template=deepcopy(bases[i%len(bases)] if bases else seeds[0])
        path=np.asarray(template['waypoints'],dtype=float)
        if len(path)==2:
            path=np.vstack([path[0],(path[0]+path[1])/2,path[1]])
        node=int(rng.integers(1,len(path)-1))
        path[node]+=rng.normal(0,rng.uniform(.002,.08),7)
        template.update(planner='hierarchical_rrt_variant',candidate_index=i,waypoints=path.tolist())
        fingerprint=hashlib.sha256(path.astype('<f8').tobytes()).digest()
        distinct.add(fingerprint);catalog_digest.update(fingerprint)
        proposals.append((template,node))
        if (i+1)%1000==0 or i+1==total:
            emit({'stage':'generation','generated':i+1,'target':total,'elapsed_seconds':time.perf_counter()-tic,'message':f'Generated {i+1:,} / {total:,} distinct joint-space trajectories.'})
    eligible=[];rejections={'joint_limit':0,'kinematic_collision':0,'no_feasible_seed_path':0}
    limits=world.model.jnt_range[:7]
    for i,(action,node) in enumerate(proposals):
        path=np.asarray(action['waypoints'])
        if np.any(path<limits[:,0]) or np.any(path>limits[:,1]):
            rejections['joint_limit']+=1
        else:
            scratch.data.qpos[:7]=path[node]
            mj.mj_forward(scratch.model,scratch.data)
            if backend.contacts(scratch):
                rejections['kinematic_collision']+=1
            elif not bases:
                rejections['no_feasible_seed_path']+=1
            else:
                proxy=float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum())
                action['screening']={'checks':['joint_limits','MuJoCo forward-kinematics contact at changed waypoint','collision-aware seed path'],'path_length_proxy_rad':proxy,'full_path_collision_proof':False}
                eligible.append((proxy,action['candidate_index'],action))
        if (i+1)%1000==0 or i+1==total:
            emit({'stage':'screening','generated':total,'screened':i+1,'rejected':sum(rejections.values()),'elapsed_seconds':time.perf_counter()-tic,'message':f'Screened {i+1:,} / {total:,}; {sum(rejections.values()):,} rejected by measured kinematic constraints.'})
    eligible.sort(key=lambda item:(item[0],item[1]))
    # Keep a diagnostic direct rollout so actual failures remain inspectable.
    actions=[seeds[0]]+[item[2] for item in eligible[:max(0,budget-1)]]
    summary={'generated':total,'distinct_generated':len(distinct),'candidate_catalog_sha256':catalog_digest.hexdigest(),'screened':total,'rejected':sum(rejections.values()),'screening_passed':len(eligible),'promoted_to_physics':len(actions),'diagnostic_rollouts':1,'rejection_reasons':rejections,'sampling':'seeded Gaussian perturbations of interior waypoints on dynamically unverified RRT paths','screening_scope':'joint limits and actual kinematic contacts; full-path/dynamic feasibility decided only by rollouts','ranking_objective':'successful execution first, then measured duration, joint path length, goal error, candidate index'}
    emit(summary|{'stage':'screening_complete','elapsed_seconds':time.perf_counter()-tic,'message':f'Screening complete. {len(eligible):,} passed cheap checks; {len(actions)} promoted to real physics (including one diagnostic).'} )
    return actions,time.perf_counter()-tic,summary
