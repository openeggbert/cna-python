"""CNA-backed XNA Game lifecycle and timing values."""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from enum import IntEnum, IntFlag
import threading
from typing import Any
import weakref

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.runtime_context import set_current_game

from ._language import Event


def _ticks(value: timedelta) -> int:
    if not isinstance(value, timedelta):
        raise TypeError("TimeSpan values map to datetime.timedelta")
    return (value.days * 86_400 + value.seconds) * 10_000_000 + value.microseconds * 10


def _timedelta_from_ticks(value: int) -> timedelta:
    return timedelta(microseconds=value / 10)


class GameTime:
    __slots__ = ("_total_game_time", "_elapsed_game_time", "_is_running_slowly")

    def __init__(self, *args: object) -> None:
        if not args:
            totalGameTime, elapsedGameTime, isRunningSlowly = timedelta(), timedelta(), False
        elif len(args) == 2:
            totalGameTime, elapsedGameTime = args
            isRunningSlowly = False
        elif len(args) == 3:
            totalGameTime, elapsedGameTime, isRunningSlowly = args
        else:
            raise TypeError("GameTime expects zero, two, or three arguments")
        if not isinstance(totalGameTime, timedelta) or not isinstance(elapsedGameTime, timedelta):
            raise TypeError("GameTime TimeSpan arguments map to datetime.timedelta")
        if type(isRunningSlowly) is not bool:
            raise TypeError("isRunningSlowly must be bool")
        self._total_game_time = totalGameTime
        self._elapsed_game_time = elapsedGameTime
        self._is_running_slowly = bool(isRunningSlowly)

    @property
    def TotalGameTime(self) -> timedelta:
        return self._total_game_time

    @property
    def ElapsedGameTime(self) -> timedelta:
        return self._elapsed_game_time

    @property
    def IsRunningSlowly(self) -> bool:
        return self._is_running_slowly

    @classmethod
    def _from_native(cls, value: abi.CNA_GameTime | None) -> "GameTime":
        if value is None:
            return cls()
        return cls(_timedelta_from_ticks(value.total_game_time_ticks),
                   _timedelta_from_ticks(value.elapsed_game_time_ticks),
                   value.is_running_slowly != 0)


class PlayerIndex(IntEnum):
    One = 0
    Two = 1
    Three = 2
    Four = 3


class DisplayOrientation(IntFlag):
    Default = 0
    LandscapeLeft = 1
    LandscapeRight = 2
    Portrait = 4


