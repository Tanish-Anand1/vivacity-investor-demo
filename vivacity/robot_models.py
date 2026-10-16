"""Trusted model assembly. Source arms retain their actual joint counts/dynamics.

Non-Panda arms use a modeled Panda parallel-jaw flange attachment. This is a
simulation fixture, not a manufacturer-approved physical hardware integration.
"""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET
import hashlib
import mujoco as mj
import numpy as np

from .robotics import ASSET_DIR, RobotWorld
from .compiled import remember, reuse_world
from .pick_place import PickPlaceBackend

MODELS={'ur5e':('universal_robots_ur5e','ur5e.xml',6), 'iiwa':('kuka_iiwa_14','iiwa14.xml',7),
        'gen3':('kinova_gen3','gen3.xml',7),'xarm7':('ufactory_xarm7','xarm7_nohand.xml',7),
        'scara':(None,None,4),'dual_arm':('franka_emika_panda','panda.xml',7)}


def _rename_body(root,old,new):
    for element in root.iter():
        for key in ('body1','body2','body','subtree1','subtree2'):
            if element.get(key)==old:element.set(key,new)
        if element.tag=='body' and element.get('name')==old:element.set('name',new)


def _scara():
    return ET.fromstring('''<mujoco model="Vivacity analytical SCARA"><compiler angle="radian" autolimits="true"/><option integrator="implicitfast"/>
    <default><joint damping="20"/><geom density="1000" rgba=".5 .55 .6 1"/></default>
    <worldbody><body name="link0"><geom type="cylinder" size=".1 .2" pos="0 0 .2"/>
     <body name="scara_shoulder" pos="0 0 .45"><joint name="scara_joint1" axis="0 0 1" range="-3.14 3.14"/><geom type="capsule" fromto="0 0 0 .35 0 0" size=".045"/>
      <body name="scara_elbow" pos=".35 0 0"><joint name="scara_joint2" axis="0 0 1" range="-2.8 2.8"/><geom type="capsule" fromto="0 0 0 .3 0 0" size=".04"/>
       <body name="scara_slide" pos=".3 0 0"><joint name="scara_joint3" type="slide" axis="0 0 -1" range="0 .35"/><geom type="cylinder" size=".025 .08" pos="0 0 .08"/>
        <body name="scara_wrist"><joint name="scara_joint4" axis="0 0 1" range="-6.28 6.28"/><geom type="cylinder" size=".045 .02"/><site name="attachment_site" quat="0 1 0 0"/></body>
       </body></body></body></body></worldbody>
    <actuator><position joint="scara_joint1" kp="1000" kv="100" ctrlrange="-3.14 3.14"/><position joint="scara_joint2" kp="1000" kv="100" ctrlrange="-2.8 2.8"/>
     <position joint="scara_joint3" kp="2000" kv="100" ctrlrange="0 .35"/><position joint="scara_joint4" kp="1000" kv="100" ctrlrange="-6.28 6.28"/></actuator>
    <keyframe><key qpos="-.6 1.2 .12 -.6" ctrl="-.6 1.2 .12 -.6"/></keyframe></mujoco>''')


