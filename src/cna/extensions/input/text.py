"""Text input and IME composition.

XNA 4.0 has no text-input API at all: a game reads keys, not characters, and
there is nowhere in ``Microsoft.Xna.Framework`` for a composition update or a
candidate list to go. This is the whole of CNA's, projected as it is.

UTF-16, not characters
----------------------

CNA delivers committed text **one UTF-16 code unit at a time**, exactly as the
platform event does, and a code point above U+FFFF arrives as two calls: a high
surrogate then a low surrogate. This module does not hide that and does not
guess: :func:`on_text_input` hands over each code unit as CNA gives it, and
:class:`TextInputAccumulator` is the explicit, testable place where a surrogate
pair becomes one character. A composition update's ``start`` and ``length`` are
UTF-16 offsets into its own text for the same reason -- that is what an editor
must apply them to.

Subscriptions are **process-global**: CNA's subscribe routes take no game
handle, so a registration outlives any one game and is released by closing it.
"""

from __future__ import annotations

import ctypes as c
from typing import Callable, TYPE_CHECKING

from Microsoft.Xna.Framework import Rectangle

from _cna_native import input_abi as _input
from _cna_native import input_support as _in
from _cna_native.family_support import CallbackRoot, checked, string_view

from .values import TextEditing, TextEditingCandidates, TextInputType

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "TextInputSubscription",
    "TextInputAccumulator",
    "start_text_input",
    "stop_text_input",
    "is_text_input_active",
    "is_screen_keyboard_shown",
    "set_input_rectangle",
    "on_text_input",
    "on_text_editing",
    "on_text_editing_candidates",
]

_support = _in.support
_VERSION = 1

#: Every live text-input registration, rooted for as long as CNA can call it.
#:
#: CNA's subscribe routes take no game handle, so a registration is process
#: global rather than owned by a game. Keeping the trampolines here rather than
#: on a game object is what makes that visible instead of surprising.
_roots = CallbackRoot()


class TextInputSubscription:
    """One live text-input registration. Closing it stops the callbacks."""

    __slots__ = ("_handle", "_key", "_closed")

    def __init__(self, handle: int, key: object) -> None:
        self._handle = int(handle)
        self._key = key
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _roots.release(self._key)
        _support.call("cna_text_input_unsubscribe_ext", c.c_uint64(self._handle))

    def __enter__(self) -> "TextInputSubscription":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


def callback_failures() -> list:
    """``(handler, exception)`` for every text-input handler that raised.

    A Python exception must never unwind through C, so one raised inside a
    handler is caught at the boundary and recorded here.
    """
    return list(_roots.failures)


def start_text_input(game: "Game", kind: TextInputType | None = None) -> None:
    """Starts text input, optionally telling the platform what kind of text."""
    handle = _in.game_handle(game, "text input")
    if kind is None:
        _support.call("cna_text_input_start_ext", handle)
        return
    _support.call("cna_text_input_start_with_type_ext", handle,
                  c.c_uint32(TextInputType(kind)))


def stop_text_input(game: "Game") -> None:
    """Stops text input."""
    _support.call("cna_text_input_stop_ext", _in.game_handle(game, "text input"))


def is_text_input_active(game: "Game") -> bool:
    """Whether text input is currently started."""
    return _support.out_bool("cna_text_input_is_active_ext",
                             _in.game_handle(game, "text input"))


def is_screen_keyboard_shown(game: "Game", window: int | None = None) -> bool:
    """Whether an on-screen keyboard is visible.

    ``window`` names a specific platform window; without it the question is
    about the game's own, which CNA tracks separately.
    """
    handle = _in.game_handle(game, "text input")
    if window is None:
        return _support.out_bool("cna_text_input_is_screen_keyboard_shown_ext", handle)
    return _support.out_bool("cna_text_input_is_screen_keyboard_shown_for_window_ext",
                             handle, c.c_uint64(checked(window, "uint64", "window")))


def set_input_rectangle(game: "Game", rectangle: Rectangle) -> None:
    """Tells the platform where the text being composed will appear.

    An IME puts its candidate window next to this, so it is not decoration.
    """
    if not isinstance(rectangle, Rectangle):
        raise TypeError(
            f"rectangle must be a Rectangle, not {type(rectangle).__name__}")
    from _cna_native import abi

    value = abi.CNA_Rectangle()
    value.x, value.y = int(rectangle.X), int(rectangle.Y)
    value.width, value.height = int(rectangle.Width), int(rectangle.Height)
    _support.call("cna_text_input_set_input_rectangle_ext",
                  _in.game_handle(game, "text input"), value)


