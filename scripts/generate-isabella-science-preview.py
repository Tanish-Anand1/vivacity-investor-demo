"""Export a reproducible, clearly labelled recorded SciPy result for the homepage.

The UI uses this as an example result. New experiments always run through the API.
No hidden generator parameter is serialized into the public artifact.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vivacity.schemas import ScienceConfig
from vivacity.science import ScienceBackend


def main():
    backend = ScienceBackend()
    world = backend.create_world(ScienceConfig().model_dump(), seed=7)
    hypotheses = []
    for action in backend.candidates(world, 2, 0)[0]:
        branch = backend.fork(backend.snapshot(world))
        backend.apply_action(branch, action)
        result = backend.simulate(branch, {})
        evaluation = backend.evaluate(branch, result)
        if not evaluation['success']:
            raise RuntimeError(f"homepage preview fit failed: {evaluation['status']}")
        hypotheses.append({
            'id': action['hypothesis'],
            'definition': action['definition'],
            'train_rmse': result['train_rmse'],
            'heldout_rmse': result['heldout_rmse'],
            'training_bic': result['training_bic'],
            'predicted_positions': [frame['predicted_position'] for frame in result['trace']],
            'residuals': result['residuals'],
        })
    public = world.state
    artifact = {
        'schema_version': 'vivacity.recorded-science/1.0',
        'status': 'recorded_scipy_result',
        'simulator_version': backend.version,
        'seed': public['seed'],
        'model': 'Restricted nondimensional 2D gravity; stationary perturbing location is declared.',
        'times': public['times'],
        'observations': public['observations'],
        'train_count': int(len(public['times']) * public['config']['train_fraction']),
        'hypotheses': hypotheses,
    }
    target = Path(__file__).resolve().parents[1] / 'frontend/src/generated/isabellaSciencePreview.json'
    target.write_text(json.dumps(artifact, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f"{target}: {target.stat().st_size} bytes, {len(artifact['times'])} samples")


if __name__ == '__main__':
    main()
