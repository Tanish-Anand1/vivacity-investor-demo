"""Regenerate frontend geometry from the actual compiled MuJoCo model."""
from pathlib import Path
from shutil import copyfile
from .export_robot_geometry import export


def main():
    export()
    root = Path(__file__).resolve().parents[1]
    dest = root / 'frontend' / 'public' / 'vivacity'
    dest.mkdir(parents=True, exist_ok=True)
    for name in ('robot-geometry.json', 'robot-meshes.bin'):
        copyfile(root / 'docs' / name, dest / name)
    copyfile(root / 'assets' / 'menagerie' / 'franka_emika_panda' / 'LICENSE', dest / 'PANDA_LICENSE.txt')
    print(f'Compiled Panda geometry synchronized to {dest}')


if __name__ == '__main__':
    main()
