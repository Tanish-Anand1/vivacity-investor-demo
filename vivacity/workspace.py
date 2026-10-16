"""Capability-owned world/configuration library using the existing SQLite store."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
import numpy as np

from .schemas import CreateWorld, SessionRequest, EnvironmentProvenance
from .workspace_schemas import LibraryWorld, EnvironmentSpec, ExperimentConfiguration, ResolvedConfiguration, GenerationResponse
from .world_presets import prebuilt, box
from .providers import OpenAIInterpreter, WorldLabs, ProviderError, download_asset
from .storage import encode


def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()
def owner(token):return hashlib.sha256(token.encode()).hexdigest()


class WorkspaceService:
    def __init__(self,runtime,interpreter=None,worldlabs=None):
        self.runtime=runtime;self.store=runtime.store
        self.interpreter=interpreter or OpenAIInterpreter();self.worldlabs=worldlabs or WorldLabs()
        self.stop=threading.Event();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='vivacity-generation')
        self.visual_lock=threading.Lock()
        with self.store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS library_items(id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS library_owner ON library_items(owner,kind);
                CREATE TABLE IF NOT EXISTS configuration_runs(session_id TEXT PRIMARY KEY, owner TEXT NOT NULL, configuration_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS generation_keys(owner TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, job_id TEXT NOT NULL, PRIMARY KEY(owner,key));''')
            pending=[json.loads(row[0]) for row in db.execute("SELECT payload FROM library_items WHERE kind='generation'")]
        for job in pending:
            if job['status'] not in ('completed','failed'):
                if job.get('operation_id'):self.executor.submit(self._resume,job)
                else:self._stage(job,'failed','Server restarted before a provider operation was recorded; retry explicitly.')

    def close(self):self.stop.set();self.executor.shutdown(wait=True)

    def _put(self,kind,token_hash,record,db=None):
        if db is None:
            with self.store.connect() as db:return self._put(kind,token_hash,record,db)
        db.execute('INSERT INTO library_items VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                   (record['id'],token_hash,kind,encode(record)))

    def _get(self,identifier,token,kind):
        with self.store.connect() as db:
            row=db.execute('SELECT payload FROM library_items WHERE id=? AND owner=? AND kind=?',(identifier,owner(token),kind)).fetchone()
        if row is None:raise KeyError(identifier)
        return json.loads(row[0])

    def list(self,token,kind):
        with self.store.connect() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM library_items WHERE owner=? AND kind=? ORDER BY rowid DESC LIMIT 100',(owner(token),kind))]
        return [r for r in rows if not r.get('deleted')]

    def worlds(self,token):return prebuilt()+self.list(token,'world')

    def world(self,identifier,token):
        preset=next((r for r in prebuilt() if r['id']==identifier),None)
        result=preset or self._get(identifier,token,'world')
        if result.get('deleted'):raise KeyError(identifier)
        return result

    def capture(self,filename,content,token):
        from .spatial import capture_metadata
        metadata=capture_metadata(filename,content)
        root=self.runtime.imports.root/'captures';root.mkdir(exist_ok=True)
        record={'schema_version':'vivacity.capture/1.0','id':str(uuid.uuid4()),'filename':filename,
                **metadata,'sha256':hashlib.sha256(content).hexdigest(),'uploaded_bytes':len(content),'created_unix_s':time.time()}
        with self.visual_lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT COUNT(*) FROM library_items WHERE kind='capture' AND owner=?",(owner(token),)).fetchone()[0]>=20:
                raise ValueError('twenty captures per workspace; administrator storage cleanup required')
            if sum(p.stat().st_size for p in root.glob('*.bin'))+len(content)>128*1024*1024:
                raise ValueError('capture storage quota reached')
            path=root/(record['id']+'.bin');path.write_bytes(content)
            try:self._put('capture',owner(token),record,db)
            except Exception:path.unlink(missing_ok=True);raise
        return record

    def capture_path(self,identifier,token):
        record=self._get(identifier,token,'capture')
        path=self.runtime.imports.root/'captures'/(record['id']+'.bin')
        if not path.is_file():raise ValueError('capture bytes are no longer available; upload again')
        return record,path

    def visual_asset(self,identifier,token,quality=None):
        """Owned visual bytes, never provider credentials or signed URLs."""
        record=self.world(identifier,token)
        if (record.get('appearance') or {}).get('format')=='glb':
            self.runtime.imports.get(record['import_id'])
            path=self.runtime.imports.root/(record['import_id']+'.glb')
            if not path.exists():raise ProviderError('Original embedded GLB is no longer available. Import it again.')
            return path
        if not record.get('appearance') or not record.get('_visual_url'):
            raise ValueError('This environment has no supported SPZ appearance. Generate a new World Labs environment.')
        if quality is not None:
            url=(record.get('_visual_urls') or {}).get(quality)
            if not url:raise ValueError('requested visual detail is not available')
            target=self.runtime.imports.root/(record['id']+'-'+quality+'.spz')
        else:
            url=record['_visual_url'];target=self.runtime.imports.root/(record['id']+'.spz')
        with self.visual_lock:
            if not target.exists():
                content=download_asset(url)
                if not content.startswith(b'\x1f\x8b'):raise ProviderError('World Labs visual output is not a compressed SPZ file.')
                cached=list(self.runtime.imports.root.glob('*.spz'))
                if sum(p.stat().st_size for p in cached)+len(content)>128*1024*1024:
                    raise ProviderError('Generated visual asset storage quota reached.')
                temporary=target.with_suffix('.spz.tmp');temporary.write_bytes(content);temporary.replace(target)
        return target

    def thumbnail_asset(self,identifier,token):
        record=self.world(identifier,token)
        if not record.get('_thumbnail_url'):raise KeyError(identifier)
        target=self.runtime.imports.root/(record['id']+'-thumbnail.img')
        with self.visual_lock:
            if not target.is_file():
                from .spatial import capture_metadata
                content=download_asset(record['_thumbnail_url'])
                if len(content)>4*1024*1024:raise ProviderError('thumbnail exceeds 4 MiB')
                extension='png' if content.startswith(b'\x89PNG') else 'webp' if content[:4]==b'RIFF' else 'jpg'
                capture_metadata('thumbnail.'+extension,content)
                target.write_bytes(content)
        return target

    def save_world(self,spec,token,source,**fields):
        record=LibraryWorld(id=str(uuid.uuid4()),name=spec.name,description=spec.description,source=source,
            spec=spec,sha256=digest(spec.model_dump()),created_unix_s=time.time(),
            physics_scope=fields.pop('physics_scope','Static collision primitives around a standardized manipulation workbench; generated appearance is not evidence of a physical outcome.'),**fields).model_dump()
        with self.store.connect() as db:
            count=db.execute("SELECT COUNT(*) FROM library_items WHERE owner=? AND kind='world'",(owner(token),)).fetchone()[0]
            total=db.execute('SELECT COUNT(*) FROM library_items').fetchone()[0]
            if count>=50 or total>=1000:raise ValueError('workspace library storage limit reached')
            self._put('world',owner(token),record,db)
        return record

    def rename(self,identifier,token,name,kind='world'):
        record=self._get(identifier,token,kind);record['name']=name
        if kind=='world':record['spec']['name']=name
        self._put(kind,owner(token),record);return record

    def set_deleted(self,identifier,token,deleted):
        record=self._get(identifier,token,'world');record['deleted']=deleted
        self._put('world',owner(token),record);return record

    def duplicate(self,identifier,token):
        original=self.world(identifier,token);spec=EnvironmentSpec.model_validate(original['spec']);spec.name=(original['name'][:56]+' copy')
        result=self.save_world(spec,token,original['source'],import_id=original.get('import_id'),
            provider_world_id=original.get('provider_world_id'),provider_url=original.get('provider_url'),
            preview_available=original['preview_available'],physics_scope=original['physics_scope'],mapping=deepcopy(original.get('mapping')),
            appearance=deepcopy(original.get('appearance')),representations=deepcopy(original.get('representations')),
            generation=deepcopy(original.get('generation')),thumbnail_available=original.get('thumbnail_available',False))
        if original.get('_visual_url'):
            result['_visual_url']=original['_visual_url'];self._put('world',owner(token),result)
        for key in ('_visual_urls','_thumbnail_url'):
            if original.get(key):result[key]=deepcopy(original[key])
        self._put('world',owner(token),result)
        return result

    def map_import(self,record,preview,mapping,token,source='imported',**fields):
        vertices=np.asarray(preview.get('source_bounds_m') or preview['positions'],dtype=float)*mapping.scale
        if mapping.up_axis=='y':vertices=vertices[:,[0,2,1]]*np.array([1,-1,1])
        lo,hi=vertices.min(axis=0),vertices.max(axis=0)
        half=np.maximum((hi-lo)/2,.005);center=np.asarray(mapping.position_m)
        if np.max(half)>4 or np.max(np.abs(center)+half)>8:raise ValueError('mapped scene exceeds supported bounds; reduce its scale')
        geometry=box('import_collision_proxy',center.tolist(),half.tolist())
        spec=EnvironmentSpec(name=mapping.name,description='Imported static geometry with an explicitly configured conservative bounding-box collision proxy.',
                             dimensions_m=[min(16.,max(4.,float(2*(abs(center[i])+half[i])))) for i in range(3)],geometries=[geometry])
        result=self.save_world(spec,token,source,import_id=record['id'],preview_available=True,
            physics_scope='Original triangles are a visual preview. Physics uses a solid axis-aligned bounding-box proxy, centered at the chosen position and scale, plus the standard Panda workbench. A concave room must not be treated as an accurate solid-box reconstruction.',**fields)
        result['mapping']={'scale':mapping.scale,'position_m':mapping.position_m,'up_axis':mapping.up_axis,
                           'original_center_m':((lo+hi)/2).tolist(),'source_sha256':record['sha256']}
        result['representations']={'schema_version':'vivacity.representations/1.0',
            'visual':{'kind':'static mesh preview','physics_source':False},
            'geometry':{'source_sha256':record['sha256'],'original_glb_preserved':(self.runtime.imports.root/(record['id']+'.glb')).is_file(),
                        'validation':record.get('summary',{}).get('geometry_validation')},
            'physical':{'engine':'MuJoCo','collision':'explicit conservative solid box proxy',
                        'readiness':'configured_proxy','calibration':'not performed','parameters':'configured estimates',
                        'source_visual_alignment':'not independently validated'}}
        if source=='imported' and (self.runtime.imports.root/(record['id']+'.glb')).is_file():
            result['appearance']={'format':'glb','embedded_resources':True}
        self._put('world',owner(token),result)
        return result

    def resolve(self,configuration,token):
        from .registry import validate_hardware
        validate_hardware(configuration.robot_id,configuration.gripper_id,configuration.operation_id)
        scene=self.world(configuration.environment_id,token)
        if configuration.validation_trials>self.runtime.max_physics_trials:
            raise ValueError(f'This host permits at most {self.runtime.max_physics_trials} full validation trials.')
        if configuration.operation_id=='cloth_fold':
            from .schemas import PhysicsSettings
            if configuration.physics != PhysicsSettings() or configuration.object_material!='custom':
                raise ValueError('Configurable air/material/force settings currently apply to rigid robotics tasks, not the dedicated cloth fixture.')
            if scene['id']!='textile_fixture':raise ValueError('Choose the textile fixture for cloth folding.')
            world=CreateWorld(backend='cloth',seed=configuration.seed)
        else:
            if scene['id']=='textile_fixture':raise ValueError('Textile fixture requires the cloth-fold operation.')
            reach=configuration.operation_id=='reach'
            metadata=EnvironmentProvenance(id=scene['id'],name=scene['name'],version=scene['version'],source=scene['source'],
                                           source_sha256=scene['sha256'],collision_scope=scene['physics_scope'])
            config=dict(task='reach' if reach else 'pick_place',robot_model=configuration.robot_id,
                        physical_operation=configuration.operation_id if configuration.operation_id in ('sorting','assembly','stacking','insertion','machine_tending') else 'pick_place',obstacle_enabled=False,
                        cube_position=[*configuration.target_position[:2],configuration.object_half_sizes[2]+.001],placement_position=[*configuration.destination_position[:2],configuration.object_half_sizes[2]+.001],
                        cube_half_sizes=configuration.object_half_sizes,cube_mass=configuration.object_mass_kg,cube_friction=configuration.object_friction,
                        physics=configuration.physics.model_dump(),object_material=configuration.object_material,
                        scene_geometries=scene['spec']['geometries'],environment=metadata.model_dump())
            if configuration.operation_id=='stacking':config['placement_position']=[*configuration.destination_position[:2],3*configuration.object_half_sizes[2]+.001]
            if configuration.operation_id=='sorting':
                value=configuration.object_mass_kg if configuration.sort_property=='mass' else configuration.object_half_sizes[0]*2
                config['sorting_rule']={'property':configuration.sort_property,'threshold':configuration.sort_threshold}
                if value<configuration.sort_threshold:config['placement_position']=[*configuration.alternate_destination_position[:2],configuration.object_half_sizes[2]+.001]
            if reach:config['target_position']=[configuration.destination_position[0],configuration.destination_position[1],.22]
            world=CreateWorld(backend='mujoco',seed=configuration.seed,config=config)
        adaptive=world.backend=='mujoco' and world.config.task=='pick_place' and configuration.trial_mode=='adaptive'
        fixed=world.backend=='mujoco' and world.config.task=='pick_place' and configuration.trial_mode=='fixed'
        session=SessionRequest(**world.model_dump(),variation=configuration.variation,
            max_cycles=configuration.randomization_cycles if configuration.operation_id=='randomized_manipulation' or configuration.variation.enabled else 1,
            realtime_speed=configuration.realtime_speed,realtime_execution=True,adaptive_trials=adaptive,
            physics_trials=configuration.validation_trials if fixed else 0,
            search_candidates=configuration.validation_trials if fixed else 256,
            physics_budget=configuration.validation_trials)
        return ResolvedConfiguration(world=world,session=session,provenance={'environment':scene['sha256'],'environment_version':scene['version'],
             'robot_id':configuration.robot_id,'gripper_id':configuration.gripper_id,'operation_id':configuration.operation_id,
             'configuration_sha256':digest(configuration.model_dump()),'seed':configuration.seed})

    def save_configuration(self,configuration,token):
        self.resolve(configuration,token)
        record={'schema_version':'vivacity.saved-configuration/1.0','id':str(uuid.uuid4()),'configuration':configuration.model_dump(),
                'created_unix_s':time.time(),'sha256':digest(configuration.model_dump()),'deleted':False}
        if len(self.list(token,'configuration'))>=100:raise ValueError('configuration quota reached')
        self._put('configuration',owner(token),record);return record

    def configuration(self,identifier,token):return self._get(identifier,token,'configuration')

    def start_run(self,identifier,token,actual_config=None):
        import secrets
        record=self.configuration(identifier,token)
        resolved=self.resolve(ExperimentConfiguration.model_validate(record['configuration']),token)
        if actual_config is not None:
            actual=CreateWorld(backend=resolved.world.backend,seed=resolved.world.seed,config=actual_config)
            resolved.world=actual;resolved.session.config=actual.config
        resolved.provenance['execution_configuration_sha256']=digest(resolved.session.model_dump())
        capability=secrets.token_urlsafe(36)
        session=self.runtime.supervisor.create(resolved.session,capability)
        with self.store.connect() as db:
            db.execute('INSERT INTO configuration_runs VALUES(?,?,?,?)',(session['id'],owner(token),identifier,
                        encode({'session_id':session['id'],'configuration_id':identifier,'provenance':resolved.provenance,'initial_configuration':resolved.world.model_dump(),
                                'created_unix_s':time.time(),'capability':capability})))
        return {'session':session,'session_token':capability}

    def runs(self,token):
        with self.store.connect() as db:
            records=[json.loads(r[0]) for r in db.execute('SELECT payload FROM configuration_runs WHERE owner=? ORDER BY rowid DESC LIMIT 100',(owner(token),))]
        result=[]
        for r in records:
            session=self.runtime.supervisor.get(r['session_id'],r['capability'])
            experiments=[self.runtime.get_experiment(eid) for eid in session['experiments']]
            entries=[];robustness_inputs=[]
            for experiment in experiments:
                branches=self.store.branches(experiment['id'])
                # Public experiment responses omit config. Reports use the
                # persisted execution inputs, not the current editable world.
                executed=self.store.get('experiments',experiment['id'])['config']
                robustness_inputs.append((experiment|{'config':executed},[{k:b[k] for k in ('id','evaluation')} for b in branches]))
                measured=[b for b in branches if b['action'].get('execution_role')!='authoritative_execution']
                with self.store.connect() as db:
                    total,successes=db.execute("SELECT COUNT(*),COALESCE(SUM(json_extract(payload,'$.evaluation.success')),0) FROM trials WHERE experiment_id=?",(experiment['id'],)).fetchone()
                if not total:total=len(measured);successes=sum(bool(b['evaluation']['success']) for b in measured)
                entries.append({'experiment':experiment,'evaluations':[{'branch_id':b['id'],'evaluation':b['evaluation'],'performance':b['performance']} for b in measured],
                                'validation_count':total,'successful_validations':successes,'success_rate':successes/total if total else None,
                                'energy_joules':None,'energy_scope':'Energy accounting is not implemented.'})
            from .variation import report
            result.append({k:v for k,v in r.items() if k!='capability'}|{'session':session,'experiments':entries,
                'robustness':report(robustness_inputs,session['conditions'])})
        return result

    def compare_measurements(self,sid,request,token):
        with self.store.connect() as db:
            row=db.execute('SELECT payload FROM configuration_runs WHERE session_id=? AND owner=?',(sid,owner(token))).fetchone()
        if row is None:raise KeyError(sid)
        saved=json.loads(row[0]);session=self.runtime.supervisor.get(sid,saved['capability'])
        if request.experiment_id not in session['experiments']:raise ValueError('experiment is not part of this owned run')
        experiment=self.runtime.get_experiment(request.experiment_id)
        if experiment['status']!='completed':raise ValueError('measurements require a completed simulation')
        branch=self.store.get('branches',request.branch_id)
        if branch['experiment_id']!=request.experiment_id:raise ValueError('branch is not part of this experiment')
        samples=[]
        for frame in branch['trace']:
            body=next((b for b in frame.get('body_transforms',[]) if b['name']=='target'),None)
            if body:samples.append([frame['time'],*body['position']])
        if len(samples)<2:raise ValueError('this branch has no recorded object trajectory')
        simulated=np.asarray(samples);observed=np.asarray([[p.time_s+request.time_offset_s,*p.position_m] for p in request.samples])
        inside=(observed[:,0]>=simulated[0,0])&(observed[:,0]<=simulated[-1,0])
        matched=observed[inside]
        if len(matched)<2:raise ValueError('at least two observations must overlap the recorded simulation; no extrapolation is performed')
        predicted=np.column_stack([np.interp(matched[:,0],simulated[:,0],simulated[:,i]) for i in range(1,4)])
        errors=np.linalg.norm(predicted-matched[:,1:],axis=1)
        record={'schema_version':'vivacity.measurement-comparison/1.0','id':str(uuid.uuid4()),'created_unix_s':time.time(),
            'session_id':sid,'experiment_id':request.experiment_id,'branch_id':request.branch_id,
            'source_label':request.source_label,'source_kind':request.source_kind,'coordinate_system':request.coordinate_system,
            'time_offset_s':request.time_offset_s,'input_sha256':digest(request.model_dump()),'matched_samples':len(matched),
            'excluded_samples':len(observed)-len(matched),'rmse_position_m':float(np.sqrt(np.mean(errors**2))),
            'max_position_error_m':float(errors.max()),'mean_position_error_m':float(errors.mean()),
            'observed_displacement_m':(matched[-1,1:]-matched[0,1:]).tolist(),
            'simulated_displacement_m':(predicted[-1]-predicted[0]).tolist(),
            'overlap_duration_s':float(matched[-1,0]-matched[0,0]),'residuals_m':errors.tolist(),
            'samples':request.model_dump()['samples'],'simulated_positions_m':predicted.tolist(),
            'scope':'User-supplied object positions in runtime meters, Z-up, linearly interpolated recorded MuJoCo states. Source authenticity and hardware predictive accuracy are not independently verified. No automatic spatial calibration, robot/contact alignment or parameter fitting.'}
        if len(self.list(token,'measurement_comparison'))>=30:raise ValueError('measurement comparison quota reached')
        self._put('measurement_comparison',owner(token),record);return record

    def _stage(self,job,status,message=None):
        job['status']=status;job['updated_unix_s']=time.time()
        if status=='failed':job['error']=message or 'Generation could not complete.'
        job['events'].append({'stage':status,'timestamp_unix_s':time.time(),'message':message or status})
        self._put('generation',job['_owner'],job)

    def generation(self,identifier,token):
        record=self._get(identifier,token,'generation')
        return GenerationResponse.model_validate({k:v for k,v in record.items() if not k.startswith('_')}).model_dump()

    def generate(self,request,token,key):
        if not os.getenv('OPENAI_API_KEY'):raise ProviderError('OpenAI is not configured on the server.')
        if request.provider=='worldlabs' and not os.getenv('WORLDLABS_API_KEY'):raise ProviderError('World Labs is not configured on the server.')
        for reference in request.inputs:
            capture,_=self.capture_path(reference.capture_id,token)
            if capture['kind']!=('video' if request.input_type=='video' else 'image'):
                raise ValueError('capture kind does not match the requested generation input')
            if request.input_type=='panorama':
                width,height=capture['dimensions_px']
                if abs(width/height-2)>.02:raise ValueError('panorama must be a 2:1 equirectangular image')
        fingerprint=digest(request.model_dump());hashed=owner(token)
        from .runtime import Busy,Conflict
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT fingerprint,job_id FROM generation_keys WHERE owner=? AND key=?',(hashed,key)).fetchone()
            if prior:
                if prior[0]!=fingerprint:raise Conflict('generation key already used with different input')
                return self.generation(prior[1],token)
            jobs=[json.loads(r[0]) for r in db.execute("SELECT payload FROM library_items WHERE kind='generation'")]
            if any(j['status'] not in ('completed','failed') for j in jobs):raise Busy('one world generation is already active')
            if sum(j['created_unix_s']>time.time()-86400 for j in jobs)>=int(os.getenv('VIVACITY_GENERATIONS_PER_DAY','4')):
                raise Busy('the server daily generation budget has been reached')
            now=time.time();job=GenerationResponse(id=str(uuid.uuid4()),status='queued',provider=request.provider,prompt=request.prompt,
                seed=request.seed,model=request.model,input_type=request.input_type,inputs=request.inputs,
                created_unix_s=now,updated_unix_s=now).model_dump()|{'_owner':hashed,'_token':token}
            self._put('generation',hashed,job,db)
            db.execute('INSERT INTO generation_keys VALUES(?,?,?,?)',(hashed,key,fingerprint,job['id']))
        self.executor.submit(self._run,job)
        return self.generation(job['id'],token)

    def _run(self,job):
        try:
            self._stage(job,'interpreting','OpenAI is interpreting the prompt into a bounded scene specification.')
            spec,provenance=self.interpreter.environment(job['prompt']);job['interpretation']=spec.model_dump();job['_interpretation_provenance']=provenance
            if job['provider']=='openai':
                record=self.save_world(spec,job['_token'],'openai')
                job['world_id']=record['id'];self._stage(job,'completed','OpenAI structured primitive scene saved. This is not a World Labs generation.');return
            self._stage(job,'generating','Submitting a private World Labs generation request.')
            if job.get('input_type','text')=='text':
                operation=self.worldlabs.generate(job['prompt'],spec.name,job['seed'],job['model'])
            else:
                contents=[];job['_capture_provenance']=[]
                for ref in job['inputs']:
                    record,path=self.capture_path(ref['capture_id'],job['_token'])
                    media_id=self.worldlabs.upload_capture(record['filename'],record['kind'],record['extension'],path.read_bytes())
                    contents.append({'source':'media_asset','media_asset_id':media_id})
                    job['_capture_provenance'].append(record|{'provider_media_asset_id':media_id,'azimuth_deg':ref.get('azimuth_deg')})
                kind=job['input_type'];world_prompt={'type':'image' if kind=='panorama' else kind,'text_prompt':job['prompt']}
                if kind=='multi-image':world_prompt['multi_image_prompt']=[{'content':content,**({'azimuth':ref['azimuth_deg']} if ref.get('azimuth_deg') is not None else {})} for content,ref in zip(contents,job['inputs'])]
                elif kind=='video':world_prompt['video_prompt']=contents[0]
                else:world_prompt.update(image_prompt=contents[0],is_pano=kind=='panorama')
                operation=self.worldlabs.generate(job['prompt'],spec.name,job['seed'],job['model'],world_prompt)
            from .providers import identifier
            identifier(operation.get('operation_id'));job['operation_id']=operation['operation_id'];self._stage(job,'generating','World Labs operation accepted; polling its actual status.')
            self._poll(job)
        except Exception as exc:self._stage(job,'failed',str(exc) if isinstance(exc,(ProviderError,ValueError)) else 'Generation failed; no successful world was fabricated.')

    def _resume(self,job):
        try:self._poll(job)
        except Exception as exc:self._stage(job,'failed',str(exc) if isinstance(exc,(ProviderError,ValueError)) else 'Provider operation could not be resumed.')

    def retry_retrieval(self,identifier,token):
        job=self._get(identifier,token,'generation')
        if job['status']!='failed' or not job.get('operation_id'):
            raise ValueError('only an existing failed provider retrieval can be resumed without a new generation')
        if any(j['status'] not in ('failed','completed') for j in self.list(token,'generation')):
            raise ValueError('a generation is already active')
        job['error']=None;self._stage(job,'generating','Resuming the existing World Labs operation; no new generation is submitted.')
        self.executor.submit(self._resume,job)
        return self.generation(identifier,token)

    def _poll(self,job):
        deadline=time.monotonic()+900
        while not self.stop.is_set() and time.monotonic()<deadline:
            result=self.worldlabs.operation(job['operation_id'])
            if result.get('done'):
                job['provider_cost_credits']=(result.get('cost') or {}).get('total_credits')
                if result.get('error'):raise ProviderError('World Labs reported generation failure; no world was saved.')
                response=result.get('response') or {};world_id=response.get('world_id') or response.get('id')
                if not world_id:raise ProviderError('World Labs completed without a world identifier.')
                world=self.worldlabs.world(world_id)
                world=world.get('world',world)
                assets=world.get('assets') or {};mesh=assets.get('mesh') or {}
                url=mesh.get('collider_mesh_url') or mesh.get('full_res_mesh_url')
                if not url:raise ProviderError('World Labs produced no compatible collider mesh. Gaussian splats alone are not collision geometry.')
                self._stage(job,'receiving','Retrieving and validating the actual generated collider mesh.')
                content=download_asset(url)
                record=self.runtime.imports.create('worldlabs-collider.glb',content,reduce_preview=True)
                preview=self.runtime.imports.get(record['id'],preview=True)
                from .workspace_schemas import ImportMapping
                span=np.ptp(np.asarray(preview.get('source_bounds_m') or preview['positions'],dtype=float),axis=0)
                scale=min(1.,2./max(float(np.max(span)),.001))
                library=self.map_import(record,preview,ImportMapping(name=world.get('display_name') or job['interpretation']['name'],scale=scale),job['_token'],'worldlabs',
                    provider_world_id=world_id,provider_url=world.get('world_marble_url'))
                library['description']=assets.get('caption') or job['interpretation']['description']
                splats=assets.get('splats') or {}
                urls=splats.get('spz_urls') or {}
                visual_url=urls.get('500k') or urls.get('100k')
                if not visual_url:raise ProviderError('World Labs returned collision geometry but no supported visual SPZ asset. No primitive visual substitute was saved.')
                from .providers import asset_url
                asset_url(visual_url)
                library['appearance']={'format':'spz','quality':'500k' if urls.get('500k') else '100k',
                    'qualities':[quality for quality in ('100k','500k') if urls.get(quality)],
                    'semantics':splats.get('semantics_metadata'),'coordinate_system':'marble_raw_opencv',
                    'metric_scale_verified':bool(splats.get('semantics_metadata'))}
                library['_visual_url']=visual_url
                library['_visual_urls']={quality:asset_url(urls[quality]) for quality in ('100k','500k') if urls.get(quality)}
                library['representations']['visual']={'kind':'Gaussian splats','format':'SPZ','qualities':list(library['_visual_urls']),
                    'coordinates':'Marble raw OpenCV','semantics':splats.get('semantics_metadata'),'physics_source':False}
                library['generation']={'provider':'worldlabs','job_id':job['id'],'operation_id':job['operation_id'],
                    'source_prompt':job['prompt'],'input_type':job.get('input_type','text'),
                    'inputs':job.get('_capture_provenance',[]),'geometry_origin':'generated/inferred from observations; not a measured digital twin',
                    'model':job['model'],'seed':job['seed'],'provider_cost_credits':job['provider_cost_credits'],
                    'processing_status':'received','validation_status':'bounded geometry checks; explicit proxy physics; uncalibrated'}
                if assets.get('thumbnail_url'):
                    library['_thumbnail_url']=asset_url(assets['thumbnail_url']);library['thumbnail_available']=True
                self._put('world',job['_owner'],library)
                self.visual_asset(library['id'],job['_token'],'100k' if urls.get('100k') else '500k')
                if library['thumbnail_available']:
                    try:self.thumbnail_asset(library['id'],job['_token'])
                    except (ProviderError,ValueError):
                        library['thumbnail_available']=False;self._put('world',job['_owner'],library)
                job['world_id']=library['id'];job['provider_cost_credits']=(result.get('cost') or {}).get('total_credits')
                self._stage(job,'completed','World Labs colored SPZ appearance and separate collision mesh retrieved. Review the conservative collision mapping before experimentation.');return
            job['updated_unix_s']=time.time();self._put('generation',job['_owner'],job)
            self.stop.wait(5.)
        raise ProviderError('Generation polling stopped or exceeded 15 minutes; the provider operation ID is retained and never automatically resubmitted.')
