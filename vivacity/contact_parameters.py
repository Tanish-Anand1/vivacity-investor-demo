"""Editable contact-task definitions, kept separate from controller source hashes.

Request bounds admit failure experiments. They are not the successful operating
envelope. Every public task field has an explicit dependency and test reference.
"""
from .bimanual import BimanualConfig
from .physical_parameters import parameter_manifest


TASK_PARAMETERS = {
    'parcel': {'unit':None, 'dependency':'compiled parcel geometry, inertia and contact solver',
               'requires_rebuild':True, 'test':'tests/test_physical_parameters.py::test_every_editable_box_parameter_has_dependency_and_test'},
    'controller': {'unit':None, 'dependency':'native-servo task controller selection; constrained task fixes its own controller',
                   'requires_rebuild':True, 'test':'tests/test_constrained_bimanual.py::test_constrained_task_preserves_the_original_native_actuator_and_damping_model'},
    'source_xy_m': {'unit':'m', 'axes':[{'label':'Source X (m)','minimum':.18,'maximum':.7},
                                      {'label':'Source Y (m)','minimum':-.3,'maximum':.3}],
                    'dependency':'parcel initial free-joint position and approach/grip targets', 'requires_rebuild':True,
                    'test':'tests/test_contact_parameters.py::test_effective_native_parameters_match_manifest_dependencies'},
    'destination_xy_m': {'unit':'m','axes':[{'label':'Destination X (m)','minimum':.18,'maximum':.7},
                                          {'label':'Destination Y (m)','minimum':-.3,'maximum':.3}],
                         'dependency':'transfer/lower targets and measured placement-error goal', 'requires_rebuild':True,
                         'test':'tests/test_contact_parameters.py::test_destination_seed_and_budget_remain_explicit_task_configuration'},
    'floor_friction': {'unit':'1','dependency':'floor geom sliding friction and priority-resolved floor contacts',
                       'requires_rebuild':True,'test':'tests/test_contact_parameters.py::test_effective_native_parameters_match_manifest_dependencies'},
    'hand_torque_scale': {'unit':'1','dependency':'native articulated finger joint actuator-force ranges',
                          'requires_rebuild':True,'test':'tests/test_contact_parameters.py::test_effective_native_parameters_match_manifest_dependencies'},
    'gravity_m_s2': {'unit':'m/s^2','dependency':'model.opt.gravity negative-Z component',
                     'requires_rebuild':True,'test':'tests/test_contact_parameters.py::test_effective_native_parameters_match_manifest_dependencies'},
    'disturbance_n': {'unit':'N','dependency':'bounded horizontal base perturbation during the task',
                      'requires_rebuild':True,'test':'tests/test_contact_parameters.py::test_destination_seed_and_budget_remain_explicit_task_configuration'},
    'seed': {'unit':None,'dependency':'checkpointed random generator; current deterministic controller adds no random motion',
             'requires_rebuild':True,'test':'tests/test_contact_parameters.py::test_destination_seed_and_budget_remain_explicit_task_configuration'},
    'timeout_s': {'unit':'s','dependency':'task simulation-time failure boundary',
                  'requires_rebuild':True,'test':'tests/test_contact_parameters.py::test_destination_seed_and_budget_remain_explicit_task_configuration'},
}


def contact_parameter_manifest():
    schema = BimanualConfig.model_json_schema()
    return {'schema_version':'vivacity.contact-parameters/1',
            'parameters':{key:definition | {'schema':schema['properties'][key]}
                          for key,definition in TASK_PARAMETERS.items()},
            'parcel':parameter_manifest(),
            'successful_envelope':{'source_xy_m':[[.315,.325],[-.005,.005]],
                'destination_xy_m':[[.395,.405],[-.005,.005]],'mass_kg':[.4,.6],
                'sliding_friction':[.7,.9],'dimensions_m':[.18,.18,.16],
                'qualification':'Native-servo baseline only. Constrained-controller acceptance remains separate.'}}
