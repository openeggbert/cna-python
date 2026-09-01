"""Exceptions copied from CNA's thread-local error state."""

from __future__ import annotations


class NativeError(RuntimeError):
    def __init__(self, operation: str, result: int, category: int | None, message: str, context: str | None = None) -> None:
        self.operation = operation
        self.result = result
        self.category = category
        self.native_message = message
        self.context = context
        detail = f"{operation} failed with CNA result {result}"
        if category is not None:
            detail += f" (category {category})"
        if message:
            detail += f": {message}"
        if context:
            detail += f" [{context}]"
        super().__init__(detail)


class NativeLibraryError(RuntimeError):
    """The native library could not be resolved, loaded, or audited."""


class NativeUnavailableError(NativeLibraryError):
    """No usable CNA C ABI library is configured."""


class NativeAbiMismatchError(NativeLibraryError):
    def __init__(self, expected: int, actual: int, path: str) -> None:
        self.expected = expected
        self.actual = actual
        self.path = path
        def _text(version: int) -> str:
            return f"{version >> 16}.{(version >> 8) & 0xff}.{version & 0xff}"

        super().__init__(
            f"CNA C ABI mismatch for {path}: this build supports the "
            f"{expected >> 16}.{(expected >> 8) & 0xff}.x generation "
            f"(qualified at {_text(expected)}), got 0x{actual:08x} ({_text(actual)}). "
            "CNA 0.x is experimental and an incompatible change increments the minor, "
            "so a different minor is a different contract"
        )


class NativeCapabilityError(NativeError):
    """An XNA overload is structurally present but the qualified CNA runtime cannot execute it.

    The message must name the measured reason on the current runtime, never a
    historical ABI generation.
    """
