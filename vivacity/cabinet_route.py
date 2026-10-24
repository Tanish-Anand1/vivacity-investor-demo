"""Seeded collision-aware free-space approach on independent planning data.

This certifies sampled kinematic clearance only. The native execution still
checks contacts, forces and stability; object manipulation is not routed here.
"""
import mujoco as mj
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .pickup_planning import joint_route


def route_tool_to_posture(model, initial_qpos, goal_qpos, joint_names, tool_geoms,
                          fixture_geoms, rng, *, opening_joints=(), mechanism_sweep=None,
                          clearance_m=.01, iterations=600):
    """Find a native-geometry-checked arm route, preserving the holding arm.

    Finger bounds keep an already released grasp open. The final posture is
    checked against the next mechanism motion before the route is accepted.
    All computations use private planning data; there is no physics success
    claim until the actuator-driven task executes the route.
    """
    initial,goal=np.asarray(initial_qpos,dtype=float),np.asarray(goal_qpos,dtype=float)
    joints=np.asarray([model.joint(name).id for name in joint_names],dtype=int)
    if (initial.shape!=(model.nq,) or goal.shape!=(model.nq,) or
            not np.isfinite(initial).all() or not np.isfinite(goal).all() or
            not len(joints) or len(set(joints))!=len(joints) or not np.all(model.jnt_limited[joints]) or
            not np.isin(model.jnt_type[joints],[int(mj.mjtJoint.mjJNT_SLIDE),int(mj.mjtJoint.mjJNT_HINGE)]).all() or
            not np.isfinite(clearance_m) or not 0<clearance_m<=.05 or
            type(iterations) is not int or not 0<=iterations<=1500):
        raise ValueError('bounded posture route inputs required')
    qadr=model.jnt_qposadr[joints]
    limits=model.jnt_range[joints].copy()
    for name in opening_joints:
        index=joint_names.index(name)
        if int(model.jnt_type[joints[index]])!=int(mj.mjtJoint.mjJNT_SLIDE):
            raise ValueError('opening joint must be a selected slide')
        limits[index,0]=max(limits[index,0],min(initial[qadr[index]],goal[qadr[index]])-.001)
        limits[index,1]=min(limits[index,1],max(initial[qadr[index]],goal[qadr[index]])+.02)
    pairs=np.array([(a,b) for a in tool_geoms for b in fixture_geoms],dtype=int).reshape(-1,2)
    if not len(pairs) or np.any(pairs<0) or np.any(pairs>=model.ngeom):
        raise ValueError('valid explicit collision geometry required')
    scratch=mj.MjData(model)
    scratch.qpos[:]=initial
    bounds_squared=(model.geom_rbound[pairs[:,0]]+model.geom_rbound[pairs[:,1]]+clearance_m)**2
    checks=0

    def clear():
        nonlocal checks
        checks+=1
        mj.mj_kinematics(model,scratch)
        delta=scratch.geom_xpos[pairs[:,0]]-scratch.geom_xpos[pairs[:,1]]
        for index in np.flatnonzero(np.sum(delta*delta,axis=1)<=bounds_squared):
            a,b=pairs[index]
            if mj.mj_geomDistance(model,scratch,a,b,clearance_m+.01,None)<clearance_m:
                return False
        return True

    def valid(values):
        if np.any(values<limits[:,0]) or np.any(values>limits[:,1]):
            return False
        scratch.qpos[:]=initial
        scratch.qpos[qadr]=values
        return clear()

    sweep_samples=0
    if mechanism_sweep is not None:
        name,target=mechanism_sweep
        joint=model.joint(name)
        if (int(joint.type[0]) not in (int(mj.mjtJoint.mjJNT_HINGE),int(mj.mjtJoint.mjJNT_SLIDE)) or
                not joint.limited[0] or not np.isfinite(target) or not joint.range[0]<=target<=joint.range[1]
                or joint.id in joints):
            raise ValueError('bounded independent mechanism sweep required')
        address=int(joint.qposadr[0])
        angles=np.linspace(initial[address],target,max(2,int(np.ceil(abs(target-initial[address])/.01))+1))
        for angle in angles:
            scratch.qpos[:]=initial
            scratch.qpos[qadr]=goal[qadr]
            scratch.qpos[address]=angle
            sweep_samples+=1
            if not clear():
                return {'feasible':False,'waypoints':[],'collision_checks':checks,
                    'failure':'parked_posture_intersects_mechanism','sweep_samples':sweep_samples}
    route=_connect_route(initial[qadr],goal[qadr],limits,valid,rng,iterations)
    waypoints=[]
    for values in route or ():
        qpos=initial.copy()
        qpos[qadr]=values
        waypoints.append(qpos.tolist())
    return {'feasible':route is not None,'waypoints':waypoints,'collision_checks':checks,
            'planner':'seeded_rrt_connect','clearance_m':clearance_m,'edge_resolution':.005,
            'iteration_budget':iterations,'joint_names':list(joint_names),'sweep_samples':sweep_samples}


