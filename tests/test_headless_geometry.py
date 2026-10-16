from copy import deepcopy
import xml.etree.ElementTree as ET
import mujoco as mj
import numpy as np
import pytest
from vivacity.headless import collision_only
from vivacity.robotics import ASSET_DIR
from vivacity.robot_models import trusted_root


@pytest.mark.parametrize('arm',['panda','ur5e','iiwa','gen3','xarm7','scara','dual_arm'])
def test_collision_only_preserves_real_robot_dynamics(arm):
    if arm=='panda':
        root=ET.parse(ASSET_DIR/'panda.xml').getroot()
        root.find('compiler').set('meshdir',str(ASSET_DIR/'assets'))
    else:
        root,_=trusted_root(arm)
    original=mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
    pruned=deepcopy(root);removed=collision_only(pruned,True)
    lean=mj.MjModel.from_xml_string(ET.tostring(pruned,encoding='unicode'))
    if arm!='scara':assert removed>0 and lean.nmeshvert<original.nmeshvert
    assert (lean.nq,lean.nv,lean.nu,lean.nbody)==(original.nq,original.nv,original.nu,original.nbody)
    for attribute in ('body_mass','body_inertia','body_ipos','body_iquat','jnt_range','dof_damping'):
        np.testing.assert_allclose(getattr(lean,attribute),getattr(original,attribute),atol=1e-12,rtol=0)
    def collision_names(model):
        return [model.geom(i).name for i in range(model.ngeom) if model.geom_contype[i] or model.geom_conaffinity[i]]
    assert collision_names(lean)==collision_names(original)
    a,b=mj.MjData(original),mj.MjData(lean)
    if original.nkey:
        mj.mj_resetDataKeyframe(original,a,0);mj.mj_resetDataKeyframe(lean,b,0)
    for _ in range(125):
        mj.mj_step(original,a);mj.mj_step(lean,b)
    np.testing.assert_allclose(a.qpos,b.qpos,atol=1e-10,rtol=0)
    np.testing.assert_allclose(a.qvel,b.qvel,atol=1e-10,rtol=0)


def test_inferred_mass_and_explicit_contact_references_are_preserved():
    root=ET.fromstring('''<mujoco><worldbody>
      <body name="inferred"><geom name="mass_source" type="box" size=".1 .1 .1" contype="0" conaffinity="0"/></body>
      <body name="explicit"><inertial pos="0 0 0" mass="1" diaginertia=".1 .1 .1"/>
        <geom name="referenced" type="sphere" size=".1" contype="0" conaffinity="0"/>
        <geom name="decorative" type="sphere" size=".1" contype="0" conaffinity="0"/>
      </body></worldbody><contact><pair geom1="referenced" geom2="mass_source"/></contact></mujoco>''')
    assert collision_only(root,True)==1
    assert {e.get('name') for e in root.findall('.//worldbody//geom')}=={'mass_source','referenced'}
