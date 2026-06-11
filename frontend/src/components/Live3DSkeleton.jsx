import { useRef, useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Html } from '@react-three/drei'
import * as THREE from 'three'

// Skeleton topology: bone = (joint_a, joint_b) in MediaPipe pose indices
const POSE_BONES = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
  [27, 31], [28, 32],
]

const COLOR_BY_BONE = {
  torso: '#3b82f6',
  arm: '#10b981',
  leg: '#f59e0b',
}

/**
 * 3D skeleton that updates in real-time from live perception data.
 */
function LiveSkeleton({ frame }) {
  const groupRef = useRef()
  const jointsRef = useRef([])
  const bonesRef = useRef([])

  // Initialize mesh pool once
  useEffect(() => {
    if (!groupRef.current) return

    // Create 33 joint spheres
    for (let i = 0; i < 33; i++) {
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.025, 12, 12),
        new THREE.MeshStandardMaterial({ color: '#7c3aed', emissive: '#3a1a6e' })
      )
      sphere.visible = false
      groupRef.current.add(sphere)
      jointsRef.current.push(sphere)
    }

    // Create bone cylinders
    for (let i = 0; i < POSE_BONES.length; i++) {
      const cyl = new THREE.Mesh(
        new THREE.CylinderGeometry(0.012, 0.012, 1, 8),
        new THREE.MeshStandardMaterial({ color: '#3b82f6' })
      )
      cyl.visible = false
      groupRef.current.add(cyl)
      bonesRef.current.push(cyl)
    }

    return () => {
      // Clear children
      if (groupRef.current) {
        while (groupRef.current.children.length > 0) {
          groupRef.current.remove(groupRef.current.children[0])
        }
      }
      jointsRef.current = []
      bonesRef.current = []
    }
  }, [])

  // Update skeleton each frame
  useEffect(() => {
    if (!frame?.pose_33 || !groupRef.current) return

    // Update joint positions
    frame.pose_33.forEach((lm, i) => {
      if (i >= jointsRef.current.length) return
      const sphere = jointsRef.current[i]
      if (lm.v > 0.3) {
        // MediaPipe: (x, y) in image coords, y-down; z toward camera
        // Three.js: (x, y, z) with y-up
        sphere.position.set(
          (lm.x - 0.5) * 2.0,    // Normalize and scale to fit view
          -(lm.y - 0.5) * 2.0,   // Flip y
          -lm.z * 2.0
        )
        sphere.visible = true
      } else {
        sphere.visible = false
      }
    })

    // Update bone cylinders
    POSE_BONES.forEach(([a, b], i) => {
      if (i >= bonesRef.current.length) return
      if (a >= 33 || b >= 33) return

      const jointA = jointsRef.current[a]
      const jointB = jointsRef.current[b]
      const cyl = bonesRef.current[i]

      if (!jointA || !jointB || !jointA.visible || !jointB.visible) {
        cyl.visible = false
        return
      }

      const start = jointA.position
      const end = jointB.position
      const mid = start.clone().add(end).multiplyScalar(0.5)
      const dir = end.clone().sub(start)
      const len = dir.length()

      cyl.position.copy(mid)
      cyl.scale.set(1, len, 1)

      // Orient cylinder along direction
      const up = new THREE.Vector3(0, 1, 0)
      cyl.quaternion.setFromUnitVectors(up, dir.clone().normalize())

      // Color by region
      let color = COLOR_BY_BONE.torso
      if (POSE_BONES[i][0] >= 11 && POSE_BONES[i][0] <= 16) color = COLOR_BY_BONE.arm
      if (POSE_BONES[i][0] >= 23 && POSE_BONES[i][0] <= 28) color = COLOR_BY_BONE.leg
      cyl.material.color.set(color)

      cyl.visible = true
    })
  }, [frame])

  return <group ref={groupRef} />
}

/**
 * Floating label that shows current intent/action
 */
function LiveLabel({ frame }) {
  if (!frame) return null
  return (
    <Html position={[0, 1.2, 0]} center>
      <div style={{
        background: 'rgba(10, 14, 39, 0.9)',
        border: '1px solid #00d9ff',
        color: '#00d9ff',
        padding: '8px 14px',
        borderRadius: 8,
        fontFamily: 'monospace',
        fontSize: 12,
        whiteSpace: 'nowrap',
        pointerEvents: 'none',
      }}>
        <div style={{ fontWeight: 'bold', fontSize: 14 }}>
          {frame.primary_intent || 'UNKNOWN'}
        </div>
        <div style={{ color: '#9ca3c4', fontSize: 10 }}>
          {frame.primary_action || 'IDLE'} · {frame.expression || 'NEUTRAL'}
        </div>
      </div>
    </Html>
  )
}

export default function Live3DSkeleton({ frame }) {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        camera={{ position: [0, 0.5, 3], fov: 50 }}
        gl={{ antialias: true }}
        style={{ background: '#0a0e27' }}
      >
        <color attach="background" args={['#0a0e27']} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[2, 4, 2]} intensity={0.8} />
        <directionalLight position={[-2, 2, -2]} intensity={0.3} />

        <Grid
          args={[3, 3]}
          cellColor="#2a3158"
          sectionColor="#1c2348"
          position={[0, -0.8, 0]}
        />

        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          target={[0, 0, 0]}
        />

        <LiveSkeleton frame={frame} />
        <LiveLabel frame={frame} />
      </Canvas>
    </div>
  )
}
