"""Private implementation boundary for CNA's stable C ABI."""

from ._native import NativeUnavailableError, require_available

__all__ = ["NativeUnavailableError", "require_available"]
