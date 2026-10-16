import threading
from vivacity.runtime import Runtime
from vivacity.schemas import CreateWorld,RoboticsConfig,ExperimentRequest
from vivacity.trial_execution import trial_results


def test_ordered_batches_overlap_and_account_for_every_result():
    barrier=threading.Barrier(2)
    class Engine:
        def simulate(self,action,settings):
            barrier.wait(timeout=5)
            return {'candidate':action['candidate_index']},{'success':True},{'state':action['candidate_index']}
    actions=[{'candidate_index':i} for i in range(4)]
    stats={'peak_parallel_trials':0}
    values=list(trial_results(Engine(),actions,{'checkpoint':lambda:True},threading.Event(),lambda frame:None,2,stats))
    assert [value[0]['candidate_index'] for value in values]==[0,1,2,3]
    assert [value[-1] for value in values]==[False,True,False,True]
    assert stats['peak_parallel_trials']==2


def test_real_parallel_mujoco_trials_match_sequential_integrations(tmp_path,monkeypatch):
    monkeypatch.setenv('VIVACITY_HEADLESS_GEOMETRY','1')
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    measurements=[]
    for workers in (1,2):
        monkeypatch.setenv('VIVACITY_PHYSICS_TRIAL_WORKERS',str(workers))
        runtime=Runtime(tmp_path/f'trials-{workers}.sqlite3')
        try:
            world=runtime.create_world(CreateWorld(backend='mujoco',seed=7,config=RoboticsConfig(task='pick_place',obstacle_enabled=False)))
            experiment=runtime.submit(world['id'],ExperimentRequest(physics_trials=3,search_candidates=3,max_simulation_seconds=40))
            final=runtime.wait(experiment['id'])
            assert final['status']=='completed' and final['selected_branch_id']
            trials=runtime.store.trials(experiment['id'])['items']
            assert len(trials)==3
            assert final['performance']['physics_trial_workers']==workers
            assert final['performance']['peak_parallel_trials']==workers
            assert all(t['performance']['simulation_steps']>0 for t in trials)
            measurements.append([(t['candidate_index'],t['evaluation'],t['final_state']) for t in trials])
        finally:runtime.close()
    assert measurements[0]==measurements[1]
