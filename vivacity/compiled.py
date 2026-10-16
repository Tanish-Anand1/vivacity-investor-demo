"""Reuse immutable compiled geometry while every fork owns independent MjData.

Weak references retain no model after its last active world is released. Model
configuration is changed only by compiling a new world, never during stepping.
This avoids compiling several copies of Panda meshes for a single experiment.
"""
from copy import copy, deepcopy
import os
import gc
import json
import sys
from collections import OrderedDict
from functools import wraps
from dataclasses import fields
from threading import RLock
from weakref import WeakValueDictionary

import mujoco as mj

_worlds = WeakValueDictionary()
_lock = RLock()
_compiled = OrderedDict()


def release_unused_memory():
    """Return freed native buffers between large jobs, never during stepping.

    glibc otherwise retains worker-thread arenas after MuJoCo/GL objects close.
    Active models and branch states remain owned and are not touched.
    """
    gc.collect()
    if sys.platform.startswith('linux'):
        import ctypes
        trim = getattr(ctypes.CDLL(None), 'malloc_trim', None)
        if trim is not None: trim(0)


def reuse_world(backend):
    """Cache two immutable model layouts, including their pristine initial state.

    Repeated HTTP world creation must not recompile large meshes while another
    simulator is active. A configuration miss releases old cached models before
    compiling; active branches retain their own model reference until they end.
    """
    def decorate(create):
        @wraps(create)
        def wrapped(self, config, seed, *args, **kwargs):
            if os.getenv('VIVACITY_IMMUTABLE_MODEL_FORKS') != '1':
                return create(self, config, seed, *args, **kwargs)
            key = (type(self).__name__,os.getenv('VIVACITY_HEADLESS_GEOMETRY'),json.dumps(config, sort_keys=True),
                   tuple(args), tuple(sorted(kwargs.items())))
            with _lock:
                saved = _compiled.get(key)
                if saved is not None:
                    template, initial = saved
                    world = _clone(template)
                    world.seed = seed
                    mj.mj_setState(world.model, world.data, initial, mj.mjtState.mjSTATE_INTEGRATION)
                    mj.mj_forward(world.model, world.data)
                    mj.mj_setState(world.model, world.data, initial, mj.mjtState.mjSTATE_INTEGRATION)
                    return remember(world, backend) if not kwargs.get('diagnostics', False) else world
                # Normal and instrumented pickup layouts can coexist. On a new
                # layout, release unrelated cached geometry before compilation.
                if len(_compiled) >= 2:
                    _compiled.clear()
                release_unused_memory()
                world = create(self, config, seed, *args, **kwargs)
                import numpy as np
                initial = np.empty(mj.mj_stateSize(world.model, mj.mjtState.mjSTATE_INTEGRATION))
                mj.mj_getState(world.model, world.data, initial, mj.mjtState.mjSTATE_INTEGRATION)
                template = copy(world)
                template.data = None
                for field in fields(world):
                    if field.name not in ('model', 'data'):
                        setattr(template, field.name, deepcopy(getattr(world, field.name)))
                _compiled[key] = (template, initial)
                return world
        return wrapped
    return decorate


def _clone(parent):
    child = copy(parent)
    for field in fields(parent):
        if field.name not in ('model', 'data'):
            setattr(child, field.name, deepcopy(getattr(parent, field.name)))
    child.data = mj.MjData(parent.model)
    child.action = {}
    return child


def remember(world, backend):
    if os.getenv('VIVACITY_IMMUTABLE_MODEL_FORKS') != '1':
        return world
    with _lock:
        _worlds[(backend, mj.__version__, world.model_hash)] = world
    return world


def fork_geometry(state):
    if os.getenv('VIVACITY_IMMUTABLE_MODEL_FORKS') != '1':
        return None
    with _lock:
        parent = _worlds.get((state['backend'], state['version'], state['model_hash']))
    if parent is None:
        return None
    child = _clone(parent)
    child.config = deepcopy(state['config'])
    child.seed = state['seed']
    child.action = {}
    return child
