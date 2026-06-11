"""
verify_exporters.py — End-to-end verification for the SignVerse 3D Export Pipeline.

Runs standalone (no FastAPI server needed).
Creates a synthetic UnifiedMotionData object with 30 frames,
then runs all exporters and checks that each output is non-empty and structurally valid.

Usage:
    venv\\Scripts\\python verify_exporters.py
"""
import sys
import json
import math
from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "exports" / "verify"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── imports ──────────────────────────────────────────────────────────────────
from backend.services.exporters.data_loader import UnifiedMotionData, CANONICAL_JOINTS
from backend.services.exporters.bvh_exporter import BVHExporter
from backend.services.exporters.fbx_exporter import FBXExporter
from backend.services.exporters.gltf_exporter import GLTFExporter
from backend.services.exporters.mujoco_exporter import MuJoCoExporter
from backend.services.exporters.urdf_exporter import URDFExporter


# ═══════════════════════════════════════════════════════════════════════════ #
# 1. Build synthetic UnifiedMotionData
# ═══════════════════════════════════════════════════════════════════════════ #

def build_synthetic_data(num_frames: int = 30, fps: float = 30.0) -> UnifiedMotionData:
    """
    Create a fake motion session with sinusoidal arm movement
    so that exporters have non-trivial values to process.
    """
    data = UnifiedMotionData(
        session_id="verify-001",
        session_name="Synthetic Verification",
        fps=fps,
        frame_count=num_frames,
        duration_s=num_frames / fps,
        source_type="synthetic",
        action_label="WAVE",
        intent="GREETING",
        created_at="2026-06-10T00:00:00",
        joint_names=list(CANONICAL_JOINTS),
    )

    for i in range(num_frames):
        t = i / fps
        ts_ms = round(t * 1000, 2)
        data.timestamps_ms.append(ts_ms)
        data.confidence_per_frame.append(0.98)
        data.actions_per_frame.append("WAVE")
        data.intents_per_frame.append("GREETING")
        data.interactions_per_frame.append({})

        # Animate: left arm raises and waves
        wave = math.sin(t * 4.0) * 45.0  # degrees
        side = math.cos(t * 2.0) * 20.0

        angles_deg = {}
        angles_rad = {}
        angles_quat = {}
        positions = {}

        # T-pose offsets (approximate)
        TPOSE_POS = {
            "Hips":         [0.0,  0.0,  0.0],
            "Spine":        [0.0,  0.15, 0.0],
            "Chest":        [0.0,  0.30, 0.0],
            "Neck":         [0.0,  0.38, 0.0],
            "Head":         [0.0,  0.45, 0.0],
            "LeftShoulder": [-0.15, 0.28, 0.0],
            "LeftArm":      [-0.35, 0.28, 0.0],
            "LeftForeArm":  [-0.55, 0.28, 0.0],
            "LeftHand":     [-0.65, 0.28, 0.0],
            "RightShoulder":[0.15,  0.28, 0.0],
            "RightArm":     [0.35,  0.28, 0.0],
            "RightForeArm": [0.55,  0.28, 0.0],
            "RightHand":    [0.65,  0.28, 0.0],
            "LeftUpLeg":    [-0.10, -0.10, 0.0],
            "LeftLeg":      [-0.10, -0.52, 0.0],
            "LeftFoot":     [-0.10, -0.90, 0.0],
            "RightUpLeg":   [0.10,  -0.10, 0.0],
            "RightLeg":     [0.10,  -0.52, 0.0],
            "RightFoot":    [0.10,  -0.90, 0.0],
        }

        for jn in CANONICAL_JOINTS:
            # Animate left arm only
            if jn == "LeftShoulder":
                d = [side, 0.0, wave]
            elif jn == "LeftArm":
                d = [wave * 0.5, 0.0, side * 0.3]
            else:
                d = [0.0, 0.0, 0.0]

            import math as m
            r = [m.radians(x) for x in d]
            w = m.cos(m.sqrt(sum(x**2 for x in r)) / 2)
            xyz = [m.sin(m.sqrt(sum(x**2 for x in r)) / 2) * (rd / (m.sqrt(sum(x**2 for x in r)) + 1e-8)) for rd in r]
            q = [w, xyz[0], xyz[1], xyz[2]]

            angles_deg[jn]  = [round(x, 4) for x in d]
            angles_rad[jn]  = [round(x, 6) for x in r]
            angles_quat[jn] = [round(x, 6) for x in q]
            positions[jn]   = TPOSE_POS.get(jn, [0.0, 0.0, 0.0]).copy()

        data.joint_angles_deg.append(angles_deg)
        data.joint_angles_rad.append(angles_rad)
        data.joint_angles_quat.append(angles_quat)
        data.joint_positions_3d.append(positions)
        data.root_positions.append([0.0, 0.0, 0.0])

    # Bone lengths from T-pose
    for jn, pos in data.joint_positions_3d[0].items():
        import math as m
        data.bone_lengths[jn] = round(m.sqrt(sum(x**2 for x in pos)), 4)

    return data


