"""Authored XACT AudioEngine, bank, category, renderer, and cue graph."""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from pathlib import Path
import weakref

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.ownership import NativeResource, Ownership

from .._language import Event
from .._numeric import f32, wrap_int32
from ._common import (
    _active_native, _copy_string, _native_emitter, _native_listener,
    _string_view, _timedelta_ticks,
)
from ._sound import AudioEmitter, AudioListener, AudioStopOptions


def _release(operation: str):
    def release(handle: int) -> None:
        library = get_library()
        library.check(getattr(library, operation)(handle), operation)
    return release


def _path(value: object, name: str) -> tuple[bytes, abi.CNA_StringView, str]:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value or "\0" in value:
        raise ValueError(f"{name} cannot be empty or contain NUL")
    resolved = str(Path(value).resolve())
    encoded, view = _string_view(resolved, name)
    return encoded, view, resolved


class RendererDetail:
    def __init__(self) -> None:
        # XNA's value-type default leaves both backing references null.  The
        # public metadata predates nullable-reference annotations, so this is
        # observable even though the CLR property types are System.String.
        self._friendly_name: str | None = None
        self._renderer_id: str | None = None
        self._hash_code = 0

    @classmethod
    def _from_native(cls, friendly_name: str | None, renderer_id: str | None,
                     hash_code: int) -> "RendererDetail":
        self = cls()
        self._friendly_name, self._renderer_id, self._hash_code = friendly_name, renderer_id, hash_code
        return self

    @property
    def FriendlyName(self) -> str | None: return self._friendly_name
    @property
    def RendererId(self) -> str | None: return self._renderer_id
    def GetHashCode(self) -> int: return self._hash_code
    def ToString(self) -> str: return "Microsoft.Xna.Framework.Audio.RendererDetail"
    def Equals(self, obj: object) -> bool: return self == obj
    def __eq__(self, other: object) -> bool:
        return isinstance(other, RendererDetail) and (
            self._friendly_name, self._renderer_id) == (other._friendly_name, other._renderer_id)
    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        return not result if result is not NotImplemented else NotImplemented
    def __hash__(self) -> int: return self.GetHashCode()
    def __str__(self) -> str: return self.ToString()
    def __copy__(self) -> "RendererDetail":
        return RendererDetail._from_native(self._friendly_name, self._renderer_id, self._hash_code)
    def __deepcopy__(self, memo: object) -> "RendererDetail": return self.__copy__()


class _CategoryState:
    def __init__(self, engine: "AudioEngine", handle: int) -> None:
        self.engine = engine
        # The public value is parent-owned/non-disposable, while this private
        # state owns the C facade handle that merely stores the copied value.
        self.native = NativeResource(handle, Ownership.OWNED,
                                     _release("cna_audio_category_destroy"))
        engine._register_child(self)

    @property
    def IsDisposed(self) -> bool: return self.native.IsDisposed
    def _require_handle(self) -> int:
        self.engine._require_handle()
        return self.native._require_handle()
    def Dispose(self) -> None:
        if self.IsDisposed: return
        self.native.Dispose()
        self.engine._unregister_child(self)


