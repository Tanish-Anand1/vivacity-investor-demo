"""Bounded asynchronous factory jobs with capability ownership and actual frames."""
from copy import deepcopy
import threading
import time
import uuid
import json
import logging
from concurrent.futures import ThreadPoolExecutor

log=logging.getLogger('uvicorn.error')

from .factory import FactoryBackend, FactorySettings, LAYOUT
from .workspace import owner
from .runtime import Busy, Conflict
from .factory_exchange import software,configuration_export,validate_import,METRICS
from .compiled import release_unused_memory
from .factory_discovery_data import QUANTITIES, scalar


class FactoryService:
    pause_lease_seconds=120.
    def __init__(self,workspace):
        self.workspace=workspace
        self.backend=FactoryBackend()
        # Share the execution lane with legacy workcells: two labs must not
        # independently allocate peak simulation memory on the small host.
        self.pool=workspace.runtime.executor
        self.lock=threading.RLock()
        self.controls={}
        self.live={}
        self.latest_states={}
        self.camera_lock=threading.Lock()
        self.report_lock=threading.Lock()
        # A single bounded numerical worker never runs on the native physics lane.
        self.discovery_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='factory-discovery')
        self.discovery_targets={}
        self.discovery_active=set()
        # Keep frequently polled metadata/pages separate from the full archive.
        # SQLite JSON traversal of a 27 MB trace can allocate hundreds of MiB.
        with workspace.store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS factory_run_index(
                    run_id TEXT PRIMARY KEY,owner TEXT NOT NULL,summary TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,final_state TEXT);
                CREATE INDEX IF NOT EXISTS factory_run_owner ON factory_run_index(owner);
                CREATE TABLE IF NOT EXISTS factory_samples(
                    run_id TEXT NOT NULL,sample_index INTEGER NOT NULL,payload TEXT NOT NULL,
                    PRIMARY KEY(run_id,sample_index));
                CREATE TABLE IF NOT EXISTS factory_discovery_points(
                    run_id TEXT NOT NULL,sample_index INTEGER NOT NULL,time_s REAL NOT NULL,values_json TEXT NOT NULL,
                    PRIMARY KEY(run_id,sample_index));
                CREATE TABLE IF NOT EXISTS factory_discoveries(
                    run_id TEXT NOT NULL,quantity TEXT NOT NULL,payload TEXT NOT NULL,
                    PRIMARY KEY(run_id,quantity));
                CREATE TABLE IF NOT EXISTS factory_relationships(
                    run_id TEXT NOT NULL,name TEXT NOT NULL,payload TEXT NOT NULL,
                    PRIMARY KEY(run_id,name));
            ''')
        # A process restart cannot resume an unrecorded native worker.
        with workspace.store.connect() as db:
            rows=db.execute("""SELECT l.owner,l.payload,l.kind FROM library_items l
                JOIN factory_run_index i ON i.run_id=l.id
                WHERE json_extract(i.summary,'$.status') IN ('running','paused','queued')
                UNION ALL SELECT owner,payload,kind FROM library_items
                WHERE (kind='factory_benchmark' OR (kind='factory_run' AND id NOT IN (SELECT run_id FROM factory_run_index)))
                AND json_extract(payload,'$.status') IN ('running','paused','queued')""").fetchall()
        for owner_id,payload,kind in rows:
            row=json.loads(payload)
            if row['status'] in ('running','paused','queued'):
                row.update(status='interrupted',error='Runtime restarted; start a new run from the saved configuration.')
                if kind=='factory_run':self._save_run(row,owner_id)
                else:workspace._put(kind,owner_id,row)

    def _save_run(self,row,owner_id):
        from .storage import encode
        if row.pop('trace_storage',None)=='sqlite_pages/1.0' and '_trace_offset' not in row:
            with self.workspace.store.connect() as db:
                row['_trace_offset']=db.execute('SELECT count(*) FROM factory_samples WHERE run_id=?',(row['id'],)).fetchone()[0]
                last=db.execute('SELECT payload FROM factory_samples WHERE run_id=? ORDER BY sample_index DESC LIMIT 1',(row['id'],)).fetchone()
            if last:row['frame']=json.loads(last[0])
        self._flush_trace(row)
        record={k:v for k,v in row.items() if not k.startswith('_') and k!='trace'}
        record.update(trace=[],trace_storage='sqlite_pages/1.0')
        with self.workspace.store.connect() as db:
            self.workspace._put('factory_run',owner_id,record,db)
            db.execute('INSERT OR REPLACE INTO factory_run_index VALUES(?,?,?,?,?)',
                       (row['id'],owner_id,encode(self._summary(row)),row.get('_trace_offset',0),
                        encode(row['final_state']) if row.get('final_state') else None))
        with self.lock:
            if row.get('_trace_offset',0)>=25 and row['status'] not in ('queued','running','paused'):
                self._schedule_discovery(row['id'],row['_trace_offset'],final=True)

    def _flush_trace(self,row):
        """Persist at most 100 pending frames; memory does not grow with a run."""
        from .storage import encode
        with self.lock:
            frames=row.get('trace',[])
            if not frames:return
            offset=row.get('_trace_offset',0)
            with self.workspace.store.connect() as db:
                db.executemany('INSERT OR REPLACE INTO factory_samples VALUES(?,?,?)',
                               ((row['id'],offset+i,encode(frame)) for i,frame in enumerate(frames)))
                db.executemany('INSERT OR REPLACE INTO factory_discovery_points VALUES(?,?,?,?)',
                               ((row['id'],offset+i,float(frame['time']),encode({name:scalar(frame,name) for name in (*QUANTITIES,'joint_acceleration','joint_velocity')}))
                                for i,frame in enumerate(frames)))
            row['_trace_offset']=offset+len(frames);row['trace']=[]
            total=row['_trace_offset']
            if total>=25:
                self._schedule_discovery(row['id'],total,final=row['status'] not in ('queued','running','paused'))

    def _schedule_discovery(self,identifier,total,final=False):
        """Coalesce arrivals: at most one pending target per run."""
        self.discovery_targets[identifier]=(total,final)
        if identifier not in self.discovery_active:
            self.discovery_active.add(identifier)
            self.discovery_pool.submit(self._discover_run,identifier)

    def _discover_run(self,identifier):
        from .factory_discovery import discover
        from .storage import encode
        try:
            while True:
                with self.lock:target,final=self.discovery_targets[identifier]
                with self.workspace.store.connect() as db:
                    rows=db.execute('SELECT time_s,values_json FROM factory_discovery_points WHERE run_id=? AND sample_index<? ORDER BY sample_index',(identifier,target)).fetchall()
                    summary=db.execute('SELECT summary FROM factory_run_index WHERE run_id=?',(identifier,)).fetchone()
                parsed=[(stamp,json.loads(values)) for stamp,values in rows]
                conditions=json.loads(summary[0]).get('config') if summary else None
                for quantity in QUANTITIES:
                    points=[(stamp,values[quantity]) for stamp,values in parsed if values.get(quantity) is not None]
                    try:
                        fit_wall=time.perf_counter();fit_cpu=time.thread_time()
                        result=discover(points,identifier,quantity,
                            families=None if final else ('constant','linear','quadratic'))
                        result['fit_stage']='final' if final else 'provisional'
                        result['source_sample_count']=len(parsed)
                        result['fit_wall_s']=time.perf_counter()-fit_wall
                        result['fit_cpu_s']=time.thread_time()-fit_cpu
                        result['updated_at']=time.time()
                        result['provenance']['experiment_conditions']=conditions
                    except Exception:
                        log.exception('factory_discovery_failed run_id=%s quantity=%s',identifier,quantity)
                        continue
                    with self.workspace.store.connect() as db:
                        db.execute('INSERT OR REPLACE INTO factory_discoveries VALUES(?,?,?)',
                                   (identifier,quantity,encode(result)))
                if final:
                    from .factory_relationships import infer_joint_torque
                    relation=infer_joint_torque(parsed,identifier)
                    relation['provenance']['experiment_conditions']=conditions
                    with self.workspace.store.connect() as db:
                        db.execute('INSERT OR REPLACE INTO factory_relationships VALUES(?,?,?)',
                                   (identifier,relation['name'],encode(relation)))
                with self.lock:
                    if self.discovery_targets.get(identifier)==(target,final):
                        self.discovery_active.discard(identifier)
                        self.discovery_targets.pop(identifier,None)
                        break
        except Exception:
            log.exception('factory_discovery_worker_failed run_id=%s',identifier)
            with self.lock:
                self.discovery_active.discard(identifier)
                self.discovery_targets.pop(identifier,None)

    def discovery(self,identifier,token):
        self._authorize_run(identifier,token)
        with self.workspace.store.connect() as db:
            rows=db.execute('SELECT quantity,payload FROM factory_discoveries WHERE run_id=?',(identifier,)).fetchall()
            count=db.execute('SELECT count(*) FROM factory_discovery_points WHERE run_id=?',(identifier,)).fetchone()[0]
            indexed=db.execute('SELECT summary FROM factory_run_index WHERE run_id=?',(identifier,)).fetchone()
            relationships=[json.loads(payload) for (payload,) in db.execute('SELECT payload FROM factory_relationships WHERE run_id=?',(identifier,))]
        series={quantity:json.loads(payload) for quantity,payload in rows}
        terminal=indexed is not None and json.loads(indexed[0])['status'] not in ('queued','running','paused')
        with self.lock:
            if count>=25 and terminal and (len(series)<len(QUANTITIES) or any(value.get('source_sample_count')!=count or value.get('fit_stage')!='final' for value in series.values())) and identifier not in self.discovery_active:
                self._schedule_discovery(identifier,count,final=True)
            processing=identifier in self.discovery_active
        return {'schema_version':'vivacity.factory-discoveries/1.0','run_id':identifier,
                'sample_count':count,'processing':processing,
                'series':series,
                'relationships':relationships,
                'source':'Measured MuJoCo frames; fitted curves are descriptive approximations.'}

    def create(self,settings,token):
        return self._create_owned(settings,owner(token))

    def _create_owned(self,settings,owner_id):
        initialized=time.perf_counter()
        settings=FactorySettings.model_validate(settings).model_dump()
        w=self.backend.create_world(settings)
        row={'id':str(uuid.uuid4()),'schema_version':'vivacity.factory-cell/1.0','created_at':time.time(),
             'software':software(),'config':settings,'world_version':LAYOUT['version'],'engine':{'name':'MuJoCo','version':self.backend.version},
             'frame':self.backend.observe(w),'initial_state':self.backend.snapshot(w),'last_run_id':None,
             'collision_geometry':self.backend.machine_collision_geometry(w)}
        row['performance']={'initialization_wall_seconds':time.perf_counter()-initialized}
        self.workspace._put('factory_cell',owner_id,row)
        return row

    def cell(self,identifier,token):return self.workspace._get(identifier,token,'factory_cell')

    def start(self,identifier,token,mode='conveyor',creator_label=None):
        cell=self.cell(identifier,token)
        if cell.get('software')!=software():raise Conflict('This cell was saved with a different controller version. Reset or apply its conditions before a new execution. Its previous results remain available.')
        if self.backend.create_world(cell['config']).model_hash!=cell['initial_state']['model_hash']:
            raise Conflict('The physical model has changed since this cell was saved. Reset or apply its conditions to create a compatible initial state. Saved results remain inspectable.')
        with self.lock:
            if any(not c['done'].is_set() for c in self.controls.values()):
                raise Busy('A factory run is already using the simulation worker.')
            self.controls.clear()
            self.live.clear()
            self.latest_states.clear()
            row={'id':str(uuid.uuid4()),'schema_version':'vivacity.factory-run/1.0','cell_id':identifier,
                 'created_at':time.time(),'creator_label':creator_label,'status':'queued','phase':'queued','config':cell['config'],
                 'software':cell.get('software'),'world_version':cell['world_version'],'engine':cell['engine'],'initial_state':cell['initial_state'],
                 'frame':cell['frame'],'trace':[],'events':[],'metrics':{},'mode':mode,'error':None}
            control={'stop':threading.Event(),'wake':threading.Event(),'done':threading.Event(),'paused':False,'emergency':False,'last_access':time.monotonic()}
            control['wake'].set()
            self.controls[row['id']]=control;self.live[row['id']]=row
            self._save_run(row,owner(token))
            cell['last_run_id']=row['id'];self.workspace._put('factory_cell',owner(token),cell)
            self.pool.submit(self._run,row['id'],owner(token),control)
            return self._summary(row)

    @staticmethod
    def _summary(row):return {k:deepcopy(v) for k,v in row.items() if not k.startswith('_') and k not in ('trace','trace_storage','initial_state','final_state','plans')}

    def _authorize_run(self,identifier,token):
        with self.workspace.store.connect() as db:
            found=db.execute("SELECT 1 FROM library_items WHERE id=? AND owner=? AND kind='factory_run'",(identifier,owner(token))).fetchone()
        if found is None:raise KeyError(identifier)

    def get(self,identifier,token,full=False):
        self._authorize_run(identifier,token)
        with self.lock:
            if identifier in self.controls:self.controls[identifier]['last_access']=time.monotonic()
            row=self.live.get(identifier)
            if row is not None:
                if not full:return self._summary(row)
                value={k:deepcopy(v) for k,v in row.items() if not k.startswith('_')}
                offset=row.get('_trace_offset',0)
                with self.workspace.store.connect() as db:
                    saved=db.execute('SELECT payload FROM factory_samples WHERE run_id=? AND sample_index<? ORDER BY sample_index',(identifier,offset)).fetchall()
                value['trace']=[json.loads(r[0]) for r in saved]+value['trace']
                return value
        if full:
            value=self.workspace._get(identifier,token,'factory_run')
            if value.pop('trace_storage',None)=='sqlite_pages/1.0':
                with self.workspace.store.connect() as db:
                    value['trace']=[json.loads(r[0]) for r in db.execute('SELECT payload FROM factory_samples WHERE run_id=? ORDER BY sample_index',(identifier,))]
            return value
        with self.workspace.store.connect() as db:
            indexed=db.execute('SELECT summary FROM factory_run_index WHERE run_id=? AND owner=?',(identifier,owner(token))).fetchone()
            if indexed:return json.loads(indexed[0])
            payload=db.execute("SELECT json_remove(payload,'$.trace','$.initial_state','$.final_state','$.plans') FROM library_items WHERE id=? AND owner=?",(identifier,owner(token))).fetchone()[0]
        return json.loads(payload)

    def record_json(self,identifier,token):
        """Stream saved sample JSON; no full archive allocation on the server."""
        from .storage import encode
        self._authorize_run(identifier,token)
        with self.lock:
            row=self.live.get(identifier)
            if row is not None:
                metadata={k:deepcopy(v) for k,v in row.items() if not k.startswith('_') and k!='trace'}
                tail=deepcopy(row['trace']);offset=row.get('_trace_offset',0)
            else:
                with self.workspace.store.connect() as db:
                    raw=db.execute('SELECT payload FROM library_items WHERE id=? AND owner=?',(identifier,owner(token))).fetchone()[0]
                metadata=json.loads(raw)
                if metadata.pop('trace_storage',None)!='sqlite_pages/1.0':return iter([raw])
                metadata.pop('trace',None);tail=[];offset=None
        def chunks():
            yield encode(metadata)[:-1]+',"trace":['
            separator='';after=-1
            while True:
                # StreamingResponse may resume the iterator on another thread.
                # Close each SQLite connection before yielding a bounded page.
                with self.workspace.store.connect() as db:
                    rows=db.execute('SELECT sample_index,payload FROM factory_samples WHERE run_id=? AND sample_index>? AND (? IS NULL OR sample_index<?) ORDER BY sample_index LIMIT 100',(identifier,after,offset,offset)).fetchall()
                if not rows:break
                yield separator+','.join(r[1] for r in rows);separator=',';after=rows[-1][0]
            if tail:yield separator+','.join(encode(frame) for frame in tail)
            yield ']}'
        return chunks()

    def command(self,identifier,token,action,kind='factory_run'):
        if kind=='factory_run':self._authorize_run(identifier,token)
        else:self.workspace._get(identifier,token,kind)
        with self.lock:
            c=self.controls.get(identifier);row=self.live.get(identifier)
            if not c or c['done'].is_set():raise Conflict('This run has ended. Start a new run to execute it again.')
            c['last_access']=time.monotonic()
            if action in ('stop','emergency_stop'):
                c['emergency']=action=='emergency_stop';c['stop'].set();c['wake'].set()
            elif action=='pause':c['paused']=True;c['wake'].clear()
            elif action=='resume':c['paused']=False;c['wake'].set()
            else:raise ValueError('unknown factory control')
            return self._summary(row)

    def samples(self,identifier,token,after=-1,limit=400):
        self._authorize_run(identifier,token)
        with self.lock:
            row=self.live.get(identifier)
            if row is not None:
                trace=row['trace'];offset=row.get('_trace_offset',0);total=offset+len(trace)
                with self.workspace.store.connect() as db:
                    saved=db.execute('SELECT payload FROM factory_samples WHERE run_id=? AND sample_index>? AND sample_index<? ORDER BY sample_index LIMIT ?',(identifier,after,offset,limit)).fetchall()
                remaining=limit-len(saved)
                tail_start=max(0,after+1-offset)
                frames=[json.loads(r[0]) for r in saved]+deepcopy(trace[tail_start:tail_start+remaining])
                return {'schema_version':'vivacity.factory-samples/1.0','run_id':identifier,'frames':frames,
                        'next_index':min(total-1,after+len(frames)),'total_samples':total,'status':row['status']}
        with self.workspace.store.connect() as db:
            indexed=db.execute('SELECT sample_count,summary FROM factory_run_index WHERE run_id=? AND owner=?',(identifier,owner(token))).fetchone()
            if indexed:
                total,summary=indexed
                rows=db.execute('SELECT payload FROM factory_samples WHERE run_id=? AND sample_index>? ORDER BY sample_index LIMIT ?',(identifier,after,limit)).fetchall()
                return {'schema_version':'vivacity.factory-samples/1.0','run_id':identifier,'frames':[json.loads(r[0]) for r in rows],
                        'next_index':min(total-1,after+len(rows)),'total_samples':total,'status':json.loads(summary)['status']}
            total,status=db.execute("SELECT json_array_length(payload,'$.trace'),json_extract(payload,'$.status') FROM library_items WHERE id=? AND owner=?",(identifier,owner(token))).fetchone()
            rows=db.execute("SELECT value FROM library_items,json_each(payload,'$.trace') WHERE library_items.id=? AND owner=? AND CAST(key AS INTEGER)>? ORDER BY CAST(key AS INTEGER) LIMIT ?",(identifier,owner(token),after,limit)).fetchall()
        return {'schema_version':'vivacity.factory-samples/1.0','run_id':identifier,'frames':[json.loads(r[0]) for r in rows],
                'next_index':min(total-1,after+len(rows)),'total_samples':total,'status':status}

    def _checkpoint(self,row,c):
        if c['stop'].is_set():return False
        if c['paused']:
            with self.lock:row.update(status='paused')
            while c['paused'] and not c['stop'].is_set():
                if time.monotonic()-c['last_access']>self.pause_lease_seconds:
                    with self.lock:row['error']='The paused experiment was stopped after two minutes without an active client. Its recorded samples remain available.'
                    c['stop'].set();c['wake'].set();break
                c['wake'].wait(.1)
            if c['stop'].is_set():return False
        with self.lock:row['status']='running'
        return True

    def _run(self,identifier,owner_id,c):
        if self.live[identifier]['mode']=='production':
            return self._production(identifier,owner_id,c)
        row=self.live[identifier];w=None;wall=time.perf_counter();steps=0
        try:
            w=self.backend.fork(row['initial_state'])
            with self.lock:row.update(status='running',phase='conveying')
            self.backend.apply_action(w,{'infeed':w.config['conveyor_speed_m_s']})
            with self.lock:row['events'].append({'time_s':0.,'kind':'conveyor_started'})
            self._frame(row,w,'conveying')
            reached=False
            while w.data.time<45.:
                if not self._checkpoint(row,c):break
                tick=time.perf_counter()
                self.backend.step(w,25);steps+=25
                if w.data.body('target').xpos[1]>=-.27 and not reached:
                    reached=True;self.backend.apply_action(w,{'infeed':0})
                    with self.lock:row['events'].append({'time_s':float(w.data.time),'kind':'station_arrival','carton_id':'target'})
                    settle_until=float(w.data.time)+.5
                self._frame(row,w,'station_ready' if reached else 'conveying')
                if reached and w.data.time>=settle_until:break
                c['stop'].wait(max(0.,.05/w.config['realtime_speed']-(time.perf_counter()-tick)))
            status='emergency_stopped' if c['emergency'] else 'stopped' if c['stop'].is_set() else 'completed' if reached else 'failed'
            with self.lock:
                row.update(status=status,phase='station_ready' if reached else status,
                           error=row.get('error') if c['stop'].is_set() else None if reached else 'The carton did not reach the station within 45 simulation seconds.')
                row['metrics']={'station_arrivals':int(reached),'simulation_steps':steps,'simulation_time_s':float(w.data.time),
                                'wall_time_s':time.perf_counter()-wall,'cartons_sorted':0,'scope':'conveyor transport acceptance only'}
                row['final_state']=self.backend.snapshot(w)
        except Exception as exc:
            with self.lock:row.update(status='failed',phase='failed',error=str(exc)[:300])
        finally:
            try:self._save_run(row,owner_id)
            finally:
                with self.lock:
                    self.live.pop(identifier,None);self.latest_states.pop(identifier,None)
                    c['done'].set()

    def _production(self,identifier,owner_id,c,pace=True,finalize_control=True,checkpoint_record=None):
        from .factory_controller import ProductionController,FactoryFault
        release_unused_memory()
        row=self.live[identifier];wall=time.perf_counter();cpu=time.thread_time();w=None;controller=None
        def event(value):
            with self.lock:row['events'].append(value)
            log.info('factory_event %s',json.dumps({'run_id':identifier,**value},separators=(',',':')))
            if w is not None:self._frame(row,w,value['kind'])
        try:
            w=self.backend.fork(row['initial_state'])
            with self.lock:row.update(status='running',phase='initializing')
            self._frame(row,w,'initializing')
            controller=ProductionController(self.backend,w,on_frame=lambda w,p:self._frame(row,w,p),
                                           on_event=event,checkpoint=lambda:self._checkpoint(checkpoint_record if checkpoint_record is not None else row,c),pace=pace)
            metrics=controller.run()
            with self.lock:row.update(status='completed',phase='completed',metrics=metrics)
        except InterruptedError:
            with self.lock:row.update(status='emergency_stopped' if c['emergency'] else 'stopped',phase='stopped')
        except Exception as exc:
            with self.lock:row.update(status='failed',phase=getattr(exc,'kind','runtime_failure'),error=str(exc)[:500])
        finally:
            if w is not None:
                self._frame(row,w,row['phase'])
                with self.lock:
                    row['final_state']=self.backend.snapshot(w)
                    row['plans']=controller.plans if controller else []
                    row['metrics'].update(cartons_sorted=controller.sorted if controller else 0,
                        station_arrivals=controller.arrivals if controller else 0,
                        simulation_steps=controller.steps if controller else 0,simulation_time_s=float(w.data.time),
                        wall_time_s=time.perf_counter()-wall,worker_cpu_time_s=time.thread_time()-cpu,
                        integration_wall_time_s=controller.physics_seconds if controller else 0.,
                        planning_wall_time_s=sum(p['planning_seconds'] for p in controller.plans) if controller else 0.,
                        candidate_plans_considered=sum(len(p['attempts']) for p in controller.plans) if controller else 0,
                        recorded_sample_count=row.get('_trace_offset',0)+len(row['trace']))
            try:self._save_run(row,owner_id)
            finally:
                with self.lock:
                    self.live.pop(identifier,None);self.latest_states.pop(identifier,None)
                    if finalize_control:c['done'].set()

    def start_benchmark(self,identifier,token,request):
        from .factory_benchmark import BenchmarkRequest,definition
        cell=self.cell(identifier,token);settings=BenchmarkRequest.model_validate(request).model_dump()
        if cell.get('software')!=software():raise Conflict('Reset or apply this cell’s conditions to use the current controller before starting a new benchmark.')
        spec=definition(cell['config'],settings)
        with self.lock:
            if any(not c['done'].is_set() for c in self.controls.values()):raise Busy('A factory experiment is already using the simulation worker.')
            self.controls.clear();self.live.clear();self.latest_states.clear()
            row={'id':str(uuid.uuid4()),'schema_version':'vivacity.factory-benchmark-record/1.0','created_at':time.time(),
                 'name':settings['name'],'status':'queued','phase':'queued','cell_id':identifier,
                 'software':software(),'definition':spec,'request':settings,'engine':cell['engine'],'controller_version':'factory-1',
                 'trials':[],'comparison':{},'error':None,'total_trials':len(spec['trial_configurations'])}
            c={'stop':threading.Event(),'wake':threading.Event(),'done':threading.Event(),'paused':False,'emergency':False,'last_access':time.monotonic()}
            c['wake'].set();self.controls[row['id']]=c;self.live[row['id']]=row
            self.workspace._put('factory_benchmark',owner(token),row)
            self.pool.submit(self._benchmark,row,owner(token),c)
            return deepcopy(row)

    def benchmark(self,identifier,token):
        row=self.workspace._get(identifier,token,'factory_benchmark')
        with self.lock:
            if identifier in self.controls:self.controls[identifier]['last_access']=time.monotonic()
            return deepcopy(self.live.get(identifier,row))

    def benchmarks(self,token):
        rows=self.workspace.list(token,'factory_benchmark')
        with self.lock:return [deepcopy(self.live.get(r['id'],r)) for r in rows]

    def history(self,token):
        with self.workspace.store.connect() as db:
            rows=db.execute('''SELECT summary FROM (
                SELECT summary FROM factory_run_index WHERE owner=?
                UNION ALL SELECT json_remove(payload,'$.trace','$.initial_state','$.final_state','$.plans')
                FROM library_items WHERE owner=? AND kind='factory_run'
                AND id NOT IN (SELECT run_id FROM factory_run_index))
                ORDER BY json_extract(summary,'$.created_at') DESC LIMIT 30''',(owner(token),owner(token))).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _benchmark(self,row,owner_id,c):
        from .factory_benchmark import comparison
        started=time.perf_counter();cpu=time.thread_time()
        try:
            for number,trial in enumerate(row['definition']['trial_configurations']):
                if not self._checkpoint(row,c):break
                cell=self._create_owned(trial['config'],owner_id);identifier=str(uuid.uuid4())
                run={'id':identifier,'schema_version':'vivacity.factory-run/1.0','cell_id':cell['id'],
                     'benchmark_id':row['id'],'created_at':time.time(),'status':'queued','phase':'queued','config':trial['config'],
                     'software':row.get('software'),'world_version':row['definition']['world_version'],'engine':row['engine'],'initial_state':cell['initial_state'],
                     'frame':cell['frame'],'trace':[],'events':[],'metrics':{},'mode':'production','error':None}
                cell['last_run_id']=identifier;self.workspace._put('factory_cell',owner_id,cell)
                with self.lock:
                    self.live[identifier]=run;row.update(phase=f'{trial["partition"]}: {trial["condition"]}',active_run_id=identifier)
                self._save_run(run,owner_id)
                self._production(identifier,owner_id,c,pace=False,finalize_control=False,checkpoint_record=row)
                result={k:trial[k] for k in ('partition','repeat','condition','config')}
                result.update(run_id=identifier,status=run['status'],failure_kind=run['phase'] if run['status']!='completed' else None,
                              metrics=run['metrics'],error=run['error'])
                with self.lock:
                    row['trials'].append(result);row['comparison']=comparison(row['trials'],row['request']['repeats'])
                    self.live.pop(identifier,None);self.latest_states.pop(identifier,None)
                self.workspace._put('factory_benchmark',owner_id,row)
                log.info('factory_trial %s',json.dumps({'benchmark_id':row['id'],'run_id':identifier,'partition':trial['partition'],'condition':trial['condition'],'status':run['status'],'simulation_steps':run['metrics'].get('simulation_steps',0)},separators=(',',':')))
                del run
                if c['stop'].is_set():break
            with self.lock:row.update(status='stopped' if c['stop'].is_set() else 'completed',phase='finished',active_run_id=None,active_frame=None)
        except Exception as exc:
            with self.lock:row.update(status='failed',phase='failed',error=str(exc)[:500])
        finally:
            with self.lock:row.update(wall_time_s=time.perf_counter()-started,worker_cpu_time_s=time.thread_time()-cpu)
            try:self.workspace._put('factory_benchmark',owner_id,row)
            finally:c['done'].set()

    def _frame(self,row,w,phase):
        frame=self.backend.observe(w)|{'phase':phase}
        with self.lock:
            self.latest_states[row['id']]=self.backend.snapshot(w)
            row['frame']=frame;row['phase']=phase
            parent=self.live.get(row.get('benchmark_id'))
            if parent is not None:parent.update(active_phase=phase,active_time_s=frame['time'],active_frame=frame)
            if frame['time']>row.get('_last_sample_time',-1):
                row['trace'].append(frame);row['_last_sample_time']=frame['time']
            if len(row['trace'])>=100 or row.get('_trace_offset',0)==0 and len(row['trace'])>=25:
                self._flush_trace(row)

    def observation(self,identifier,token,source='latest'):
        from .factory_vision import observe_camera
        cell=self.cell(identifier,token);state=cell['initial_state']
        if source=='latest' and cell['last_run_id']:
            identifier=cell['last_run_id'];self._authorize_run(identifier,token)
            with self.lock:live=deepcopy(self.latest_states.get(identifier))
            if live is not None:state=live
            else:
                with self.workspace.store.connect() as db:
                    indexed=db.execute('SELECT final_state FROM factory_run_index WHERE run_id=? AND owner=?',(identifier,owner(token))).fetchone()
                    saved=indexed[0] if indexed else db.execute("SELECT json_extract(payload,'$.final_state') FROM library_items WHERE id=? AND owner=?",(identifier,owner(token))).fetchone()[0]
                if saved:state=json.loads(saved)
        if not self.camera_lock.acquire(blocking=False):raise Busy('The simulated camera is capturing another frame. Try again shortly.')
        try:
            w=self.backend.fork(state)
            result={'camera':observe_camera(w),'ground_truth':self.backend.observe(w)}
            del w
            return result
        finally:
            release_unused_memory()
            self.camera_lock.release()

    def export_configuration(self,identifier,token,kind='configuration'):
        benchmark=self.benchmark(identifier,token) if kind=='benchmark' else None
        cell=self.cell(benchmark['cell_id'] if benchmark else identifier,token)
        if not cell.get('software'):
            raise Conflict('This record predates versioned interchange. Reset or apply its conditions to export a reproducible configuration; its recorded results remain available.')
        return configuration_export(cell,benchmark)

    def import_configuration(self,value,token):
        value=validate_import(value,self.backend)
        cell=self.create(value['configuration'],token)
        receipt={'id':str(uuid.uuid4()),'schema_version':'vivacity.factory-import/1.0','created_at':time.time(),
                 'cell_id':cell['id'],'source_file':value,'status':'configuration_imported_not_executed'}
        self.workspace._put('factory_import',owner(token),receipt)
        return {'cell':cell,'benchmark_request':value['benchmark_request'],'receipt_id':receipt['id'],
                'message':'Compatible configuration imported. No experiment has started. Run it to produce new verified results.'}

    def export_record(self,identifier,token,raw=False):
        row=self.get(identifier,token)
        if row['status'] in ('running','paused','queued'):raise Conflict('Stop or finish the run before exporting its complete record.')
        metadata={'schema_version':'vivacity.factory-record-export/1.0','units':'SI','coordinates':'right-handed Z-up; quaternion wxyz',
                'metric_definitions':METRICS,'missing_data':'null means unavailable; missing fields were not measured.',
                'provenance':'Saved backend MuJoCo execution; imported measurements are never accepted as a verified run.'}
        if raw:
            from itertools import chain
            return chain([json.dumps(metadata,allow_nan=False)[:-1]+',"record":'],self.record_json(identifier,token),['}'])
        return metadata|{'record':self.get(identifier,token,full=True)}

    def report(self,identifier,token,kind='run',archive=False,project_id=None):
        from .factory_report import report_pdf,csv_samples
        import tempfile,zipfile
        from pathlib import Path
        if not self.report_lock.acquire(blocking=False):raise Busy('Another report is being prepared. Try again shortly.')
        target=None
        try:
            if kind=='run':self._authorize_run(identifier,token)
            else:self.benchmark(identifier,token)
            # A final frame can precede the durable SQLite flush by a moment.
            with self.lock:
                finishing=[c['done'] for key,c in self.controls.items() if not c['done'].is_set() and self.live.get(key,{}).get('status') not in ('queued','running','paused')]
            for done in finishing:done.wait(5)
            with self.lock:
                if any(not c['done'].is_set() for c in self.controls.values()):raise Busy('Finish or stop active factory simulation before preparing a report.')
            release_unused_memory()
            benchmark=self.benchmark(identifier,token) if kind=='benchmark' else None
            if benchmark and not benchmark['trials']:raise Conflict('This benchmark has no recorded trials to report.')
            run=self.get(benchmark['trials'][0]['run_id'] if benchmark else identifier,token,full=True)
            if run['status'] in ('running','paused','queued'):raise Conflict('Finish or stop this run before preparing a report.')
            discovery=self.discovery(run['id'],token)
            attribution=None
            if project_id:
                from .factory_projects import FactoryProjects
                project=FactoryProjects(self).get(project_id,token)
                if not any(a['kind']==kind and a['record_id']==identifier for a in project['attachments']):raise Conflict('This result is not attached to the selected project.')
                attribution={'project':project['name']+' / '+project['team_label'],'creator':run.get('creator_label') or 'Not recorded'}
            pdf=report_pdf(run,benchmark,attribution,discovery)
            if not archive:return pdf
            handle=tempfile.NamedTemporaryFile(prefix='vivacity-report-',suffix='.zip',delete=False);target=Path(handle.name);handle.close()
            encoder=json.JSONEncoder(ensure_ascii=False,allow_nan=False,separators=(',',':'))
            with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
                z.writestr('report.pdf',pdf)
                z.writestr('discovery.json',json.dumps(discovery,allow_nan=False))
                z.writestr('README.txt','Saved MuJoCo evidence. CSV uses SI units and blank cells for unavailable measurements. Complete JSON retains every stored sample and full integration states. Definitions can be imported; measured results cannot be imported as verified executions.')
                if benchmark:z.writestr('benchmark-results.json',json.dumps(benchmark,allow_nan=False))
                try:z.writestr('definition.json',json.dumps(self.export_configuration(identifier if benchmark else run['cell_id'],token,'benchmark' if benchmark else 'configuration'),allow_nan=False))
                except Conflict as exc:z.writestr('legacy-provenance.txt',str(exc))
                ids=[t['run_id'] for t in benchmark['trials']] if benchmark else [run['id']]
                for run_id in ids:
                    if run['id']!=run_id:run=self.get(run_id,token,full=True)
                    z.writestr('runs/'+run_id+'.csv',csv_samples(run))
                    with z.open('runs/'+run_id+'.json','w') as out:
                        for chunk in encoder.iterencode(run):out.write(chunk.encode('utf-8'))
            return target
        except BaseException:
            if target is not None:target.unlink(missing_ok=True)
            raise
        finally:self.report_lock.release()

    def close(self):
        for control in self.controls.values():control['stop'].set();control['wake'].set()
        self.discovery_pool.shutdown(wait=True,cancel_futures=False)
        # Runtime.close owns shutdown of the shared executor.
