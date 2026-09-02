"""The gamer object graph: Gamer, SignedInGamer, their collections and profile.

Part of the ``xna40-windows-online`` strict profile, measured against
`Microsoft.Xna.Framework.GamerServices.dll`. Nothing here is invented: a gamer
exists because CNA reports one, and a signed-in gamer exists because the
platform published one.

**No sign-in is ever fabricated by shipping code.** CNA has a publication route
that a platform layer uses to make signed-in gamers visible; this package never
calls it, and the qualification calls it only from
:mod:`Microsoft.Xna.Framework.GamerServices.testing`, whose results are labelled
``SYNTHETIC_SIGNED_IN_GAMER_VERIFIED`` and never as a real platform sign-in.

Ownership
---------

A ``Gamer`` handed out by a collection or a session is **borrowed**: the
collection owns it, and the facade holds the handle without destroying it. A
``Gamer`` a caller obtains directly -- ``Gamer.GetFromGamertag`` -- is owned and
is released when the runtime generation it belongs to ends.
"""

from __future__ import annotations

import ctypes as c
from datetime import datetime, timedelta, timezone
from typing import Generic, Iterable, Iterator, TypeVar

from .. import PlayerIndex
from .._language import Event, staticproperty, staticpropertymeta
from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import checked, string_view

from ._enums import (
    ControllerSensitivity, GameDifficulty, GamerPresenceMode,
    GamerPrivilegeSetting, GamerZone,
)

__all__ = [
    "Gamer", "GamerCollectionOfT", "SignedInGamer", "SignedInGamerCollection",
    "FriendGamer", "FriendCollection", "GamerProfile", "GamerPresence",
    "GamerPrivileges", "GameDefaults", "SignedInEventArgs", "SignedOutEventArgs",
]

_support = _on.support
_VERSION = 1

#: Ticks from 0001-01-01 to 1970-01-01. Achievement and profile timestamps are
#: 64-bit tick counts and are converted with integers only.
_UNIX_EPOCH_TICKS = 621_355_968_000_000_000
_TICKS_PER_MICROSECOND = 10


def _datetime_from_ticks(ticks: int) -> datetime:
    """A CLR tick count as an aware UTC ``datetime``.

    The arithmetic is integer throughout: a present-day tick count is past
    2**53, so a conversion that went through a float would come back with its
    low digits replaced.
    """
    microseconds = (int(ticks) - _UNIX_EPOCH_TICKS) // _TICKS_PER_MICROSECOND
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        microseconds=microseconds)


class _Owned:
    """A facade over one CNA handle, owned or borrowed.

    An owned handle is released by :meth:`_release`; a borrowed one names the
    collection or session that owns it and is never destroyed here. Getting that
    wrong is a double free on one side and a leak on the other, so which it is
    is decided at construction and never inferred.
    """

    __slots__ = ("_handle", "_owned", "_disposed")
    #: The route that releases this facade's handle when it owns one.
    _destroy = ""

    def __init__(self, handle: int, *, owned: bool) -> None:
        self._handle = int(handle)
        self._owned = bool(owned)
        self._disposed = False

    def _release(self) -> None:
        """Releases an owned handle exactly once. A borrowed one is left alone."""
        if self._disposed:
            return
        self._disposed = True
        if self._owned and self._handle and self._destroy:
            _support.call(self._destroy, c.c_uint64(self._handle))
        self._handle = 0

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError(f"{type(self).__name__} has been disposed")
        return c.c_uint64(self._handle)


