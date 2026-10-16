import numpy as np

from vivacity.pickup_planning import joint_route, stage_commands, stage_distance


def test_seeded_rrt_routes_around_a_blocked_joint_region():
    start=np.zeros(7); goal=np.zeros(7); goal[0]=1
    limits=np.tile([-.8,1.2],(7,1))
    valid=lambda q: np.linalg.norm(q[:2]-[.5,0])>.2
    route=joint_route(start,goal,limits,valid,np.random.default_rng(7),1000)
    assert route is not None and len(route)>2
    for a,b in zip(route[:-1],route[1:]):
        assert all(valid(a+(b-a)*t) for t in np.linspace(0,1,100))
    repeat=joint_route(start,goal,limits,valid,np.random.default_rng(7),1000)
    assert np.array_equal(route,repeat)


def test_stage_commands_follow_routed_waypoints_and_preserve_endpoints():
    start=np.zeros(7); bend=np.zeros(7); bend[1]=.4
    goal=np.zeros(7); goal[0]=.8
    stage={'start':start.tolist(),'goal':goal.tolist(),'waypoints':[start.tolist(),bend.tolist(),goal.tolist()]}
    fractions=np.linspace(0,1,301)
    commands=stage_commands(stage,fractions)
    assert np.isclose(stage_distance(stage),1.2)
    assert np.allclose(commands[0],start) and np.allclose(commands[-1],goal)
    assert np.allclose(commands[100],bend)
    assert np.isfinite(commands).all()