def trusted_root(identifier):
    if identifier=='scara':root=_scara();directory=None
    else:
        folder,filename,_=MODELS[identifier];directory=ASSET_DIR.parent/folder
        root=ET.parse(directory/filename).getroot()
        root.find('compiler').set('meshdir','')
        for mesh in root.findall('.//asset/mesh'):
            mesh.set('file',str(directory/'assets'/mesh.get('file')))
    home=root.find('keyframe/key')
    initial=np.asarray([float(x) for x in home.get('qpos').split()]) if home is not None else np.zeros(MODELS[identifier][2])
    if identifier=='dual_arm':
        # Two independent actuated Panda models. The primary arm executes the
        # task; coordinated bimanual planning is deliberately not claimed.
        base=deepcopy(root.find("worldbody/body[@name='link0']"));base.set('pos','-1.4 0 0')
        names={e.get('name'):'secondary_'+e.get('name') for e in base.iter() if e.get('name')}
        for element in base.iter():
            if element.get('name') in names:element.set('name',names[element.get('name')])
        root.find('worldbody').append(base)
        for section in ('tendon','equality','actuator','contact'):
            source=root.find(section)
            if source is None:continue
            for item in list(source):
                copied=deepcopy(item)
                for element in copied.iter():
                    for key,value in list(element.attrib.items()):
                        if value in names:element.set(key,names[value])
                        elif key=='name':element.set(key,'secondary_'+value)
                        elif key=='tendon' and value=='split':element.set(key,'secondary_split')
                source.append(copied)
        initial=np.r_[initial,initial]
    else:
        primary=root.find('worldbody/body')
        _rename_body(root,primary.get('name'),'link0')
        if identifier=='gen3':
            contact=root.find('contact')
            if contact is None:contact=ET.SubElement(root,'contact')
            ET.SubElement(contact,'exclude',body1='link0',body2='shoulder_link')
        source=ET.parse(ASSET_DIR/'panda.xml').getroot()
        hand=deepcopy(source.find(".//body[@name='hand']"))
        classes={e.get('class'):'grip_'+e.get('class') for e in source.findall('.//default') if e.get('class')}
        materials={e.get('name'):'grip_'+e.get('name') for e in source.findall('asset/material')}
        meshes={(e.get('name') or Path(e.get('file')).stem):'grip_'+(e.get('name') or Path(e.get('file')).stem) for e in source.findall('asset/mesh')}
        for element in hand.iter():
            for key in ('class','childclass','material','mesh'):
                value=element.get(key)
                mapped=(classes if key in ('class','childclass') else materials if key=='material' else meshes)
                if value in mapped:element.set(key,mapped[value])
        defaults=deepcopy(source.find('default/default'))
        for element in defaults.iter():
            if element.get('class') in classes:element.set('class',classes[element.get('class')])
            if element.get('material') in materials:element.set('material',materials[element.get('material')])
        root.find('default').append(defaults)
        asset=root.find('asset')
        if asset is None:asset=ET.SubElement(root,'asset')
        used={e.get('mesh') for e in hand.iter() if e.get('mesh')}
        for element in source.find('asset'):
            item=deepcopy(element)
            if item.get('class') in classes:item.set('class',classes[item.get('class')])
            if item.tag=='material':item.set('name',materials[item.get('name')])
            elif item.tag=='mesh':
                item.set('name',meshes[item.get('name') or Path(item.get('file')).stem])
                if item.get('name') not in used:continue
                item.set('file',str(ASSET_DIR/'assets'/item.get('file')))
            asset.append(item)
        site=root.find(".//site[@name='attachment_site']")
        if site is None:site=root.find(".//site[@name='pinch_site']")
        parent=next((b for b in root.iter('body') if site is not None and site in list(b)),None)
        if parent is None:parent=list(primary.iter('body'))[-1]
        hand.set('pos',site.get('pos','0 0 0') if site is not None else '0 0 0')
        hand.set('quat',site.get('quat','1 0 0 0') if site is not None else '1 0 0 0')
        parent.append(hand)
        for section in ('tendon','equality'):
            source_section=source.find(section)
            if source_section is not None:root.append(deepcopy(source_section))
        actuator=deepcopy(list(source.find('actuator'))[-1]);actuator.set('class','grip_panda');actuator.set('name','parallel_gripper')
        root.find('actuator').append(actuator)
        initial=np.r_[initial,.04,.04]
    if root.find('keyframe') is not None:root.remove(root.find('keyframe'))
    return root,initial