class AudioCategory:
    def __init__(self) -> None:
        self._state: _CategoryState | None = None

    @classmethod
    def _from_state(cls, state: _CategoryState) -> "AudioCategory":
        self = cls(); self._state = state; return self

    def _handle(self) -> int:
        if self._state is None:
            raise RuntimeError("AudioCategory is uninitialized")
        return self._state._require_handle()

    @property
    def Name(self) -> str | None:
        if self._state is None: return None
        library = get_library()
        return _copy_string(library, self._handle(), "cna_audio_category_get_name_size",
                            "cna_audio_category_copy_name")

    def SetVolume(self, volume: float) -> None:
        value = f32(volume); library = get_library()
        library.check(library.cna_audio_category_set_volume(self._handle(), value),
                      "cna_audio_category_set_volume")
    def Pause(self) -> None:
        library = get_library(); library.check(library.cna_audio_category_pause(self._handle()),
                                               "cna_audio_category_pause")
    def Resume(self) -> None:
        library = get_library(); library.check(library.cna_audio_category_resume(self._handle()),
                                               "cna_audio_category_resume")
    def Stop(self, options: AudioStopOptions) -> None:
        if not isinstance(options, AudioStopOptions): raise TypeError("options must be AudioStopOptions")
        library = get_library(); library.check(
            library.cna_audio_category_stop(self._handle(), int(options)),
            "cna_audio_category_stop")
    def ToString(self) -> str: return "" if self._state is None else self.Name
    def Equals(self, other: object) -> bool:
        if not isinstance(other, AudioCategory): return False
        if self._state is None or other._state is None: return self._state is other._state
        if self._state.engine is not other._state.engine: return False
        output = c.c_uint8(); library = get_library()
        library.check(library.cna_audio_category_equals(
            self._handle(), other._handle(), c.byref(output)), "cna_audio_category_equals")
        return bool(output.value)
    def GetHashCode(self) -> int:
        if self._state is None: return 0
        output = c.c_int32(); library = get_library()
        library.check(library.cna_audio_category_get_hash_code(
            self._handle(), c.byref(output)), "cna_audio_category_get_hash_code")
        return wrap_int32(int(output.value) ^ hash(self._state.engine))
    def __eq__(self, other: object) -> bool: return self.Equals(other)
    def __ne__(self, other: object) -> bool: return not self.Equals(other)
    def __hash__(self) -> int: return self.GetHashCode()
    def __str__(self) -> str: return self.ToString()
    def __copy__(self) -> "AudioCategory":
        self_copy = AudioCategory(); self_copy._state = self._state; return self_copy
    def __deepcopy__(self, memo: object) -> "AudioCategory": return self.__copy__()


