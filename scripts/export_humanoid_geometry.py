"""Export the exact compiled visual/collision geometry used by humanoid trials.

The binary files are geometry only. Trial movement comes from recorded MuJoCo
body transforms returned by the API. Keep source model licenses with exports.
"""

from pathlib import Path
from shutil import copyfile
import sys
from types import SimpleNamespace

from scripts.export_robot_geometry import export
from vivacity.humanoids import ASSETS, MODELS, compiled_model


def main(robot_ids=None):
    root = Path(__file__).resolve().parents[1] / 'frontend/public/vivacity/humanoids'
    for robot_id in robot_ids or MODELS:
        if robot_id not in MODELS:
            raise ValueError(f'Unknown humanoid model: {robot_id}')
        model, digest = compiled_model(robot_id)
        destination = root / robot_id
        export(destination, SimpleNamespace(model=model, model_hash=digest, config={'robot_id': robot_id}))
        copyfile(ASSETS / robot_id / 'LICENSE', destination / 'LICENSE.txt')


if __name__ == '__main__':
    main(sys.argv[1:])
