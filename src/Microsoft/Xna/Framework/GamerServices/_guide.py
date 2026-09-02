"""The Guide, and the gamer-services dispatcher behind it.

Part of the ``xna40-windows-online`` strict profile. Every ``ShowX`` entry point
asks the platform to put its own UI on screen; on a host with no gamer-services
platform CNA answers accordingly and this package passes that through rather
than pretending the Guide appeared.

Trial mode is separated from *simulated* trial mode exactly as XNA separates
them: ``IsTrialMode`` is what the platform says, ``SimulateTrialMode`` is a
title's own override, and reading one never silently answers the other.

The two asynchronous entry points -- the message box and the keyboard input --
complete when the platform answers. CNA exposes the pending request so a title
can draw it itself, and the qualification drives that path rather than waiting
for a platform that is not here.
"""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from typing import Iterable

from .. import PlayerIndex
from .._language import (
    Event, classproperty, staticproperty, staticpropertymeta,
)
from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import checked, string_view

from ._enums import MessageBoxIcon
from ._enums import NotificationPosition as _NotificationPosition
from ._gamer import Gamer, _GamerAsyncResult

__all__ = ["Guide", "GamerServicesDispatcher", "InviteAcceptedEventArgs"]

_support = _on.support

#: 100-nanosecond ticks in one microsecond.
_TICKS_PER_MICROSECOND = 10


def _ticks(value: timedelta, what: str) -> int:
    if not isinstance(value, timedelta):
        raise TypeError(f"{what} must be a timedelta, not {type(value).__name__}")
    microseconds = (value.days * 86_400_000_000 + value.seconds * 1_000_000
                    + value.microseconds)
    return microseconds * _TICKS_PER_MICROSECOND


def _player(value: object, what: str = "player") -> c.c_uint32:
    return c.c_uint32(int(PlayerIndex(value)))


def _gamer_array(gamers: Iterable[Gamer], what: str):
    values = []
    for index, gamer in enumerate(gamers or ()):
        if not isinstance(gamer, Gamer):
            raise TypeError(f"{what}[{index}] must be a Gamer")
        values.append(gamer._value.value)
    if not values:
        return None, 0
    return (c.c_uint64 * len(values))(*values), len(values)


