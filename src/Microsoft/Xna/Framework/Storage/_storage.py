"""Ownership-safe XNA storage projection over CNA ABI 0.7."""

from __future__ import annotations

import ctypes as c
import os
from pathlib import Path, PurePosixPath
import re
import threading
import weakref
from collections.abc import Callable

from _cna_native import abi
from _cna_native.errors import NativeError
from _cna_native.loader import get_library
from _cna_native.runtime_context import live_game

from .. import PlayerIndex
from .._game_objects import _string_view
from .._language import Event, staticpropertymeta
from .._numeric import int32


class StorageDeviceNotConnectedException(Exception):
    def __init__(self, *args: object) -> None:
        if not args:
            super().__init__()
        elif len(args) == 1 and isinstance(args[0], str):
            super().__init__(args[0])
        elif (len(args) == 2 and isinstance(args[0], str)
              and isinstance(args[1], Exception)):
            super().__init__(args[0]); self.__cause__ = args[1]
        else:
            raise TypeError("StorageDeviceNotConnectedException expects (), message, or message and innerException")


class _StorageAsyncResult:
    """Private, opaque, synchronously completed IAsyncResult mapping."""
    def __init__(self, operation: str, owner: object | None, state: object,
                 game: object, host: object, release_operation: str) -> None:
        self._operation, self._owner, self._state = operation, owner, state
        self._game_ref, self._host = weakref.ref(game), host
        self._release_operation = release_operation
        self._handle, self._ended, self._disposed = 0, False, False
        game._register_native_child(self)
    @property
    def AsyncState(self) -> object: return self._state
    @property
    def CompletedSynchronously(self) -> bool: return True
    @property
    def IsCompleted(self) -> bool: return True
    @property
    def IsDisposed(self) -> bool: return self._disposed
    def _set_handle(self, handle: int) -> None: self._handle = handle
    def _validate(self, operation: str, owner: object | None) -> int:
        game = self._game_ref()
        if (self._disposed or self._ended or not self._handle
                or self._operation != operation or self._owner is not owner):
            raise ValueError("result does not belong to this End operation")
        if (game is None or game._disposed or game._host is not self._host
                or not self._host.handle):
            raise ValueError("result belongs to an expired runtime generation")
        self._ended, handle = True, self._handle
        self._handle, self._disposed = 0, True
        game._unregister_native_child(self)
        return handle
    def Dispose(self) -> None:
        if self._disposed: return
        game = self._game_ref()
        if self._handle:
            library = get_library()
            library.check(getattr(library, self._release_operation)(self._handle), self._release_operation)
            self._handle = 0
        self._disposed = True
        if game is not None: game._unregister_native_child(self)


class _StorageDeviceLease:
    def __init__(self, device: "StorageDevice", game: object) -> None:
        self._device, self._game_ref, self._disposed = device, weakref.ref(game), False
        game._register_native_child(self)
    @property
    def IsDisposed(self) -> bool: return self._disposed
    def Dispose(self) -> None:
        if self._disposed: return
        device = self._device
        if device is not None:
            device._release_for_game()
            device._lease = None
        self._device = None
        self._disposed = True
        game = self._game_ref()
        if game is not None: game._unregister_native_child(self)


class _DeviceEventLease:
    def __init__(self, game: object) -> None:
        self._game_ref, self._disposed = weakref.ref(game), False
        game._register_native_child(self)
    @property
    def IsDisposed(self) -> bool: return self._disposed
    def Dispose(self) -> None:
        if self._disposed: return
        StorageDevice._release_device_event_registration()
        self._disposed = True
        game = self._game_ref()
        if game is not None: game._unregister_native_child(self)


def _callback(value: object, name: str) -> Callable[[object], object] | None:
    if value is not None and not callable(value): raise TypeError(f"{name} must be callable or None")
    return value


