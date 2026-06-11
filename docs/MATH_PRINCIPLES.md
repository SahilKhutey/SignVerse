# 🔬 MATHEMATICAL CAPABILITY & ENGINEERING PRINCIPLES
### The Complete Mathematical Foundation of SignVerse Robotics

The deep math — every transformation, every algorithm, every derivation that makes the system work. From coordinate geometry to quaternions, from SLERP to Kalman filters, from forward kinematics to robot retargeting.

---

## 📐 1. Mathematical Foundation: Coordinate Systems

### 1.1 The Three Coordinate Systems

```
┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM A: IMAGE SPACE (MediaPipe Output)                          │
│  • Origin: Top-left corner of image                                │
│  • X axis: → (right)                                               │
│  • Y axis: ↓ (down)                                                │
│  • Z axis: ⊙ (toward camera, depth from camera plane)              │
│  • Units: Normalized [0, 1] for x,y; relative for z                │
│  • Y is INVERTED compared to math convention                       │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
                    [TRANSFORMATION T₁]
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM B: ROBOTICS STANDARD                                        │
│  • Origin: User-defined (root joint / hip center)                  │
│  • X axis: → (forward, direction of motion)                        │
│  • Y axis: ↑ (up, opposite of gravity)                             │
│  • Z axis: ⊙ (left, follows right-hand rule)                       │
│  • Units: Meters                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
                    [TRANSFORMATION T₂]
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM C: 3D ENGINE (Blender, Three.js)                          │
│  • Origin: Scene root                                              │
│  • X axis: → (right)                                               │
│  • Y axis: ↑ (up)                                                  │
│  • Z axis: ⊙ (toward viewer, out of screen)                        │
│  • Units: Meters (or arbitrary scaled)                             │
│  • Right-handed coordinate system                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Transformation Matrices

#### $T_1$: Image $\rightarrow$ Robotics

Image space coordinates $(u, v, w)$ are defined as:
* $u = x$ (right, normalized $[0, 1]$)
* $v = y$ (down, normalized $[0, 1]$)
* $w = z$ (depth, negative is into the scene)

Robotics space $(X, Y, Z)$ is defined as:
* $X$ = forward
* $Y$ = up
* $Z$ = left

Applying a $180^\circ$ rotation around the X-axis followed by a $90^\circ$ rotation around the Z-axis, we obtain the transformation mappings $X' = w$, $Y' = -v$, $Z' = -u$ (assuming normalization and origin shifts are corrected).

```python
import numpy as np

def image_to_robotics(u, v, w):
    """
    Transform a single point from MediaPipe image space to robotics space.
    
    Mathematical derivation:
    Step 1: Flip Y (image down → math up):  v' = -v
    Step 2: Swap X and Z (image Z forward → math Z left):  X' = w, Z' = -u
    Step 3: Scale to meters using depth: multiply by depth
    
    Combined as 4x4 homogeneous transformation matrix:
    T = [[0, 0, 1, 0],
         [0,-1, 0, 0],
         [-1,0, 0, 0],
         [0, 0, 0, 1]]
    """
    X = w  # Image Z forward → Robotics X forward
    Y = -v  # Image Y down → Robotics Y up (inverted)
    Z = -u  # Image X right → Robotics Z left (inverted)
    return np.array([X, Y, Z])
```

#### $T_2$: Robotics $\rightarrow$ 3D Engine (Three.js / Blender)

```python
def robotics_to_threejs(X, Y, Z, scale=1.0):
    """
    Robotics to Three.js: identity transform with scaling.
    
    Three.js uses right-handed Y-up coordinate system, which matches
    the robotics standard. Only scaling may differ.
    """
    return np.array([X * scale, Y * scale, Z * scale])
```

### 1.3 Homogeneous Transformation Matrices
For composing transformations (rotations + translations):

```python
def make_transform(R, t):
    """
    Create 4x4 homogeneous transformation matrix from rotation R (3x3) 
    and translation t (3x1).
    
    T = [R  t]
        [0  1]
    
    Properties:
    - T represents a rigid body transformation in 3D
    - Preserves distances and angles
    - det(T) = 1 (proper rotation, not reflection)
    - T⁻¹ = [Rᵀ  -Rᵀt]
            [0    1   ]
    """
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def transform_point(T, p):
    """
    Apply transformation T to homogeneous point p.
    
    p' = T * p  (where p is [x, y, z, 1]ᵀ)
    """
    p_h = np.append(p, 1)
    return (T @ p_h)[:3]


def compose_transforms(T1, T2):
    """
    Compose two transformations: T_combined = T1 * T2.
    First applies T2, then T1.
    """
    return T1 @ T2
