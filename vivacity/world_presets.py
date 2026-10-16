"""Usable primitive collision scenes, not facility digital twins or images."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .workspace_schemas import EnvironmentSpec, LibraryWorld


def box(name, position, size, color=(.35, .4, .43, 1.)):
    return dict(name=name, type='box', position=position, size=size, rgba=list(color), friction=.8)


def preset(identifier, name, description, additions=(), dimensions=(6., 6., 3.)):
    geometry = [box('floor', [0, 0, -.84], [dimensions[0]/2, dimensions[1]/2, .04], (.32,.34,.35,1.)),
                box('back_wall', [0, dimensions[1]/2, .7], [dimensions[0]/2,.05,1.5], (.52,.54,.53,1.))]
    geometry.extend(additions)
    spec = EnvironmentSpec(name=name, description=description, dimensions_m=list(dimensions), geometries=geometry)
    digest = hashlib.sha256(json.dumps(spec.model_dump(), sort_keys=True).encode()).hexdigest()
    return LibraryWorld(id=identifier, name=name, description=description, source='prebuilt', spec=spec,editable=False,
                        sha256=digest, created_unix_s=0., physics_scope='Static MuJoCo collision primitives around a standardized Panda workbench. Simplified task workcell, not a complete facility twin.')


def shelf(prefix, x, y):
    return [box(prefix+'_left',[x-.6,y,.2],[.05,.25,1.]), box(prefix+'_right',[x+.6,y,.2],[.05,.25,1.]),
            *[box(prefix+f'_level{i}',[x,y,-.4+i*.55],[.6,.3,.04]) for i in range(3)]]


PREBUILT = [
    preset('warehouse','Industrial warehouse','Pallet racks and a rigid handling workbench.',shelf('rack',-1.6,1.8)),
    preset('factory','Manufacturing factory','Machine surrogates and a robot transfer cell.',[box('machine',[-1.5,1.8,.2],[.55,.6,1.])]),
    preset('robotics_lab','Robotics laboratory','A controlled bench with measurement fixtures.',[box('instrument',[1.8,1.6,-.1],[.45,.35,.7])]),
    preset('automotive','Automotive assembly cell','A guarded handling station beside a component fixture.',[box('fixture',[-1.8,1.7,-.1],[.7,.5,.7])]),
    preset('logistics','Logistics fulfilment','Parcel surrogates and fixed packing zones.',[box('parcel_a',[-1.4,1.8,-.5],[.25,.3,.3],(.57,.41,.25,1.)),box('parcel_b',[-2.1,1.8,-.4],[.3,.3,.4],(.57,.41,.25,1.))]),
    preset('research','Research laboratory','A small test cell with controlled object conditions.',[box('cabinet',[-1.5,1.9,.1],[.5,.3,.9])]),
    preset('packaging','Packaging facility','A packing workbench and fixed carton staging.',[box('staging',[-1.7,1.6,-.45],[.8,.5,.35],(.57,.41,.25,1.))]),
    preset('cleanroom','Cleanroom station','An enclosed simplified component-handling cell.',[box('partition',[-2,0,.5],[.04,1.5,1.3],(.8,.81,.8,1.))]),
    preset('workshop','Industrial workshop','A workbench with an adjacent equipment cabinet.',[box('equipment',[-1.3,1.7,.05],[.6,.4,.85])]),
    preset('desktop','Desktop robotics workspace','A compact workcell for repeatable manipulation.',dimensions=(4.,4.,3.)),
    preset('cluttered_cell','Cluttered manipulation','A collision fixture beside the pickup workspace.',[box('collision_fixture',[.75,-.4,.18],[.04,.08,.18],(.55,.28,.2,1.))]),
    preset('quality_control','Quality-control workstation','Part presentation and measured placement; visual defect inspection is not implemented.',[box('station',[-1.4,1.8,-.1],[.5,.4,.7])]),
    preset('textile_fixture','Textile folding fixture','Existing Panda-actuated sheet fixture. This option uses its dedicated cloth adapter and fixed hinge.',dimensions=(2.,2.,2.)),
]


def prebuilt():
    result=deepcopy([item.model_dump() for item in PREBUILT])
    catalog=json.loads(Path(__file__).with_name('visual_catalog.json').read_text(encoding='utf-8'))
    for record in result:
        if record['id'] in catalog:
            visual=catalog[record['id']]
            record['appearance']=deepcopy(visual['appearance'])
            record['provider_world_id']=visual['provider_world_id']
            record['description']='Curated World Labs '+('laboratory' if record['id']=='robotics_lab' else 'warehouse')+' appearance around a bounded robotics workcell.'
            record['physics_scope']+=' The colored environment is visual context; its furniture is not automatically reconstructed into collision geometry.'
    return result
