"""The low-memory production loader must preserve MuJoCo model behavior."""

import hashlib
import json

import mujoco as mj
import numpy as np
import pytest

from vivacity.humanoids import (
    _compiled_xml_model, _verified_binary_path, compiled_model, configured_digest,
)


def test_precompiled_g1_matches_source_and_supports_parameter_edits(tmp_path, monkeypatch):
    source, digest = _compiled_xml_model('unitree_g1', .8, .5)
    binary = tmp_path / 'unitree_g1.mjb'
    mj.mj_saveModel(source, str(binary))
    with binary.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = tmp_path / 'unitree_g1.json'
    record = {'simulator_version': mj.__version__, 'model_hash': digest,
              'binary_sha256': checksum}
    manifest.write_text(json.dumps(record), encoding='utf-8')

    monkeypatch.setenv('VIVACITY_HUMANOID_MODEL_DIR', str(tmp_path))
    loaded, loaded_digest = compiled_model('unitree_g1')
    assert loaded_digest == configured_digest('unitree_g1') == digest
    assert loaded.nq == source.nq and loaded.nv == source.nv
    assert loaded.nu == source.nu and loaded.ngeom == source.ngeom
    assert np.array_equal(loaded.body_mass, source.body_mass)
    assert np.array_equal(loaded.geom_friction, source.geom_friction)

    varied, varied_digest = compiled_model('unitree_g1', .4, 1.2)
    assert varied_digest != loaded_digest
    assert varied.body_mass[varied.body('parcel').id] == pytest.approx(1.2)
    assert varied.geom_friction[varied.geom('floor').id, 0] == pytest.approx(.4)
    assert loaded.body_mass[loaded.body('parcel').id] == pytest.approx(.5)
    assert loaded.geom_friction[loaded.geom('floor').id, 0] == pytest.approx(.8)

    record['simulator_version'] = 'mismatched-version'
    manifest.write_text(json.dumps(record), encoding='utf-8')
    _verified_binary_path.cache_clear()
    with pytest.raises(RuntimeError, match='does not match source'):
        compiled_model('unitree_g1')
    _verified_binary_path.cache_clear()
