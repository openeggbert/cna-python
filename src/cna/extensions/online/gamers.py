"""Publishing gamers, and the collections CNA can build from them.

Every function here is CNA-only. None is called by
``Microsoft.Xna.Framework.GamerServices``, and a shipping game has no reason to
call most of them: publishing a signed-in gamer is what a *platform layer* does,
and a game that did it would be inventing a user.

What a qualification proves through :func:`publish_signed_in_gamers` is
``SYNTHETIC_SIGNED_IN_GAMER_VERIFIED``. It is evidence about the object graph,
the roster arithmetic and this binding. It is never evidence that anyone signed
in.
"""

from __future__ import annotations

import ctypes as c
from datetime import datetime, timezone
from typing import Callable, Sequence

from Microsoft.Xna.Framework import PlayerIndex
from Microsoft.Xna.Framework.GamerServices import (
    Achievement, AchievementCollection, FriendCollection, FriendGamer, Gamer,
    GamerCollectionOfT, GamerPresenceMode, SignedInGamer,
)

from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import CallbackRoot, checked, string_view

__all__ = [
    "create_signed_in_gamer", "publish_signed_in_gamers", "create_friend_gamer",
    "create_friend_collection", "create_achievement",
    "create_achievement_collection", "gamer_collection_add",
    "gamer_collection_remove", "gamer_collection_clear", "on_signed_in",
    "on_signed_out", "on_installing_title_update", "unsubscribe_gamer_event",
    "set_presence_mode_string", "freed_gamer_count", "update_dispatcher_async",
]

_support = _on.support
_VERSION = 1
_UNIX_EPOCH_TICKS = 621_355_968_000_000_000
_TICKS_PER_MICROSECOND = 10

#: Subscriptions this package holds for as long as CNA can call them.
_roots = CallbackRoot()


def callback_failures() -> list:
    """``(handler, exception)`` for every handler registered here that raised."""
    return list(_roots.failures)


def create_signed_in_gamer(gamertag: str, *, is_signed_in_to_live: bool = False,
                           is_guest: bool = False,
                           player_index: PlayerIndex = PlayerIndex.One) -> SignedInGamer:
    """Creates a signed-in gamer object. **This is not a sign-in.**

    CNA's factory exists so a platform layer can publish the gamer the platform
    signed in. Calling it from a game invents a user, so this package is where
    it lives and the qualification is the only thing that calls it.
    """
    view, _keep = string_view(gamertag, "gamertag")
    handle = _support.out_handle(
        "cna_signed_in_gamer_create_ext", view,
        c.c_uint8(1 if is_signed_in_to_live else 0),
        c.c_uint8(1 if is_guest else 0),
        c.c_uint32(int(PlayerIndex(player_index))))
    return SignedInGamer(handle, owned=True)


def publish_signed_in_gamers(gamers: Sequence[SignedInGamer]) -> None:
    """Replaces the process-wide signed-in collection.

    CNA retains each handle for as long as the collection references it, so a
    gamer published here outlives the Python object that made it until the
    collection is replaced. Publishing an empty sequence releases them.
    """
    values = []
    for index, gamer in enumerate(gamers):
        if not isinstance(gamer, SignedInGamer):
            raise TypeError(f"gamers[{index}] must be a SignedInGamer")
        values.append(gamer._value.value)
    array = (c.c_uint64 * len(values))(*values) if values else None
    _support.call("cna_gamer_set_signed_in_gamers_ext", array,
                  c.c_uint64(len(values)))


def create_friend_gamer(gamertag: str, display_name: str, *, is_online: bool = False,
                        is_playing: bool = False, is_away: bool = False,
                        is_busy: bool = False, friend_request_sent_to: bool = False,
                        friend_request_received_from: bool = False) -> FriendGamer:
    """Creates one friend, with the state a platform would have filled in."""
    tag_view, _keep_tag = string_view(gamertag, "gamertag")
    name_view, _keep_name = string_view(display_name, "display_name")
    return FriendGamer(_support.out_handle(
        "cna_friend_gamer_create_ext", tag_view, name_view,
        c.c_uint8(1 if is_online else 0), c.c_uint8(1 if is_playing else 0),
        c.c_uint8(1 if is_away else 0), c.c_uint8(1 if is_busy else 0),
        c.c_uint8(1 if friend_request_sent_to else 0),
        c.c_uint8(1 if friend_request_received_from else 0)), owned=True)


def create_friend_collection(friends: Sequence[FriendGamer]) -> FriendCollection:
    """Builds a friends list from friends this package created."""
    values = []
    for index, friend in enumerate(friends):
        if not isinstance(friend, Gamer):
            raise TypeError(f"friends[{index}] must be a FriendGamer")
        values.append(friend._value.value)
    array = (c.c_uint64 * len(values))(*values) if values else None
    return FriendCollection(_support.out_handle(
        "cna_friend_collection_create_ext", array, c.c_uint64(len(values))))