def plan_tool_clearance(model, initial_qpos, site_name, joint_names, finger_joints,
                        tool_geoms, fixture_geoms, grasp_pairs, target_positions, *,
                        opening_m=.04, minimum_clearance_m=.003, minimum_grasp_gap_m=.01,
                        mechanism_sweep=None):
    """Propose a bounded withdrawal with free wrist orientation on scratch data.

    A loaded grasp fixes orientation; withdrawal need not. Keeping the same
    wrist orientation can make a reachable free-space position appear
    unreachable. These proposals prioritize position, then small orientation
    and posture changes. Every edge is sampled against the actual native
    geometry. Intended grasp surfaces may touch while unloading, but cannot be
    penetrated more deeply than their initial compliance tolerance. Kinematic
    clearance is not physics success: the executing task still checks contacts.
    """
    initial=np.asarray(initial_qpos,dtype=float)
    targets=np.asarray(target_positions,dtype=float)
    joints=np.array([model.joint(name).id for name in joint_names],dtype=int)
    fingers=np.array([model.joint(name).id for name in finger_joints],dtype=int)
    if (initial.shape!=(model.nq,) or not np.isfinite(initial).all() or
            targets.ndim!=2 or targets.shape[1:]!=(3,) or not 1<=len(targets)<=64 or
            not np.isfinite(targets).all() or not len(joints) or
            len(set(joints))!=len(joints) or set(joints).intersection(fingers) or
            not np.isin(model.jnt_type[joints],[int(mj.mjtJoint.mjJNT_SLIDE),int(mj.mjtJoint.mjJNT_HINGE)]).all() or
            not np.all(model.jnt_limited[np.r_[joints,fingers]]) or
            not np.isfinite([opening_m,minimum_clearance_m,minimum_grasp_gap_m]).all() or
            not 0<=minimum_clearance_m<=.05 or not 0<minimum_grasp_gap_m<=.2 or
            np.any(opening_m<model.jnt_range[fingers,0]) or np.any(opening_m>model.jnt_range[fingers,1])):
        raise ValueError('bounded tool-clearance inputs required')
    pairs=list(dict.fromkeys((int(a),int(b)) for a in tool_geoms for b in fixture_geoms))
    intended=sorted(set(tuple(map(int,pair)) for pair in grasp_pairs))
    if not pairs or not intended or not set(intended).issubset(pairs):
        raise ValueError('explicit tool, fixture and intended grasp geometry required')
    if any(not 0<=i<model.ngeom for pair in pairs for i in pair):
        raise ValueError('invalid clearance geometry')
    forbidden=[pair for pair in pairs if pair not in intended]
    scratch=mj.MjData(model)
    scratch.qpos[:]=initial
    mj.mj_kinematics(model,scratch)
    rotation=scratch.site(site_name).xmat.reshape(3,3).copy()
    qadr,fadr=model.jnt_qposadr[joints],model.jnt_qposadr[fingers]
    low,high=model.jnt_range[joints,0]+.002,model.jnt_range[joints,1]-.002
    if np.any(low>=high):
        raise ValueError('planning joint range too narrow')
    sweep=None
    if mechanism_sweep is not None:
        name,target=mechanism_sweep
        joint=model.joint(name)
        if (int(joint.type[0]) not in (int(mj.mjtJoint.mjJNT_HINGE),int(mj.mjtJoint.mjJNT_SLIDE)) or
                not joint.limited[0] or not np.isfinite(target) or not joint.range[0]<=target<=joint.range[1] or
                joint.id in np.r_[joints,fingers]):
            raise ValueError('bounded independent mechanism sweep required')
        address=int(joint.qposadr[0])
        sweep=(address,np.linspace(initial[address],target,
            max(2,int(np.ceil(abs(target-initial[address])/.01))+1)))
    initial_grasp={pair:float(mj.mj_geomDistance(model,scratch,*pair,1.,None)) for pair in intended}
    checks=0
    proposals=[]
    rejected={key:0 for key in ('unreachable_target','prohibited_geometry',
                              'grasp_penetration','insufficient_separation','mechanism_sweep')}
    for target in targets:
        scratch.qpos[:]=initial

        def residual(values):
            scratch.qpos[qadr]=values
            mj.mj_kinematics(model,scratch)
            angular=Rotation.from_matrix(rotation @ scratch.site(site_name).xmat.reshape(3,3).T).as_rotvec()
            return np.r_[10.*(scratch.site(site_name).xpos-target),.08*angular,.005*(values-initial[qadr])]

        result=least_squares(residual,np.clip(initial[qadr],low,high),bounds=(low,high),
            max_nfev=100,ftol=1e-8,xtol=1e-8,gtol=1e-8)
        goal=initial.copy()
        goal[qadr]=result.x
        goal[fadr]=opening_m
        scratch.qpos[:]=goal
        mj.mj_kinematics(model,scratch)
        position=scratch.site(site_name).xpos.copy()
        orientation=scratch.site(site_name).xmat.reshape(3,3).copy()
        if np.linalg.norm(position-target)>.01:
            rejected['unreachable_target']+=1
            continue
        clearance=1.
        valid=True
        # Bound every checked joint increment, including the finger slides.
        samples=max(41,int(np.ceil(np.linalg.norm(goal[np.r_[qadr,fadr]]-
                initial[np.r_[qadr,fadr]])/.005))+1)
        for fraction in np.linspace(0.,1.,samples):
            scratch.qpos[:]=initial+(goal-initial)*fraction
            mj.mj_kinematics(model,scratch)
            for a,b in forbidden:
                if np.linalg.norm(scratch.geom_xpos[a]-scratch.geom_xpos[b]) > (
                        model.geom_rbound[a]+model.geom_rbound[b]+.05):
                    continue
                checks+=1
                distance=float(mj.mj_geomDistance(model,scratch,a,b,.05,None))
                clearance=min(clearance,distance)
                if distance<minimum_clearance_m:
                    valid=False
                    rejected['prohibited_geometry']+=1
                    break
            if not valid:
                break
            for pair in intended:
                checks+=1
                distance=float(mj.mj_geomDistance(model,scratch,*pair,1.,None))
                if distance<min(initial_grasp[pair],0.)-.001:
                    valid=False
                    rejected['grasp_penetration']+=1
                    break
            if not valid:
                break
        if not valid:
            continue
        gap=min(float(mj.mj_geomDistance(model,scratch,*pair,1.,None)) for pair in intended)
        if gap<minimum_grasp_gap_m:
            rejected['insufficient_separation']+=1
            continue
        swept_clearance=1.
        if sweep is not None:
            address,positions=sweep
            for position_value in positions:
                scratch.qpos[:]=goal
                scratch.qpos[address]=position_value
                mj.mj_kinematics(model,scratch)
                for a,b in pairs:
                    if np.linalg.norm(scratch.geom_xpos[a]-scratch.geom_xpos[b])>(
                            model.geom_rbound[a]+model.geom_rbound[b]+minimum_grasp_gap_m):
                        continue
                    checks+=1
                    distance=float(mj.mj_geomDistance(model,scratch,a,b,.5,None))
                    swept_clearance=min(swept_clearance,distance)
                    if distance<minimum_grasp_gap_m:
                        valid=False
                        break
                if not valid:
                    break
            if not valid:
                rejected['mechanism_sweep']+=1
                continue
        proposals.append({'qpos':goal.tolist(),'position':position.tolist(),
            'rotation':orientation.tolist(),'minimum_sampled_clearance_m':clearance,
            'final_grasp_gap_m':gap,'samples':samples,
            'sweep_samples':len(sweep[1]) if sweep is not None else 0,
            'swept_clearance_m':swept_clearance if sweep is not None else None,
            'joint_motion':float(np.linalg.norm(goal[qadr]-initial[qadr]))})
    selected=min(proposals,key=lambda value:value['joint_motion']) if proposals else None
    return {'feasible':selected is not None,'selected':selected,
        'planner':'bounded_orientation_relaxed_withdrawal','candidate_count':len(targets),
        'feasible_candidate_count':len(proposals),'collision_checks':checks,'rejections':rejected}


