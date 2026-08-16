"""Private boundary for the future CNA C ABI mapping."""


class NativeUnavailableError(RuntimeError):
    """Raised when the CNA native ABI cannot be used."""


def require_available() -> None:
    """Fail explicitly while the upstream stable C ABI is unavailable."""
    raise NativeUnavailableError("CNA native C ABI is not available yet")
