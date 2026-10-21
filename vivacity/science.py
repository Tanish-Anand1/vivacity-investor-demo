"""Restricted 2D gravity with isolated observation generation and held-out fitting."""
from copy import deepcopy
from dataclasses import dataclass, field
import time
import numpy as np
import scipy
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares


def orbit(times, initial, location, central_mu, mass):
    times = np.asarray(times)
    location = np.asarray(location)

    def rhs(t, state):
        r = state[:2]
        delta = location-r
        radius, distance = np.linalg.norm(r), np.linalg.norm(delta)
        if radius < 0.05 or distance < 0.05:
            raise ValueError('trajectory approached a gravitational singularity')
        acc = -central_mu*r/radius**3 + mass*delta/distance**3
        return np.r_[state[2:], acc]

    sol = solve_ivp(rhs, (0, float(times[-1])), initial, t_eval=times, method='DOP853', rtol=2e-8, atol=2e-10)
    if not sol.success or sol.y.shape[1] != len(times) or not np.isfinite(sol.y).all():
        raise ValueError('orbital integration failed')
    return sol.y.T


@dataclass
class ScienceWorld:
    state: dict
    action: dict = field(default_factory=dict)


class ScienceBackend:
    version = scipy.__version__
    action_schema = {'type': 'fit_hypothesis', 'hypotheses': ['central_only', 'central_plus_fixed_perturber'], 'units': 'nondimensional', 'method': 'solve_ivp DOP853 + least_squares'}

    def create_world(self, config, seed):
        times = np.linspace(0, config['horizon'], config['samples'])
        # Truth exists only in this scope. Neither state nor policy receives it.
        true = orbit(times, config['initial_state'], config['perturbing_position'], config['central_mu'], config['hidden_mass'])
        observed = true[:, :2] + np.random.default_rng(seed).normal(0, config['noise_std'], (len(times), 2))
        public_config = {k: v for k, v in config.items() if k not in ('hidden_mass', 'central_mu')}
        return ScienceWorld({'backend': 'scipy', 'version': self.version, 'seed': seed, 'config': public_config, 'times': times.tolist(), 'observations': observed.tolist(), 'current_state': config['initial_state'], 'selected_model': None})

    def snapshot(self, world):
        return deepcopy(world.state)

    def fork(self, state):
        if state['version'] != self.version:
            raise ValueError('SciPy snapshot version mismatch')
        return ScienceWorld(deepcopy(state))

    def observe(self, world):
        return self.snapshot(world)

    def candidates(self, world, count, iterations):
        return [{'kind': 'fit_hypothesis', 'hypothesis': 'central_only', 'definition': 'Test particle under central Newtonian gravity; one fitted gravitational parameter.'}, {'kind': 'fit_hypothesis', 'hypothesis': 'central_plus_fixed_perturber', 'definition': 'Central gravity plus a stationary external mass at a known declared location; two fitted parameters.'}], 0.

    def apply_action(self, world, action):
        if action['hypothesis'] not in self.action_schema['hypotheses']:
            raise ValueError('unsupported hypothesis')
        world.action = deepcopy(action)

    def simulate(self, world, limits):
        tic = time.perf_counter(); s = world.state; c = s['config']
        times, obs = np.asarray(s['times']), np.asarray(s['observations'])
        split = int(len(times)*c['train_fraction'])
        extra = world.action['hypothesis'] != 'central_only'
        calls = 0

        def predict(params, ts):
            nonlocal calls
            if limits.get('checkpoint') and not limits['checkpoint']():raise InterruptedError('cancelled before numerical integration')
            calls += 1
            return orbit(ts, c['initial_state'], c['perturbing_position'], params[0], params[1] if extra else 0)

        def residual(params):
            return ((predict(params, times[:split])[:, :2]-obs[:split])/c['noise_std']).ravel()

        try:
            fit = least_squares(residual, [1., 0.05] if extra else [1.], bounds=([0.5, 0.] if extra else [0.5], [1.5, 0.4] if extra else [1.5]), max_nfev=100, xtol=1e-9, ftol=1e-9, gtol=1e-8)
            predicted = predict(fit.x, times)
            errors = predicted[:, :2]-obs
            train_rmse = float(np.sqrt(np.mean(errors[:split]**2)))
            holdout_rmse = float(np.sqrt(np.mean(errors[split:]**2)))
            chi2 = float(np.sum((errors[:split]/c['noise_std'])**2))
            bic = chi2 + len(fit.x)*np.log(split*2)
            rank = int(np.linalg.matrix_rank(fit.jac))
            covariance = np.linalg.pinv(fit.jac.T @ fit.jac)
            std = np.sqrt(np.maximum(0, np.diag(covariance)))
            names = ['central_mu', 'perturbing_mass'] if extra else ['central_mu']
            params = dict(zip(names, fit.x.tolist()))
            world.state['selected_model'] = {'hypothesis': world.action['hypothesis'], 'parameters': params}
            world.state['current_state'] = predicted[-1].tolist()
            return {'failure': None if fit.success else 'optimizer_failure', 'fit_message': str(fit.message), 'parameters': params, 'uncertainty': {'method': 'local linearized covariance using known measurement noise; not posterior probability', 'standard_errors': dict(zip(names, std.tolist())), 'jacobian_rank': rank, 'full_rank': rank == len(fit.x), 'active_bounds': fit.active_mask.tolist(), 'caveat': 'Gaussian local approximation; boundary mass and misspecified physics limit interpretation'}, 'train_rmse': train_rmse, 'heldout_rmse': holdout_rmse, 'training_bic': float(bic), 'train_count': split, 'heldout_count': len(times)-split, 'residuals': errors.tolist(), 'trace': [{'time': float(t), 'observed_position': o.tolist(), 'predicted_position': p[:2].tolist(), 'predicted_velocity': p[2:].tolist(), 'split': 'train' if i < split else 'heldout'} for i, (t, o, p) in enumerate(zip(times, obs, predicted))], 'integration_calls': calls, 'optimizer_evaluations': fit.nfev, 'physics_wall_seconds': time.perf_counter()-tic}
        except (ValueError, FloatingPointError) as exc:
            return {'failure': 'integration_failure', 'fit_message': str(exc), 'trace': [], 'integration_calls': calls, 'physics_wall_seconds': time.perf_counter()-tic}

    def evaluate(self, world, result):
        return {k: deepcopy(v) for k, v in result.items() if k not in ('trace', 'physics_wall_seconds')} | {'success': result['failure'] is None, 'status': result['failure'] or 'fit_completed', 'hypothesis': world.action['hypothesis']}

    def choose(self, branches):
        valid = [b for b in branches if b['evaluation']['success']]
        if not valid:
            return None, {'conclusion': 'Both numerical hypotheses failed; no supported result.'}
        if len(valid) == 1:
            return None, {'conclusion': 'One hypothesis failed numerically; model comparison is incomplete.'}
        base, extra = valid
        be, ee = base['evaluation'], extra['evaluation']
        delta = be['training_bic']-ee['training_bic']
        improved = ee['heldout_rmse'] < be['heldout_rmse']*0.95
        selected = extra if delta > 6 and improved and ee['uncertainty']['full_rank'] else base
        return selected['id'], {'conclusion': 'Additional fixed gravitational influence supported by training complexity penalty and held-out predictions.' if selected is extra else 'Additional mass is not sufficiently supported; retain the central-only model.', 'bic_improvement_for_extra_mass': delta, 'heldout_rmse_improvement': be['heldout_rmse']-ee['heldout_rmse'], 'criterion': 'extra mass requires BIC improvement > 6 and held-out RMSE improvement > 5%, with full-rank Jacobian', 'scope': 'Comparison of two simplified models; not discovery of a new physical law.'}

    def commit(self, state):
        return self.snapshot(self.fork(state))

    def replay(self, branch):
        source = 'failed_adapter_execution' if branch['evaluation']['status'] == 'adapter_failure' else 'executed_scipy_predictions_and_observations'
        return {'branch_id': branch['id'], 'source': source, 'frames': branch['trace'], 'evaluation': branch['evaluation']}