class ModelPickupBackend(PickPlaceBackend):
    search_speed_bounds=(.16,.2)
    def __init__(self,identifier):
        self.identifier=identifier;self.arm_dof=MODELS[identifier][2]
        self.action_schema=super().action_schema|{'joints':self.arm_dof,'robot_model':identifier,'gripper':'modeled Panda parallel-jaw flange fixture'}

    @reuse_world('mujoco')
    def create_world(self,config,seed,diagnostics=False):
        root,initial=trusted_root(self.identifier)
        root.find('option').set('timestep','.002');root.find('option').set('cone','elliptic')
        for body in root.iter('body'):body.set('gravcomp','1')
        hand=root.find(".//body[@name='hand']")
        ET.SubElement(hand,'site',name='pregrasp',pos='0 0 .103',size='.008')
        wb=root.find('worldbody')
        ET.SubElement(wb,'geom',name='ground',type='plane',pos='0 0 -.8',size='2 2 .1')
        ET.SubElement(wb,'geom',name='table',type='box',pos='.4 0 -.04',size='.7 .65 .04',friction='1 .005 .0001')
        target=ET.SubElement(wb,'body',name='target',pos=' '.join(map(str,config['cube_position'])))
        ET.SubElement(target,'freejoint',name='cube_free')
        sizes=config.get('cube_half_sizes') or [config.get('cube_half_size',.025)]*3
        ET.SubElement(target,'geom',name='cube',type='box',size=' '.join(map(str,sizes)),mass=str(config['cube_mass']),
                      friction=f"{config['cube_friction']} .005 .0001",condim='4',priority='1',solref='.004 1',rgba='.05 .35 .9 1')
        obstacle=ET.SubElement(wb,'body',name='obstacle',pos=' '.join(map(str,config['obstacle_position'])))
        ET.SubElement(obstacle,'geom',name='obstacle_geom',type='box',size=' '.join(map(str,config['obstacle_size'])),
                      contype='1' if config['obstacle_enabled'] else '0',conaffinity='1' if config['obstacle_enabled'] else '0')
        from .scene import append_scene
        append_scene(wb,config,root)
        from .physical_properties import configure_xml
        configure_xml(root, config)
        portable=deepcopy(root)
        for mesh in portable.findall('.//asset/mesh'):
            mesh.set('file',Path(mesh.get('file')).relative_to(ASSET_DIR.parent).as_posix())
        physical_xml=ET.tostring(portable)
        checksum=hashlib.sha256(physical_xml+_model_assets_digest(self.identifier)+self.version.encode()).hexdigest()
        sensors=ET.SubElement(root,'sensor')
        for name,attributes in [('robot_contacts',{'subtree1':'link0'}),('mount_contacts',{'body1':'link0','geom2':'table'}),
            ('left_grasp',{'body1':'left_finger','geom2':'cube'}),('right_grasp',{'body1':'right_finger','geom2':'cube'}),
            ('table_support',{'geom1':'cube','geom2':'table'}),('object_obstacle',{'geom1':'cube','geom2':'obstacle_geom'}),('object_ground',{'geom1':'cube','geom2':'ground'})]:
            ET.SubElement(sensors,'contact',name=name,data='found force',reduce='maxforce',**attributes)
        from .scene import append_object_environment_sensors
        append_object_environment_sensors(root,sensors)
        if self.identifier=='dual_arm':
            ET.SubElement(sensors,'contact',name='secondary_robot_contacts',subtree1='secondary_link0',data='found force',reduce='maxforce')
            ET.SubElement(sensors,'contact',name='secondary_mount_contacts',body1='secondary_link0',geom2='table',data='found force',reduce='maxforce')
        from .headless import collision_only
        collision_only(root)
        model=mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
        # MuJoCo ignores range for continuous joints. Supply a finite RRT/DLS
        # search window without enabling a nonexistent mechanical limit.
        for i in range(self.arm_dof):
            if not model.jnt_limited[i]:model.jnt_range[i]=[-2*np.pi,2*np.pi]
        data=mj.MjData(model)
        data.qpos[:len(initial)]=initial
        data.ctrl[:self.arm_dof]=initial[:self.arm_dof];data.ctrl[self.arm_dof]=255
        if self.identifier=='dual_arm':data.ctrl[8:15]=initial[9:16];data.ctrl[15]=255
        from .scene import initialize_task
        initialize_task(model,data,config)
        from .physical_properties import initialize_inputs
        initialize_inputs(model, data, config)
        mj.mj_forward(model,data)
        world=RobotWorld(model,data,deepcopy(config),seed,checksum)
        return world if diagnostics else remember(world,'mujoco')

    def candidates(self,world,count,iterations):
        from .pickup_planning import stage_distance
        actions,seconds=super().candidates(world,count,iterations)
        for action in actions:
            for stage in action.get('stages',[]):
                stage['duration_s']=max(stage['duration_s'],stage_distance(stage)/.2)
        return actions,seconds

    def contacts(self,world):
        violations=[];m,d=world.model,world.data
        def is_robot(i):
            while i:
                if m.body(i).name in ('link0','secondary_link0'):return True
                i=int(m.body_parentid[i])
            return False
        robot_ids={i for i in range(1,m.nbody) if is_robot(i)}
        for contact in d.contact[:d.ncon]:
            if contact.dist>0:continue
            geoms=[m.geom(int(i)).name or f'geom_{i}' for i in (contact.geom1,contact.geom2)]
            bodies=[int(m.geom_bodyid[i]) for i in (contact.geom1,contact.geom2)]
            names=[m.body(i).name or 'world' for i in bodies]
            if 'link0' in names and 'table' in geoms:continue
            if 'cube' in geoms and any(n in ('left_finger','right_finger') for n in names):continue
            if 'cube' in geoms and any(n in ('obstacle_geom','ground') or n.startswith('environment_') for n in geoms):
                if 'table' not in geoms:violations.append({'bodies':names,'geoms':geoms,'penetration_m':float(-contact.dist),'category':'object_environment_collision'})
            if any(i in robot_ids for i in bodies):violations.append({'bodies':names,'geoms':geoms,'penetration_m':float(-contact.dist),
                'category':'self_collision' if all(i in robot_ids for i in bodies) else 'environment_collision'})
        return violations


class ModelReachBackend(ModelPickupBackend):
    def __init__(self,identifier):
        super().__init__(identifier)
        from .robotics import RoboticsBackend
        self.action_schema=RoboticsBackend.action_schema|{'joints':self.arm_dof,'robot_model':identifier}

    def candidates(self,*args):
        from .robotics import RoboticsBackend
        return RoboticsBackend.candidates(self,*args)

    def apply_action(self,*args):
        from .robotics import RoboticsBackend
        return RoboticsBackend.apply_action(self,*args)

    def simulate(self,*args):
        from .robotics import RoboticsBackend
        return RoboticsBackend.simulate(self,*args)

    def evaluate(self,*args):
        from .robotics import RoboticsBackend
        return RoboticsBackend.evaluate(self,*args)


@lru_cache(maxsize=8)
def _model_assets_digest(identifier):
    digest=hashlib.sha256()
    directories=[ASSET_DIR/'assets']
    if MODELS[identifier][0] and identifier!='dual_arm':directories.append(ASSET_DIR.parent/MODELS[identifier][0]/'assets')
    for directory in directories:
        for file in sorted(directory.iterdir()):digest.update(file.name.encode());digest.update(file.read_bytes())
    return digest.digest()