class AudioEngine:
    ContentVersion = 39
    Disposing = Event()

    def __init__(self, *args: object) -> None:
        if len(args) not in (1, 3):
            raise TypeError("AudioEngine expects settingsFile or settingsFile, lookAheadTime, rendererId")
        settings_bytes, settings_view, settings_path = _path(args[0], "settingsFile")
        with open(settings_path, "rb") as stream:
            prefix = stream.read(5)
        if len(prefix) <= 4 or prefix[:4] != b"XGSF":
            raise ValueError("audio settings file has an invalid content version")
        game, _, library, game_handle = _active_native(); output = c.c_uint64()
        if len(args) == 1:
            result = library.cna_audio_engine_create(game_handle, settings_view, c.byref(output))
            operation = "cna_audio_engine_create"
        else:
            ticks = _timedelta_ticks(args[1], "lookAheadTime")
            renderer_bytes, renderer_view = _string_view(args[2], "rendererId")
            result = library.cna_audio_engine_create_with_renderer(
                game_handle, settings_view, ticks, renderer_view, c.byref(output))
            operation = "cna_audio_engine_create_with_renderer"
            _ = renderer_bytes
        library.check(result, operation)
        _ = settings_bytes
        self._game = game
        self._native = NativeResource(int(output.value), Ownership.OWNED,
                                      _release("cna_audio_engine_destroy"))
        self._children: list[weakref.ReferenceType[object]] = []
        self._category_cache: dict[str, AudioCategory] = {}
        self._renderer_cache: tuple[RendererDetail, ...] | None = None
        game._register_native_child(self)

    def _register_child(self, child: object) -> None: self._children.append(weakref.ref(child))
    def _unregister_child(self, child: object) -> None:
        self._children = [value for value in self._children if value() not in (None, child)]
    def _require_handle(self) -> int: return self._native._require_handle()
    @property
    def IsDisposed(self) -> bool: return self._native.IsDisposed

    @property
    def RendererDetails(self) -> tuple[RendererDetail, ...]:
        self._require_handle()
        if self._renderer_cache is not None: return self._renderer_cache
        library = get_library(); count = c.c_uint64()
        library.check(library.cna_audio_engine_get_renderer_count(
            self._require_handle(), c.byref(count)), "cna_audio_engine_get_renderer_count")
        values = []
        for index in range(count.value):
            friendly = _copy_string(
                library, self._require_handle(),
                "cna_audio_engine_get_renderer_friendly_name_size",
                "cna_audio_engine_copy_renderer_friendly_name", index)
            renderer_id = _copy_string(
                library, self._require_handle(), "cna_audio_engine_get_renderer_id_size",
                "cna_audio_engine_copy_renderer_id", index)
            hash_code = c.c_int32()
            library.check(library.cna_audio_engine_get_renderer_hash_code(
                self._require_handle(), index, c.byref(hash_code)),
                "cna_audio_engine_get_renderer_hash_code")
            values.append(RendererDetail._from_native(friendly, renderer_id, int(hash_code.value)))
        self._renderer_cache = tuple(values)
        return self._renderer_cache

    def GetCategory(self, name: str) -> AudioCategory:
        encoded, view = _string_view(name, "name")
        cached = self._category_cache.get(name)
        if cached is not None:
            cached._handle(); return cached
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_audio_engine_get_category(
            self._require_handle(), view, c.byref(output)), "cna_audio_engine_get_category")
        _ = encoded
        state = _CategoryState(self, int(output.value))
        category = AudioCategory._from_state(state)
        self._category_cache[name] = category
        return category

    def GetGlobalVariable(self, name: str) -> float:
        encoded, view = _string_view(name, "name"); output = c.c_float(); library = get_library()
        library.check(library.cna_audio_engine_get_global_variable(
            self._require_handle(), view, c.byref(output)), "cna_audio_engine_get_global_variable")
        _ = encoded; return f32(output.value)
    def SetGlobalVariable(self, name: str, value: float) -> None:
        encoded, view = _string_view(name, "name"); narrowed = f32(value); library = get_library()
        library.check(library.cna_audio_engine_set_global_variable(
            self._require_handle(), view, narrowed), "cna_audio_engine_set_global_variable")
        _ = encoded
    def Update(self) -> None:
        library = get_library(); library.check(library.cna_audio_engine_update(self._require_handle()),
                                               "cna_audio_engine_update")

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        disposing = True if not args else args[0]
        if self.IsDisposed: return
        first_error: BaseException | None = None
        for reference in reversed(self._children):
            child = reference()
            if child is not None and not child.IsDisposed:
                try: child.Dispose()
                except BaseException as error: first_error = first_error or error
        if first_error is not None: raise first_error
        self._children.clear(); self._category_cache.clear()
        self._native.Dispose(); self._game._unregister_native_child(self)
        if disposing:
            self.Disposing(self, None)
    def __enter__(self) -> "AudioEngine": self._require_handle(); return self
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: self.Dispose()


class _XactResource:
    Disposing = Event()
    _destroy_operation = ""

    def _init_xact(self, engine: AudioEngine, handle: int) -> None:
        self._engine = engine
        self._native = NativeResource(handle, Ownership.OWNED,
                                      _release(self._destroy_operation))
        engine._register_child(self)
    def _require_handle(self) -> int:
        self._engine._require_handle(); return self._native._require_handle()
    @property
    def IsDisposed(self) -> bool: return self._native.IsDisposed
    def _before_release(self) -> None: return None
    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        disposing = True if not args else args[0]
        if self.IsDisposed: return
        self._before_release(); self._native.Dispose(); self._engine._unregister_child(self)
        if disposing:
            self.Disposing(self, None)
    def __enter__(self): self._require_handle(); return self
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: self.Dispose()


