import pytest
from vivacity.factory import FactoryBackend,FactorySettings
from vivacity.factory_controller import ProductionController,FactoryFault,grasp_evidence

def test_three_cartons_physically_gripped_released_and_sorted_to_both_lanes():
    backend=FactoryBackend();w=backend.create_world(FactorySettings().model_dump());events=[]
    controller=ProductionController(backend,w,on_event=events.append,pace=False)
    result=controller.run()
    assert result['cartons_sorted']==3 and result['station_arrivals']==3
    assert result['simulation_steps']>10000
    arrivals=[e for e in events if e['kind']=='destination_arrival']
    assert len(arrivals)==3 and {e['lane'] for e in arrivals}=={'A','B'}
    assert all(e['grasp']['bilateral_grasp'] for e in events if e['kind']=='close_completed')
    assert len([e for e in events if e['kind']=='physical_transfer_verified'])==3
    for event in arrivals:
        expected='A' if w.model.body(event['carton_id']).mass[0]<w.config['sort_threshold_kg'] else 'B'
        assert expected==event['lane']
        assert 'bin_'+expected+'_floor' in grasp_evidence(w,event['carton_id'])['support_geoms']
    assert result['max_tracking_error_rad']<.1

def test_insufficient_finger_force_records_failure_without_sorting():
    backend=FactoryBackend();w=backend.create_world(FactorySettings(carton_count=1,carton_mass_kg=.15,carton_friction=.05,gripper_force_scale=.005).model_dump())
    events=[];controller=ProductionController(backend,w,on_event=events.append,pace=False)
    with pytest.raises(FactoryFault) as error:controller.run()
    assert error.value.kind in ('grasp_failure','dropped_object','lift_failure')
    assert controller.sorted==0
    assert not any(e['kind']=='destination_arrival' for e in events)

def test_cancel_stops_integration_at_checkpoint():
    backend=FactoryBackend();w=backend.create_world(FactorySettings(carton_count=1).model_dump())
    controller=ProductionController(backend,w,checkpoint=lambda:w.data.time<.1,pace=False)
    with pytest.raises(InterruptedError):controller.run()
    assert w.data.time==pytest.approx(.1)
    assert controller.sorted==0
