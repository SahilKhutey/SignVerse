import numpy as np

def bone_to_euler(dir_vec, parent_dir_vec=None):
    """
    Computes Euler angles in radians and degrees relative to standard vertical orientation.
    Returns (euler_rad, euler_deg) as 3-element lists.
    """
    x, y, z = dir_vec
    
    # yaw (rotation about Z) = arctan2(x, -y)
    # pitch (rotation about X) = arctan2(z, -y)
    # roll (rotation about Y) = 0.0
    yaw_rad = float(np.arctan2(x, -y + 1e-8))
    pitch_rad = float(np.arctan2(z, -y + 1e-8))
    roll_rad = 0.0
    
    e_rad = [roll_rad, pitch_rad, yaw_rad]
    e_deg = [float(np.degrees(a)) for a in e_rad]
    
    return e_rad, e_deg

def euler_to_quat(euler_rad):
    """
    Converts roll, pitch, yaw radians to a quaternion [w, x, y, z].
    """
    rx, ry, rz = euler_rad
    
    cx = np.cos(rx * 0.5)
    sx = np.sin(rx * 0.5)
    cy = np.cos(ry * 0.5)
    sy = np.sin(ry * 0.5)
    cz = np.cos(rz * 0.5)
    sz = np.sin(rz * 0.5)
    
    w = cx * cy * cz + sx * sy * sz
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    
    return [float(w), float(x), float(y), float(z)]