def create_achievement(key: str, name: str, description: str, *,
                       display_before_earned: bool = True, is_earned: bool = False,
                       earned: datetime | None = None) -> Achievement:
    """Creates one achievement, with an exact earned timestamp.

    ``earned`` becomes a 64-bit tick count with integer arithmetic; a present-day
    timestamp is past 2**53 and would not survive a float.
    """
    key_view, _kk = string_view(key, "key")
    name_view, _kn = string_view(name, "name")
    description_view, _kd = string_view(description, "description")
    if earned is None:
        ticks = 0
    else:
        moment = earned if earned.tzinfo else earned.replace(tzinfo=timezone.utc)
        delta = moment.astimezone(timezone.utc) - datetime(1970, 1, 1,
                                                           tzinfo=timezone.utc)
        microseconds = (delta.days * 86_400_000_000 + delta.seconds * 1_000_000
                        + delta.microseconds)
        ticks = microseconds * _TICKS_PER_MICROSECOND + _UNIX_EPOCH_TICKS
    return Achievement(_support.out_handle(
        "cna_achievement_create_ext", key_view, name_view, description_view,
        c.c_uint8(1 if display_before_earned else 0),
        c.c_uint8(1 if is_earned else 0),
        c.c_int64(checked(ticks, "int64", "earned"))), owned=True)


def create_achievement_collection(
        achievements: Sequence[Achievement]) -> AchievementCollection:
    """Builds an achievement collection from achievements this package created."""
    values = []
    for index, achievement in enumerate(achievements):
        if not isinstance(achievement, Achievement):
            raise TypeError(f"achievements[{index}] must be an Achievement")
        values.append(achievement._value.value)
    array = (c.c_uint64 * len(values))(*values) if values else None
    return AchievementCollection(_support.out_handle(
        "cna_achievement_collection_create_ext", array, c.c_uint64(len(values))))


def gamer_collection_add(collection: GamerCollectionOfT, gamer: Gamer) -> None:
    """Adds a gamer to a collection.

    XNA's ``GamerCollection<T>`` is read-only; CNA's is not, because something
    has to fill it. That something is a platform layer, so it is here.
    """
    _support.call("cna_gamer_collection_add", collection._value, gamer._value)


def gamer_collection_remove(collection: GamerCollectionOfT, gamer: Gamer) -> None:
    """Removes a gamer from a collection."""
    _support.call("cna_gamer_collection_remove", collection._value, gamer._value)


def gamer_collection_clear(collection: GamerCollectionOfT) -> None:
    """Empties a collection."""
    _support.call("cna_gamer_collection_clear", collection._value)


def set_presence_mode_string(gamer: SignedInGamer, mode: str) -> None:
    """Sets a presence mode CNA names with a string rather than an identity."""
    view, _keep = string_view(mode, "mode")
    _support.call("cna_signed_in_gamer_set_presence_mode_string_ext", gamer._value,
                  view)


def _subscribe(route: str, factory: type, handler: Callable, adapt) -> int:
    if not callable(handler):
        raise TypeError("handler must be callable")
    key = object()
    trampoline = _roots.root(key, factory, adapt)
    try:
        registration = _support.out_handle(route, trampoline, None)
    except BaseException:
        _roots.release(key)
        raise
    _roots.root(registration, factory, adapt)
    _roots.release(key)
    return registration


def on_signed_in(handler: Callable[[SignedInGamer], None]) -> int:
    """Calls ``handler(gamer)`` when a gamer signs in. Returns a registration."""

    def adapt(_context, pointer) -> None:
        handler(SignedInGamer(int(pointer.contents.gamer), owned=False))

    return _subscribe("cna_signed_in_gamer_subscribe_signed_in_ext",
                      _online.CNA_SignedInGamerEventCallback, handler, adapt)


def on_signed_out(handler: Callable[[SignedInGamer], None]) -> int:
    """Calls ``handler(gamer)`` when a gamer signs out. Returns a registration."""

    def adapt(_context, pointer) -> None:
        handler(SignedInGamer(int(pointer.contents.gamer), owned=False))

    return _subscribe("cna_signed_in_gamer_subscribe_signed_out_ext",
                      _online.CNA_SignedInGamerEventCallback, handler, adapt)


def on_installing_title_update(handler: Callable[[], None]) -> int:
    """Calls ``handler()`` while the platform installs a title update."""

    def adapt(_context) -> None:
        handler()

    return _subscribe("cna_gamer_services_dispatcher_subscribe_installing_title_update_ext",
                      _online.CNA_GamerAsyncCallback, handler, adapt)


def unsubscribe_gamer_event(registration: int) -> None:
    """Releases a registration this module handed out. No callback follows."""
    _roots.release(registration)
    _support.call("cna_gamer_unsubscribe_ext",
                  c.c_uint64(checked(registration, "uint64", "registration")))


def freed_gamer_count() -> int:
    """How many gamer objects CNA has released.

    A leak check: the number rises as owned gamers are destroyed, and a facade
    that forgot to release one leaves it flat.
    """
    return _support.out_u64("cna_gamer_services_dispatcher_get_freed_gamer_count_ext")


def update_dispatcher_async() -> bool:
    """Pumps the dispatcher once; ``True`` when it had work to do.

    XNA's ``GamerServicesDispatcher.Update`` reports nothing. CNA's asynchronous
    form says whether anything happened, which is what makes a pump loop
    testable rather than a fixed number of iterations.
    """
    return _support.out_bool("cna_gamer_services_dispatcher_update_async")
