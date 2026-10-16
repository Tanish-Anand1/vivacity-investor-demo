"""Trusted adaptation of the supplied orbital fixture, never arbitrary upload XML.

The original has fixed fingers, oversized cargo and unreachable endpoints.
Only its static scene primitives are reused; Panda manipulation is explicit.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

SOURCE_SHA256 = '6d623c9fbd7aa337b195282f55dbbcc83432ffad69a95090dde2a831a4763354'
UPGRADES = [
    'Original three-hinge arm and fixed fingers replaced by actuated Menagerie Panda.',
    'Cargo width reduced from 0.21 m to 0.05 m; mass from 0.28 kg to 0.06 kg.',
    'Cargo and docking target moved into the validated Panda workspace.',
    'Deck surface aligned to z=0; docking is a marked region of the physical deck.',
    'Reactor relocated outside the fixed benchmark path; collisions remain enabled.',
    'Gravity remains terrestrial (-9.81 m/s²); this is an orbital-themed laboratory.',
]


def adapt_scene(root, config):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/imports/orbital_salvage_lab.zip'
    content = fixture.read_bytes()
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        raise ValueError('trusted Orbital fixture checksum mismatch')
    with zipfile.ZipFile(fixture) as archive:
        original = ET.fromstring(archive.read('Orbital_Salvage_Lab.xml'))
    wb = root.find('worldbody')
    # The native deck is the physical support, including the docking region.
    table = wb.find("geom[@name='table']")
    table.set('size', '1.95 1.45 .018')
    table.set('pos', '0 0 -.018')
    table.set('rgba', '.09 .13 .17 1')
    root.find(".//geom[@name='cube']").set('rgba', '.95 .42 .12 1')
    reactor = root.find(".//geom[@name='obstacle_geom']")
    reactor.set('type', 'cylinder')
    reactor.set('size', f"{config['obstacle_size'][0]} {config['obstacle_size'][2]}")
    reactor.set('rgba', '.9 .24 .06 1')
    for geom in original.findall('./worldbody/geom'):
        name = geom.get('name', '')
        if 'rail' in name:
            copied = deepcopy(geom)
            copied.attrib.pop('material', None)
            copied.set('rgba', '.2 .3 .37 1')
            wb.append(copied)
    destination = config['placement_position']
    ET.SubElement(wb, 'geom', name='docking_marker', type='cylinder',
                  pos=f'{destination[0]} {destination[1]} .001', size='.09 .001',
                  contype='0', conaffinity='0', rgba='.1 .7 .65 .75')
    obstacle = root.find(".//body[@name='obstacle']")
    ET.SubElement(obstacle, 'geom', name='reactor_ring', type='cylinder',
                  pos=f"0 0 {config['obstacle_size'][2] + .01}",
                  size=f"{config['obstacle_size'][0]+.035} .01",
                  contype='0', conaffinity='0', rgba='1 .5 .1 1')


def scene_geometry(world):
    import mujoco as mj
    m, d = world.model, world.data
    names = {'table', 'ground', 'cube', 'obstacle_geom', 'reactor_ring', 'docking_marker'}
    result = []
    for i in range(m.ngeom):
        name = mj.mj_id2name(m, mj.mjtObj.mjOBJ_GEOM, i) or ''
        if name not in names and 'rail' not in name:
            continue
        if name in ('obstacle_geom', 'reactor_ring') and not world.config['obstacle_enabled']:
            continue
        quaternion = __import__('numpy').zeros(4)
        mj.mju_mat2Quat(quaternion, d.geom_xmat[i])
        result.append({'name': name, 'type': mj.mjtGeom(int(m.geom_type[i])).name.removeprefix('mjGEOM_').lower(),
                       'position': d.geom_xpos[i].tolist(), 'quaternion_wxyz': quaternion.tolist(),
                       'size': m.geom_size[i].tolist(), 'rgba': m.geom_rgba[i].tolist()})
    return result