def _storage_root() -> Path:
    library = get_library(); size = c.c_uint64()
    library.check(library.cna_storage_get_root_size_ext(c.byref(size)), "cna_storage_get_root_size_ext")
    buffer = c.create_string_buffer(size.value or 1); written = c.c_uint64()
    library.check(library.cna_storage_copy_root_ext(buffer, size.value, c.byref(written)), "cna_storage_copy_root_ext")
    return Path(bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict"))


def _validate_container_name(value: object, name: str) -> str:
    if not isinstance(value, str): raise TypeError(f"{name} must be str")
    if not value or "\0" in value: raise ValueError(f"{name} must contain a non-NUL value")
    portable = value.replace("\\", "/")
    if (portable.startswith("/") or "/" in portable or portable in {".", ".."}
            or re.match(r"^[A-Za-z]:", portable)):
        raise ValueError(f"{name} escapes the storage root")
    return value


_FILE_MODES = {"create_new": 1, "create": 2, "open": 3,
               "open_or_create": 4, "truncate": 5, "append": 6}
_FILE_ACCESS = {"read": 1, "write": 2, "read_write": 3}
_FILE_SHARE = {"read": 1, "write": 2, "delete": 4, "inheritable": 16}


def _mapped(mapping: dict[str, int], value: object, name: str) -> int:
    if not isinstance(value, str) or value not in mapping:
        raise ValueError(f"{name} must be one of {tuple(mapping)}")
    return mapping[value]


def _share(value: object) -> int:
    if not isinstance(value, frozenset) or not all(isinstance(item, str) for item in value):
        raise TypeError("fileShare must be frozenset[str]")
    unknown = value - _FILE_SHARE.keys()
    if unknown: raise ValueError(f"fileShare contains unknown values: {sorted(unknown)}")
    result = 0
    for item in value: result |= _FILE_SHARE[item]
    return result


class StorageDevice(metaclass=staticpropertymeta):
    DeviceChanged = Event(static=True)
    _device_event_callback = None
    _device_event_registration = 0
    _device_event_lease = None

    def __init__(self, handle: int, game: object, host: object, player: PlayerIndex | None,
                 _token: object = None) -> None:
        if _token is not StorageDevice: raise TypeError("StorageDevice values are returned by EndShowSelector")
        self._handle, self._game_ref, self._host = handle, weakref.ref(game), host
        self._player, self._containers, self._disposed = player, [], False
        self._lease = _StorageDeviceLease(self, game)

    @classmethod
    def _event_subscribe(cls, name: str) -> None:
        try:
            cls._ensure_device_event_registration()
        except RuntimeError:
            # XNA permits static subscription before a Game exists. The next
            # native Game creation attaches the process registration.
            return
    @classmethod
    def _event_unsubscribe(cls, name: str) -> None:
        cls._release_device_event_registration()
    @classmethod
    def _ensure_device_event_registration(cls) -> None:
        if cls._device_event_registration: return
        game = live_game("StorageDevice.DeviceChanged")
        game_ref, host = weakref.ref(game), game._host
        @abi.CNA_StorageCompletionCallback
        def native(context):
            current = game_ref()
            if (current is not None and not current._disposed and current._host is host
                    and host.handle):
                host._queue_dispatch_callback(lambda: cls.DeviceChanged(None, None))
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_storage_device_subscribe_device_changed(native, None, c.byref(output)),
                      "cna_storage_device_subscribe_device_changed")
        cls._device_event_callback, cls._device_event_registration = native, int(output.value)
        cls._device_event_lease = _DeviceEventLease(game)
    @classmethod
    def _attach_game(cls, game: object) -> None:
        event = cls.__dict__["DeviceChanged"]
        if event._handlers_for(cls) and not cls._device_event_registration:
            cls._ensure_device_event_registration()
    @classmethod
    def _release_device_event_registration(cls) -> None:
        if cls._device_event_registration:
            library = get_library(); library.check(
                library.cna_storage_device_unsubscribe_device_changed(cls._device_event_registration),
                "cna_storage_device_unsubscribe_device_changed")
        cls._device_event_registration, cls._device_event_callback = 0, None
        cls._device_event_lease = None

    @staticmethod
    def BeginShowSelector(*args: object) -> object:
        game = live_game("StorageDevice.BeginShowSelector"); host = game._host
        event = StorageDevice.__dict__["DeviceChanged"]
        if event._handlers_for(StorageDevice) and not StorageDevice._device_event_registration:
            StorageDevice._ensure_device_event_registration()
        player = None
        if len(args) == 2:
            callback, state = args; operation = "cna_storage_device_show_selector"; prefix = ()
        elif len(args) == 3:
            player, callback, state = args
            if not isinstance(player, PlayerIndex): raise TypeError("player must be PlayerIndex")
            operation, prefix = "cna_storage_device_show_selector_for_player", (int(player),)
        elif len(args) == 4:
            size, directories, callback, state = args
            size, directories = int32(size, name="sizeInBytes"), int32(directories, name="directoryCount")
            if size < 0: raise ValueError("sizeInBytes must be nonnegative")
            # XNA accepts negative directoryCount; CNA adds a minimum-count
            # check, so normalize only at the native boundary.
            operation, prefix = "cna_storage_device_show_selector_with_space", (size, max(0, directories))
        elif len(args) == 5:
            player, size, directories, callback, state = args
            if not isinstance(player, PlayerIndex): raise TypeError("player must be PlayerIndex")
            size, directories = int32(size, name="sizeInBytes"), int32(directories, name="directoryCount")
            if size < 0: raise ValueError("sizeInBytes must be nonnegative")
            operation, prefix = "cna_storage_device_show_selector_for_player_with_space", (int(player), size, max(0, directories))
        else:
            raise TypeError("no matching BeginShowSelector overload")
        callback = _callback(callback, "callback")
        token = _StorageAsyncResult("selector", None, state, game, host, "cna_storage_device_destroy")
        token._player = player
        observed = [0]
        @abi.CNA_StorageCompletionCallback
        def native(context): observed[0] += 1
        native_argument = native if callback is not None else abi.CNA_StorageCompletionCallback()
        output = c.c_uint64(); library = get_library()
        try:
            library.check(getattr(library, operation)(*prefix, native_argument, None, c.byref(output)), operation)
            token._set_handle(int(output.value))
            if callback is not None:
                if observed[0] != 1:
                    raise RuntimeError("CNA storage selector must complete synchronously exactly once")
                callback(token)
            return token
        except BaseException:
            token.Dispose(); raise

    @staticmethod
    def EndShowSelector(result: object) -> "StorageDevice":
        if not isinstance(result, _StorageAsyncResult): raise ValueError("result was not produced by BeginShowSelector")
        handle = result._validate("selector", None)
        game = result._game_ref()
        return StorageDevice(handle, game, result._host, getattr(result, "_player", None), StorageDevice)

    def _require_handle(self) -> int:
        game = self._game_ref()
        if (self._disposed or not self._handle or game is None or game._disposed
                or game._host is not self._host or not self._host.handle):
            raise StorageDeviceNotConnectedException("The storage device is not connected")
        return self._handle

    def _read(self, operation: str, kind) -> object:
        value = kind(); library = get_library()
        try: library.check(getattr(library, operation)(self._require_handle(), c.byref(value)), operation)
        except NativeError as error:
            if error.result == 3: raise StorageDeviceNotConnectedException(str(error)) from error
            raise
        return value.value
    @property
    def FreeSpace(self) -> int: return int(self._read("cna_storage_device_get_free_space", c.c_int64))
    @property
    def IsConnected(self) -> bool:
        if self._disposed: return False
        return bool(self._read("cna_storage_device_get_is_connected", c.c_uint8))
    @property
    def TotalSpace(self) -> int: return int(self._read("cna_storage_device_get_total_space", c.c_int64))

    def BeginOpenContainer(self, displayName: str, callback: object, state: object) -> object:
        displayName = _validate_container_name(displayName, "displayName")
        callback = _callback(callback, "callback")
        game = self._game_ref(); token = _StorageAsyncResult(
            "container", self, state, game, self._host, "cna_storage_container_destroy")
        token._display_name = displayName
        observed = [0]
        @abi.CNA_StorageCompletionCallback
        def native(context): observed[0] += 1
        native_argument = native if callback is not None else abi.CNA_StorageCompletionCallback()
        encoded, view = _string_view(displayName, name="displayName")
        output = c.c_uint64(); library = get_library()
        try:
            library.check(library.cna_storage_container_open(
                self._require_handle(), view, native_argument, None, c.byref(output)),
                "cna_storage_container_open")
            token._set_handle(int(output.value))
            if callback is not None:
                if observed[0] != 1:
                    raise RuntimeError("CNA storage container open must complete synchronously exactly once")
                callback(token)
            return token
        except BaseException:
            token.Dispose(); raise
        finally: del encoded

    def EndOpenContainer(self, result: object) -> "StorageContainer":
        if not isinstance(result, _StorageAsyncResult): raise ValueError("result was not produced by BeginOpenContainer")
        handle = result._validate("container", self)
        container = StorageContainer(handle, self, result._display_name, StorageContainer)
        self._containers.append(container)
        return container

    def DeleteContainer(self, titleName: str) -> None:
        selected = _validate_container_name(titleName, "titleName")
        encoded, view = _string_view(selected, name="titleName"); library = get_library()
        try: library.check(library.cna_storage_device_delete_container(self._require_handle(), view), "cna_storage_device_delete_container")
        finally: del encoded

    def _release_for_game(self) -> None:
        if self._disposed: return
        first_error = None
        for container in tuple(reversed(self._containers)):
            try: container.Dispose()
            except BaseException as error: first_error = first_error or error
        if first_error is not None:
            raise first_error
        if self._handle:
            try: get_library().check(get_library().cna_storage_device_destroy(self._handle), "cna_storage_device_destroy")
            except BaseException as error: first_error = first_error or error
            else: self._handle = 0; self._disposed = True
        if first_error is not None: raise first_error


