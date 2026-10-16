"""Bounded, leased autonomous sessions. Each cycle computes a new world and seed.

Sessions share the one simulation worker, never simulator state. Capability tokens
protect session-owned worlds; legacy public demo worlds remain public.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import secrets
import threading
import time
import uuid

import numpy as np

from .schemas import CreateWorld, ExperimentRequest, SessionRequest
from .storage import encode
from .control import PauseControl


class Supervisor:
    lease_seconds = 180
    max_wall_seconds = 1800

    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='vivacity-session')
        self.capacity = threading.BoundedSemaphore(2)
        self.stops = {}; self.controls = {}; self.futures = {}; self.closed = False
        with runtime.store.connect() as db:
            import json
            for row in db.execute('SELECT payload FROM sessions').fetchall():
                session = json.loads(row[0])
                if session['status'] in ('active','stopping'):
                    session.update(status='failed',error='supervisor_interrupted_by_restart')
                    runtime.store.put('sessions',session,db)

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def authorize(self, sid, token):
        s = self.runtime.store.get('sessions',sid)
        if not token or not secrets.compare_digest(s['token_hash'],self.token_hash(token)):
            raise PermissionError('session capability required')
        return s

    def authorize_world(self, world_id, token):
        with self.runtime.store.connect() as db:
            row = db.execute('SELECT session_id FROM session_worlds WHERE world_id=?',(world_id,)).fetchone()
        if row:
            self.authorize(row[0],token)

    @staticmethod
    def public(session):
        return {k:v for k,v in session.items() if k not in ('token_hash','request')}

    def get(self, sid, token, heartbeat=True):
        with self.lock:
            s = self.authorize(sid,token)
            if heartbeat and time.time()-s['last_heartbeat_unix_s']>5:
                s['last_heartbeat_unix_s']=time.time();self.runtime.store.put('sessions',s)
            control=self.controls.get(sid)
            return self.public(s) | (control.state() if control else {})

    def create(self, request, token):
        self.runtime.validate_trial_budget(request.physics_trials)
        if request.adaptive_trials:
            self.runtime.validate_trial_budget(request.physics_budget)
        from .runtime import Busy, Unavailable, Conflict
        with self.lock:
            with self.runtime.store.connect() as db:
                row=db.execute("SELECT id FROM sessions WHERE json_extract(payload,'$.token_hash')=?",(self.token_hash(token),)).fetchone()
            if row:
                prior=self.authorize(row[0],token)
                if SessionRequest.model_validate(prior['request']).model_dump()!=request.model_dump():
                    raise Conflict('session capability already used with different settings')
                return self.get(prior['id'],token)
            if self.closed:
                raise Unavailable('session supervisor is shutting down')
            if not self.capacity.acquire(blocking=False):
                raise Busy('two active sessions already own the available supervision slots')
            try:
                w = self.runtime.create_world(CreateWorld(backend=request.backend,seed=request.seed,config=request.config))
                now=time.time();sid=str(uuid.uuid4())
                max_cycles=min(request.max_cycles,2) if request.backend=='cloth' else request.max_cycles
                s={'schema_version':'vivacity.session/1.0','id':sid,'backend':request.backend,'status':'active',
                   'world_id':w['id'],'experiment_id':None,'cycle':0,'max_cycles':max_cycles,
                   'experiments':[],'world_ids':[w['id']],'conditions':[], 'error':None,
                   'started_unix_s':now,'last_heartbeat_unix_s':now,'token_hash':self.token_hash(token),
                   'request':request.model_dump()}
                with self.runtime.store.connect() as db:
                    self.runtime.store.put('sessions',s,db)
                    db.execute('INSERT INTO session_worlds(world_id,session_id) VALUES(?,?)',(w['id'],sid))
                self.stops[sid]=threading.Event()
                self.controls[sid]=PauseControl()
                future=self.executor.submit(self.run,sid)
                self.futures[sid]=future
                return self.public(s)
            except BaseException:
                self.capacity.release();raise

    def stop(self, sid, token):
        with self.lock:
            s=self.authorize(sid,token)
            flag=self.stops.get(sid)
            if flag and s['status']=='active':
                flag.set();s['status']='stopping';self.runtime.store.put('sessions',s)
                if s['experiment_id']:
                    self.runtime.cancel(s['experiment_id'])
            return self.public(s)

    def set_paused(self, sid, token, paused):
        from .runtime import Conflict
        with self.lock:
            s=self.authorize(sid,token);control=self.controls.get(sid)
            if s['status']!='active' or not control:
                raise Conflict('only an active session can be paused or resumed')
            control.pause() if paused else control.resume()
            if s['experiment_id']:
                self.runtime.store.event(s['experiment_id'],'progress',{'stage':'pause_requested' if paused else 'resumed',
                    'message':'Pausing the actual worker at its next safe boundary.' if paused else 'Continuing from preserved simulator state.'})
            return self.get(sid,token)

    def run(self, sid):
        r=self.runtime; stop=self.stops[sid];control=self.controls[sid]
        def alive():
            s=r.store.get('sessions',sid)
            bound=max(self.max_wall_seconds,7200) if s['request'].get('physics_trials') or s['request'].get('adaptive_trials') else self.max_wall_seconds
            return time.time()-s['last_heartbeat_unix_s']<=self.lease_seconds and time.time()-s['started_unix_s']<=bound
        try:
            for cycle in range(r.store.get('sessions',sid)['max_cycles']):
                if not control.checkpoint(stop,alive):break
                with self.lock:
                    s=r.store.get('sessions',sid)
                    if stop.is_set() or not alive():
                        stop.set()
                        break
                    request=s['request'];seed=(request['seed']+cycle)%2**32
                    config=deepcopy(request['config'])
                    partition='unpartitioned'
                    variation=request.get('variation',{})
                    if variation.get('enabled'):
                        from .variation import conditions
                        config,partition=conditions(config,seed,cycle,s['max_cycles'],variation)
                    if cycle:
                        rng=np.random.default_rng(seed)
                        if s['backend']=='mujoco' and config.get('task')=='pick_place' and not variation.get('enabled'):
                            center_z=(config.get('cube_half_sizes') or [config.get('cube_half_size',.025)]*3)[2]+.001
                            config['cube_position']=[float(rng.uniform(.46,.54)),float(rng.uniform(-.2,-.1)),center_z]
                            config['placement_position']=[float(rng.uniform(.46,.54)),float(rng.uniform(.12,.23)),center_z]
                        elif s['backend']=='cloth':
                            config['friction']=float(rng.uniform(.5,.9))
                        w=r.create_world(CreateWorld(backend=s['backend'],seed=seed,config=config))
                        s['world_ids'].append(w['id']);s['world_id']=w['id']
                        with r.store.connect() as db:
                            db.execute('INSERT INTO session_worlds(world_id,session_id) VALUES(?,?)',(w['id'],sid))
                    else:
                        w=r.get_world(s['world_id'])
                    s['cycle']=cycle+1
                    s['conditions'].append({'cycle':cycle+1,'seed':seed,'world_id':w['id'],
                                            'partition':partition,'configuration_sha256':hashlib.sha256(encode(w['config']).encode()).hexdigest()})
                    settings=ExperimentRequest(candidates=3,max_simulation_seconds=40,physics_trials=request.get('physics_trials',0),
                        adaptive_trials=request.get('adaptive_trials',False),
                        execute_selected=s['backend'] in ('mujoco','cloth'),realtime_execution=request['realtime_execution'],realtime_speed=request.get('realtime_speed',1.),
                        search_candidates=request['search_candidates'],physics_budget=request['physics_budget'])
                    e=r.submit(w['id'],settings,idempotency_key=f'session-{sid}-cycle-{cycle}',control=control)
                    s['experiment_id']=e['id'];s['experiments'].append(e['id']);r.store.put('sessions',s)
                    r.store.event(e['id'],'progress',{'stage':'next_experiment_started','cycle':cycle+1,'seed':seed,
                                                     'message':f'Fresh autonomous experiment {cycle+1}; recorded seed {seed}.'})
                # Polling permits cancellation and lease expiry even while queued.
                while True:
                    e=r.get_experiment(e['id'])
                    s=r.store.get('sessions',sid)
                    wall_bound=max(self.max_wall_seconds,7200) if s['request'].get('physics_trials') or s['request'].get('adaptive_trials') else self.max_wall_seconds
                    if stop.is_set() or time.time()-s['last_heartbeat_unix_s']>self.lease_seconds or time.time()-s['started_unix_s']>wall_bound:
                        stop.set();r.cancel(e['id'])
                    if e['status'] not in ('queued','running'):
                        break
                    stop.wait(.1) if not stop.is_set() else time.sleep(.1)
                if stop.is_set():
                    break
                if e['status']=='failed':
                    raise RuntimeError(e['error'] or 'experiment failed')
                # Preserve a readable result state before the next actual world.
                if stop.wait(3):
                    break
            with self.lock:
                s=r.store.get('sessions',sid)
                s['status']='stopped' if stop.is_set() else 'completed'
                r.store.put('sessions',s)
        except Exception as exc:
            with self.lock:
                s=r.store.get('sessions',sid);s.update(status='failed',error=f'supervisor_failed:{type(exc).__name__}')
                r.store.put('sessions',s)
        finally:
            with self.lock:
                control.resume()
                s=r.store.get('sessions',sid);s.update(control.state());r.store.put('sessions',s)
                self.futures.pop(sid,None);self.stops.pop(sid,None);self.controls.pop(sid,None)
            self.capacity.release()

    def close(self):
        with self.lock:
            self.closed=True
            for sid,flag in list(self.stops.items()):
                flag.set();s=self.runtime.store.get('sessions',sid)
                if s['experiment_id']:
                    self.runtime.cancel(s['experiment_id'])
        self.executor.shutdown(wait=True)
