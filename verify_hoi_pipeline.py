"""
SignVerse HOI Pipeline -- End-to-End Verification Script
Runs 10 checks covering every layer of the implementation.

Usage:
    python verify_hoi_pipeline.py
"""
import sys
import importlib
import traceback

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PASS = "[PASS]"
FAIL = "[FAIL]"


def check(name: str, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        return True
    except Exception as e:
        print(f"  {FAIL}  {name}")
        print(f"         {e}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        return False


results = []

print("\n" + "="*60)
print("  SignVerse HOI Pipeline — Verification Suite  v5")
print("="*60 + "\n")


# -- CHECK 1: Object Library -------------------------------------
print("Layer 4 — Scene / Object Library")

def c1():
    from backend.services.scene.object_library import OBJECT_CATALOG, get_model, ObjectGeometryBuilder
    assert len(OBJECT_CATALOG) >= 30, f"Expected >=30 models, got {len(OBJECT_CATALOG)}"
    cup = get_model("cup")
    assert cup is not None, "cup model not found"
    assert len(cup.dimensions) >= 1
    # Build a box GLTF mesh
    mesh, meta, buf = ObjectGeometryBuilder.build_box_gltf(0.05, 0.10, 0.05, (0.9,0.5,0.3,1.0))
    assert buf is not None and len(buf) > 0
    assert "primitives" in mesh

results.append(check("Object library: 30+ models, cup geometry, box builder", c1))


# -- CHECK 2: Scene Composer dataclass ---------------------------
def c2():
    import importlib
    # Import directly from the module to avoid __init__ partial state
    sc_mod = importlib.import_module("backend.services.scene.scene_composer")
    SceneData = sc_mod.SceneData
    AnimatedSceneObject = sc_mod.AnimatedSceneObject
    HoldEvent = sc_mod.HoldEvent
    from dataclasses import fields
    field_names = {f.name for f in fields(SceneData)}
    assert "motion_data" in field_names
    assert "session_id" in field_names
    assert "scene_objects" in field_names
    anim_fields = {f.name for f in fields(AnimatedSceneObject)}
    assert "world_trajectory" in anim_fields
    assert "hold_events" in anim_fields

results.append(check("SceneComposer: SceneData / AnimatedSceneObject dataclasses", c2))


# -- CHECK 3: Database schema -------------------------------------
print("\nLayer 2 — Database Schema")

def c3():
    from backend.models.database import ObjectTrajectory, HandObjectInteractionRecord, MotionSession
    from sqlalchemy import inspect as sa_inspect
    engine_ok = True
    # Check table columns
    for attr in ["session_id", "frame_id", "track_id", "class_name", "pos_x", "pos_y", "pos_z"]:
        assert hasattr(ObjectTrajectory, attr), f"ObjectTrajectory missing column: {attr}"
    for attr in ["session_id", "frame_id", "hand", "object_class", "interaction_type", "confidence"]:
        assert hasattr(HandObjectInteractionRecord, attr), f"HOIRecord missing column: {attr}"

results.append(check("DB schema: ObjectTrajectory + HandObjectInteractionRecord columns", c3))


# -- CHECK 4: Exporter package imports ----------------------------
print("\nLayer 5 — Exporters")

def c4():
    from backend.services.exporters import (
        BVHExporter, BVHSceneExporter,
        GLTFExporter, GLTFSceneExporter,
        MuJoCoExporter, MuJoCoSceneExporter,
        USDExporter,
    )
    for cls in [BVHExporter, BVHSceneExporter, GLTFExporter,
                GLTFSceneExporter, MuJoCoExporter, MuJoCoSceneExporter, USDExporter]:
        assert cls is not None, f"{cls} is None"

results.append(check("Exporter package: all 7 exporter classes importable", c4))


# -- CHECK 5: BVH Scene export with synthetic data ---------------
def c5():
    from backend.services.exporters import BVHSceneExporter
    from backend.services.scene.scene_composer import SceneData, AnimatedSceneObject, HoldEvent
    from backend.services.exporters.data_loader import UnifiedMotionData
    from unittest.mock import MagicMock

    data = MagicMock(spec=UnifiedMotionData)
    data.num_frames = 5
    data.fps = 30.0
    data.root_positions = [[0, 0, 0]] * 5
    data.joint_angles_deg = [{} for _ in range(5)]
    data.joint_positions_3d = [{}] * 5
    data.session_name = "test"

    obj = AnimatedSceneObject(
        track_id=1, class_name="cup",
        model=None,
        world_trajectory=[[i, [0.1*i, 0.5, 0.3]] for i in range(5)],
        hold_events=[], first_frame=0, last_frame=4, avg_confidence=0.9,
    )

    scene = SceneData(motion_data=data, session_id="test", scene_objects=[obj])
    bvh_sc = BVHSceneExporter()
    output = bvh_sc.export_scene(scene)
    assert "HIERARCHY" in output
    assert "cup_1" in output
    assert "MOTION" in output
    assert "Frame Time" in output

results.append(check("BVH Scene: person + object ROOT joints in output", c5))


# -- CHECK 6: USD Scene export ------------------------------------
def c6():
    from backend.services.exporters import USDExporter
    from backend.services.scene.scene_composer import SceneData, AnimatedSceneObject
    from unittest.mock import MagicMock

    data = MagicMock()
    data.num_frames = 3
    data.fps = 30.0
    data.root_positions = [[0,0,0]] * 3
    data.joint_angles_quat = [{} for _ in range(3)]
    data.session_name = "test_usd"

    obj = AnimatedSceneObject(
        track_id=7, class_name="bottle",
        model=MagicMock(color_rgba=[0.8,0.3,0.1,1.0], dimensions=[0.04,0.3,0.04], geometry="cylinder"),
        world_trajectory=[[i, [0.2, 0.3, 0.4]] for i in range(3)],
        hold_events=[], first_frame=0, last_frame=2, avg_confidence=0.85,
    )

    scene = SceneData(motion_data=data, session_id="usd_test", scene_objects=[obj])
    usd = USDExporter()
    output = usd.export_scene(scene)
    assert "#usda 1.0" in output
    assert "SignVerseScene" in output
    assert "bottle_7" in output

results.append(check("USD Scene: valid .usda with person + object mesh prim", c6))


# -- CHECK 7: GLTF Scene exporter class --------------------------
def c7():
    from backend.services.exporters.gltf_exporter import GLTFSceneExporter
    assert hasattr(GLTFSceneExporter, "export_scene"), "export_scene method missing"
    assert hasattr(GLTFSceneExporter, "export"), "export method missing (person-only)"

results.append(check("GLTF Scene: GLTFSceneExporter has export + export_scene", c7))


# -- CHECK 8: MuJoCo Scene exporter class -------------------------
def c8():
    from backend.services.exporters.mujoco_exporter import MuJoCoSceneExporter
    assert hasattr(MuJoCoSceneExporter, "export_scene")
    assert hasattr(MuJoCoSceneExporter, "export")

results.append(check("MuJoCo Scene: MuJoCoSceneExporter has export + export_scene", c8))


# -- CHECK 9: HOI router registered in main.py -------------------
print("\nLayer 6 -- API Routing")

def c9():
    # Import just the HOI router module directly to avoid mediapipe init
    from backend.routers.hoi import router as hoi_router
    routes = [r.path for r in hoi_router.routes]
    assert any("timeline" in r or "objects" in r or "stats" in r for r in routes), \
        f"HOI sub-routes not found. Got: {routes}"

results.append(check("HOI router: /api/hoi/* routes defined in hoi.py", c9))


# -- CHECK 10: Exporters router has scene formats -----------------
def c10():
    import os
    path = os.path.join(
        os.path.dirname(__file__),
        "backend", "routers", "exporters.py"
    )
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    for fmt in ["gltf_scene", "glb_scene", "bvh_scene", "mujoco_scene", "usd_scene"]:
        assert fmt in source, f"Format handler '{fmt}' missing from exporters router"

results.append(check("Exporters router: all 5 scene format handlers present", c10))


# -- Summary ------------------------------------------------------
print("\n" + "-"*60)
passed = sum(results)
total  = len(results)
color  = "\033[92m" if passed == total else "\033[93m"
print(f"  {color}{passed}/{total} checks passed\033[0m")
print("-"*60 + "\n")

if passed < total:
    sys.exit(1)
