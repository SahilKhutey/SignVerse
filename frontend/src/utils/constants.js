export const EXPORT_FORMATS = [
  { id: 'bvh', label: 'Biovision Hierarchy (BVH)', ext: '.bvh', icon: '🦴', desc: 'Standard skeleton animation format for Blender, Maya, and MotionBuilder.' },
  { id: 'fbx', label: 'Autodesk FBX', ext: '.fbx', icon: '🎮', desc: 'Game engine friendly format for Unity, Unreal Engine, and WebGL applications.' },
  { id: 'gltf_scene', label: 'glTF Scene', ext: '.gltf', icon: '📦', desc: '3D scene layout containing both human skeletons and tracked interactable objects.' },
  { id: 'glb_scene', label: 'GLB Scene (Binary)', ext: '.glb', icon: '📦', desc: 'Single-file binary glTF containing meshes, materials, and skeleton hierarchies.' },
  { id: 'mujoco_scene', label: 'MuJoCo XML (MJCF)', ext: '.xml', icon: '🔬', desc: 'Physics-simulation model including humanoid kinematic properties and object collision geometries.' },
  { id: 'urdf', label: 'Robot Description (URDF)', ext: '.urdf', icon: '🤖', desc: 'Unified Robot Description Format describing kinematic links, joints, and visual limits.' },
  { id: 'ros2_trajectory', label: 'ROS2 Trajectory (JSON)', ext: '.json', icon: '🛰️', desc: 'Time-series joint states and object positions serialized for ROS2 controllers.' },
  { id: 'csv_timeseries', label: 'CSV Time Series', ext: '.csv', icon: '📊', desc: 'Flat table of 3D joint locations and object coordinates over every frame.' },
  { id: 'pinocchio_json', label: 'Pinocchio Kinematics (JSON)', ext: '.json', icon: '📏', desc: 'Rigid body dynamics configuration compatible with the Pinocchio C++ library.' },
  { id: 'blender_script', label: 'Blender Python Script', ext: '.py', icon: '🐍', desc: 'Automated script to build armatures and keyframe coordinates directly inside Blender.' },
  { id: 'usd_scene', label: 'Pixar USD Scene', ext: '.usd', icon: '🎬', desc: 'Universal Scene Description for high-end cinematic visualization and staging.' }
]

export const SOURCE_TYPES = {
  upload: { label: 'Local Video', icon: '📤' },
  youtube: { label: 'YouTube Stream', icon: '📺' },
  camera: { label: 'Webcam Stream', icon: '🎥' },
  demo: { label: 'Demo Session', icon: '🤖' }
}

export const BREAKERS = [
  { id: 'yolov8_detector', label: 'YOLOv8 Object Detector' },
  { id: 'holistic_tracker', label: 'MediaPipe Holistic Tracker' },
  { id: 'depth_estimator', label: 'Depth Estimation Engine' },
  { id: 'database_pool', label: 'SQLite Connection Pool' },
  { id: 'message_bus', label: 'Message Bus Dispatcher' }
]