class _NativeGameHost:
    def __init__(self, game: "Game") -> None:
        self.game = game
        self.library = get_library()
        self.handle = 0
        self.pending_exception: BaseException | None = None
        self.owner_thread = threading.get_ident()
        self._callback_buffers: list[c.Array[Any]] = []
        self._callbacks_keepalive: list[object] = []
        self._title = b"CNA"
        self._callbacks = self._make_callbacks()
        self._hooks = self._make_hooks()

    def _time(self, pointer: c.POINTER(abi.CNA_GameTime)) -> GameTime:
        return GameTime._from_native(pointer.contents if bool(pointer) else None)

    def _set_callback_error(self, out_error: c.POINTER(abi.CNA_CallbackError), error: BaseException) -> None:
        if not bool(out_error):
            return
        encoded = f"{type(error).__name__}: {error}".encode("utf-8", errors="replace")
        buffer = c.create_string_buffer(encoded)
        self._callback_buffers.append(buffer)
        out_error.contents.message.data = c.cast(buffer, c.c_char_p)
        out_error.contents.message.byte_length = len(encoded)

    def _invoke(self, name: str, time_pointer: c.POINTER(abi.CNA_GameTime),
                out_error: c.POINTER(abi.CNA_CallbackError)) -> int:
        if self.pending_exception is not None:
            return 9
        try:
            if threading.get_ident() != self.owner_thread:
                raise RuntimeError(f"CNA invoked {name} on a non-owner thread")
            self.game._begin_native_callback(self.handle)
            if name == "OnExiting":
                self.game.OnExiting(self.game, None)
            elif name in ("Initialize", "LoadContent", "BeginRun", "BeginDraw", "EndDraw", "EndRun", "UnloadContent"):
                getattr(self.game, name)()
            else:
                getattr(self.game, name)(self._time(time_pointer))
            return 0
        except BaseException as error:
            self.pending_exception = error
            self._set_callback_error(out_error, error)
            return 9
        finally:
            self.game._end_native_callback()

    def _lifecycle(self, name: str) -> abi.CNA_GameLifecycleCallback:
        @abi.CNA_GameLifecycleCallback
        def callback(game_handle, game_time, context, out_error):
            return self._invoke(name, game_time, out_error)
        self._callbacks_keepalive.append(callback)
        return callback

    def _begin_draw(self) -> abi.CNA_GameBeginDrawCallback:
        @abi.CNA_GameBeginDrawCallback
        def callback(game_handle, game_time, context, out_should_draw, out_error):
            if self.pending_exception is not None:
                return 9
            try:
                if threading.get_ident() != self.owner_thread:
                    raise RuntimeError("CNA invoked BeginDraw on a non-owner thread")
                self.game._begin_native_callback(self.handle)
                out_should_draw.contents.value = 1 if self.game.BeginDraw() else 0
                return 0
            except BaseException as error:
                self.pending_exception = error
                self._set_callback_error(out_error, error)
                return 9
            finally:
                self.game._end_native_callback()
        self._callbacks_keepalive.append(callback)
        return callback

    def _make_callbacks(self) -> abi.CNA_GameCallbacks:
        value = abi.CNA_GameCallbacks()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.load_content = self._lifecycle("LoadContent")
        value.update = self._lifecycle("Update")
        value.draw = self._lifecycle("Draw")
        value.unload_content = self._lifecycle("UnloadContent")
        value.exiting = self._lifecycle("OnExiting")
        value.context = None
        return value

    def _make_hooks(self) -> abi.CNA_GameFrameHooks:
        value = abi.CNA_GameFrameHooks()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.initialize = self._lifecycle("Initialize")
        value.begin_run = self._lifecycle("BeginRun")
        value.end_run = self._lifecycle("EndRun")
        value.begin_draw = self._begin_draw()
        value.end_draw = self._lifecycle("EndDraw")
        value.context = None
        return value

    def create(self) -> None:
        info = abi.CNA_GameCreateInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        info.is_fixed_time_step = 1 if self.game.IsFixedTimeStep else 0
        info.target_elapsed_time_ticks = _ticks(self.game.TargetElapsedTime)
        info.window_title = abi.CNA_StringView(self._title, len(self._title))
        info.callbacks = c.pointer(self._callbacks)
        output = c.c_uint64()
        self.library.check(self.library.cna_game_create(c.byref(info), c.byref(output)), "cna_game_create")
        self.handle = int(output.value)
        self.library.check(self.library.cna_game_set_frame_hooks_ext(self.handle, c.byref(self._hooks)),
                           "cna_game_set_frame_hooks_ext")
        self.library.check(
            self.library.cna_game_set_inactive_sleep_time_ticks(
                self.handle, _ticks(self.game._inactive_sleep_time)
            ),
            "cna_game_set_inactive_sleep_time_ticks",
        )
        self.library.check(
            self.library.cna_game_set_is_mouse_visible(self.handle, self.game._is_mouse_visible),
            "cna_game_set_is_mouse_visible",
        )

    def _finish_call(self, result: int, operation: str) -> None:
        if self.pending_exception is not None:
            error = self.pending_exception
            self.pending_exception = None
            raise error
        self.library.check(result, operation)

    def run(self) -> None:
        self._callback_buffers.clear()
        result = self.library.cna_game_run(self.handle)
        self._finish_call(result, "cna_game_run")

    def run_one_frame(self) -> None:
        self._callback_buffers.clear()
        result = self.library.cna_game_run_one_frame(self.handle)
        self._finish_call(result, "cna_game_run_one_frame")

    def request_exit(self) -> None:
        self.library.check(self.library.cna_game_request_exit(self.handle), "cna_game_request_exit")

    def destroy(self) -> None:
        if self.handle == 0:
            return
        self._callback_buffers.clear()
        result = self.library.cna_game_destroy(self.handle)
        if result in (0, 9):
            self.handle = 0
        # CNA retains the earlier callback failure through destruction. The
        # original Python exception was already re-raised by Run; do not emit a
        # second, less accurate NativeError. A new shutdown callback exception
        # is still present in pending_exception and is re-raised below.
        if result == 9 and self.pending_exception is None:
            return
        self._finish_call(result, "cna_game_destroy")


