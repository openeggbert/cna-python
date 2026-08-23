"""Microsoft.Xna.Framework.Graphics.PackedVector managed projection."""

from ._packed import (
    Alpha8, Bgr565, Bgra4444, Bgra5551, Byte4, HalfSingle, HalfVector2,
    HalfVector4, IPackedVector, IPackedVectorOfT, NormalizedByte2,
    NormalizedByte4, NormalizedShort2, NormalizedShort4, Rg32, Rgba1010102,
    Rgba64, Short2, Short4,
)

__all__ = [
    "Alpha8", "Bgr565", "Bgra4444", "Bgra5551", "Byte4", "HalfSingle",
    "HalfVector2", "HalfVector4", "IPackedVector", "IPackedVectorOfT",
    "NormalizedByte2", "NormalizedByte4", "NormalizedShort2",
    "NormalizedShort4", "Rg32", "Rgba1010102", "Rgba64", "Short2", "Short4",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