def _connect_route(start,goal,limits,valid,rng,iterations):
    """Bidirectional extension through densely checked joint-space edges."""
    def edge(a,b):
        return all(valid(a+(b-a)*t) for t in np.linspace(0.,1.,
            max(2,int(np.ceil(np.linalg.norm(b-a)/.005))+1)))
    if not valid(start) or not valid(goal):
        return None
    if edge(start,goal):
        return [start,goal]
    first,second=([start.copy()],[-1]),([goal.copy()],[-1])
    forward=True

    def extend(tree,target):
        nodes,parents=tree
        parent=int(np.argmin(np.linalg.norm(np.asarray(nodes)-target,axis=1)))
        delta=target-nodes[parent]
        distance=np.linalg.norm(delta)
        candidate=nodes[parent]+delta*min(1.,.25/max(distance,1e-12))
        if not edge(nodes[parent],candidate):
            return None,False
        nodes.append(candidate);parents.append(parent)
        return len(nodes)-1,distance<=.25

    def chain(tree,index):
        result=[]
        while index>=0:
            result.append(tree[0][index]);index=tree[1][index]
        return list(reversed(result))

    for _ in range(iterations):
        if rng.random()<.7:
            sample=start+rng.random()*(goal-start)+rng.normal(0.,.45,len(start))
            sample=np.clip(sample,limits[:,0]+.001,limits[:,1]-.001)
        else:
            sample=rng.uniform(limits[:,0]+.001,limits[:,1]-.001)
        index,_=extend(first,sample)
        if index is not None:
            for _ in range(80):
                other,reached=extend(second,first[0][index])
                if other is None:
                    break
                if reached:
                    a,b=chain(first,index),chain(second,other)
                    route=a+list(reversed(b))[1:]
                    if not forward:
                        route.reverse()
                    shortened=[route[0]]
                    i=0
                    while i<len(route)-1:
                        j=len(route)-1
                        while j>i+1 and not edge(route[i],route[j]):
                            j-=1
                        shortened.append(route[j]);i=j
                    return shortened
        first,second=second,first
        forward=not forward
    return None


