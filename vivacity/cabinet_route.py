"""Seeded collision-aware free-space approach on independent planning data.

This certifies sampled kinematic clearance only. The native execution still
checks contacts, forces and stability; object manipulation is not routed here.
"""
import mujoco as mj
import numpy as np

from .pickup_planning import joint_route


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
        full=np.asarray(goal_qpos).copy()
        full[qadr]=point
        waypoints.append(full.tolist())
    return {'waypoints':waypoints,'collision_checks':checks,
            'feasible':route is not None,'planner':'seeded_rrt_connect',
            'clearance_m':.03,'edge_resolution':.005,'iteration_budget':iterations}
