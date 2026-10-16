"""Drop rendering-only meshes from the server, preserving all physics geometry.

The React viewer owns the detailed display assets. MuJoCo still owns joints,
inertias, collision meshes, contacts, actuators and the integrated state.
"""
import os
from pathlib import Path


def collision_only(root,enabled=None):
    if enabled is None:
        enabled=os.getenv('VIVACITY_HEADLESS_GEOMETRY')=='1'
    compiler=root.find('compiler')
    if not enabled or compiler is not None and compiler.get('inertiafromgeom')=='true':
        return 0
    defaults={}
    def collect(node,inherited):
        geom=node.find('geom')
        attrs=inherited|({} if geom is None else geom.attrib)
        defaults[node.get('class','__main__')]=attrs
        for child in node.findall('default'):collect(child,attrs)
    for node in root.findall('default'):collect(node,{})
    referenced={e.get(key) for e in root.iter() for key in ('geom','geom1','geom2') if e.get(key)}
    removed=0
    def visit(body,inherited_class='__main__'):
        nonlocal removed
        child_class=body.get('childclass',inherited_class)
        # Explicit inertia is essential. Decorative geoms on bodies whose mass
        # is inferred from geometry (e.g. the cloth bar) must remain intact.
        if body.tag=='body' and body.find('inertial') is not None:
            for geom in list(body.findall('geom')):
                attrs=defaults.get(geom.get('class',child_class),{})|geom.attrib
                if attrs.get('contype','1')=='0' and attrs.get('conaffinity','1')=='0' and geom.get('name') not in referenced:
                    body.remove(geom);removed+=1
        for child in body.findall('body'):visit(child,child_class)
    worldbody=root.find('worldbody')
    if worldbody is not None:visit(worldbody)
    used={e.get('mesh') for e in root.iter() if e.get('mesh')}
    for asset in root.findall('asset'):
        for mesh in list(asset.findall('mesh')):
            name=mesh.get('name') or Path(mesh.get('file','')).stem
            if name not in used:asset.remove(mesh)
    return removed