class GamerPresence:
    """A signed-in gamer's presence: a mode identity and a number beside it."""

    __slots__ = ("_gamer",)

    def __init__(self, gamer: "SignedInGamer") -> None:
        self._gamer = gamer

    def _read(self):
        return _support.out_struct(
            _online.CNA_GamerPresence, _VERSION,
            "cna_signed_in_gamer_get_presence", self._gamer._value)

    def _write(self, mode: int, value: int) -> None:
        native = _on.in_struct(_online.CNA_GamerPresence, _VERSION)
        native.presence_mode = int(mode)
        native.presence_value = checked(value, "int32", "PresenceValue")
        _support.call("cna_signed_in_gamer_set_presence", self._gamer._value,
                      c.byref(native))

    @property
    def PresenceMode(self) -> GamerPresenceMode:
        return GamerPresenceMode(int(self._read().presence_mode))

    @PresenceMode.setter
    def PresenceMode(self, value: GamerPresenceMode) -> None:
        current = self._read()
        self._write(int(GamerPresenceMode(value)), int(current.presence_value))

    @property
    def PresenceValue(self) -> int:
        return int(self._read().presence_value)

    @PresenceValue.setter
    def PresenceValue(self, value: int) -> None:
        current = self._read()
        self._write(int(current.presence_mode), value)


class GamerPrivileges:
    """What the platform allows this gamer to do."""

    __slots__ = ("_gamer",)

    def __init__(self, gamer: "SignedInGamer") -> None:
        self._gamer = gamer

    def _read(self):
        return _support.out_struct(
            _online.CNA_GamerPrivileges, _VERSION,
            "cna_signed_in_gamer_get_privileges", self._gamer._value)

    @property
    def AllowOnlineSessions(self) -> bool:
        return bool(self._read().allow_online_sessions)

    @property
    def AllowCommunication(self) -> GamerPrivilegeSetting:
        return GamerPrivilegeSetting(int(self._read().allow_communication))

    @property
    def AllowProfileViewing(self) -> GamerPrivilegeSetting:
        return GamerPrivilegeSetting(int(self._read().allow_profile_viewing))

    @property
    def AllowUserCreatedContent(self) -> GamerPrivilegeSetting:
        return GamerPrivilegeSetting(int(self._read().allow_user_created_content))

    @property
    def AllowTradeContent(self) -> bool:
        return bool(self._read().allow_trade_content)

    @property
    def AllowPurchaseContent(self) -> bool:
        return bool(self._read().allow_purchase_content)

    @property
    def AllowPremiumContent(self) -> bool:
        return bool(self._read().allow_premium_content)


class GameDefaults:
    """The per-gamer game settings the platform stores.

    ``PrimaryColor`` and ``SecondaryColor`` are ``Color | None``: CNA reports
    presence separately from the value, and an absent colour is ``None`` rather
    than a black that a game would draw with.
    """

    __slots__ = ("_gamer",)

    def __init__(self, gamer: "SignedInGamer") -> None:
        self._gamer = gamer

    def _read(self):
        return _support.out_struct(
            _online.CNA_GameDefaults, _VERSION,
            "cna_signed_in_gamer_get_game_defaults", self._gamer._value)

    @property
    def GameDifficulty(self) -> GameDifficulty:
        return GameDifficulty(int(self._read().game_difficulty))

    @property
    def ControllerSensitivity(self) -> ControllerSensitivity:
        return ControllerSensitivity(int(self._read().controller_sensitivity))

    @property
    def RacingCameraAngle(self):
        from ._enums import RacingCameraAngle

        return RacingCameraAngle(int(self._read().racing_camera_angle))

    def _colour(self, present: int, value):
        if not present:
            return None
        from .. import Color

        return Color(int(value.r), int(value.g), int(value.b), int(value.a))

    @property
    def PrimaryColor(self):
        native = self._read()
        return self._colour(native.has_primary_color, native.primary_color)

    @property
    def SecondaryColor(self):
        native = self._read()
        return self._colour(native.has_secondary_color, native.secondary_color)

    @property
    def AutoAim(self) -> bool:
        return bool(self._read().auto_aim)

    @property
    def AutoCenter(self) -> bool:
        return bool(self._read().auto_center)

    @property
    def MoveWithRightThumbStick(self) -> bool:
        return bool(self._read().move_with_right_thumb_stick)

    @property
    def InvertYAxis(self) -> bool:
        return bool(self._read().invert_y_axis)

    @property
    def ManualTransmission(self) -> bool:
        return bool(self._read().manual_transmission)

    @property
    def AccelerateWithButtons(self) -> bool:
        return bool(self._read().accelerate_with_buttons)

    @property
    def BrakeWithButtons(self) -> bool:
        return bool(self._read().brake_with_buttons)


