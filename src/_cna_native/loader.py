"""Deterministic dynamic loader for the qualified CNA C ABI generation.

CNA's own contract (`docs/c-api/ABI_VERSIONING.md`) states that ABI `0.x` is
experimental, that a consumer "must reject a different major and may require a
minimum minor", and that within `0.x` **an incompatible change requires a
minor-version increment**.  A minor therefore names one compatibility
generation, and a patch inside it cannot change a contract.

CNA-Python supports exactly one generation: the one it qualifies against.  It is
not multiplexed across generations, because a single ctypes manifest cannot be
truthful for two `0.x` minors that are permitted to differ incompatibly, and
because no artifact of the historical `0.7.0` generation still exists to test
against.  Accepting a different minor would be an unverified claim.
"""

from __future__ import annotations

import ctypes as c
import os
from pathlib import Path
import sys
from threading import RLock

from . import abi
from .errors import NativeAbiMismatchError, NativeError, NativeLibraryError, NativeUnavailableError
from .cnb_manifest import (
    CNB_FUNCTION_MANIFEST,
    CURVE_CODEC_FUNCTION_MANIFEST,
    NATIVE_CONTENT_MANAGER_FUNCTION_MANIFEST,
)
from .engine_manifest import ENGINE_FUNCTION_MANIFEST
from .media_manifest import MEDIA_FUNCTION_MANIFEST

SUPPORTED_ABI_MAJOR = 0
SUPPORTED_ABI_MINOR = 21

#: The exact encoded ABI this binding is qualified against.  Patch releases
#: inside :data:`SUPPORTED_ABI_MINOR` are accepted; a different minor is not.
QUALIFIED_ABI = (
    (SUPPORTED_ABI_MAJOR & 0xFFFF) << 16 | (SUPPORTED_ABI_MINOR & 0xFF) << 8 | 0
)

#: Retained for callers that import the historical name.
EXPECTED_ABI = QUALIFIED_ABI


def decode_abi(version: int) -> tuple[int, int, int]:
    """Splits an encoded CNA ABI version into ``(major, minor, patch)``."""
    return (version >> 16) & 0xFFFF, (version >> 8) & 0xFF, version & 0xFF


def format_abi(version: int) -> str:
    major, minor, patch = decode_abi(version)
    return f"{major}.{minor}.{patch}"


