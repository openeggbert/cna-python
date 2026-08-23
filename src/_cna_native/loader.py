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
    ("cna_graphics_resource_get_name_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_set_name", c.c_uint32, [c.c_uint64, abi.CNA_StringView], "borrowed resource"),
    ("cna_graphics_resource_get_string_byte_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_copy_string", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_resource_subscribe_disposing", c.c_uint32, [c.c_uint64, abi.CNA_GraphicsResourceDisposingCallback, c.c_void_p, c.POINTER(c.c_uint64)], "owned registration"),
    ("cna_vertex_declaration_create", c.c_uint32, [c.POINTER(abi.CNA_VertexElement), c.c_uint64, c.POINTER(c.c_uint64)], "owned declaration"),
    ("cna_vertex_declaration_create_with_stride", c.c_uint32, [c.c_int32, c.POINTER(abi.CNA_VertexElement), c.c_uint64, c.POINTER(c.c_uint64)], "owned declaration"),
    ("cna_vertex_declaration_destroy", c.c_uint32, [c.c_uint64], "consumes declaration"),
    ("cna_vertex_declaration_get_stride", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)], "caller output"),
    ("cna_vertex_declaration_copy_elements", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexElement), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_vertex_buffer_create", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferCreateInfo), c.POINTER(c.c_uint64)], "owned vertex buffer"),
    ("cna_vertex_buffer_destroy", c.c_uint32, [c.c_uint64], "consumes vertex buffer"),
    ("cna_vertex_buffer_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferInfo)], "caller output"),
    ("cna_vertex_buffer_copy_declaration_elements", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexElement), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_vertex_buffer_set_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferTransfer), c.c_void_p, c.c_uint64], "copies typed vertices"),
    ("cna_vertex_buffer_get_data", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_VertexBufferTransfer), c.c_void_p, c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_vertex_buffer_set_data_raw", c.c_uint32, [c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32], "copies vertex bytes"),
    ("cna_vertex_buffer_set_data_raw_at", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint32], "copies vertex bytes"),
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
    ("cna_render_target_destroy", c.c_uint32, [c.c_uint64], "consumes render target"),
    ("cna_graphics_device_set_render_target2d", c.c_uint32, [c.c_uint64, c.c_uint64], "borrows render target"),
    ("cna_graphics_device_set_render_targets", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTargetBinding), c.c_uint64], "borrows render targets"),
    ("cna_graphics_device_get_render_target_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_graphics_device_copy_render_targets", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_RenderTargetBinding), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_sprite_font_create", c.c_uint32, [c.POINTER(abi.CNA_SpriteFontCreateInfo), c.POINTER(c.c_uint64)], "owned sprite font"),
    ("cna_sprite_font_get_info", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteFontInfo)], "caller output"),
    ("cna_sprite_font_copy_characters", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint16), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_sprite_font_copy_glyphs", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteFontGlyph), c.c_uint64, c.POINTER(c.c_uint64)], "caller output"),
    ("cna_sprite_font_set_default_character", c.c_uint32, [c.c_uint64, c.c_uint8, c.c_uint16], "borrowed font"),
    ("cna_sprite_font_set_line_spacing", c.c_uint32, [c.c_uint64, c.c_int32], "borrowed font"),
    ("cna_sprite_font_set_spacing", c.c_uint32, [c.c_uint64, c.c_float], "borrowed font"),
    ("cna_sprite_font_measure_utf8", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.POINTER(abi.CNA_Vector2)], "caller output"),
    ("cna_sprite_font_destroy", c.c_uint32, [c.c_uint64], "consumes sprite font"),
    ("cna_sprite_batch_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)], "owned sprite batch"),
    ("cna_sprite_batch_begin", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_SpriteBatchBeginInfo)], "borrowed sprite batch"),
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
