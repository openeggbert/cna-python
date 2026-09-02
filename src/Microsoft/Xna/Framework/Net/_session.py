"""NetworkSession, its gamers, and the sessions discovery finds.

Part of the ``xna40-windows-online`` strict profile, measured against
`Microsoft.Xna.Framework.Net.dll`.

Creating a session needs at least one signed-in gamer, which is a *platform
identity*: nothing here invents one, and a host with nobody signed in gets CNA's
own refusal rather than a session that appears to exist. The qualification
publishes a synthetic signed-in gamer through
:mod:`Microsoft.Xna.Framework.GamerServices.testing` and labels every result
``SYNTHETIC_SIGNED_IN_GAMER_VERIFIED``.

Rosters
-------

A session has four: all gamers, the local ones, the remote ones, and the ones
who have left. CNA numbers them and this module reads each through its own
identity, so a roster is never read with another's number.

Packet sizes
------------

``ReceiveData`` into a destination that is too small is a *refusal* in XNA, not a
silent truncation. This module refuses before CNA is called when the destination
cannot hold what is waiting, and it says so.
"""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from typing import Iterable

from .._language import Event, classproperty, staticpropertymeta
from ..GamerServices._gamer import (
    Gamer, GamerCollectionOfT, SignedInGamer, _GamerAsyncResult,
)
from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import CallbackRoot, checked, string_view

from ._packets import PacketReader, PacketWriter
from ._values import (
    GameEndedEventArgs, GameStartedEventArgs, GamerJoinedEventArgs,
    GamerLeftEventArgs, HostChangedEventArgs, NetworkSessionEndReason,
    NetworkSessionEndedEventArgs, NetworkSessionJoinError,
    NetworkSessionJoinException, NetworkSessionProperties, NetworkSessionState,
    NetworkSessionType, QualityOfService, SendDataOptions,
    WriteLeaderboardsEventArgs,
)

__all__ = [
    "NetworkGamer", "LocalNetworkGamer", "NetworkMachine",
    "AvailableNetworkSession", "AvailableNetworkSessionCollection",
    "NetworkSession",
]

_support = _on.support
_VERSION = 1
_TICKS_PER_MICROSECOND = 10

#: Which roster a collection reads, from the generated ABI.
_ROSTER_ALL = _online.CNA_NETWORK_SESSION_ROSTER_ALL
_ROSTER_LOCAL = _online.CNA_NETWORK_SESSION_ROSTER_LOCAL
_ROSTER_REMOTE = _online.CNA_NETWORK_SESSION_ROSTER_REMOTE
_ROSTER_PREVIOUS = _online.CNA_NETWORK_SESSION_ROSTER_PREVIOUS