```

---

## 🔄 2. Rotational Mathematics

### 2.1 Rotation Representations
A rotation in 3D can be represented in 5 equivalent ways:

| Representation | DOF | Pros | Cons |
| :--- | :--- | :--- | :--- |
| **Rotation Matrix** | 9 (3×3) | Easy composition, no singularities | 6 redundant parameters |
| **Euler Angles** | 3 | Intuitive, human-readable | Gimbal lock, non-unique |
| **Axis-Angle** | 4 | Compact | Not directly composable |
| **Quaternion** | 4 | No gimbal lock, smooth interpolation | Less intuitive |
| **Rotation Vector** | 3 | Compact, differentiable | No constraint handling |

### 2.2 Euler Angles (ZYX Convention)

```python
def euler_to_rotation_matrix(roll, pitch, yaw):
    """
    Convert Euler angles to rotation matrix using ZYX intrinsic convention.
    
    The rotation is applied in order: R = Rz(yaw) @ Ry(pitch) @ Rx(roll)
    
    Mathematical derivation using Tait-Bryan angles:
    
    Rx(roll) = [1  0       0      ]
               [0  cos(α) -sin(α)]
               [0  sin(α)  cos(α)]
    
    Ry(pitch) = [ cos(β)  0  sin(β)]
                [ 0       1  0     ]
                [-sin(β)  0  cos(β)]
    
    Rz(yaw) = [cos(γ) -sin(γ)  0]
              [sin(γ)  cos(γ)  0]
              [0       0       1]
    
    Combined:
    R = Rz @ Ry @ Rx
    
    Args:
        roll:  rotation around X axis (radians)
        pitch: rotation around Y axis (radians)  
        yaw:   rotation around Z axis (radians)
    
    Returns:
        3x3 rotation matrix
    """
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    
    # Combined rotation matrix (ZYX order)
    R = np.array([
        [cy*cp,            cy*sp*sr - sy*cr,    cy*sp*cr + sy*sr],
        [sy*cp,            sy*sp*sr + cy*cr,    sy*sp*cr - cy*sr],
        [-sp,              cp*sr,               cp*cr           ]
    ])
    return R


def rotation_matrix_to_euler(R):
    """
    Extract Euler angles from rotation matrix.
    
    Derivation:
    R[2,0] = -sin(pitch)         →  pitch = asin(-R[2,0])
    R[2,1] / R[2,2] = tan(roll)  →  roll  = atan2(R[2,1], R[2,2])
    R[1,0] / R[0,0] = tan(yaw)   →  yaw   = atan2(R[1,0], R[0,0])
    
    GIMBAL LOCK occurs when pitch = ±π/2:
    - cos(pitch) = 0
    - roll and yaw become coupled (lose 1 DOF)
    - At gimbal lock, set roll = 0 and compute yaw from other elements
    """
    sy = np.sqrt(R[0,0] * R[0,0] + R[1,0] * R[1,0])
    singular = sy < 1e-6
    
    if not singular:
        pitch = np.arctan2(-R[2,0], sy)
        roll = np.arctan2(R[2,1], R[2,2])
        yaw = np.arctan2(R[1,0], R[0,0])
    else:
        # Gimbal lock case
        pitch = np.pi / 2 * np.sign(-R[2,0])
        roll = 0
        yaw = np.arctan2(-R[1,2], R[0,2])
    
    return roll, pitch, yaw
```

### 2.3 Quaternion Mathematics

```python
class Quaternion:
    """
    Quaternion representation of rotation.
    q = w + xi + yj + zk  (stored as [w, x, y, z])
    
    Properties:
    - Unit quaternion represents rotation: |q| = 1
    - Composition: q3 = q1 * q2 (Hamilton product)
    - Inverse: q⁻¹ = conjugate(q) / |q|² 
    - For unit quat: q⁻¹ = conjugate(q) = [w, -x, -y, -z]
    """
    
    def __init__(self, w=1, x=0, y=0, z=0):
        self.w, self.x, self.y, self.z = w, x, y, z
        self._normalize()
    
    def _normalize(self):
        """Normalize to unit quaternion."""
        n = np.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if n > 1e-8:
            self.w /= n; self.x /= n; self.y /= n; self.z /= n
    
    def conjugate(self):
        """Conjugate: (w, -x, -y, -z). For unit quat, this is the inverse."""
        return Quaternion(self.w, -self.x, -self.y, -self.z)
    
    def multiply(self, other):
        """
        Hamilton product: q1 * q2.
        
        Derivation from (a + bi + cj + dk)(e + fi + gj + hk):
        Real part: ae - bf - cg - dh
        i part:   af + be + ch - dg
        j part:   ag - bh + ce + df
        k part:   ah + bg - cf + de
        
        This is NOT commutative: q1*q2 ≠ q2*q1
        """
        w = self.w*other.w - self.x*other.x - self.y*other.y - self.z*other.z
        x = self.w*other.x + self.x*other.w + self.y*other.z - self.z*other.y
        y = self.w*other.y - self.x*other.z + self.y*other.w + self.z*other.x
        z = self.w*other.z + self.x*other.y - self.y*other.x + self.z*other.w
        return Quaternion(w, x, y, z)
    
    def to_rotation_matrix(self):
        """
        Convert to 3x3 rotation matrix.
        
        Formula:
        R = [1-2(y²+z²)   2(xy-wz)    2(xz+wy)  ]
            [2(xy+wz)     1-2(x²+z²)  2(yz-wx)  ]
            [2(xz-wy)     2(yz+wx)    1-2(x²+y²)]
        """
        w, x, y, z = self.w, self.x, self.y, self.z
        
        return np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
            [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
            [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)]
        ])
    
    @staticmethod
    def from_axis_angle(axis, angle):
        """
        Create quaternion from axis-angle representation.
        
        q = (cos(θ/2), sin(θ/2)*ax, sin(θ/2)*ay, sin(θ/2)*az)
        
        where axis is unit vector and θ is rotation angle.
        """
        axis = np.array(axis) / (np.linalg.norm(axis) + 1e-8)
        s = np.sin(angle / 2)
        return Quaternion(np.cos(angle/2), axis[0]*s, axis[1]*s, axis[2]*s)
    
    @staticmethod
    def from_euler(roll, pitch, yaw):
        """
        Convert Euler angles to quaternion.
        
        Using half-angle formulas:
        cy = cos(yaw/2), sy = sin(yaw/2)
        cp = cos(pitch/2), sp = sin(pitch/2)
        cr = cos(roll/2), sr = sin(roll/2)
        
        w = cr*cp*cy + sr*sp*sy
        x = sr*cp*cy - cr*sp*sy
        y = cr*sp*cy + sr*cp*sy
        z = cr*cp*sy - sr*sp*cy
        """
        cr, sr = np.cos(roll/2), np.sin(roll/2)
        cp, sp = np.cos(pitch/2), np.sin(pitch/2)
        cy, sy = np.cos(yaw/2), np.sin(yaw/2)
        
        w = cr*cp*cy + sr*sp*sy
        x = sr*cp*cy - cr*sp*sy
        y = cr*sp*cy + sr*cp*sy
        z = cr*cp*sy - sr*sp*cy
        
        return Quaternion(w, x, y, z)
