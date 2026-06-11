import { useRef, useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Html } from '@react-three/drei'
import * as THREE from 'three'

const POSE_BONES = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
  [27, 31], [28, 32],
]

function LiveSkeleton({ frame }) {
  const groupRef = useRef()
  const jointsRef = useRef([])
  const bonesRef = useRef([])
  
  useEffect(() => {
    if (!groupRef.current) return
    for (let i = 0; i < 33; i++) {
      const s = new THREE.Mesh(
        new THREE.SphereGeometry(0.025, 12, 12),
        new THREE.MeshStandardMaterial({ color: '#7c3aed', emissive: '#3a1a6e' })
      )
      s.visible = false
      groupRef.current.add(s)
      jointsRef.current.push(s)
    }
    for (let i = 0; i < POSE_BONES.length; i++) {
      const c = new THREE.Mesh(
        new THREE.CylinderGeometry(0.012, 0.012, 1, 8),
        new THREE.MeshStandardMaterial({ color: '#3b82f6' })
      )
      c.visible = false
      groupRef.current.add(c)
      bonesRef.current.push(c)
    }
    return () => { jointsRef.current = []; bonesRef.current = [] }
  }, [])
  
  useEffect(() => {
    if (!frame?.pose_33) return
    frame.pose_33.forEach((lm, i) => {
      if (i >= jointsRef.current.length) return
      const s = jointsRef.current[i]
      if (lm.v > 0.3) {
        s.position.set((lm.x - 0.5) * 1.5, -(lm.y - 0.5) * 1.5, -lm.z * 1.5)
        s.visible = true
      } else {
        s.visible = false
      }
    })
    POSE_BONES.forEach(([a, b], i) => {
      if (i >= bonesRef.current.length) return
      const ja = jointsRef.current[a]
      const jb = jointsRef.current[b]
      const cyl = bonesRef.current[i]
      if (!ja?.visible || !jb?.visible) { cyl.visible = false; return }
      const start = ja.position
      const end = jb.position
      const mid = start.clone().add(end).multiplyScalar(0.5)
      const dir = end.clone().sub(start)
      const len = dir.length()
      cyl.position.copy(mid)
      cyl.scale.set(1, len, 1)
      cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize())
      cyl.visible = true
    })
  }, [frame])
  
  return <group ref={groupRef} />
}

function IntentLabel({ frame }) {
  if (!frame) return null
  return (
    <Html position={[0, 0.8, 0]} center>
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
        <div style={{ fontWeight: 'bold' }}>{frame.primary_intent}</div>
        <div style={{ color: '#9ca3c4', fontSize: 10 }}>{frame.primary_action} · {frame.expression}</div>
      </div>
    </Html>
  )
}

export default function ThreeViewerInternal({ frame }) {
  return (
    <Canvas
      camera={{ position: [0, 0, 2], fov: 50 }}
      gl={{ antialias: true }}
      style={{ background: '#0a0e27', minHeight: 250, height: '100%' }}
    >
      <color attach="background" args={['#0a0e27']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[2, 4, 2]} intensity={0.8} />
      <directionalLight position={[-2, 2, -2]} intensity={0.3} />
      <Grid args={[3, 3]} cellColor="#2a3158" sectionColor="#1c2348" position={[0, -0.8, 0]} />
      <OrbitControls enableDamping dampingFactor={0.05} target={[0, 0, 0]} />
      <LiveSkeleton frame={frame} />
      <IntentLabel frame={frame} />
    </Canvas>
  )
}