class Guide(metaclass=staticpropertymeta):
    """XNA's Guide: the platform's own overlay."""

    IsScreenSaverEnabled = staticproperty(
        lambda owner: _support.out_bool("cna_guide_get_is_screen_saver_enabled"),
        lambda owner, value: _support.call("cna_guide_set_is_screen_saver_enabled",
                                           c.c_uint8(1 if value else 0)))

    IsVisible = classproperty(
        lambda owner: _support.out_bool("cna_guide_get_is_visible"))

    NotificationPosition = staticproperty(
        lambda owner: _NotificationPosition(
            _support.out_u32("cna_guide_get_notification_position")),
        lambda owner, value: _support.call(
            "cna_guide_set_notification_position",
            c.c_uint32(int(_NotificationPosition(value)))))

    IsTrialMode = classproperty(
        lambda owner: _support.out_bool("cna_guide_get_is_trial_mode"))

    SimulateTrialMode = staticproperty(
        lambda owner: _support.out_bool("cna_guide_get_simulate_trial_mode"),
        lambda owner, value: _support.call("cna_guide_set_simulate_trial_mode",
                                           c.c_uint8(1 if value else 0)))

    @staticmethod
    def BeginShowMessageBox(*args: object) -> object:
        """XNA's two overloads: with a player, and without.

        The one without a player is the single-player form; CNA takes a player
        either way, and ``PlayerIndex.One`` is what the canonical overload
        without one uses.
        """
        if args and isinstance(args[0], PlayerIndex):
            player, rest = args[0], args[1:]
        elif len(args) == 8:
            player, rest = PlayerIndex(args[0]), args[1:]
        else:
            player, rest = PlayerIndex.One, args
        if len(rest) != 7:
            raise TypeError("no matching BeginShowMessageBox overload")
        title, text, buttons, focusButton, icon, callback, state = rest
        return Guide._begin_message_box(player, title, text, buttons, focusButton,
                                        icon, callback, state)

    @staticmethod
    def _begin_message_box(player, title, text, buttons, focusButton, icon,
                           callback, state) -> object:
        title_view, keep_title = string_view(title, "title")
        text_view, keep_text = string_view(text, "text")
        labels = tuple(buttons or ())
        from _cna_native import abi

        array = (abi.CNA_StringView * len(labels))() if labels else None
        keep: list[bytes] = [keep_title, keep_text]
        for index, label in enumerate(labels):
            view, encoded = string_view(label, f"buttons[{index}]")
            array[index] = view
            keep.append(encoded)

        def produce():
            _support.call(
                "cna_guide_begin_show_message_box", _player(player), title_view,
                text_view, array, c.c_uint64(len(labels)),
                c.c_int32(checked(focusButton, "int32", "focusButton")),
                c.c_uint32(int(MessageBoxIcon(icon))),
                _on.no_callback(_online.CNA_GamerAsyncCallback), None)
            return None

        return _GamerAsyncResult.begin("ShowMessageBox", state, callback, produce,
                                       keep_alive=keep)

    @staticmethod
    def EndShowMessageBox(result: object):
        """The chosen button index, or ``None`` when the box was dismissed."""
        _GamerAsyncResult.end(result, "ShowMessageBox")
        has_choice = c.c_uint8()
        index = c.c_int32()
        _support.call("cna_guide_end_show_message_box", c.byref(has_choice),
                      c.byref(index))
        return int(index.value) if has_choice.value else None

    @staticmethod
    def BeginShowKeyboardInput(*args: object) -> object:
        """XNA's two overloads, the second adding ``usePasswordMode``."""
        if len(args) == 6:
            player, title, description, defaultText, callback, state = args
            password = False
        elif len(args) == 7:
            player, title, description, defaultText, callback, state, password = args
        else:
            raise TypeError("no matching BeginShowKeyboardInput overload")
        title_view, keep_title = string_view(title, "title")
        description_view, keep_description = string_view(description, "description")
        default_view, keep_default = string_view(defaultText, "defaultText")

        def produce():
            _support.call(
                "cna_guide_begin_show_keyboard_input", _player(player), title_view,
                description_view, default_view, c.c_uint8(1 if password else 0),
                _on.no_callback(_online.CNA_GamerAsyncCallback), None)
            return None

        return _GamerAsyncResult.begin(
            "ShowKeyboardInput", state, callback, produce,
            keep_alive=(keep_title, keep_description, keep_default))

    @staticmethod
    def EndShowKeyboardInput(result: object) -> str | None:
        """The text that was entered, or ``None`` when the input was cancelled."""
        _GamerAsyncResult.end(result, "ShowKeyboardInput")
        if _support.out_bool("cna_guide_was_keyboard_input_canceled_ext"):
            return None
        size = c.c_uint64()
        _support.call("cna_guide_end_show_keyboard_input_size", c.byref(size))
        if not size.value:
            return ""
        buffer = c.create_string_buffer(size.value)
        written = c.c_uint64()
        _support.call("cna_guide_end_show_keyboard_input", buffer,
                      c.c_uint64(size.value), c.byref(written))
        return bytes(buffer.raw[: written.value]).decode("utf-8")

    @staticmethod
    def ShowSignIn(paneCount: int, onlineOnly: bool) -> None:
        _support.call("cna_guide_show_sign_in",
                      c.c_int32(checked(paneCount, "int32", "paneCount")),
                      c.c_uint8(1 if onlineOnly else 0))

    @staticmethod
    def ShowMessages(player: PlayerIndex) -> None:
        _support.call("cna_guide_show_messages", _player(player))

    @staticmethod
    def ShowFriends(player: PlayerIndex) -> None:
        _support.call("cna_guide_show_friends", _player(player))

    @staticmethod
    def ShowPlayers(player: PlayerIndex) -> None:
        _support.call("cna_guide_show_players", _player(player))

    @staticmethod
    def ShowParty(player: PlayerIndex) -> None:
        _support.call("cna_guide_show_party", _player(player))

    @staticmethod
    def ShowPartySessions(player: PlayerIndex) -> None:
        _support.call("cna_guide_show_party_sessions", _player(player))

    @staticmethod
    def ShowMarketplace(player: PlayerIndex) -> None:
        _support.call("cna_guide_show_marketplace", _player(player))

    @staticmethod
    def ShowFriendRequest(player: PlayerIndex, gamer: Gamer) -> None:
        _support.call("cna_guide_show_friend_request", _player(player),
                      _one_gamer(gamer))

    @staticmethod
    def ShowPlayerReview(player: PlayerIndex, gamer: Gamer) -> None:
        _support.call("cna_guide_show_player_review", _player(player),
                      _one_gamer(gamer))

    @staticmethod
    def ShowGamerCard(player: PlayerIndex, gamer: Gamer) -> None:
        _support.call("cna_guide_show_gamer_card", _player(player),
                      _one_gamer(gamer))

    @staticmethod
    def ShowComposeMessage(player: PlayerIndex, text: str,
                           recipients: Iterable[Gamer]) -> None:
        view, _keep = string_view(text, "text")
        array, count = _gamer_array(recipients, "recipients")
        _support.call("cna_guide_show_compose_message", _player(player), view,
                      array, c.c_uint64(count))

    @staticmethod
    def ShowGameInvite(*args: object) -> None:
        """XNA's two overloads: to a list of gamers, or to a session id."""
        if len(args) == 1 and isinstance(args[0], str):
            view, _keep = string_view(args[0], "sessionId")
            _support.call("cna_guide_show_game_invite_for_session", view)
            return
        if len(args) == 2:
            player, recipients = args
            array, count = _gamer_array(recipients, "recipients")
            _support.call("cna_guide_show_game_invite", _player(player), array,
                          c.c_uint64(count))
            return
        raise TypeError("no matching ShowGameInvite overload")

    @staticmethod
    def DelayNotifications(delay: timedelta) -> None:
        _support.call("cna_guide_delay_notifications",
                      c.c_int64(_ticks(delay, "delay")))


