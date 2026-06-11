import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

// Standard MediaPipe pose connections
const POSE_CONNECTIONS = [
  [11, 12],
  [11, 23], [12, 24],
  [23, 24],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
  [23, 25], [25, 27], [27, 29], [29, 31], [27, 31],
  [24, 26], [26, 28], [28, 30], [30, 32], [28, 32],
]

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [9, 10], [10, 11], [11, 12],
  [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
]

const JOINT_NAMES = {
  0: "Nose / Head", 1: "Left Eye Inner", 2: "Left Eye", 3: "Left Eye Outer",
  4: "Right Eye Inner", 5: "Right Eye", 6: "Right Eye Outer",
  7: "Left Ear", 8: "Right Ear", 9: "Mouth Left", 10: "Mouth Right",
  11: "Left Shoulder", 12: "Right Shoulder", 13: "Left Elbow", 14: "Right Elbow",
  15: "Left Wrist", 16: "Right Wrist", 17: "Left Pinky", 18: "Right Pinky",
  19: "Left Index", 20: "Right Index", 21: "Left Thumb", 22: "Right Thumb",
  23: "Left Hip", 24: "Right Hip", 25: "Left Knee", 26: "Right Knee",
  27: "Left Ankle", 28: "Right Ankle", 29: "Left Heel", 30: "Right Heel",
  31: "Left Foot Index", 32: "Right Foot Index"
}

// HOI type → emissive glow color
const HOI_GLOW = {
  HOLDING:     0x00e676,
  GRASPING:    0xff4400,
  LIFTING:     0x00e5ff,
  MOVING:      0x7c4dff,
  PLACING:     0xff6d00,
  TOUCHING:    0xff8800,
  NEAR:        0xffcc00,
  RELEASING:   0xe040fb,
  POINTING:    0x40c4ff,
  DEFAULT:     0x888888,
}

function getHOIColor(interactionType) {
  return HOI_GLOW[interactionType] || HOI_GLOW.DEFAULT
}