```

### 2.4 SLERP (Spherical Linear Interpolation)

```python
def slerp(q1, q2, t):
    """
    Spherical Linear Interpolation between two unit quaternions.
    
    SLERP provides constant angular velocity along the great circle
    arc on the 4D unit sphere.
    
    Mathematical formula:
    q(t) = sin((1-t)θ)/sin(θ) * q1 + sin(tθ)/sin(θ) * q2
    
    where θ = arccos(q1 · q2) is the angle between the quaternions.
    
    Special cases:
    - If θ ≈ 0: use linear interpolation (LERP)
    - If θ ≈ π: quaternions are opposite; choose perpendicular path
    
    Args:
        q1, q2: unit quaternions as [w, x, y, z]
        t: interpolation parameter [0, 1]
    
    Returns:
        Interpolated quaternion
    """
    q1 = np.array(q1)
    q2 = np.array(q2)
    
    # Compute angle between quaternions
    dot = np.dot(q1, q2)
    
    # If dot < 0, negate one quaternion to take shortest path
    if dot < 0:
        q2 = -q2
        dot = -dot
    
    # If quaternions are very close, use linear interpolation
    if dot > 0.9995:
        result = q1 + t * (q2 - q1)
        return result / np.linalg.norm(result)
    
    # Compute SLERP
    theta_0 = np.arccos(dot)  # Angle between quaternions
    theta = theta_0 * t       # Interpolated angle
    sin_theta = np.sin(theta)
    sin_theta_0 = np.sin(theta_0)
    
    s1 = np.cos(theta) - dot * sin_theta / sin_theta_0
    s2 = sin_theta / sin_theta_0
    
    return s1 * q1 + s2 * q2
```

---

## 🎯 3. Forward Kinematics

### 3.1 Skeleton as Kinematic Chain

```python
class KinematicChain:
    """
    Represents a kinematic chain (skeleton) with forward kinematics.
    
    A skeleton is a tree of bones where:
    - Each bone has a parent (except root)
    - Each bone has a local transformation (rotation + translation)
    - World transform = composition of all parent transforms
    
    Forward Kinematics (FK):
    Given joint angles, compute world position of end-effector.
    
    Recursive formula:
    T_world[i] = T_world[parent(i)] @ T_local[i]
    
    where T_local[i] = T_translation(offset[i]) @ T_rotation(angle[i])
    """
    
    def __init__(self):
        self.bones = {}  # name -> {parent, offset, angle}
        self.root = "Hips"
    
    def forward_kinematics(self, joint_angles):
        """
        Compute world transforms for all joints.
        
        Args:
            joint_angles: dict of {joint_name: (rx, ry, rz) in radians}
        
        Returns:
            dict of {joint_name: 4x4 transform matrix}
        """
        transforms = {}
        transforms[self.root] = np.eye(4)  # Root at origin
        
        # Process in topological order (parents before children)
        for bone_name in self._topological_order():
            bone = self.bones[bone_name]
            parent_transform = transforms[bone['parent']]
            
            # Local transform: offset * rotation
            T_offset = self._translation_matrix(bone['offset'])
            
            angles = joint_angles.get(bone_name, (0, 0, 0))
            T_rotation = euler_to_rotation_matrix(*angles)
            
            T_local = T_offset @ T_rotation
            
            # World transform
            transforms[bone_name] = parent_transform @ T_local
        
        return transforms
    
    def _translation_matrix(self, offset):
        """4x4 translation matrix from offset vector."""
        T = np.eye(4)
        T[:3, 3] = offset
        return T
    
    def _topological_order(self):
        """Return bones in order such that parents come before children."""
        order = []
        visited = set()
        self._dfs(self.root, visited, order)
        return order
    
    def _dfs(self, bone, visited, order):
        if bone in visited:
            return
        visited.add(bone)
        order.append(bone)
        for child in self._get_children(bone):
            self._dfs(child, visited, order)
    
    def _get_children(self, parent):
        return [name for name, b in self.bones.items() if b['parent'] == parent]


class SkeletonFK:
    """
    Specific MediaPipe skeleton with forward kinematics.
    
    Bone lengths (in meters, averaged from anthropometric data):
    - Torso: 0.50m
    - Upper arm: 0.28m
    - Forearm: 0.27m
    - Thigh: 0.42m
    - Shin: 0.41m
    - Shoulder width: 0.40m
    - Hip width: 0.32m
    """
    
    BONE_LENGTHS = {
        # Spine chain
        "Spine": 0.50,
        "Neck": 0.10,
        "Head": 0.13,
        # Arms
        "LeftUpperArm": 0.28,
        "LeftForearm": 0.27,
        "RightUpperArm": 0.28,
        "RightForearm": 0.27,
        # Legs
        "LeftThigh": 0.42,
        "LeftShin": 0.41,
        "RightThigh": 0.42,
        "RightShin": 0.41,
    }
    
    def compute_end_effector_position(self, joint_angles):
        """
        Compute position of hand/foot given all joint angles.
        
        For reaching tasks, the end-effector position is:
        p_hand = T_root @ T_spine @ T_neck @ T_shoulder @ T_upper_arm @ T_forearm @ T_hand_offset
        
        This is the position the robot's IK solver needs to match.
        """
        transforms = self.forward_kinematics(joint_angles)
        return transforms["LeftHand"][:3, 3]