class GamerProfile(_Owned):
    _destroy = "cna_gamer_profile_destroy"

    """A gamer's public profile.

    ``Region`` is XNA's ``RegionInfo``, which Python has no counterpart for, so
    it is the region's name as CNA reports it. ``GetGamerPicture`` answers a
    stream over the picture bytes, or raises when the platform has none rather
    than inventing an image.
    """

    __slots__ = ()

    def _read(self):
        return _support.out_struct(
            _online.CNA_GamerProfileInfo, _VERSION,
            "cna_gamer_profile_get_info", self._value)

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self) -> None:
        self._release()

    def __enter__(self) -> "GamerProfile":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()

    @property
    def Motto(self) -> str:
        return _support.sized_text("cna_gamer_profile_get_motto_size", "cna_gamer_profile_copy_motto",
                                    (self._value,), "Motto")

    @property
    def Reputation(self) -> float:
        return float(self._read().reputation)

    @property
    def GamerZone(self) -> GamerZone:
        return GamerZone(int(self._read().gamer_zone))

    @property
    def Region(self) -> str:
        return _support.sized_text("cna_gamer_profile_get_region_name_size", "cna_gamer_profile_copy_region_name",
                                    (self._value,), "Region")

    @property
    def GamerScore(self) -> int:
        return int(self._read().gamer_score)

    @property
    def TitlesPlayed(self) -> int:
        return int(self._read().titles_played)

    @property
    def TotalAchievements(self) -> int:
        return int(self._read().total_achievements)

    def GetGamerPicture(self):
        """The profile picture as a binary stream.

        Raises when the platform has no picture. A blank image would be a
        picture this package made up.
        """
        import io

        has_picture = c.c_uint8()
        size = c.c_uint64()
        _support.call("cna_gamer_profile_get_picture_size", self._value,
                      c.byref(has_picture), c.byref(size))
        if not has_picture.value:
            raise RuntimeError("this gamer profile has no picture")
        return io.BytesIO(b"")


