"""Private generation, ownership, identity, and callback state for Media."""

from __future__ import annotations

import ctypes as c
from threading import RLock, get_ident
import weakref

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.runtime_context import live_game


class _IdentityDomain:
    def __init__(self) -> None:
        self.items: dict[type, list[_NativeHandle]] = {}


class _MediaRuntime:
    def __init__(self) -> None:
        self.lock = RLock()
        self.generation = 0
        self.game_ref: weakref.ReferenceType[object] | None = None
        self.owner_thread: int | None = None
        self.objects: list[_NativeHandle] = []
        self.queue: object | None = None
        self.sources: dict[tuple[int, str, int], object] = {}
        self.registrations: dict[str, tuple[int, object]] = {}
        self.desired_events: set[str] = set()

    def attach(self, game: object) -> None:
        with self.lock:
            current = self.game_ref() if self.game_ref is not None else None
            if current is not None and current is not game:
                raise RuntimeError("MediaPlayer already has a different live Game generation")
            self.generation += 1
            self.game_ref = weakref.ref(game)
            self.owner_thread = get_ident()
            for name in tuple(self.desired_events):
                self._register_event(name)

    def require(self, operation: str) -> tuple[object, object, object, int, int]:
        game = live_game(operation)
        with self.lock:
            if self.game_ref is None or self.game_ref() is not game:
                raise RuntimeError(f"{operation} has no attached Media generation")
            host = getattr(game, "_host", None)
            if host is None or not host.handle or get_ident() != self.owner_thread:
                raise RuntimeError(f"{operation} requires the live Game owner thread")
            return game, host, host.library, int(host.handle), self.generation

    def track(self, value: "_NativeHandle") -> None:
        with self.lock:
            self.objects.append(value)

    def untrack(self, value: "_NativeHandle") -> None:
        with self.lock:
            try:
                self.objects.remove(value)
            except ValueError:
                pass

    def want_event(self, name: str) -> None:
        with self.lock:
            self.desired_events.add(name)
            if self.game_ref is not None and self.game_ref() is not None:
                self._register_event(name)

    def unwant_event(self, name: str) -> None:
        with self.lock:
            self.desired_events.discard(name)
            registration = self.registrations.pop(name, None)
            if registration is not None:
                library = get_library()
                library.check(library.cna_media_player_unsubscribe_ext(registration[0]),
                              "cna_media_player_unsubscribe_ext")

    def _register_event(self, name: str) -> None:
        if name in self.registrations:
            return
        game = self.game_ref() if self.game_ref is not None else None
        host = getattr(game, "_host", None)
        if game is None or host is None or not host.handle:
            return
        generation = self.generation

        @abi.CNA_MediaPlayerEventCallback
        def callback(context: object) -> None:
            try:
                with self.lock:
                    active = self.game_ref() if self.game_ref is not None else None
                    if active is not game or self.generation != generation:
                        return
                    from ._player import MediaPlayer
                    descriptor = MediaPlayer.__dict__[name]
                    handlers = tuple(descriptor._handlers_for(MediaPlayer))
                def deliver() -> None:
                    with self.lock:
                        current = self.game_ref() if self.game_ref is not None else None
                        if current is not game or self.generation != generation:
                            return
                    for handler in handlers:
                        handler(MediaPlayer, None)
                host._queue_dispatch_callback(deliver)
            except BaseException as error:
                if host.pending_exception is None:
                    host.pending_exception = error

        output = c.c_uint64()
        operation = ("cna_media_player_subscribe_active_song_changed_ext"
                     if name == "ActiveSongChanged"
                     else "cna_media_player_subscribe_media_state_changed_ext")
        host.library.check(getattr(host.library, operation)(callback, None, c.byref(output)), operation)
        self.registrations[name] = (int(output.value), callback)

    def detach(self, game: object) -> None:
        with self.lock:
            if self.game_ref is None or self.game_ref() is not game:
                return
            host = getattr(game, "_host", None)
            library = getattr(host, "library", None)
            handle = int(getattr(host, "handle", 0))
            first: BaseException | None = None
            for registration, _callback in reversed(tuple(self.registrations.values())):
                try:
                    library.check(library.cna_media_player_unsubscribe_ext(registration),
                                  "cna_media_player_unsubscribe_ext")
                except BaseException as error:
                    first = first or error
            self.registrations.clear()
            if handle:
                try:
                    library.check(library.cna_media_player_program_exit_ext(handle),
                                  "cna_media_player_program_exit_ext")
                except BaseException as error:
                    first = first or error
            queue, self.queue = self.queue, None
            if queue is not None:
                try:
                    queue._destroy_native()
                except BaseException as error:
                    first = first or error
            # Player-held Video pointers must be released before any Video,
            # independent of Python construction order.  The remaining graph
            # keeps reverse-acquisition order (catalog children before their
            # MediaLibrary provider root).
            values = list(reversed(tuple(self.objects)))
            values.sort(key=lambda value: 0 if type(value).__name__ == "VideoPlayer"
                        else 1 if type(value).__name__ == "Video" else 2)
            for value in values:
                try:
                    value._destroy_native()
                except BaseException as error:
                    first = first or error
            self.objects.clear()
            self.sources.clear()
            self.game_ref = None
            self.owner_thread = None
            if first is not None:
                raise first