```

---

## 🔙 4. Inverse Kinematics

### 4.1 Analytic IK (2-Bone Chain)

```python
def analytic_ik_2bone(shoulder_pos, elbow_pos, wrist_pos, hand_length=0.19):
    """
    Analytical inverse kinematics for a 2-bone chain (like an arm).
    
    Problem: Given desired hand position, find shoulder and elbow angles.
    
    Using law of cosines:
    For triangle formed by (shoulder, elbow, wrist):
    - Upper arm: a (from shoulder to elbow)
    - Forearm: b (from elbow to wrist)
    - Reach distance: c (from shoulder to wrist)
    
    cos(C) = (a² + b² - c²) / (2ab)
    
    where C is the elbow angle.
    
    For the shoulder angle, use atan2:
    θ_shoulder = atan2(target.y - shoulder.y, target.x - shoulder.x)
    
    Derivation:
    c² = (wx - sx)² + (wy - sy)² + (wz - sz)²
    
    If c > a + b: target unreachable, clamp to reachable distance
    If c < |a - b|: target too close, set to minimum reach
    """
    shoulder = np.array(shoulder_pos)
    elbow = np.array(elbow_pos)
    wrist = np.array(wrist_pos)
    
    # Bone lengths
    a = np.linalg.norm(elbow - shoulder)  # Upper arm
    b = np.linalg.norm(wrist - elbow)     # Forearm
    
    # Target reach distance
    target = wrist  # Where hand should be
    c = np.linalg.norm(target - shoulder)
    
    # Clamp to reachable range
    c = np.clip(c, abs(a - b) + 0.01, a + b - 0.01)
    
    # Elbow angle using law of cosines
    cos_elbow = (a*a + b*b - c*c) / (2*a*b)
    elbow_angle = np.arccos(np.clip(cos_elbow, -1, 1)) - np.pi  # Interior angle
    
    # Shoulder angle in XY plane
    dx = target[0] - shoulder[0]
    dy = target[1] - shoulder[1]
    shoulder_angle = np.arctan2(dy, dx)
    
    return shoulder_angle, elbow_angle


def analytic_ik_2bone_3d(p_shoulder, p_elbow, p_wrist, p_hand):
    """
    3D two-bone IK solver.
    
    Solves for the angles that place the end-effector at p_hand,
    given the kinematic chain shoulder → elbow → wrist → hand.
    
    Steps:
    1. Compute the plane containing shoulder, elbow, wrist
    2. Within that plane, use 2D IK to find angles
    3. Compute rotation to orient the arm plane correctly in 3D
    """
    p_shoulder = np.array(p_shoulder)
    p_elbow = np.array(p_elbow)
    p_wrist = np.array(p_wrist)
    p_hand = np.array(p_hand)
    
    # Bone lengths
    a = np.linalg.norm(p_elbow - p_shoulder)
    b = np.linalg.norm(p_wrist - p_elbow)
    c = np.linalg.norm(p_hand - p_shoulder)
    
    # Clamp reach
    c = np.clip(c, abs(a - b) + 0.01, a + b - 0.01)
    
    # Law of cosines for elbow angle
    cos_elbow = (a*a + b*b - c*c) / (2*a*b)
    elbow_angle = np.pi - np.arccos(np.clip(cos_elbow, -1, 1))
    
    # Compute plane normal
    v1 = p_elbow - p_shoulder
    v2 = p_hand - p_shoulder
    plane_normal = np.cross(v1, v2)
    if np.linalg.norm(plane_normal) > 1e-6:
        plane_normal = plane_normal / np.linalg.norm(plane_normal)
    else:
        plane_normal = np.array([0, 0, 1])
    
    # Shoulder yaw (rotation around vertical axis to point at target)
    target_dir = p_hand - p_shoulder
    shoulder_yaw = np.arctan2(target_dir[0], target_dir[2])
    
    # Shoulder pitch (angle from vertical)
    horiz_dist = np.sqrt(target_dir[0]**2 + target_dir[2]**2)
    shoulder_pitch = -np.arctan2(horiz_dist, target_dir[1])
    
    return {
        "shoulder_yaw": shoulder_yaw,
        "shoulder_pitch": shoulder_pitch,
        "elbow": elbow_angle,
    }
```

### 4.2 CCD (Cyclic Coordinate Descent) IK

```python
def ccd_ik(joint_chain, target_pos, max_iterations=50, tolerance=0.01):
    """
    Cyclic Coordinate Descent Inverse Kinematics.
    
    Iterative algorithm that rotates each joint to bring the
    end-effector closer to the target.
    
    Algorithm:
    For each iteration:
      For each joint (from end-effector to root):
        1. Compute vector from joint to end-effector: v_ee
        2. Compute vector from joint to target: v_target
        3. Compute rotation that aligns v_ee with v_target
        4. Apply that rotation to the joint
        5. Update end-effector position
      Check if within tolerance
    """
    end_effector = joint_chain[-1]
    
    for iteration in range(max_iterations):
        for joint in reversed(joint_chain[:-1]):
            joint_pos = joint.world_position()
            ee_pos = end_effector.world_position()
            
            to_ee = ee_pos - joint_pos
            to_target = np.array(target_pos) - joint_pos
            
            to_ee_n = to_ee / (np.linalg.norm(to_ee) + 1e-8)
            to_target_n = to_target / (np.linalg.norm(to_target) + 1e-8)
            
            axis = np.cross(to_ee_n, to_target_n)
            axis_len = np.linalg.norm(axis)
            
            if axis_len < 1e-6:
                continue
            
            axis = axis / axis_len
            
            cos_angle = np.clip(np.dot(to_ee_n, to_target_n), -1, 1)
            angle = np.arccos(cos_angle)
            
            # Limit rotation per step (for stability)
            angle = np.clip(angle, -np.pi/4, np.pi/4)
            joint.apply_rotation(axis, angle)
        
        final_ee = end_effector.world_position()
        error = np.linalg.norm(np.array(target_pos) - final_ee)
        if error < tolerance:
            return True, iteration
    
    return False, max_iterations
