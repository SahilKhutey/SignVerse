"""
3D Object Library — procedural geometry catalog for scene reconstruction.

Every YOLO-detectable class gets:
  • Real-world dimensions (m)
  • A color (RGBA)
  • A geometry type (box | cylinder | capsule | sphere)
  • Pivot offset (for hand-parenting during hold events)

The ObjectGeometryBuilder generates:
  • GLTF mesh + binary buffer bytes
  • MuJoCo <geom> XML snippets
  • URDF <geometry> XML snippets
  • Blender Python mesh creation code
"""
import struct
import base64
import math
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════ #
# Data model
# ═══════════════════════════════════════════════════════════════════ #

@dataclass
class ObjectModel3D:
    """3D model spec for one YOLO class."""
    class_name:      str
    geometry:        str             # "box" | "cylinder" | "sphere" | "capsule"
    dimensions:      Tuple           # (w, h, d) for box; (r, h) for cylinder; (r,) for sphere
    pivot_offset:    Tuple[float, float, float]  # hand grasp point relative to object centre
    color_rgba:      Tuple[float, float, float, float]  # [0,1] linear
    real_dims_m:     Tuple[float, float, float]  # actual width, height, depth in metres

    def mujoco_size_str(self) -> str:
        """Return MuJoCo size= attribute string."""
        g = self.geometry
        d = self.dimensions
        if g == "box":
            # MuJoCo box size is half-extents
            return f"{d[0]/2:.4f} {d[1]/2:.4f} {d[2]/2:.4f}"
        elif g == "cylinder":
            return f"{d[0]:.4f} {d[1]/2:.4f}"
        elif g == "sphere":
            return f"{d[0]:.4f}"
        elif g == "capsule":
            return f"{d[0]:.4f} {d[1]/2:.4f}"
        return "0.05 0.05 0.05"

    def urdf_geometry_xml(self) -> str:
        g = self.geometry
        d = self.dimensions
        if g == "box":
            return f'<box size="{d[0]:.4f} {d[1]:.4f} {d[2]:.4f}"/>'
        elif g == "cylinder":
            return f'<cylinder radius="{d[0]:.4f}" length="{d[1]:.4f}"/>'
        elif g == "sphere":
            return f'<sphere radius="{d[0]:.4f}"/>'
        return f'<box size="0.1 0.1 0.1"/>'

    def blender_mesh_code(self, var_name: str) -> str:
        """Return Blender Python snippet to create a mesh primitive."""
        g = self.geometry
        d = self.dimensions
        r, g2, b, a = self.color_rgba
        if g == "box":
            return (
                f'bpy.ops.mesh.primitive_cube_add(size=1.0)\n'
                f'{var_name} = bpy.context.active_object\n'
                f'{var_name}.scale = ({d[0]:.4f}, {d[2]:.4f}, {d[1]:.4f})\n'
                f'{var_name}.name = "{self.class_name}"\n'
                f'mat_{var_name} = bpy.data.materials.new("{self.class_name}_mat")\n'
                f'mat_{var_name}.use_nodes = False\n'
                f'mat_{var_name}.diffuse_color = ({r:.3f}, {g2:.3f}, {b:.3f}, {a:.3f})\n'
                f'{var_name}.data.materials.append(mat_{var_name})\n'
            )
        elif g == "cylinder":
            return (
                f'bpy.ops.mesh.primitive_cylinder_add(radius={d[0]:.4f}, depth={d[1]:.4f})\n'
                f'{var_name} = bpy.context.active_object\n'
                f'{var_name}.name = "{self.class_name}"\n'
                f'mat_{var_name} = bpy.data.materials.new("{self.class_name}_mat")\n'
                f'mat_{var_name}.use_nodes = False\n'
                f'mat_{var_name}.diffuse_color = ({r:.3f}, {g2:.3f}, {b:.3f}, {a:.3f})\n'
                f'{var_name}.data.materials.append(mat_{var_name})\n'
            )
        elif g == "sphere":
            return (
                f'bpy.ops.mesh.primitive_uv_sphere_add(radius={d[0]:.4f})\n'
                f'{var_name} = bpy.context.active_object\n'
                f'{var_name}.name = "{self.class_name}"\n'
            )
        return f'bpy.ops.mesh.primitive_cube_add()\n{var_name} = bpy.context.active_object\n'


# ═══════════════════════════════════════════════════════════════════ #
# Object Catalog  (80 COCO classes)
# ═══════════════════════════════════════════════════════════════════ #

def _box(w, h, d, pivot=(0,0,0), color=(0.5,0.5,0.5,1.0), name=""):
    return ObjectModel3D(name, "box", (w, h, d), pivot, color, (w, h, d))

