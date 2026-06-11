from dataclasses import dataclass, field
from typing import List, Dict, Tuple

class MP:
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT = 31
    RIGHT_FOOT = 32

@dataclass
class Joint:
    """Represents a single skeletal joint node"""
    name: str
    index: int  # MediaPipe landmark index
    parent: str = None  # parent joint name
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # rest-pose offset
    children: List[str] = field(default_factory=list)

class SkeletonGraph:
    """
    Hierarchical skeleton graph built from MediaPipe 33 landmarks.
    Provides mappings for kinematic solvers and BVH hierarchies.
    """

    # Human-readable hierarchical tree layout
    HIERARCHY = {
        "hips": None,
        "spine": "hips",
        "chest": "spine",
        "neck": "chest",
        "head": "neck",
        # Left arm
        "left_shoulder": "chest",
        "left_upper_arm": "left_shoulder",
        "left_lower_arm": "left_upper_arm",
        "left_hand": "left_lower_arm",
        # Right arm
        "right_shoulder": "chest",
        "right_upper_arm": "right_shoulder",
        "right_lower_arm": "right_upper_arm",
        "right_hand": "right_lower_arm",
        # Left leg
        "left_hip": "hips",
        "left_upper_leg": "left_hip",
        "left_lower_leg": "left_upper_leg",
        "left_foot": "left_lower_leg",
        "left_toe": "left_foot",
        # Right leg
        "right_hip": "hips",
        "right_upper_leg": "right_hip",
        "right_lower_leg": "right_upper_leg",
        "right_foot": "right_lower_leg",
        "right_toe": "right_foot",
    }

    # Midpoints and mapping to MediaPipe indices
    MP_INDEX = {
        "hips": (MP.LEFT_HIP + MP.RIGHT_HIP) // 2,
        "spine": (MP.LEFT_HIP + MP.RIGHT_HIP) // 2,
        "chest": (MP.LEFT_SHOULDER + MP.RIGHT_SHOULDER) // 2,
        "neck": (MP.LEFT_SHOULDER + MP.RIGHT_SHOULDER) // 2,
        "head": MP.NOSE,
        "left_shoulder": MP.LEFT_SHOULDER,
        "left_upper_arm": MP.LEFT_ELBOW,
        "left_lower_arm": MP.LEFT_WRIST,
        "left_hand": MP.LEFT_WRIST,
        "right_shoulder": MP.RIGHT_SHOULDER,
        "right_upper_arm": MP.RIGHT_ELBOW,
        "right_lower_arm": MP.RIGHT_WRIST,
        "right_hand": MP.RIGHT_WRIST,
        "left_hip": MP.LEFT_HIP,
        "left_upper_leg": MP.LEFT_KNEE,
        "left_lower_leg": MP.LEFT_ANKLE,
        "left_foot": MP.LEFT_FOOT,
        "left_toe": MP.LEFT_FOOT,
        "right_hip": MP.RIGHT_HIP,
        "right_upper_leg": MP.RIGHT_KNEE,
        "right_lower_leg": MP.RIGHT_ANKLE,
        "right_foot": MP.RIGHT_FOOT,
        "right_toe": MP.RIGHT_FOOT,
    }

    SYMMETRIC = {
        MP.LEFT_SHOULDER: MP.RIGHT_SHOULDER,
        MP.LEFT_ELBOW: MP.RIGHT_ELBOW,
        MP.LEFT_WRIST: MP.RIGHT_WRIST,
        MP.LEFT_HIP: MP.RIGHT_HIP,
        MP.LEFT_KNEE: MP.RIGHT_KNEE,
        MP.LEFT_ANKLE: MP.RIGHT_ANKLE,
        MP.LEFT_FOOT: MP.RIGHT_FOOT,
    }

    def __init__(self):
        self.joints: Dict[str, Joint] = self._build_graph()

    def _build_graph(self) -> Dict[str, Joint]:
        joints = {}
        for name, parent_name in self.HIERARCHY.items():
            mp_idx = self.MP_INDEX[name]
            joints[name] = Joint(
                name=name, index=mp_idx, parent=parent_name, children=[]
            )

        # Wire up child relations
        for name, joint in joints.items():
            if joint.parent and joint.parent in joints:
                joints[joint.parent].children.append(name)

        return joints

    def get_chain_to_root(self, joint_name: str) -> List[str]:
        """Traverse up hierarchy tree and return list of parent node names"""
        chain = []
        current = self.joints.get(joint_name)
        while current:
            chain.append(current.name)
            current = self.joints.get(current.parent) if current.parent else None
        return chain

    def get_bones(self) -> List[Tuple[str, str, int, int]]:
        """Returns bone segments as (parent_name, child_name, parent_index, child_index)"""
        bones = []
        for name, joint in self.joints.items():
            if joint.parent:
                parent = self.joints[joint.parent]
                bones.append((joint.parent, name, parent.index, joint.index))
        return bones

    def get_ordered_joints(self) -> List[Joint]:
        """Returns DFS ordered joints for flat writing in BVH frames"""
        ordered = []

        def dfs(name):
            joint = self.joints[name]
            ordered.append(joint)
            for child in joint.children:
                dfs(child)

        dfs("hips")
        return ordered