```

### 4.3 FABRIK (Forward And Backward Reaching IK)

```python
def fabrik_ik(joint_positions, target_pos, max_iterations=20, tolerance=0.01):
    """
    FABRIK Inverse Kinematics.
    
    Modern, efficient IK algorithm that avoids matrix operations
    and operates directly on geometric positions.
    """
    positions = [np.array(p, dtype=float) for p in joint_positions]
    bone_lengths = [np.linalg.norm(positions[i+1] - positions[i]) 
                    for i in range(len(positions)-1)]
    target = np.array(target_pos, dtype=float)
    root = positions[0].copy()
    
    # Check if target is reachable
    total_length = sum(bone_lengths)
    to_target = np.linalg.norm(target - root)
    if to_target > total_length:
        direction = (target - root) / to_target
        positions = [root] + [root + direction * sum(bone_lengths[:i+1])
                              for i in range(len(bone_lengths))]
        return positions, False
    
    for iteration in range(max_iterations):
        # FORWARD PASS: Start from end-effector, move toward target
        positions[-1] = target
        for i in range(len(positions) - 2, -1, -1):
            direction = (positions[i] - positions[i+1])
            direction = direction / (np.linalg.norm(direction) + 1e-8)
            positions[i] = positions[i+1] + direction * bone_lengths[i]
        
        # BACKWARD PASS: Start from root, restore bone lengths
        positions[0] = root
        for i in range(len(positions) - 1):
            direction = (positions[i+1] - positions[i])
            direction = direction / (np.linalg.norm(direction) + 1e-8)
            positions[i+1] = positions[i] + direction * bone_lengths[i]
        
        # Check convergence
        error = np.linalg.norm(positions[-1] - target)
        if error < tolerance:
            return positions, True
    
    return positions, False
```

---

## 🔮 5. Kalman Filter Mathematics

### 5.1 State Estimation

```python
class KalmanFilter1D:
    """
    1D Kalman Filter for tracking a single variable.
    
    State: x (position), ẋ (velocity)
    Observation: z (noisy position measurement)
    
    PREDICT STEP (time update):
    x̂⁻ = F·x̂ + B·u       (state prediction)
    P⁻ = F·P·Fᵀ + Q        (covariance prediction)
    
    UPDATE STEP (measurement update):
    y = z - H·x̂⁻            (innovation / residual)
    S = H·P⁻·Hᵀ + R         (innovation covariance)
    K = P⁻·Hᵀ·S⁻¹            (Kalman gain)
    x̂ = x̂⁻ + K·y            (state update)
    P = (I - K·H)·P⁻         (covariance update)
    """
    
    def __init__(self, process_noise=0.01, measurement_noise=0.1):
        self.x = np.zeros(2)
        self.P = np.eye(2) * 0.1
        self.dt = 1/30  # 30 FPS
        self.F = np.array([
            [1, self.dt],
            [0, 1]
        ])
        self.Q = np.array([
            [self.dt**4/4, self.dt**3/2],
            [self.dt**3/2, self.dt**2]
        ]) * process_noise
        self.H = np.array([[1, 0]])
        self.R = np.array([[measurement_noise]])
    
    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x
    
    def update(self, z):
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + (K @ y).flatten()
        
        # Joseph form covariance update
        I_KH = np.eye(2) - K @ self.H
        self.P = I_KH @ self.P @ I_KH.T + K @ self.R @ K.T
        
        return self.x
```

### 5.2 Why Kalman Works

```python
def kalman_gain_derivation():
    """
    Mathematical proof that Kalman gain is optimal.
    
    Objective: Minimize posterior error covariance trace(P)
    
    K_optimal = argmin trace((I - K·H)·P⁻·(I - K·H)ᵀ + K·R·Kᵀ)
    
    Taking derivative w.r.t. K and setting to 0:
    d/dK [trace(...)] = -2·(I - K·H)·P⁻·Hᵀ + 2·K·R = 0
    
    Solving:
    P⁻·Hᵀ - K·H·P⁻·Hᵀ - K·R = 0
    K·(H·P⁻·Hᵀ + R) = P⁻·Hᵀ
    K = P⁻·Hᵀ·(H·P⁻·Hᵀ + R)⁻¹
    
    This is the optimal Kalman gain that minimizes mean squared error.
    
    Intuition:
    - When R (measurement noise) is small: K is large, trust measurement more
    - When Q (process noise) is small: P⁻ is small, K is small, trust prediction more
    - K automatically balances prediction vs measurement based on uncertainty
    """
    pass
```

---

## 6. Motion Analysis Mathematics

### 6.1 Velocity and Acceleration

```python
def compute_velocity(positions, fps=30, smoothing_window=3):
    """
    Compute velocity using central difference.
    
    Central difference is more accurate than forward difference:
    v(t) = (x(t+1) - x(t-1)) / (2·dt)     (order O(dt²))
    
    vs forward difference:
    v(t) = (x(t+1) - x(t)) / dt            (order O(dt))
    """
    n = len(positions)
    dt = 1.0 / fps
    velocities = []
    
    for i in range(n):
        if i == 0:
            v = (positions[1] - positions[0]) / dt
        elif i == n - 1:
            v = (positions[-1] - positions[-2]) / dt
        else:
            v = (positions[i+1] - positions[i-1]) / (2 * dt)
        velocities.append(v)
    
    if smoothing_window > 1:
        velocities = moving_average(velocities, smoothing_window)
    
    return velocities


