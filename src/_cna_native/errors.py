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
        super().__init__(
            f"CNA C ABI mismatch for {path}: expected 0x{expected:08x} (0.7.0), "
            f"got 0x{actual:08x} ({actual >> 16}.{(actual >> 8) & 0xff}.{actual & 0xff})"
        )


class NativeCapabilityError(NativeError):
    """An XNA overload is structurally present but ABI 0.7 cannot execute it."""
