"""What the host machine can tell a game about itself.

Clipboard, display metrics, device class, preferred locales, power, system
information, and handing a URL to the host browser. None of these has an XNA
counterpart, and none of them is guessed: where CNA reports a sentinel, this
module turns it into ``None`` and says so, and where CNA reports a real answer
that looks like a failure -- ``PowerState.Error`` -- it stays a real answer.

Nothing here fabricates a value. A machine with no battery reports no battery.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Microsoft.Xna.Framework import Rectangle

from _cna_native import devices_support as _dev
from _cna_native.family_support import checked, string_view

from .values import DeviceType, PowerState

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "Locale",
    "PowerInformation",
    "SystemInformation",
    "device_services_available",
    "device_type",
    "content_scale",
    "safe_area",
    "preferred_locales",
    "power_information",
    "system_information",
    "clipboard_text",
    "set_clipboard_text",
    "open_url",
]

_support = _dev.support


@dataclass(frozen=True, slots=True)
class Locale:
    """One preferred locale: a language and, when the host gives one, a country.

    An empty country is what CNA reports for a language-only preference, and it
    stays an empty string rather than becoming ``None``: the distinction between
    "no country" and "the country is unknown" is not one CNA draws.
    """

    language: str
    country: str


@dataclass(frozen=True, slots=True)
class PowerInformation:
    """The host's power state, with the two unknown values as ``None``.

    CNA reports ``-1`` for an unknown battery percentage or an unknown remaining
    time. That sentinel is turned into ``None`` here exactly once, so no caller
    has to remember it and no arithmetic can accidentally treat it as a value.
    """

    state: PowerState
    battery_percent: int | None
    seconds_remaining: int | None


@dataclass(frozen=True, slots=True)
class SystemInformation:
    """What the host reports about its own hardware."""

    logical_cpu_cores: int
    system_ram_megabytes: int


def device_services_available() -> bool:
    """Whether this CNA build has the device-services layer at all.

    Needs no ``Game``, because it is a fact about the loaded library rather than
    about a running game. Everything else in this module needs one.
    """
    return _dev.device_services_available()


def device_type() -> DeviceType:
    """Whether the process is on real hardware or an emulator."""
    return DeviceType(_support.out_u32("cna_environment_get_device_type"))


def content_scale(game: "Game") -> float:
    """The display's content scale factor."""
    return _support.out_f32("cna_display_info_get_content_scale_ext",
                            _dev.game_handle(game, "content scale"))


def safe_area(game: "Game") -> Rectangle:
    """The part of the display that is not covered by system chrome."""
    from _cna_native import abi

    value = abi.CNA_Rectangle()
    _support.call("cna_display_info_get_safe_area_ext",
                  _dev.game_handle(game, "safe area"), c.byref(value))
    return Rectangle(int(value.x), int(value.y), int(value.width), int(value.height))


def preferred_locales(game: "Game") -> list[Locale]:
    """The host's preferred locales, most preferred first.

    The order is the host's and is preserved: a caller choosing a language reads
    the first entry it supports, and reordering would change which one that is.
    """
    handle = _dev.game_handle(game, "preferred locales")
    count = _support.out_u64("cna_locale_get_preferred_count_ext", handle)
    result: list[Locale] = []
    for index in range(count):
        position = c.c_uint64(index)
        result.append(Locale(
            _support.copied_text("cna_locale_copy_language_at_ext",
                                 (handle, position), "locale language"),
            _support.copied_text("cna_locale_copy_country_at_ext",
                                 (handle, position), "locale country")))
    return result


def power_information(game: "Game") -> PowerInformation:
    """The host's power state and battery, with unknown values as ``None``."""
    handle = _dev.game_handle(game, "power information")
    state = PowerState(_support.out_u32("cna_power_get_state_ext", handle))
    percent = _support.out_i32("cna_power_get_battery_percent_ext", handle)
    seconds = _support.out_i32("cna_power_get_seconds_remaining_ext", handle)
    return PowerInformation(state,
                            None if percent < 0 else int(percent),
                            None if seconds < 0 else int(seconds))


def system_information(game: "Game") -> SystemInformation:
    """The host's logical core count and installed memory."""
    handle = _dev.game_handle(game, "system information")
    return SystemInformation(
        _support.out_i32("cna_system_info_get_logical_cpu_core_count_ext", handle),
        _support.out_i32("cna_system_info_get_system_ram_megabytes_ext", handle))


def clipboard_text(game: "Game") -> str:
    """The clipboard's current text.

    ``devices.h`` writes the clipboard and ``input_devices.h`` reads it, so the
    read goes through the input family's route. The two are one clipboard, and
    this is here so a caller reading device services does not have to know which
    header CNA put which half in.
    """
    from cna.extensions.input.clipboard import clipboard_text as _read

    return _read(game)


def set_clipboard_text(game: "Game", text: str) -> bool:
    """Puts ``text`` on the clipboard; ``False`` when the host refused it.

    Refusal is a real answer -- a headless host may have no clipboard -- and is
    reported rather than raised.
    """
    view, _keep = string_view(text, "text")
    return _support.out_bool("cna_devices_clipboard_set_text_ext",
                             _dev.game_handle(game, "clipboard"), view)


def open_url(game: "Game", url: str) -> bool:
    """Asks the host to open ``url``; ``False`` when it would not.

    This hands a URL to the host's own browser. It opens nothing itself, reads
    nothing back, and is never called by anything else in this package.
    """
    view, _keep = string_view(url, "url")
    return _support.out_bool("cna_url_launcher_open_ext",
                             _dev.game_handle(game, "url launcher"), view)
