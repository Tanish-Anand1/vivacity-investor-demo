"""Readiness and compatibility are explicit; a catalogue entry is not a controller."""
from copy import deepcopy

REGISTRY={
 'robots':[
  {'id':'panda','name':'Franka Panda','manufacturer':'Franka Emika','category':'Collaborative / research','dof':7,'status':'available','model':'MuJoCo Menagerie MJCF','grippers':['panda_parallel','fold_fixture'],'scope':'Measured joint dynamics, DLS/RRT reaching and contact-driven manipulation.'},
  *[{'id':identifier,'name':name,'manufacturer':manufacturer,'category':category,'dof':dof,'status':'reference','model':model,'grippers':[],'scope':'Model/controller integration is not yet tested in this runtime.'} for identifier,name,manufacturer,category,dof,model in [
    ('ur3e','UR3e','Universal Robots','Collaborative',6,'Menagerie reference'),('ur5e','UR5e','Universal Robots','Collaborative',6,'Menagerie reference'),
    ('ur10e','UR10e','Universal Robots','Industrial',6,'Model integration required'),('iiwa','KUKA iiwa','KUKA','Industrial / research',7,'Menagerie reference'),
    ('gen3','Kinova Gen3','Kinova','Research',7,'Menagerie reference'),('abb','ABB IRB series','ABB','Industrial',6,'Specific model must be selected'),
    ('xarm','xArm series','UFACTORY','Desktop',6,'Specific model must be selected'),('scara','SCARA','Generic','Educational',4,'Analytical model integration required'),
    ('dual_arm','Dual Panda','Franka Emika','Research',14,'Coordinated controller required')]],
 ],
 'grippers':[
   {'id':'panda_parallel','name':'Panda parallel-jaw gripper','status':'available','robots':['panda'],'scope':'Two actuated fingers; native collision pads and measured contact/friction.'},
   {'id':'fold_fixture','name':'Panda folding fixture','status':'experimental','robots':['panda'],'scope':'Pre-attached clamps and hinge, not autonomous cloth grasp.'},
   *[{'id':key,'name':name,'status':'reference','robots':[],'scope':'End-effector dynamics and contact controller are not implemented.'} for key,name in [('adaptive','Adaptive gripper'),('vacuum','Vacuum gripper'),('three_finger','Three-finger gripper'),('custom','Custom end effector')]]],
 'operations':[
   {'id':'pick_place','name':'Pick and place','status':'available','scope':'Actual finger contact, lift, retention, release and supported placement.'},
   {'id':'object_transfer','name':'Object transfer','status':'available','scope':'Measured transfer between two locations on the fixed workbench.'},
   {'id':'reach','name':'Inspection pose / reach','status':'available','scope':'Reach a pre-grasp pose; no camera defect detection or grasp claimed.'},
   {'id':'randomized_manipulation','name':'Randomized manipulation','status':'available','scope':'Seeded pickup positions across repeated independently initialized cycles.'},
   {'id':'cloth_fold','name':'Cloth folding','status':'experimental','scope':'Fixture-assisted flex fold with measured alignment and vertex coverage.'},
    *[{'id':key,'name':name,'status':'reference','scope':'Task geometry, controller and task-specific success criteria require implementation.'} for key,name in [('sorting','Object sorting'),('assembly','Assembly'),('stacking','Stacking'),('insertion','Insertion')]]]
}


def registry():return deepcopy(REGISTRY)


# Availability here declares implemented model/controller code. Physical
# feasibility is still measured separately for every proposed trajectory.
for robot in REGISTRY['robots']:
    if robot['id'] in ('ur5e','iiwa','gen3','scara','dual_arm'):
        robot.update(status='available',grippers=['panda_parallel'],model='Trusted MuJoCo dynamics + modeled Panda flange gripper',
                     scope='Independent integrated branches and measured grasp/placement. SCARA is an analytical educational model; dual Panda executes with the primary arm, not coordinated bimanual planning.')
REGISTRY['robots'].append({'id':'xarm7','name':'UFACTORY xArm7','manufacturer':'UFACTORY','category':'Desktop / collaborative','dof':7,
                          'status':'available','model':'Menagerie xArm7 + modeled Panda flange gripper','grippers':['panda_parallel'],
                          'scope':'Independent MuJoCo state, DLS/RRT and contact-driven manipulation.'})
REGISTRY['grippers'][0]['robots']=['panda','ur5e','iiwa','gen3','xarm7','scara','dual_arm']
REGISTRY['operations'].append({'id':'machine_tending','name':'Machine bay loading','status':'available','scope':'Load a single part and close a modeled actuated bay door; no production-machine process or hardware interlocks.'})
for operation in REGISTRY['operations']:
    if operation['id'] in ('sorting','assembly','stacking','insertion'):
        operation['status']='available'
        operation['scope']={
            'sorting':'One part classified by a mass/width rule and physically transferred to its assigned zone; simulator properties, not camera-based recognition.',
            'assembly':'Single-component seating in a passive alignment fixture; no fastening or multi-part joining.',
            'stacking':'One dynamic component placed on a second dynamic base; measured support and alignment.',
            'insertion':'Gravity-assisted placement into a passive receptacle; no force-guided tight-tolerance insertion.'}[operation['id']]


def validate_hardware(robot,gripper,operation):
    r=next((r for r in REGISTRY['robots'] if r['id']==robot and r['status']=='available'),None)
    if not r:raise ValueError('This robot does not yet have a tested controller in this runtime.')
    if gripper not in r['grippers']:raise ValueError('Select a compatible implemented end effector.')
    if (operation=='cloth_fold')!=(gripper=='fold_fixture'):raise ValueError('Cloth folding requires the folding fixture; object handling uses the parallel gripper.')
