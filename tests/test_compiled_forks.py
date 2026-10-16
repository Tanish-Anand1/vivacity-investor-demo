import gc
import weakref

import mujoco as mj
import pytest

from vivacity.cloth import ClothBackend
from vivacity.pick_place import PickPlaceBackend
from vivacity.robotics import RoboticsBackend
from vivacity.schemas import ClothConfig, RoboticsConfig


@pytest.mark.parametrize('kind', ['reach', 'pick_place', 'cloth'])
def test_forks_share_only_immutable_geometry_and_release_templates(kind, monkeypatch):
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS', '1')
    backend = {'reach': RoboticsBackend, 'pick_place': PickPlaceBackend,
               'cloth': ClothBackend}[kind]()
    config = ClothConfig() if kind == 'cloth' else RoboticsConfig(task=kind)
    parent = backend.create_world(config.model_dump(), 7)
    saved = backend.snapshot(parent)
    child = backend.fork(saved)
    sibling = backend.fork(saved)
    # Compiling every branch duplicated the large Panda mesh allocations.
    assert parent.model is child.model is sibling.model
    assert child.data is not parent.data and child.data is not sibling.data
    child.data.ctrl[0] += .1
    for _ in range(5):
        mj.mj_step(child.model, child.data)
    child.config['test_only'] = True
    assert backend.snapshot(parent) == saved == backend.snapshot(sibling)
    parent.data.ctrl[0] += .2
    for _ in range(5):
        mj.mj_step(parent.model, parent.data)
    fresh = backend.create_world(config.model_dump(), 11)
    assert fresh.model is parent.model and fresh.data is not parent.data
    assert backend.snapshot(fresh)['integration_state'] == saved['integration_state']
    assert fresh.seed == 11
    reference = weakref.ref(parent)
    del parent
    gc.collect()
    assert reference() is None
    # The weak template can disappear while a child still owns its model.
    restored = backend.fork(saved)
    assert backend.snapshot(restored) == saved