def _timespan(ticks: int) -> timedelta:
    return timedelta(microseconds=int(ticks) // _TICKS_PER_MICROSECOND)


def _ticks(value: timedelta, what: str) -> int:
    if not isinstance(value, timedelta):
        raise TypeError(f"{what} must be a timedelta, not {type(value).__name__}")
    microseconds = (value.days * 86_400_000_000 + value.seconds * 1_000_000
                    + value.microseconds)
    return microseconds * _TICKS_PER_MICROSECOND


def _last_join_error() -> NetworkSessionJoinError | None:
    """Why the last join failed, or ``None`` when CNA recorded no reason."""
    error = c.c_uint32()
    present = c.c_uint8()
    _support.call("cna_net_get_last_join_error", c.byref(error), c.byref(present))
    return NetworkSessionJoinError(int(error.value)) if present.value else None


class NetworkGamer(Gamer):
    """A gamer in a session.

    XNA derives this from ``Gamer``, so ``Gamertag``, ``DisplayName``, ``Tag``,
    ``ToString`` and ``GetProfile`` are inherited. CNA keeps network gamers in a
    **separate handle family**: the ``cna_gamer_*`` routes answer
    ``CNA_RESULT_INVALID_HANDLE`` for one, and ``net_gamers.h`` declares no
    gamertag, display-name or profile route of its own.

    A *local* gamer has a signed-in gamer behind it, and the inherited members
    resolve through that -- which is both correct and what XNA means. A *remote*
    one has nothing to resolve to, so those members raise an error naming the
    missing route rather than answering with an empty string. That is a measured
    upstream gap, recorded in ``docs/online-upstream-findings.md``.
    """

    __slots__ = ()
    _destroy = "cna_network_gamer_destroy"

    @property
    def _gamer_handle(self) -> c.c_uint64:
        if self.IsLocal:
            return c.c_uint64(_support.out_handle(
                "cna_local_network_gamer_get_signed_in_gamer", self._value))
        raise NotImplementedError(
            "a remote NetworkGamer's inherited Gamer members have no route to "
            "reach: CNA's cna_gamer_* routes reject a network-gamer handle, and "
            "net_gamers.h declares no gamertag, display-name or profile route "
            "of its own")

    @property
    def Session(self) -> "NetworkSession":
        return NetworkSession._adopt(
            _support.out_handle("cna_network_gamer_get_session", self._value),
            owned=False)

    @property
    def Machine(self) -> "NetworkMachine":
        return NetworkMachine(
            _support.out_handle("cna_network_gamer_copy_machine", self._value),
            owned=False)

    @property
    def IsHost(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_host", self._value)

    @property
    def IsLocal(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_local", self._value)

    @property
    def IsPrivateSlot(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_private_slot", self._value)

    @property
    def IsReady(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_ready", self._value)

    @IsReady.setter
    def IsReady(self, value: bool) -> None:
        _support.call("cna_network_gamer_set_is_ready", self._value,
                      c.c_uint8(1 if value else 0))

    @property
    def HasVoice(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_has_voice", self._value)

    @property
    def IsTalking(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_talking", self._value)

    @property
    def IsMutedByLocalUser(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_muted_by_local_user",
                                 self._value)

    @property
    def IsGuest(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_is_guest", self._value)

    @property
    def RoundtripTime(self) -> timedelta:
        return _timespan(_support.out_i64("cna_network_gamer_get_roundtrip_ticks",
                                          self._value))

    @property
    def Id(self) -> int:
        return _support.out_u8("cna_network_gamer_get_id", self._value)

    @property
    def HasLeftSession(self) -> bool:
        return _support.out_bool("cna_network_gamer_get_has_left_session",
                                 self._value)


class LocalNetworkGamer(NetworkGamer):
    """A gamer this machine owns: the one that can send and receive."""

    __slots__ = ()

    @property
    def SignedInGamer(self) -> SignedInGamer:
        return SignedInGamer(_support.out_handle(
            "cna_local_network_gamer_get_signed_in_gamer", self._value), owned=False)

    @property
    def IsDataAvailable(self) -> bool:
        return _support.out_bool("cna_local_network_gamer_get_is_data_available",
                                 self._value)

    def EnableSendVoice(self, remoteGamer: NetworkGamer, enable: bool) -> None:
        if not isinstance(remoteGamer, NetworkGamer):
            raise TypeError("remoteGamer must be a NetworkGamer")
        _support.call("cna_local_network_gamer_enable_send_voice", self._value,
                      remoteGamer._value, c.c_uint8(1 if enable else 0))

    def SendPartyInvites(self) -> None:
        _support.call("cna_local_network_gamer_send_party_invites", self._value)

    def SendData(self, *args: object) -> None:
        """XNA's seven ``SendData`` overloads.

        Three shapes -- a byte array, a byte array with an offset and a count, or
        a ``PacketWriter`` -- each with an optional recipient.
        """
        if not args:
            raise TypeError("no matching SendData overload")
        data = args[0]
        rest = args[1:]
        if isinstance(data, PacketWriter):
            if len(rest) == 1:
                options, recipient = rest[0], None
            elif len(rest) == 2:
                options, recipient = rest
            else:
                raise TypeError("no matching SendData overload")
            if recipient is None:
                _support.call("cna_local_network_gamer_send_packet_writer",
                              self._value, data._value,
                              c.c_uint32(int(SendDataOptions(options))))
                return
            _support.call("cna_local_network_gamer_send_packet_writer_to",
                          self._value, data._value,
                          c.c_uint32(int(SendDataOptions(options))),
                          _network_gamer(recipient)._value)
            return
        payload = bytes(bytearray(data))
        buffer = (c.c_uint8 * len(payload))(*payload) if payload else None
        if len(rest) in (1, 2) and not isinstance(rest[0], int):
            options = rest[0]
            recipient = rest[1] if len(rest) == 2 else None
            if recipient is None:
                _support.call("cna_local_network_gamer_send_data", self._value,
                              buffer, c.c_uint64(len(payload)),
                              c.c_uint32(int(SendDataOptions(options))))
                return
            _support.call("cna_local_network_gamer_send_data_to", self._value,
                          buffer, c.c_uint64(len(payload)),
                          c.c_uint32(int(SendDataOptions(options))),
                          _network_gamer(recipient)._value)
            return
        if len(rest) in (3, 4):
            offset, count, options = rest[0], rest[1], rest[2]
            recipient = rest[3] if len(rest) == 4 else None
            offset = checked(offset, "int32", "offset")
            count = checked(count, "int32", "count")
            if offset < 0 or count < 0 or offset + count > len(payload):
                raise ValueError(
                    f"offset {offset} and count {count} are outside a "
                    f"{len(payload)}-byte array")
            if recipient is None:
                _support.call("cna_local_network_gamer_send_data_range", self._value,
                              buffer, c.c_uint64(len(payload)), c.c_int32(offset),
                              c.c_int32(count),
                              c.c_uint32(int(SendDataOptions(options))))
                return
            _support.call("cna_local_network_gamer_send_data_range_to", self._value,
                          buffer, c.c_uint64(len(payload)), c.c_int32(offset),
                          c.c_int32(count),
                          c.c_uint32(int(SendDataOptions(options))),
                          _network_gamer(recipient)._value)
            return
        raise TypeError("no matching SendData overload")

    def ReceiveData(self, *args: object):
        """XNA's three ``ReceiveData`` overloads.

        Each answers ``(byteCount, sender)``: XNA's ``out NetworkGamer sender``
        becomes a second return value, which is this projection's rule for every
        ``out`` parameter.
        """
        if not args:
            raise TypeError("no matching ReceiveData overload")
        destination = args[0]
        if isinstance(destination, PacketReader):
            if len(args) != 1:
                raise TypeError("no matching ReceiveData overload")
            sender = c.c_uint64()
            received = c.c_uint64()
            _support.call("cna_local_network_gamer_receive_data_into_packet_reader",
                          self._value, destination._value, c.byref(sender),
                          c.byref(received))
            return int(received.value), _sender(sender)
        offset = 0
        if len(args) == 2:
            offset = checked(args[1], "int32", "offset")
        elif len(args) != 1:
            raise TypeError("no matching ReceiveData overload")
        capacity = len(destination)
        if offset < 0 or offset > capacity:
            raise ValueError(f"offset {offset} is outside a {capacity}-byte array")
        buffer = (c.c_uint8 * capacity)() if capacity else None
        sender = c.c_uint64()
        received = c.c_uint64()
        route = ("cna_local_network_gamer_receive_data" if len(args) == 1
                 else "cna_local_network_gamer_receive_data_at")
        arguments = ([self._value, buffer, c.c_uint64(capacity)] if len(args) == 1
                     else [self._value, buffer, c.c_uint64(capacity),
                           c.c_int32(offset)])
        _support.call(route, *arguments, c.byref(sender), c.byref(received))
        count = int(received.value)
        for index in range(count):
            destination[offset + index if len(args) == 2 else index] = \
                int(buffer[offset + index if len(args) == 2 else index])
        return count, _sender(sender)


LocalNetworkGamer.__xna_arities__ = {"SendData": {2, 3, 4, 5}, "ReceiveData": {1, 2}}


def _network_gamer(value: object) -> NetworkGamer:
    if not isinstance(value, NetworkGamer):
        raise TypeError("recipient must be a NetworkGamer")
    return value


def _sender(handle: c.c_uint64) -> NetworkGamer | None:
    return NetworkGamer(int(handle.value), owned=False) if handle.value else None


class NetworkMachine:
    """The gamers one machine contributes to a session."""

    __slots__ = ("_handle", "_owned")

    def __init__(self, handle: int, *, owned: bool = False) -> None:
        self._handle = int(handle)
        self._owned = owned

    @property
    def _value(self) -> c.c_uint64:
        if not self._handle:
            raise RuntimeError("NetworkMachine has been disposed")
        return c.c_uint64(self._handle)

    def _release(self) -> None:
        if self._owned and self._handle:
            _support.call("cna_network_machine_destroy", c.c_uint64(self._handle))
        self._handle = 0

    @property
    def Gamers(self) -> tuple[NetworkGamer, ...]:
        count = _support.out_i32("cna_network_machine_get_gamer_count", self._value)
        return tuple(
            NetworkGamer(_support.out_handle("cna_network_machine_get_gamer",
                                             self._value, c.c_int32(index)),
                         owned=False)
            for index in range(count))

    def RemoveFromSession(self) -> None:
        _support.call("cna_network_machine_remove_from_session", self._value)


class AvailableNetworkSession:
    """One session discovery found."""

    __slots__ = ("_handle", "_owned")

    def __init__(self, handle: int, *, owned: bool = False) -> None:
        self._handle = int(handle)
        self._owned = owned

    @property
    def _value(self) -> c.c_uint64:
        if not self._handle:
            raise RuntimeError("AvailableNetworkSession has been disposed")
        return c.c_uint64(self._handle)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AvailableNetworkSession):
            return NotImplemented
        return _support.out_bool("cna_available_network_session_equals",
                                 self._value, other._value)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, AvailableNetworkSession):
            return NotImplemented
        return _support.out_bool("cna_available_network_session_not_equals",
                                 self._value, other._value)

    def __hash__(self) -> int:
        return hash(self._handle)

    @property
    def HostGamertag(self) -> str:
        return _support.sized_text(
            "cna_available_network_session_get_host_gamertag_size",
            "cna_available_network_session_copy_host_gamertag",
            (self._value,), "HostGamertag")

    @property
    def CurrentGamerCount(self) -> int:
        return _support.out_i32(
            "cna_available_network_session_get_current_gamer_count", self._value)

    @property
    def OpenPublicGamerSlots(self) -> int:
        return _support.out_i32(
            "cna_available_network_session_get_open_public_gamer_slots", self._value)

    @property
    def OpenPrivateGamerSlots(self) -> int:
        return _support.out_i32(
            "cna_available_network_session_get_open_private_gamer_slots", self._value)

    @property
    def SessionProperties(self) -> NetworkSessionProperties:
        return NetworkSessionProperties(handle=_support.out_handle(
            "cna_available_network_session_copy_session_properties", self._value),
            owned=False)

    def _connect_address(self) -> str:
        """Where CNA would connect for this session. Not XNA surface, but CNA's."""
        return _support.sized_text(
            "cna_available_network_session_get_connect_address_size_ext",
            "cna_available_network_session_copy_connect_address_ext",
            (self._value,), "connect address")

    def _connect_port(self) -> int:
        return _support.out_u16("cna_available_network_session_get_connect_port_ext",
                                self._value)

    def _session_type(self) -> NetworkSessionType:
        return NetworkSessionType(_support.out_u32(
            "cna_available_network_session_get_session_type_ext", self._value))

    def _release(self) -> None:
        if self._owned and self._handle:
            _support.call("cna_available_network_session_destroy",
                          c.c_uint64(self._handle))
        self._handle = 0

    @property
    def QualityOfService(self) -> QualityOfService:
        return QualityOfService(_support.out_struct(
            _online.CNA_QualityOfService, _VERSION,
            "cna_available_network_session_get_quality_of_service", self._value))


class _ReadOnlySessionCollection:
    """``Count`` comes from ``ReadOnlyCollection<T>``, which XNA inherits it from."""

    __slots__ = ("_handle", "_disposed")

    @property
    def Count(self) -> int:
        return _support.out_i32("cna_available_network_session_collection_get_count",
                                self._value)

    def __len__(self) -> int:
        return self.Count


class AvailableNetworkSessionCollection(_ReadOnlySessionCollection):
    """What ``NetworkSession.Find`` returns."""

    __slots__ = ()

    def __init__(self, handle: int) -> None:
        self._handle = int(handle)
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("AvailableNetworkSessionCollection has been disposed")
        return c.c_uint64(self._handle)

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call("cna_available_network_session_collection_dispose",
                          c.c_uint64(self._handle))
            _support.call("cna_available_network_session_collection_destroy",
                          c.c_uint64(self._handle))
        self._handle = 0

    def __getitem__(self, index: int) -> AvailableNetworkSession:
        count = self.Count
        position = checked(index, "int32", "index")
        if not 0 <= position < count:
            raise IndexError(f"index {position} is outside 0..{count - 1}")
        return AvailableNetworkSession(_support.out_handle(
            "cna_available_network_session_collection_copy_session", self._value,
            c.c_int32(position)), owned=False)

    def __iter__(self):
        for index in range(self.Count):
            yield self[index]

    def __enter__(self):
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()


class _SessionGamerCollection(GamerCollectionOfT):  # noqa: D101 - see below
    """One of a session's four rosters, read through its own identity."""

    __slots__ = ("_session", "_roster")

    def __init__(self, session: "NetworkSession", roster: int, factory) -> None:
        super().__init__(0, factory)
        self._session = session
        self._roster = roster

    def __len__(self) -> int:
        return _support.out_i32("cna_network_session_get_gamer_count",
                                self._session._value, c.c_uint32(self._roster))

    def __getitem__(self, index: int):
        count = len(self)
        position = checked(index, "int32", "index")
        if not 0 <= position < count:
            raise IndexError(f"index {position} is outside 0..{count - 1}")
        return self._factory(_support.out_handle(
            "cna_network_session_get_gamer", self._session._value,
            c.c_uint32(self._roster), c.c_int32(position)))

    def __contains__(self, gamer: object) -> bool:
        return any(entry.Id == gamer.Id for entry in self) \
            if isinstance(gamer, NetworkGamer) else False

    def IndexOf(self, gamer) -> int:
        for index, entry in enumerate(self):
            if entry.Id == gamer.Id:
                return index
        return -1

    def GetEnumerator(self):
        return iter(list(self))

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]

    def CopyTo(self, array, index: int) -> None:
        position = checked(index, "int32", "index")
        for offset, gamer in enumerate(self):
            array[position + offset] = gamer


class NetworkSession(metaclass=staticpropertymeta):
    """A multiplayer session."""

    __slots__ = ("_handle", "_owned", "_disposed", "_callbacks",
                 "_registrations", "__weakref__")

    #: XNA's two published limits, from the pinned contract.
    MaxSupportedGamers = 31
    MaxPreviousGamers = 100

    SessionEnded = Event()
    GamerJoined = Event()
    GamerLeft = Event()
    GameStarted = Event()
    GameEnded = Event()
    HostChanged = Event()
    WriteArbitratedLeaderboard = Event()
    WriteTrueSkill = Event()
    WriteUnarbitratedLeaderboard = Event()
    #: The one static event: an invite accepted outside any one session.
    InviteAccepted = Event(static=True)

    def __init__(self, handle: int, *, owned: bool = True) -> None:
        self._handle = int(handle)
        self._owned = owned
        self._disposed = False
        self._callbacks = CallbackRoot()
        self._registrations: list[int] = []
        if owned:
            self._subscribe_all()

    @classmethod
    def _adopt(cls, handle: int, *, owned: bool) -> "NetworkSession":
        session = cls.__new__(cls)
        session._handle = int(handle)
        session._owned = owned
        session._disposed = False
        session._callbacks = CallbackRoot()
        session._registrations = []
        return session

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("NetworkSession has been disposed")
        return c.c_uint64(self._handle)

    # -- events -------------------------------------------------------------

    def _subscribe_all(self) -> None:
        """Roots one native subscription per event and fans it out in Python.

        One native source, one Python fan-out: a second handler added to
        ``GamerJoined`` does not add a second native subscription, which is what
        keeps the delivery order the event's rather than the registration's.
        """
        self._subscribe("cna_network_session_subscribe_gamer_joined",
                        _online.CNA_GamerJoinedCallback, "GamerJoined",
                        lambda info: GamerJoinedEventArgs(
                            NetworkGamer(int(info.gamer), owned=False)))
        self._subscribe("cna_network_session_subscribe_gamer_left",
                        _online.CNA_GamerLeftCallback, "GamerLeft",
                        lambda info: GamerLeftEventArgs(
                            NetworkGamer(int(info.gamer), owned=False)))
        self._subscribe("cna_network_session_subscribe_game_started",
                        _online.CNA_GameStartedCallback, "GameStarted",
                        lambda info: GameStartedEventArgs())
        self._subscribe("cna_network_session_subscribe_game_ended",
                        _online.CNA_GameEndedCallback, "GameEnded",
                        lambda info: GameEndedEventArgs())
        self._subscribe("cna_network_session_subscribe_host_changed",
                        _online.CNA_HostChangedCallback, "HostChanged",
                        lambda info: HostChangedEventArgs(
                            NetworkGamer(int(info.old_host), owned=False)
                            if info.old_host else None,
                            NetworkGamer(int(info.new_host), owned=False)
                            if info.new_host else None))
        self._subscribe("cna_network_session_subscribe_session_ended",
                        _online.CNA_NetworkSessionEndedCallback, "SessionEnded",
                        lambda info: NetworkSessionEndedEventArgs(
                            NetworkSessionEndReason(int(info.end_reason))))
        for route, name in (
                ("cna_network_session_subscribe_write_arbitrated_leaderboard",
                 "WriteArbitratedLeaderboard"),
                ("cna_network_session_subscribe_write_true_skill", "WriteTrueSkill"),
                ("cna_network_session_subscribe_write_unarbitrated_leaderboard",
                 "WriteUnarbitratedLeaderboard")):
            self._subscribe(route, _online.CNA_WriteLeaderboardsCallback, name,
                            lambda info: WriteLeaderboardsEventArgs(
                                NetworkGamer(int(info.gamer), owned=False)
                                if info.gamer else None, bool(info.is_leaving)))

    def _subscribe(self, route: str, factory: type, event: str, build) -> None:
        def adapt(_session, pointer, _context) -> None:
            getattr(type(self), event)._handlers_for(self)
            arguments = build(pointer.contents)
            for handler in list(getattr(type(self), event)._handlers_for(self)):
                handler(self, arguments)

        trampoline = self._callbacks.root(event, factory, adapt)
        self._registrations.append(_support.out_handle(
            route, self._value, trampoline, None))

    # -- creation -----------------------------------------------------------

    @staticmethod
    def _local_gamer_handles(localGamers) -> tuple[object, int]:
        values = []
        for gamer in localGamers:
            if not isinstance(gamer, SignedInGamer):
                raise TypeError("every entry of localGamers must be a SignedInGamer")
            values.append(gamer._value.value)
        if not values:
            raise ValueError("a session needs at least one local gamer")
        return (c.c_uint64 * len(values))(*values), len(values)

    @staticmethod
    def Create(*args: object) -> "NetworkSession":
        """XNA's three ``Create`` overloads."""
        if len(args) == 3 and isinstance(args[1], int):
            sessionType, maxLocalGamers, maxGamers = args
            return NetworkSession(_support.out_handle(
                "cna_network_session_create",
                c.c_uint32(int(NetworkSessionType(sessionType))),
                c.c_int32(checked(maxLocalGamers, "int32", "maxLocalGamers")),
                c.c_int32(checked(maxGamers, "int32", "maxGamers"))))
        if len(args) == 5 and isinstance(args[1], int):
            (sessionType, maxLocalGamers, maxGamers, privateGamerSlots,
             sessionProperties) = args
            return NetworkSession(_support.out_handle(
                "cna_network_session_create_with_properties",
                c.c_uint32(int(NetworkSessionType(sessionType))),
                c.c_int32(checked(maxLocalGamers, "int32", "maxLocalGamers")),
                c.c_int32(checked(maxGamers, "int32", "maxGamers")),
                c.c_int32(checked(privateGamerSlots, "int32", "privateGamerSlots")),
                _properties(sessionProperties)))
        if len(args) == 5:
            (sessionType, localGamers, maxGamers, privateGamerSlots,
             sessionProperties) = args
            array, count = NetworkSession._local_gamer_handles(localGamers)
            return NetworkSession(_support.out_handle(
                "cna_network_session_create_with_local_gamers",
                c.c_uint32(int(NetworkSessionType(sessionType))), array,
                c.c_uint64(count),
                c.c_int32(checked(maxGamers, "int32", "maxGamers")),
                c.c_int32(checked(privateGamerSlots, "int32", "privateGamerSlots")),
                _properties(sessionProperties)))
        raise TypeError("no matching Create overload")

    @staticmethod
    def _create_async(*args: object) -> "NetworkSession":
        """CNA's asynchronous create, whose three shapes mirror ``Create``."""
        if len(args) == 3 and isinstance(args[1], int):
            sessionType, maxLocalGamers, maxGamers = args
            return NetworkSession(_support.out_handle(
                "cna_network_session_create_async",
                c.c_uint32(int(NetworkSessionType(sessionType))),
                c.c_int32(checked(maxLocalGamers, "int32", "maxLocalGamers")),
                c.c_int32(checked(maxGamers, "int32", "maxGamers")),
                _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))
        if len(args) == 5 and isinstance(args[1], int):
            (sessionType, maxLocalGamers, maxGamers, privateGamerSlots,
             sessionProperties) = args
            return NetworkSession(_support.out_handle(
                "cna_network_session_create_with_properties_async",
                c.c_uint32(int(NetworkSessionType(sessionType))),
                c.c_int32(checked(maxLocalGamers, "int32", "maxLocalGamers")),
                c.c_int32(checked(maxGamers, "int32", "maxGamers")),
                c.c_int32(checked(privateGamerSlots, "int32", "privateGamerSlots")),
                _properties(sessionProperties),
                _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))
        if len(args) == 5:
            (sessionType, localGamers, maxGamers, privateGamerSlots,
             sessionProperties) = args
            array, count = NetworkSession._local_gamer_handles(localGamers)
            return NetworkSession(_support.out_handle(
                "cna_network_session_create_with_local_gamers_async",
                c.c_uint32(int(NetworkSessionType(sessionType))), array,
                c.c_uint64(count),
                c.c_int32(checked(maxGamers, "int32", "maxGamers")),
                c.c_int32(checked(privateGamerSlots, "int32", "privateGamerSlots")),
                _properties(sessionProperties),
                _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))
        raise TypeError("no matching BeginCreate overload")

    @staticmethod
    def BeginCreate(*args: object) -> object:
        callback, state = args[-2], args[-1]
        return _GamerAsyncResult.begin(
            "CreateSession", state, callback,
            lambda: NetworkSession._create_async(*args[:-2]))

    @staticmethod
    def EndCreate(result: object) -> "NetworkSession":
        return _GamerAsyncResult.end(result, "CreateSession")

    @staticmethod
    def Find(*args: object) -> AvailableNetworkSessionCollection:
        """XNA's two ``Find`` overloads."""
        if len(args) != 3:
            raise TypeError("no matching Find overload")
        sessionType, second, searchProperties = args
        if isinstance(second, int):
            return AvailableNetworkSessionCollection(_support.out_handle(
                "cna_network_session_find",
                c.c_uint32(int(NetworkSessionType(sessionType))),
                c.c_int32(checked(second, "int32", "maxLocalGamers")),
                _properties(searchProperties)))
        array, count = NetworkSession._local_gamer_handles(second)
        return AvailableNetworkSessionCollection(_support.out_handle(
            "cna_network_session_find_with_local_gamers",
            c.c_uint32(int(NetworkSessionType(sessionType))), array,
            c.c_uint64(count), _properties(searchProperties)))

    @staticmethod
    def _find_async(sessionType, second, searchProperties):
        if isinstance(second, int):
            return AvailableNetworkSessionCollection(_support.out_handle(
                "cna_network_session_find_async",
                c.c_uint32(int(NetworkSessionType(sessionType))),
                c.c_int32(checked(second, "int32", "maxLocalGamers")),
                _properties(searchProperties),
                _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))
        array, count = NetworkSession._local_gamer_handles(second)
        return AvailableNetworkSessionCollection(_support.out_handle(
            "cna_network_session_find_with_local_gamers_async",
            c.c_uint32(int(NetworkSessionType(sessionType))), array,
            c.c_uint64(count), _properties(searchProperties),
            _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))

    @staticmethod
    def BeginFind(*args: object) -> object:
        callback, state = args[-2], args[-1]
        return _GamerAsyncResult.begin(
            "FindSessions", state, callback,
            lambda: NetworkSession._find_async(*args[:-2]))

    @staticmethod
    def EndFind(result: object) -> AvailableNetworkSessionCollection:
        return _GamerAsyncResult.end(result, "FindSessions")

    @staticmethod
    def Join(availableSession: AvailableNetworkSession) -> "NetworkSession":
        if not isinstance(availableSession, AvailableNetworkSession):
            raise TypeError("availableSession must be an AvailableNetworkSession")
        try:
            return NetworkSession(_support.out_handle(
                "cna_network_session_join", availableSession._value))
        except RuntimeError as error:
            reason = _last_join_error()
            if reason is None:
                raise
            raise NetworkSessionJoinException(str(error), reason) from None

    @staticmethod
    def BeginJoin(availableSession: AvailableNetworkSession, callback: object,
                  asyncState: object) -> object:
        return _GamerAsyncResult.begin(
            "JoinSession", asyncState, callback,
            lambda: NetworkSession(_support.out_handle(
                "cna_network_session_join_async", availableSession._value,
                _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None)))

    @staticmethod
    def EndJoin(result: object) -> "NetworkSession":
        return _GamerAsyncResult.end(result, "JoinSession")

    @staticmethod
    def JoinInvited(localGamers: object) -> "NetworkSession":
        """XNA's two ``JoinInvited`` overloads: a count, or the gamers."""
        if isinstance(localGamers, int):
            return NetworkSession(_support.out_handle(
                "cna_network_session_join_invited",
                c.c_int32(checked(localGamers, "int32", "maxLocalGamers"))))
        array, count = NetworkSession._local_gamer_handles(localGamers)
        return NetworkSession(_support.out_handle(
            "cna_network_session_join_invited_with_local_gamers", array,
            c.c_uint64(count)))

    @staticmethod
    def _join_invited_async(localGamers: object) -> "NetworkSession":
        if isinstance(localGamers, int):
            return NetworkSession(_support.out_handle(
                "cna_network_session_join_invited_async",
                c.c_int32(checked(localGamers, "int32", "maxLocalGamers")),
                _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))
        array, count = NetworkSession._local_gamer_handles(localGamers)
        return NetworkSession(_support.out_handle(
            "cna_network_session_join_invited_with_local_gamers_async", array,
            c.c_uint64(count),
            _on.no_callback(_online.CNA_NetworkSessionAsyncCallback), None))

    @staticmethod
    def BeginJoinInvited(localGamers: object, callback: object,
                         asyncState: object) -> object:
        return _GamerAsyncResult.begin(
            "JoinInvited", asyncState, callback,
            lambda: NetworkSession._join_invited_async(localGamers))

    @staticmethod
    def EndJoinInvited(result: object) -> "NetworkSession":
        return _GamerAsyncResult.end(result, "JoinInvited")

    # -- lifetime -----------------------------------------------------------

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self) -> None:
        """Ends the session.

        Every native subscription is released first, so no event can arrive
        after the object that would dispatch it is gone.
        """
        if self._disposed:
            return
        for registration in self._registrations:
            _support.call("cna_network_session_unsubscribe", c.c_uint64(registration))
        self._registrations.clear()
        self._callbacks.clear()
        self._disposed = True
        if self._owned and self._handle:
            # CNA's dispose *is* the end of the object: ``cna_network_session_destroy``
            # afterwards answers INVALID_STATE, and the qualification asserts
            # that rather than calling both and hoping. A session that was never
            # disposed is destroyed instead, which is the other half of the pair.
            _support.call("cna_network_session_dispose", c.c_uint64(self._handle))
        self._handle = 0

    def _destroy_without_dispose(self) -> None:
        """Releases a session's handle without disposing the session first.

        The other half of CNA's pair. ``Dispose`` ends the session and the
        handle with it; this is for a handle whose session was never started --
        the case a discovery result that nothing joined leaves behind.
        """
        if self._disposed or not self._handle:
            return
        self._disposed = True
        _support.call("cna_network_session_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self):
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()

    # -- state --------------------------------------------------------------

    def Update(self) -> None:
        _support.call("cna_network_session_update", self._value)

    def StartGame(self) -> None:
        _support.call("cna_network_session_start_game", self._value)

    def EndGame(self) -> None:
        _support.call("cna_network_session_end_game", self._value)

    def ResetReady(self) -> None:
        _support.call("cna_network_session_reset_ready", self._value)

    def _replace_session_properties(self, properties: NetworkSessionProperties) -> None:
        """Swaps the whole advertised property list for another.

        XNA has no public setter for ``SessionProperties`` -- a title mutates the
        list it already has -- so this is CNA's route without a public name.
        """
        _support.call("cna_network_session_replace_session_properties", self._value,
                      _properties(properties))

    def AddLocalGamer(self, gamer: SignedInGamer) -> None:
        if not isinstance(gamer, SignedInGamer):
            raise TypeError("gamer must be a SignedInGamer")
        _support.call("cna_network_session_add_local_gamer", self._value,
                      gamer._value)

    def FindGamerById(self, gamerId: int) -> NetworkGamer | None:
        handle = _support.out_handle("cna_network_session_find_gamer_by_id",
                                     self._value,
                                     c.c_uint8(checked(gamerId, "uint8", "gamerId")))
        return NetworkGamer(handle, owned=False) if handle else None

    @property
    def SessionType(self) -> NetworkSessionType:
        return NetworkSessionType(_support.out_u32(
            "cna_network_session_get_session_type", self._value))

    @property
    def SessionState(self) -> NetworkSessionState:
        return NetworkSessionState(_support.out_u32(
            "cna_network_session_get_session_state", self._value))

    @property
    def IsHost(self) -> bool:
        return _support.out_bool("cna_network_session_get_is_host", self._value)

    @property
    def Host(self) -> NetworkGamer | None:
        handle = _support.out_handle("cna_network_session_get_host", self._value)
        return NetworkGamer(handle, owned=False) if handle else None

    @property
    def AllGamers(self) -> GamerCollectionOfT:
        return _SessionGamerCollection(
            self, _ROSTER_ALL, lambda value: NetworkGamer(value, owned=False))

    @property
    def LocalGamers(self) -> GamerCollectionOfT:
        return _SessionGamerCollection(
            self, _ROSTER_LOCAL, lambda value: LocalNetworkGamer(value, owned=False))

    @property
    def RemoteGamers(self) -> GamerCollectionOfT:
        return _SessionGamerCollection(
            self, _ROSTER_REMOTE, lambda value: NetworkGamer(value, owned=False))

    @property
    def PreviousGamers(self) -> GamerCollectionOfT:
        return _SessionGamerCollection(
            self, _ROSTER_PREVIOUS, lambda value: NetworkGamer(value, owned=False))

    @property
    def IsEveryoneReady(self) -> bool:
        return _support.out_bool("cna_network_session_get_is_everyone_ready",
                                 self._value)

    @property
    def MaxGamers(self) -> int:
        return _support.out_i32("cna_network_session_get_max_gamers", self._value)

    @MaxGamers.setter
    def MaxGamers(self, value: int) -> None:
        _support.call("cna_network_session_set_max_gamers", self._value,
                      c.c_int32(checked(value, "int32", "MaxGamers")))

    @property
    def PrivateGamerSlots(self) -> int:
        return _support.out_i32("cna_network_session_get_private_gamer_slots",
                                self._value)

    @PrivateGamerSlots.setter
    def PrivateGamerSlots(self, value: int) -> None:
        _support.call("cna_network_session_set_private_gamer_slots", self._value,
                      c.c_int32(checked(value, "int32", "PrivateGamerSlots")))

    @property
    def SimulatedPacketLoss(self) -> float:
        return _support.out_f32("cna_network_session_get_simulated_packet_loss",
                                self._value)

    @SimulatedPacketLoss.setter
    def SimulatedPacketLoss(self, value: float) -> None:
        _support.call("cna_network_session_set_simulated_packet_loss", self._value,
                      c.c_float(float(value)))

    @property
    def SimulatedLatency(self) -> timedelta:
        return _timespan(_support.out_i64(
            "cna_network_session_get_simulated_latency_ticks", self._value))

    @SimulatedLatency.setter
    def SimulatedLatency(self, value: timedelta) -> None:
        _support.call("cna_network_session_set_simulated_latency_ticks", self._value,
                      c.c_int64(_ticks(value, "SimulatedLatency")))

    @property
    def BytesPerSecondSent(self) -> int:
        return _support.out_i32("cna_network_session_get_bytes_per_second_sent",
                                self._value)

    @property
    def BytesPerSecondReceived(self) -> int:
        return _support.out_i32("cna_network_session_get_bytes_per_second_received",
                                self._value)

    @property
    def SessionProperties(self) -> NetworkSessionProperties:
        return NetworkSessionProperties(handle=_support.out_handle(
            "cna_network_session_copy_session_properties", self._value), owned=False)

    @property
    def AllowJoinInProgress(self) -> bool:
        return _support.out_bool("cna_network_session_get_allow_join_in_progress",
                                 self._value)

    @AllowJoinInProgress.setter
    def AllowJoinInProgress(self, value: bool) -> None:
        _support.call("cna_network_session_set_allow_join_in_progress", self._value,
                      c.c_uint8(1 if value else 0))

    @property
    def AllowHostMigration(self) -> bool:
        return _support.out_bool("cna_network_session_get_allow_host_migration",
                                 self._value)

    @AllowHostMigration.setter
    def AllowHostMigration(self, value: bool) -> None:
        _support.call("cna_network_session_set_allow_host_migration", self._value,
                      c.c_uint8(1 if value else 0))


def _properties(value: object) -> c.c_uint64:
    if value is None:
        return c.c_uint64(0)
    if not isinstance(value, NetworkSessionProperties):
        raise TypeError("sessionProperties must be a NetworkSessionProperties")
    return value._value


NetworkSession.__xna_arities__ = {
    "Create": {3, 5}, "BeginCreate": {5, 7}, "Find": {3}, "BeginFind": {5},
    "JoinInvited": {1}, "BeginJoinInvited": {3},
}