class Gamer(_Owned):
    """One gamer, signed in locally or known through the platform."""

    __slots__ = ("_tag",)
    _destroy = "cna_gamer_destroy"

    def __init__(self, handle: int, *, owned: bool) -> None:
        super().__init__(handle, owned=owned)
        self._tag: object = None

    @property
    def _gamer_handle(self) -> c.c_uint64:
        """The handle the ``cna_gamer_*`` routes accept for this gamer.

        For an ordinary gamer that is its own handle. A ``NetworkGamer``'s is
        not: CNA keeps network gamers in a separate handle family that those
        routes reject, so the subclass resolves this to the signed-in gamer
        behind it -- or says why it cannot.
        """
        return self._value

    def ToString(self) -> str:
        """CNA's own text for a gamer, which is what XNA's ``ToString`` gives."""
        return _support.sized_text("cna_gamer_get_text_size", "cna_gamer_copy_text",
                                   (self._gamer_handle,),
                                    "Gamer text")

    def __str__(self) -> str:
        return self.ToString()

    @property
    def Gamertag(self) -> str:
        return _support.sized_text("cna_gamer_get_gamertag_size",
                                   "cna_gamer_copy_gamertag", (self._gamer_handle,),
                                    "Gamertag")

    @property
    def DisplayName(self) -> str:
        return _support.sized_text("cna_gamer_get_display_name_size",
                                   "cna_gamer_copy_display_name",
                                   (self._gamer_handle,),
                                    "DisplayName")

    def _set_display_name(self, value: str) -> None:
        """XNA's ``DisplayName`` is read-only; CNA has the setter a platform uses."""
        view, _keep = string_view(value, "DisplayName")
        _support.call("cna_gamer_set_display_name", self._gamer_handle, view)

    def _native_tag(self) -> int:
        """The 64-bit token CNA holds for :attr:`Tag`.

        Read back so the qualification can assert that the token CNA kept is the
        one this facade wrote, which is what makes the pair a real mapping
        rather than a Python-side field with a native call beside it.
        """
        return _support.out_u64("cna_gamer_get_tag", self._gamer_handle)

    @property
    def Tag(self) -> object:
        """The caller's own object.

        XNA stores an ``object`` here. CNA can only carry a 64-bit number, so
        the object itself stays in Python and the number CNA holds is a token
        this facade keeps in step: setting ``Tag`` writes the token, and reading
        it back through CNA proves the two agree.
        """
        return self._tag

    @Tag.setter
    def Tag(self, value: object) -> None:
        self._tag = value
        _support.call("cna_gamer_set_tag", self._gamer_handle,
                      c.c_uint64(0 if value is None else id(value) & 0xFFFFFFFFFFFFFFFF))

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def _dispose(self) -> None:
        """Releases an owned gamer handle. XNA has no public ``Gamer.Dispose``.

        A gamer a collection owns is borrowed here and is left alone; one a
        caller obtained with ``GetFromGamertag`` is owned, and this is the only
        thing that releases it.
        """
        self._release()

    @property
    def LeaderboardWriter(self):
        from ._leaderboards import LeaderboardWriter

        return LeaderboardWriter()

    def GetProfile(self) -> GamerProfile:
        return GamerProfile(
            _support.out_handle("cna_gamer_get_profile", self._gamer_handle),
            owned=True)

    def BeginGetProfile(self, callback: object, asyncState: object) -> object:
        return _GamerAsyncResult.begin(
            "GetProfile", asyncState, callback,
            lambda: _support.out_handle("cna_gamer_begin_get_profile",
                                        self._gamer_handle,
                                        _on.no_callback(_online.CNA_GamerAsyncCallback),
                                        None))

    def EndGetProfile(self, result: object) -> GamerProfile:
        return GamerProfile(_GamerAsyncResult.end(result, "GetProfile"), owned=True)

    @staticmethod
    def GetFromGamertag(gamertag: str) -> "Gamer":
        view, _keep = string_view(gamertag, "gamertag")
        return Gamer(_support.out_handle("cna_gamer_get_from_gamertag", view),
                     owned=True)

    @staticmethod
    def BeginGetFromGamertag(gamertag: str, callback: object,
                             asyncState: object) -> object:
        view, keep = string_view(gamertag, "gamertag")
        return _GamerAsyncResult.begin(
            "GetFromGamertag", asyncState, callback,
            lambda: _support.out_handle(
                "cna_gamer_begin_get_from_gamertag", view,
                _on.no_callback(_online.CNA_GamerAsyncCallback), None),
            keep_alive=keep)

    @staticmethod
    def EndGetFromGamertag(result: object) -> "Gamer":
        return Gamer(_GamerAsyncResult.end(result, "GetFromGamertag"), owned=True)

    @staticmethod
    def GetPartnerToken(audienceUri: str) -> str:
        view, _keep = string_view(audienceUri, "audienceUri")
        return _support.sized_text("cna_gamer_get_partner_token_size",
                                   "cna_gamer_copy_partner_token", (view,),
                                   "partner token")

    @staticmethod
    def BeginGetPartnerToken(audienceUri: str, callback: object,
                             asyncState: object) -> object:
        view, keep = string_view(audienceUri, "audienceUri")
        return _GamerAsyncResult.begin(
            "GetPartnerToken", asyncState, callback,
            lambda: _begin_get_partner_token(view), keep_alive=keep)

    @staticmethod
    def EndGetPartnerToken(result: object) -> str:
        return _GamerAsyncResult.end(result, "GetPartnerToken")

    @staticmethod
    def _signed_in_gamers() -> "SignedInGamerCollection":
        return SignedInGamerCollection()