def compute_acceleration(velocities, fps=30):
    """Compute acceleration from velocity (second derivative)."""
    dt = 1.0 / fps
    n = len(velocities)
    accelerations = []
    
    for i in range(n):
        if i == 0 or i == n - 1:
            a = np.zeros(3)
        else:
            a = (velocities[i+1] - velocities[i-1]) / (2 * dt)
        accelerations.append(a)
    
    return accelerations


def moving_average(data, window=3):
    """Apply moving average filter to smooth signal."""
    n = len(data)
    result = []
    half = window // 2
    
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        result.append(np.mean(data[start:end], axis=0))
    
    return result
```

### 6.2 Joint Angles from 3D Points

```python
def angle_between_vectors(v1, v2):
    """
    Compute angle between two 3D vectors.
    
    cos(θ) = (v1 · v2) / (|v1| · |v2|)
    θ = arccos(cos(θ))
    
    Range: [0, π]
    """
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    return np.arccos(np.clip(cos_angle, -1, 1))


def signed_angle_between_vectors(v1, v2, normal):
    """
    Compute signed angle between two vectors around an axis.
    
    Used for joint angles where direction matters.
    
    θ = atan2((v1 × v2) · n, v1 · v2)
    
    Range: [-π, π]
    """
    cross = np.cross(v1, v2)
    dot = np.dot(v1, v2)
    return np.arctan2(np.dot(cross, normal), dot)


def joint_angle_3points(p1, p2, p3):
    """
    Compute angle at joint p2 in a 3-point chain.
    v1 = p1 - p2
    v2 = p3 - p2
    """
    v1 = np.array(p1) - np.array(p2)
    v2 = np.array(p3) - np.array(p2)
    return angle_between_vectors(v1, v2)
```

### 6.3 Bone Vector Computation

```python
def compute_bone_vector(p_parent, p_child):
    """
    Compute 3D bone vector from parent joint to child joint.
    """
    p_parent = np.array(p_parent)
    p_child = np.array(p_child)
    
    vector = p_child - p_parent
    length = np.linalg.norm(vector)
    direction = vector / (length + 1e-8)
    
    return {
        "vector": vector,
        "direction": direction,
        "length": length,
    }


def bone_angle_between_frames(bone1, bone2):
    """
    Compute angular change of a bone between two frames.
    """
    dir1 = np.array(bone1["direction"])
    dir2 = np.array(bone2["direction"])
    return angle_between_vectors(dir1, dir2)
```

---

## 7. Object Detection Mathematics

### 7.1 Pinhole Camera Model

```python
class PinholeCamera:
    """
    Pinhole camera model for 3D reconstruction from 2D.
    
    Projection equations:
    u = fx * X / Z + cx
    v = fy * Y / Z + cy
    """
    
    def __init__(self, fx, fy, cx, cy, width, height):
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        self.width = width
        self.height = height
        self.K = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ])
    
    def project_point(self, point_3d):
        X, Y, Z = point_3d
        if Z <= 0:
            return None
        u = self.fx * X / Z + self.cx
        v = self.fy * Y / Z + self.cy
        return (u, v)
    
    def estimate_depth(self, pixel_size, real_size_meters):
        return (self.fx * real_size_meters) / pixel_size
    
    def backproject_pixel(self, u, v, depth):
        X = (u - self.cx) * depth / self.fx
        Y = (v - self.cy) * depth / self.fy
        return (X, Y, depth)
```

### 7.2 Depth Estimation

```python
def depth_from_disparity(disparity, baseline, focal_length):
    """Compute depth from stereo disparity: Z = (f * B) / d."""
    return (focal_length * baseline) / (disparity + 1e-8)


def monocular_depth_from_size(bbox_height_px, real_height_m, focal_length):
    """Estimate depth of object from its observed pixel height."""
    return (real_height_m * focal_length) / (bbox_height_px + 1e-8)
```

---

## 8. Robot Retargeting Mathematics

### 8.1 Morphology Mapping

```python
def human_to_robot_retarget(human_joints, robot_morphology, scale_factor=1.0):
    """
    Retarget human motion to robot with different morphology.
    """
    robot_angles = {}
    
    for robot_joint, human_joint_mapping in robot_morphology.items():
        if isinstance(human_joint_mapping, str):
            human_angles = human_joints.get(human_joint_mapping, (0, 0, 0))
        elif isinstance(human_joint_mapping, tuple):
            human_angles = compute_weighted_joint_angle(
                human_joints, human_joint_mapping
            )
        
        scaled_angles = tuple(a * scale_factor for a in human_angles)
        limits = robot_morphology.get_limits(robot_joint)
        clamped = tuple(
            np.clip(a, limits[0], limits[1])
            for a in scaled_angles
        )
        robot_angles[robot_joint] = clamped
    
    return robot_angles


def compute_weighted_joint_angle(joint_angles, mapping):
    """Compute weighted combination of multiple joints."""
    if isinstance(mapping, tuple) and len(mapping) == 2:
        joint_name, weight = mapping
        return tuple(a * weight for a in joint_angles.get(joint_name, (0, 0, 0)))
    return (0, 0, 0)
```

### 8.2 Action-Intent Mapping

```python
def map_human_action_to_robot_primitive(human_action, context):
    """
    Map high-level human actions to low-level robot primitives.
    """
    intent = None
    
    if context.get("object_in_hand") == "cup" and context.get("hand_near_face"):
        intent = "DRINK"
    elif context.get("object_in_hand") == "phone" and context.get("hand_near_ear"):
        intent = "ANSWER_CALL"
    elif context.get("gesture") == "WAVE":
        intent = "GREET"
    elif context.get("stepping_motion"):
        intent = "WALK"
    
    return intent or "UNKNOWN"