def window_handle(game: "Game") -> int:
    """The platform window CNA delivers text input for."""
    return _support.out_u64("cna_text_input_get_window_handle_ext",
                            _in.game_handle(game, "text input"))


def _subscribe(route: str, factory: type, adapt) -> TextInputSubscription:
    key = object()
    trampoline = _roots.root(key, factory, adapt)
    try:
        registration = _support.out_handle(route, trampoline, None)
    except BaseException:
        _roots.release(key)
        raise
    return TextInputSubscription(registration, key)


def on_text_input(handler: Callable[[int], None]) -> TextInputSubscription:
    """Calls ``handler(code_unit)`` for each committed **UTF-16 code unit**.

    A character above U+FFFF arrives as two calls. Use
    :class:`TextInputAccumulator` when you want characters rather than code
    units; nothing here silently pairs them for you.
    """

    def adapt(code_unit, _context) -> None:
        handler(int(code_unit))

    return _subscribe("cna_text_input_subscribe_text_input_ext",
                      _input.CNA_TextInputCallback, adapt)


def on_text_editing(handler: Callable[[TextEditing], None]) -> TextInputSubscription:
    """Calls ``handler(update)`` for each IME composition update."""

    def adapt(pointer, _context) -> None:
        info = pointer.contents
        handler(TextEditing(_text_of(info.text), int(info.start), int(info.length)))

    return _subscribe("cna_text_input_subscribe_text_editing_ext",
                      _input.CNA_TextEditingCallback, adapt)


def on_text_editing_candidates(
        handler: Callable[[TextEditingCandidates], None]) -> TextInputSubscription:
    """Calls ``handler(candidates)`` whenever the IME's candidate list changes."""

    def adapt(pointer, _context) -> None:
        info = pointer.contents
        count = int(info.candidate_count)
        # The array is `count` views long and is valid only for this call, so
        # every string is copied out before the handler can keep one.
        views = c.cast(info.candidates,
                       c.POINTER(_input.abi.CNA_StringView * count)).contents \
            if count else ()
        candidates = tuple(_text_of(views[index]) for index in range(count))
        selected = int(info.selected)
        handler(TextEditingCandidates(
            candidates, None if selected < 0 else selected,
            bool(info.horizontal)))

    return _subscribe("cna_text_input_subscribe_text_editing_candidates_ext",
                      _input.CNA_TextEditingCandidatesCallback, adapt)


def _text_of(view) -> str:
    """One borrowed ``CNA_StringView`` copied out as a Python string."""
    length = int(view.byte_length)
    if not length or not view.data:
        return ""
    raw = c.string_at(view.data, length)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("text input is not well-formed UTF-8") from error


class TextInputAccumulator:
    """Turns the stream of UTF-16 code units into characters, explicitly.

    A high surrogate is held until its low surrogate arrives, and the pair
    becomes one character. An unpaired surrogate is **not** guessed at: it is
    reported through :attr:`unpaired` and dropped from the text, because
    inventing a replacement character would be a different string from what was
    typed.

    This is a separate object rather than something :func:`on_text_input` does
    for you, so the raw code units stay available and the pairing is one
    testable thing rather than a hidden step.
    """

    __slots__ = ("_parts", "_pending", "unpaired")

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._pending: int | None = None
        #: Every code unit that was a surrogate with no partner, in order.
        self.unpaired: list[int] = []

    def __call__(self, code_unit: int) -> None:
        unit = checked(code_unit, "uint16", "code_unit")
        if 0xD800 <= unit <= 0xDBFF:
            if self._pending is not None:
                self.unpaired.append(self._pending)
            self._pending = unit
            return
        if 0xDC00 <= unit <= 0xDFFF:
            if self._pending is None:
                self.unpaired.append(unit)
                return
            high, self._pending = self._pending, None
            self._parts.append(chr(0x10000 + ((high - 0xD800) << 10) + (unit - 0xDC00)))
            return
        if self._pending is not None:
            self.unpaired.append(self._pending)
            self._pending = None
        self._parts.append(chr(unit))

    @property
    def text(self) -> str:
        """Everything committed so far, with surrogate pairs joined."""
        return "".join(self._parts)

    @property
    def pending_high_surrogate(self) -> int | None:
        """The high surrogate waiting for its partner, if one is."""
        return self._pending

    def clear(self) -> None:
        self._parts.clear()
        self._pending = None
        self.unpaired.clear()