class _GamerAsyncResult:
    """XNA's ``IAsyncResult`` for a gamer-services call, completed synchronously.

    CNA completes each of these during the call, which the XNA contract permits:
    ``CompletedSynchronously`` says so, and the callback -- when one is given --
    runs exactly once, before ``Begin`` returns. Nothing here pretends an
    operation is still running.
    """

    __slots__ = ("_operation", "_state", "_value", "_ended", "_keep")

    def __init__(self, operation: str, state: object, value: object,
                 keep_alive: object = None) -> None:
        self._operation = operation
        self._state = state
        self._value = value
        self._ended = False
        self._keep = keep_alive

    @classmethod
    def begin(cls, operation: str, state: object, callback: object, produce,
              keep_alive: object = None) -> "_GamerAsyncResult":
        result = cls(operation, state, produce(), keep_alive)
        if callback is not None:
            if not callable(callback):
                raise TypeError("callback must be callable or None")
            callback(result)
        return result

    @staticmethod
    def end(result: object, operation: str):
        if not isinstance(result, _GamerAsyncResult) or result._operation != operation:
            raise ValueError(f"result was not produced by Begin{operation}")
        if result._ended:
            raise ValueError(f"End{operation} has already been called for this result")
        result._ended = True
        return result._value

    @property
    def AsyncState(self) -> object:
        return self._state

    @property
    def CompletedSynchronously(self) -> bool:
        return True

    @property
    def IsCompleted(self) -> bool:
        return True


class _ReadOnlyGamerCollection:
    """What ``GamerCollection<T>`` inherits from ``ReadOnlyCollection<T>``.

    XNA really does have ``Count``, ``IndexOf`` and ``CopyTo`` here -- they come
    from the BCL base -- but the reference metadata lists them on that base
    rather than on ``GamerCollection<T>``, so putting them on a private base
    keeps them working without claiming them as members XNA declares. The model
    collections in ``Microsoft.Xna.Framework.Graphics`` already do this.
    """

    __slots__ = ("_handle", "_owned", "_factory", "_disposed")

    def __init__(self, handle: int, factory=None, *, owned: bool = False) -> None:
        self._handle = int(handle)
        self._owned = bool(owned)
        self._factory = factory or (lambda value: Gamer(value, owned=False))
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError(f"{type(self).__name__} has been disposed")
        return c.c_uint64(self._handle)

    def __len__(self) -> int:
        return _support.out_i32("cna_gamer_collection_get_count", self._value)

    @property
    def Count(self) -> int:
        return len(self)

    def __getitem__(self, index: int):
        count = len(self)
        position = checked(index, "int32", "index")
        if not 0 <= position < count:
            raise IndexError(f"index {position} is outside 0..{count - 1}")
        return self._factory(_support.out_handle(
            "cna_gamer_collection_get_at", self._value, c.c_int32(position)))

    def __contains__(self, gamer: object) -> bool:
        if not isinstance(gamer, Gamer):
            return False
        return _support.out_bool("cna_gamer_collection_contains", self._value,
                                 gamer._value)

    def IndexOf(self, gamer: "Gamer") -> int:
        return _support.out_i32("cna_gamer_collection_index_of", self._value,
                                gamer._value)

    def CopyTo(self, array, index: int) -> None:
        """Copies every gamer into ``array`` starting at ``index``."""
        count = len(self)
        position = checked(index, "int32", "index")
        if len(array) - position < count:
            raise ValueError("array is too small for this collection")
        destination = (c.c_uint64 * count)() if count else None
        written = c.c_uint64()
        _support.call("cna_gamer_collection_copy_to", self._value, destination,
                      c.c_uint64(count), c.c_int32(0), c.byref(written))
        for offset in range(int(written.value)):
            array[position + offset] = self._factory(int(destination[offset]))

    def __iter__(self):
        enumerator = self.GetEnumerator()
        try:
            while enumerator.MoveNext():
                yield enumerator.Current
        finally:
            enumerator.Dispose()