```

---

## 9. Numerical Methods

### 9.1 Least Squares for Scale Recovery

```python
def recover_scale_least_squares(measurements):
    """
    Recover metric scale factor from multiple size measurements.
    
    A · scale = b
    scale = (AᵀWA)⁻¹ · AᵀWb
    """
    A = np.array([m["pixel_size"] for m in measurements])
    b = np.array([m["real_size_m"] for m in measurements])
    weights = np.array([m.get("confidence", 1.0) for m in measurements])
    
    W = np.diag(weights)
    AtWA = A @ W @ A
    AtWb = A @ W @ b
    
    if AtWA > 1e-8:
        scale = AtWb / AtWA
    else:
        scale = 1.0
    
    return scale
```

### 9.2 Moving Average Smoothing

```python
def exponential_moving_average(values, alpha=0.3):
    """
    Exponential Moving Average (EMA) for time series smoothing.
    EMA_t = α · x_t + (1 - α) · EMA_{t-1}
    """
    if not values:
        return []
    
    ema = [values[0]]
    for i in range(1, len(values)):
        ema.append(alpha * values[i] + (1 - alpha) * ema[-1])
    
    return ema
```

### 9.3 Coordinate Transformations

```python
def camera_to_world(camera_point, camera_pose):
    """
    Transform point from camera frame to world frame.
    World_point = R · Camera_point + t
    """
    R = camera_pose[:3, :3]
    t = camera_pose[:3, 3]
    return R @ camera_point + t


def world_to_camera(world_point, camera_pose):
    """
    Transform point from world frame to camera frame.
    Camera_point = Rᵀ · (World_point - t)
    """
    R = camera_pose[:3, :3]
    t = camera_pose[:3, 3]
    return R.T @ (world_point - t)
```

---

## 🏛️ 10. Engineering Principles Applied

### 10.1 SOLID Principles in Code Structure

```python
from abc import ABC, abstractmethod

# SINGLE RESPONSIBILITY: Each class does one thing
class PoseExtractor:
    """Only extracts pose from images."""
    pass

class KinematicCalculator:
    """Only computes kinematic properties."""
    pass

# OPEN/CLOSED: Open for extension, closed for modification
class BaseExporter(ABC):
    @abstractmethod
    def export(self, data): pass

class BVHExporter(BaseExporter):
    def export(self, data): pass

class GLTFExporter(BaseExporter):
    def export(self, data): pass

# LISKOV SUBSTITUTION: Subtypes must be substitutable
def export_data(exporter: BaseExporter, data):
    return exporter.export(data)  # Works with any exporter type

# INTERFACE SEGREGATION: Many specific interfaces > one general
class IExportable(ABC):
    @abstractmethod
    def to_bvh(self): pass

class IRenderable(ABC):
    @abstractmethod
    def to_gltf(self): pass

# DEPENDENCY INVERSION: Depend on abstractions
class MotionProcessor:
    def __init__(self, extractor: PoseExtractor, notifier: BaseExporter):
        self.extractor = extractor
        self.notifier = notifier
```

### 10.2 Design Patterns Used

| Pattern | Where Used | Why |
| :--- | :--- | :--- |
| **Singleton** | HolisticExtractor, ObjectDetector | Ensures only one large model instance is loaded in memory. |
| **Factory** | Exporter creation, Sensor creation | Decouples formatting logic instantiation from main application logic. |
| **Strategy** | Gesture classifiers, IK solvers | Allows swapping solver algorithms (CCD, FABRIK, Analytic) at runtime. |
| **Observer** | MessageBus, event subscriptions | Decouples processing pipeline stages through publish/subscribe. |
| **Circuit Breaker** | Networked API integrations | Prevents cascade failures when remote databases or model servers fail. |
| **Token Bucket** | API gateway rate limiting | Controls client request spikes smoothly. |
| **State Machine** | Task processing lifecycle | Formally transitions states: `queued` $\rightarrow$ `processing` $\rightarrow$ `completed`. |

### 10.3 Performance Optimizations

```python
# 1. Vectorization: Process arrays, not loops
def vectorized_bone_lengths(landmarks):
    """Vectorized bone length computation."""
    pairs = np.array([
        [11, 13], [13, 15], [12, 14], [14, 16],  # arms
        [23, 25], [25, 27], [24, 26], [26, 28],  # legs
    ])
    starts = landmarks[pairs[:, 0]]
    ends = landmarks[pairs[:, 1]]
    vectors = ends - starts
    lengths = np.linalg.norm(vectors, axis=1)
    return lengths

# 2. Memory pre-allocation
class PreallocatedBuffer:
    """Pre-allocate arrays to avoid garbage collection pressure on video loops."""
    def __init__(self, size=1000):
        self.buffer = np.zeros((size, 33, 3))
        self.idx = 0
    
    def add(self, frame):
        self.buffer[self.idx % len(self.buffer)] = frame
        self.idx += 1

# 3. Connection pooling
from contextlib import contextmanager

class ConnectionPool:
    """Reuse database connections to avoid TCP handshake overheads."""
    def __init__(self, size=5):
        self.pool = [create_connection() for _ in range(size)]
        self.available = list(self.pool)
    
    @contextmanager
    def get(self):
        conn = self.available.pop()
        try:
            yield conn
        finally:
            self.available.append(conn)
