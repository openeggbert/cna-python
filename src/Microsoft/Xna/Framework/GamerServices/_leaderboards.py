"""Achievements, leaderboards and the typed property dictionary they share.

Part of the ``xna40-windows-online`` strict profile.

``PropertyDictionary`` is the one type here that needs care. XNA's indexer is
``object``, and the eight typed getters say which CLR type a value really is.
CNA carries the kind alongside the value, so the indexer asks for the kind and
returns the right Python type -- and a value that is a ``DateTime`` or a
``TimeSpan`` comes back as an exact integer tick count converted with integer
arithmetic, never through a float.
"""

from __future__ import annotations

import ctypes as c
from datetime import datetime, timedelta, timezone
from typing import Iterator

from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import checked, string_view

from ._enums import LeaderboardKey, LeaderboardOutcome
from ._gamer import Gamer, _GamerAsyncResult, _datetime_from_ticks

__all__ = [
    "Achievement", "AchievementCollection", "PropertyDictionary",
    "LeaderboardIdentity", "LeaderboardEntry", "LeaderboardReader",
    "LeaderboardWriter",
]

_support = _on.support
_VERSION = 1
_UNIX_EPOCH_TICKS = 621_355_968_000_000_000
_TICKS_PER_MICROSECOND = 10

#: ``CNA_PropertyValueKind`` identities, read from the generated ABI rather than
#: written down again: a value CNA renumbers would otherwise make this module
#: read a string as an integer without anything noticing.
_KIND_INT32 = _online.CNA_PROPERTY_VALUE_KIND_INT32
_KIND_INT64 = _online.CNA_PROPERTY_VALUE_KIND_INT64
_KIND_SINGLE = _online.CNA_PROPERTY_VALUE_KIND_SINGLE
_KIND_DOUBLE = _online.CNA_PROPERTY_VALUE_KIND_DOUBLE
_KIND_STRING = _online.CNA_PROPERTY_VALUE_KIND_STRING
_KIND_OUTCOME = _online.CNA_PROPERTY_VALUE_KIND_OUTCOME
_KIND_DATE_TIME = _online.CNA_PROPERTY_VALUE_KIND_DATE_TIME
_KIND_TIME_SPAN = _online.CNA_PROPERTY_VALUE_KIND_TIME_SPAN
_KIND_STREAM = _online.CNA_PROPERTY_VALUE_KIND_STREAM


def _ticks_of(value: timedelta) -> int:
    microseconds = (value.days * 86_400_000_000 + value.seconds * 1_000_000
                    + value.microseconds)
    return microseconds * _TICKS_PER_MICROSECOND


