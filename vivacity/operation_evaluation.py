"""Operation milestones measured from actual state/contact geometry."""
import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation


def evaluate_operation(world,evaluation):
    operation=world.config.get('physical_operation','pick_place')
    if operation=='pick_place':return evaluation
    p=world.data.body('target').xpos
    target=np.asarray(world.config['placement_position']);sizes=np.asarray(world.config.get('cube_half_sizes') or [world.config.get('cube_half_size',.025)]*3)
    gap=.006 if operation=='assembly' else .02
    contained=bool(np.max(np.abs(p[:2]-target[:2]))<=gap)
    q=world.data.body('target').xquat
    yaw=Rotation.from_quat(np.roll(q,-1)).as_euler('xyz')[2]
    alignment=float(abs((yaw+np.pi/4)%(np.pi/2)-np.pi/4))
    if operation in ('assembly','insertion','machine_tending'):
        contacts=[]
        for i,c in enumerate(world.data.contact[:world.data.ncon]):
            names=[world.model.geom(int(j)).name or '' for j in (c.geom1,c.geom2)]
            if 'cube' in names and any(name.startswith('task_fixture_') for name in names):
                force=np.zeros(6);mj.mj_contactForce(world.model,world.data,i,force)
                contacts.append({'geoms':names,'normal_force_N':float(abs(force[0]))})
        seated=contained and abs(p[2]-target[2])<.01 and np.linalg.norm(world.data.qvel[int(world.model.jnt_dofadr[world.model.joint('cube_free').id]):])<.05
        assembly=world.config.get('assembly') if world.config.get('program_id')=='precision_assembly' else None
        position_tolerance=assembly['placement_tolerance_m'] if assembly else gap
        orientation_tolerance=assembly['orientation_tolerance_rad'] if assembly else .12
        valid=seated and (operation!='assembly' or (evaluation['goal_error_m']<=position_tolerance and alignment<=orientation_tolerance))
        evaluation.update(milestone='single_component_fixture_seating' if operation=='assembly' else 'gravity_assisted_receptacle_insertion',
            contained_in_fixture=contained,seated=bool(seated),alignment_error_rad=alignment,fixture_contacts=contacts,
            operation_scope='Single rigid component in a passive fixture. No fastening or force-guided tight-tolerance insertion.')
        if assembly:
            evaluation.update(placement_tolerance_m=position_tolerance,orientation_tolerance_rad=orientation_tolerance,
                              placement_within_tolerance=bool(evaluation['goal_error_m']<=position_tolerance and alignment<=orientation_tolerance))
        if operation=='machine_tending':
            angle=float(world.data.qpos[int(world.model.jnt_qposadr[world.model.joint('machine_door_joint').id])])
            valid=valid and abs(angle)<.04
            evaluation.update(milestone='single_part_machine_bay_loading',machine_door_angle_rad=angle,
                machine_door_closed=abs(angle)<.04,operation_scope='Load a passive bay and close its actuated door. No actual production machine, machining process or hardware interlocks.')
    elif operation=='stacking':
        base=world.data.body('stack_base').xpos
        stacked=bool(np.linalg.norm(p[:2]-base[:2])<.015 and abs((p[2]-base[2])-2*sizes[2])<.01)
        valid=stacked and evaluation['table_supported']
        evaluation.update(milestone='two_dynamic_body_stack',stack_verified=valid,base_position=base.tolist(),
                          operation_scope='One dynamic component placed on one dynamic base; both integrate under gravity/contact.')
    else:
        rule=world.config['sorting_rule']
        value=float(world.model.body_mass[world.model.body('target').id]) if rule['property']=='mass' else float(world.model.geom_size[world.model.geom('cube').id][0]*2)
        valid=True
        evaluation.update(milestone='single_part_rule_based_sort',sort_rule=rule,measured_sort_property=value,sort_category='below_threshold' if value<rule['threshold'] else 'at_or_above_threshold',
                          operation_scope='One part classified from supplied simulator properties and physically transferred to its configured zone; not camera-based multi-object recognition.')
    if evaluation['success'] and not valid:evaluation.update(success=False,status='operation_goal_failure')
    return evaluation