def _cyl(r, h, pivot=(0,0,0), color=(0.5,0.5,0.5,1.0), name=""):
    return ObjectModel3D(name, "cylinder", (r, h), pivot, color, (r*2, h, r*2))

def _sph(r, pivot=(0,0,0), color=(0.5,0.5,0.5,1.0), name=""):
    return ObjectModel3D(name, "sphere", (r,), pivot, color, (r*2, r*2, r*2))


OBJECT_CATALOG: Dict[str, ObjectModel3D] = {}

def _reg(name, geom, dims, pivot, color):
    """Register object model. real_dims = (w, h, d) always 3 floats."""
    if geom == "box":
        real = (dims[0], dims[1], dims[2])
    elif geom in ("cylinder", "capsule"):
        r, h = dims[0], dims[1]
        real = (r * 2, h, r * 2)
    elif geom == "sphere":
        r = dims[0]
        real = (r * 2, r * 2, r * 2)
    else:
        real = (dims[0], dims[0], dims[0])
    OBJECT_CATALOG[name] = ObjectModel3D(name, geom, dims, pivot, color, real)

# ── Tableware ─────────────────────────────────────────────────────
_reg("cup",        "cylinder", (0.04, 0.10), (0,-0.05,0), (0.85, 0.75, 0.60, 1.0))
_reg("bottle",     "cylinder", (0.035, 0.25),(0,-0.12,0), (0.30, 0.60, 0.30, 1.0))
_reg("wine glass", "cylinder", (0.035, 0.20),(0,-0.10,0), (0.90, 0.90, 0.95, 0.85))
_reg("bowl",       "cylinder", (0.075, 0.08),(0,-0.04,0), (0.85, 0.80, 0.70, 1.0))
_reg("fork",       "box",      (0.015,0.20,0.008),(0,-0.10,0),(0.80,0.80,0.80,1.0))
_reg("knife",      "box",      (0.015,0.22,0.005),(0,-0.11,0),(0.75,0.75,0.75,1.0))
_reg("spoon",      "box",      (0.03, 0.18, 0.008),(0,-0.09,0),(0.80,0.80,0.80,1.0))
# ── Food ──────────────────────────────────────────────────────────
_reg("banana",     "capsule",  (0.02, 0.18), (0,0,0),    (1.0, 0.90, 0.10, 1.0))
_reg("apple",      "sphere",   (0.04,),      (0,0,0),    (0.90, 0.15, 0.10, 1.0))
_reg("orange",     "sphere",   (0.04,),      (0,0,0),    (1.0, 0.55, 0.05, 1.0))
_reg("sandwich",   "box",      (0.12, 0.05, 0.12),(0,0,0),(0.90,0.80,0.55,1.0))
_reg("pizza",      "cylinder", (0.175,0.03), (0,0,0),    (0.95,0.65,0.20,1.0))
_reg("donut",      "cylinder", (0.05, 0.03), (0,0,0),    (0.85,0.55,0.30,1.0))
_reg("cake",       "cylinder", (0.125,0.12), (0,0,0),    (0.95,0.90,0.75,1.0))
_reg("hot dog",    "capsule",  (0.02, 0.14), (0,0,0),    (0.90,0.65,0.35,1.0))
_reg("broccoli",   "sphere",   (0.075,),     (0,0,0),    (0.15,0.65,0.15,1.0))
_reg("carrot",     "capsule",  (0.015,0.18), (0,0,0),    (0.95,0.50,0.10,1.0))
# ── Electronics ───────────────────────────────────────────────────
_reg("cell phone", "box",      (0.07, 0.15, 0.009),(0,0,0),(0.12,0.12,0.14,1.0))
_reg("laptop",     "box",      (0.35, 0.022, 0.25),(0,0,-0.125),(0.20,0.20,0.22,1.0))
_reg("mouse",      "box",      (0.06, 0.03, 0.10), (0,0,0),(0.25,0.25,0.25,1.0))
_reg("remote",     "box",      (0.05, 0.018, 0.20),(0,-0.08,0),(0.15,0.15,0.18,1.0))
_reg("keyboard",   "box",      (0.45, 0.018, 0.15),(0,0,0),(0.18,0.18,0.20,1.0))
_reg("tv",         "box",      (1.00, 0.58, 0.04), (0,0,0),(0.10,0.10,0.12,1.0))
_reg("microwave",  "box",      (0.50, 0.33, 0.40), (0,0,0),(0.60,0.60,0.60,1.0))
_reg("oven",       "box",      (0.60, 0.88, 0.60), (0,0,0),(0.55,0.55,0.55,1.0))
_reg("toaster",    "box",      (0.28, 0.20, 0.20), (0,0,0),(0.65,0.65,0.65,1.0))
_reg("refrigerator","box",     (0.70, 1.80, 0.70), (0,0,0),(0.90,0.90,0.90,1.0))
# ── Books / stationery ────────────────────────────────────────────
_reg("book",       "box",      (0.20, 0.028, 0.15),(0,0,0.075),(0.65,0.45,0.25,1.0))
_reg("scissors",   "box",      (0.08, 0.015, 0.15),(0,0,0),(0.70,0.70,0.10,1.0))
_reg("toothbrush", "capsule",  (0.01, 0.19), (0,-0.09,0),(0.40,0.80,0.40,1.0))
_reg("hair drier", "capsule",  (0.04, 0.25), (0,-0.10,0),(0.90,0.90,0.20,1.0))
_reg("vase",       "cylinder", (0.075, 0.28),(0,-0.14,0),(0.40,0.55,0.80,1.0))
_reg("clock",      "cylinder", (0.15, 0.04), (0,0,0),    (0.80,0.80,0.80,1.0))
_reg("teddy bear", "sphere",   (0.15,),      (0,0,0),    (0.90,0.75,0.55,1.0))
# ── Bags ──────────────────────────────────────────────────────────
_reg("backpack",   "box",      (0.35, 0.50, 0.20),(0,0,0),(0.25,0.25,0.70,1.0))
_reg("handbag",    "box",      (0.35, 0.28, 0.14),(0,0,0),(0.40,0.20,0.10,1.0))
_reg("suitcase",   "box",      (0.50, 0.70, 0.28),(0,0,0),(0.30,0.30,0.35,1.0))
_reg("umbrella",   "capsule",  (0.05, 0.90), (0,-0.40,0),(0.20,0.20,0.80,1.0))
# ── Sports ────────────────────────────────────────────────────────
_reg("sports ball","sphere",   (0.11,),      (0,0,0),    (0.90,0.55,0.10,1.0))
_reg("baseball bat","capsule", (0.035,0.85),(0,-0.38,0), (0.70,0.50,0.30,1.0))
_reg("tennis racket","box",    (0.27, 0.68, 0.04),(0,0,0),(0.20,0.80,0.20,1.0))
_reg("skateboard", "box",      (0.20, 0.09, 0.80),(0,0,0),(0.50,0.35,0.15,1.0))
_reg("frisbee",    "cylinder", (0.135,0.02), (0,0,0),    (0.85,0.15,0.15,1.0))
_reg("kite",       "box",      (1.00, 0.80, 0.008),(0,0,0),(0.90,0.50,0.10,1.0))
_reg("skis",       "box",      (0.10, 1.80, 0.10),(0,0,0),(0.80,0.80,0.85,1.0))
_reg("snowboard",  "box",      (0.28, 1.50, 0.09),(0,0,0),(0.90,0.50,0.20,1.0))
# ── Furniture ─────────────────────────────────────────────────────
_reg("chair",      "box",      (0.50, 1.00, 0.50),(0,0,0),(0.55,0.45,0.35,1.0))
_reg("couch",      "box",      (2.00, 0.90, 0.90),(0,0,0),(0.60,0.50,0.40,1.0))
_reg("bed",        "box",      (1.60, 0.55, 2.10),(0,0,0),(0.80,0.75,0.70,1.0))
_reg("dining table","box",     (1.50, 0.75, 0.90),(0,0,0),(0.65,0.50,0.35,1.0))
_reg("toilet",     "box",      (0.40, 0.80, 0.65),(0,0,0),(0.90,0.90,0.90,1.0))
_reg("sink",       "box",      (0.60, 0.25, 0.50),(0,0,0),(0.80,0.85,0.90,1.0))
_reg("potted plant","box",     (0.28, 0.45, 0.28),(0,0,0),(0.20,0.65,0.20,1.0))
_reg("bench",      "box",      (1.50, 0.80, 0.55),(0,0,0),(0.60,0.48,0.35,1.0))
# ── Fallback for unknown ───────────────────────────────────────────
_DEFAULT = ObjectModel3D("__default__","box",(0.10,0.10,0.10),(0,0,0),(0.6,0.6,0.6,1.0),(0.10,0.10,0.10))


