import pytest
import hashlib
import json
from pathlib import Path

from vivacity.hardware_transfer import DryRunCommandGate, JointEnvelope, validate_sensor_replay


def gate():
    return DryRunCommandGate(JointEnvelope(('joint',), (-1.,), (1.,), (2.,)), 'a'*64)


def test_explicit_dry_run_arming_and_watchdog_latches_without_sending_hardware_commands():
    controller = gate()
    assert controller.tick(0.)['reason'] == 'not_armed'
    with pytest.raises(ValueError):
        controller.arm(0., [0.], manifest_sha256='a'*64)
    with pytest.raises(ValueError):
        controller.arm(0., [0.], manifest_sha256='b'*64, operator_acknowledged=True)
    controller.arm(0., [0.], manifest_sha256='a'*64, operator_acknowledged=True)
    result = controller.accept(sequence=0, timestamp_s=.02, positions=[.01], now_s=.02)
    assert result['operation'] == 'validated_position_reference'
    assert result['hardware_command_sent'] is False
    assert controller.tick(.13)['reason'] == 'command_watchdog_expired'
    assert controller.accept(sequence=1, timestamp_s=.14, positions=[.02], now_s=.14)['operation'] == 'disable'


@pytest.mark.parametrize('change,reason', [
    ({'positions':[float('nan')]}, 'invalid_joint_command'),
    ({'positions':[2.]}, 'invalid_joint_command'),
    ({'positions':[.8]}, 'command_rate_exceeded'),
    ({'sequence':-1}, 'invalid_command_order'),
    ({'timestamp_s':.03}, 'invalid_command_order'),
    ({'now_s':-.01}, 'clock_reversed'),
])
def test_invalid_commands_fail_closed(change, reason):
    controller = gate()
    controller.arm(0., [0.], manifest_sha256='a'*64, operator_acknowledged=True)
    command = dict(sequence=0, timestamp_s=.02, positions=[.01], now_s=.02)
    command.update(change)
    result = controller.accept(**command)
    assert result['operation'] == 'disable' and result['reason'] == reason
    assert not controller.armed and not result['hardware_command_sent']


def test_sensor_replay_preserves_order_joint_mapping_and_simulated_provenance():
    frame = dict(schema_version='vivacity.recorded-proprioception/1',
        provenance='native_mujoco_simulation', joint_names=['joint'], timestamp_s=0.,
        position_rad=[0.], velocity_rad_s=[0.])
    result = validate_sensor_replay([frame, dict(frame, timestamp_s=.02)], ['joint'])
    assert result['samples'] == 2 and not result['hardware_validation']
    with pytest.raises(ValueError, match='timestamps'):
        validate_sensor_replay([frame, frame], ['joint'])
    with pytest.raises(ValueError, match='mapping'):
        validate_sensor_replay([frame], ['other'])
    with pytest.raises(ValueError, match='provenance'):
        validate_sensor_replay([dict(frame, provenance='validated_hardware')], ['joint'])


def test_exported_transfer_package_has_matching_identity_and_real_recorded_samples():
    folder = Path(__file__).parents[1]/'hardware-transfer/g1-carton'
    content = (folder/'manifest.json').read_bytes()
    assert hashlib.sha256(content).hexdigest() == (folder/'manifest.sha256').read_text().strip()
    manifest = json.loads(content)
    assert not manifest['hardware_validated'] and not manifest['transport_implemented']
    names = [joint['joint'] for joint in manifest['joints']]
    records = [json.loads(line) for line in (folder/'simulated-proprioception.jsonl').read_text().splitlines()]
    assert validate_sensor_replay(records, names) == manifest['sensor_replay']
    assert len(records) > 300
    assert records[-1]['timestamp_s'] > records[0]['timestamp_s']
    assert records[-1]['position_rad'] != records[0]['position_rad']
