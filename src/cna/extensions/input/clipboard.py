"""The host clipboard.

CNA declares the read side in ``input_devices.h`` and the write side in both
that header and ``devices.h``. They are one clipboard, so this module is the
whole of it and ``cna.extensions.devices`` re-exports the read.

Text is UTF-8 on the wire and ``str`` here. The byte length and the character
length are different numbers and are never confused: the size half of the
two-call protocol counts **bytes**, and this module never uses it as a character
count.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from _cna_native import input_support as _in
from _cna_native.family_support import string_view

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = ["clipboard_has_text", "clipboard_text", "clipboard_text_byte_length",
           "set_clipboard_text"]

_support = _in.support


def clipboard_has_text(game: "Game") -> bool:
    """Whether the clipboard currently holds text."""
    return _support.out_bool("cna_clipboard_get_has_text",
                             _in.game_handle(game, "clipboard"))


def clipboard_text_byte_length(game: "Game") -> int:
    """The clipboard text's length in **UTF-8 bytes**, not in characters.

    Exposed because it is what the native protocol counts, and because a caller
    sizing a buffer needs the byte count while a caller counting characters
    needs ``len(clipboard_text(game))``. The two differ for anything outside
    ASCII, and conflating them is the defect this name exists to prevent.
    """
    return _support.out_u64("cna_clipboard_get_text_size",
                            _in.game_handle(game, "clipboard"))


def clipboard_text(game: "Game") -> str:
    """The clipboard's current text, decoded strictly as UTF-8."""
    return _support.copied_text("cna_clipboard_copy_text",
                                (_in.game_handle(game, "clipboard"),),
                                "clipboard text")


def set_clipboard_text(game: "Game", text: str) -> None:
    """Puts ``text`` on the clipboard.

    ``cna.extensions.devices.set_clipboard_text`` is the other route CNA
    declares for this, and it reports the host's refusal instead of raising.
    """
    view, _keep = string_view(text, "text")
    _support.call("cna_clipboard_set_text", _in.game_handle(game, "clipboard"), view)
