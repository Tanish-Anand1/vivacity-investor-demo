"""Lightweight projection of recorded MuJoCo frames for equation discovery."""
import math

QUANTITIES = {
    'x': ('Carton X position', 'm'),
    'y': ('Carton Y position', 'm'),
    'z': ('Carton height', 'm'),
    'speed': ('Carton speed', 'm/s'),
    'torque': ('Robot joint 1 torque', 'N m'),
    'force': ('Gripper contact normal force', 'N'),
    'power': ('Actuator mechanical power', 'W'),
    'work': ('Net mechanical work', 'J'),
}


def scalar(frame, quantity):
    """Read only simulator-generated quantities; missing values stay missing."""
    target = next((c for c in frame.get('cartons', ()) if c['id'] == 'target'), None)
    measure = frame.get('measurements') or {}
    robot = measure.get('robot') or {}
    value = {
        'x': lambda: target['position_m'][0] if target else None,
        'y': lambda: target['position_m'][1] if target else None,
        'z': lambda: target['position_m'][2] if target else None,
        'speed': lambda: math.hypot(*target['linear_velocity_m_s']) if target else None,
        'torque': lambda: (robot.get('joint_torque_nm') or [None])[0],
        'joint_acceleration': lambda: (robot.get('joint_acceleration_rad_s2') or [None])[0],
        'joint_velocity': lambda: (robot.get('joint_velocity_rad_s') or [None])[0],
        'force': lambda: robot.get('gripper_contact_normal_force_n'),
        'power': lambda: measure.get('actuator_power_w'),
        'work': lambda: measure.get('mechanical_work_j'),
    }[quantity]()
    return float(value) if value is not None and math.isfinite(float(value)) else None
