import json
import numpy as np
import pytest
from vivacity.science import ScienceBackend
from vivacity.schemas import ScienceConfig, CreateWorld, ExperimentRequest


@pytest.mark.parametrize('mass,mu', [(0.12, 1.0), (0.08, 1.05)])
def test_parameter_recovery_and_heldout(runtime, mass, mu):
    w = runtime.create_world(CreateWorld(backend='scipy', config=ScienceConfig(hidden_mass=mass, central_mu=mu)))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest())['id'])
    assert e['status'] == 'completed'
    branches = runtime.store.branches(e['id'])
    baseline, extra = [b['evaluation'] for b in branches]
    assert e['selected_branch_id'] == branches[1]['id']
    assert extra['parameters']['perturbing_mass'] == pytest.approx(mass, abs=0.003)
    assert extra['parameters']['central_mu'] == pytest.approx(mu, abs=0.002)
    assert extra['heldout_rmse'] < 0.003
    assert extra['heldout_rmse'] < baseline['heldout_rmse']/10
    assert len(branches[1]['trace']) == 70
    errors = np.asarray(extra['residuals'])[extra['train_count']:]
    assert extra['heldout_rmse'] == pytest.approx(np.sqrt(np.mean(errors**2)))
    assert extra['uncertainty']['full_rank']
    assert extra['uncertainty']['standard_errors']['perturbing_mass'] > 0


@pytest.mark.parametrize('seed', [7, 11, 23])
def test_unnecessary_mass_rejected(runtime, seed):
    w = runtime.create_world(CreateWorld(backend='scipy', seed=seed, config=ScienceConfig(hidden_mass=0)))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest())['id'])
    branches = runtime.store.branches(e['id'])
    assert e['selected_branch_id'] == branches[0]['id']


def test_no_truth_leakage_and_fork_independence(runtime):
    w = runtime.create_world(CreateWorld(backend='scipy', config=ScienceConfig(hidden_mass=0.123456789)))
    serialized = json.dumps(w)
    assert 'hidden_mass' not in serialized and '0.123456789' not in serialized
    assert 'central_mu' not in serialized
    a, b = runtime.fork(w['id']), runtime.fork(w['id'])
    a.state['observations'][0][0] = 100
    assert b.state['observations'][0][0] != 100
    assert runtime.observe(w['id'])['observation']['observations'][0][0] != 100


def test_fits_do_not_use_heldout_observations():
    backend = ScienceBackend()
    w = backend.create_world(ScienceConfig().model_dump(), 7)
    a, b = backend.fork(backend.snapshot(w)), backend.fork(backend.snapshot(w))
    split = int(70*0.7)
    b.state['observations'][split:] = [[100., 100.]] * (70-split)
    action = backend.candidates(w, 2, 0)[0][1]
    backend.apply_action(a, action); backend.apply_action(b, action)
    ra, rb = backend.simulate(a, {}), backend.simulate(b, {})
    assert ra['parameters'] == rb['parameters']
    assert ra['training_bic'] == rb['training_bic']
    assert rb['heldout_rmse'] > 90


def test_science_reproducibility_and_new_settings(runtime):
    w1 = runtime.create_world(CreateWorld(backend='scipy'))
    w2 = runtime.create_world(CreateWorld(backend='scipy'))
    assert w1['state'] == w2['state']
    old = w1['state']['observations']
    changed = runtime.environment(w1['id'], ScienceConfig(noise_std=0.01, samples=50))
    assert len(changed['state']['observations']) == 50
    assert changed['state']['observations'] != old
    e = runtime.wait(runtime.submit(w1['id'], ExperimentRequest())['id'])
    selected = next(b for b in runtime.store.branches(e['id']) if b['id'] == e['selected_branch_id'])
    runtime.commit(w1['id'], e['id'], selected['id'])
    assert runtime.observe(w1['id'])['observation']['selected_model']
    assert runtime.reset(w1['id'])['state']['selected_model'] is None


def test_singular_orbit_fails_honestly():
    backend = ScienceBackend()
    w = backend.create_world(ScienceConfig().model_dump(), 7)
    w.state['config']['initial_state'] = [0, 0, 0, 1]
    backend.apply_action(w, backend.candidates(w, 2, 0)[0][0])
    result = backend.simulate(w, {})
    assert result['failure'] == 'integration_failure'
    assert not backend.evaluate(w, result)['success']