class Game:
    Exiting = Event()
    Disposed = Event()

    def __init__(self) -> None:
        self._native_children: list[weakref.ReferenceType[object]] = []
        self._disposed = False
        self._host: _NativeGameHost | None = None
        self._graphics_manager: object | None = None
        self._in_native_callback = False
        self._exit_requested = False
        self._has_run = False
        self._is_fixed_time_step = True
        self._target_elapsed_time = timedelta(microseconds=16667)
        self._inactive_sleep_time = timedelta(milliseconds=20)
        self._is_mouse_visible = False
        from .Content import ContentManager
        self._content = ContentManager(None)

    def _register_native_child(self, child: object) -> None:
        self._native_children.append(weakref.ref(child))

    def _unregister_native_child(self, child: object) -> None:
        self._native_children = [reference for reference in self._native_children
                                 if reference() not in (None, child)]

    def _dispose_native_children(self) -> None:
        first_error: BaseException | None = None
        for reference in reversed(self._native_children):
            child = reference()
            if child is None or child.IsDisposed:
                continue
            try:
                child.Dispose()
            except BaseException as error:
                first_error = first_error or error
        self._native_children.clear()
        if first_error is not None:
            raise first_error

    @property
    def GraphicsDevice(self):
        if self._graphics_manager is None:
            raise RuntimeError("Game has no GraphicsDeviceManager")
        return self._graphics_manager.GraphicsDevice

    @property
    def IsActive(self) -> bool:
        if self._host is None or self._host.handle == 0:
            return False
        value = c.c_uint8()
        operation = "cna_game_get_is_active"
        self._host.library.check(getattr(self._host.library, operation)(self._host.handle, c.byref(value)), operation)
        return value.value != 0

    def _native_bool(self, getter: str, fallback: bool) -> bool:
        if self._host is None or self._host.handle == 0:
            return fallback
        value = c.c_uint8()
        operation = f"cna_game_get_{getter}"
        self._host.library.check(getattr(self._host.library, operation)(self._host.handle, c.byref(value)), operation)
        return value.value != 0

    def _native_ticks(self, getter: str, fallback: timedelta) -> timedelta:
        if self._host is None or self._host.handle == 0:
            return fallback
        value = c.c_int64()
        operation = f"cna_game_get_{getter}_ticks"
        self._host.library.check(getattr(self._host.library, operation)(self._host.handle, c.byref(value)), operation)
        return _timedelta_from_ticks(value.value)

    @property
    def IsFixedTimeStep(self) -> bool:
        return self._native_bool("is_fixed_time_step", self._is_fixed_time_step)

    @IsFixedTimeStep.setter
    def IsFixedTimeStep(self, value: bool) -> None:
        self._is_fixed_time_step = bool(value)
        if self._host is not None and self._host.handle:
            operation = "cna_game_set_is_fixed_time_step"
            self._host.library.check(getattr(self._host.library, operation)(self._host.handle, self._is_fixed_time_step), operation)

    @property
    def IsMouseVisible(self) -> bool:
        return self._native_bool("is_mouse_visible", self._is_mouse_visible)

    @IsMouseVisible.setter
    def IsMouseVisible(self, value: bool) -> None:
        self._is_mouse_visible = bool(value)
        if self._host is not None and self._host.handle:
            operation = "cna_game_set_is_mouse_visible"
            self._host.library.check(getattr(self._host.library, operation)(self._host.handle, self._is_mouse_visible), operation)

    @property
    def TargetElapsedTime(self) -> timedelta:
        return self._native_ticks("target_elapsed_time", self._target_elapsed_time)

    @TargetElapsedTime.setter
    def TargetElapsedTime(self, value: timedelta) -> None:
        ticks = _ticks(value)
        if ticks <= 0:
            raise ValueError("TargetElapsedTime must be positive")
        self._target_elapsed_time = value
        if self._host is not None and self._host.handle:
            operation = "cna_game_set_target_elapsed_time_ticks"
            self._host.library.check(getattr(self._host.library, operation)(self._host.handle, ticks), operation)

    @property
    def InactiveSleepTime(self) -> timedelta:
        return self._native_ticks("inactive_sleep_time", self._inactive_sleep_time)

    @InactiveSleepTime.setter
    def InactiveSleepTime(self, value: timedelta) -> None:
        ticks = _ticks(value)
        if ticks < 0:
            raise ValueError("InactiveSleepTime cannot be negative")
        self._inactive_sleep_time = value
        if self._host is not None and self._host.handle:
            operation = "cna_game_set_inactive_sleep_time_ticks"
            self._host.library.check(getattr(self._host.library, operation)(self._host.handle, ticks), operation)

    @property
    def Content(self):
        return self._content

    @Content.setter
    def Content(self, value) -> None:
        from .Content import ContentManager
        if not isinstance(value, ContentManager):
            raise TypeError("Content must be a ContentManager")
        self._content = value

    def _attach_graphics_manager(self, manager: object) -> None:
        if self._graphics_manager is not None:
            raise ValueError("a Game accepts exactly one GraphicsDeviceManager")
        self._graphics_manager = manager

    def _begin_native_callback(self, game_handle: int) -> None:
        self._in_native_callback = True
        if self._graphics_manager is not None:
            self._graphics_manager._begin_native_callback(game_handle)

    def _end_native_callback(self) -> None:
        if self._graphics_manager is not None:
            self._graphics_manager._end_native_callback()
        self._in_native_callback = False

    def _ensure_host(self) -> _NativeGameHost:
        if self._disposed:
            raise RuntimeError("Game is disposed")
        if self._host is None:
            host = _NativeGameHost(self)
            host.create()
            self._host = host
            if self._graphics_manager is not None:
                self._graphics_manager._create_native(host)
            if self._exit_requested:
                host.request_exit()
        return self._host

    def Run(self) -> None:
        if self._has_run:
            raise RuntimeError("Game.Run may only be called once")
        host = self._ensure_host()
        self._has_run = True
        set_current_game(self)
        try:
            host.run()
        finally:
            set_current_game(None)

    def RunOneFrame(self) -> None:
        host = self._ensure_host()
        set_current_game(self)
        try:
            host.run_one_frame()
        finally:
            set_current_game(None)

    def Tick(self) -> None:
        self.RunOneFrame()

    def Exit(self) -> None:
        if self._disposed:
            raise RuntimeError("Game is disposed")
        self._exit_requested = True
        if self._host is not None:
            self._host.request_exit()

    # These are canonical override hooks. CNA performs the surrounding framework
    # work; the base hook intentionally has no user action.
    def Initialize(self) -> None: return None
    def LoadContent(self) -> None: return None
    def UnloadContent(self) -> None: return None
    def BeginRun(self) -> None: return None
    def EndRun(self) -> None: return None
    def Update(self, gameTime: GameTime) -> None: return None
    def BeginDraw(self) -> bool: return True
    def Draw(self, gameTime: GameTime) -> None: return None
    def EndDraw(self) -> None: return None

    def OnExiting(self, sender: object, args: object) -> None:
        self.Exiting(sender, args)

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if self._disposed:
            return
        first_error: BaseException | None = None
        try:
            self.Content.Dispose()
            self._dispose_native_children()
        except BaseException as error:
            first_error = error
        if self._graphics_manager is not None:
            try:
                self._graphics_manager.Dispose()
            except BaseException as error:
                first_error = first_error or error
        if self._host is not None:
            try:
                self._host.destroy()
            except BaseException as error:
                first_error = first_error or error
        self._disposed = True
        self.Disposed(self, None)
        if first_error is not None:
            raise first_error

    def __enter__(self) -> "Game":
        if self._disposed:
            raise RuntimeError("Game is disposed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


GameTime.__xna_arities__ = {"__init__": {0, 2, 3}}
Game.__xna_arities__ = {"Dispose": {0, 1}}