class _StorageStream:
    def __init__(self, handle: int, container: "StorageContainer") -> None:
        self._handle, self._container, self._closed = handle, container, False
    @property
    def closed(self) -> bool: return self._closed
    def _require(self) -> int:
        if self._closed or not self._handle: raise ValueError("I/O operation on closed storage stream")
        if self._container.IsDisposed: raise ValueError("storage container is disposed")
        return self._handle
    def _capability(self, operation: str) -> bool:
        value = c.c_uint8(); library = get_library(); library.check(
            getattr(library, operation)(self._require(), c.byref(value)), operation)
        return value.value != 0
    def readable(self) -> bool: return self._capability("cna_storage_stream_get_can_read")
    def writable(self) -> bool: return self._capability("cna_storage_stream_get_can_write")
    def seekable(self) -> bool: return self._capability("cna_storage_stream_get_can_seek")
    def tell(self) -> int:
        value = c.c_int64(); library = get_library(); library.check(
            library.cna_storage_stream_get_position(self._require(), c.byref(value)), "cna_storage_stream_get_position")
        return int(value.value)
    def seek(self, offset: int, whence: int = 0) -> int:
        if isinstance(offset, bool) or not isinstance(offset, int): raise TypeError("offset must be int")
        if whence not in (0, 1, 2): raise ValueError("whence must be 0, 1, or 2")
        value = c.c_int64(); library = get_library(); library.check(
            library.cna_storage_stream_seek(self._require(), offset, whence, c.byref(value)), "cna_storage_stream_seek")
        return int(value.value)
    def _length(self) -> int:
        value = c.c_int64(); library = get_library(); library.check(
            library.cna_storage_stream_get_length(self._require(), c.byref(value)), "cna_storage_stream_get_length")
        return int(value.value)
    def read(self, size: int = -1) -> bytes:
        if isinstance(size, bool) or not isinstance(size, int): raise TypeError("size must be int")
        if size < -1: raise ValueError("size must be nonnegative or -1")
        if size == -1: size = max(0, self._length() - self.tell())
        native = (c.c_uint8 * size)(); read = c.c_uint64(); library = get_library()
        library.check(library.cna_storage_stream_read(self._require(), native, size, c.byref(read)), "cna_storage_stream_read")
        return bytes(native[:read.value])
    def readinto(self, buffer: object) -> int:
        try: view = memoryview(buffer).cast("B")
        except TypeError as error: raise TypeError("buffer must be writable bytes-like") from error
        if view.readonly: raise TypeError("buffer must be writable")
        data = self.read(len(view)); view[:len(data)] = data; return len(data)
    def write(self, data: object) -> int:
        try: payload = bytes(memoryview(data).cast("B"))
        except TypeError as error: raise TypeError("data must be bytes-like") from error
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload); library = get_library()
        library.check(library.cna_storage_stream_write(self._require(), native, len(payload)), "cna_storage_stream_write")
        return len(payload)
    def truncate(self, size: int | None = None) -> int:
        selected = self.tell() if size is None else size
        if isinstance(selected, bool) or not isinstance(selected, int) or selected < 0: raise ValueError("size must be a nonnegative int")
        library = get_library(); library.check(library.cna_storage_stream_set_length(self._require(), selected), "cna_storage_stream_set_length")
        return selected
    def flush(self) -> None:
        library = get_library(); library.check(library.cna_storage_stream_flush(self._require()), "cna_storage_stream_flush")
    def close(self) -> None:
        if self._closed: return
        handle = self._handle; library = get_library()
        library.check(library.cna_storage_stream_close(handle), "cna_storage_stream_close")
        self._handle, self._closed = 0, True
        self._container._remove_stream(self)
    def __enter__(self): self._require(); return self
    def __exit__(self, exc_type, exc, traceback): self.close()


