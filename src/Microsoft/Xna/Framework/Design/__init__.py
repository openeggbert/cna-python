"""Microsoft.Xna.Framework.Design converter projection."""

from ._converters import (
    BoundingBoxConverter, BoundingSphereConverter, ColorConverter,
    MathTypeConverter, MatrixConverter, PlaneConverter, PointConverter,
    QuaternionConverter, RayConverter, RectangleConverter, Vector2Converter,
    Vector3Converter, Vector4Converter,
)

__all__ = [
    "BoundingBoxConverter", "BoundingSphereConverter", "ColorConverter",
    "MathTypeConverter", "MatrixConverter", "PlaneConverter", "PointConverter",
    "QuaternionConverter", "RayConverter", "RectangleConverter",
    "Vector2Converter", "Vector3Converter", "Vector4Converter",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
