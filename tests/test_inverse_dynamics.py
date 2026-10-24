import mujoco as mj
import numpy as np
import pytest

from vivacity.inverse_dynamics import ConstrainedInverseDynamics, ControllerInfeasible


def pendulum(limit=10.):
    model = mj.MjModel.from_xml_string(f'''<mujoco><option timestep=".001"/>
    <worldbody><body pos="0 0 1"><joint name="hinge" axis="0 1 0" range="-70 70"/>
    <geom type="capsule" fromto="0 0 0 .5 0 0" size=".025" mass="1"/>
    </body></worldbody><actuator><motor joint="hinge" ctrlrange="-{limit} {limit}"/>
    </actuator></mujoco>''')
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    return model, data


def test_inverse_dynamics_holds_pendulum_through_actuator_torque():
    model, data = pendulum()
    controller = ConstrainedInverseDynamics(model)
    initial = data.qpos.copy()
    for _ in range(300):
        solution = controller.compute(data, initial)
        assert solution.residual < .001
        assert np.max(np.abs(solution.commands)) <= 10.001
        data.ctrl[:] = solution.commands
        mj.mj_step(model, data)
        mj.mj_forward(model, data)
    assert abs(data.qpos[0]) < .001
    assert abs(data.ctrl[0]) == pytest.approx(9.81*.25, rel=.02)
    state = controller.snapshot()
    restored = ConstrainedInverseDynamics(model)
    restored.restore(state)
    assert restored.snapshot() == state
    np.testing.assert_array_equal(controller.compute(data, initial).commands,
                                  restored.compute(data, initial).commands)


def test_insufficient_torque_does_not_invent_support():
    model, data = pendulum(.1)
    controller = ConstrainedInverseDynamics(model)
    initial = data.qpos.copy()
    for _ in range(300):
        try:
            solution = controller.compute(data, initial)
        except ControllerInfeasible:
            # The predictive joint-stop constraint cannot be met by an
            # overloaded actuator. Stopping is a valid, explicit failure.
            break
        assert abs(solution.commands[0]) <= .1001
        data.ctrl[:] = solution.commands
        mj.mj_step(model, data)
        mj.mj_forward(model, data)
    assert abs(data.qpos[0]) > .1