class WaveBank(_XactResource):
    _destroy_operation = "cna_wave_bank_destroy"
    def __init__(self, *args: object) -> None:
        if len(args) not in (2, 4):
            raise TypeError("WaveBank expects engine, filename or engine, filename, offset, packetsize")
        engine = args[0]
        if not isinstance(engine, AudioEngine): raise TypeError("audioEngine must be AudioEngine")
        filename_bytes, filename_view, _ = _path(args[1], "filename")
        output = c.c_uint64(); library = get_library()
        if len(args) == 2:
            result = library.cna_wave_bank_create(engine._require_handle(), filename_view, c.byref(output))
            operation = "cna_wave_bank_create"
        else:
            offset, packet = args[2], args[3]
            if isinstance(offset, bool) or not isinstance(offset, int): raise TypeError("offset must be Int32")
            if offset < -2_147_483_648 or offset > 2_147_483_647: raise OverflowError("offset is outside Int32")
            if isinstance(packet, bool) or not isinstance(packet, int): raise TypeError("packetsize must be Int16")
            if packet < -32768 or packet > 32767: raise OverflowError("packetsize is outside Int16")
            result = library.cna_wave_bank_create_streaming(
                engine._require_handle(), filename_view, offset, packet, c.byref(output))
            operation = "cna_wave_bank_create_streaming"
        library.check(result, operation); _ = filename_bytes
        self._init_xact(engine, int(output.value))
    def _flag(self, operation: str) -> bool:
        value = c.c_uint8(); library = get_library(); library.check(
            getattr(library, operation)(self._require_handle(), c.byref(value)), operation)
        return bool(value.value)
    @property
    def IsInUse(self) -> bool: return self._flag("cna_wave_bank_get_is_in_use")
    @property
    def IsPrepared(self) -> bool: return self._flag("cna_wave_bank_get_is_prepared")


class SoundBank(_XactResource):
    _destroy_operation = "cna_sound_bank_destroy"
    def __init__(self, audioEngine: AudioEngine, filename: str) -> None:
        if not isinstance(audioEngine, AudioEngine): raise TypeError("audioEngine must be AudioEngine")
        filename_bytes, filename_view, _ = _path(filename, "filename")
        output = c.c_uint64(); library = get_library(); library.check(
            library.cna_sound_bank_create(audioEngine._require_handle(), filename_view, c.byref(output)),
            "cna_sound_bank_create"); _ = filename_bytes
        self._cues: list[weakref.ReferenceType[Cue]] = []
        self._init_xact(audioEngine, int(output.value))
    @property
    def IsInUse(self) -> bool:
        value = c.c_uint8(); library = get_library(); library.check(
            library.cna_sound_bank_get_is_in_use(self._require_handle(), c.byref(value)),
            "cna_sound_bank_get_is_in_use"); return bool(value.value)
    def GetCue(self, name: str) -> "Cue":
        encoded, view = _string_view(name, "name"); output = c.c_uint64(); library = get_library()
        library.check(library.cna_sound_bank_get_cue(
            self._require_handle(), view, c.byref(output)), "cna_sound_bank_get_cue"); _ = encoded
        cue = Cue._from_handle(self, int(output.value)); self._cues.append(weakref.ref(cue)); return cue
    def PlayCue(self, *args: object) -> None:
        if len(args) not in (1, 3): raise TypeError("PlayCue expects name or name, listener, emitter")
        encoded, view = _string_view(args[0], "name"); library = get_library(); handle = self._require_handle()
        if len(args) == 1:
            result = library.cna_sound_bank_play_cue(handle, view)
            operation = "cna_sound_bank_play_cue"
        else:
            listener, emitter = _native_listener(args[1]), _native_emitter(args[2])
            result = library.cna_sound_bank_play_cue_3d(
                handle, view, c.byref(listener), c.byref(emitter))
            operation = "cna_sound_bank_play_cue_3d"
        library.check(result, operation); _ = encoded
    def _before_release(self) -> None:
        first_error: BaseException | None = None
        for reference in reversed(self._cues):
            cue = reference()
            if cue is not None and not cue.IsDisposed:
                try: cue.Dispose()
                except BaseException as error: first_error = first_error or error
        if first_error is not None: raise first_error
        self._cues.clear()


