"""
SignVerse Scene Package
Procedural 3D geometry + scene composition for object-inclusive exports.
"""
from .object_library import OBJECT_CATALOG, ObjectModel3D, ObjectGeometryBuilder, get_model
# scene_composer imports separately to avoid circular dependency
# (scene_composer -> object_library is fine; object_library must NOT import scene_composer)

__all__ = [
    "OBJECT_CATALOG", "ObjectModel3D", "ObjectGeometryBuilder", "get_model",
]
