"""Mouse cursors.

XNA 4.0 exposes exactly one thing about the cursor -- ``Game.IsMouseVisible`` --
so a stock cursor, a cursor built from a texture, and setting the active one all
belong here rather than there.

Ownership is the part worth reading twice. A cursor is an owned object with an
explicit ``close``. The cursor that is currently *active* is **borrowed** by the
platform: closing it while it is still set would leave the platform pointing at
freed memory, so :func:`set_cursor` records which cursor is active and
:meth:`MouseCursor.close` refuses to close that one until another is set.
"""

from __future__ import annotations

import ctypes as c
from typing import TYPE_CHECKING

from _cna_native import input_support as _in

from .values import MouseCursorStock

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game
    from Microsoft.Xna.Framework.Graphics import Texture2D

__all__ = ["MouseCursor", "set_cursor", "active_cursor"]

_support = _in.support

#: The cursor the platform is currently pointing at, or ``None``.
_active: "MouseCursor | None" = None


class MouseCursor:
    """One cursor.

    Build one with :meth:`stock` or :meth:`from_texture`; the constructor makes
    CNA's default cursor, which is what ``cna_mouse_cursor_create_ext`` returns.
    """

    __slots__ = ("_handle",)

    def __init__(self) -> None:
        handle = _support.out_handle("cna_mouse_cursor_create_ext")
        self._handle = _support.handle(handle, "cna_mouse_cursor_destroy", "cursor")

    @classmethod
    def _adopt(cls, handle: int) -> "MouseCursor":
        cursor = cls.__new__(cls)
        cursor._handle = _support.handle(handle, "cna_mouse_cursor_destroy", "cursor")
        return cursor

    @classmethod
    def stock(cls, game: "Game", which: MouseCursorStock) -> "MouseCursor":
        """One of the platform's own cursors."""
        return cls._adopt(_support.out_handle(
            "cna_mouse_cursor_get_stock_ext", _in.game_handle(game, "cursor"),
            c.c_uint32(MouseCursorStock(which))))

    @classmethod
    def from_texture(cls, game: "Game", texture: "Texture2D",
                     origin_x: int, origin_y: int) -> "MouseCursor":
        """A cursor drawn from a ``Texture2D``, with its hot spot at the origin.

        The texture is read during the call and is not retained, so the caller
        keeps owning it and may dispose it immediately afterwards.
        """
        if not hasattr(texture, "_require_handle"):
            raise TypeError(
                "texture must be a Microsoft.Xna.Framework.Graphics.Texture2D, "
                f"not {type(texture).__name__}")
        from _cna_native.family_support import checked

        return cls._adopt(_support.out_handle(
            "cna_mouse_cursor_create_from_texture2d",
            _in.game_handle(game, "cursor"), c.c_uint64(texture._require_handle()),
            c.c_int32(checked(origin_x, "int32", "origin_x")),
            c.c_int32(checked(origin_y, "int32", "origin_y"))))

    def dispose(self) -> None:
        """Disposes the canonical cursor object, as its ``Dispose`` does.

        Not :meth:`close`: the C handle is still live and still has to be closed.
        """
        _support.call("cna_mouse_cursor_dispose", self._handle.argument)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self, *, force: bool = False) -> None:
        """Destroys the cursor.

        Refuses while this cursor is the active one. CNA says so in as many
        words -- "the C API does not keep the cursor alive on the caller's
        behalf: releasing it while it is the active cursor is the caller's
        responsibility to avoid" -- and a use-after-free there is not something
        a Python-level error could describe afterwards.

        ``force=True`` is the way out for the *last* cursor, at shutdown, when
        the platform will not draw it again. It is deliberately explicit: there
        is no way to un-set an active cursor, so somebody eventually has to say
        that this one is finished with.
        """
        if self._handle.closed:
            return
        if _active is self and not force:
            from .errors import InputStateError

            raise InputStateError(
                "cna_mouse_cursor_destroy", 3, None,
                "this cursor is the active one; the platform borrows it, so set "
                "another cursor before closing this one")
        self._handle.close()

    def __enter__(self) -> "MouseCursor":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close(force=True)


def set_cursor(game: "Game", cursor: MouseCursor) -> None:
    """Makes ``cursor`` the active one.

    The platform borrows it from here on; it must outlive the next
    :func:`set_cursor`, and this module enforces that by refusing to close it in
    the meantime.
    """
    global _active
    if not isinstance(cursor, MouseCursor):
        raise TypeError(f"cursor must be a MouseCursor, not {type(cursor).__name__}")
    _support.call("cna_mouse_set_cursor_ext", _in.game_handle(game, "cursor"),
                  cursor._handle.argument)
    _active = cursor


def active_cursor() -> MouseCursor | None:
    """The cursor :func:`set_cursor` last made active, if any."""
    return _active