class Cue(_XactResource):
    _destroy_operation = "cna_cue_destroy"
    def __init__(self, *args: object) -> None:
        raise TypeError("Cue instances are returned by SoundBank.GetCue")
    @classmethod
    def _from_handle(cls, bank: SoundBank, handle: int) -> "Cue":
        self = cls.__new__(cls); self._bank_ref = weakref.ref(bank)
        self._init_xact(bank._engine, handle); return self
    def _info(self):
        value = abi.CNA_CueInfo(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_cue_get_info(
            self._require_handle(), c.byref(value)), "cna_cue_get_info"); return value
    @property
    def Name(self) -> str:
        return _copy_string(get_library(), self._require_handle(),
                            "cna_cue_get_name_size", "cna_cue_copy_name")
    @property
    def IsCreated(self) -> bool: return bool(self._info().is_created)
    @property
    def IsPreparing(self) -> bool: return bool(self._info().is_preparing)
    @property
    def IsPrepared(self) -> bool: return bool(self._info().is_prepared)
    @property
    def IsPlaying(self) -> bool: return bool(self._info().is_playing)
    @property
    def IsStopping(self) -> bool: return bool(self._info().is_stopping)
    @property
    def IsStopped(self) -> bool: return bool(self._info().is_stopped)
    @property
    def IsPaused(self) -> bool: return bool(self._info().is_paused)
    def Play(self) -> None: self._simple("cna_cue_play")
    def Pause(self) -> None: self._simple("cna_cue_pause")
    def Resume(self) -> None: self._simple("cna_cue_resume")
    def _simple(self, operation: str) -> None:
        library = get_library(); library.check(getattr(library, operation)(self._require_handle()), operation)
    def Stop(self, options: AudioStopOptions) -> None:
        if not isinstance(options, AudioStopOptions): raise TypeError("options must be AudioStopOptions")
        library = get_library(); library.check(library.cna_cue_stop(
            self._require_handle(), int(options)), "cna_cue_stop")
    def Apply3D(self, listener: AudioListener, emitter: AudioEmitter) -> None:
        native_listener, native_emitter = _native_listener(listener), _native_emitter(emitter)
        library = get_library(); library.check(library.cna_cue_apply_3d(
            self._require_handle(), c.byref(native_listener), c.byref(native_emitter)),
            "cna_cue_apply_3d")
    def GetVariable(self, name: str) -> float:
        encoded, view = _string_view(name, "name"); output = c.c_float(); library = get_library()
        library.check(library.cna_cue_get_variable(
            self._require_handle(), view, c.byref(output)), "cna_cue_get_variable")
        _ = encoded; return f32(output.value)
    def SetVariable(self, name: str, value: float) -> None:
        encoded, view = _string_view(name, "name"); narrowed = f32(value); library = get_library()
        library.check(library.cna_cue_set_variable(
            self._require_handle(), view, narrowed), "cna_cue_set_variable"); _ = encoded
    def Dispose(self) -> None:
        if self.IsDisposed: return
        bank = self._bank_ref()
        super().Dispose()
        if bank is not None:
            bank._cues = [value for value in bank._cues if value() not in (None, self)]


RendererDetail.__xna_arities__ = {
    "GetHashCode": {0}, "ToString": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1},
}
AudioCategory.__xna_arities__ = {
    "__init__": {0}, "SetVolume": {1}, "Pause": {0}, "Resume": {0}, "Stop": {1},
    "ToString": {0}, "Equals": {1}, "GetHashCode": {0}, "__eq__": {1}, "__ne__": {1},
}
AudioEngine.__xna_arities__ = {
    "__init__": {1, 3}, "GetCategory": {1}, "GetGlobalVariable": {1},
    "SetGlobalVariable": {2}, "Update": {0}, "Dispose": {0, 1},
}
WaveBank.__xna_arities__ = {"__init__": {2, 4}, "Dispose": {0, 1}}
SoundBank.__xna_arities__ = {
    "__init__": {2}, "GetCue": {1}, "PlayCue": {1, 3}, "Dispose": {0, 1},
}
Cue.__xna_arities__ = {
    "Play": {0}, "Pause": {0}, "Resume": {0}, "Stop": {1},
    "GetVariable": {1}, "SetVariable": {2}, "Apply3D": {2}, "Dispose": {0},
}
