"""Bounded imports. Native compilation requires an explicit isolated probe.

Static glTF triangles are decoded into a trusted preview representation. XML
and bundles are inspected without extracting files, resolving entities, loading
native plugins or accessing their resource paths on disk. A separate disposable
worker compiles scoped in-memory data only after an explicit verification request.
"""
import base64
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import stat
import struct
import threading
import time
import uuid
import zipfile
from xml.etree import ElementTree as ET
import numpy as np

MAX_UPLOAD=16*1024*1024
MAX_PROVIDER_ASSET=64*1024*1024
MAX_EXPANDED=32*1024*1024
MAX_VERTICES=100000
EXTENSIONS={'.glb','.gltf','.bin','.xml','.mjcf','.urdf','.png','.jpg','.jpeg','.json','.obj','.stl'}


def safe_name(name):
    if not isinstance(name,str) or len(name)>180 or '\\' in name or ':' in name or '\x00' in name:raise ValueError('invalid asset path')
    p=PurePosixPath(name)
    if p.is_absolute() or any(v in ('.','..','') for v in name.split('/')):raise ValueError('unsafe asset path')
    return str(p)


def decode_json(data):
    def constant(_):raise ValueError('non-finite JSON number')
    try:return json.loads(data,parse_constant=constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:raise ValueError('malformed JSON') from exc


def integer(v,maximum):
    if type(v) is not int or not 0<=v<=maximum:raise ValueError('integer outside resource bounds')
    return v


def vector(v,n):
    if not isinstance(v,list) or len(v)!=n:raise ValueError('invalid geometry vector')
    a=np.asarray(v,dtype=float)
    if not np.isfinite(a).all() or np.max(np.abs(a))>1e5:raise ValueError('non-finite or excessive geometry')
    return a


def resource(uri,files):
    if not isinstance(uri,str):raise ValueError('invalid resource reference')
    if uri.startswith('data:'):
        header,sep,data=uri.partition(',')
        if not sep or header not in ('data:application/octet-stream;base64','data:application/gltf-buffer;base64','data:image/png;base64','data:image/jpeg;base64'):raise ValueError('unsupported embedded resource')
        try:result=base64.b64decode(data,validate=True)
        except ValueError as exc:raise ValueError('malformed embedded resource') from exc
        if len(result)>MAX_UPLOAD:raise ValueError('embedded resource exceeds limit')
        return result
    name=safe_name(uri)
    if name not in files:raise ValueError('external or missing resource; use an embedded glTF or manifest ZIP')
    return files[name]


def unpack(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries=z.infolist()
            if len(entries)>64:raise ValueError('bundle exceeds 64 entries')
            total=0;files={}
            for item in entries:
                name=safe_name(item.filename.rstrip('/') if item.is_dir() else item.filename)
                if item.flag_bits&1 or stat.S_ISLNK(item.external_attr>>16):raise ValueError('encrypted entries and symbolic links are unsupported')
                if item.is_dir():continue
                if PurePosixPath(name).suffix.lower() not in EXTENSIONS:raise ValueError('unsupported bundle extension')
                total+=item.file_size
                if total>MAX_EXPANDED or item.file_size>MAX_UPLOAD or item.file_size/max(1,item.compress_size)>100:raise ValueError('bundle exceeds expansion limits')
                if name in files:raise ValueError('duplicate bundle path')
                files[name]=z.read(item)
            manifest=decode_json(files.get('manifest.json',b'{}'))
            if not isinstance(manifest,dict) or set(manifest)!={'entrypoint'}:raise ValueError('ZIP requires manifest.json with only an entrypoint')
            entry=safe_name(manifest['entrypoint'])
            if entry not in files:raise ValueError('manifest entrypoint missing')
            # Relative resources are scoped to the entrypoint directory.
            parent=str(PurePosixPath(entry).parent)
            resources={k[len(parent)+1:]:v for k,v in files.items() if parent!='.' and k.startswith(parent+'/')} if parent!='.' else files
            return entry,files[entry],resources,{'bundle_entries':len(files),'expanded_bytes':total}
    except (zipfile.BadZipFile,RuntimeError) as exc:raise ValueError('malformed ZIP bundle') from exc


def gltf_preview(data,extension,files,reduce_preview=False):
    binary=None
    if extension=='.glb':
        if len(data)<20:raise ValueError('truncated GLB')
        magic,version,length=struct.unpack_from('<4sII',data)
        if magic!=b'glTF' or version!=2 or length!=len(data):raise ValueError('invalid GLB header')
        offset=12;chunks=[]
        while offset<len(data):
            if offset+8>len(data):raise ValueError('truncated GLB chunk')
            size,kind=struct.unpack_from('<II',data,offset);offset+=8
            if size%4 or offset+size>len(data):raise ValueError('invalid GLB chunk size')
            chunks.append((kind,data[offset:offset+size]));offset+=size
        if len(chunks) not in (1,2) or chunks[0][0]!=0x4E4F534A or len(chunks)==2 and chunks[1][0]!=0x004E4942:raise ValueError('unsupported GLB chunks')
        doc=decode_json(chunks[0][1]);binary=chunks[1][1] if len(chunks)==2 else None
    else:doc=decode_json(data)
    if not isinstance(doc,dict) or doc.get('asset',{}).get('version')!='2.0':raise ValueError('expected glTF 2.0')
    if doc.get('extensionsUsed') or doc.get('extensionsRequired') or doc.get('animations') or doc.get('skins'):raise ValueError('extensions, animation and skinning are not supported by this static preview')
    def inspect(value,depth=0):
        if depth>32:raise ValueError('glTF nesting limit exceeded')
        if isinstance(value,dict):
            for key,v in value.items():
                if key=='uri':resource(v,files)
                if key=='extensions':raise ValueError('unsupported glTF extension')
                inspect(v,depth+1)
        elif isinstance(value,list):
            for v in value:inspect(v,depth+1)
    inspect(doc)
    buffers=[]
    for i,b in enumerate(doc.get('buffers',[])):
        raw=resource(b['uri'],files) if 'uri' in b else binary if i==0 else None
        length=integer(b.get('byteLength'),MAX_PROVIDER_ASSET if reduce_preview else MAX_UPLOAD)
        if raw is None or length>len(raw) or len(raw)-length>3:raise ValueError('invalid glTF buffer length')
        buffers.append(raw[:length])
    if sum(map(len,buffers))>(MAX_PROVIDER_ASSET if reduce_preview else MAX_EXPANDED):raise ValueError('buffer memory limit exceeded')
    accessors=doc.get('accessors',[]);views=doc.get('bufferViews',[])
    if len(accessors)>1024 or len(views)>1024:raise ValueError('accessor limit exceeded')
    def read(index,positions=False):
        a=accessors[integer(index,len(accessors)-1)]
        if 'sparse' in a or a.get('normalized'):raise ValueError('sparse/normalized geometry unsupported')
        source_limit=1000000 if reduce_preview else MAX_VERTICES
        count=integer(a['count'],source_limit if positions else source_limit*6)
        if positions and (a['componentType']!=5126 or a['type']!='VEC3'):raise ValueError('positions must be float32 VEC3')
        if not positions and (a['componentType'] not in (5121,5123,5125) or a['type']!='SCALAR'):raise ValueError('indices must be unsigned scalar')
        dtype={5126:'<f4',5121:'u1',5123:'<u2',5125:'<u4'}[a['componentType']];width=3 if positions else 1;item=np.dtype(dtype).itemsize
        v=views[integer(a['bufferView'],len(views)-1)];raw=buffers[integer(v['buffer'],len(buffers)-1)]
        start=integer(v.get('byteOffset',0),len(raw));size=integer(v['byteLength'],len(raw));inner=integer(a.get('byteOffset',0),size);stride=integer(v.get('byteStride',width*item),252)
        if stride<width*item or stride%item or (start+inner)%item or start+size>len(raw) or inner+(count-1)*stride+width*item>size:raise ValueError('accessor outside buffer or misaligned')
        return np.ndarray((count,width),dtype=dtype,buffer=raw,offset=start+inner,strides=(stride,item)).copy()
    nodes=doc.get('nodes',[]);meshes=doc.get('meshes',[])
    if len(nodes)>512 or len(meshes)>256:raise ValueError('scene complexity limit exceeded')
    positions=[];indices=[];visited=set();active=set();vertex_count=0;triangle_count=0;source_bounds=[]
    def walk(index,parent,depth=0):
        nonlocal vertex_count,triangle_count
        index=integer(index,len(nodes)-1)
        if depth>32 or index in active or index in visited:raise ValueError('cyclic/shared node hierarchy unsupported')
        active.add(index);visited.add(index);node=nodes[index]
        if 'matrix' in node:matrix=vector(node['matrix'],16).reshape(4,4,order='F')
        else:
            q=vector(node.get('rotation',[0,0,0,1]),4)
            if abs(np.linalg.norm(q)-1)>1e-4:raise ValueError('invalid node quaternion')
            from scipy.spatial.transform import Rotation
            matrix=np.eye(4);matrix[:3,:3]=Rotation.from_quat(q).as_matrix()@np.diag(vector(node.get('scale',[1,1,1]),3));matrix[:3,3]=vector(node.get('translation',[0,0,0]),3)
        if not np.allclose(matrix[3],[0,0,0,1]):raise ValueError('non-affine node matrix unsupported')
        matrix=parent@matrix
        if 'mesh' in node:
            mesh=meshes[integer(node['mesh'],len(meshes)-1)]
            for primitive in mesh.get('primitives',[]):
                if primitive.get('mode',4)!=4 or primitive.get('targets'):raise ValueError('only static triangle primitives supported')
                p=read(primitive['attributes']['POSITION'],True);ind=read(primitive['indices']).flatten() if 'indices' in primitive else np.arange(len(p))
                if len(ind)%3 or len(ind) and int(ind.max())>=len(p):raise ValueError('invalid triangle indices')
                transformed=p@matrix[:3,:3].T+matrix[:3,3]
                if not np.isfinite(transformed).all() or transformed.size and np.max(np.abs(transformed))>1e5:raise ValueError('invalid transformed vertices')
                if len(transformed):source_bounds.extend([transformed.min(axis=0),transformed.max(axis=0)])
                if reduce_preview:
                    triangles=ind.reshape(-1,3)
                    remaining=max(1,25000-triangle_count)
                    triangles=triangles[::max(1,int(np.ceil(len(triangles)/remaining)))]
                    used,remapped=np.unique(triangles,return_inverse=True)
                    transformed=transformed[used];p=transformed;ind=remapped.reshape(-1)
                vertex_count+=len(p);triangle_count+=len(ind)//3
                if vertex_count>MAX_VERTICES or triangle_count>MAX_VERTICES:raise ValueError('decoded preview exceeds geometry limit')
                positions.extend(transformed.tolist());indices.extend((ind+vertex_count-len(p)).tolist())
        for child in node.get('children',[]):walk(child,matrix,depth+1)
        active.remove(index)
    scenes=doc.get('scenes',[])
    if not scenes:raise ValueError('glTF scene is required')
    for root in scenes[integer(doc.get('scene',0),len(scenes)-1)].get('nodes',[]):walk(root,np.eye(4))
    if not indices:raise ValueError('scene contains no supported triangles')
    return {'positions':positions,'indices':indices,'vertex_count':vertex_count,'triangle_count':triangle_count,'source_bounds_m':[np.min(source_bounds,axis=0).tolist(),np.max(source_bounds,axis=0).tolist()], 'coordinate_system':'glTF Y-up; original scene transforms applied; camera framing is display-only'},['Static triangles only. Materials, textures, animation and physical properties are not imported.']


def inspect_xml(data,extension,files):
    if len(data)>1024*1024:raise ValueError('XML exceeds 1 MiB')
    try:text=data.decode('utf-8-sig')
    except UnicodeError as exc:raise ValueError('XML must use UTF-8 encoding') from exc
    if '\x00' in text:raise ValueError('XML must use UTF-8 encoding')
    upper=text.upper()
    if '<!DOCTYPE' in upper or '<!ENTITY' in upper or '<?XML-STYLESHEET' in upper:raise ValueError('XML entities, DTDs and resource processing are prohibited')
    try:root=ET.fromstring(text)
    except ET.ParseError as exc:raise ValueError('malformed XML') from exc
    expected='robot' if extension=='.urdf' else 'mujoco'
    if root.tag!=expected:raise ValueError(f'expected {expected} description root')
    elements=list(root.iter())
    if len(elements)>2000:raise ValueError('description exceeds element limit')
    def visit(node,depth=0):
        if depth>32:raise ValueError('description nesting limit exceeded')
        if node.tag in ('include','plugin','extension'):raise ValueError('includes and native plugins are prohibited')
        for key,value in node.attrib.items():
            if key in ('file','filename'):resource(value,files)
            if key in ('pos','quat','euler','xyz','rpy','size','range','mass','density','radius','length','lower','upper','effort','velocity','damping','friction'):
                try:values=np.asarray(value.split(),dtype=float)
                except ValueError as exc:raise ValueError('invalid numeric description field') from exc
                if not len(values) or not np.isfinite(values).all() or np.max(np.abs(values))>1e5:raise ValueError('description geometry outside numeric bounds')
                if key in ('size','mass','density','radius','length') and np.any(values<=0):raise ValueError('geometry dimensions/mass must be positive')
                if key=='range' and (len(values)!=2 or values[0]>=values[1]):raise ValueError('invalid joint/actuator range')
        if node.tag=='joint':
            kinds=('fixed','revolute','continuous','prismatic','floating','planar') if expected=='robot' else ('hinge','slide','ball','free')
            if node.get('type','hinge') not in kinds:raise ValueError('unsupported joint type')
        if node.tag=='limit' and 'lower' in node.attrib and 'upper' in node.attrib and float(node.get('lower'))>=float(node.get('upper')):raise ValueError('invalid URDF joint limits')
        for child in node:visit(child,depth+1)
    visit(root)
    counts={k:sum(n.tag==k for n in elements) for k in ('body','link','joint','geom','collision','actuator')}
    if counts['joint']>128 or counts['geom']>512:raise ValueError('robot description complexity exceeds limit')
    return counts,['Description structurally inspected; not compiled or executed.','Configure an isolated native worker, validated inertia/collisions, controller and task criteria before simulation.']


def triangle_preview(content, extension):
    """Bounded OBJ/STL geometry only; materials and external resources are ignored."""
    positions=[];indices=[]
    if extension=='.obj':
        try:lines=content.decode('utf-8-sig').splitlines()
        except UnicodeError:raise ValueError('OBJ must be UTF-8 text') from None
        for line in lines:
            parts=line.split()
            if not parts or parts[0].startswith('#'):continue
            if parts[0]=='v':
                if len(parts)<4:raise ValueError('invalid OBJ vertex')
                positions.append(vector([float(v) for v in parts[1:4]],3).tolist())
                if len(positions)>MAX_VERTICES:raise ValueError('OBJ vertex limit exceeded')
            elif parts[0]=='f':
                if not 4<=len(parts)<=66:raise ValueError('OBJ face exceeds bounds')
                face=[]
                for entry in parts[1:]:
                    value=int(entry.split('/')[0]);index=value-1 if value>0 else len(positions)+value
                    if not 0<=index<len(positions):raise ValueError('OBJ face references a missing vertex')
                    face.append(index)
                for i in range(1,len(face)-1):indices.extend([face[0],face[i],face[i+1]])
            if len(indices)>MAX_VERTICES*3:raise ValueError('OBJ triangle limit exceeded')
    elif len(content)>=84 and len(content)==84+50*struct.unpack_from('<I',content,80)[0]:
        count=struct.unpack_from('<I',content,80)[0]
        if count*3>MAX_VERTICES:raise ValueError('STL triangle limit exceeded')
        for i in range(count):
            values=struct.unpack_from('<9f',content,84+50*i+12)
            for j in range(3):positions.append(vector(list(values[j*3:j*3+3]),3).tolist())
        indices=list(range(len(positions)))
    else:
        try:lines=content.decode('ascii').splitlines()
        except UnicodeError:raise ValueError('invalid binary or ASCII STL') from None
        for line in lines:
            parts=line.split()
            if parts and parts[0]=='vertex':
                if len(parts)!=4:raise ValueError('invalid STL vertex')
                positions.append(vector([float(v) for v in parts[1:]],3).tolist())
                if len(positions)>MAX_VERTICES:raise ValueError('STL vertex limit exceeded')
        if len(positions)%3:raise ValueError('incomplete STL facet')
        indices=list(range(len(positions)))
    if not positions or not indices:raise ValueError('no supported triangles found')
    return {'positions':positions,'indices':indices,'vertex_count':len(positions),'triangle_count':len(indices)//3,
            'coordinate_system':'Original static mesh coordinates; scale and source up axis are selected during mapping.'}, ['Static uploaded triangles decoded; materials/textures and physics are not inferred.']


class ImportService:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock()
        self.verifying=None
        for path in self.root.glob('*.json'):
            payload=json.loads(path.read_bytes())
            if payload['record']['status']=='physics_verifying':
                payload['record']['status']='physics_failed'
                payload['record']['diagnostics'].append('Native verification was interrupted by server restart; retry explicitly.')
                self._save(payload)

    def _load(self,identifier):
        try:identifier=str(uuid.UUID(identifier))
        except ValueError:raise KeyError('import missing')
        path=self.root/f'{identifier}.json'
        if not path.exists():raise KeyError('import missing')
        return json.loads(path.read_bytes())

    def _save(self,payload):
        target=self.root/f'{payload["record"]["id"]}.json'
        encoded=json.dumps(payload,allow_nan=False).encode()
        existing_bytes=sum(p.stat().st_size for p in self.root.glob('*.json') if p!=target)
        if existing_bytes+len(encoded)>128*1024*1024:raise ValueError('import storage quota reached; administrator cleanup required')
        temp=target.with_suffix('.tmp');temp.write_bytes(encoded);temp.replace(target)

    def verify(self,identifier,executor):
        with self.lock:
            payload=self._load(identifier);record=payload['record']
            if record['status']=='physics_verifying':return record
            if self.verifying is not None:raise ValueError('another native probe is queued or running; retry after it completes')
            if not payload.get('source'):raise ValueError('visual-only imports have no native physics description')
            record['status']='physics_verifying';self.verifying=identifier;self._save(payload)
            try:executor.submit(self._verify,identifier)
            except Exception:
                self.verifying=None;record['status']='physics_failed'
                record['diagnostics'].append('Native probe could not be queued.');self._save(payload)
                raise ValueError('native probe could not be queued') from None
            return record

    def _verify(self,identifier):
        from .import_physics import native_probe
        payload=self._load(identifier);record=payload['record']
        try:
            result=native_probe(payload['source'],record['sha256'])
            record['capabilities']=result
            record['status']='actuation_verified' if result['robot_actuation_verified'] else 'physics_valid'
            record['readiness']=['physics_model_valid']+(['robot_actuation_verified'] if result['robot_actuation_verified'] else [])
            record['diagnostics']=['MuJoCo compiled the model and integrated a bounded actual actuator probe.',
                                   'No manipulation task is configured. Actuation alone does not verify a grasp or delivery.']
        except Exception as error:
            record['status']='physics_failed';record['readiness']=[]
            record['diagnostics']=['Native physics verification failed: '+str(error)[:700]]
        finally:
            with self.lock:
                self.verifying=None;self._save(payload)

    def create(self,filename,data,reduce_preview=False):
        name=safe_name(filename)
        if '/' in name:raise ValueError('upload filename must be a basename')
        limit=MAX_PROVIDER_ASSET if reduce_preview and name.endswith('.glb') else MAX_UPLOAD
        if not data or len(data)>limit:raise ValueError('scene asset exceeds its bounded byte limit')
        ext=PurePosixPath(name).suffix.lower();files={};bundle={}
        if ext=='.zip':name,content,files,bundle=unpack(data);ext=PurePosixPath(name).suffix.lower()
        else:content=data
        preview=None
        try:
            if ext in ('.glb','.gltf'):
                preview,diagnostics=gltf_preview(content,ext,files,reduce_preview);status='visual_only';summary={'vertices':preview['vertex_count'],'triangles':preview['triangle_count']}
                if reduce_preview:diagnostics.append('Display triangles were deterministically subsampled to a bounded preview; this is not a faithful concave collision reconstruction.')
            elif ext in ('.obj','.stl'):preview,diagnostics=triangle_preview(content,ext);status='visual_only';summary={'vertices':preview['vertex_count'],'triangles':preview['triangle_count']}
            elif ext in ('.xml','.mjcf','.urdf'):summary,diagnostics=inspect_xml(content,ext,files);status='configuration_required'
            else:raise ValueError('unsupported entrypoint format')
        except (KeyError,TypeError,IndexError,OverflowError,RecursionError,struct.error) as exc:raise ValueError('malformed or unsupported scene content') from exc
        record={'schema_version':'vivacity.import/1.0','id':str(uuid.uuid4()),'filename':filename,'entrypoint':name,'format':ext[1:],'status':status,'physics_ready':False,'preview_available':preview is not None,'sha256':hashlib.sha256(data).hexdigest(),'uploaded_bytes':len(data),'created_unix_s':time.time(),'summary':summary|bundle,'diagnostics':diagnostics}
        if preview:
            from .spatial import geometry_evidence
            record['summary']['geometry_validation']=geometry_evidence(preview,sampled=reduce_preview)
        source=None
        if ext in ('.xml','.mjcf','.urdf'):
            source={'entrypoint':name,'content':base64.b64encode(content).decode(),
                    'assets':{k:base64.b64encode(v).decode() for k,v in files.items() if k!=name and k!='manifest.json'}}
        payload=json.dumps({'record':record,'preview':preview,'source':source},allow_nan=False).encode()
        with self.lock:
            existing=list(self.root.glob('*.json'))
            preserve_glb=ext=='.glb' and not files
            stored=list(self.root.glob('*.json'))+list(self.root.glob('*.glb'))
            if len(existing)>=100 or sum(p.stat().st_size for p in stored)+len(payload)+(len(content) if preserve_glb else 0)>128*1024*1024:raise ValueError('import storage quota reached; administrator cleanup required')
            target=self.root/f'{record["id"]}.json';temp=target.with_suffix('.tmp');temp.write_bytes(payload);temp.replace(target)
            if preserve_glb:
                # The static parser already rejected network URIs/extensions.
                # Preserve the embedded visual asset rather than flattening PBR
                # materials, UVs and texture bytes into the collision preview.
                visual=self.root/f'{record["id"]}.glb';visual.write_bytes(content)
        return record

    def get(self,identifier,preview=False):
        result=self._load(identifier)
        geometry=result.get('preview')
        if geometry:geometry.setdefault('coordinate_system','Original static mesh coordinates; scale and source up axis are selected during mapping.')
        # NumPy 2.x can retain the triangle matrix shape in return_inverse.
        # Normalize early provider previews as well as the corrected producer.
        if geometry and geometry['indices'] and isinstance(geometry['indices'][0],list):
            if any(len(row)!=3 or any(type(v) is not int for v in row) for row in geometry['indices']):
                raise ValueError('stored preview has malformed triangle rows')
            geometry['indices']=[v for row in geometry['indices'] for v in row]
            geometry['triangle_count']=len(geometry['indices'])//3
            result['record']['summary']['triangles']=geometry['triangle_count']
        value=result['preview' if preview else 'record']
        if value is None:raise ValueError('this description has no supported triangle preview')
        return value

    def configure_orbital(self, identifier, runtime):
        from .orbital import SOURCE_SHA256
        from .schemas import CreateWorld, RoboticsConfig
        with self.lock:
            payload = self._load(identifier)
            record = payload['record']
            if record['sha256'] != SOURCE_SHA256 or not (record.get('capabilities') or {}).get('robot_actuation_verified'):
                raise ValueError('only the supplied, successfully verified Orbital fixture has a configured manipulation adapter')
            existing = record.get('configured_world_id')
            if existing:
                try:
                    runtime.get_world(existing)
                    return record
                except KeyError:
                    pass
            config = RoboticsConfig(task='pick_place', scene_profile='orbital_salvage',
                                    source_import_id=identifier, obstacle_enabled=True,
                                    obstacle_position=[.75, -.4, .33], obstacle_size=[.18, .18, .33])
            world = runtime.create_world(CreateWorld(backend='mujoco', config=config))
            record.update(status='manipulation_configured', physics_ready=True, configured_world_id=world['id'])
            record['readiness'] = ['physics_model_valid', 'robot_actuation_verified', 'manipulation_configured']
            record['diagnostics'].append('Configured an adapted Panda salvage task. The original robot is replaced; cargo resized and endpoints relocated. Execution success still requires measured validation.')
            self._save(payload)
            return record