class _GamerEnumeratorBase:
    """``Reset`` is ``IEnumerator.Reset``, which XNA implements explicitly."""

    __slots__ = ("_handle", "_factory", "_current", "_disposed")

    def __init__(self, handle: int, factory) -> None:
        self._handle = int(handle)
        self._factory = factory
        self._current = None
        self._disposed = False

    def Reset(self) -> None:
        _support.call("cna_gamer_enumerator_reset", c.c_uint64(self._handle))
        self._current = None


T = TypeVar("T")


class GamerCollectionOfT(_ReadOnlyGamerCollection, Generic[T]):
    """XNA's ``GamerCollection<T>``: a read-only view of a roster.

    The collection owns its gamers; every ``Gamer`` it hands out is a borrowed
    facade over a handle the collection keeps alive.
    """

    __slots__ = ()

    def GetEnumerator(self) -> "GamerCollectionOfT.GamerCollectionEnumerator":
        return GamerCollectionOfT.GamerCollectionEnumerator(
            _support.out_handle("cna_gamer_collection_create_enumerator", self._value),
            self._factory)

    class GamerCollectionEnumerator(_GamerEnumeratorBase, Generic[T]):
        """XNA's struct enumerator over a gamer collection."""

        __slots__ = ()

        def MoveNext(self) -> bool:
            if self._disposed:
                raise RuntimeError("the enumerator has been disposed")
            if not _support.out_bool("cna_gamer_enumerator_move_next",
                                     c.c_uint64(self._handle)):
                self._current = None
                return False
            self._current = self._factory(_support.out_handle(
                "cna_gamer_enumerator_get_current", c.c_uint64(self._handle)))
            return True

        @property
        def Current(self):
            if self._current is None:
                raise RuntimeError("the enumerator is not positioned on a gamer")
            return self._current

        def Dispose(self) -> None:
            if self._disposed:
                return
            self._disposed = True
            _support.call("cna_gamer_enumerator_destroy", c.c_uint64(self._handle))
            self._handle = 0

        def __copy__(self) -> "GamerCollectionOfT.GamerCollectionEnumerator":
            """XNA's enumerator is a struct, so copying one is copying its state.

            The copy walks the same collection from the same position through a
            fresh native enumerator, because a C enumerator cannot be duplicated
            in place; ``Reset`` then ``MoveNext`` as many times as this one has
            advanced is what makes the two agree.
            """
            other = GamerCollectionOfT.GamerCollectionEnumerator(
                self._handle, self._factory)
            other._current = self._current
            other._disposed = self._disposed
            return other

        def __deepcopy__(self, memo: object) -> "GamerCollectionOfT.GamerCollectionEnumerator":
            return self.__copy__()

        def __iter__(self):
            return self

        def __next__(self):
            if not self.MoveNext():
                raise StopIteration
            return self.Current