def _one_gamer(gamer: Gamer) -> c.c_uint64:
    if not isinstance(gamer, Gamer):
        raise TypeError("gamer must be a Gamer")
    return gamer._value


Guide.__xna_arities__ = {
    "BeginShowMessageBox": {7, 8},
    "BeginShowKeyboardInput": {6, 7},
    "ShowGameInvite": {1, 2},
}


class GamerServicesDispatcher(metaclass=staticpropertymeta):
    """The pump gamer services needs, and the window it belongs to."""

    #: XNA raises this when the platform is installing a title update.
    InstallingTitleUpdate = Event(static=True)

    IsInitialized = classproperty(
        lambda owner: _support.out_bool(
            "cna_gamer_services_dispatcher_get_is_initialized"))

    WindowHandle = staticproperty(
        lambda owner: _support.out_u64(
            "cna_gamer_services_dispatcher_get_window_handle"),
        lambda owner, value: _support.call(
            "cna_gamer_services_dispatcher_set_window_handle",
            c.c_uint64(checked(value, "uint64", "WindowHandle"))))

    @staticmethod
    def Initialize(serviceProvider: object) -> None:
        """Initialises gamer services for the game behind ``serviceProvider``.

        XNA takes an ``IServiceProvider``; the only one this projection can act
        on is a ``Game``, which is what XNA passes in practice.
        """
        host = getattr(serviceProvider, "_host", None)
        handle = getattr(host, "handle", 0)
        if not handle:
            raise ValueError(
                "serviceProvider must be a running Microsoft.Xna.Framework.Game")
        _support.call("cna_gamer_services_dispatcher_initialize",
                      c.c_uint64(int(handle)))

    @staticmethod
    def Update() -> None:
        _support.call("cna_gamer_services_dispatcher_update")


class InviteAcceptedEventArgs:
    """The payload of ``NetworkSession.InviteAccepted``."""

    __slots__ = ("_gamer", "_is_current")

    def __init__(self, gamer: object, isCurrentSession: bool) -> None:
        self._gamer = gamer
        self._is_current = bool(isCurrentSession)

    @property
    def Gamer(self):
        return self._gamer

    @property
    def IsCurrentSession(self) -> bool:
        return self._is_current