_runtime = _MediaRuntime()


class _NativeHandle:
    _destroy_symbol = ""

    def _init_handle(self, handle: int, generation: int, domain: _IdentityDomain | None = None) -> None:
        self._handle = int(handle)
        self._generation = generation
        self._domain = domain or _IdentityDomain()
        self._properties: dict[str, object] = {}
        _runtime.track(self)

    def _live_handle(self, operation: str) -> tuple[object, int]:
        _game, _host, library, _game_handle, generation = _runtime.require(operation)
        if not self._handle or self._generation != generation:
            raise RuntimeError(f"{type(self).__name__} belongs to a stale Game generation")
        return library, self._handle

    def _destroy_native(self) -> None:
        handle, self._handle = self._handle, 0
        self._properties.clear()
        if handle and self._destroy_symbol:
            library = get_library()
            library.check(getattr(library, self._destroy_symbol)(handle), self._destroy_symbol)

    def __enter__(self):
        self._live_handle(f"{type(self).__name__}.__enter__")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


def _active(operation: str) -> tuple[object, object, object, int, int]:
    return _runtime.require(operation)


def _string_view(value: object, name: str) -> tuple[bytes, abi.CNA_StringView]:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if "\0" in value:
        raise ValueError(f"{name} cannot contain NUL")
    encoded = value.encode("utf-8", errors="strict")
    return encoded, abi.CNA_StringView(encoded, len(encoded))


def _copy_string(library: object, handle: int, stem: str, *prefix: object) -> str:
    size = c.c_uint64()
    size_name, copy_name = f"{stem}_get_name_size", f"{stem}_copy_name"
    library.check(getattr(library, size_name)(handle, *prefix, c.byref(size)), size_name)
    if not size.value:
        return ""
    output = c.create_string_buffer(size.value)
    written = c.c_uint64()
    library.check(getattr(library, copy_name)(handle, *prefix, output, size.value,
                                               c.byref(written)), copy_name)
    return bytes(output.raw[:written.value]).decode("utf-8", errors="strict")


def _copy_bytes(library: object, handle: int, stem: str) -> bytes:
    size = c.c_uint64()
    size_name, copy_name = f"{stem}_size", f"{stem.replace('_get_', '_copy_')}"
    library.check(getattr(library, size_name)(handle, c.byref(size)), size_name)
    if not size.value:
        return b""
    output = (c.c_uint8 * size.value)()
    written = c.c_uint64()
    library.check(getattr(library, copy_name)(handle, output, size.value, c.byref(written)), copy_name)
    return bytes(output[:written.value])


def _attach_media_game(game: object) -> None:
    _runtime.attach(game)


def _detach_media_game(game: object) -> None:
    _runtime.detach(game)
