"""CNA's deterministic input backends, for qualification rather than for games.

Every function here raises an event CNA would otherwise get from the platform,
or resets the state a previous test left behind. They exist so text input, IME
composition, candidate lists and hotplug can be measured on a machine with no
IME, no second keyboard and no joystick.

Read the boundary literally: a result obtained through this module is
``SYNTHETIC_BACKEND_VERIFIED``. It is evidence about the event plumbing, the
UTF-16 handling and this binding. It is **never** evidence that a physical
device was read.

A shipping game should not import this module. Nothing else in
``cna.extensions.input`` does.
"""

from __future__ import annotations

import ctypes as c
from typing import Sequence, TYPE_CHECKING

from _cna_native import input_support as _in
from _cna_native.family_support import checked, string_view

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "raise_text_input",
    "raise_text_input_string",
    "raise_text_editing",
    "raise_text_editing_candidates",
    "reset_text_input",
    "set_text_input_window",
    "raise_joystick_connected",
    "raise_joystick_disconnected",
    "reset_joysticks",
    "raise_keyboard_connected",
    "raise_keyboard_disconnected",
    "raise_mouse_connected",
    "raise_mouse_disconnected",
    "reset_input_devices",
]

_support = _in.support


def raise_text_input(game: "Game", code_unit: int) -> None:
    """Delivers one committed **UTF-16 code unit**.

    A character above U+FFFF needs two calls, a high surrogate then a low one --
    which is exactly what the platform does, and exactly what
    :func:`raise_text_input_string` does for you.
    """
    _support.call("cna_text_input_raise_text_input_ext",
                  _in.game_handle(game, "text input"),
                  c.c_uint16(checked(code_unit, "uint16", "code_unit")))


def raise_text_input_string(game: "Game", text: str) -> None:
    """Delivers ``text`` one UTF-16 code unit at a time, as the platform would.

    Encoding to UTF-16 here is what splits a non-BMP character into its
    surrogate pair, and doing it in one obvious place is why the pairing can be
    tested rather than assumed.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, not {type(text).__name__}")
    encoded = text.encode("utf-16-le")
    for index in range(0, len(encoded), 2):
        raise_text_input(game, int.from_bytes(encoded[index:index + 2], "little"))


def raise_text_editing(game: "Game", text: str, start: int, length: int) -> None:
    """Delivers one IME composition update.

    ``start`` and ``length`` index UTF-16 code units in ``text``, which is what
    the platform reports and what CNA passes through.
    """
    view, _keep = string_view(text, "text")
    _support.call("cna_text_input_raise_text_editing_ext",
                  _in.game_handle(game, "text input"), view,
                  c.c_int32(checked(start, "int32", "start")),
                  c.c_int32(checked(length, "int32", "length")))


def raise_text_editing_candidates(game: "Game", candidates: Sequence[str],
                                  selected: int = -1,
                                  horizontal: bool = True) -> None:
    """Delivers one IME candidate list.

    ``selected`` is an index into ``candidates``, or ``-1`` for none -- CNA's own
    sentinel, which the public event turns into ``None``.
    """
    from _cna_native import abi

    candidates = tuple(candidates)
    keep: list[bytes] = []
    array = (abi.CNA_StringView * len(candidates))() if candidates else None
    for index, value in enumerate(candidates):
        view, encoded = string_view(value, f"candidates[{index}]")
        array[index] = view
        keep.append(encoded)
    _support.call("cna_text_input_raise_text_editing_candidates_ext",
                  _in.game_handle(game, "text input"), array,
                  c.c_int32(len(candidates)),
                  c.c_int32(checked(selected, "int32", "selected")),
                  c.c_uint8(1 if horizontal else 0))


def reset_text_input(game: "Game") -> None:
    """Clears every text-input registration and state CNA is holding."""
    _support.call("cna_text_input_reset_for_tests_ext",
                  _in.game_handle(game, "text input"))


def set_text_input_window(game: "Game", window: int) -> None:
    """Points text input at a specific platform window."""
    _support.call("cna_text_input_set_window_handle_ext",
                  _in.game_handle(game, "text input"),
                  c.c_uint64(checked(window, "uint64", "window")))


def raise_joystick_connected(game: "Game", joystick_id: int) -> None:
    """Delivers a joystick connect event."""
    _support.call("cna_joysticks_raise_connected_ext",
                  _in.game_handle(game, "joysticks"),
                  c.c_uint32(checked(joystick_id, "uint32", "joystick_id")))


def raise_joystick_disconnected(game: "Game", joystick_id: int) -> None:
    """Delivers a joystick disconnect event."""
    _support.call("cna_joysticks_raise_disconnected_ext",
                  _in.game_handle(game, "joysticks"),
                  c.c_uint32(checked(joystick_id, "uint32", "joystick_id")))


def reset_joysticks(game: "Game") -> None:
    """Clears every joystick registration CNA is holding."""
    _support.call("cna_joysticks_reset_for_tests_ext",
                  _in.game_handle(game, "joysticks"))


def raise_keyboard_connected(game: "Game", device_id: int) -> None:
    """Delivers a keyboard connect event."""
    _support.call("cna_input_devices_raise_keyboard_connected_ext",
                  _in.game_handle(game, "input devices"),
                  c.c_uint32(checked(device_id, "uint32", "device_id")))


def raise_keyboard_disconnected(game: "Game", device_id: int) -> None:
    """Delivers a keyboard disconnect event."""
    _support.call("cna_input_devices_raise_keyboard_disconnected_ext",
                  _in.game_handle(game, "input devices"),
                  c.c_uint32(checked(device_id, "uint32", "device_id")))


def raise_mouse_connected(game: "Game", device_id: int) -> None:
    """Delivers a mouse connect event."""
    _support.call("cna_input_devices_raise_mouse_connected_ext",
                  _in.game_handle(game, "input devices"),
                  c.c_uint32(checked(device_id, "uint32", "device_id")))


def raise_mouse_disconnected(game: "Game", device_id: int) -> None:
    """Delivers a mouse disconnect event."""
    _support.call("cna_input_devices_raise_mouse_disconnected_ext",
                  _in.game_handle(game, "input devices"),
                  c.c_uint32(checked(device_id, "uint32", "device_id")))


def reset_input_devices(game: "Game") -> None:
    """Clears every input-device registration CNA is holding."""
    _support.call("cna_input_devices_reset_for_tests_ext",
                  _in.game_handle(game, "input devices"))
