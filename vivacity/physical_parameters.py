"""Native MuJoCo box parameters with explicit mass/inertia/contact semantics.

The manifest is data for future editor controls and a coverage contract for
tests. It does not claim that all humanoid tasks support all parameter values.
"""
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


BOX_PARAMETER_MANIFEST = {
    'dimensions_m': {'unit': 'm', 'bounds': [.04, .5], 'dependency': 'geom.size, body.inertia; body.mass in density mode',
                     'requires_rebuild': True, 'test': 'test_box_mass_density_dimensions_and_inertia'},
    'mass_mode': {'unit': None, 'options': ['mass', 'density'], 'dependency': 'mass calculation',
                  'requires_rebuild': True, 'test': 'test_box_mass_density_dimensions_and_inertia'},
    'mass_kg': {'unit': 'kg', 'bounds': [.01, 20.], 'dependency': 'body.mass in mass mode',
                'requires_rebuild': True, 'test': 'test_box_mass_density_dimensions_and_inertia'},
    'density_kg_m3': {'unit': 'kg/m^3', 'bounds': [1., 20000.], 'dependency': 'body.mass = density * volume in density mode',
                      'requires_rebuild': True, 'test': 'test_box_mass_density_dimensions_and_inertia'},
    'custom_inertia_kg_m2': {'unit': 'kg m^2', 'dependency': 'body.inertia and body.iquat from principal axes',
                            'requires_rebuild': True, 'test': 'test_custom_inertia_validation_and_native_value'},
    'sliding_friction': {'unit': '1', 'bounds': [.001, 2.], 'dependency': 'geom.friction[0], contact.friction[:2]',
                         'requires_rebuild': True, 'test': 'test_native_contact_parameters'},
    'torsional_friction_m': {'unit': 'm', 'bounds': [0., .05], 'dependency': 'geom.friction[1], contact.friction[2]',
                             'requires_rebuild': True, 'test': 'test_native_contact_parameters'},
    'rolling_friction_m': {'unit': 'm', 'bounds': [0., .02], 'dependency': 'geom.friction[2], contact.friction[3:5]',
                           'requires_rebuild': True, 'test': 'test_native_contact_parameters'},
    'contact_time_constant_s': {'unit': 's', 'bounds': [.004, .1], 'dependency': 'geom.solref[0], contact.solref[0]',
                                'requires_rebuild': True, 'test': 'test_native_contact_parameters'},
    'contact_damping_ratio': {'unit': '1', 'bounds': [.1, 4.], 'dependency': 'geom.solref[1], contact.solref[1]',
                              'requires_rebuild': True, 'test': 'test_native_contact_parameters'},
}


class BoxPhysics(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)
    dimensions_m: tuple[float, float, float] = (.18, .18, .16)
    mass_mode: Literal['mass', 'density'] = 'mass'
    mass_kg: float = Field(default=.5, ge=.01, le=20.)
    density_kg_m3: float = Field(default=100., ge=1., le=20000.)
    # Ixx, Iyy, Izz, Ixy, Ixz, Iyz about the object's center of mass.
    custom_inertia_kg_m2: tuple[float, float, float, float, float, float] | None = None
    sliding_friction: float = Field(default=.8, ge=.001, le=2.)
    torsional_friction_m: float = Field(default=.005, ge=0, le=.05)
    rolling_friction_m: float = Field(default=.0001, ge=0, le=.02)
    contact_time_constant_s: float = Field(default=.02, ge=.004, le=.1)
    contact_damping_ratio: float = Field(default=1., ge=.1, le=4.)

    @model_validator(mode='after')
    def physically_valid(self):
        if not all(.04 <= dimension <= .5 for dimension in self.dimensions_m):
            raise ValueError('full box dimensions must lie in [0.04, 0.5] metres')
        if not .01 <= self.effective_mass <= 20.:
            raise ValueError('effective mass must lie in [0.01, 20] kg')
        if self.custom_inertia_kg_m2 is not None:
            moments = np.linalg.eigvalsh(self.inertia_matrix)
            if moments[0] <= 1e-9 or moments[2] > moments[0]+moments[1]+1e-10:
                raise ValueError('inertia must be positive definite and satisfy principal-moment triangle inequalities')
            second_moment = np.eye(3)*np.trace(self.inertia_matrix)/2-self.inertia_matrix
            if np.any(np.diag(second_moment) > self.effective_mass*(np.asarray(self.dimensions_m)/2)**2+1e-10):
                raise ValueError('inertia exceeds the mass distribution bounds of the box geometry')
        return self

    @property
    def effective_mass(self):
        return self.mass_kg if self.mass_mode == 'mass' else float(np.prod(self.dimensions_m)*self.density_kg_m3)

    @property
    def inertia_matrix(self):
        if self.custom_inertia_kg_m2 is not None:
            xx, yy, zz, xy, xz, yz = self.custom_inertia_kg_m2
            return np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        x, y, z = self.dimensions_m
        return np.diag(np.array([y*y+z*z, x*x+z*z, x*x+y*y])*self.effective_mass/12)

    def mjcf_geom(self):
        return {'type': 'box', 'size': ' '.join(str(v/2) for v in self.dimensions_m),
                'mass': str(self.effective_mass), 'condim': '6', 'priority': '3',
                'friction': f'{self.sliding_friction} {self.torsional_friction_m} {self.rolling_friction_m}',
                'solref': f'{self.contact_time_constant_s} {self.contact_damping_ratio}'}

    def mjcf_inertial(self):
        if self.custom_inertia_kg_m2 is None:
            return None
        return {'pos': '0 0 0', 'mass': str(self.effective_mass),
                'fullinertia': ' '.join(map(str, self.custom_inertia_kg_m2))}


def parameter_manifest():
    schema = BoxPhysics.model_json_schema()
    return {'schema_version': 'vivacity.physical-parameters/1',
            'parameters': {key: metadata | {'schema': schema['properties'][key]}
                           for key, metadata in BOX_PARAMETER_MANIFEST.items()},
            'contact_model': 'MuJoCo elliptic or pyramidal friction cone as configured by the compiled model; positive-format solref time constant and damping ratio. Not independent static/dynamic friction or restitution.'}
