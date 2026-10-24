"""Resolved contact wrenches, independent of a task's success decision.

MuJoCo contact-frame rows are world-space axes. mj_contactForce returns the
wrench acting on geom2; geom1 receives the opposite force. Normal force is not
vertical support. Keep these quantities separate when evaluating grasps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

import mujoco as mj
import numpy as np


@dataclass
class ContactLoad:
    force_world_n: np.ndarray = field(default_factory=lambda: np.zeros(3))
    torque_world_nm: np.ndarray = field(default_factory=lambda: np.zeros(3))
    normal_force_n: float = 0.
    count: int = 0

    def as_dict(self):
        return {'force_world_n': self.force_world_n.tolist(),
                'torque_world_nm': self.torque_world_nm.tolist(),
                'normal_force_n': self.normal_force_n, 'contact_count': self.count}


def body_contact_loads(model: mj.MjModel, data: mj.MjData, body_id: int,
                       groups: Mapping[str, set[int]]) -> dict[str, ContactLoad]:
    """Sum all contact forces on one rigid body by the opposing body's group.

    Torques include the moment arm about the body's inertial center. Explicit
    group membership avoids guessing semantic identity from geometry names.
    Unclassified contacts are always retained in ``other``.
    """
    seen = set()
    for members in groups.values():
        if seen.intersection(members):
            raise ValueError('contact groups must not overlap')
        seen.update(members)
    if 'other' in groups:
        raise ValueError('other is reserved for unclassified contacts')
    result = {name: ContactLoad() for name in (*groups, 'other')}
    center = data.xipos[body_id]
    for index, contact in enumerate(data.contact[:data.ncon]):
        bodies = [int(model.geom_bodyid[int(g)]) for g in (contact.geom1, contact.geom2)]
        if body_id not in bodies or bodies[0] == bodies[1]:
            continue
        other = bodies[1] if bodies[0] == body_id else bodies[0]
        key = next((name for name, members in groups.items() if other in members), 'other')
        local = np.zeros(6)
        mj.mj_contactForce(model, data, index, local)
        sign = 1. if bodies[1] == body_id else -1.
        rotation = np.asarray(contact.frame).reshape(3, 3).T
        force = sign * (rotation @ local[:3])
        torque = sign * (rotation @ local[3:]) + np.cross(contact.pos-center, force)
        load = result[key]
        load.force_world_n += force
        load.torque_world_nm += torque
        load.normal_force_n += max(0., float(local[0]))
        load.count += int(local[0] > 1e-8)
    return result


def descendants(model: mj.MjModel, body_name: str) -> set[int]:
    root = model.body(body_name).id
    found = {root}
    for body in range(root+1, model.nbody):
        if int(model.body_parentid[body]) in found:
            found.add(body)
    return found


def bilateral_support(loads: Mapping[str, ContactLoad], mass_kg: float,
                      gravity_m_s2: float, acceleration_z_m_s2: float) -> dict:
    """A per-sample balance check, not a sustained-transport certificate."""
    expected = mass_kg * (gravity_m_s2+acceleration_z_m_s2)
    left = float(loads['left'].force_world_n[2])
    right = float(loads['right'].force_world_n[2])
    total = left+right
    other = sum(float(load.force_world_n[2]) for name, load in loads.items()
                if name not in ('left', 'right'))
    return {
        'left_vertical_n': left, 'right_vertical_n': right,
        'other_vertical_n': other, 'expected_vertical_n': expected,
        'force_balance_error_n': total+other-expected,
        'left_fraction': left/total if total > 1e-8 else None,
        'right_fraction': right/total if total > 1e-8 else None,
        'bilateral_load': bool(total > .5*mass_kg*gravity_m_s2 and
                               min(left, right) >= .15*total),
        'unsupported_by_environment': bool(abs(other) < .02*mass_kg*gravity_m_s2),
    }
