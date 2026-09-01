"""Private CNA C ABI implementation package.

Nothing in this package is part of ``Microsoft.Xna.Framework`` public API.
"""

from .errors import (
    NativeAbiMismatchError,
    NativeCapabilityError,
    NativeError,
    NativeLibraryError,
    NativeUnavailableError,
)
from .loader import EXPECTED_ABI, QUALIFIED_ABI, get_library, require_available

__all__ = [
    "EXPECTED_ABI",
    "QUALIFIED_ABI",
    "NativeAbiMismatchError",
    "NativeCapabilityError",
    "NativeError",
    "NativeLibraryError",
    "NativeUnavailableError",
    "get_library",
    "require_available",
]
