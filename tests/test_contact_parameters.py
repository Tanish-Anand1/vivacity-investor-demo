import ast
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from vivacity.bimanual import BimanualConfig, compile_scene
from vivacity.contact_parameters import TASK_PARAMETERS, contact_parameter_manifest


def test_every_public_task_parameter_has_dependency_schema_and_executable_test_reference():
    assert set(TASK_PARAMETERS) == set(BimanualConfig.model_fields)
    manifest = contact_parameter_manifest()
    root = Path(__file__).parents[1]
    for definition in manifest['parameters'].values():
        assert definition['dependency'] and definition['schema'] and definition['requires_rebuild']
        path, function = definition['test'].split('::')
        names = {n.name for n in ast.parse((root/path).read_text()).body if isinstance(n, ast.FunctionDef)}
        assert function in names, (path, function)
    for field in ('source_xy_m','destination_xy_m'):
        for axis, bounds in enumerate(manifest['parameters'][field]['axes']):
            value = list(getattr(BimanualConfig(), field))
            value[axis] = bounds['minimum']-.001
            with pytest.raises(ValidationError):
                BimanualConfig(**{field:value})
            value[axis] = bounds['maximum']+.001
            with pytest.raises(ValidationError):
                BimanualConfig(**{field:value})


def test_effective_native_parameters_match_manifest_dependencies():
    baseline = compile_scene(BimanualConfig())
    from vivacity.bimanual import BimanualTask
    task = BimanualTask(BimanualConfig(source_xy_m=(.34,.02),floor_friction=.3,
                                     gravity_m_s2=4.,hand_torque_scale=.2))
    changed = task.model
    np.testing.assert_allclose(changed.opt.gravity,[0,0,-4.])
    assert changed.geom('floor').friction[0] == pytest.approx(.3)
    np.testing.assert_allclose(task.data.body('parcel').xpos[:2],[.34,.02])
    affected = []
    for joint in range(changed.njnt):
        if not np.array_equal(changed.jnt_actfrcrange[joint],baseline.jnt_actfrcrange[joint]):
            affected.append(joint)
            np.testing.assert_allclose(changed.jnt_actfrcrange[joint],.2*baseline.jnt_actfrcrange[joint])
    assert len(affected) >= 10


def test_destination_seed_and_budget_remain_explicit_task_configuration():
    # These fields control task logic or reproducibility, not fictional native
    # MuJoCo model properties. Check actual consumers as well as validation.
    config = BimanualConfig(destination_xy_m=(.42,.02),seed=29,timeout_s=8.,disturbance_n=50.)
    from vivacity.bimanual import BimanualTask
    task = BimanualTask(config)
    snapshot = task.snapshot().checkpoint
    assert snapshot.task_state['config']['destination_xy_m'] == (.42,.02)
    assert snapshot.task_state['config']['timeout_s'] == 8.
    assert snapshot.task_state['config']['disturbance_n'] == 50.
    assert snapshot.random_state == np.random.default_rng(29).bit_generator.state
    # Initial positions are independent of the placement goal; changing that
    # goal cannot teleport the object at initialization.
    np.testing.assert_allclose(task.data.body('parcel').xpos[:2],[.32,0.])