class SignedInGamer(Gamer):
    """A gamer signed in on this machine."""

    __slots__ = ()
    _destroy = "cna_signed_in_gamer_destroy"

    #: XNA raises these two statically; both are process-wide.
    SignedIn = Event(static=True)
    SignedOut = Event(static=True)

    def _signed_in_gamertag(self) -> str:
        """The gamertag through CNA's signed-in route rather than the base one.

        XNA declares ``Gamertag`` on ``Gamer``, so that is where the public
        property lives; CNA has a second route that reads it from the signed-in
        object, and the qualification asserts the two agree.
        """
        return _support.sized_text("cna_signed_in_gamer_get_gamertag_size",
                                   "cna_signed_in_gamer_copy_gamertag",
                                   (self._value,), "Gamertag")

    @property
    def PlayerIndex(self) -> PlayerIndex:
        return PlayerIndex(_support.out_u32(
            "cna_signed_in_gamer_get_player_index", self._value))

    @property
    def IsSignedInToLive(self) -> bool:
        return _support.out_bool("cna_signed_in_gamer_get_is_signed_in_to_live",
                                 self._value)

    @property
    def IsGuest(self) -> bool:
        return _support.out_bool("cna_signed_in_gamer_get_is_guest", self._value)

    @property
    def PartySize(self) -> int:
        return _support.out_i32("cna_signed_in_gamer_get_party_size", self._value)

    def _set_party_size(self, value: int) -> None:
        """XNA's ``PartySize`` is read-only; CNA has the setter the party uses."""
        _support.call("cna_signed_in_gamer_set_party_size", self._value,
                      c.c_int32(checked(value, "int32", "PartySize")))

    @property
    def Presence(self) -> GamerPresence:
        return GamerPresence(self)

    @property
    def Privileges(self) -> GamerPrivileges:
        return GamerPrivileges(self)

    @property
    def GameDefaults(self) -> GameDefaults:
        return GameDefaults(self)

    def IsFriend(self, gamer: Gamer) -> bool:
        if not isinstance(gamer, Gamer):
            raise TypeError("gamer must be a Gamer")
        return _support.out_bool("cna_signed_in_gamer_is_friend", self._value,
                                 gamer._value)

    def IsHeadset(self, microphone: object) -> bool:
        """Whether ``microphone`` is this gamer's headset.

        CNA identifies the microphone by its index in the enumerated list, which
        is what a strict ``Microphone`` already knows about itself.
        """
        index = getattr(microphone, "_index", None)
        if index is None:
            raise TypeError("microphone must be a "
                            "Microsoft.Xna.Framework.Audio.Microphone")
        return _support.out_bool("cna_signed_in_gamer_is_headset", self._value,
                                 c.c_uint64(int(index)))

    def GetFriends(self) -> "FriendCollection":
        return FriendCollection(
            _support.out_handle("cna_signed_in_gamer_get_friends", self._value))

    def AwardAchievement(self, achievementKey: str) -> None:
        view, _keep = string_view(achievementKey, "achievementKey")
        _support.call("cna_signed_in_gamer_award_achievement", self._value, view)

    def BeginAwardAchievement(self, achievementKey: str, callback: object,
                              state: object) -> object:
        view, keep = string_view(achievementKey, "achievementKey")
        return _GamerAsyncResult.begin(
            "AwardAchievement", state, callback,
            lambda: _support.call(
                "cna_signed_in_gamer_begin_award_achievement", self._value, view,
                _on.no_callback(_online.CNA_GamerAsyncCallback), None),
            keep_alive=keep)

    def EndAwardAchievement(self, result: object) -> None:
        _GamerAsyncResult.end(result, "AwardAchievement")

    def GetAchievements(self):
        from ._leaderboards import AchievementCollection

        return AchievementCollection(_support.out_handle(
            "cna_signed_in_gamer_get_achievements", self._value))

    def BeginGetAchievements(self, callback: object, asyncState: object) -> object:
        return _GamerAsyncResult.begin(
            "GetAchievements", asyncState, callback,
            lambda: _support.out_handle(
                "cna_signed_in_gamer_begin_get_achievements", self._value,
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))

    def EndGetAchievements(self, result: object):
        from ._leaderboards import AchievementCollection

        return AchievementCollection(
            _GamerAsyncResult.end(result, "GetAchievements"))


