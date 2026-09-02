"""Exceptions ``cna.extensions.online`` raises.

The strict online profile raises XNA-shaped exceptions -- ``ValueError``,
``RuntimeError``, ``GamerServicesNotAvailableException``. This package's own
surface is CNA-only, so its failures get their own names.
"""

from __future__ import annotations

__all__ = ["OnlineExtensionError", "OnlineExtensionStateError"]


class OnlineExtensionError(Exception):
    """A CNA online-extension route failed."""

    def __init__(self, operation: str, result: int, category: object,
                 message: str | None) -> None:
        self.operation = operation
        self.result = int(result)
        self.category = category
        self.native_message = message
        detail = f": {message}" if message else ""
        super().__init__(f"{operation} failed with CNA result {result}{detail}")


class OnlineExtensionStateError(OnlineExtensionError, RuntimeError):
    """The call is wrong for the state the object is in."""
