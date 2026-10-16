"""Bounded, descriptive equation fits over recorded MuJoCo measurements.

These are approximations of observed trajectories, not inferred laws of motion.
The final fifth of each time series is held out in chronological order.
"""
from __future__ import annotations

import math
import time
from decimal import Decimal

import numpy as np
from .factory_discovery_data import QUANTITIES


def _metrics(actual, predicted, reference_variation=0.):
    residual = actual - predicted
    rmse = float(np.sqrt(np.mean(residual * residual)))
    mae = float(np.mean(np.abs(residual)))
    total = float(np.sum((actual - np.mean(actual)) ** 2))
    # A nearly flat future window has no useful variance denominator. Keep
    # residual errors, but do not display an arbitrarily huge R² quotient.
    meaningful = total > max(1e-20, len(actual) * (reference_variation * .05) ** 2)
    return {'rmse': rmse, 'mae': mae, 'r2': 1 - float(np.sum(residual * residual)) / total if meaningful else None}


def _number(value):
    # Desmos expressions use decimal literals, not Python's 1e-7 notation.
    return format(Decimal(format(float(value), '.8g')), 'f')


def _candidate(kind, x, y, t0, scale):
    """Return parameters and an evaluator; every optimizer sees training data only."""
    u = (x - t0) / scale
    mean = float(np.mean(y))
    span = float(np.ptp(y)) or max(abs(mean), 1.) * 1e-6
    if kind == 'constant':
        return [mean], lambda z, p: np.full_like(z, p[0], dtype=float)
    if kind in ('linear', 'quadratic', 'cubic'):
        degree = {'linear': 1, 'quadratic': 2, 'cubic': 3}[kind]
        p = np.polynomial.polynomial.polyfit(u, y, degree)
        return p.tolist(), lambda z, q: np.polynomial.polynomial.polyval(z, q)
    if kind == 'piecewise_linear':
        best = None
        for fraction in (.3, .5, .7):
            split = int(len(x) * fraction)
            if split < 8 or len(x) - split < 8:
                continue
            left = np.polynomial.polynomial.polyfit(u[:split], y[:split], 1)
            right = np.polynomial.polynomial.polyfit(u[split:], y[split:], 1)
            boundary = float((u[split - 1] + u[split]) / 2)
            prediction = np.where(u <= boundary, np.polynomial.polynomial.polyval(u, left), np.polynomial.polynomial.polyval(u, right))
            loss = float(np.mean((y - prediction) ** 2))
            if best is None or loss < best[0]:
                best = (loss, [*left, *right, boundary])
        if best is None:
            raise ValueError('too few points for piecewise fit')
        return best[1], lambda z, q: np.where(z <= q[4], q[0] + q[1] * z, q[2] + q[3] * z)
    if kind == 'exponential':
        def evaluate(z, p):
            return p[0] + p[1] * np.exp(np.clip(p[2] * z, -30, 30))
        starts = ([mean, span, -.5], [mean, -span, -.5], [mean, span, .5], [mean, -span, .5])
        bounds = ([-np.inf, -np.inf, -4], [np.inf, np.inf, 4])
    elif kind in ('sinusoidal', 'damped_sinusoidal'):
        def evaluate(z, p):
            envelope = np.exp(-p[4] * np.maximum(z, 0)) if kind == 'damped_sinusoidal' else 1
            return p[0] + p[1] * envelope * np.sin(p[2] * z + p[3])
        frequencies = (2 * math.pi * i for i in (0.5, 1, 2, 3))
        starts = ([mean, span / 2, f, 0, .2] if kind == 'damped_sinusoidal' else [mean, span / 2, f, 0] for f in frequencies)
        bounds = ([-np.inf, -np.inf, .1, -2 * math.pi, 0] if kind == 'damped_sinusoidal' else [-np.inf, -np.inf, .1, -2 * math.pi],
                  [np.inf, np.inf, 8 * math.pi, 2 * math.pi, 4] if kind == 'damped_sinusoidal' else [np.inf, np.inf, 8 * math.pi, 2 * math.pi])
    else:
        raise ValueError('unknown model family')
    # Import SciPy only for final nonlinear fits. Live linear updates must not
    # make the native physics lane contend with a cold optimizer import.
    from scipy.optimize import least_squares
    best = None
    for start in starts:
        fit = least_squares(lambda p: evaluate(u, p) - y, start, bounds=bounds, max_nfev=120)
        if not fit.success or not np.all(np.isfinite(fit.x)):
            continue
        loss = float(np.mean((evaluate(u, fit.x) - y) ** 2))
        if best is None or loss < best[0]:
            best = (loss, fit.x.tolist())
    if best is None:
        raise ValueError('fit did not converge')
    return best[1], evaluate


