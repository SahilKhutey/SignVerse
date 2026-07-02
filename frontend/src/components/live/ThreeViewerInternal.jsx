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

const HOI_COLORS = {
  HOLDING:     '#00e676',
  GRASPING:    '#ff4400',
  LIFTING:     '#00e5ff',
  MOVING:      '#7c4dff',
  PLACING:     '#ff6d00',
  TOUCHING:    '#ff8800',
  NEAR:        '#ffcc00',
  RELEASING:   '#e040fb',
  POINTING:    '#40c4ff',
  DEFAULT:     '#5a6188',
}

function getHOIColor(interactionType) {
  return HOI_COLORS[interactionType] || HOI_COLORS.DEFAULT
}

function getClassColor(className) {
  const colors = {
    cup: '#ff0055',
    bottle: '#00d9ff',
    cellphone: '#7c3aed',
    book: '#10b981',
    chair: '#f59e0b',
    table: '#3b82f6',
    person: '#e4e7f1',
  }
  return colors[className?.toLowerCase()] || '#88aaff'
}

function LiveObjects({ frame }) {
  const objects = frame?.metric_frame?.objects_metric || []
  const interactions = frame?.interaction_graph?.interactions || []

  // Create interaction map
  const interactionMap = {}
  for (const ia of interactions) {
    const tid = ia.object_track_id
    if (tid != null) interactionMap[tid] = ia.interaction_type
  }

  return (
    <group>
      {objects.map((obj) => {
        const tid = obj.track_id
        const pos = obj.position_m // [x_m, y_m, depth_z]
        const size = obj.size_m || [0.1, 0.1, 0.1]
        
        // Scale and coordinates mapping to match LiveSkeleton
        const scale = 1.5
        const posX = pos[0] * scale
        const posY = pos[1] * scale
        const posZ = -pos[2] * scale
        
        const itype = interactionMap[tid]
        const glowColor = getHOIColor(itype)
        const baseColor = getClassColor(obj.class)

        return (
          <group key={tid} position={[posX, posY, posZ]}>
            {/* Object Box Mesh */}
            <mesh castShadow receiveShadow>
              <boxGeometry args={size} />
              <meshPhongMaterial
                color={baseColor}
                emissive={new THREE.Color(glowColor)}
                emissiveIntensity={itype ? 0.8 : 0.2}
                transparent
                opacity={0.8}
                shininess={60}
              />
            </mesh>

            {/* Glowing outer wireframe if interacted */}
            {itype && (
              <mesh>
                <boxGeometry args={size.map(s => s * 1.08)} />
                <meshBasicMaterial
                  color={glowColor}
                  wireframe
                  transparent
                  opacity={0.6}
                />
              </mesh>
            )}

            {/* Object Label Sprite */}
            <Html distanceFactor={3} position={[0, size[1] / 2 + 0.12, 0]} center>
              <div style={{
                background: 'rgba(7, 11, 20, 0.92)',
                border: `1px solid ${itype ? glowColor : '#00d9ff'}`,
                borderRadius: 4,
                padding: '3px 8px',
                color: '#fff',
                fontSize: 10,
                fontWeight: 'bold',
                fontFamily: 'monospace',
                whiteSpace: 'nowrap',
                pointerEvents: 'none',
                boxShadow: itype ? `0 0 10px ${glowColor}` : 'none',
              }}>
                {obj.class} #{tid} {itype ? `· ${itype}` : ''}
              </div>
            </Html>
          </group>
        )
      })}
    </group>
  )
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
      <LiveObjects frame={frame} />
      <IntentLabel frame={frame} />
    </Canvas>
  )
}


