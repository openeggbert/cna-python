"""Deterministic dynamic loader for the exact CNA 0.7.0 C ABI."""

from __future__ import annotations

import ctypes as c
import os
from pathlib import Path
import sys
from threading import RLock

from . import abi
from .errors import NativeAbiMismatchError, NativeError, NativeLibraryError, NativeUnavailableError

EXPECTED_ABI = 0x00000700

_NAMES = {
    "win32": ("cna_c_api.dll",),
    "darwin": ("libcna_c_api.dylib",),
}.get(sys.platform, ("libcna_c_api.so",))


FUNCTION_MANIFEST: tuple[tuple[str, object, list[object], str], ...] = (
    ("cna_get_abi_version", c.c_uint32, [], "borrowed library"),
    ("cna_error_get_last_info", c.c_uint32, [c.POINTER(abi.CNA_ErrorInfo)], "caller output"),
    ("cna_error_get_last_message_size", c.c_uint32, [c.POINTER(c.c_uint64)], "caller output"),
    ("cna_error_copy_last_message", c.c_uint32, [c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_create", c.c_uint32, [c.POINTER(abi.CNA_GameCreateInfo), c.POINTER(c.c_uint64)], "owned game"),
    ("cna_game_set_frame_hooks_ext", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_GameFrameHooks)], "copied callbacks"),
    ("cna_game_run", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_game_run_one_frame", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_game_request_exit", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_game_get_is_active", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_game_get_is_mouse_visible", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_game_set_is_mouse_visible", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed game"),
    ("cna_game_get_is_fixed_time_step", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_game_set_is_fixed_time_step", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed game"),
    ("cna_game_get_target_elapsed_time_ticks", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_game_set_target_elapsed_time_ticks", c.c_uint32, [c.c_uint64, c.c_int64], "borrowed game"),
    ("cna_game_get_inactive_sleep_time_ticks", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_game_set_inactive_sleep_time_ticks", c.c_uint32, [c.c_uint64, c.c_int64], "borrowed game"),
    ("cna_game_destroy", c.c_uint32, [c.c_uint64], "consumes game on release"),
    ("cna_framework_dispatcher_update", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_graphics_device_manager_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned manager"),
    ("cna_graphics_device_manager_set_graphics_profile", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed manager"),
    ("cna_graphics_device_manager_set_preferred_depth_stencil_format", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed manager"),
    ("cna_graphics_device_manager_set_preferred_back_buffer_format", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed manager"),
    ("cna_graphics_device_manager_set_preferred_back_buffer_width", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed manager"),
    ("cna_graphics_device_manager_set_preferred_back_buffer_height", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed manager"),
    ("cna_graphics_device_manager_set_is_full_screen", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed manager"),
    ("cna_graphics_device_manager_set_synchronize_with_vertical_retrace", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed manager"),
    ("cna_graphics_device_manager_set_prefer_multi_sampling", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed manager"),
    ("cna_graphics_device_manager_set_supported_orientations", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed manager"),
    ("cna_graphics_device_manager_apply_changes", c.c_uint32, [c.c_uint64], "borrowed manager"),
    ("cna_graphics_device_manager_toggle_full_screen", c.c_uint32, [c.c_uint64], "borrowed manager"),
    ("cna_graphics_device_manager_get_graphics_device", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "callback-borrowed device"),
    ("cna_graphics_device_manager_destroy", c.c_uint32, [c.c_uint64], "consumes manager"),
    ("cna_game_get_graphics_device", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "callback-borrowed device"),
    ("cna_viewport_get_title_safe_area", c.c_uint32, [abi.CNA_Viewport, c.POINTER(abi.CNA_Rectangle)], "caller output"),
    ("cna_graphics_device_get_viewport", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Viewport)], "caller output"),
    ("cna_graphics_device_set_viewport", c.c_uint32, [c.c_uint64, abi.CNA_Viewport], "borrowed device"),
    ("cna_graphics_device_clear_rgba", c.c_uint32, [c.c_uint64, c.c_float, c.c_float, c.c_float, c.c_float], "borrowed device"),
    ("cna_texture2d_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture2DCreateInfo), c.POINTER(c.c_uint64)], "owned texture"),
    ("cna_texture2d_create_from_encoded_memory", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(abi.CNA_Texture2DDecodeInfo), c.POINTER(c.c_uint64)], "owned texture"),
    ("cna_texture2d_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture2DInfo)], "caller output"),
    ("cna_texture2d_set_data", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_Texture2DTransfer), c.c_void_p, c.c_uint64], "copies elements"),
    ("cna_texture2d_get_data", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_Texture2DTransfer), c.c_void_p, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_texture2d_destroy", c.c_uint32, [c.c_uint64], "consumes texture"),
    ("cna_sprite_batch_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned sprite batch"),
    ("cna_sprite_batch_begin", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteBatchBeginInfo)], "borrowed sprite batch"),
    ("cna_sprite_batch_submit_scaled_many", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteScaledCommand), c.c_uint64], "copies commands"),
    ("cna_sprite_batch_end", c.c_uint32, [c.c_uint64], "borrowed sprite batch"),
    ("cna_sprite_batch_destroy", c.c_uint32, [c.c_uint64], "consumes sprite batch"),
    ("cna_keyboard_get_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_KeyboardState)], "caller output"),
    ("cna_keyboard_get_state_for_player", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_KeyboardState)], "caller output"),
    ("cna_mouse_get_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_MouseState)], "caller output"),
    ("cna_mouse_set_position", c.c_uint32, [c.c_uint64, c.c_int32, c.c_int32], "borrowed game"),
    ("cna_gamepad_get_state_with_dead_zone", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.POINTER(abi.CNA_GamePadState)], "caller output"),
)


def _resolve() -> Path:
    explicit = os.environ.get("CNA_NATIVE_LIBRARY")
    if explicit is not None:
        path = Path(explicit)
        if not path.is_absolute():
            raise NativeLibraryError("CNA_NATIVE_LIBRARY must name an absolute file")
        if not path.is_file():
            raise NativeUnavailableError(f"CNA_NATIVE_LIBRARY does not name an existing file: {path}")
        return path
    directory_value = os.environ.get("CNA_NATIVE_DIR")
    if directory_value is not None:
        directory = Path(directory_value)
        if not directory.is_absolute():
            raise NativeLibraryError("CNA_NATIVE_DIR must name an absolute directory")
        if not directory.is_dir():
            raise NativeUnavailableError(f"CNA_NATIVE_DIR does not name an existing directory: {directory}")
        for name in _NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        raise NativeUnavailableError(f"CNA_NATIVE_DIR contains none of the expected library names {_NAMES}: {directory}")
    package_native = Path(__file__).resolve().parent / "native"
    for name in _NAMES:
        candidate = package_native / name
        if candidate.is_file():
            return candidate
    raise NativeUnavailableError(
        "CNA native library is not configured; set CNA_NATIVE_LIBRARY to the absolute ABI-0.7.0 library file "
        "or CNA_NATIVE_DIR to its absolute directory"
    )


class NativeLibrary:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self._cdll = c.CDLL(str(path))
        except OSError as error:
            raise NativeUnavailableError(f"failed to load CNA C ABI library {path}: {error}") from error
        version_symbol, version_restype, version_argtypes, _ = FUNCTION_MANIFEST[0]
        try:
            version_function = getattr(self._cdll, version_symbol)
        except AttributeError as error:
            raise NativeLibraryError(f"CNA library {path} has no cna_get_abi_version symbol") from error
        version_function.restype, version_function.argtypes = version_restype, version_argtypes
        setattr(self, version_symbol, version_function)
        actual = int(version_function())
        if actual != EXPECTED_ABI:
            raise NativeAbiMismatchError(EXPECTED_ABI, actual, str(path))
        for symbol, restype, argtypes, _ownership in FUNCTION_MANIFEST[1:]:
            try:
                function = getattr(self._cdll, symbol)
            except AttributeError as error:
                raise NativeLibraryError(f"CNA ABI 0.7.0 library {path} is missing required symbol {symbol}") from error
            function.restype = restype
            function.argtypes = argtypes
            setattr(self, symbol, function)

    def _last_error(self) -> tuple[int | None, str]:
        info = abi.CNA_ErrorInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        category = None
        if self.cna_error_get_last_info(c.byref(info)) == 0:
            category = int(info.category)
        size = c.c_uint64()
        if self.cna_error_get_last_message_size(c.byref(size)) != 0 or size.value == 0:
            return category, ""
        buffer = c.create_string_buffer(size.value)
        written = c.c_uint64()
        if self.cna_error_copy_last_message(buffer, size.value, c.byref(written)) != 0:
            return category, ""
        return category, bytes(buffer.raw[:written.value]).decode("utf-8", errors="replace")

    def check(self, result: int, operation: str, *, context: str | None = None) -> None:
        if result == 0:
            return
        category, message = self._last_error()
        raise NativeError(operation, int(result), category, message, context)


_lock = RLock()
_library: NativeLibrary | None = None


def get_library() -> NativeLibrary:
    global _library
    with _lock:
        if _library is None:
            _library = NativeLibrary(_resolve())
        return _library


def require_available() -> NativeLibrary:
    return get_library()


def _reset_for_tests() -> None:
    global _library
    with _lock:
        _library = None