def _latex(kind, p, t0, scale, minimum, maximum, parameterized=False):
    u = f'\\left(\\frac{{x-{_number(t0)}}}{{{_number(scale)}}}\\right)'
    n = _number
    v = (lambda i: f'a_{{{i+1}}}') if parameterized else (lambda i: n(p[i]))
    if kind == 'constant':
        expression = v(0)
    elif kind in ('linear', 'quadratic', 'cubic'):
        expression = '+'.join(f'({v(i)}){u}^{i}' if i else v(i) for i, _ in enumerate(p))
    elif kind == 'exponential':
        expression = f'{v(0)}+({v(1)})e^{{({v(2)}){u}}}'
    elif kind in ('sinusoidal', 'damped_sinusoidal'):
        envelope = f'e^{{-({v(4)}){u}}}' if kind == 'damped_sinusoidal' else ''
        expression = f'{v(0)}+({v(1)}){envelope}\\sin\\left(({v(2)}){u}+({v(3)})\\right)'
    elif kind == 'piecewise_linear':
        boundary = f'({n(t0)}+{n(scale)}{v(4)})' if parameterized else n(t0 + scale * p[4])
        expression = f'\\left\\{{x\\le {boundary}:{v(0)}+({v(1)}){u},{v(2)}+({v(3)}){u}\\right\\}}'
    else:
        raise ValueError(kind)
    return f'y={expression}\\left\\{{{n(minimum)}\\le x\\le {n(maximum)}\\right\\}}'


def _display_latex(kind, p, t0, scale, minimum, maximum):
    """Typeset the same measured fit with conventional time and cases notation.

    Desmos needs its own piecewise/domain syntax; this form is for readers.
    Both expressions are generated from the identical fitted parameters.
    """
    n = _number

    def sum_terms(intercept, terms):
        expression = n(intercept)
        for coefficient, factor in terms:
            sign = '-' if coefficient < 0 else '+'
            expression += f' {sign} {n(abs(coefficient))}{factor}'
        return expression

    if kind == 'constant':
        expression = n(p[0])
    elif kind in ('linear', 'quadratic', 'cubic'):
        expression = sum_terms(p[0], [(p[i], 'u' if i == 1 else f'u^{{{i}}}') for i in range(1, len(p))])
    elif kind == 'exponential':
        expression = sum_terms(p[0], [(p[1], f'e^{{{n(p[2])}u}}')])
    elif kind in ('sinusoidal', 'damped_sinusoidal'):
        phase = sum_terms(0., [(p[2], 'u'), (p[3], '')])
        # Remove the artificial zero introduced by the shared signed formatter.
        phase = phase.removeprefix('0 + ').removeprefix('0 - ')
        if p[2] < 0:
            phase = '-' + phase
        envelope = f'e^{{-{n(p[4])}u}}' if kind == 'damped_sinusoidal' else ''
        expression = sum_terms(p[0], [(p[1], f'{envelope}\\sin\\left({phase}\\right)')])
    elif kind == 'piecewise_linear':
        boundary = n(t0 + scale * p[4])
        left = sum_terms(p[0], [(p[1], 'u')])
        right = sum_terms(p[2], [(p[3], 'u')])
        expression = (r'\begin{cases}' + f'{left}, & t\\le {boundary}'
                      + r'\\' + f'{right}, & t>{boundary}' + r'\end{cases}')
    else:
        raise ValueError(kind)
    time_shift = 't' if abs(t0) < 1e-12 else f't-{n(t0)}' if t0 > 0 else f't+{n(abs(t0))}'
    return (r'\begin{aligned}y(t)&=' + expression + r'\\'
            + f'u&=\\frac{{{time_shift}}}{{{n(scale)}}},\\quad '
            + f'{n(minimum)}\\le t\\le {n(maximum)}\\;\\mathrm{{s}}'
            + r'\end{aligned}')


def _plain(kind, p, t0, scale, minimum, maximum):
    """A readable counterpart to the machine-ready Desmos LaTeX."""
    n = _number
    u = f'((t-{n(t0)})/{n(scale)})'
    if kind == 'constant':
        expression = n(p[0])
    elif kind in ('linear', 'quadratic', 'cubic'):
        expression = ' + '.join(f'({n(value)})×{u}^{i}' if i else n(value) for i, value in enumerate(p))
    elif kind == 'exponential':
        expression = f'{n(p[0])} + ({n(p[1])})×exp(({n(p[2])})×{u})'
    elif kind in ('sinusoidal', 'damped_sinusoidal'):
        envelope = f'exp(-({n(p[4])})×{u})×' if kind == 'damped_sinusoidal' else ''
        expression = f'{n(p[0])} + ({n(p[1])})×{envelope}sin(({n(p[2])})×{u}+({n(p[3])}))'
    else:
        boundary = t0 + scale * p[4]
        expression = f'{n(p[0])} + ({n(p[1])})×{u} when t ≤ {n(boundary)}; {n(p[2])} + ({n(p[3])})×{u} otherwise'
    return f'y(t) = {expression}, {n(minimum)} ≤ t ≤ {n(maximum)} s'


