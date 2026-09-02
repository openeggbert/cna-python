"""The Guide's pending request, and drawing it yourself.

XNA's Guide draws itself: a title calls ``BeginShowMessageBox`` and the platform
puts an overlay on screen. On a host with no platform overlay there is nothing to
put there, and CNA answers by *holding the request* instead -- the title, the
text, the buttons -- so a title can draw it with its own SpriteBatch and font.

That is a real capability rather than a stub, and it is CNA's rather than XNA's,
which is why it lives here. Everything below reads or drives a request the
strict :class:`~Microsoft.Xna.Framework.GamerServices.Guide` made.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Microsoft.Xna.Framework import PlayerIndex

from _cna_native import online_support as _on
from _cna_native.family_support import checked

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework.Graphics import GraphicsDevice, SpriteBatch, SpriteFont, Texture2D

__all__ = [
    "PendingMessageBox", "PendingKeyboardInput", "pending_message_box",
    "pending_keyboard_input", "render_pending_message_box",
    "render_pending_keyboard_input", "reset_pending_message_box",
    "reset_pending_keyboard_input", "click_pending_message_box",
    "cancel_pending_keyboard_input", "set_guide_visible", "set_trial_mode",
    "show_achievements",
]

_support = _on.support


@dataclass(frozen=True, slots=True)
class PendingMessageBox:
    """A message box the Guide was asked to show and has not answered."""

    focus_button: int


@dataclass(frozen=True, slots=True)
class PendingKeyboardInput:
    """A keyboard-input request the Guide was asked to show and has not answered."""

    title: str
    description: str
    display_text: str


def pending_message_box() -> PendingMessageBox | None:
    """The message box waiting to be answered, or ``None``."""
    if not _support.out_bool("cna_guide_get_has_pending_message_box_ext"):
        return None
    return PendingMessageBox(_support.out_i32(
        "cna_guide_get_pending_message_box_focus_button_ext"))


def pending_keyboard_input() -> PendingKeyboardInput | None:
    """The keyboard-input request waiting to be answered, or ``None``."""
    if not _support.out_bool("cna_guide_get_has_pending_keyboard_input_ext"):
        return None
    return PendingKeyboardInput(
        _support.sized_text("cna_guide_get_pending_keyboard_input_title_size_ext",
                            "cna_guide_copy_pending_keyboard_input_title_ext", (),
                            "keyboard input title"),
        _support.sized_text(
            "cna_guide_get_pending_keyboard_input_description_size_ext",
            "cna_guide_copy_pending_keyboard_input_description_ext", (),
            "keyboard input description"),
        _support.sized_text(
            "cna_guide_get_pending_keyboard_input_display_text_size_ext",
            "cna_guide_copy_pending_keyboard_input_display_text_ext", (),
            "keyboard input display text"))


def _drawing(device: "GraphicsDevice", sprite_batch: "SpriteBatch",
             font: "SpriteFont", white_pixel: "Texture2D"):
    for name, value in (("device", device), ("sprite_batch", sprite_batch),
                        ("font", font), ("white_pixel", white_pixel)):
        if not hasattr(value, "_require_handle"):
            raise TypeError(f"{name} must be a strict XNA graphics object")
    return (c.c_uint64(device._require_handle()),
            c.c_uint64(sprite_batch._require_handle()),
            c.c_uint64(font._require_handle()),
            c.c_uint64(white_pixel._require_handle()))


def render_pending_message_box(device: "GraphicsDevice", sprite_batch: "SpriteBatch",
                               font: "SpriteFont", white_pixel: "Texture2D") -> None:
    """Draws the pending message box with the caller's own font and batch."""
    _support.call("cna_guide_render_pending_message_box_ext",
                  *_drawing(device, sprite_batch, font, white_pixel))


def render_pending_keyboard_input(device: "GraphicsDevice",
                                  sprite_batch: "SpriteBatch", font: "SpriteFont",
                                  white_pixel: "Texture2D") -> None:
    """Draws the pending keyboard-input request the same way."""
    _support.call("cna_guide_render_pending_keyboard_input_ext",
                  *_drawing(device, sprite_batch, font, white_pixel))


def reset_pending_message_box() -> None:
    """Discards the pending message box without answering it."""
    _support.call("cna_guide_reset_pending_message_box_ext")


def reset_pending_keyboard_input() -> None:
    """Discards the pending keyboard-input request without answering it."""
    _support.call("cna_guide_reset_pending_keyboard_input_ext")


def click_pending_message_box(button_index: int) -> None:
    """Answers the pending message box as if that button had been pressed."""
    _support.call("cna_guide_simulate_message_box_click_ext",
                  c.c_int32(checked(button_index, "int32", "button_index")))


def cancel_pending_keyboard_input() -> None:
    """Answers the pending keyboard-input request as a cancellation."""
    _support.call("cna_guide_simulate_keyboard_input_cancel_ext")


def set_guide_visible(visible: bool) -> None:
    """Forces the Guide's visibility.

    XNA's ``Guide.IsVisible`` is read-only, because the platform decides. CNA
    has the setter a platform layer would use, and it is here rather than there.
    """
    _support.call("cna_guide_set_is_visible", c.c_uint8(1 if visible else 0))


def set_trial_mode(is_trial_mode: bool) -> None:
    """Forces the platform's trial-mode answer.

    Distinct from XNA's ``Guide.SimulateTrialMode``, which is a title's own
    override: this is what the *platform* says, and only a platform layer sets it.
    """
    _support.call("cna_guide_set_is_trial_mode",
                  c.c_uint8(1 if is_trial_mode else 0))


def show_achievements(player: PlayerIndex) -> None:
    """Shows the achievements pane.

    XNA 4.0 has no ``Guide.ShowAchievements``; CNA does, so it is here.
    """
    _support.call("cna_guide_show_achievements_ext",
                  c.c_uint32(int(PlayerIndex(player))))