export default function Skeleton3DViewer({
  frames,
  currentFrame,
  playing,
  onFrameChange,
  sceneObjects = [],        // List of AnimatedSceneObject from HOI API
  interactions = [],        // Active interactions for current frame
}) {
  const containerRef    = useRef(null)
  const sceneRef        = useRef(null)
  const cameraRef       = useRef(null)
  const rendererRef     = useRef(null)
  const controlsRef     = useRef(null)
  const skeletonGroupRef= useRef(null)
  const objectMeshesRef = useRef({})  // track_id → THREE.Mesh
  const frameDataRef    = useRef(null)

  // Interactive UI State
  const [hoveredJoint, setHoveredJoint] = useState(null)
  const [selectedJoints, setSelectedJoints] = useState([])
  const [hoverMode, setHoverMode] = useState(true)
  const [rulerMode, setRulerMode] = useState(false)

  // Track frame data in ref for raycast callbacks
  useEffect(() => {
    if (frames && frames[currentFrame]) {
      frameDataRef.current = frames[currentFrame]
    }
  }, [frames, currentFrame])

  // ── Initialize Three.js scene ──────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return

    const width  = containerRef.current.clientWidth || 600
    const height = 450

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x070b14)
    scene.fog = new THREE.FogExp2(0x070b14, 0.08)
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.set(0, 0.5, 3.5)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    containerRef.current.appendChild(renderer.domElement)
    rendererRef.current = renderer

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.minDistance = 0.5
    controls.maxDistance = 15
    controlsRef.current = controls

    // Lighting
    scene.add(new THREE.AmbientLight(0x334455, 0.6))

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
    dirLight.position.set(3, 8, 5)
    dirLight.castShadow = true
    scene.add(dirLight)

    const pointLight1 = new THREE.PointLight(0x00d9ff, 1.5, 6)
    pointLight1.position.set(-2, 2, 1)
    scene.add(pointLight1)

    const pointLight2 = new THREE.PointLight(0xff0055, 1.0, 4)
    pointLight2.position.set(2, 1, -1)
    scene.add(pointLight2)

    // Grid
    const gridHelper = new THREE.GridHelper(12, 24, 0x00d9ff22, 0x1a2535)
    gridHelper.position.y = -1.1
    scene.add(gridHelper)

    // Ground plane for shadows
    const groundGeo = new THREE.PlaneGeometry(12, 12)
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x0a1020, roughness: 0.9, metalness: 0.1,
    })
    const ground = new THREE.Mesh(groundGeo, groundMat)
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -1.1
    ground.receiveShadow = true
    scene.add(ground)

    // Skeleton Group
    const skeletonGroup = new THREE.Group()
    scene.add(skeletonGroup)
    skeletonGroupRef.current = skeletonGroup

    // Animation Loop
    let animId
    const animate = () => {
      animId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return
      const w = containerRef.current.clientWidth
      rendererRef.current.setSize(w, height)
      cameraRef.current.aspect = w / height
      cameraRef.current.updateProjectionMatrix()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      if (renderer.domElement && containerRef.current?.contains(renderer.domElement)) {
        containerRef.current.removeChild(renderer.domElement)
      }
      renderer.dispose()
    }
  }, [])

  // ── Update skeleton + objects on frame change ──────────────────
  useEffect(() => {
    const scene = sceneRef.current
    const group = skeletonGroupRef.current
    if (!scene || !group) return
    if (!frames || frames.length === 0) return

    // Clear skeleton group
    while (group.children.length > 0) {
      group.remove(group.children[0])
    }

    const frameData = frames[currentFrame]
    if (!frameData) return

    const scale = 2.0
    const translate = (lm) => new THREE.Vector3(
      (lm.x - 0.5) * scale,
      (0.5 - lm.y) * scale,
      -(lm.z || 0) * scale
    )

    // Materials
    const poseJointMat  = new THREE.MeshPhongMaterial({ color: 0x00d9ff, emissive: 0x006688, shininess: 120 })
    const handJointMat  = new THREE.MeshPhongMaterial({ color: 0xff0055, emissive: 0x660022, shininess: 80 })
    const poseBoneMat   = new THREE.LineBasicMaterial({ color: 0x00ffcc })
    const handBoneMat   = new THREE.LineBasicMaterial({ color: 0xff88aa })

    const jointGeo      = new THREE.SphereGeometry(0.024, 12, 12)
    const handJointGeo  = new THREE.SphereGeometry(0.012, 8, 8)

    const poseLandmarks  = frameData.pose_33 || []
    const leftHandLms    = frameData.left_hand_21 || []
    const rightHandLms   = frameData.right_hand_21 || []

    // Pose joints
    const poseVecs = poseLandmarks.map((lm, idx) => {
      const vec = translate(lm)
      const mesh = new THREE.Mesh(jointGeo, poseJointMat)
      mesh.position.copy(vec)
      mesh.castShadow = true
      mesh.userData = { index: idx, type: 'pose', name: JOINT_NAMES[idx] || `Pose Joint ${idx}`, isJoint: true }
      group.add(mesh)
      return vec
    })

    // Pose bones
    POSE_CONNECTIONS.forEach(([i, j]) => {
      if (poseVecs[i] && poseVecs[j]) {
        const geom = new THREE.BufferGeometry().setFromPoints([poseVecs[i], poseVecs[j]])
        group.add(new THREE.Line(geom, poseBoneMat))
      }
    })

    // Hands
    const drawHand = (lms, handType, jMat, bMat) => {
      const vecs = lms.map((lm, idx) => {
        const v = translate(lm)
        const m = new THREE.Mesh(handJointGeo, jMat)
        m.position.copy(v)
        m.userData = { index: idx, type: handType, name: `${handType === 'left' ? 'Left' : 'Right'} Hand Joint ${idx}`, isJoint: true }
        group.add(m)
        return v
      })
      HAND_CONNECTIONS.forEach(([i, j]) => {
        if (vecs[i] && vecs[j]) {
          group.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([vecs[i], vecs[j]]), bMat
          ))
        }
      })
    }

    if (leftHandLms.length > 0)  drawHand(leftHandLms,  'left',  handJointMat, handBoneMat)
    if (rightHandLms.length > 0) drawHand(rightHandLms, 'right', handJointMat, handBoneMat)

    // ── Interactive 3D Ruler lines ──
    if (rulerMode && selectedJoints.length === 2) {
      let meshA = null, meshB = null
      group.children.forEach(child => {
        if (child.isMesh && child.userData.isJoint && child.userData.type === 'pose') {
          if (child.userData.index === selectedJoints[0].index) meshA = child
          if (child.userData.index === selectedJoints[1].index) meshB = child
        }
      })

      if (meshA && meshB) {
        // Line connection
        const lineGeom = new THREE.BufferGeometry().setFromPoints([meshA.position, meshB.position])
        const lineMat = new THREE.LineBasicMaterial({ color: 0xf43f5e, linewidth: 3 })
        const connectionLine = new THREE.Line(lineGeom, lineMat)
        group.add(connectionLine)

        // Selected markers (rings)
        const ringGeo = new THREE.RingGeometry(0.045, 0.055, 32)
        const ringMat = new THREE.MeshBasicMaterial({ color: 0xf43f5e, side: THREE.DoubleSide })
        
        const ringA = new THREE.Mesh(ringGeo, ringMat)
        ringA.position.copy(meshA.position)
        if (cameraRef.current) ringA.lookAt(cameraRef.current.position)
        group.add(ringA)

        const ringB = new THREE.Mesh(ringGeo, ringMat)
        ringB.position.copy(meshB.position)
        if (cameraRef.current) ringB.lookAt(cameraRef.current.position)
        group.add(ringB)
      }
    }

    // ── Scene Objects (3D tracked objects) ──────────────────────
    // Remove stale object meshes
    const activeIds = new Set(sceneObjects.map(o => o.track_id))
    for (const [tid, mesh] of Object.entries(objectMeshesRef.current)) {
      if (!activeIds.has(Number(tid))) {
        scene.remove(mesh)
        delete objectMeshesRef.current[tid]
      }
    }

    // Current active interactions
    const interactionMap = {}
    for (const ia of interactions) {
      const tid = ia.object_id || ia.object_track_id
      if (tid != null) interactionMap[tid] = ia.interaction_type
    }

    sceneObjects.forEach(obj => {
      const tid = obj.track_id

      // Compute position for current frame
      let pos3d = [0, 0, 2]
      if (obj.world_trajectory && obj.world_trajectory.length > 0) {
        const traj = obj.world_trajectory
        const frameEntry = traj.find(([fi]) => fi === currentFrame)
        if (frameEntry) {
          pos3d = frameEntry[1]
        } else if (traj.length > 0) {
          // Interpolate
          let prev = traj[0], next = traj[traj.length - 1]
          for (let i = 0; i < traj.length - 1; i++) {
            if (traj[i][0] <= currentFrame && traj[i+1][0] >= currentFrame) {
              prev = traj[i]; next = traj[i+1]; break
            }
          }
          const span = Math.max(next[0] - prev[0], 1)
          const t    = (currentFrame - prev[0]) / span
          pos3d = prev[1].map((v, i) => v + t * (next[1][i] - v))
        }
      }

      // Get interaction type for this object
      const itype = interactionMap[tid]
      const glowColor = getHOIColor(itype)

      // Reuse or create mesh
      let mesh = objectMeshesRef.current[tid]
      if (!mesh) {
        const dims = obj.model?.dimensions || [0.1, 0.1, 0.1]
        const [w, h, d] = dims.length >= 3 ? dims : [dims[0]*2, dims[1] || dims[0]*2, dims[0]*2]
        const geo = new THREE.BoxGeometry(w, h, d)
        const baseColor = obj.model?.color_rgba
          ? new THREE.Color(...(obj.model.color_rgba.slice(0, 3)))
          : new THREE.Color(0x88aaff)

        const mat = new THREE.MeshPhongMaterial({
          color: baseColor,
          emissive: new THREE.Color(glowColor),
          emissiveIntensity: 0.4,
          transparent: true,
          opacity: 0.88,
          shininess: 80,
        })
        mesh = new THREE.Mesh(geo, mat)
        mesh.castShadow = true
        scene.add(mesh)
        objectMeshesRef.current[tid] = mesh
      }

      // Update emissive glow based on interaction
      if (mesh.material) {
        const intensity = itype ? 0.6 : 0.15
        mesh.material.emissive.set(glowColor)
        mesh.material.emissiveIntensity = intensity
      }

      // Convert 3D world position to Three.js coords (depth flipped, Y-up)
      mesh.position.set(
        pos3d[0] * scale,
        pos3d[1] * scale,
        -pos3d[2] * 0.8
      )

      // Add class label sprite above object
      if (!mesh.userData.labelAdded) {
        const canvas = document.createElement('canvas')
        canvas.width = 200; canvas.height = 48
        const ctx = canvas.getContext('2d')
        ctx.fillStyle = 'rgba(0,0,0,0.6)'
        ctx.roundRect(0, 0, 200, 48, 8)
        ctx.fill()
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 18px Inter, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(`${obj.class_name} #${tid}`, 100, 30)
        const tex = new THREE.CanvasTexture(canvas)
        const spriteMat = new THREE.SpriteMaterial({ map: tex, transparent: true })
        const sprite = new THREE.Sprite(spriteMat)
        sprite.scale.set(0.5, 0.12, 1)
        const dims2 = obj.model?.dimensions || [0.1, 0.1, 0.1]
        sprite.position.set(0, (dims2[1] || 0.1) * scale + 0.15, 0)
        mesh.add(sprite)
        mesh.userData.labelAdded = true
      }

      mesh.visible = (obj.first_frame <= currentFrame && currentFrame <= obj.last_frame)

      // Interaction highlight ring around held object
      if (itype && ['HOLDING', 'LIFTING', 'MOVING'].includes(itype)) {
        if (!mesh.userData.ringAdded) {
          const ringGeo = new THREE.TorusGeometry(0.12, 0.008, 8, 32)
          const ringMat = new THREE.MeshBasicMaterial({ color: glowColor, transparent: true, opacity: 0.7 })
          const ring = new THREE.Mesh(ringGeo, ringMat)
          ring.rotation.x = Math.PI / 2
          mesh.add(ring)
          mesh.userData.ringAdded = true
          mesh.userData.ring = ring
        }
        mesh.userData.ring.material.color.set(glowColor)
        mesh.userData.ring.visible = true
      } else if (mesh.userData.ring) {
        mesh.userData.ring.visible = false
      }
    })

  }, [frames, currentFrame, sceneObjects, interactions, selectedJoints, rulerMode])

  // ── Auto-play ──────────────────────────────────────────────────
  useEffect(() => {
    if (!playing || !frames || frames.length === 0) return
    const interval = setInterval(() => {
      onFrameChange(prev => {
        const next = prev + 1
        return next >= frames.length ? 0 : next
      })
    }, 33.33)
    return () => clearInterval(interval)
  }, [playing, frames])

  // ── Raycasting Hover & Click Handlers ───────────────────────────
  const raycasterRef = useRef(new THREE.Raycaster())
  const mouseRef = useRef(new THREE.Vector2())

  const getIntersectedJoint = (clientX, clientY) => {
    if (!rendererRef.current || !cameraRef.current || !skeletonGroupRef.current) return null
    
    const rect = rendererRef.current.domElement.getBoundingClientRect()
    const x = ((clientX - rect.left) / rect.width) * 2 - 1
    const y = -((clientY - rect.top) / rect.height) * 2 + 1
    
    mouseRef.current.set(x, y)
    raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current)

    const joints = []
    skeletonGroupRef.current.traverse((child) => {
      if (child.isMesh && child.userData.isJoint) {
        joints.push(child)
      }
    })

    const intersects = raycasterRef.current.intersectObjects(joints)
    if (intersects.length > 0) {
      return intersects[0].object
    }
    return null
  }

  const handlePointerMove = (e) => {
    if (!hoverMode && !rulerMode) return
    const rect = rendererRef.current.domElement.getBoundingClientRect()
    const joint = getIntersectedJoint(e.clientX, e.clientY)
    
    if (joint) {
      const data = joint.userData
      let metricPos = null
      if (frameDataRef.current?.metric_frame?.pose_33_metric && data.type === 'pose') {
        metricPos = frameDataRef.current.metric_frame.pose_33_metric[data.index]
      }

      setHoveredJoint({
        name: data.name,
        index: data.index,
        type: data.type,
        metricPos,
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    } else {
      setHoveredJoint(null)
    }
  }

  const handlePointerDown = (e) => {
    if (!rulerMode) return
    const joint = getIntersectedJoint(e.clientX, e.clientY)
    if (joint && joint.userData.type === 'pose') {
      const data = joint.userData
      const metricPose = frameDataRef.current?.metric_frame?.pose_33_metric
      
      if (metricPose && metricPose[data.index]) {
        const pt = metricPose[data.index]
        setSelectedJoints(prev => {
          if (prev.length >= 2) {
            return [{ name: data.name, index: data.index, position: pt }]
          }
          const exists = prev.some(item => item.index === data.index)
          if (exists) return prev // Avoid selecting same joint twice
          return [...prev, { name: data.name, index: data.index, position: pt }]
        })
      }
    }
  }

  const clearRuler = () => {
    setSelectedJoints([])
  }

  // Calculate 3D distance for selected joints
  let currentRulerDistance = null
  if (selectedJoints.length === 2) {
    const ptA = selectedJoints[0].position
    const ptB = selectedJoints[1].position
    const dx = ptA[0] - ptB[0]
    const dy = ptA[1] - ptB[1]
    const dz = ptA[2] - ptB[2]
    currentRulerDistance = Math.sqrt(dx * dx + dy * dy + dz * dz)
  }

  return (
    <div style={{
      position: 'relative', width: '100%',
      borderRadius: '12px', overflow: 'hidden',
      border: '1px solid var(--border)',
      boxShadow: '0 0 32px rgba(0,217,255,0.06)',
    }}>
      {/* ── Cyber-HUD Toolbar ── */}
      <div style={{
        position: 'absolute',
        top: 10,
        left: 10,
        zIndex: 10,
        display: 'flex',
        gap: '6px',
      }}>
        {/* Hover Toggle */}
        <button
          onClick={() => { setHoverMode(h => !h); setHoveredJoint(null) }}
          style={{
            fontSize: '10px',
            padding: '4px 8px',
            background: hoverMode ? 'rgba(0, 217, 255, 0.15)' : 'rgba(10, 15, 30, 0.85)',
            border: `1px solid ${hoverMode ? 'var(--accent)' : 'rgba(255,255,255,0.1)'}`,
            color: hoverMode ? 'var(--accent)' : '#fff',
            borderRadius: '5px',
            cursor: 'pointer',
            fontWeight: 600,
            transition: 'all 0.12s ease',
          }}
        >
          🖱️ Hover Tooltip
        </button>

        {/* Ruler Toggle */}
        <button
          onClick={() => { setRulerMode(r => !r); clearRuler() }}
          style={{
            fontSize: '10px',
            padding: '4px 8px',
            background: rulerMode ? 'rgba(244, 63, 94, 0.15)' : 'rgba(10, 15, 30, 0.85)',
            border: `1px solid ${rulerMode ? '#f43f5e' : 'rgba(255,255,255,0.1)'}`,
            color: rulerMode ? '#f43f5e' : '#fff',
            borderRadius: '5px',
            cursor: 'pointer',
            fontWeight: 600,
            transition: 'all 0.12s ease',
          }}
        >
          📏 Interactive Ruler
        </button>
      </div>

      {/* Main viewport */}
      <div
        ref={containerRef}
        onPointerMove={handlePointerMove}
        onPointerDown={handlePointerDown}
        style={{ width: '100%', height: '450px', cursor: rulerMode ? 'crosshair' : 'default' }}
      />

      {/* ── Holographic Coordinate Hover Tooltip ── */}
      {hoverMode && hoveredJoint && (
        <div style={{
          position: 'absolute',
          left: `${hoveredJoint.x + 15}px`,
          top: `${hoveredJoint.y + 15}px`,
          background: 'rgba(5, 10, 20, 0.88)',
          border: `1px solid ${hoveredJoint.type === 'pose' ? 'var(--accent)' : '#ff0055'}`,
          boxShadow: `0 0 10px ${hoveredJoint.type === 'pose' ? 'rgba(0, 217, 255, 0.3)' : 'rgba(255, 0, 85, 0.3)'}`,
          color: '#fff',
          padding: '6px 10px',
          borderRadius: '6px',
          fontSize: '10px',
          fontFamily: 'monospace',
          pointerEvents: 'none',
          zIndex: 20,
        }}>
          <div style={{ fontWeight: 'bold', color: hoveredJoint.type === 'pose' ? 'var(--accent)' : '#ff0055', marginBottom: '3px' }}>
            {hoveredJoint.name}
          </div>
          {hoveredJoint.metricPos ? (
            <>
              <div>X: {hoveredJoint.metricPos[0].toFixed(3)}m</div>
              <div>Y: {hoveredJoint.metricPos[1].toFixed(3)}m</div>
              <div>Z: {hoveredJoint.metricPos[2].toFixed(3)}m</div>
            </>
          ) : (
            <div style={{ color: 'rgba(255,255,255,0.5)' }}>No metric data</div>
          )}
        </div>
      )}

      {/* ── Ruler HUD Status Box ── */}
      {rulerMode && (
        <div style={{
          position: 'absolute',
          bottom: '40px',
          right: '10px',
          background: 'rgba(10, 15, 30, 0.85)',
          border: '1px solid rgba(244, 63, 94, 0.3)',
          borderRadius: '8px',
          padding: '10px',
          width: '240px',
          color: '#fff',
          fontSize: '11px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 10,
        }}>
          <div style={{ fontWeight: 'bold', color: '#f43f5e', textTransform: 'uppercase', fontSize: '9px', letterSpacing: '0.05em' }}>
            📏 3D Skeletal Ruler Active
          </div>
          {selectedJoints.length === 0 && (
            <div style={{ color: 'rgba(255,255,255,0.6)' }}>Click a joint on the skeleton to begin measuring.</div>
          )}
          {selectedJoints.length === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <div>Joint A: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{selectedJoints[0].name}</span></div>
              <div style={{ color: 'rgba(255,255,255,0.4)', fontStyle: 'italic' }}>Click a second joint to compute distance...</div>
            </div>
          )}
          {selectedJoints.length === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div>A: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{selectedJoints[0].name}</span></div>
              <div>B: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{selectedJoints[1].name}</span></div>
              <div style={{
                background: 'rgba(244, 63, 94, 0.1)',
                border: '1px solid rgba(244, 63, 94, 0.2)',
                borderRadius: '4px',
                padding: '4px',
                textAlign: 'center',
                marginTop: '2px',
              }}>
                Distance: <strong style={{ color: '#f43f5e', fontFamily: 'monospace', fontSize: '13px' }}>
                  {currentRulerDistance !== null ? `${(currentRulerDistance * 100).toFixed(1)} cm` : '--'}
                </strong>
              </div>
              <button
                onClick={clearRuler}
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: '4px',
                  color: '#fff',
                  fontSize: '9px',
                  padding: '2px 4px',
                  cursor: 'pointer',
                  marginTop: '4px',
                }}
              >
                Reset Ruler
              </button>
            </div>
          )}
        </div>
      )}

      {/* Object count badge */}
      {sceneObjects.length > 0 && (
        <div style={{
          position: 'absolute', top: 10, right: 10,
          background: 'rgba(0,217,255,0.12)',
          border: '1px solid rgba(0,217,255,0.25)',
          borderRadius: 8, padding: '4px 10px',
          fontSize: 11, color: '#00d9ff', fontWeight: 600,
        }}>
          📦 {sceneObjects.length} object{sceneObjects.length !== 1 ? 's' : ''} in scene
        </div>
      )}

      {/* Controls hint */}
      <div style={{
        position: 'absolute', bottom: 10, left: 10,
        background: 'rgba(7, 11, 20, 0.85)',
        padding: '5px 10px', borderRadius: 6,
        fontSize: '0.72rem', color: 'var(--text-secondary)',
        pointerEvents: 'none',
        border: '1px solid rgba(255,255,255,0.04)',
      }}>
        🖱️ Drag: Rotate · Right: Pan · Scroll: Zoom
      </div>
    </div>
  )
}