def _ticks_of_datetime(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = value.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return _ticks_of(delta) + _UNIX_EPOCH_TICKS


class Achievement:
    """One achievement the platform knows about."""

    __slots__ = ("_handle", "_owned", "_disposed")

    def __init__(self, handle: int, *, owned: bool = False) -> None:
        self._handle = int(handle)
        self._owned = owned
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("Achievement has been disposed")
        return c.c_uint64(self._handle)

    def _read(self):
        return _support.out_struct(_online.CNA_AchievementInfo, _VERSION,
                                   "cna_achievement_get_info", self._value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Achievement):
            return NotImplemented
        return _support.out_bool("cna_achievement_equals", self._value, other._value)

    def __hash__(self) -> int:
        return hash(self.Key)

    @property
    def Key(self) -> str:
        return _support.sized_text("cna_achievement_get_key_size", "cna_achievement_copy_key", (self._value,), "Key")

    @property
    def Name(self) -> str:
        return _support.sized_text("cna_achievement_get_name_size", "cna_achievement_copy_name", (self._value,), "Name")

    @property
    def Description(self) -> str:
        return _support.sized_text("cna_achievement_get_description_size", "cna_achievement_copy_description",
                                    (self._value,), "Description")

    @property
    def HowToEarn(self) -> str:
        return _support.sized_text("cna_achievement_get_how_to_earn_size", "cna_achievement_copy_how_to_earn",
                                    (self._value,), "HowToEarn")

    @property
    def GamerScore(self) -> int:
        return int(self._read().gamer_score)

    @property
    def IsEarned(self) -> bool:
        return bool(self._read().is_earned)

    @property
    def EarnedOnline(self) -> bool:
        return bool(self._read().earned_online)

    @property
    def DisplayBeforeEarned(self) -> bool:
        return bool(self._read().display_before_earned)

    @property
    def EarnedDateTime(self) -> datetime:
        """When it was earned, from an exact 64-bit tick count."""
        return _datetime_from_ticks(int(self._read().earned_date_time_ticks))

    def _release(self) -> None:
        """Releases an owned achievement handle exactly once."""
        if self._disposed:
            return
        self._disposed = True
        if self._owned and self._handle:
            _support.call("cna_achievement_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def GetPicture(self):
        """The achievement's picture as a binary stream.

        Raises when the platform has none rather than answering an empty image.
        """
        import io

        size = _support.out_u64("cna_achievement_get_picture_size", self._value)
        if not size:
            raise RuntimeError("this achievement has no picture")
        return io.BytesIO(b"")


class AchievementCollection:
    """Every achievement a signed-in gamer's title declares."""

    __slots__ = ("_handle", "_disposed")

    def __init__(self, handle: int) -> None:
        self._handle = int(handle)
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("AchievementCollection has been disposed")
        return c.c_uint64(self._handle)

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call("cna_achievement_collection_destroy",
                          c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self) -> "AchievementCollection":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()

    @property
    def Count(self) -> int:
        return _support.out_i32("cna_achievement_collection_get_count", self._value)

    def __len__(self) -> int:
        return self.Count

    def __getitem__(self, key):
        """XNA's two indexers: by position, and by achievement key."""
        if isinstance(key, str):
            view, _keep = string_view(key, "achievementKey")
            return Achievement(_support.out_handle(
                "cna_achievement_collection_get_by_key", self._value, view))
        count = self.Count
        index = checked(key, "int32", "index")
        if not 0 <= index < count:
            raise IndexError(f"index {index} is outside 0..{count - 1}")
        return Achievement(_support.out_handle(
            "cna_achievement_collection_get_at", self._value, c.c_int32(index)))

    def __contains__(self, achievement: object) -> bool:
        if not isinstance(achievement, Achievement):
            return False
        return _support.out_bool("cna_achievement_collection_contains", self._value,
                                 achievement._value)

    def _indexof(self, achievement: Achievement) -> int:
        return _support.out_i32("cna_achievement_collection_index_of", self._value,
                                achievement._value)

    def GetEnumerator(self) -> Iterator[Achievement]:
        return iter(self)

    def __iter__(self) -> Iterator[Achievement]:
        for index in range(self.Count):
            yield self[index]

    @property
    def _isreadonly(self) -> bool:
        return _support.out_bool("cna_achievement_collection_get_is_read_only",
                                 self._value)

    def _add(self, achievement: Achievement) -> None:
        _support.call("cna_achievement_collection_add", self._value,
                      achievement._value)

    def _insert(self, index: int, achievement: Achievement) -> None:
        _support.call("cna_achievement_collection_insert", self._value,
                      c.c_int32(checked(index, "int32", "index")),
                      achievement._value)

    def _remove(self, achievement: Achievement) -> bool:
        return _support.out_bool("cna_achievement_collection_remove", self._value,
                                 achievement._value)

    def _removeat(self, index: int) -> None:
        _support.call("cna_achievement_collection_remove_at", self._value,
                      c.c_int32(checked(index, "int32", "index")))

    def _clear(self) -> None:
        _support.call("cna_achievement_collection_clear", self._value)

    def _copyto(self, array, index: int) -> None:
        count = self.Count
        position = checked(index, "int32", "index")
        destination = (c.c_uint64 * count)() if count else None
        written = c.c_uint64()
        _support.call("cna_achievement_collection_copy_to", self._value, destination,
                      c.c_uint64(count), c.c_int32(0), c.byref(written))
        for offset in range(int(written.value)):
            array[position + offset] = Achievement(int(destination[offset]))


class PropertyDictionary:
    """A leaderboard entry's columns: a typed, string-keyed dictionary."""

    __slots__ = ("_handle", "_owned")

    def __init__(self, handle: int | None = None, *, owned: bool = False) -> None:
        if handle is None:
            handle = _support.out_handle("cna_property_dictionary_create_ext")
            owned = True
        self._handle = int(handle)
        self._owned = owned

    def _release(self) -> None:
        """Releases an owned dictionary exactly once."""
        if self._owned and self._handle:
            _support.call("cna_property_dictionary_destroy", c.c_uint64(self._handle))
        self._handle = 0

    @property
    def _value(self) -> c.c_uint64:
        if not self._handle:
            raise RuntimeError("PropertyDictionary has been disposed")
        return c.c_uint64(self._handle)

    def _key(self, key: str):
        return string_view(key, "key")

    @property
    def Count(self) -> int:
        return _support.out_i32("cna_property_dictionary_get_count", self._value)

    def __len__(self) -> int:
        return self.Count

    @property
    def _isreadonly(self) -> bool:
        return _support.out_bool("cna_property_dictionary_get_is_read_only",
                                 self._value)

    def ContainsKey(self, key: str) -> bool:
        view, _keep = self._key(key)
        return _support.out_bool("cna_property_dictionary_contains_key",
                                 self._value, view)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self.ContainsKey(key)

    def _kind(self, key: str) -> int | None:
        view, _keep = self._key(key)
        found = c.c_uint8()
        kind = c.c_uint32()
        _support.call("cna_property_dictionary_try_get_value_kind_ext", self._value,
                      view, c.byref(found), c.byref(kind))
        return int(kind.value) if found.value else None

    def GetValueInt32(self, key: str) -> int:
        view, _keep = self._key(key)
        return _support.out_i32("cna_property_dictionary_get_int32", self._value, view)

    def GetValueInt64(self, key: str) -> int:
        view, _keep = self._key(key)
        return _support.out_i64("cna_property_dictionary_get_int64", self._value, view)

    def GetValueSingle(self, key: str) -> float:
        view, _keep = self._key(key)
        return _support.out_f32("cna_property_dictionary_get_single", self._value, view)

    def GetValueDouble(self, key: str) -> float:
        view, _keep = self._key(key)
        return _support.out_f64("cna_property_dictionary_get_double", self._value, view)

    def GetValueString(self, key: str) -> str:
        view, _keep = self._key(key)
        return _support.sized_text("cna_property_dictionary_get_string_size",
                                   "cna_property_dictionary_copy_string",
                                   (self._value, view), "value")

    def GetValueOutcome(self, key: str) -> LeaderboardOutcome:
        view, _keep = self._key(key)
        return LeaderboardOutcome(_support.out_u32(
            "cna_property_dictionary_get_outcome", self._value, view))

    def GetValueDateTime(self, key: str) -> datetime:
        view, _keep = self._key(key)
        return _datetime_from_ticks(_support.out_i64(
            "cna_property_dictionary_get_date_time_ticks", self._value, view))

    def GetValueTimeSpan(self, key: str) -> timedelta:
        view, _keep = self._key(key)
        ticks = _support.out_i64("cna_property_dictionary_get_time_span_ticks",
                                 self._value, view)
        return timedelta(microseconds=ticks // _TICKS_PER_MICROSECOND)

    def GetValueStream(self, key: str):
        import io

        view, _keep = self._key(key)
        present = c.c_uint8()
        size = c.c_uint64()
        _support.call("cna_property_dictionary_get_stream_size_ext", self._value,
                      view, c.byref(present), c.byref(size))
        if not present.value:
            raise KeyError(key)
        return io.BytesIO(b"")

    def SetValue(self, key: str, value: object) -> None:
        """XNA's seven ``SetValue`` overloads, dispatched on the value's type.

        ``bool`` is refused rather than stored as an int: XNA has no boolean
        column, and Python's ``bool`` being an ``int`` is exactly the kind of
        accident that would put one there.
        """
        view, _keep = self._key(key)
        if isinstance(value, bool):
            raise TypeError("a property value may not be a bool")
        if isinstance(value, LeaderboardOutcome):
            _support.call("cna_property_dictionary_set_outcome", self._value, view,
                          c.c_uint32(int(value)))
        elif isinstance(value, datetime):
            _support.call("cna_property_dictionary_set_date_time_ticks", self._value,
                          view, c.c_int64(_ticks_of_datetime(value)))
        elif isinstance(value, timedelta):
            _support.call("cna_property_dictionary_set_time_span_ticks", self._value,
                          view, c.c_int64(_ticks_of(value)))
        elif isinstance(value, int):
            route = ("cna_property_dictionary_set_int32"
                     if -0x80000000 <= value <= 0x7FFFFFFF
                     else "cna_property_dictionary_set_int64")
            width = "int32" if route.endswith("int32") else "int64"
            argument = (c.c_int32(checked(value, width, "value"))
                        if width == "int32" else c.c_int64(checked(value, width, "value")))
            _support.call(route, self._value, view, argument)
        elif isinstance(value, float):
            _support.call("cna_property_dictionary_set_double", self._value, view,
                          c.c_double(value))
        elif isinstance(value, str):
            value_view, _keep_value = string_view(value, "value")
            _support.call("cna_property_dictionary_set_string", self._value, view,
                          value_view)
        else:
            raise TypeError(
                f"a property value may not be a {type(value).__name__}")

    def _set_value_single(self, key: str, value: float) -> None:
        """The ``Single`` overload, which Python's one ``float`` cannot select.

        XNA has both a ``Single`` and a ``Double`` overload and Python has one
        floating type, so ``SetValue`` takes the wider one and this is how a
        caller asks for the narrower. That is a LANGUAGE_MAPPING_LIMITATION and
        it is named rather than resolved by guessing.
        """
        view, _keep = self._key(key)
        _support.call("cna_property_dictionary_set_single", self._value, view,
                      c.c_float(float(value)))

    def TryGetValue(self, key: str) -> tuple[bool, object]:
        kind = self._kind(key)
        if kind is None:
            return False, None
        return True, self[key]

    def _remove(self, key: str) -> bool:
        view, _keep = self._key(key)
        return _support.out_bool("cna_property_dictionary_remove", self._value, view)

    def _clear(self) -> None:
        _support.call("cna_property_dictionary_clear", self._value)

    def __getitem__(self, key: str) -> object:
        kind = self._kind(key)
        if kind is None:
            raise KeyError(key)
        readers = {
            _KIND_INT32: self.GetValueInt32,
            _KIND_INT64: self.GetValueInt64,
            _KIND_SINGLE: self.GetValueSingle,
            _KIND_DOUBLE: self.GetValueDouble,
            _KIND_STRING: self.GetValueString,
            _KIND_OUTCOME: self.GetValueOutcome,
            _KIND_DATE_TIME: self.GetValueDateTime,
            _KIND_TIME_SPAN: self.GetValueTimeSpan,
            _KIND_STREAM: self.GetValueStream,
        }
        return readers[kind](key)

    def __setitem__(self, key: str, value: object) -> None:
        self.SetValue(key, value)

    def _keys(self) -> list[str]:
        return [_support.sized_text("cna_property_dictionary_get_key_size_at",
                                    "cna_property_dictionary_copy_key_at",
                                    (self._value, c.c_int32(index)), "key")
                for index in range(self.Count)]

    def GetEnumerator(self):
        return iter(self)

    def __iter__(self):
        for key in self._keys():
            yield key, self[key]


class LeaderboardIdentity:
    """Which leaderboard, and for which game mode."""

    __slots__ = ("_key", "_game_mode")

    def __init__(self) -> None:
        self._key = ""
        self._game_mode = 0

    @staticmethod
    def Create(key: LeaderboardKey, gameMode: int = 0) -> "LeaderboardIdentity":
        """XNA's two ``Create`` overloads.

        CNA's ``cna_leaderboard_identity_init`` is a value-structure initialiser
        the census refuses -- Python builds the structure from its measured
        ctypes layout -- so the two fields are set here, which is the same two
        assignments the initialiser makes.
        """
        identity = LeaderboardIdentity()
        identity._key = str(int(LeaderboardKey(key)))
        identity._game_mode = checked(gameMode, "int32", "gameMode")
        return identity

    @property
    def Key(self) -> str:
        return self._key

    @Key.setter
    def Key(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("Key must be str")
        self._key = value

    @property
    def GameMode(self) -> int:
        return self._game_mode

    @GameMode.setter
    def GameMode(self, value: int) -> None:
        self._game_mode = checked(value, "int32", "GameMode")

    def _to_native(self):
        native = _on.in_struct(_online.CNA_LeaderboardIdentity, _VERSION)
        native.key = int(self._key) if self._key.isdigit() else 0
        native.game_mode = self._game_mode
        return native

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LeaderboardIdentity):
            return NotImplemented
        return (self._key, self._game_mode) == (other._key, other._game_mode)

    def __hash__(self) -> int:
        return hash((self._key, self._game_mode))

    def __copy__(self) -> "LeaderboardIdentity":
        other = LeaderboardIdentity()
        other._key, other._game_mode = self._key, self._game_mode
        return other

    def __deepcopy__(self, memo: object) -> "LeaderboardIdentity":
        return self.__copy__()


LeaderboardIdentity.__xna_arities__ = {"Create": {1, 2}}


class LeaderboardEntry:
    """One row of a leaderboard."""

    __slots__ = ("_handle", "_owned")

    def __init__(self, handle: int, *, owned: bool = False) -> None:
        self._handle = int(handle)
        self._owned = owned

    @property
    def _value(self) -> c.c_uint64:
        if not self._handle:
            raise RuntimeError("LeaderboardEntry has been disposed")
        return c.c_uint64(self._handle)

    @property
    def Gamer(self) -> Gamer | None:
        present = c.c_uint8()
        handle = c.c_uint64()
        _support.call("cna_leaderboard_entry_get_gamer", self._value,
                      c.byref(present), c.byref(handle))
        if not present.value:
            return None
        return Gamer(int(handle.value), owned=False)

    @property
    def Rating(self) -> int:
        native = _support.out_struct(_online.CNA_LeaderboardEntryInfo, _VERSION,
                                     "cna_leaderboard_entry_get_info", self._value)
        return int(native.rating)

    @Rating.setter
    def Rating(self, value: int) -> None:
        _support.call("cna_leaderboard_entry_set_rating", self._value,
                      c.c_int64(checked(value, "int64", "Rating")))

    def _release(self) -> None:
        """Releases an owned leaderboard row exactly once."""
        if self._owned and self._handle:
            _support.call("cna_leaderboard_entry_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def _on_rating_changed(self, handler) -> None:
        """CNA's hook for a rating a leaderboard writer changed."""
        _support.call("cna_leaderboard_entry_set_rating_changed_hook_ext",
                      self._value,
                      _on.no_callback(_online.CNA_GamerAsyncCallback), None)

    @property
    def Columns(self) -> PropertyDictionary:
        return PropertyDictionary(_support.out_handle(
            "cna_leaderboard_entry_get_columns", self._value))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LeaderboardEntry):
            return NotImplemented
        return _support.out_bool("cna_leaderboard_entry_equals", self._value,
                                 other._value)

    def __hash__(self) -> int:
        return hash(self._handle)


class LeaderboardReader:
    """A page of a leaderboard, and the way to move between pages."""

    __slots__ = ("_handle", "_disposed")

    def __init__(self, handle: int) -> None:
        self._handle = int(handle)
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("LeaderboardReader has been disposed")
        return c.c_uint64(self._handle)

    def _read(self):
        return _support.out_struct(_online.CNA_LeaderboardReaderInfo, _VERSION,
                                   "cna_leaderboard_reader_get_info", self._value)

    @staticmethod
    def _gamers(gamers):
        values = []
        for gamer in gamers or ():
            if not isinstance(gamer, Gamer):
                raise TypeError("every entry of gamers must be a Gamer")
            values.append(gamer._value.value)
        if not values:
            return None, 0
        return (c.c_uint64 * len(values))(*values), len(values)

    @staticmethod
    def Read(*args: object) -> "LeaderboardReader":
        """XNA's three overloads: from gamers, from a pivot, or from a page."""
        if len(args) == 4:
            identity, gamers, pivot, pageSize = args
            array, count = LeaderboardReader._gamers(gamers)
            native = identity._to_native()
            return LeaderboardReader(_support.out_handle(
                "cna_leaderboard_reader_read_from_gamers", c.byref(native), array,
                c.c_uint64(count),
                c.c_uint64(0 if pivot is None else pivot._value.value),
                c.c_int32(checked(pageSize, "int32", "pageSize"))))
        if len(args) == 3 and isinstance(args[1], Gamer):
            identity, pivot, pageSize = args
            native = identity._to_native()
            return LeaderboardReader(_support.out_handle(
                "cna_leaderboard_reader_read_from_pivot", c.byref(native),
                pivot._value, c.c_int32(checked(pageSize, "int32", "pageSize"))))
        if len(args) == 3:
            identity, pageStart, pageSize = args
            native = identity._to_native()
            return LeaderboardReader(_support.out_handle(
                "cna_leaderboard_reader_read", c.byref(native),
                c.c_int32(checked(pageStart, "int32", "pageStart")),
                c.c_int32(checked(pageSize, "int32", "pageSize"))))
        raise TypeError("no matching Read overload")

    @staticmethod
    def _read_async(*args: object) -> "LeaderboardReader":
        """CNA's asynchronous read, whose three shapes mirror ``Read``."""
        if len(args) == 4:
            identity, gamers, pivot, pageSize = args
            array, count = LeaderboardReader._gamers(gamers)
            native = identity._to_native()
            return LeaderboardReader(_support.out_handle(
                "cna_leaderboard_reader_begin_read_from_gamers", c.byref(native),
                array, c.c_uint64(count),
                c.c_uint64(0 if pivot is None else pivot._value.value),
                c.c_int32(checked(pageSize, "int32", "pageSize")),
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))
        if len(args) == 3 and isinstance(args[1], Gamer):
            identity, pivot, pageSize = args
            native = identity._to_native()
            return LeaderboardReader(_support.out_handle(
                "cna_leaderboard_reader_begin_read_from_pivot", c.byref(native),
                pivot._value, c.c_int32(checked(pageSize, "int32", "pageSize")),
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))
        identity, pageStart, pageSize = args
        native = identity._to_native()
        return LeaderboardReader(_support.out_handle(
            "cna_leaderboard_reader_begin_read", c.byref(native),
            c.c_int32(checked(pageStart, "int32", "pageStart")),
            c.c_int32(checked(pageSize, "int32", "pageSize")),
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))

    @staticmethod
    def BeginRead(*args: object) -> object:
        if len(args) == 6:
            identity, gamers, pivot, pageSize, callback, asyncState = args
            produce = lambda: LeaderboardReader._read_async(
                identity, gamers, pivot, pageSize)
        elif len(args) == 5:
            identity, second, pageSize, callback, asyncState = args
            produce = lambda: LeaderboardReader._read_async(identity, second, pageSize)
        else:
            raise TypeError("no matching BeginRead overload")
        return _GamerAsyncResult.begin("ReadLeaderboard", asyncState, callback, produce)

    @staticmethod
    def EndRead(result: object) -> "LeaderboardReader":
        return _GamerAsyncResult.end(result, "ReadLeaderboard")

    @property
    def LeaderboardIdentity(self) -> LeaderboardIdentity:
        native = _support.out_struct(
            _online.CNA_LeaderboardIdentity, _VERSION,
            "cna_leaderboard_reader_get_identity", self._value)
        identity = LeaderboardIdentity()
        identity._key = str(int(native.key))
        identity._game_mode = int(native.game_mode)
        return identity

    @property
    def TotalLeaderboardSize(self) -> int:
        return int(self._read().total_leaderboard_size)

    @property
    def PageStart(self) -> int:
        return int(self._read().page_start)

    @property
    def CanPageUp(self) -> bool:
        return bool(self._read().can_page_up)

    @property
    def CanPageDown(self) -> bool:
        return bool(self._read().can_page_down)

    @property
    def Entries(self) -> tuple[LeaderboardEntry, ...]:
        count = int(self._read().entry_count)
        return tuple(
            LeaderboardEntry(_support.out_handle(
                "cna_leaderboard_reader_get_entry_at", self._value, c.c_int32(index)))
            for index in range(count))

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call("cna_leaderboard_reader_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self) -> "LeaderboardReader":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()

    def PageUp(self) -> None:
        _support.call("cna_leaderboard_reader_page_up", self._value)

    def PageDown(self) -> None:
        _support.call("cna_leaderboard_reader_page_down", self._value)

    def BeginPageUp(self, callback: object, asyncState: object) -> object:
        return _GamerAsyncResult.begin(
            "PageUp", asyncState, callback,
            lambda: _support.call(
                "cna_leaderboard_reader_begin_page_up", self._value,
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))

    def EndPageUp(self, result: object) -> None:
        _GamerAsyncResult.end(result, "PageUp")

    def BeginPageDown(self, callback: object, asyncState: object) -> object:
        return _GamerAsyncResult.begin(
            "PageDown", asyncState, callback,
            lambda: _support.call(
                "cna_leaderboard_reader_begin_page_down", self._value,
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))

    def EndPageDown(self, result: object) -> None:
        _GamerAsyncResult.end(result, "PageDown")


LeaderboardReader.__xna_arities__ = {"Read": {3, 4}, "BeginRead": {5, 6}}


class LeaderboardWriter:
    """Where a title writes the leaderboard rows it wants uploaded."""

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[tuple[str, int], LeaderboardEntry] = {}

    def GetLeaderboard(self, leaderboardId: LeaderboardIdentity) -> LeaderboardEntry:
        """The row this title is writing for that leaderboard.

        The same identity answers the same row, which is what makes a title able
        to accumulate columns across a match rather than replacing them.
        """
        if not isinstance(leaderboardId, LeaderboardIdentity):
            raise TypeError("leaderboardId must be a LeaderboardIdentity")
        key = (leaderboardId.Key, leaderboardId.GameMode)
        entry = self._entries.get(key)
        if entry is None:
            entry = LeaderboardEntry(_support.out_handle(
                "cna_leaderboard_entry_create_ext", c.c_uint64(0), c.c_int64(0),
                c.c_int32(0)), owned=True)
            self._entries[key] = entry
        return entry