class StorageContainer:
    Disposing = Event()
    def __init__(self, handle: int, device: StorageDevice, display_name: str, _token: object = None) -> None:
        if _token is not StorageContainer: raise TypeError("StorageContainer values are returned by EndOpenContainer")
        self._handle, self._device, self._display_name = handle, device, display_name
        self._disposed, self._streams = False, []
        self._dispose_in_progress, self._disposing_event_delivered = False, False
        self._disposing_callback, self._disposing_registration = None, 0
        player = "AllPlayers" if device._player is None else f"Player{int(device._player) + 1}"
        self._root = _storage_root() / display_name / player
    def _require(self) -> int:
        if self._disposed or not self._handle: raise RuntimeError("StorageContainer is disposed")
        self._device._require_handle(); return self._handle
    def _event_subscribe(self, name: str) -> None:
        if self._disposing_registration: return
        @abi.CNA_StorageCompletionCallback
        def native(context): self._native_disposing_observed = True
        output = c.c_uint64(); library = get_library(); library.check(
            library.cna_storage_container_subscribe_disposing(self._require(), native, None, c.byref(output)),
            "cna_storage_container_subscribe_disposing")
        self._native_disposing_observed = False
        self._disposing_callback, self._disposing_registration = native, int(output.value)
    def _event_unsubscribe(self, name: str) -> None:
        if self._disposing_registration:
            library = get_library(); library.check(
                library.cna_storage_container_unsubscribe_disposing(self._disposing_registration),
                "cna_storage_container_unsubscribe_disposing")
        self._disposing_registration, self._disposing_callback = 0, None
    def _path(self, value: object, name: str) -> str:
        if not isinstance(value, str): raise TypeError(f"{name} must be str")
        if not value or "\0" in value: raise ValueError(f"{name} must contain a non-NUL value")
        portable = value.replace("\\", "/")
        if portable.startswith("/") or re.match(r"^[A-Za-z]:", portable):
            raise ValueError(f"{name} escapes the storage container")
        parts = []
        for component in PurePosixPath(portable).parts:
            if component in ("", "."): continue
            if component == "..":
                if not parts: raise ValueError(f"{name} escapes the storage container")
                parts.pop()
            else: parts.append(component)
        root = self._root.resolve(strict=False)
        candidate = self._root.joinpath(*parts).resolve(strict=False)
        try: contained = os.path.commonpath((str(root), str(candidate))) == str(root)
        except ValueError: contained = False
        if not contained: raise ValueError(f"{name} escapes the storage container")
        return "/".join(parts) or "."
    def _pattern(self, value: object) -> str:
        if not isinstance(value, str): raise TypeError("searchPattern must be str")
        if not value or "\0" in value: raise ValueError("searchPattern must contain a non-NUL value")
        if "/" in value or "\\" in value or re.match(r"^[A-Za-z]:", value):
            raise ValueError("searchPattern cannot contain a directory separator")
        return value
    def _view(self, value: str, name: str): return _string_view(value, name=name)
    def _unary(self, operation: str, value: object, name: str) -> None:
        selected = self._path(value, name); encoded, view = self._view(selected, name)
        try: get_library().check(getattr(get_library(), operation)(self._require(), view), operation)
        finally: del encoded
    def _exists(self, operation: str, value: object, name: str) -> bool:
        selected = self._path(value, name); encoded, view = self._view(selected, name); output = c.c_uint8()
        try: get_library().check(getattr(get_library(), operation)(self._require(), view, c.byref(output)), operation)
        finally: del encoded
        return output.value != 0
    def DirectoryExists(self, directory: str) -> bool: return self._exists("cna_storage_container_directory_exists", directory, "directory")
    def FileExists(self, file: str) -> bool: return self._exists("cna_storage_container_file_exists", file, "file")
    def CreateDirectory(self, directory: str) -> None: self._unary("cna_storage_container_create_directory", directory, "directory")
    def DeleteDirectory(self, directory: str) -> None: self._unary("cna_storage_container_delete_directory", directory, "directory")
    def DeleteFile(self, file: str) -> None: self._unary("cna_storage_container_delete_file", file, "file")
    def _stream(self, handle: int) -> _StorageStream:
        result = _StorageStream(handle, self); self._streams.append(result); return result
    def _remove_stream(self, stream: _StorageStream) -> None:
        self._streams = [value for value in self._streams if value is not stream]
    def CreateFile(self, file: str):
        selected = self._path(file, "file"); encoded, view = self._view(selected, "file"); output = c.c_uint64()
        try: get_library().check(get_library().cna_storage_container_create_file(self._require(), view, c.byref(output)), "cna_storage_container_create_file")
        finally: del encoded
        return self._stream(int(output.value))
    def OpenFile(self, *args: object):
        if len(args) not in (2, 3, 4): raise TypeError("no matching OpenFile overload")
        selected = self._path(args[0], "file"); mode = _mapped(_FILE_MODES, args[1], "fileMode")
        encoded, view = self._view(selected, "file"); output = c.c_uint64(); library = get_library()
        try:
            if len(args) == 2: result = library.cna_storage_container_open_file(self._require(), view, mode, c.byref(output)); operation = "cna_storage_container_open_file"
            elif len(args) == 3:
                access = _mapped(_FILE_ACCESS, args[2], "fileAccess"); operation = "cna_storage_container_open_file_access"
                result = library.cna_storage_container_open_file_access(self._require(), view, mode, access, c.byref(output))
            else:
                access, share = _mapped(_FILE_ACCESS, args[2], "fileAccess"), _share(args[3]); operation = "cna_storage_container_open_file_share"
                result = library.cna_storage_container_open_file_share(self._require(), view, mode, access, share, c.byref(output))
            library.check(result, operation)
        finally: del encoded
        return self._stream(int(output.value))
    def _names(self, directory: bool, pattern: object | None) -> list[str]:
        selected = "" if pattern is None else self._pattern(pattern)
        encoded, view = self._view(selected, "searchPattern"); count = c.c_uint64(); library = get_library()
        prefix = "directory" if directory else "file"
        count_op = f"cna_storage_container_get_{prefix}_name_count"
        copy_op = f"cna_storage_container_copy_{prefix}_name"
        library.check(getattr(library, count_op)(self._require(), view, c.byref(count)), count_op)
        result = []
        for index in range(count.value):
            required = c.c_uint64()
            code = getattr(library, copy_op)(self._require(), view, index, None, 0, c.byref(required))
            if code not in (0, 14): library.check(code, copy_op)
            buffer = c.create_string_buffer(required.value or 1); written = c.c_uint64()
            library.check(getattr(library, copy_op)(self._require(), view, index, buffer, required.value, c.byref(written)), copy_op)
            result.append(bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict"))
        del encoded
        return result
    def GetDirectoryNames(self, *args: object) -> list[str]:
        if len(args) > 1: raise TypeError("GetDirectoryNames expects zero or one argument")
        return self._names(True, args[0] if args else None)
    def GetFileNames(self, *args: object) -> list[str]:
        if len(args) > 1: raise TypeError("GetFileNames expects zero or one argument")
        return self._names(False, args[0] if args else None)
    @property
    def DisplayName(self) -> str:
        handle = self._require(); size = c.c_uint64(); library = get_library()
        library.check(library.cna_storage_container_get_display_name_size(handle, c.byref(size)),
                      "cna_storage_container_get_display_name_size")
        buffer = c.create_string_buffer(size.value or 1); written = c.c_uint64()
        library.check(library.cna_storage_container_copy_display_name(
            handle, buffer, size.value, c.byref(written)),
            "cna_storage_container_copy_display_name")
        return bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict")
    @property
    def StorageDevice(self) -> StorageDevice: return self._device
    @property
    def IsDisposed(self) -> bool:
        if self._disposed or not self._handle:
            return True
        value = c.c_uint8(); library = get_library()
        library.check(library.cna_storage_container_get_is_disposed(
            self._handle, c.byref(value)), "cna_storage_container_get_is_disposed")
        return value.value != 0
    def Dispose(self) -> None:
        if self._disposed and not self._handle: return
        if self._dispose_in_progress: return
        self._dispose_in_progress = True
        try:
            first_error = None
            for stream in tuple(reversed(self._streams)):
                try: stream.close()
                except BaseException as error: first_error = first_error or error
            # Never invalidate a parent while a child stream could not close.
            if first_error is not None:
                raise first_error
            if not self._disposed:
                try:
                    get_library().check(get_library().cna_storage_container_dispose(
                        self._handle), "cna_storage_container_dispose")
                except BaseException as error:
                    first_error = first_error or error
                else:
                    self._disposed = True
                    if self._disposing_registration and not self._native_disposing_observed:
                        first_error = first_error or RuntimeError(
                            "CNA did not deliver the registered StorageContainer.Disposing callback")
                    elif not self._disposing_event_delivered:
                        # One-shot before invocation makes recursive Dispose safe.
                        self._disposing_event_delivered = True
                        try: self.Disposing(self, None)
                        except BaseException as error: first_error = first_error or error
            if not self._disposed:
                if first_error is not None: raise first_error
                return
            if self._disposing_registration:
                try: self._event_unsubscribe("Disposing")
                except BaseException as error: first_error = first_error or error
            # A failed unsubscribe leaves a live registration and handle for an
            # owner-thread retry; destroying through it would be unsafe.
            if not self._disposing_registration:
                try: get_library().check(get_library().cna_storage_container_destroy(self._handle), "cna_storage_container_destroy")
                except BaseException as error: first_error = first_error or error
                else:
                    self._handle = 0
                    self._device._containers = [value for value in self._device._containers if value is not self]
                    type(self).__dict__["Disposing"]._clear_for(self)
            if first_error is not None: raise first_error
        finally:
            self._dispose_in_progress = False
    def __enter__(self): self._require(); return self
    def __exit__(self, exc_type, exc, traceback): self.Dispose()


StorageDeviceNotConnectedException.__xna_arities__ = {"__init__": {0, 1, 2}}
StorageDevice.__xna_arities__ = {"BeginShowSelector": {2, 3, 4, 5}}
StorageContainer.__xna_arities__ = {"OpenFile": {2, 3, 4}, "GetDirectoryNames": {0, 1}, "GetFileNames": {0, 1}}