def abi_is_supported(version: int) -> bool:
    """Reports whether an encoded ABI version is the supported generation."""
    major, minor, _patch = decode_abi(version)
    return major == SUPPORTED_ABI_MAJOR and minor == SUPPORTED_ABI_MINOR

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
    ("cna_game_reset_elapsed_time", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_game_suppress_draw", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_game_subscribe", c.c_uint32, [c.c_uint64, c.c_uint32, abi.CNA_GameEventCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_game_unsubscribe", c.c_uint32, [c.c_uint64], "consumes registration"),
    ("cna_game_launch_parameters_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_launch_parameters_get_value_size", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_launch_parameters_copy_value", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_launch_parameters_get_key_size", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_launch_parameters_copy_key", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_launch_parameters_add", c.c_uint32, [c.c_uint64, abi.CNA_StringView, abi.CNA_StringView], "borrowed game"),
    ("cna_game_set_window_title", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed game"),
    ("cna_title_location_set_path_ext", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed game; process-wide title path"),
    ("cna_title_container_read_ext", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_window_get_allow_user_resizing", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_game_window_set_allow_user_resizing", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed game"),
    ("cna_game_window_get_client_bounds", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Rectangle)], "caller output"),
    ("cna_game_window_get_current_orientation", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_game_window_get_native_handle_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_window_get_screen_device_name_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_window_copy_screen_device_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_window_get_title_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_window_copy_title", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_game_window_begin_screen_device_change", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed game"),
    ("cna_game_window_end_screen_device_change", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_int32, c.c_int32], "borrowed game"),
    ("cna_game_window_subscribe", c.c_uint32, [c.c_uint64, c.c_uint32, abi.CNA_GameEventCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
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
    # Renderer identity. Runtime capability evidence must name the renderer that
    # actually ran, so a measurement is never attributed to the wrong backend.
    ("cna_graphics_renderer_get_selected_ext", c.c_uint32, [c.POINTER(c.c_uint32)], "caller output"),
    ("cna_graphics_renderer_get_active_ext", c.c_uint32, [c.POINTER(c.c_uint32)], "caller output"),
    ("cna_graphics_renderer_get_is_latched_ext", c.c_uint32, [c.POINTER(c.c_uint8)], "caller output"),
    ("cna_graphics_renderer_get_current_name_size", c.c_uint32, [c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_copy_current_name", c.c_uint32, [c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    # Renderer selection and fallback reporting, consumed by cna.extensions.graphics.
    ("cna_graphics_renderer_get_current_type", c.c_uint32, [c.POINTER(c.c_uint32)], "caller output"),
    ("cna_graphics_renderer_get_available_count_ext", c.c_uint32, [c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_copy_available_ext", c.c_uint32, [c.POINTER(c.c_uint32), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_get_is_available_ext", c.c_uint32, [c.c_uint32, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_graphics_renderer_try_parse_name_ext", c.c_uint32, [abi.CNA_StringView, c.POINTER(c.c_uint32), c.POINTER(c.c_uint8)], "caller output"),
    ("cna_graphics_renderer_set_preferred_ext", c.c_uint32, [c.c_uint32], "process-wide selection"),
    ("cna_graphics_renderer_set_preferred_by_name_ext", c.c_uint32, [abi.CNA_StringView], "process-wide selection"),
    ("cna_graphics_renderer_set_fallback_chain_ext", c.c_uint32, [c.POINTER(c.c_uint32), c.c_uint64], "copies the chain; process-wide selection"),
    ("cna_graphics_renderer_set_automatic_fallback_ext", c.c_uint32, [c.c_uint8], "process-wide selection"),
    ("cna_graphics_renderer_get_automatic_fallback_ext", c.c_uint32, [c.POINTER(c.c_uint8)], "caller output"),
    ("cna_graphics_renderer_get_fallback_count_ext", c.c_uint32, [c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_get_fallback_at_ext", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_GraphicsRendererFallbackRecord)], "caller output"),
    ("cna_graphics_renderer_fallback_get_message_size_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_fallback_copy_message_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_fallback_reason_get_name_size_ext", c.c_uint32, [c.c_uint32, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_renderer_fallback_reason_copy_name_ext", c.c_uint32, [c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    # XNA Audio + XACT.  Every callback is the canonical
    # ``void(void*)`` observer and every submitted PCM buffer is copied.
    ("cna_sound_effect_create_pcm16_range_ext", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SoundEffectCreateInfo), c.POINTER(c.c_uint8), c.c_uint64, c.c_int32, c.c_int32, c.c_int32, c.c_int32, c.POINTER(c.c_uint64)], "copies PCM; owned SoundEffect"),
    ("cna_sound_effect_create_from_encoded_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)], "copies encoded bytes; owned SoundEffect"),
    ("cna_sound_effect_get_duration_ticks", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_sound_effect_get_name_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_sound_effect_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_sound_effect_set_name", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "copies name"),
    ("cna_sound_effect_create_instance", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned SoundEffectInstance child"),
    ("cna_sound_effect_destroy", c.c_uint32, [c.c_uint64], "consumes SoundEffect"),
    ("cna_sound_effect_play", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "borrowed SoundEffect"),
    ("cna_sound_effect_play_with_settings", c.c_uint32, [c.c_uint64, c.c_float, c.c_float, c.c_float, c.POINTER(c.c_uint8)], "borrowed SoundEffect"),
    ("cna_sound_effect_get_master_volume", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "process-global output"),
    ("cna_sound_effect_set_master_volume", c.c_uint32, [c.c_uint64, c.c_float], "process-global setting"),
    ("cna_sound_effect_get_distance_scale", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "process-global output"),
    ("cna_sound_effect_set_distance_scale", c.c_uint32, [c.c_uint64, c.c_float], "process-global setting"),
    ("cna_sound_effect_get_doppler_scale", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "process-global output"),
    ("cna_sound_effect_set_doppler_scale", c.c_uint32, [c.c_uint64, c.c_float], "process-global setting"),
    ("cna_sound_effect_get_speed_of_sound", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "process-global output"),
    ("cna_sound_effect_set_speed_of_sound", c.c_uint32, [c.c_uint64, c.c_float], "process-global setting"),
    ("cna_sound_effect_instance_destroy", c.c_uint32, [c.c_uint64], "consumes SoundEffectInstance"),
    ("cna_sound_effect_instance_play", c.c_uint32, [c.c_uint64], "borrowed instance"),
    ("cna_sound_effect_instance_pause", c.c_uint32, [c.c_uint64], "borrowed instance"),
    ("cna_sound_effect_instance_resume", c.c_uint32, [c.c_uint64], "borrowed instance"),
    ("cna_sound_effect_instance_stop", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed instance"),
    ("cna_sound_effect_instance_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SoundEffectInstanceInfo)], "caller output"),
    ("cna_sound_effect_instance_set_volume", c.c_uint32, [c.c_uint64, c.c_float], "borrowed instance"),
    ("cna_sound_effect_instance_set_pitch", c.c_uint32, [c.c_uint64, c.c_float], "borrowed instance"),
    ("cna_sound_effect_instance_set_pan", c.c_uint32, [c.c_uint64, c.c_float], "borrowed instance"),
    ("cna_sound_effect_instance_set_is_looped", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed instance"),
    ("cna_sound_effect_instance_apply_3d", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_AudioListener), c.POINTER(abi.CNA_AudioEmitter)], "copies listener/emitter"),
    ("cna_sound_effect_instance_apply_3d_multi_ext", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_AudioListener), c.c_uint64, c.POINTER(abi.CNA_AudioEmitter)], "copies listeners/emitter; any positive listener count since ABI 0.9"),
    ("cna_dynamic_sound_effect_instance_create", c.c_uint32, [c.c_uint64, c.c_int32, c.c_uint32, c.POINTER(c.c_uint64)], "owned dynamic instance child"),
    ("cna_dynamic_sound_effect_instance_get_pending_buffer_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_dynamic_sound_effect_instance_submit_buffer", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.c_int32, c.c_int32], "copies PCM buffer"),
    ("cna_dynamic_sound_effect_instance_get_sample_duration_ticks", c.c_uint32, [c.c_uint64, c.c_int32, c.POINTER(c.c_int64)], "caller output"),
    ("cna_dynamic_sound_effect_instance_get_sample_size_in_bytes", c.c_uint32, [c.c_uint64, c.c_int64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_dynamic_sound_effect_instance_subscribe_buffer_needed", c.c_uint32, [c.c_uint64, abi.CNA_AudioEventCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned callback registration"),
    ("cna_microphone_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_microphone_get_default_index_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64), c.POINTER(c.c_uint8)], "caller output"),
    ("cna_microphone_get_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_microphone_copy_name_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_microphone_get_buffer_duration_ticks_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_microphone_set_buffer_duration_ticks_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_int64], "borrowed microphone index"),
    ("cna_microphone_get_is_headset_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_microphone_get_sample_rate_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_microphone_get_state_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_microphone_start_at", c.c_uint32, [c.c_uint64, c.c_uint64], "borrowed microphone index"),
    ("cna_microphone_stop_at", c.c_uint32, [c.c_uint64, c.c_uint64], "borrowed microphone index"),
    ("cna_microphone_get_data_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_microphone_get_sample_duration_ticks_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_int32, c.POINTER(c.c_int64)], "caller output"),
    ("cna_microphone_get_sample_size_in_bytes_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_int64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_microphone_subscribe_buffer_ready_at", c.c_uint32, [c.c_uint64, c.c_uint64, abi.CNA_AudioEventCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned callback registration"),
    ("cna_audio_unsubscribe_ext", c.c_uint32, [c.c_uint64], "consumes audio registration"),
    ("cna_audio_engine_create", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned AudioEngine child"),
    ("cna_audio_engine_create_with_renderer", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_int64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned AudioEngine child; renderer/look-ahead accepted but ignored"),
    ("cna_audio_engine_destroy", c.c_uint32, [c.c_uint64], "consumes AudioEngine"),
    ("cna_audio_engine_update", c.c_uint32, [c.c_uint64], "borrowed AudioEngine"),
    ("cna_audio_engine_get_global_variable", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_float)], "caller output"),
    ("cna_audio_engine_set_global_variable", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_float], "borrowed AudioEngine"),
    ("cna_audio_engine_get_category", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned category C facade"),
    ("cna_audio_engine_get_renderer_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_engine_get_renderer_friendly_name_size", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_engine_copy_renderer_friendly_name", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_engine_get_renderer_id_size", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_engine_copy_renderer_id", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_engine_get_renderer_hash_code", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_audio_category_destroy", c.c_uint32, [c.c_uint64], "consumes category C facade"),
    ("cna_audio_category_get_name_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_category_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_audio_category_pause", c.c_uint32, [c.c_uint64], "borrowed category"),
    ("cna_audio_category_resume", c.c_uint32, [c.c_uint64], "borrowed category"),
    ("cna_audio_category_set_volume", c.c_uint32, [c.c_uint64, c.c_float], "borrowed category"),
    ("cna_audio_category_stop", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed category"),
    ("cna_audio_category_equals", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_audio_category_get_hash_code", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_wave_bank_create", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned WaveBank child"),
    ("cna_wave_bank_create_streaming", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_int32, c.c_int16, c.POINTER(c.c_uint64)], "owned streaming WaveBank child"),
    ("cna_wave_bank_destroy", c.c_uint32, [c.c_uint64], "consumes WaveBank"),
    ("cna_wave_bank_get_is_prepared", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_wave_bank_get_is_in_use", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_sound_bank_create", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned SoundBank child"),
    ("cna_sound_bank_destroy", c.c_uint32, [c.c_uint64], "consumes SoundBank"),
    ("cna_sound_bank_get_is_in_use", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_sound_bank_get_cue", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned Cue child"),
    ("cna_sound_bank_play_cue", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed SoundBank"),
    ("cna_sound_bank_play_cue_3d", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(abi.CNA_AudioListener), c.POINTER(abi.CNA_AudioEmitter)], "copies listener/emitter"),
    ("cna_cue_destroy", c.c_uint32, [c.c_uint64], "consumes Cue"),
    ("cna_cue_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_CueInfo)], "caller output"),
    ("cna_cue_get_name_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_cue_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_cue_apply_3d", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_AudioListener), c.POINTER(abi.CNA_AudioEmitter)], "copies listener/emitter"),
    ("cna_cue_get_variable", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_float)], "caller output"),
    ("cna_cue_set_variable", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_float], "borrowed Cue"),
    ("cna_cue_play", c.c_uint32, [c.c_uint64], "borrowed Cue"),
    ("cna_cue_pause", c.c_uint32, [c.c_uint64], "borrowed Cue"),
    ("cna_cue_resume", c.c_uint32, [c.c_uint64], "borrowed Cue"),
    ("cna_cue_stop", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed Cue"),
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
    ("cna_graphics_device_manager_create_device", c.c_uint32, [c.c_uint64], "borrowed manager"),
    ("cna_graphics_device_manager_begin_draw", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "borrowed manager"),
    ("cna_graphics_device_manager_end_draw", c.c_uint32, [c.c_uint64], "borrowed manager"),
    ("cna_graphics_device_manager_dispose", c.c_uint32, [c.c_uint64], "borrowed manager"),
    ("cna_graphics_device_manager_subscribe", c.c_uint32, [c.c_uint64, c.c_uint32, abi.CNA_GameEventCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_graphics_device_manager_subscribe_preparing_device_settings_ext", c.c_uint32, [c.c_uint64, abi.CNA_PreparingDeviceSettingsMutatorEXT, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_graphics_device_manager_get_graphics_device", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "callback-borrowed device"),
    ("cna_graphics_device_manager_destroy", c.c_uint32, [c.c_uint64], "consumes manager"),
    ("cna_game_get_graphics_device", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "callback-borrowed device"),
    ("cna_graphics_adapter_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_adapter_get_info", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_GraphicsAdapterInfo)], "caller output"),
    ("cna_graphics_adapter_copy_description", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_adapter_copy_device_name", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_adapter_get_current_display_mode", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_DisplayMode)], "caller output"),
    ("cna_graphics_adapter_get_display_mode_count", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint8, c.c_uint32, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_adapter_copy_display_modes", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint8, c.c_uint32, c.POINTER(abi.CNA_DisplayMode), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_adapter_set_device_preferences", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint8, c.c_uint8], "borrowed adapter"),
    ("cna_graphics_adapter_is_profile_supported", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_graphics_adapter_query_render_target_format", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.c_uint32, c.c_uint32, c.c_int32, c.POINTER(abi.CNA_GraphicsFormatSelection)], "caller output"),
    ("cna_graphics_adapter_query_backbuffer_format", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.c_uint32, c.c_uint32, c.c_int32, c.POINTER(abi.CNA_GraphicsFormatSelection)], "caller output"),
    ("cna_graphics_device_get_presentation_parameters", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_PresentationParameters)], "caller output"),
    ("cna_graphics_device_get_display_mode", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_DisplayMode)], "caller output"),
    ("cna_viewport_get_title_safe_area", c.c_uint32, [abi.CNA_Viewport, c.POINTER(abi.CNA_Rectangle)], "caller output"),
    ("cna_graphics_device_get_viewport", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Viewport)], "caller output"),
    ("cna_graphics_device_set_viewport", c.c_uint32, [c.c_uint64, abi.CNA_Viewport], "borrowed device"),
    ("cna_graphics_device_get_blend_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_BlendState)], "caller output"),
    ("cna_graphics_device_set_blend_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_BlendState)], "copies descriptor"),
    ("cna_graphics_device_get_depth_stencil_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_DepthStencilState)], "caller output"),
    ("cna_graphics_device_set_depth_stencil_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_DepthStencilState)], "copies descriptor"),
    ("cna_graphics_device_get_rasterizer_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RasterizerState)], "caller output"),
    ("cna_graphics_device_set_rasterizer_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RasterizerState)], "copies descriptor"),
    ("cna_graphics_device_get_sampler_state", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.POINTER(abi.CNA_SamplerState)], "caller output"),
    ("cna_graphics_device_set_sampler_state", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.POINTER(abi.CNA_SamplerState)], "copies descriptor"),
    ("cna_graphics_device_get_texture", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.POINTER(abi.CNA_TextureSlotInfo)], "caller output"),
    ("cna_graphics_device_set_texture", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.c_uint64], "borrows texture"),
    ("cna_graphics_device_unbind_texture", c.c_uint32, [c.c_uint64, c.c_uint64], "borrows device and texture"),
    ("cna_graphics_device_get_status", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_graphics_device_get_adapter_index", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_graphics_device_get_graphics_profile", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_graphics_device_get_scissor_rectangle", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Rectangle)], "caller output"),
    ("cna_graphics_device_set_scissor_rectangle", c.c_uint32, [c.c_uint64, abi.CNA_Rectangle], "borrowed device"),
    ("cna_graphics_device_get_blend_factor", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Color)], "caller output"),
    ("cna_graphics_device_set_blend_factor", c.c_uint32, [c.c_uint64, abi.CNA_Color], "borrowed device"),
    ("cna_graphics_device_get_multi_sample_mask", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_graphics_device_set_multi_sample_mask", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed device"),
    ("cna_graphics_device_get_reference_stencil", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_graphics_device_set_reference_stencil", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed device"),
    ("cna_graphics_device_clear_options", c.c_uint32, [c.c_uint64, c.c_uint32, abi.CNA_Color, c.c_float, c.c_int32], "borrowed device"),
    ("cna_graphics_device_create", c.c_uint32, [c.c_uint32, c.c_uint32, c.POINTER(abi.CNA_PresentationParameters), c.POINTER(c.c_uint64)], "owned GraphicsDevice"),
    ("cna_graphics_device_destroy", c.c_uint32, [c.c_uint64], "consumes a caller-created GraphicsDevice"),
    ("cna_graphics_device_present", c.c_uint32, [c.c_uint64], "borrowed device"),
    ("cna_graphics_device_reset", c.c_uint32, [c.c_uint64], "borrowed device"),
    ("cna_graphics_device_reset_with_parameters", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_PresentationParameters), c.POINTER(c.c_uint32)], "borrowed device"),
    ("cna_graphics_device_subscribe_event", c.c_uint32, [c.c_uint64, c.c_uint32, abi.CNA_GraphicsDeviceEventCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_graphics_device_unsubscribe", c.c_uint32, [c.c_uint64], "consumes registration"),
    ("cna_graphics_device_clear_rgba", c.c_uint32, [c.c_uint64, c.c_float, c.c_float, c.c_float, c.c_float], "borrowed device"),
    ("cna_texture2d_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture2DCreateInfo), c.POINTER(c.c_uint64)], "owned texture"),
    ("cna_texture2d_create_from_encoded_memory", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(abi.CNA_Texture2DDecodeInfo), c.POINTER(c.c_uint64)], "owned texture"),
    ("cna_texture2d_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture2DInfo)], "caller output"),
    ("cna_texture2d_get_encoded_byte_count", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.c_uint32, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_texture2d_copy_encoded", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.c_uint32, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_texture2d_set_data", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_Texture2DTransfer), c.c_void_p, c.c_uint64], "copies elements"),
    ("cna_texture2d_get_data", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_Texture2DTransfer), c.c_void_p, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_texture2d_destroy", c.c_uint32, [c.c_uint64], "consumes texture"),
    ("cna_texture3d_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture3DCreateInfo), c.POINTER(c.c_uint64)], "owned Texture3D"),
    ("cna_texture3d_destroy", c.c_uint32, [c.c_uint64], "consumes Texture3D"),
    ("cna_texture3d_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture3DInfo)], "caller output"),
    ("cna_texture3d_set_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture3DTransfer), c.POINTER(abi.CNA_Color), c.c_uint64], "copies Color voxels"),
    ("cna_texture3d_get_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Texture3DTransfer), c.POINTER(abi.CNA_Color), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_texturecube_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_TextureCubeCreateInfo), c.POINTER(c.c_uint64)], "owned TextureCube"),
    ("cna_texturecube_destroy", c.c_uint32, [c.c_uint64], "consumes TextureCube"),
    ("cna_texturecube_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_TextureCubeInfo)], "caller output"),
    ("cna_texturecube_set_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_TextureCubeTransfer), c.POINTER(abi.CNA_Color), c.c_uint64], "copies Color texels"),
    ("cna_texturecube_get_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_TextureCubeTransfer), c.POINTER(abi.CNA_Color), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    # Effect ownership/execution routes.  Reflection views are added
    # only when consumed by the Python projection; stock effects use the
    # canonical owned Effect handle and generic apply route.
    ("cna_effect_create_empty", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned Effect"),
    ("cna_effect_create_compiled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)], "owned Effect"),
    ("cna_effect_clone", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned Effect clone"),
    ("cna_effect_destroy", c.c_uint32, [c.c_uint64], "consumes Effect"),
    ("cna_effect_apply", c.c_uint32, [c.c_uint64], "borrowed Effect"),
    ("cna_effect_get_parameters", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned parameter collection view"),
    ("cna_effect_get_techniques", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned technique collection view"),
    ("cna_effect_get_current_technique", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned technique view"),
    ("cna_effect_set_current_technique", c.c_uint32, [c.c_uint64, c.c_uint64], "borrowed technique view"),
    ("cna_effect_technique_collection_destroy", c.c_uint32, [c.c_uint64], "consumes technique collection view"),
    ("cna_effect_technique_collection_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_technique_collection_get_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "owned technique view"),
    ("cna_effect_technique_destroy", c.c_uint32, [c.c_uint64], "consumes technique view"),
    ("cna_effect_technique_get_name_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_technique_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_technique_get_passes", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned pass collection view"),
    ("cna_effect_pass_collection_destroy", c.c_uint32, [c.c_uint64], "consumes pass collection view"),
    ("cna_effect_pass_collection_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_pass_collection_get_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "owned pass view"),
    ("cna_effect_pass_destroy", c.c_uint32, [c.c_uint64], "consumes pass view"),
    ("cna_effect_pass_get_name_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_pass_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_pass_apply", c.c_uint32, [c.c_uint64], "borrowed pass view"),
    ("cna_effect_parameter_collection_add_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_EffectParameterCreateInfo), c.POINTER(c.c_uint64)], "owned stable parameter view"),
    ("cna_effect_parameter_destroy", c.c_uint32, [c.c_uint64], "consumes parameter view"),
    ("cna_effect_parameter_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_EffectParameterInfo)], "caller output"),
    ("cna_effect_parameter_get_name_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_get_semantic_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_copy_semantic", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_get_elements", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned parameter collection view"),
    ("cna_effect_parameter_get_structure_members", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned parameter collection view"),
    ("cna_effect_parameter_get_annotations", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned annotation collection view"),
    ("cna_effect_parameter_get_value", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_void_p], "caller typed output"),
    ("cna_effect_parameter_get_values", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint64, c.c_void_p, c.c_uint64, c.POINTER(c.c_uint64)], "caller typed array output"),
    ("cna_effect_parameter_set_value", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_void_p], "copies typed value"),
    ("cna_effect_parameter_set_values", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_void_p, c.c_uint64], "copies typed values"),
    ("cna_effect_parameter_get_value_string_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_copy_value_string", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_set_value_string", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "copies UTF-8 string"),
    ("cna_effect_parameter_get_value_texture", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)], "retained texture handle"),
    ("cna_effect_parameter_set_value_texture", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint64], "retains texture handle"),
    ("cna_effect_parameter_collection_destroy", c.c_uint32, [c.c_uint64], "consumes parameter collection view"),
    ("cna_effect_parameter_collection_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_parameter_collection_get_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "owned parameter view"),
    ("cna_effect_parameter_collection_find_name", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "owned parameter view when found"),
    ("cna_effect_parameter_collection_find_semantic", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "owned parameter view when found"),
    ("cna_effect_annotation_create", c.c_uint32, [c.POINTER(abi.CNA_EffectAnnotationCreateInfo), c.POINTER(c.c_uint64)], "owned standalone annotation"),
    ("cna_effect_annotation_destroy", c.c_uint32, [c.c_uint64], "consumes annotation view"),
    ("cna_effect_annotation_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_EffectAnnotationInfo)], "caller output"),
    ("cna_effect_annotation_get_name_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_get_semantic_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_copy_semantic", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_get_value_boolean", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_effect_annotation_get_value_int32", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_effect_annotation_get_value_single", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_effect_annotation_get_value_string_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_copy_value_string", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_get_value_vector2", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector2)], "caller output"),
    ("cna_effect_annotation_get_value_vector3", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_effect_annotation_get_value_vector4", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector4)], "caller output"),
    ("cna_effect_annotation_get_value_matrix", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Matrix)], "caller output"),
    ("cna_effect_annotation_collection_destroy", c.c_uint32, [c.c_uint64], "consumes annotation collection view"),
    ("cna_effect_annotation_collection_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_effect_annotation_collection_add", c.c_uint32, [c.c_uint64, c.c_uint64], "copies annotation into collection"),
    ("cna_effect_annotation_collection_get_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)], "owned annotation copy"),
    ("cna_effect_annotation_collection_find", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "owned annotation copy when found"),
    ("cna_effect_pass_get_annotations", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned annotation collection view"),
    ("cna_effect_technique_get_annotations", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned annotation collection view"),
    ("cna_basic_effect_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned BasicEffect"),
    ("cna_alpha_test_effect_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned AlphaTestEffect"),
    ("cna_dual_texture_effect_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned DualTextureEffect"),
    ("cna_environment_map_effect_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned EnvironmentMapEffect"),
    ("cna_skinned_effect_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned SkinnedEffect"),
    ("cna_effect_material_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned EffectMaterial"),
    ("cna_effect_matrices_get_world", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Matrix)], "caller output"),
    ("cna_effect_matrices_set_world", c.c_uint32, [c.c_uint64, abi.CNA_Matrix], "copies matrix"),
    ("cna_effect_matrices_get_view", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Matrix)], "caller output"),
    ("cna_effect_matrices_set_view", c.c_uint32, [c.c_uint64, abi.CNA_Matrix], "copies matrix"),
    ("cna_effect_matrices_get_projection", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Matrix)], "caller output"),
    ("cna_effect_matrices_set_projection", c.c_uint32, [c.c_uint64, abi.CNA_Matrix], "copies matrix"),
    ("cna_effect_fog_get_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_effect_fog_set_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_effect_fog_get_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_effect_fog_set_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_effect_fog_get_start", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_effect_fog_set_start", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_effect_fog_get_end", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_effect_fog_set_end", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_effect_lights_get_ambient_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_effect_lights_set_ambient_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_effect_lights_get_directional_light", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)], "owned directional-light view"),
    ("cna_effect_lights_get_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_effect_lights_set_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_effect_lights_enable_default", c.c_uint32, [c.c_uint64], "borrowed effect"),
    ("cna_directional_light_destroy", c.c_uint32, [c.c_uint64], "consumes directional-light view"),
    ("cna_directional_light_get_diffuse_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_directional_light_set_diffuse_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_directional_light_get_direction", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_directional_light_set_direction", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_directional_light_get_specular_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_directional_light_set_specular_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_directional_light_get_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_directional_light_set_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed light"),
    ("cna_basic_effect_get_vertex_color_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_basic_effect_set_vertex_color_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_basic_effect_get_prefer_per_pixel_lighting", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_basic_effect_set_prefer_per_pixel_lighting", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_basic_effect_get_diffuse_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_basic_effect_set_diffuse_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_basic_effect_get_emissive_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_basic_effect_set_emissive_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_basic_effect_get_specular_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_basic_effect_set_specular_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_basic_effect_get_specular_power", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_basic_effect_set_specular_power", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_basic_effect_get_alpha", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_basic_effect_set_alpha", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_basic_effect_get_texture_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_basic_effect_set_texture_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_basic_effect_get_texture", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "borrowed retained texture identity"),
    ("cna_basic_effect_set_texture", c.c_uint32, [c.c_uint64, c.c_uint64], "retains texture"),
    ("cna_alpha_test_effect_get_diffuse_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_alpha_test_effect_set_diffuse_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_alpha_test_effect_get_alpha", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_alpha_test_effect_set_alpha", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_alpha_test_effect_get_texture", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "borrowed retained texture identity"),
    ("cna_alpha_test_effect_set_texture", c.c_uint32, [c.c_uint64, c.c_uint64], "retains texture"),
    ("cna_alpha_test_effect_get_vertex_color_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_alpha_test_effect_set_vertex_color_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_alpha_test_effect_get_alpha_function", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_alpha_test_effect_set_alpha_function", c.c_uint32, [c.c_uint64, c.c_uint32], "borrowed effect"),
    ("cna_alpha_test_effect_get_reference_alpha", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_alpha_test_effect_set_reference_alpha", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed effect"),
    ("cna_dual_texture_effect_get_diffuse_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_dual_texture_effect_set_diffuse_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_dual_texture_effect_get_alpha", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_dual_texture_effect_set_alpha", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_dual_texture_effect_get_texture", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "borrowed retained texture identity"),
    ("cna_dual_texture_effect_set_texture", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint64], "retains texture"),
    ("cna_dual_texture_effect_get_vertex_color_enabled", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_dual_texture_effect_set_vertex_color_enabled", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_environment_map_effect_get_diffuse_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_environment_map_effect_set_diffuse_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_environment_map_effect_get_emissive_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_environment_map_effect_set_emissive_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_environment_map_effect_get_alpha", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_environment_map_effect_set_alpha", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_environment_map_effect_get_texture", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "borrowed retained texture identity"),
    ("cna_environment_map_effect_set_texture", c.c_uint32, [c.c_uint64, c.c_uint64], "retains texture"),
    ("cna_environment_map_effect_get_environment_map", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "borrowed retained texture identity"),
    ("cna_environment_map_effect_set_environment_map", c.c_uint32, [c.c_uint64, c.c_uint64], "retains texture"),
    ("cna_environment_map_effect_get_amount", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_environment_map_effect_set_amount", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_environment_map_effect_get_specular", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_environment_map_effect_set_specular", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_environment_map_effect_get_fresnel_factor", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_environment_map_effect_set_fresnel_factor", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_skinned_effect_get_diffuse_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_skinned_effect_set_diffuse_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_skinned_effect_get_emissive_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_skinned_effect_set_emissive_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_skinned_effect_get_specular_color", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3)], "caller output"),
    ("cna_skinned_effect_set_specular_color", c.c_uint32, [c.c_uint64, abi.CNA_Vector3], "copies vector"),
    ("cna_skinned_effect_get_specular_power", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_skinned_effect_set_specular_power", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_skinned_effect_get_alpha", c.c_uint32, [c.c_uint64, c.POINTER(c.c_float)], "caller output"),
    ("cna_skinned_effect_set_alpha", c.c_uint32, [c.c_uint64, c.c_float], "borrowed effect"),
    ("cna_skinned_effect_get_prefer_per_pixel_lighting", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_skinned_effect_set_prefer_per_pixel_lighting", c.c_uint32, [c.c_uint64, c.c_uint8], "borrowed effect"),
    ("cna_skinned_effect_get_texture", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.POINTER(c.c_uint64)], "borrowed retained texture identity"),
    ("cna_skinned_effect_set_texture", c.c_uint32, [c.c_uint64, c.c_uint64], "retains texture"),
    ("cna_skinned_effect_get_weights_per_vertex", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_skinned_effect_set_weights_per_vertex", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed effect"),
    ("cna_skinned_effect_set_bone_transforms", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Matrix), c.c_uint64], "copies matrices"),
    ("cna_skinned_effect_copy_bone_transforms", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(abi.CNA_Matrix), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_get_name_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_set_name", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed resource"),
    ("cna_graphics_resource_get_string_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_copy_string", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_subscribe_disposing", c.c_uint32, [c.c_uint64, abi.CNA_GraphicsResourceDisposingCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_vertex_declaration_create", c.c_uint32, [c.POINTER(abi.CNA_VertexElement), c.c_uint64, c.POINTER(c.c_uint64)], "owned declaration"),
    ("cna_vertex_declaration_create_with_stride", c.c_uint32, [c.c_int32, c.POINTER(abi.CNA_VertexElement), c.c_uint64, c.POINTER(c.c_uint64)], "owned declaration"),
    ("cna_vertex_declaration_destroy", c.c_uint32, [c.c_uint64], "consumes declaration"),
    ("cna_vertex_buffer_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferCreateInfo), c.POINTER(c.c_uint64)], "owned vertex buffer"),
    ("cna_vertex_buffer_destroy", c.c_uint32, [c.c_uint64], "consumes vertex buffer"),
    ("cna_vertex_buffer_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferInfo)], "caller output"),
    ("cna_vertex_buffer_set_data_raw", c.c_uint32, [c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32], "copies vertex bytes"),
    ("cna_vertex_buffer_set_data_raw_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32], "copies vertex bytes"),
    ("cna_vertex_buffer_set_data_raw_with_options", c.c_uint32, [c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32, c.c_uint32], "copies vertex bytes with a streaming hint"),
    ("cna_vertex_buffer_set_data_raw_at_with_options", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32, c.c_uint32], "copies vertex bytes into a buffer window with a streaming hint"),
    ("cna_vertex_buffer_get_data_raw", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32], "caller output"),
    ("cna_index_buffer_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_IndexBufferCreateInfo), c.POINTER(c.c_uint64)], "owned index buffer"),
    ("cna_index_buffer_destroy", c.c_uint32, [c.c_uint64], "consumes index buffer"),
    ("cna_index_buffer_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_IndexBufferInfo)], "caller output"),
    ("cna_index_buffer_set_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_IndexBufferTransfer), c.c_void_p, c.c_uint64], "copies indices"),
    ("cna_index_buffer_set_data_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(abi.CNA_IndexBufferTransfer), c.c_void_p, c.c_uint64], "copies indices"),
    ("cna_index_buffer_get_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_IndexBufferTransfer), c.c_void_p, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_device_set_vertex_buffer", c.c_uint32, [c.c_uint64, c.c_uint64], "borrows binding"),
    ("cna_graphics_device_set_vertex_buffer_offset", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_int32], "borrows binding"),
    ("cna_graphics_device_set_vertex_buffers", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferBinding), c.c_uint64], "borrows bindings"),
    ("cna_graphics_device_get_vertex_buffer_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_device_copy_vertex_buffers", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferBinding), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_device_set_index_buffer", c.c_uint32, [c.c_uint64, c.c_uint64], "borrows binding"),
    ("cna_graphics_device_get_index_buffer", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_device_get_backbuffer_data_window", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_BackBufferReadback), c.POINTER(abi.CNA_Color), c.c_uint64], "caller output"),
    ("cna_graphics_device_draw_primitives", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_int32, c.c_int32], "borrowed device"),
    ("cna_graphics_device_draw_indexed_primitives", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_int32, c.c_int32, c.c_int32, c.c_int32, c.c_int32], "borrowed device"),
    ("cna_graphics_device_draw_instanced_primitives", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_int32, c.c_int32, c.c_int32, c.c_int32, c.c_int32, c.c_int32], "borrowed device"),
    ("cna_graphics_device_draw_user_primitives", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_UserPrimitives)], "reads caller vertices"),
    ("cna_graphics_device_draw_user_indexed_primitives", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_UserPrimitives), c.POINTER(abi.CNA_UserIndices)], "reads caller vertices and indices"),
    ("cna_render_target2d_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTarget2DCreateInfo), c.POINTER(c.c_uint64)], "owned render target"),
    ("cna_render_target_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTargetInfo)], "caller output"),
    ("cna_render_target_subscribe_content_lost", c.c_uint32, [c.c_uint64, abi.CNA_RenderTargetContentLostCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_render_target_unsubscribe_content_lost", c.c_uint32, [c.c_uint64], "consumes registration"),
    ("cna_render_target_destroy", c.c_uint32, [c.c_uint64], "consumes render target"),
    ("cna_graphics_device_set_render_target2d", c.c_uint32, [c.c_uint64, c.c_uint64], "borrows render target"),
    ("cna_graphics_device_set_render_targets", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTargetBinding), c.c_uint64], "borrows render targets"),
    ("cna_graphics_device_get_render_target_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_device_copy_render_targets", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTargetBinding), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_sprite_font_create", c.c_uint32, [c.POINTER(abi.CNA_SpriteFontCreateInfo), c.POINTER(c.c_uint64)], "owned sprite font"),
    ("cna_sprite_font_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteFontInfo)], "caller output"),
    ("cna_sprite_font_set_default_character", c.c_uint32, [c.c_uint64, c.c_uint8, c.c_uint16], "borrowed font"),
    ("cna_sprite_font_set_line_spacing", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed font"),
    ("cna_sprite_font_set_spacing", c.c_uint32, [c.c_uint64, c.c_float], "borrowed font"),
    ("cna_sprite_font_measure_utf8", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(abi.CNA_Vector2)], "caller output"),
    ("cna_sprite_font_destroy", c.c_uint32, [c.c_uint64], "consumes sprite font"),
    ("cna_sprite_batch_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned sprite batch"),
    ("cna_sprite_batch_begin", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteBatchBeginInfo)], "borrowed sprite batch"),
    ("cna_sprite_batch_submit_many", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteCommand), c.c_uint64], "copies destination-rectangle commands"),
    ("cna_sprite_batch_submit_scaled_many", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteScaledCommand), c.c_uint64], "copies commands"),
    ("cna_sprite_batch_end", c.c_uint32, [c.c_uint64], "borrowed sprite batch"),
    ("cna_sprite_batch_destroy", c.c_uint32, [c.c_uint64], "consumes sprite batch"),
    ("cna_keyboard_get_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_KeyboardState)], "caller output"),
    ("cna_keyboard_get_state_for_player", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_KeyboardState)], "caller output"),
    ("cna_mouse_get_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_MouseState)], "caller output"),
    ("cna_mouse_get_window_handle", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_mouse_set_window_handle", c.c_uint32, [c.c_uint64, c.c_uint64], "borrowed game"),
    ("cna_mouse_set_position", c.c_uint32, [c.c_uint64, c.c_int32, c.c_int32], "borrowed game"),
    ("cna_gamepad_get_state_with_dead_zone", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_uint32, c.POINTER(abi.CNA_GamePadState)], "caller output"),
    ("cna_gamepad_get_capabilities", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(abi.CNA_GamePadCapabilities)], "caller output"),
    ("cna_gamepad_set_vibration", c.c_uint32, [c.c_uint64, c.c_uint32, c.c_float, c.c_float, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_render_target_cube_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTargetCubeCreateInfo), c.POINTER(c.c_uint64)], "owned cube render target"),
    ("cna_graphics_device_set_render_target_cube", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_uint32], "borrows cube render target"),
    ("cna_occlusion_query_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned OcclusionQuery"),
    ("cna_occlusion_query_begin", c.c_uint32, [c.c_uint64], "borrowed OcclusionQuery"),
    ("cna_occlusion_query_end", c.c_uint32, [c.c_uint64], "borrowed OcclusionQuery"),
    ("cna_occlusion_query_get_is_complete", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_occlusion_query_get_pixel_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_occlusion_query_has_renderer", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_occlusion_query_destroy", c.c_uint32, [c.c_uint64], "consumes OcclusionQuery"),
    ("cna_gamer_services_dispatcher_set_window_handle", c.c_uint32, [c.c_uint64], "process dispatcher setting"),
    ("cna_gamer_services_dispatcher_initialize", c.c_uint32, [c.c_uint64], "borrowed game"),
    ("cna_gamer_services_dispatcher_update", c.c_uint32, [], "process dispatcher update"),
    ("cna_touch_get_capabilities", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_TouchCapabilities)], "caller output"),
    ("cna_touch_get_state", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_TouchState)], "caller output"),
    ("cna_touch_panel_get_display_width", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_touch_panel_set_display_width", c.c_uint32, [c.c_uint64, c.c_int32], "process touch setting"),
    ("cna_touch_panel_get_display_height", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_touch_panel_set_display_height", c.c_uint32, [c.c_uint64, c.c_int32], "process touch setting"),
    ("cna_touch_panel_get_display_orientation", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_touch_panel_set_display_orientation", c.c_uint32, [c.c_uint64, c.c_uint32], "process touch setting"),
    ("cna_touch_panel_get_enabled_gestures", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)], "caller output"),
    ("cna_touch_panel_set_enabled_gestures", c.c_uint32, [c.c_uint64, c.c_uint32], "process touch setting"),
    ("cna_touch_panel_get_is_gesture_available", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_touch_panel_get_window_handle", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_touch_panel_set_window_handle", c.c_uint32, [c.c_uint64, c.c_uint64], "process touch setting"),
    ("cna_touch_panel_read_gesture", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_GestureSample)], "caller output"),
    ("cna_storage_device_show_selector", c.c_uint32, [abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned StorageDevice"),
    ("cna_storage_get_root_size_ext", c.c_uint32, [c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_copy_root_ext", c.c_uint32, [c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_device_show_selector_for_player", c.c_uint32, [c.c_uint32, abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned StorageDevice"),
    ("cna_storage_device_show_selector_with_space", c.c_uint32, [c.c_int32, c.c_int32, abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned StorageDevice"),
    ("cna_storage_device_show_selector_for_player_with_space", c.c_uint32, [c.c_uint32, c.c_int32, c.c_int32, abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned StorageDevice"),
    ("cna_storage_device_get_free_space", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_storage_device_get_is_connected", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_device_get_total_space", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_storage_device_delete_container", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed StorageDevice"),
    ("cna_storage_device_subscribe_device_changed", c.c_uint32, [abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_storage_device_unsubscribe_device_changed", c.c_uint32, [c.c_uint64], "consumes registration"),
    ("cna_storage_device_destroy", c.c_uint32, [c.c_uint64], "consumes StorageDevice"),
    ("cna_storage_container_open", c.c_uint32, [c.c_uint64, abi.CNA_StringView, abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned StorageContainer"),
    ("cna_storage_container_get_display_name_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_container_copy_display_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_container_get_is_disposed", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_container_dispose", c.c_uint32, [c.c_uint64], "borrowed StorageContainer"),
    ("cna_storage_container_subscribe_disposing", c.c_uint32, [c.c_uint64, abi.CNA_StorageCompletionCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_storage_container_unsubscribe_disposing", c.c_uint32, [c.c_uint64], "consumes registration"),
    ("cna_storage_container_create_directory", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed StorageContainer"),
    ("cna_storage_container_directory_exists", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_container_delete_directory", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed StorageContainer"),
    ("cna_storage_container_file_exists", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_container_delete_file", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed StorageContainer"),
    ("cna_storage_container_get_directory_name_count", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_container_copy_directory_name", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_container_get_file_name_count", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_container_copy_file_name", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_container_create_file", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)], "owned StorageStream"),
    ("cna_storage_container_open_file", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_uint32, c.POINTER(c.c_uint64)], "owned StorageStream"),
    ("cna_storage_container_open_file_access", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_uint32, c.c_uint32, c.POINTER(c.c_uint64)], "owned StorageStream"),
    ("cna_storage_container_open_file_share", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_uint32, c.c_uint32, c.c_uint32, c.POINTER(c.c_uint64)], "owned StorageStream"),
    ("cna_storage_container_destroy", c.c_uint32, [c.c_uint64], "consumes StorageContainer"),
    ("cna_storage_stream_read", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_storage_stream_write", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64], "copies bytes"),
    ("cna_storage_stream_seek", c.c_uint32, [c.c_uint64, c.c_int64, c.c_uint32, c.POINTER(c.c_int64)], "caller output"),
    ("cna_storage_stream_get_position", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_storage_stream_get_length", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int64)], "caller output"),
    ("cna_storage_stream_set_length", c.c_uint32, [c.c_uint64, c.c_int64], "borrowed StorageStream"),
    ("cna_storage_stream_get_can_read", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_stream_get_can_write", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_stream_get_can_seek", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)], "caller output"),
    ("cna_storage_stream_flush", c.c_uint32, [c.c_uint64], "borrowed StorageStream"),
    ("cna_storage_stream_close", c.c_uint32, [c.c_uint64], "consumes StorageStream"),
)

FUNCTION_MANIFEST += MEDIA_FUNCTION_MANIFEST
# The CNA-native compiled-content extension family, and the minimal curve
# slice its codec depends on.  See `docs/cnb-cnj-extensions.md`.
FUNCTION_MANIFEST += (CNB_FUNCTION_MANIFEST + CURVE_CODEC_FUNCTION_MANIFEST
                      + NATIVE_CONTENT_MANAGER_FUNCTION_MANIFEST)
# CNA's modern engine layer.  See `docs/engine-extensions.md`.
FUNCTION_MANIFEST += ENGINE_FUNCTION_MANIFEST


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
        "CNA native library is not configured; set CNA_NATIVE_LIBRARY to the absolute "
        f"CNA {SUPPORTED_ABI_MAJOR}.{SUPPORTED_ABI_MINOR}.x C ABI library file "
        "or CNA_NATIVE_DIR to its absolute directory"
    )


#: Routes actually called during this process, recorded only when
#: ``CNA_PYTHON_ROUTE_LOG`` names a file to append them to.  Reachability analysis
#: uses this as evidence that a route with no statically resolvable call site is
#: genuinely invoked, rather than admitting it on trust.
_CALLED_ROUTES: set[str] = set()


def _route_recorder():
    destination = os.environ.get("CNA_PYTHON_ROUTE_LOG")
    if not destination:
        return None
    import atexit

    def flush() -> None:
        try:
            with open(destination, "a", encoding="utf-8") as handle:
                for name in sorted(_CALLED_ROUTES):
                    handle.write(name + "\n")
        except OSError:
            pass

    if not _CALLED_ROUTES:
        atexit.register(flush)

    def wrap(symbol: str, function):
        def recorded(*arguments):
            _CALLED_ROUTES.add(symbol)
            return function(*arguments)
        return recorded

    return wrap


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
        if not abi_is_supported(actual):
            raise NativeAbiMismatchError(QUALIFIED_ABI, actual, str(path))
        self.abi_version = actual
        recorder = _route_recorder()
        for symbol, restype, argtypes, _ownership in FUNCTION_MANIFEST[1:]:
            try:
                function = getattr(self._cdll, symbol)
            except AttributeError as error:
                raise NativeLibraryError(
                    f"CNA ABI {format_abi(actual)} library {path} is missing required symbol {symbol}"
                ) from error
            function.restype = restype
            function.argtypes = argtypes
            setattr(self, symbol, function if recorder is None else recorder(symbol, function))

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