# ═══════════════════════════════════════════════════════════════════════════ #
# 2. Verification runner
# ═══════════════════════════════════════════════════════════════════════════ #

def check(label, content, out_file=None, min_size=50):
    """Assert non-empty output, optionally write file."""
    raw = content if isinstance(content, bytes) else content.encode("utf-8") if isinstance(content, str) else json.dumps(content).encode("utf-8")
    size = len(raw)
    if size < min_size:
        print(f"  [FAIL] {label}: output too small ({size} bytes)")
        return False
    if out_file:
        p = OUTPUT_DIR / out_file
        p.write_bytes(raw)
        print(f"  [ OK ] {label}: {size:,} bytes -> {p.name}")
    else:
        print(f"  [ OK ] {label}: {size:,} bytes")
    return True


def run():
    print("=" * 60)
    print("  SignVerse v4.0 — Exporter Verification Suite")
    print("=" * 60)
    print()

    data = build_synthetic_data(num_frames=60, fps=30.0)
    print(f"Synthetic data: {data.num_frames} frames / {data.fps} fps / {data.duration_s:.2f}s\n")

    results = []

    # ── BVH ──────────────────────────────────────────────────────────── #
    print("[1] BVH Exporter")
    bvh_str = BVHExporter().export(data)
    ok = check("BVH hierarchy + motion", bvh_str, "verify_motion.bvh")
    # Structural checks
    if ok:
        assert "HIERARCHY" in bvh_str, "Missing HIERARCHY"
        assert "MOTION" in bvh_str, "Missing MOTION"
        assert f"Frames: {data.num_frames}" in bvh_str, "Wrong frame count"
        print("  [ OK ] BVH structure validated (HIERARCHY, MOTION, frame count)")
    results.append(("BVH", ok))

    # ── ASCII FBX ─────────────────────────────────────────────────────── #
    print("\n[2] FBX Exporter (ASCII 7.4)")
    fbx_str = FBXExporter().export(data)
    ok = check("ASCII FBX", fbx_str, "verify_motion.fbx")
    if ok:
        assert "FBXHeaderExtension" in fbx_str, "Missing FBX header"
        assert "AnimationCurve" in fbx_str, "Missing AnimationCurve"
        assert "Objects" in fbx_str, "Missing Objects section"
        print("  [ OK ] FBX structure validated (header, objects, curves)")
    results.append(("FBX", ok))

    # ── GLTF 2.0 ─────────────────────────────────────────────────────── #
    print("\n[3] GLTF 2.0 Exporter")
    gltf_dict, bin_buf = GLTFExporter().export(data, embed_binary=True)
    gltf_json = json.dumps(gltf_dict, indent=2)
    ok_json = check("GLTF JSON", gltf_json, "verify_motion.gltf")
    ok_bin  = check("GLTF binary buffer", bin_buf, min_size=100)
    if ok_json:
        assert gltf_dict["asset"]["version"] == "2.0", "Wrong GLTF version"
        assert "animations" in gltf_dict, "Missing animations"
        assert "skins" in gltf_dict, "Missing skins"
        assert "nodes" in gltf_dict, "Missing nodes"
        print("  [ OK ] GLTF structure validated (asset, animations, skins, nodes)")
    results.append(("GLTF", ok_json and ok_bin))

    # ── GLB ──────────────────────────────────────────────────────────── #
    print("\n[4] GLB Binary Builder")
    import struct as st
    gltf_dict2, bin_buf2 = GLTFExporter().export(data, embed_binary=False)
    gltf_dict2["buffers"][0].pop("uri", None)
    jb = json.dumps(gltf_dict2).encode()
    if len(jb) % 4: jb += b" " * (4 - len(jb) % 4)
    bb = bin_buf2
    if len(bb) % 4: bb += b"\x00" * (4 - len(bb) % 4)
    total = 12 + 8 + len(jb) + 8 + len(bb)
    glb = st.pack("<III", 0x46546C67, 2, total)
    glb += st.pack("<II", len(jb), 0x4E4F534A) + jb
    glb += st.pack("<II", len(bb), 0x004E4942) + bb
    ok = check("GLB binary", glb, "verify_motion.glb", min_size=200)
    if ok:
        magic = st.unpack_from("<I", glb, 0)[0]
        assert magic == 0x46546C67, "Wrong GLB magic"
        print("  [ OK ] GLB magic validated (0x46546C67)")
    results.append(("GLB", ok))

    # ── MuJoCo ───────────────────────────────────────────────────────── #
    print("\n[5] MuJoCo XML Exporter")
    mujoco_xml = MuJoCoExporter().export(data)
    ok = check("MuJoCo XML", mujoco_xml, "verify_mujoco.xml")
    if ok:
        assert "<mujoco" in mujoco_xml, "Missing <mujoco>"
        assert "<worldbody>" in mujoco_xml, "Missing worldbody"
        assert "<keyframe>" in mujoco_xml, "Missing keyframe"
        assert "<actuator>" in mujoco_xml, "Missing actuator"
        print("  [ OK ] MuJoCo structure validated (model, worldbody, actuator, keyframe)")
    results.append(("MuJoCo", ok))

    # ── URDF ─────────────────────────────────────────────────────────── #
    print("\n[6] URDF Exporter")
    urdf_xml = URDFExporter().export_urdf(data)
    ok = check("URDF XML", urdf_xml, "verify_humanoid.urdf")
    if ok:
        assert "<robot" in urdf_xml, "Missing <robot>"
        assert "<joint" in urdf_xml, "Missing joints"
        assert "<link" in urdf_xml, "Missing links"
        print("  [ OK ] URDF structure validated (robot, links, joints)")
    results.append(("URDF", ok))

    # ── ROS2 YAML ────────────────────────────────────────────────────── #
    print("\n[7] ROS2 JointTrajectory YAML")
    ros2_yaml = URDFExporter().export_ros2_trajectory(data)
    ok = check("ROS2 YAML", ros2_yaml, "verify_ros2_trajectory.yaml")
    if ok:
        assert "joint_trajectory:" in ros2_yaml, "Missing joint_trajectory key"
        assert "joint_names:" in ros2_yaml, "Missing joint_names"
        assert "positions:" in ros2_yaml, "Missing positions"
        print("  [ OK ] ROS2 YAML structure validated")
    results.append(("ROS2", ok))

    # ── CSV ───────────────────────────────────────────────────────────── #
    print("\n[8] CSV Time Series")
    csv_str = URDFExporter().export_csv(data)
    ok = check("CSV", csv_str, "verify_motion.csv")
    if ok:
        lines = csv_str.strip().split("\n")
        header = lines[0]
        assert "frame_idx" in header, "Missing frame_idx column"
        assert "Hips_rad_x" in header, "Missing joint angle columns"
        assert len(lines) == data.num_frames + 1, f"Expected {data.num_frames+1} lines, got {len(lines)}"
        print(f"  [ OK ] CSV validated ({len(lines)-1} data rows, {len(header.split(','))} columns)")
    results.append(("CSV", ok))

    # ── Pinocchio ─────────────────────────────────────────────────────── #
    print("\n[9] Pinocchio JSON")
    pin_dict = URDFExporter().export_pinocchio(data)
    pin_json = json.dumps(pin_dict, indent=2)
    ok = check("Pinocchio JSON", pin_json, "verify_pinocchio.json")
    if ok:
        assert pin_dict["schema"] == "signverse-pinocchio-v1", "Wrong schema"
        assert "frames" in pin_dict, "Missing frames"
        assert len(pin_dict["frames"]) == data.num_frames, "Frame count mismatch"
        print(f"  [ OK ] Pinocchio validated ({len(pin_dict['frames'])} frames, {pin_dict['nq']} nq)")
    results.append(("Pinocchio", ok))

    # ── Blender Script ────────────────────────────────────────────────── #
    print("\n[10] Blender Python Script")
    blender_py = URDFExporter().export_blender_script(data)
    ok = check("Blender Script", blender_py, "verify_blender_script.py")
    if ok:
        assert "import bpy" in blender_py, "Missing bpy import"
        assert "armature_add" in blender_py, "Missing armature creation"
        assert "keyframe_insert" in blender_py, "Missing keyframe insertion"
        print("  [ OK ] Blender script validated (bpy, armature, keyframes)")
    results.append(("Blender Script", ok))

    # ═══════════════════════════════════════════════════════════════════ #
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    print(f"  Results: {passed}/{total} exporters PASSED")
    print("=" * 60)

    for name, ok in results:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {name}")

    print("\n  Output files written to:", OUTPUT_DIR)
    print()

    if passed == total:
        print("  ALL EXPORTERS VERIFIED SUCCESSFULLY")
        return True
    else:
        print("  WARNING: SOME EXPORTERS FAILED -- check output above")
        return False


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
