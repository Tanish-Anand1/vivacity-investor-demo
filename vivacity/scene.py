"""Trusted primitive scene construction; rendered poses come from MuJoCo."""
import xml.etree.ElementTree as ET
import mujoco as mj


def append_scene(worldbody, config, root=None):
    for item in config.get('scene_geometries', []):
        size = item['size'][:2] if item['type'] == 'cylinder' else item['size']
        ET.SubElement(worldbody, 'geom', name='environment_' + item['name'],
                      type=item['type'], pos=' '.join(map(str, item['position'])),
                      quat=' '.join(map(str, item.get('quaternion_wxyz', [1., 0., 0., 0.]))),
                      size=' '.join(map(str, size)), rgba=' '.join(map(str, item['rgba'])),
                      friction=f"{item['friction']} .005 .0001")
    operation=config.get('physical_operation','pick_place')
    destination=config['placement_position'];sizes=config.get('cube_half_sizes') or [config.get('cube_half_size',.025)]*3
    if config.get('program_id') == 'precision_assembly':
        # Four rigid tray rails around the source; the part remains a free body.
        # Their poses use the same world-Z-up frame and metre units as the table.
        source=config['cube_position']
        for axis in range(2):
            for sign in (-1,1):
                position=[source[0],source[1],.012]
                position[axis]+=sign*.09
                size=[.09,.09,.012];size[axis]=.004
                ET.SubElement(worldbody,'geom',name=f'task_fixture_source_tray_{axis}_{sign+1}',type='box',
                              pos=' '.join(map(str,position)),size=' '.join(map(str,size)),
                              rgba='.34 .39 .41 1',friction='.8 .005 .0001')
    if operation=='stacking':
        support=ET.SubElement(worldbody,'body',name='stack_base',pos=f'{destination[0]} {destination[1]} {sizes[2]+.001}')
        ET.SubElement(support,'freejoint',name='stack_base_free')
        ET.SubElement(support,'geom',name='task_fixture_stack_base',type='box',size=' '.join(map(str,sizes)),
                      mass='.15',friction='1.2 .005 .0001',rgba='.48 .56 .46 1',condim='4')
    elif operation in ('assembly','insertion','machine_tending'):
        gap=(.006 if operation=='assembly' else .02)
        for axis in range(2):
            for sign in (-1,1):
                position=[destination[0],destination[1],.03]
                position[axis]+=sign*(sizes[axis]+gap+.004)
                wall_size=[sizes[0]+gap+.008,sizes[1]+gap+.008,.03];wall_size[axis]=.004
                ET.SubElement(worldbody,'geom',name=f'task_fixture_{axis}_{sign+1}',type='box',
                              pos=' '.join(map(str,position)),size=' '.join(map(str,wall_size)),rgba='.4 .5 .45 1',friction='.8 .005 .0001')
        if operation=='machine_tending':
            door=ET.SubElement(worldbody,'body',name='machine_door',pos=f'{destination[0]-.06} {destination[1]-.065} .03')
            ET.SubElement(door,'joint',name='machine_door_joint',type='hinge',axis='0 0 -1',range='0 1.5707963',damping='2')
            ET.SubElement(door,'geom',name='task_fixture_machine_door',type='box',size='.06 .005 .03',pos='.06 0 0',mass='.2',rgba='.35 .4 .43 1')
            actuator=root.find('actuator')
            ET.SubElement(actuator,'position',name='machine_door_motor',joint='machine_door_joint',kp='100',kv='10',ctrlrange='0 1.5707963',forcerange='-5 5')


def append_object_environment_sensors(root,sensors):
    for geom in root.findall('.//geom'):
        name=geom.get('name','')
        if name.startswith(('environment_','task_fixture_source_tray_')):
            ET.SubElement(sensors,'contact',name='object_environment_'+name,geom1='cube',geom2=name,data='found force',reduce='maxforce')


def initialize_task(model,data,config):
    if config.get('physical_operation')=='machine_tending':
        data.qpos[int(model.jnt_qposadr[model.joint('machine_door_joint').id])]=1.5707963
        data.ctrl[model.actuator('machine_door_motor').id]=1.5707963


def finish_task(world,limits,trace,backend,start_time,wall_start,pause_start):
    if world.config.get('physical_operation')!='machine_tending':return 0,None,[]
    import time
    world.data.ctrl[world.model.actuator('machine_door_motor').id]=0
    steps=0;failure=None;violations=[]
    for step in range(750):
        if limits.get('checkpoint') and not limits['checkpoint']():failure='cancelled';break
        if limits.get('cancel_event') and limits['cancel_event'].is_set():failure='cancelled';break
        mj.mj_step(world.model,world.data);mj.mj_forward(world.model,world.data);steps+=1
        contacts=backend.contacts(world)
        if contacts:failure='collision_failure';violations.extend(contacts)
        if any(world.data.warning.number):failure='controller_failure'
        elapsed=time.perf_counter()-wall_start-(limits.get('pause_seconds',lambda:0.)()-pause_start)
        if world.data.time-start_time>=limits['max_simulation_seconds'] or elapsed>limits.get('max_wall_seconds',120):failure='timeout'
        if step%25==0 or failure:
            frame=backend.observe(world)|{'phase':'closing_machine_fixture'}
            trace.append(frame)
            if limits.get('on_frame'):limits['on_frame'](frame)
        if failure:break
    return steps,failure,violations


def observed_scene(world):
    m, d = world.model, world.data
    return [{'name': m.geom(i).name, 'type': mj.mjtGeom(int(m.geom_type[i])).name.removeprefix('mjGEOM_').lower(),
             'position': d.geom_xpos[i].tolist(), 'quaternion_wxyz': _quaternion(d.geom_xmat[i]),
             'size': m.geom_size[i].tolist(), 'rgba': m.geom_rgba[i].tolist()}
            for i in range(m.ngeom) if m.geom(i).name.startswith(('environment_','task_fixture_'))]


def _quaternion(matrix):
    import numpy as np
    quaternion = np.empty(4)
    mj.mju_mat2Quat(quaternion, matrix)
    return quaternion.tolist()