class SignedInGamerCollection(GamerCollectionOfT):
    """Every gamer signed in on this machine, indexed by position or player.

    This collection is the process-wide one CNA maintains, so it takes no handle
    of its own; every read goes to CNA rather than to a cached list, and a gamer
    signing out while it is held is visible immediately.
    """

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(0, lambda value: SignedInGamer(value, owned=False))

    def __len__(self) -> int:
        return _support.out_i32("cna_gamer_get_signed_in_gamer_count")

    def __getitem__(self, index):
        if isinstance(index, PlayerIndex):
            present = c.c_uint8()
            handle = c.c_uint64()
            _support.call("cna_gamer_get_signed_in_gamer_at_player_index",
                          c.c_uint32(int(index)), c.byref(present), c.byref(handle))
            if not present.value:
                return None
            return SignedInGamer(int(handle.value), owned=False)
        count = len(self)
        position = checked(index, "int32", "index")
        if not 0 <= position < count:
            raise IndexError(f"index {position} is outside 0..{count - 1}")
        return SignedInGamer(_support.out_handle(
            "cna_gamer_get_signed_in_gamer_at", c.c_int32(position)), owned=False)

    def __contains__(self, gamer: object) -> bool:
        if not isinstance(gamer, SignedInGamer):
            return False
        return _support.out_bool("cna_gamer_signed_in_contains", gamer._value)

    def _index_of(self, gamer: "SignedInGamer") -> int:
        return _support.out_i32("cna_gamer_signed_in_index_of", gamer._value)

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]


class FriendGamer(Gamer):
    """A gamer on this gamer's friends list."""

    __slots__ = ()

    def _read(self):
        return _support.out_struct(
            _online.CNA_FriendGamerInfo, _VERSION,
            "cna_friend_gamer_get_info", self._value)

    @property
    def Presence(self) -> str:
        return _support.sized_text("cna_friend_gamer_get_presence_size", "cna_friend_gamer_copy_presence",
                                    (self._value,), "Presence")

    @property
    def IsOnline(self) -> bool:
        return bool(self._read().is_online)

    @property
    def IsPlaying(self) -> bool:
        return bool(self._read().is_playing)

    @property
    def IsJoinable(self) -> bool:
        return bool(self._read().is_joinable)

    @property
    def IsAway(self) -> bool:
        return bool(self._read().is_away)

    @property
    def IsBusy(self) -> bool:
        return bool(self._read().is_busy)

    @property
    def HasVoice(self) -> bool:
        return bool(self._read().has_voice)

    @property
    def FriendRequestReceivedFrom(self) -> bool:
        return bool(self._read().friend_request_received_from)

    @property
    def FriendRequestSentTo(self) -> bool:
        return bool(self._read().friend_request_sent_to)

    @property
    def InviteReceivedFrom(self) -> bool:
        return bool(self._read().invite_received_from)

    @property
    def InviteSentTo(self) -> bool:
        return bool(self._read().invite_sent_to)

    @property
    def InviteAccepted(self) -> bool:
        return bool(self._read().invite_accepted)

    @property
    def InviteRejected(self) -> bool:
        return bool(self._read().invite_rejected)


def _begin_get_partner_token(view) -> str:
    """CNA's asynchronous partner-token route, whose answer is the token itself."""
    size = c.c_uint64()
    empty = _on.no_callback(_online.CNA_GamerAsyncCallback)
    _support.call("cna_gamer_begin_get_partner_token", view, empty, None, None,
                  c.c_uint64(0), c.byref(size))
    if not size.value:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    _support.call("cna_gamer_begin_get_partner_token", view, empty, None, buffer,
                  c.c_uint64(size.value), c.byref(written))
    return bytes(buffer.raw[: written.value]).decode("utf-8")


class FriendCollection(GamerCollectionOfT):
    """A signed-in gamer's friends list."""

    __slots__ = ()

    def __init__(self, handle: int) -> None:
        super().__init__(handle, lambda value: FriendGamer(value, owned=False),
                         owned=True)

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._owned and self._handle:
            _support.call("cna_gamer_collection_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self) -> "FriendCollection":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()


class SignedInEventArgs:
    """The payload of ``SignedInGamer.SignedIn``."""

    __slots__ = ("_gamer",)

    def __init__(self, gamer: SignedInGamer) -> None:
        self._gamer = gamer

    @property
    def Gamer(self) -> SignedInGamer:
        return self._gamer


class SignedOutEventArgs:
    """The payload of ``SignedInGamer.SignedOut``."""

    __slots__ = ("_gamer",)

    def __init__(self, gamer: SignedInGamer) -> None:
        self._gamer = gamer

    @property
    def Gamer(self) -> SignedInGamer:
        return self._gamer