```

---

## 📊 11. Accuracy & Validation Metrics

To measure 3D pose accuracy and temporal smoothness, SignVerse computes the following metrics:

### 11.1 Mean Per Joint Position Error (MPJPE)
MPJPE measures the Euclidean distance error in 3D coordinate space. For $N$ keypoints:

$$\text{MPJPE} = \frac{1}{N} \sum_{i=1}^N \| \mathbf{p}_{\text{pred}}^{(i)} - \mathbf{p}_{\text{gt}}^{(i)} \|_2$$

```python
def compute_mpjpe(predicted, ground_truth):
    """
    Mean Per Joint Position Error (MPJPE).
    Typical values: SOTA (30-50mm), MediaPipe (50-80mm).
    """
    predicted = np.array(predicted)
    ground_truth = np.array(ground_truth)
    
    # Per-joint L2 distance
    errors = np.linalg.norm(predicted - ground_truth, axis=-1)
    return np.mean(errors)
```

### 11.2 Percentage of Correct Keypoints (PCK)
PCK measures the fraction of keypoints that fall within a defined metric threshold $b$ (e.g., $5\text{cm}$ or $15\text{cm}$):

$$\text{PCK}_b = \frac{1}{N} \sum_{i=1}^N \mathbb{I}\left( \| \mathbf{p}_{\text{pred}}^{(i)} - \mathbf{p}_{\text{gt}}^{(i)} \|_2 < b \right)$$

```python
def compute_pck(predicted, ground_truth, threshold=0.05):
    """
    Percentage of Correct Keypoints (PCK) at a given distance threshold (in meters).
    Returns value in range [0.0, 1.0].
    """
    predicted = np.array(predicted)
    ground_truth = np.array(ground_truth)
    
    # Calculate L2 distances for all joints
    distances = np.linalg.norm(predicted - ground_truth, axis=-1)
    
    # Calculate fraction of joints within the threshold
    correct = np.sum(distances < threshold)
    return float(correct) / len(distances)
```

### 11.3 Area Under the Curve (PCK AUC)
PCK AUC integrates the PCK curve from $0$ up to a maximum threshold (commonly $150\text{mm}$) to provide a threshold-independent coordinate accuracy score.

```python
def compute_pck_auc(predicted, ground_truth, max_threshold=0.15, steps=100):
    """
    Compute Area Under Curve (AUC) for PCK by sampling thresholds.
    """
    thresholds = np.linspace(0.0, max_threshold, steps)
    pck_values = [compute_pck(predicted, ground_truth, t) for t in thresholds]
    return float(np.mean(pck_values))
```

### 11.4 Procrustes-Aligned MPJPE (P-MPJPE)
P-MPJPE applies Procrustes alignment (rigid rotation, scale adjustment, translation alignment) to align the predicted coordinates to the ground-truth skeleton prior to computing MPJPE. This decouples global orientation/position offsets from local relative joint geometry.

```python
def procrustes_alignment(predicted, ground_truth):
    """
    Align predicted points to ground_truth using Orthogonal Procrustes.
    Finds rotation R, scale s, and translation t: s * R * P + t ≈ Y.
    """
    X = np.array(predicted, dtype=float)
    Y = np.array(ground_truth, dtype=float)
    
    # Translate to centroids
    mu_X = X.mean(axis=0)
    mu_Y = Y.mean(axis=0)
    X_zero = X - mu_X
    Y_zero = Y - mu_Y
    
    # Scale normalization
    scale_X = np.linalg.norm(X_zero)
    scale_Y = np.linalg.norm(Y_zero)
    if scale_X > 1e-8 and scale_Y > 1e-8:
        X_zero /= scale_X
        Y_zero /= scale_Y
    
    # Solve for Rotation matrix via SVD (Orthogonal Procrustes)
    H = X_zero.T @ Y_zero
    U, S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    
    # Check for reflection
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
        
    # Scale factor mapping
    s = np.trace(np.diag(S)) * (scale_Y / scale_X) if scale_X > 1e-8 else 1.0
    t = mu_Y - s * R @ mu_X
    
    # Transform
    X_aligned = s * (X @ R.T) + t
    return X_aligned


def compute_p_mpjpe(predicted, ground_truth):
    """
    Procrustes-aligned MPJPE (P-MPJPE).
    Decouples absolute global coordinate error from relative skeletal shape.
    """
    predicted_aligned = procrustes_alignment(predicted, ground_truth)
    return compute_mpjpe(predicted_aligned, ground_truth)
```

### 11.5 Motion Smoothness and Jitter Metrics
Jitter and temporal noise are analyzed by looking at the discrepancy between the derivatives (velocity/acceleration) of the trajectory.

```python
def compute_acceleration_error(predicted_seq, ground_truth_seq, fps=30):
    """
    Compute Mean Absolute Acceleration Error.
    Measures how closely the predicted dynamic transitions match physical acceleration.
    """
    dt = 1.0 / fps
    pred_velocities = [
        (predicted_seq[i+1] - predicted_seq[i-1]) / (2 * dt)
        for i in range(1, len(predicted_seq) - 1)
    ]
    gt_velocities = [
        (ground_truth_seq[i+1] - ground_truth_seq[i-1]) / (2 * dt)
        for i in range(1, len(ground_truth_seq) - 1)
    ]
    
    pred_accel = [
        (pred_velocities[i+1] - pred_velocities[i-1]) / (2 * dt)
        for i in range(1, len(pred_velocities) - 1)
    ]
    gt_accel = [
        (gt_velocities[i+1] - gt_velocities[i-1]) / (2 * dt)
        for i in range(1, len(gt_velocities) - 1)
    ]
    
    errors = [np.linalg.norm(pa - ga) for pa, ga in zip(pred_accel, gt_accel)]
    return float(np.mean(errors))
```