def discover(points, run_id, quantity, *, updated_at=None, families=None):
    """Fit bounded candidate families; return validation evidence and provenance.

    A contiguous future holdout tests extrapolation within the recorded run.
    No claim of causality or transfer across conditions follows from this fit.
    """
    if quantity not in QUANTITIES:
        raise ValueError('unsupported quantity')
    clean = sorted((float(x), float(y)) for x, y in points if x is not None and y is not None and math.isfinite(float(x)) and math.isfinite(float(y)))
    if len(clean) < 25:
        return {'schema_version': 'vivacity.factory-discovery/1.0', 'run_id': run_id, 'quantity': quantity,
                'label': QUANTITIES[quantity][0], 'unit': QUANTITIES[quantity][1], 'x_unit': 's',
                'sample_count': len(clean), 'status': 'insufficient_data', 'reason': 'At least 25 finite measurements are required.',
                'models': [], 'selected_model': None, 'updated_at': updated_at or time.time()}
    values = np.asarray(clean, dtype=float)
    # Deduplicate repeated physics timestamps (event samples can share a time).
    times, unique = np.unique(values[:, 0], return_index=True)
    actual = values[unique, 1]
    split = max(20, int(len(times) * .8))
    if len(times) - split < 5:
        return discover(list(zip(times[:24], actual[:24])), run_id, quantity, updated_at=updated_at)
    training_x, training_y = times[:split], actual[:split]
    held_x, held_y = times[split:], actual[split:]
    t0 = float(training_x[0]);scale = max(float(training_x[-1] - training_x[0]), 1e-9)
    models = []
    for kind, parameters in [('constant', 1), ('linear', 2), ('quadratic', 3), ('cubic', 4),
                             ('exponential', 3), ('sinusoidal', 4), ('damped_sinusoidal', 5), ('piecewise_linear', 5)]:
        if families is not None and kind not in families:
            continue
        if split < max(20, 6 * parameters):
            continue
        try:
            p, evaluate = _candidate(kind, training_x, training_y, t0, scale)
            train_pred = evaluate((training_x - t0) / scale, p)
            held_pred = evaluate((held_x - t0) / scale, p)
            if not np.all(np.isfinite(train_pred)) or not np.all(np.isfinite(held_pred)):
                continue
            train = _metrics(training_y, train_pred)
            validation = _metrics(held_y, held_pred, float(np.std(training_y)))
            if not all(math.isfinite(value) for value in (train['rmse'], validation['rmse'])):
                continue
            # Complexity cost discourages unnecessarily flexible descriptions.
            score = validation['rmse'] + max(1e-9, float(np.std(training_y)) * 1e-4) * parameters
            curve_x = np.linspace(float(times[0]), float(times[-1]), min(160, len(times)))
            curve_y = evaluate((curve_x - t0) / scale, p)
            if not np.all(np.isfinite(curve_y)):
                continue
            models.append({'model': kind, 'parameters': [float(v) for v in p], 'parameter_count': parameters,
                           'equation_latex': _latex(kind, p, t0, scale, float(times[0]), float(times[-1])),
                           'display_latex': _display_latex(kind, p, t0, scale, float(times[0]), float(times[-1])),
                           'editable_latex': _latex(kind, p, t0, scale, float(times[0]), float(times[-1]), True),
                           'equation_text': _plain(kind, p, t0, scale, float(times[0]), float(times[-1])),
                           'training': train, 'validation': validation, 'selection_score': float(score),
                           'predicted_curve': [[float(a), float(b)] for a, b in zip(curve_x, curve_y)],
                           'domain_s': [float(times[0]), float(times[-1])], 'origin_s': t0, 'scale_s': scale})
        except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError):
            continue
    models.sort(key=lambda row: row['selection_score'])
    baseline = next((row for row in models if row['model'] == 'constant'), None)
    variation = float(np.std(training_y))
    tolerance = max(1e-9, variation * .01)
    for model in models:
        validated = (model['validation']['rmse'] <= max(tolerance, 1.5 * model['training']['rmse'] + .1 * variation)
            and (model['validation']['rmse'] <= tolerance if model['model'] == 'constant' else
                 model['validation']['r2'] is not None and model['validation']['r2'] >= .25
                 and baseline is not None and model['validation']['rmse'] < baseline['validation']['rmse'] * .9))
        model['validation_status'] = 'validated_approximation' if validated else 'poor_fit'
    models.sort(key=lambda row: (row['validation_status']!='validated_approximation',row['selection_score']))
    selected = models[0] if models else None
    return {'schema_version': 'vivacity.factory-discovery/1.0', 'run_id': run_id, 'quantity': quantity,
            'label': QUANTITIES[quantity][0], 'unit': QUANTITIES[quantity][1], 'x_unit': 's',
            'sample_count': len(times), 'train_count': len(training_x), 'held_out_count': len(held_x),
            'status': selected['validation_status'] if selected else 'poor_fit',
            'reason': 'Time-ordered 20% holdout; descriptive approximation only.' if selected and selected['validation_status']=='validated_approximation' else 'The selected model does not predict the held-out interval well enough.',
            'models': models, 'selected_model': selected['model'] if selected else None,
            'updated_at': updated_at or time.time(),
            'provenance': {'source': 'MuJoCo factory frames', 'run_id': run_id, 'quantity': quantity,
                           'x': 'simulation time', 'object_id': 'target', 'joint_index': 0 if quantity == 'torque' else None,
                           'method': 'training first 80%, held-out final 20%; validation RMSE plus 0.01% training standard deviation per parameter'}}
