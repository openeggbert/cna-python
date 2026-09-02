"""The Net profile's enumerations, values and event payloads.

Part of the ``xna40-windows-online`` strict profile, measured against
`Microsoft.Xna.Framework.Net.dll`. Every enum value is XNA's; nothing here
chooses one.
"""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from enum import IntEnum, IntFlag
from typing import Iterator

from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import checked

from ..GamerServices._errors import NetworkException as _NetworkException

__all__ = [
    "SendDataOptions", "NetworkSessionType", "NetworkSessionState",
    "NetworkSessionEndReason", "NetworkSessionJoinError", "QualityOfService",
    "NetworkSessionProperties", "NetworkSessionJoinException",
    "GameStartedEventArgs", "GameEndedEventArgs", "GamerJoinedEventArgs",
    "GamerLeftEventArgs", "HostChangedEventArgs", "NetworkSessionEndedEventArgs",
    "WriteLeaderboardsEventArgs",
]

_support = _on.support
_VERSION = 1
_TICKS_PER_MICROSECOND = 10


def _timespan(ticks: int) -> timedelta:
    return timedelta(microseconds=int(ticks) // _TICKS_PER_MICROSECOND)


class SendDataOptions(IntFlag):
    """How a packet is delivered.

    A flag set, because XNA declares it with ``FlagsAttribute`` and the
    reference metadata says so: ``ReliableInOrder`` really is
    ``Reliable | InOrder``.
    """

    None_ = 0
    Reliable = 1
    InOrder = 2
    ReliableInOrder = 3
    Chat = 4


class NetworkSessionType(IntEnum):
    """What kind of session this is."""

    Local = 0
    SystemLink = 1
    PlayerMatch = 2
    Ranked = 3
    LocalWithLeaderboards = 4


class NetworkSessionState(IntEnum):
    """Where a session is in its lifetime."""

    Lobby = 0
    Playing = 1
    Ended = 2


class NetworkSessionEndReason(IntEnum):
    """Why a session ended."""

    ClientSignedOut = 0
    HostEndedSession = 1
    RemovedByHost = 2
    Disconnected = 3


class NetworkSessionJoinError(IntEnum):
    """Why a join failed."""

    SessionNotFound = 0
    SessionNotJoinable = 1
    SessionFull = 2


class NetworkSessionJoinException(_NetworkException):
    """A join failed, with the reason CNA gave for it."""

    def __init__(self, *args: object) -> None:
        self._join_error = NetworkSessionJoinError.SessionNotFound
        if not args:
            super().__init__()
        elif len(args) == 1 and isinstance(args[0], str):
            super().__init__(args[0])
        elif (len(args) == 2 and isinstance(args[0], str)
              and isinstance(args[1], NetworkSessionJoinError)):
            super().__init__(args[0])
            self._join_error = args[1]
        elif (len(args) == 2 and isinstance(args[0], str)
              and isinstance(args[1], BaseException)):
            super().__init__(args[0])
            self.__cause__ = args[1]
        else:
            raise TypeError(
                "NetworkSessionJoinException expects (), message, "
                "message and joinError, or message and innerException")

    @property
    def JoinError(self) -> NetworkSessionJoinError:
        return self._join_error

    @JoinError.setter
    def JoinError(self, value: NetworkSessionJoinError) -> None:
        self._join_error = NetworkSessionJoinError(value)


    def GetObjectData(self, info: object, context: object) -> None:
        """XNA's ``ISerializable`` hook, which .NET calls when serializing.

        Nothing in this projection serializes an exception, and Python has no
        ``SerializationInfo``; the two parameters are mapped to ``object`` by
        the language rules and are accepted and ignored, which is what the
        method has to do to exist at all here.
        """
        if info is None:
            raise ValueError("info must not be None")


NetworkSessionJoinException.__xna_arities__ = {"__init__": {0, 1, 2},
                                               "GetObjectData": {2}}


class QualityOfService:
    """What discovery measured about a session's connection.

    ``IsAvailable`` says whether the measurement happened at all. When it did
    not, the four numbers are still readable and are what CNA reports for an
    unmeasured session -- a caller checks ``IsAvailable`` rather than reading a
    zero as a real latency.
    """

    __slots__ = ("_native",)

    def __init__(self, native=None) -> None:
        self._native = native if native is not None else _support.out_struct(
            _online.CNA_QualityOfService, _VERSION, "cna_quality_of_service_init")

    @staticmethod
    def _measured(roundtrip: timedelta) -> "QualityOfService":
        microseconds = (roundtrip.days * 86_400_000_000
                        + roundtrip.seconds * 1_000_000 + roundtrip.microseconds)
        return QualityOfService(_support.out_struct(
            _online.CNA_QualityOfService, _VERSION,
            "cna_quality_of_service_init_measured",
            c.c_int64(microseconds * _TICKS_PER_MICROSECOND)))

    @property
    def IsAvailable(self) -> bool:
        return bool(self._native.is_available)

    @property
    def BytesPerSecondUpstream(self) -> int:
        return int(self._native.bytes_per_second_upstream)

    @property
    def BytesPerSecondDownstream(self) -> int:
        return int(self._native.bytes_per_second_downstream)

    @property
    def AverageRoundtripTime(self) -> timedelta:
        return _timespan(self._native.average_roundtrip_ticks)

    @property
    def MinimumRoundtripTime(self) -> timedelta:
        return _timespan(self._native.minimum_roundtrip_ticks)


class NetworkSessionProperties:
    """The searchable property list a session advertises.

    Every slot is ``int | None``: XNA's element type is ``Nullable<int>``, and
    a slot nobody set is genuinely absent rather than zero. Discovery matches on
    the slots that are set and ignores the rest, so the difference matters.
    """

    __slots__ = ("_handle", "_owned")

    #: XNA's constructor takes nothing. ``handle`` and ``owned`` are keyword-only
    #: and private: they exist so a session can hand back the properties it
    #: already owns, and a caller writing ``NetworkSessionProperties()`` sees
    #: exactly the zero-argument constructor XNA declares.
    def __init__(self, *, handle: int | None = None, owned: bool = True) -> None:
        if handle is None:
            handle = _support.out_handle("cna_network_session_properties_create")
        self._handle = int(handle)
        self._owned = owned

    @property
    def _value(self) -> c.c_uint64:
        if not self._handle:
            raise RuntimeError("NetworkSessionProperties has been disposed")
        return c.c_uint64(self._handle)

    @property
    def Count(self) -> int:
        return _support.out_i32("cna_network_session_properties_get_count",
                                self._value)

    def __len__(self) -> int:
        return self.Count

    @property
    def _is_read_only(self) -> bool:
        return _support.out_bool("cna_network_session_properties_get_is_read_only",
                                 self._value)

    def _optional(self, index: int):
        value = _online.CNA_OptionalInt32()
        _support.call("cna_network_session_properties_get_item", self._value,
                      c.c_int32(checked(index, "int32", "index")), c.byref(value))
        return int(value.value) if value.has_value else None

    def __getitem__(self, index: int) -> int | None:
        count = self.Count
        position = checked(index, "int32", "index")
        if not 0 <= position < count:
            raise IndexError(f"index {position} is outside 0..{count - 1}")
        return self._optional(position)

    def __setitem__(self, index: int, value: int | None) -> None:
        # XNA's list has a fixed size and every slot exists from the start;
        # CNA's starts empty and grows. Assigning slot N therefore creates the
        # slots up to it, so XNA code that writes ``properties[0] = 5`` means
        # what it meant. The divergence is recorded rather than smoothed over:
        # ``Count`` still reports what CNA holds.
        position = checked(index, "int32", "index")
        while self.Count <= position:
            self._append(None)
        native = _online.CNA_OptionalInt32()
        if value is None:
            native.has_value = 0
            native.value = 0
        else:
            native.has_value = 1
            native.value = checked(value, "int32", "value")
        _support.call("cna_network_session_properties_set_item", self._value,
                      c.c_int32(checked(index, "int32", "index")), native)

    def _append(self, value: int | None) -> None:
        native = _online.CNA_OptionalInt32()
        native.has_value = 0 if value is None else 1
        native.value = 0 if value is None else checked(value, "int32", "value")
        _support.call("cna_network_session_properties_add", self._value, native)

    def _add(self, value: int | None) -> None:
        self._append(value)

    def _insert(self, index: int, value: int | None) -> None:
        native = _online.CNA_OptionalInt32()
        native.has_value = 0 if value is None else 1
        native.value = 0 if value is None else checked(value, "int32", "value")
        _support.call("cna_network_session_properties_insert", self._value,
                      c.c_int32(checked(index, "int32", "index")), native)

    def _removeat(self, index: int) -> None:
        _support.call("cna_network_session_properties_remove_at", self._value,
                      c.c_int32(checked(index, "int32", "index")))

    def _remove(self, value: int | None) -> bool:
        native = _online.CNA_OptionalInt32()
        native.has_value = 0 if value is None else 1
        native.value = 0 if value is None else checked(value, "int32", "value")
        return _support.out_bool("cna_network_session_properties_remove",
                                 self._value, native)

    def _clear(self) -> None:
        _support.call("cna_network_session_properties_clear", self._value)

    def _contains(self, value: int | None) -> bool:
        native = _online.CNA_OptionalInt32()
        native.has_value = 0 if value is None else 1
        native.value = 0 if value is None else checked(value, "int32", "value")
        return _support.out_bool("cna_network_session_properties_contains",
                                 self._value, native)

    def __contains__(self, value: object) -> bool:
        return self._contains(value if value is None else int(value))

    def _indexof(self, value: int | None) -> int:
        native = _online.CNA_OptionalInt32()
        native.has_value = 0 if value is None else 1
        native.value = 0 if value is None else checked(value, "int32", "value")
        return _support.out_i32("cna_network_session_properties_index_of",
                                self._value, native)

    def _copyto(self, array, index: int) -> None:
        count = self.Count
        position = checked(index, "int32", "index")
        destination = (_online.CNA_OptionalInt32 * count)() if count else None
        written = c.c_uint64()
        _support.call("cna_network_session_properties_copy_to", self._value,
                      destination, c.c_uint64(count), c.c_int32(0),
                      c.byref(written))
        for offset in range(int(written.value)):
            item = destination[offset]
            array[position + offset] = int(item.value) if item.has_value else None

    def GetEnumerator(self) -> Iterator[int | None]:
        return _NetworkSessionPropertyEnumerator(_support.out_handle(
            "cna_network_session_properties_create_enumerator", self._value))

    def __iter__(self) -> Iterator[int | None]:
        enumerator = self.GetEnumerator()
        try:
            while enumerator.MoveNext():
                yield enumerator.Current
        finally:
            enumerator.Dispose()


class _NetworkSessionPropertyEnumerator:
    """CNA's enumerator over a session's property list."""

    __slots__ = ("_handle", "_current", "_disposed")

    def __init__(self, handle: int) -> None:
        self._handle = int(handle)
        self._current: int | None = None
        self._disposed = False

    def MoveNext(self) -> bool:
        if self._disposed:
            raise RuntimeError("the enumerator has been disposed")
        if not _support.out_bool("cna_network_session_property_enumerator_move_next",
                                 c.c_uint64(self._handle)):
            return False
        value = _online.CNA_OptionalInt32()
        _support.call("cna_network_session_property_enumerator_get_current",
                      c.c_uint64(self._handle), c.byref(value))
        self._current = int(value.value) if value.has_value else None
        return True

    @property
    def Current(self) -> int | None:
        return self._current

    def Reset(self) -> None:
        _support.call("cna_network_session_property_enumerator_reset",
                      c.c_uint64(self._handle))
        self._current = None

    def Dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        _support.call("cna_network_session_property_enumerator_destroy",
                      c.c_uint64(self._handle))
        self._handle = 0

    def __iter__(self):
        return self

    def __next__(self):
        if not self.MoveNext():
            raise StopIteration
        return self.Current


class GameStartedEventArgs:
    """The payload of ``NetworkSession.GameStarted``."""

    __slots__ = ()

    def __init__(self) -> None:
        pass


class GameEndedEventArgs:
    """The payload of ``NetworkSession.GameEnded``."""

    __slots__ = ()

    def __init__(self) -> None:
        pass


class GamerJoinedEventArgs:
    """The payload of ``NetworkSession.GamerJoined``."""

    __slots__ = ("_gamer",)

    def __init__(self, gamer: object) -> None:
        self._gamer = gamer

    @property
    def Gamer(self):
        return self._gamer


class GamerLeftEventArgs:
    """The payload of ``NetworkSession.GamerLeft``."""

    __slots__ = ("_gamer",)

    def __init__(self, gamer: object) -> None:
        self._gamer = gamer

    @property
    def Gamer(self):
        return self._gamer


class HostChangedEventArgs:
    """The payload of ``NetworkSession.HostChanged``."""

    __slots__ = ("_old", "_new")

    def __init__(self, oldHost: object, newHost: object) -> None:
        self._old = oldHost
        self._new = newHost

    @property
    def OldHost(self):
        return self._old

    @property
    def NewHost(self):
        return self._new


class NetworkSessionEndedEventArgs:
    """The payload of ``NetworkSession.SessionEnded``."""

    __slots__ = ("_reason",)

    def __init__(self, endReason: NetworkSessionEndReason) -> None:
        self._reason = NetworkSessionEndReason(endReason)

    @property
    def EndReason(self) -> NetworkSessionEndReason:
        return self._reason


class WriteLeaderboardsEventArgs:
    """The payload of the three leaderboard-writing events."""

    __slots__ = ("_gamer", "_is_leaving")

    def __init__(self, gamer: object, isLeaving: bool) -> None:
        self._gamer = gamer
        self._is_leaving = bool(isLeaving)

    @property
    def Gamer(self):
        return self._gamer

    @property
    def IsLeaving(self) -> bool:
        return self._is_leaving