def get_model(class_name: str) -> ObjectModel3D:
    """Return the 3D model spec for a YOLO class name."""
    m = OBJECT_CATALOG.get(class_name, _DEFAULT)
    if m is _DEFAULT:
        m = ObjectModel3D(class_name, "box", (0.10,0.10,0.10), (0,0,0), (0.6,0.6,0.6,1.0), (0.10,0.10,0.10))
    return m


# ═══════════════════════════════════════════════════════════════════ #
# GLTF Geometry Builder
# ═══════════════════════════════════════════════════════════════════ #

class ObjectGeometryBuilder:
    """
    Builds minimal GLTF mesh + binary buffer data for a given object class.
    Returns (mesh_dict, accessor_list, buffer_bytes) ready to embed in a GLTF.
    """

    @staticmethod
    def build_box_gltf(
        w: float, h: float, d: float,
        color_rgba: Tuple[float,float,float,float],
    ) -> Tuple[Dict, bytes]:
        """
        Procedurally generate a GLTF box mesh (8 vertices, 12 triangles).
        Returns (mesh_json_fragment, buffer_bytes).
        """
        hw, hh, hd = w/2, h/2, d/2

        # 8 corners of the box
        positions = [
            (-hw,-hh,-hd),(+hw,-hh,-hd),(+hw,+hh,-hd),(-hw,+hh,-hd),
            (-hw,-hh,+hd),(+hw,-hh,+hd),(+hw,+hh,+hd),(-hw,+hh,+hd),
        ]
        # 12 triangles (2 per face, 6 faces)
        indices = [
            0,1,2, 0,2,3,  # back
            4,6,5, 4,7,6,  # front
            0,4,5, 0,5,1,  # bottom
            2,6,7, 2,7,3,  # top
            1,5,6, 1,6,2,  # right
            0,3,7, 0,7,4,  # left
        ]
        normals = [
            (0,0,-1),(0,0,-1),(0,0,-1),(0,0,-1),
            (0,0,+1),(0,0,+1),(0,0,+1),(0,0,+1),
            (0,-1,0),(0,-1,0),(0,-1,0),(0,-1,0),
            (0,+1,0),(0,+1,0),(0,+1,0),(0,+1,0),
            (+1,0,0),(+1,0,0),(+1,0,0),(+1,0,0),
            (-1,0,0),(-1,0,0),(-1,0,0),(-1,0,0),
        ][:8]  # just use per-vertex approximation

        # Pack binary data
        pos_fmt   = struct.pack(f"<{len(positions)*3}f",
                                *[v for p in positions for v in p])
        norm_fmt  = struct.pack(f"<{8*3}f",
                                *[v for n in ([(-hw,-hh,-hd)]*8) for v in [0.0,0.0,-1.0]])
        idx_fmt   = struct.pack(f"<{len(indices)}H", *indices)

        # Align to 4 bytes
        def pad4(b): return b + b"\x00" * ((4 - len(b) % 4) % 4)
        pos_bytes  = pad4(pos_fmt)
        norm_bytes = pad4(norm_fmt)
        idx_bytes  = pad4(idx_fmt)

        buf = pos_bytes + norm_bytes + idx_bytes
        pos_offset  = 0
        norm_offset = len(pos_bytes)
        idx_offset  = len(pos_bytes) + len(norm_bytes)

        n_verts = len(positions)
        n_idx   = len(indices)

        mesh = {
            "name": "object_mesh",
            "primitives": [{
                "attributes": {
                    "POSITION": 0,   # accessor index will be patched by caller
                    "NORMAL":   1,
                },
                "indices": 2,
                "mode": 4,           # TRIANGLES
                "material": 0,
            }],
        }

        meta = {
            "pos_offset": pos_offset, "pos_len": len(pos_bytes), "n_verts": n_verts,
            "norm_offset": norm_offset, "norm_len": len(norm_bytes),
            "idx_offset": idx_offset,  "idx_len":  len(idx_bytes), "n_idx": n_idx,
            "color_rgba": color_rgba,
        }
        return mesh, meta, buf

    @classmethod
    def build(cls, class_name: str) -> Tuple[Dict, Dict, bytes]:
        """
        Build GLTF mesh + meta + buffer for any object class.
        Falls back to box geometry for all types (sufficient for collision proxies).
        """
        model = get_model(class_name)
        g = model.geometry
        d = model.dimensions
        color = model.color_rgba

        if g == "box":
            return cls.build_box_gltf(d[0], d[1], d[2], color)
        elif g in ("cylinder", "capsule"):
            r, h = d[0], d[1]
            return cls.build_box_gltf(r*2, h, r*2, color)  # box proxy
        elif g == "sphere":
            r = d[0]
            return cls.build_box_gltf(r*2, r*2, r*2, color)
        else:
            return cls.build_box_gltf(0.10, 0.10, 0.10, color)
