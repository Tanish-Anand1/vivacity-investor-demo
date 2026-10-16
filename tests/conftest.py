from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from vivacity.runtime import Runtime
from vivacity.robotics import RoboticsBackend
from vivacity.schemas import RoboticsConfig


@pytest.fixture
def runtime(tmp_path):
    r = Runtime(tmp_path / 'experiments.sqlite3')
    yield r
    r.close()


@pytest.fixture(scope='module')
def robot():
    b = RoboticsBackend()
    return b, b.create_world(RoboticsConfig().model_dump(), 7)