def route_approach(model,initial_qpos,goal_qpos,joint_names,rng,*,iterations=1500,guides=()):
    joints=np.array([model.joint(name).id for name in joint_names],dtype=int)
    if (not len(joints) or len(set(joints))!=len(joints) or not np.all(model.jnt_limited[joints])
            or not np.isin(model.jnt_type[joints],[int(mj.mjtJoint.mjJNT_SLIDE),int(mj.mjtJoint.mjJNT_HINGE)]).all()):
        raise ValueError('approach route requires unique bounded joints')
    qadr=model.jnt_qposadr[joints]
    scratch=mj.MjData(model)
    scratch.qpos[:]=initial_qpos
    tools=[i for i in range(model.ngeom) if '_service_' in (model.geom(i).name or '')
           and (model.geom_contype[i] or model.geom_conaffinity[i])]
    fixtures=[i for i in range(model.ngeom) if (model.geom(i).name or '').startswith('service_')]
    pairs=[(tool,fixture) for tool in tools for fixture in fixtures]
    pair_indices=np.asarray(pairs,dtype=int).reshape(-1,2)
    bounds_squared=(model.geom_rbound[pair_indices[:,0]]+
                    model.geom_rbound[pair_indices[:,1]]+.03)**2
    checks=0

    def valid(values):
        nonlocal checks
        checks+=1
        scratch.qpos[qadr]=values
        mj.mj_kinematics(model,scratch)
        mj.mj_collision(model,scratch)
        for contact in scratch.contact[:scratch.ncon]:
            names=[model.geom(i).name or '' for i in (contact.geom1,contact.geom2)]
            robot=any(name.startswith('collision_') or '_service_' in name for name in names)
            fixture=any(name.startswith('service_') for name in names)
            if robot and fixture and contact.dist<.002:
                return False
        # Keep space for tracking error near the tools. Native broad-phase
        # contacts alone do not report positive clearance outside their margin.
        delta=scratch.geom_xpos[pair_indices[:,0]]-scratch.geom_xpos[pair_indices[:,1]]
        for index in np.flatnonzero(np.sum(delta*delta,axis=1)<=bounds_squared):
            tool,fixture=pairs[index]
            if mj.mj_geomDistance(model,scratch,tool,fixture,.03,None)<.03:
                return False
        return True

    start,goal=np.asarray(initial_qpos)[qadr],np.asarray(goal_qpos)[qadr]
    route=None
    # An IK guide is only a proposal: both segments receive the same clearance
    # sampling as a random route. No waypoint bypasses the collision checker.
    for full in guides:
        middle=np.asarray(full)[qadr]
        first=joint_route(start,middle,model.jnt_range[joints],valid,rng,0,edge_resolution=.005)
        second=joint_route(middle,goal,model.jnt_range[joints],valid,rng,0,edge_resolution=.005) if first else None
        if second:
            route=first[:-1]+second
            break
    if route is None:
        route=_connect_route(start,goal,model.jnt_range[joints],valid,rng,iterations)
    waypoints=[]
    for point in route or ():
        # Only the selected joints were collision checked. Preserve every
        # other coordinate, including passive fixtures and floating roots.
        full=np.asarray(initial_qpos).copy()
        full[qadr]=point
        waypoints.append(full.tolist())
    return {'waypoints':waypoints,'collision_checks':checks,
            'feasible':route is not None,'planner':'seeded_rrt_connect',
            'clearance_m':.03,'edge_resolution':.005,'iteration_budget':iterations}
