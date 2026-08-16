"""Private implementation boundary for CNA's stable C ABI."""


class NativeUnavailableError(RuntimeError):
    """Raised while the CNA native ABI is unavailable."""


def require_available() -> None:
    """Fail explicitly instead of pretending that a native runtime exists."""
    raise NativeUnavailableError("CNA native C ABI is not available yet")
