"""Reviewed ctypes layouts for the bound CNA ABI-0.7 runtime/2D slice."""

from __future__ import annotations

import ctypes as c

CNA_Result = c.c_uint32
CNA_Bool = c.c_uint8
CNA_Handle = c.c_uint64


class CNA_StringView(c.Structure):
    _fields_ = [("data", c.c_char_p), ("byte_length", c.c_uint64)]


class CNA_ErrorInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("result", c.c_uint32), ("category", c.c_uint32),
        ("message_byte_length", c.c_uint64),
    ]


class CNA_GameTime(c.Structure):
    _fields_ = [
        ("total_game_time_ticks", c.c_int64), ("elapsed_game_time_ticks", c.c_int64),
        ("is_running_slowly", c.c_uint8), ("reserved", c.c_uint8 * 7),
    ]


class CNA_CallbackError(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("message", CNA_StringView),
    ]


CNA_GameLifecycleCallback = c.CFUNCTYPE(
    c.c_uint32, c.c_uint64, c.POINTER(CNA_GameTime), c.c_void_p, c.POINTER(CNA_CallbackError)
)
CNA_GameBeginDrawCallback = c.CFUNCTYPE(
    c.c_uint32, c.c_uint64, c.POINTER(CNA_GameTime), c.c_void_p,
    c.POINTER(c.c_uint8), c.POINTER(CNA_CallbackError)
)


class CNA_GameCallbacks(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("load_content", CNA_GameLifecycleCallback), ("update", CNA_GameLifecycleCallback),
        ("draw", CNA_GameLifecycleCallback), ("unload_content", CNA_GameLifecycleCallback),
        ("exiting", CNA_GameLifecycleCallback), ("context", c.c_void_p),
    ]


class CNA_GameFrameHooks(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("initialize", CNA_GameLifecycleCallback), ("begin_run", CNA_GameLifecycleCallback),
        ("end_run", CNA_GameLifecycleCallback), ("begin_draw", CNA_GameBeginDrawCallback),
        ("end_draw", CNA_GameLifecycleCallback), ("context", c.c_void_p),
    ]


class CNA_GameCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("is_fixed_time_step", c.c_uint8), ("reserved", c.c_uint8 * 7),
        ("target_elapsed_time_ticks", c.c_int64), ("window_title", CNA_StringView),
        ("callbacks", c.POINTER(CNA_GameCallbacks)),
    ]


class CNA_Color(c.Structure):
    _fields_ = [("r", c.c_uint8), ("g", c.c_uint8), ("b", c.c_uint8), ("a", c.c_uint8)]


class CNA_Vector2(c.Structure):
    _fields_ = [("x", c.c_float), ("y", c.c_float)]


class CNA_Rectangle(c.Structure):
    _fields_ = [("x", c.c_int32), ("y", c.c_int32), ("width", c.c_int32), ("height", c.c_int32)]


class CNA_Viewport(c.Structure):
    _fields_ = [
        ("x", c.c_int32), ("y", c.c_int32), ("width", c.c_int32), ("height", c.c_int32),
        ("min_depth", c.c_float), ("max_depth", c.c_float),
    ]


class CNA_Texture2DInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("level_count", c.c_uint32),
        ("format", c.c_uint32),
    ]


class CNA_Texture2DCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("mip_map", c.c_uint8),
        ("reserved", c.c_uint8 * 3), ("format", c.c_uint32),
    ]


class CNA_Texture2DTransfer(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("level", c.c_int32), ("has_rectangle", c.c_uint8), ("reserved", c.c_uint8 * 3),
        ("rectangle", CNA_Rectangle), ("start_index", c.c_uint64),
        ("element_count", c.c_uint64),
    ]


class CNA_Texture2DDecodeInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("zoom", c.c_uint8),
        ("reserved", c.c_uint8 * 7),
    ]


class CNA_SpriteBatchBeginInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("sort_mode", c.c_uint32), ("reserved", c.c_uint32),
    ]


class CNA_SpriteScaledCommand(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("texture", c.c_uint64), ("position", CNA_Vector2), ("source", CNA_Rectangle),
        ("color", CNA_Color), ("rotation", c.c_float), ("origin", CNA_Vector2),
        ("scale", CNA_Vector2), ("effects", c.c_uint32), ("layer_depth", c.c_float),
    ]


class CNA_KeyboardState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("pressed_key_words", c.c_uint64 * 4),
    ]


class CNA_MouseState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("x", c.c_int32), ("y", c.c_int32), ("scroll_wheel", c.c_int32),
        ("horizontal_scroll_wheel", c.c_int32), ("pressed_buttons", c.c_uint32),
        ("reserved", c.c_uint32),
    ]


class CNA_GamePadAnalogState(c.Structure):
    _fields_ = [
        ("left_thumb_stick", CNA_Vector2), ("right_thumb_stick", CNA_Vector2),
        ("left_trigger", c.c_float), ("right_trigger", c.c_float),
    ]


class CNA_GamePadState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("is_connected", c.c_uint8), ("reserved0", c.c_uint8 * 3),
        ("packet_number", c.c_int32), ("pressed_buttons", c.c_uint32),
        ("reserved1", c.c_uint32), ("analog", CNA_GamePadAnalogState),
    ]
