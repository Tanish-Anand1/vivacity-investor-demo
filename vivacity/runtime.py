from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from .agent import DeterministicPolicy, HostedPolicy
from .pick_place import RobotAdapter
from .cloth import ClothBackend
from .storage import Store, encode
from .control import PauseControl

log = logging.getLogger(__name__)


def uid():
    return str(uuid.uuid4())


class Conflict(ValueError):
    pass


class Busy(ValueError):
    pass


class Unavailable(ValueError):
    pass


class Runtime:
    def __init__(self, database):
        self.physics_trial_workers=int(os.getenv('VIVACITY_PHYSICS_TRIAL_WORKERS','1'))
        if not 1<=self.physics_trial_workers<=2:
            raise ValueError('VIVACITY_PHYSICS_TRIAL_WORKERS must be 1..2')
        self.max_physics_trials = int(os.getenv('VIVACITY_MAX_PHYSICS_TRIALS', '5000'))
        if not 1 <= self.max_physics_trials <= 5000:
            raise ValueError('VIVACITY_MAX_PHYSICS_TRIALS must be 1..5000')
        self.max_pickup_wall_seconds = int(os.getenv('VIVACITY_MAX_PICKUP_WALL_SECONDS', '120'))
        if not 60 <= self.max_pickup_wall_seconds <= 1800:
            raise ValueError('VIVACITY_MAX_PICKUP_WALL_SECONDS must be 60..1800')
        self.store = Store(database)
        from pathlib import Path
        from .imports import ImportService
        self.imports = ImportService(Path(database).parent / 'imports')
        self.backends = {'mujoco': RobotAdapter(), 'cloth':ClothBackend()}
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='vivacity-simulation')
        self.capacity = threading.BoundedSemaphore(8)
        self.futures = {}
        self.cancel_flags = {}
        self.controls = {}
        self.live_states = {}
        # Single-process local deployment: persisted interrupted jobs cannot be resumed implicitly.
        with self.store.connect() as db:
            records = [json.loads(r[0]) for r in db.execute('SELECT payload FROM experiments')]
            for e in records:
                if e['status'] in ('queued', 'running'):
                    e.update(status='failed', error='worker_interrupted_by_restart')
                    self.store.put('experiments', e, db)
                    self.store.event(e['id'], 'failed', {'error': e['error']}, db)
        from .supervisor import Supervisor
        self.supervisor = Supervisor(self)

    def close(self):
        self.supervisor.close()
        for flag in list(self.cancel_flags.values()):
            flag.set()
        self.executor.shutdown(wait=True)

    def validate_trial_budget(self, requested):
        if requested > self.max_physics_trials:
            raise ValueError(f'this host supports at most {self.max_physics_trials} full physics trials per experiment')

    def validate_import_config(self, config):
        if getattr(config, 'scene_profile', None) == 'orbital_salvage':
            from .orbital import SOURCE_SHA256
            imported = self.imports.get(config.source_import_id)
            if imported['sha256'] != SOURCE_SHA256 or not (imported.get('capabilities') or {}).get('robot_actuation_verified'):
                raise ValueError('Orbital adaptation requires verified supplied source')

    def create_world(self, request):
        tic = time.perf_counter()
        if request.backend not in self.backends:
            raise ValueError('This simulation backend has been retired.')
        self.validate_import_config(request.config)
        backend = self.backends[request.backend]
        instance = backend.create_world(request.config.model_dump(), request.seed)
        state = backend.snapshot(instance)
        action_schema = backend.backend(state['config']).action_schema if request.backend == 'mujoco' else backend.action_schema
        world = {'schema_version': '1.0', 'id': uid(), 'backend': request.backend, 'config': deepcopy(state['config']), 'state': state, 'initial_state': deepcopy(state), 'action_schema': action_schema, 'simulator_version': backend.version, 'seed': request.seed, 'revision': 0, 'history': [], 'branches': [], 'evaluations': [], 'performance': {'initialization_wall_seconds': time.perf_counter()-tic}}
        self.store.put('worlds', world)
        return world

    def get_world(self, identifier):
        world = self.store.get('worlds', identifier)
        if world['backend'] not in self.backends:
            raise ValueError('This simulation backend has been retired. Create a robotics world.')
        return world

    def observe(self, identifier):
        w = self.get_world(identifier)
        instance = self.backends[w['backend']].fork(w['state'])
        observation = self.backends[w['backend']].observe(instance)
        if w['backend'] == 'mujoco' and w['config'].get('task') == 'pick_place' and w['config'].get('scene_profile') == 'workcell':
            from .perception import scan_cube
            observation['perception'] = scan_cube(instance)
        return {'schema_version': '1.0', 'world_id': identifier, 'revision': w['revision'], 'observation': observation}

    def snapshot(self, identifier):
        return deepcopy(self.get_world(identifier)['state'])

    def fork(self, identifier):
        w = self.get_world(identifier)
        return self.backends[w['backend']].fork(w['state'])

    def apply_action(self, backend, instance, action):
        self.backends[backend].apply_action(instance, action)

    def simulate(self, backend, instance, limits):
        return self.backends[backend].simulate(instance, limits)

    def evaluate(self, backend, instance, result):
        return self.backends[backend].evaluate(instance, result)

    def submit(self, world_id, request, idempotency_key=None, control=None):
        self.validate_trial_budget(request.physics_trials)
        if request.adaptive_trials:
            self.validate_trial_budget(request.physics_budget)
        if idempotency_key is not None:
            import re
            if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', idempotency_key):
                raise ValueError('invalid idempotency key')
        fingerprint = hashlib.sha256(encode(request.model_dump()).encode()).hexdigest()
        reserved = False
        try:
            with self.lock, self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if idempotency_key is not None:
                    prior = db.execute('SELECT fingerprint,experiment_id FROM submissions WHERE world_id=? AND key=?', (world_id, idempotency_key)).fetchone()
                    if prior:
                        if prior[0] != fingerprint:
                            # Additive defaults must not invalidate a pre-upgrade retry.
                            from .schemas import ExperimentRequest
                            saved=self.store.get('experiments',prior[1],db)['request']
                            if ExperimentRequest.model_validate(saved).model_dump()!=request.model_dump():
                                raise Conflict('idempotency key was already used with different experiment settings')
                        return self.get_experiment(prior[1])
                if not self.capacity.acquire(blocking=False):
                    raise Busy('experiment queue is full; retry after a job completes')
                reserved = True
                w = self.store.get('worlds', world_id, db)
                if request.physics_trials and (w['backend']!='mujoco' or w['config'].get('task')!='pick_place'):
                    raise ValueError('full physics trials require a Panda pickup world')
                eid = uid()
                e = {'schema_version': '1.0', 'id': eid, 'world_id': world_id, 'revision': w['revision'], 'status': 'queued', 'request': request.model_dump(), 'selected_branch_id': None, 'result': {}, 'performance': {}, 'error': None, 'stale': False, 'snapshot': deepcopy(w['state']), 'config': w['config'], 'backend': w['backend'], 'submitted_at': time.time()}
                self.store.put('experiments', e, db)
                self.cancel_flags[eid] = threading.Event()
                self.controls[eid] = control or PauseControl()
                self.store.event(eid, 'queued', db=db)
                if idempotency_key is not None:
                    db.execute('INSERT INTO submissions(world_id,key,fingerprint,experiment_id) VALUES(?,?,?,?)', (world_id, idempotency_key, fingerprint, eid))
                w['history'].append(eid)
                self.store.put('worlds', w, db)
            try:
                future = self.executor.submit(self._run_reserved, eid)
            except RuntimeError:
                e.update(status='failed', error='worker_submission_failed')
                with self.store.connect() as db:
                    self.store.put('experiments', e, db)
                    self.store.event(eid, 'failed', {'error': e['error']}, db)
                raise Unavailable('simulation worker unavailable; experiment failure was persisted')
            with self.lock:
                self.futures[eid] = future
            def finished(_):
                with self.lock:
                    self.futures.pop(eid, None)
                    self.cancel_flags.pop(eid, None)
                    self.controls.pop(eid, None)
            future.add_done_callback(finished)
            reserved = False  # The worker wrapper now owns the reserved queue slot.
            return self.get_experiment(eid)
        except BaseException:
            if reserved:
                self.capacity.release()
            raise

    def wait(self, eid, timeout=120):
        with self.lock:
            future = self.futures.get(eid)
        if future:
            future.result(timeout=timeout)
        return self.get_experiment(eid)

    def get_experiment(self, eid):
        e = self.store.get('experiments', eid)
        e['stale'] = self.get_world(e['world_id'])['revision'] != e.get('result',{}).get('executed_world_revision',e['revision'])
        return {k: v for k, v in e.items() if k not in ('snapshot', 'config', 'backend', 'submitted_at')}

    def _execute(self, eid):
        wall, cpu = time.perf_counter(), time.process_time()
        e = self.store.get('experiments', eid)
        cancellation = self.cancel_flags.get(eid, threading.Event())
        control=self.controls.get(eid,PauseControl())
        checkpoint=lambda:control.checkpoint(cancellation)
        try:
            if not checkpoint():
                raise InterruptedError('cancelled before execution')
            e['status'] = 'running'
            self.store.put('experiments', e); self.store.event(eid, 'running')
            backend = self.backends[e['backend']]
            instance = backend.fork(e['snapshot'])
            self.publish_live(eid, e['world_id'], 'observing', backend.observe(instance))
            policy = HostedPolicy() if e['request']['policy'] == 'llm' else DeterministicPolicy()
            settings, reasoning = policy.propose(backend.observe(instance), backend.action_schema, e['request'])
            settings=settings|{'checkpoint':checkpoint,'pause_seconds':control.elapsed}
            search = None
            if e['backend']=='mujoco' and instance.config.get('task') == 'pick_place' and settings.get('search_candidates',0):
                actions,planning_time,search=backend.search(instance,settings,lambda detail:self.store.event(eid,'progress',detail))
            elif e['backend']=='mujoco' and settings.get('search_candidates',0):
                from .search import search_reaches
                actions, planning_time, search = search_reaches(backend,instance,settings,lambda detail:self.store.event(eid,'progress',detail))
            elif e['backend']=='cloth' and settings.get('search_candidates',0):
                actions, planning_time, search = backend.search(instance,settings,lambda detail:self.store.event(eid,'progress',detail))
            else:
                actions, planning_time = backend.candidates(instance, settings['candidates'], settings['planner_iterations'])
            self.store.event(eid, 'planned', {'candidate_count': len(actions), 'planning_wall_seconds': planning_time})
            branches = []
            reference = f"{e['world_id']}:{e['revision']}:{hashlib.sha256(encode(e['snapshot']).encode()).hexdigest()}"
            def execute_action(action, run_settings, role='validation'):
                if cancellation.is_set():
                    raise InterruptedError('cancelled between branches')
                branch_wall = time.perf_counter()
                branch_instance = None
                recorded_action = deepcopy(action)
                phase = 'fork'
                try:
                    branch_instance = backend.fork(e['snapshot'])
                    phase = 'apply_action'
                    self.apply_action(e['backend'], branch_instance, action)
                    phase = 'simulate'
                    execution_settings = run_settings | {'cancel_event': cancellation,'checkpoint':checkpoint,'pause_seconds':control.elapsed}
                    if role == 'authoritative_execution':
                        execution_settings['max_wall_seconds'] = self.max_pickup_wall_seconds
                        execution_settings |= {'on_frame': lambda frame:self.publish_live(eid,e['world_id'],'executing',frame),
                                               'realtime': settings.get('realtime_execution',False)}
                        self.store.event(eid,'progress',{'stage':'executing','message':'Executing the selected action again in an independent authoritative simulator; these are live physics states.'})
                    result = self.simulate(e['backend'], branch_instance, execution_settings)
                    recorded_action = result.get('executed_action', recorded_action)
                    phase = 'evaluate'
                    evaluation = self.evaluate(e['backend'], branch_instance, result)
                    phase = 'snapshot'
                    final_state = backend.snapshot(branch_instance)
                    trace = result['trace']
                    phase = 'serialize_result'
                    encode({'evaluation': evaluation, 'trace': trace, 'final_state': final_state})
                    performance = {'wall_seconds': time.perf_counter()-branch_wall, 'physics_wall_seconds': result['physics_wall_seconds'], 'ik_planning_seconds': result.get('ik_planning_seconds', 0), 'simulation_steps': result.get('simulation_steps', 0), 'integration_calls': result.get('integration_calls', 0), 'measurement_complete': True}
                except InterruptedError:
                    raise
                except Exception as exc:
                    # Do not invent frames or step counts when an adapter loses its trace.
                    log.error('branch adapter failed: experiment=%s phase=%s type=%s', eid, phase, type(exc).__name__)
                    final_state = None
                    if branch_instance is not None:
                        try:
                            final_state = backend.snapshot(branch_instance)
                            encode(final_state)
                        except Exception:
                            final_state = None
                    trace = []
                    evaluation = {'success': False, 'status': 'adapter_failure', 'phase': phase, 'error_type': type(exc).__name__, 'trace_available': False, 'final_state_available': final_state is not None}
                    performance = {'wall_seconds': time.perf_counter()-branch_wall, 'physics_wall_seconds': None, 'simulation_steps': None, 'integration_calls': None, 'measurement_complete': False}
                branch = {'schema_version': '1.0', 'id': uid(), 'experiment_id': eid, 'parent_state_reference': reference, 'initial_state': deepcopy(e['snapshot']), 'action': deepcopy(recorded_action) | {'execution_role':role}, 'trace': trace, 'final_state': final_state, 'evaluation': evaluation, 'performance': performance}
                # Persist evidence and lineage together, even if a later branch/job fails.
                with self.lock, self.store.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    current = self.store.get('worlds', e['world_id'], db)
                    current['branches'].append({'experiment_id': eid, 'branch_id': branch['id'], 'parent_state_reference': reference, 'revision': e['revision']})
                    current['evaluations'].append({'branch_id': branch['id'], 'evaluation': evaluation})
                    self.store.put('worlds', current, db)
                    self.store.put('branches', branch, db)
                    self.store.event(eid, 'branch_completed', {'branch_id': branch['id'], 'evaluation': evaluation}, db)
                branches.append(branch)
                if search is not None and role=='validation':
                    integrated=sum(bool((b['performance']['simulation_steps'] or 0)+(b['performance']['integration_calls'] or 0)) for b in branches)
                    self.store.event(eid,'progress',{'stage':'physics','fully_simulated':integrated,'physics_attempts':len(branches),'physics_target':len(actions),'verified_feasible':sum(b['evaluation']['success'] for b in branches),'elapsed_seconds':time.perf_counter()-wall,'message':f"Validation {len(branches)} / {len(actions)}; {integrated} integrated rollouts; {sum(b['evaluation']['success'] for b in branches)} verified feasible."})
                return branch
            trial_metrics=None
            if settings.get('physics_trials') or settings.get('adaptive_trials'):
                if e['backend']!='mujoco' or instance.config.get('task')!='pick_place':
                    raise ValueError('physics trials currently require the Panda pick-and-place world')
                branches,trial_metrics=self._bulk_trials(e,actions,settings,search,reference,cancellation)
            else:
                for action in actions:
                    execute_action(action, settings)
            if cancellation.is_set():
                raise InterruptedError('cancelled after current branch')
            # Choose additional tool work from measured outcomes, with one bounded retry.
            followup = None if search is not None else DeterministicPolicy().next_experiment(e['backend'], backend.observe(instance), branches, settings)
            if followup:
                extra_actions, extra_planning = backend.candidates(instance, followup['candidates'], followup['planner_iterations'])
                planning_time += extra_planning
                self.store.event(eid, 'planned', {'candidate_count': len(extra_actions)-1, 'planning_wall_seconds': extra_planning, 'followup': True})
                for action in extra_actions[1:]:
                    action = action | {'followup': True, 'planning_iterations': followup['planner_iterations']}
                    execute_action(action, followup)
            if e['backend'] == 'mujoco':
                objective = lambda b:(not b['evaluation']['success'],b['evaluation'].get('execution_duration_s',float('inf')),b['evaluation'].get('joint_path_length_rad',float('inf')),b['evaluation'].get('goal_error_m',float('inf')),b['action'].get('candidate_index',-1))
                successful = sorted([b for b in branches if b['evaluation']['success']], key=objective)
                selected = successful[0]['id'] if successful else None
                # The reported ranking and selected winner use the same measured criterion.
                ranked = sorted(branches, key=objective)
                pickup = instance.config.get('task') == 'pick_place'
                milestone = 'physical_pick_and_place' if pickup else 'reach_only'
                conclusion = {'conclusion': ('Measured physical pickup and placement found.' if selected else 'No candidate completed physical pickup and placement.') if pickup else ('Measured collision-free reach found.' if selected else 'No candidate executed a collision-free reach.'), 'milestone': milestone, 'ranked_branch_ids': [b['id'] for b in ranked], 'top_feasible_branch_ids':[b['id'] for b in successful[:3]]}
                if settings.get('adaptive_trials') and search:
                    conclusion['conclusion'] += ' Search stopped: '+search['stopping_reason'].replace('_',' ')+'. Best measured feasible result; global optimality is not established.'
            else:
                selected, conclusion = backend.choose(branches)
            public_settings={k:v for k,v in settings.items() if k not in ('checkpoint','pause_seconds')}
            if e['backend'] == 'mujoco' and e['config'].get('task') == 'pick_place':
                public_settings['max_wall_seconds'] = self.max_pickup_wall_seconds
            safe_followup={k:v for k,v in followup.items() if k not in ('checkpoint','pause_seconds')} if followup else None
            e.update(status='completed', selected_branch_id=selected, result=conclusion | {'policy': reasoning, 'executed_settings': public_settings, 'followup_settings': safe_followup})
            validation_branches = list(branches)
            if search is not None:
                integrated=lambda b:bool((b['performance']['simulation_steps'] or 0)+(b['performance']['integration_calls'] or 0)) and b['performance']['measurement_complete']
                if not trial_metrics:
                    search.update(fully_simulated=sum(integrated(b) for b in branches),physics_attempts=len(branches),planning_failed=sum(b['evaluation']['status']=='planning_failure' for b in branches),verified_feasible=sum(b['evaluation']['success'] for b in branches),physics_rejected=sum(not b['evaluation']['success'] and integrated(b) for b in branches))
                e['result']['search']=search
            if selected and settings.get('execute_selected'):
                winner = next(b for b in validation_branches if b['id']==selected)
                executed = execute_action(winner['action'],settings,role='authoritative_execution')
                if cancellation.is_set():
                    raise InterruptedError('cancelled during authoritative execution')
                e['result']['execution_branch_id']=executed['id']
                e['result']['execution_evaluation']=executed['evaluation']
                # A successful validation never hides a failed live execution.
                if executed['evaluation']['success']:
                    with self.lock, self.store.connect() as db:
                        current = self.store.get('worlds',e['world_id'],db)
                        if current['revision'] != e['revision']:
                            raise Conflict('environment changed during authoritative execution')
                        current['state']=backend.commit(executed['final_state']);current['revision']+=1
                        self.store.put('worlds',current,db)
                        e['result']['executed_world_revision']=current['revision']
                    self.publish_live(eid,e['world_id'],'verified',executed['trace'][-1])
                    self.store.event(eid,'progress',{'stage':'task_verified','evaluation':executed['evaluation'],
                                                   'message':'Fresh authoritative execution verified and persisted.'})
                else:
                    e['result']['conclusion']='The selected validation passed, but the fresh authoritative execution failed.'
            adapter_errors = sum(b['evaluation']['status'] == 'adapter_failure' for b in branches)
            if adapter_errors == len(branches):
                e.update(status='failed', error='all_branches_failed:adapter_failure')
            e['stale'] = self.get_world(e['world_id'])['revision'] != e['result'].get('executed_world_revision',e['revision'])
            replay = self._replay(e, branches)
            e['performance'] = {'job_wall_seconds': time.perf_counter()-wall, 'process_cpu_seconds': time.process_time()-cpu, 'queue_wait_seconds': max(0., time.time()-e['submitted_at']-(time.perf_counter()-wall)), 'planning_wall_seconds': planning_time+sum(b['performance'].get('ik_planning_seconds',0) for b in branches), 'physics_wall_seconds': sum(b['performance']['physics_wall_seconds'] or 0 for b in branches), 'candidate_count': len(branches), 'simulation_steps': sum(b['performance']['simulation_steps'] or 0 for b in branches), 'integration_calls': sum(b['performance']['integration_calls'] or 0 for b in branches), 'replay_payload_bytes': len(encode(replay).encode()), 'branch_failure_rate': sum(not b['evaluation']['success'] for b in branches)/len(branches), 'adapter_error_count': adapter_errors, 'measurement_complete': adapter_errors == 0, 'job_error_rate': float(adapter_errors > 0), 'compute': 'CPU; one worker; process CPU time includes concurrent API activity; no billed model calls under deterministic policy'}
            if trial_metrics:
                extra=branches[-1] if settings.get('execute_selected') and selected else None
                e['performance'].update(trial_metrics)
                e['performance']['simulation_steps']=trial_metrics['trial_simulation_steps']+(extra['performance']['simulation_steps'] or 0 if extra else 0)
                e['performance']['integration_calls']=trial_metrics['trial_integration_calls']+(extra['performance']['integration_calls'] or 0 if extra else 0)
                e['performance']['physics_wall_seconds']=trial_metrics['trial_physics_wall_seconds']+(extra['performance']['physics_wall_seconds'] or 0 if extra else 0)
            with self.lock, self.store.connect() as db:
                w = self.store.get('worlds', e['world_id'], db)
                e['stale'] = w['revision'] != e['result'].get('executed_world_revision',e['revision'])
                self.store.put('experiments', e, db)
                terminal = 'failed' if e['status'] == 'failed' else 'completed'
                self.store.event(eid, terminal, {'selected_branch_id': selected, 'stale': e['stale'], 'adapter_error_count': adapter_errors, 'error': e['error']}, db)
        except InterruptedError:
            e.update(status='cancelled',error=None)
            with self.store.connect() as db:
                self.store.put('experiments',e,db)
                self.store.event(eid,'cancelled',{'message':'Cancelled at a safe simulation boundary; completed branch evidence is retained.'},db)
        except Exception as exc:
            log.exception('experiment %s failed', eid)
            # Provider responses and keys are never persisted or logged.
            e.update(status='failed', error=f'experiment_failed:{type(exc).__name__}')
            e['performance'] = {'job_wall_seconds': time.perf_counter()-wall, 'process_cpu_seconds': time.process_time()-cpu, 'job_error_rate': 1.0}
            with self.store.connect() as db:
                self.store.put('experiments', e, db)
                self.store.event(eid, 'failed', {'error': e['error']}, db)

    def _bulk_trials(self, e, actions, settings, search, reference, cancellation):
        from .native_pick_place import NativePickup
        engine=NativePickup(self.backends['mujoco'].backend(e['config']),e['snapshot'])
        best=[];simulated=0;attempts=0;feasible=0;steps=0;integration_calls=0;physics=0.;last_frame=[0.]
        best_duration=float('inf');no_improvement=0;stopping_reason='candidate_exhausted'
        objective=lambda b:(not b['evaluation']['success'],b['evaluation'].get('execution_duration_s',float('inf')),
                            b['evaluation'].get('goal_error_m',float('inf')),b['action']['candidate_index'])
        def live(frame):
            now=time.perf_counter()
            if now-last_frame[0]>=.05:
                self.publish_live(e['id'],e['world_id'],'testing_candidates',frame)
                last_frame[0]=now
        from .trial_execution import trial_results
        concurrency={'peak_parallel_trials':0}
        for action,result,evaluation,final_state,timing,batch_complete in trial_results(
                engine,actions,settings,cancellation,live,self.physics_trial_workers,concurrency):
            if not settings['checkpoint']():raise InterruptedError('cancelled between physical trials')
            performance={'wall_seconds':result['physics_wall_seconds'],'physics_wall_seconds':result['physics_wall_seconds'],
                         'simulation_steps':result['simulation_steps'],'integration_calls':result.get('integration_calls',0),'measurement_complete':True,**timing}
            record={'schema_version':'vivacity.trial/1.0','candidate_index':action['candidate_index'],
                    'parent_state_reference':reference,'action':deepcopy(action),'engine':engine.engine,
                    'control_sha256':hashlib.sha256(encode(action['stages']).encode()).hexdigest(),
                    'final_state':final_state,'evaluation':evaluation,'performance':performance}
            self.store.trial(e['id'],record)
            attempts+=1
            simulated+=int(result['simulation_steps']>0);feasible+=int(evaluation['success'])
            if settings.get('adaptive_trials') and evaluation['success']:
                duration=evaluation.get('execution_duration_s',float('inf'))
                if duration < best_duration-max(.05,.01*best_duration) or best_duration==float('inf'):
                    best_duration=duration;no_improvement=0
                else:
                    no_improvement+=1
            elif settings.get('adaptive_trials') and best_duration<float('inf'):
                no_improvement+=1
            steps+=result['simulation_steps'];integration_calls+=result.get('integration_calls',0);physics+=result['physics_wall_seconds']
            branch={'schema_version':'1.0','id':uid(),'experiment_id':e['id'],'parent_state_reference':reference,
                    'initial_state':deepcopy(e['snapshot']),'action':deepcopy(action)|{'execution_role':'validation','engine':engine.engine},
                    'trace':result['trace'],'final_state':final_state,'evaluation':evaluation,'performance':performance}
            if len(best)<3 or objective(branch)<objective(best[-1]):
                best=sorted(best+[branch],key=objective)[:3]
                self.store.put('branches',branch)
                with self.lock,self.store.connect() as db:
                    w=self.store.get('worlds',e['world_id'],db)
                    w['branches'].append({'experiment_id':e['id'],'branch_id':branch['id'],'parent_state_reference':reference,'revision':e['revision']})
                    w['evaluations'].append({'branch_id':branch['id'],'evaluation':evaluation});self.store.put('worlds',w,db)
            search.update(fully_simulated=simulated,physics_attempts=attempts,physics_target=len(actions),
                          verified_feasible=feasible,physics_rejected=simulated-feasible,trial_simulation_steps=steps,
                          engine=engine.engine,retained_full_traces=len(best),physics_trial_workers=self.physics_trial_workers,
                          peak_parallel_trials=concurrency['peak_parallel_trials'])
            e['result']={'search':search,'top_feasible_branch_ids':[b['id'] for b in best if b['evaluation']['success']],
                         'conclusion':f'{simulated:,} integrated physics trials evaluated; {feasible:,} feasible.'}
            self.store.put('experiments',e)
            if settings.get('adaptive_trials') or attempts%5==0 or attempts==len(actions):
                self.store.event(e['id'],'progress',search|{'stage':'physics','message':e['result']['conclusion']})
            if cancellation.is_set():raise InterruptedError('cancelled during physical trial')
            if batch_complete and attempts<len(actions) and settings.get('adaptive_trials') and attempts>=min(5,len(actions)) and best_duration<float('inf') and no_improvement>=3:
                stopping_reason='measured_improvement_plateau'
                break
        if stopping_reason!='measured_improvement_plateau' and attempts==len(actions):
            stopping_reason='host_compute_budget' if settings.get('adaptive_trials') and len(actions)>=settings['physics_budget'] else 'candidate_exhausted'
        search.update(stopping_reason=stopping_reason,physics_attempts=attempts,fully_simulated=simulated)
        e['result']={'search':search,'top_feasible_branch_ids':[b['id'] for b in best if b['evaluation']['success']],
                     'conclusion':f'{simulated:,} integrated physics trials evaluated; {feasible:,} feasible. Search stopped: {stopping_reason.replace("_"," ")}.'}
        self.store.put('experiments',e)
        self.store.event(e['id'],'progress',search|{'stage':'physics','message':e['result']['conclusion']})
        return best,{'trial_count':attempts,'integrated_trial_count':simulated,'trial_simulation_steps':steps,'trial_integration_calls':integration_calls,
                     'trial_physics_wall_seconds':physics,'trial_failure_rate':(attempts-feasible)/max(1,attempts),
                     'trial_engine':engine.engine,'stopping_reason':stopping_reason,
                     'physics_trial_workers':self.physics_trial_workers,'peak_parallel_trials':concurrency['peak_parallel_trials']}

    def cancel(self, eid):
        self.get_experiment(eid)
        with self.lock:
            flag = self.cancel_flags.get(eid)
            if flag:
                flag.set()
        return self.get_experiment(eid)

    def publish_live(self, eid, world_id, stage, frame):
        with self.lock:
            prior = self.live_states.get(eid)
            self.live_states[eid] = {'schema_version':'vivacity.live/1.0','experiment_id':eid,
                                    'world_id':world_id,'sequence':prior['sequence']+1 if prior else 0,
                                    'timestamp_unix_s':time.time(),'stage':stage,'frame':deepcopy(frame)}
            # One frame per job, with a hard cap. Completed histories live in SQLite.
            if len(self.live_states)>32:
                self.live_states.pop(next(iter(self.live_states)))

    def live(self, eid):
        with self.lock:
            return deepcopy(self.live_states.get(eid))

    def _run_reserved(self, eid):
        # Release before the Future completes, so waiters can immediately reuse capacity.
        try:
            self._execute(eid)
        finally:
            self.capacity.release()

    def commit(self, world_id, experiment_id, branch_id):
        with self.lock, self.store.connect() as db:
            w = self.store.get('worlds', world_id, db)
            e = self.store.get('experiments', experiment_id, db)
            b = self.store.get('branches', branch_id, db)
            if e['world_id'] != world_id or b['experiment_id'] != experiment_id:
                raise Conflict('branch does not belong to this world/experiment')
            if e['revision'] != w['revision'] or e['status'] != 'completed':
                raise Conflict('branch is stale or experiment is incomplete')
            if not b['evaluation']['success']:
                raise Conflict('failed branch cannot be committed')
            w['state'] = self.backends[w['backend']].commit(b['final_state'])
            w['revision'] += 1
            self.store.put('worlds', w, db)
            return w

    def reset(self, world_id):
        with self.lock, self.store.connect() as db:
            w = self.store.get('worlds', world_id, db)
            w['state'] = deepcopy(w['initial_state']); w['revision'] += 1
            self.store.put('worlds', w, db)
            return w

    def environment(self, world_id, config):
        from .schemas import RoboticsConfig, ClothConfig
        with self.lock, self.store.connect() as db:
            w = self.store.get('worlds', world_id, db)
            expected = {'mujoco':RoboticsConfig,'cloth':ClothConfig}[w['backend']]
            if not isinstance(config, expected):
                raise ValueError('config does not match world backend')
            self.validate_import_config(config)
            instance = self.backends[w['backend']].create_world(config.model_dump(), w['seed'])
            state = self.backends[w['backend']].snapshot(instance)
            w.update(state=state, initial_state=deepcopy(state), config=state['config'], revision=w['revision']+1)
            self.store.put('worlds', w, db)
            return w

    def _replay(self, e, branches):
        return {'schema_version': '1.0', 'experiment_id': e['id'], 'backend': e['backend'], 'config': e['config'], 'stale': e['stale'], 'branches': [self.backends[e['backend']].replay(b) for b in branches]}

    def replay(self, eid):
        e = self.store.get('experiments', eid)
        e['stale'] = self.get_world(e['world_id'])['revision'] != e.get('result',{}).get('executed_world_revision',e['revision'])
        return self._replay(e, self.store.branches(eid))

    def export_branch(self, eid, bid):
        e=self.store.get('experiments',eid)
        b=self.store.get('branches',bid)
        if b['experiment_id']!=eid:
            raise Conflict('branch does not belong to this experiment')
        state=b['initial_state']
        completed=next((ev['details'].get('timestamp_unix_s') for ev in self.store.events(eid) if ev['kind']=='branch_completed' and ev['details'].get('branch_id')==bid),None)
        world_type = 'physical_pick_and_place' if e['backend']=='mujoco' and e['config'].get('task')=='pick_place' else {'mujoco':'object_pregrasp','cloth':'constrained_single_fold'}[e['backend']]
        return {'schema_version':'vivacity.branch/1.0','experiment_id':eid,'branch_id':bid,'world_type':world_type,'simulation_backend':'mujoco' if e['backend']=='cloth' else e['backend'],'simulator_version':state['version'],'initial_configuration':deepcopy(e['config']),'initial_state_reference':b['parent_state_reference'],'state_encoding':'JSON serialization of mjSTATE_INTEGRATION, not a native binary .mjb file' if e['backend'] in ('mujoco','cloth') else 'JSON numerical observations and fitted-model state','initial_state':state,'final_state':b['final_state'],'action':b['action'],'recorded_frames':b['trace'],'evaluation':b['evaluation'],'constraint_violations':b['evaluation'].get('contact_violations',[]),'success':b['evaluation']['success'],'seed':state['seed'],'configuration_sha256':hashlib.sha256(encode(e['config']).encode()).hexdigest(),'model_hash':state.get('model_hash'),'timestamps':{'submitted_unix_s':e['submitted_at'],'branch_completed_unix_s':completed},'performance':b['performance']}
