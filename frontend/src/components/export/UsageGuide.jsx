export default function UsageGuide() {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h4 style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
        📖 Integration Guide
      </h4>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
        <div>
          <h5 style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)' }}>🎬 Blender Integration</h5>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Use the **Blender Python Script (.py)** format. Open Blender, go to the scripting tab, paste the downloaded script, and hit run. It will automatically build the armature bone hierarchy and keyframe all joints.
          </p>
        </div>

        <div>
          <h5 style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-2)' }}>🎮 Unreal & Unity</h5>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Download the **Autodesk FBX (.fbx)**. Drag it directly into your assets folder. Retarget it to your target skeletal mesh using Mixamo or Unreal's IK Retargeter.
          </p>
        </div>

        <div>
          <h5 style={{ fontSize: 12, fontWeight: 600, color: 'var(--success)' }}>🔬 Physics Simulation (MuJoCo)</h5>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Download the **MuJoCo XML (MJCF)**. It defines dynamic inertia parameters, actuator limits, and shapes. Load it directly into `mujoco-py` or Isaac Gym.
          </p>
        </div>

        <div>
          <h5 style={{ fontSize: 12, fontWeight: 600, color: 'var(--warning)' }}>🤖 Robot Description (URDF)</h5>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Download the **URDF** description. It outlines link masses, joint rotation limits, and visual geometries. Copy it to your ROS2 package `urdf/` folder.
          </p>
        </div>
      </div>
    </div>
  )
}
export { UsageGuide }
