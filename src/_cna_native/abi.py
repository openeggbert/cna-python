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

# Observer-only game and window events carry no native sender or payload.  The
# public facade supplies its stable Python sender when dispatching them.
CNA_GameEventCallback = c.CFUNCTYPE(None, c.c_void_p)
CNA_GraphicsResourceDisposingCallback = c.CFUNCTYPE(None, c.c_uint64, c.c_void_p)
CNA_GraphicsDeviceEventCallback = c.CFUNCTYPE(None, c.c_uint64, c.c_void_p)
CNA_RenderTargetContentLostCallback = c.CFUNCTYPE(None, c.c_uint64, c.c_void_p)


class CNA_GraphicsRendererFallbackRecord(c.Structure):
    """One renderer identity that was tried and passed over, and why."""

    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("type", c.c_uint32), ("reason", c.c_uint32),
    ]
# Audio events are observer-only ``void(void*)`` callbacks.  The canonical
# dispatcher invokes dynamic/microphone callbacks on the thread which pumps it.
CNA_AudioEventCallback = c.CFUNCTYPE(None, c.c_void_p)
CNA_StorageCompletionCallback = c.CFUNCTYPE(None, c.c_void_p)
# MediaPlayer callbacks are process-global observer notifications.  The native
# trampoline receives only the copied registration context.
CNA_MediaPlayerEventCallback = c.CFUNCTYPE(None, c.c_void_p)


class CNA_VisualizationData(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("frequencies", c.c_float * 256), ("samples", c.c_float * 256),
    ]


class CNA_VideoFrameEXT(c.Structure):
    """Borrowed view of the frame a VideoPlayer currently holds.

    ``generation`` is monotonic for the player's lifetime and changes only when a
    frame is actually decoded, which is what makes change detection possible; the
    texture itself stays borrowed until the next call on that player.
    """

    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("texture", c.c_uint64), ("generation", c.c_uint64),
        ("presentation_time", c.c_double),
        ("available", c.c_uint8), ("reserved", c.c_uint8 * 3),
    ]


CNA_VIDEO_FRAME_EXT_STRUCT_VERSION = 1


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


class CNA_Vector3(c.Structure):
    _fields_ = [("x", c.c_float), ("y", c.c_float), ("z", c.c_float)]


class CNA_Vector4(c.Structure):
    _fields_ = [("x", c.c_float), ("y", c.c_float), ("z", c.c_float), ("w", c.c_float)]


class CNA_AudioCapabilities(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("is_playback_available", c.c_uint8), ("reserved0", c.c_uint8 * 3),
        ("reserved1", c.c_uint32),
    ]


class CNA_SoundEffectCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("sample_rate", c.c_uint32), ("channels", c.c_uint32),
        ("reserved", c.c_uint64),
    ]


class CNA_SoundEffectInstanceInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("state", c.c_uint32), ("is_looped", c.c_uint8),
        ("reserved0", c.c_uint8 * 3), ("volume", c.c_float),
        ("pitch", c.c_float), ("pan", c.c_float), ("reserved1", c.c_uint32),
    ]


class CNA_AudioEmitter(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("doppler_scale", c.c_float), ("forward", CNA_Vector3),
        ("position", CNA_Vector3), ("up", CNA_Vector3), ("velocity", CNA_Vector3),
    ]


class CNA_AudioListener(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("forward", CNA_Vector3), ("position", CNA_Vector3),
        ("up", CNA_Vector3), ("velocity", CNA_Vector3),
    ]


class CNA_CueInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("is_created", c.c_uint8), ("is_disposed", c.c_uint8),
        ("is_paused", c.c_uint8), ("is_playing", c.c_uint8),
        ("is_prepared", c.c_uint8), ("is_preparing", c.c_uint8),
        ("is_stopped", c.c_uint8), ("is_stopping", c.c_uint8),
    ]


class CNA_Quaternion(c.Structure):
    _fields_ = [("x", c.c_float), ("y", c.c_float), ("z", c.c_float), ("w", c.c_float)]


class CNA_Matrix(c.Structure):
    _fields_ = [(f"m{row}{column}", c.c_float)
                for row in range(1, 5) for column in range(1, 5)]


class CNA_Rectangle(c.Structure):
    _fields_ = [("x", c.c_int32), ("y", c.c_int32), ("width", c.c_int32), ("height", c.c_int32)]


class CNA_Viewport(c.Structure):
    _fields_ = [
        ("x", c.c_int32), ("y", c.c_int32), ("width", c.c_int32), ("height", c.c_int32),
        ("min_depth", c.c_float), ("max_depth", c.c_float),
    ]


class CNA_DisplayMode(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_int32), ("height", c.c_int32),
        ("aspect_ratio", c.c_float), ("format", c.c_uint32),
    ]


class CNA_GraphicsAdapterInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("adapter_index", c.c_uint32), ("is_default_adapter", c.c_uint8),
        ("is_wide_screen", c.c_uint8), ("use_null_device", c.c_uint8),
        ("use_reference_device", c.c_uint8), ("vendor_id", c.c_int32),
        ("device_id", c.c_int32), ("revision", c.c_int32),
        ("subsystem_id", c.c_int32), ("description_byte_length", c.c_uint64),
        ("device_name_byte_length", c.c_uint64),
    ]


class CNA_GraphicsFormatSelection(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("exact_match", c.c_uint8), ("reserved", c.c_uint8 * 3),
        ("format", c.c_uint32), ("depth_format", c.c_uint32),
        ("multi_sample_count", c.c_int32),
    ]


class CNA_PresentationParameters(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("back_buffer_format", c.c_uint32), ("back_buffer_width", c.c_int32),
        ("back_buffer_height", c.c_int32), ("depth_stencil_format", c.c_uint32),
        ("multi_sample_count", c.c_int32), ("presentation_interval", c.c_uint32),
        ("display_orientation", c.c_uint32), ("render_target_usage", c.c_uint32),
        ("is_full_screen", c.c_uint8), ("headless_ext", c.c_uint8),
        ("reserved", c.c_uint8 * 2),
    ]


class CNA_GraphicsDeviceInformation(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("adapter_index", c.c_int32), ("graphics_profile", c.c_uint32),
        ("presentation_parameters", CNA_PresentationParameters),
    ]


CNA_PreparingDeviceSettingsMutatorEXT = c.CFUNCTYPE(
    None, c.POINTER(CNA_GraphicsDeviceInformation), c.c_void_p
)


class CNA_BlendState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("alpha_blend_function", c.c_uint32), ("alpha_destination_blend", c.c_uint32),
        ("alpha_source_blend", c.c_uint32), ("color_blend_function", c.c_uint32),
        ("color_destination_blend", c.c_uint32), ("color_source_blend", c.c_uint32),
        ("color_write_channels", c.c_uint32), ("color_write_channels1", c.c_uint32),
        ("color_write_channels2", c.c_uint32), ("color_write_channels3", c.c_uint32),
        ("blend_factor", CNA_Color), ("multi_sample_mask", c.c_int32),
    ]


class CNA_DepthStencilState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("depth_buffer_enable", c.c_uint8), ("depth_buffer_write_enable", c.c_uint8),
        ("stencil_enable", c.c_uint8), ("two_sided_stencil_mode", c.c_uint8),
        ("depth_buffer_function", c.c_uint32), ("stencil_function", c.c_uint32),
        ("stencil_mask", c.c_int32), ("stencil_write_mask", c.c_int32),
        ("reference_stencil", c.c_int32), ("stencil_fail", c.c_uint32),
        ("stencil_depth_buffer_fail", c.c_uint32), ("stencil_pass", c.c_uint32),
        ("counter_clockwise_stencil_function", c.c_uint32),
        ("counter_clockwise_stencil_fail", c.c_uint32),
        ("counter_clockwise_stencil_depth_buffer_fail", c.c_uint32),
        ("counter_clockwise_stencil_pass", c.c_uint32), ("reserved", c.c_uint32),
    ]


class CNA_RasterizerState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("cull_mode", c.c_uint32), ("fill_mode", c.c_uint32),
        ("depth_bias", c.c_float), ("slope_scale_depth_bias", c.c_float),
        ("multi_sample_anti_alias", c.c_uint8), ("scissor_test_enable", c.c_uint8),
        ("reserved", c.c_uint8 * 2),
    ]


class CNA_SamplerState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("address_u", c.c_uint32), ("address_v", c.c_uint32),
        ("address_w", c.c_uint32), ("filter", c.c_uint32),
        ("max_anisotropy", c.c_int32), ("max_mip_level", c.c_int32),
        ("mip_map_level_of_detail_bias", c.c_float), ("reserved", c.c_uint32),
    ]


class CNA_TextureSlotInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("bound", c.c_uint8), ("reserved", c.c_uint8 * 7), ("texture", c.c_uint64),
    ]


class CNA_VertexElement(c.Structure):
    _fields_ = [
        ("offset", c.c_int32), ("format", c.c_uint32),
        ("usage", c.c_uint32), ("usage_index", c.c_int32),
    ]


class CNA_VertexBufferCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("vertex_declaration", c.c_uint64), ("vertex_count", c.c_int32),
        ("buffer_usage", c.c_uint32), ("dynamic", c.c_uint8),
        ("reserved", c.c_uint8 * 7),
    ]


class CNA_VertexBufferInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("vertex_count", c.c_int32), ("buffer_usage", c.c_uint32),
        ("dynamic", c.c_uint8), ("is_content_lost", c.c_uint8),
        ("has_renderer", c.c_uint8), ("reserved0", c.c_uint8),
        ("vertex_stride", c.c_int32), ("vertex_element_count", c.c_uint64),
    ]


class CNA_VertexBufferTransfer(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("vertex_type", c.c_uint32), ("options", c.c_uint32),
        ("start_index", c.c_uint64), ("element_count", c.c_uint64),
    ]


class CNA_VertexPositionColor(c.Structure):
    _fields_ = [("position", CNA_Vector3), ("color", CNA_Color)]


class CNA_VertexPositionColorTexture(c.Structure):
    _fields_ = [("position", CNA_Vector3), ("color", CNA_Color),
                ("texture_coordinate", CNA_Vector2)]


class CNA_VertexPositionNormalTexture(c.Structure):
    _fields_ = [("position", CNA_Vector3), ("normal", CNA_Vector3),
                ("texture_coordinate", CNA_Vector2)]


class CNA_VertexPositionTexture(c.Structure):
    _fields_ = [("position", CNA_Vector3), ("texture_coordinate", CNA_Vector2)]


class CNA_VertexBufferBinding(c.Structure):
    _fields_ = [
        ("vertex_buffer", c.c_uint64), ("vertex_offset", c.c_int32),
        ("instance_frequency", c.c_int32),
    ]


class CNA_IndexBufferCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("index_count", c.c_int32), ("index_element_size", c.c_uint32),
        ("buffer_usage", c.c_uint32), ("dynamic", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]


class CNA_IndexBufferInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("index_count", c.c_int32), ("index_element_size", c.c_uint32),
        ("buffer_usage", c.c_uint32), ("dynamic", c.c_uint8),
        ("is_content_lost", c.c_uint8), ("has_renderer", c.c_uint8),
        ("reserved", c.c_uint8),
    ]


class CNA_IndexBufferTransfer(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("index_element_size", c.c_uint32), ("options", c.c_uint32),
        ("start_index", c.c_uint64), ("element_count", c.c_uint64),
    ]


class CNA_RenderTarget2DCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("mip_map", c.c_uint8),
        ("reserved0", c.c_uint8 * 3), ("format", c.c_uint32),
        ("depth_format", c.c_uint32), ("multi_sample_count", c.c_int32),
        ("usage", c.c_uint32), ("reserved1", c.c_uint32),
    ]


class CNA_RenderTargetCubeCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("size", c.c_uint32), ("mip_map", c.c_uint8),
        ("reserved", c.c_uint8 * 3), ("format", c.c_uint32),
        ("depth_format", c.c_uint32), ("multi_sample_count", c.c_int32),
        ("usage", c.c_uint32),
    ]


class CNA_RenderTargetInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("kind", c.c_uint32), ("width", c.c_uint32), ("height", c.c_uint32),
        ("level_count", c.c_uint32), ("format", c.c_uint32),
        ("depth_format", c.c_uint32), ("multi_sample_count", c.c_int32),
        ("usage", c.c_uint32), ("is_content_lost", c.c_uint8),
        ("renderer_available", c.c_uint8), ("reserved", c.c_uint8 * 2),
    ]


class CNA_RenderTargetBinding(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("render_target", c.c_uint64), ("array_slice", c.c_int32),
        ("cube_map_face", c.c_uint32),
    ]


class CNA_BackBufferReadback(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("has_source_rectangle", c.c_uint8), ("reserved", c.c_uint8 * 3),
        ("source_rectangle", CNA_Rectangle), ("start_index", c.c_uint64),
        ("element_count", c.c_uint64),
    ]


class CNA_UserPrimitives(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("primitive_type", c.c_uint32), ("vertex_source", c.c_uint32),
        ("vertex_data", c.c_void_p), ("vertex_declaration", c.c_uint64),
        ("vertex_offset", c.c_int32), ("num_vertices", c.c_int32),
        ("primitive_count", c.c_int32), ("reserved", c.c_uint32),
    ]


class CNA_UserIndices(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("index_element_size", c.c_uint32), ("index_offset", c.c_int32),
        ("index_data", c.c_void_p),
    ]


class CNA_SpriteFontGlyph(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("glyph_bounds", CNA_Rectangle), ("cropping", CNA_Rectangle),
        ("character", c.c_uint16), ("reserved", c.c_uint16),
        ("kerning", CNA_Vector3),
    ]


class CNA_SpriteFontCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("texture", c.c_uint64), ("glyphs", c.POINTER(CNA_SpriteFontGlyph)),
        ("glyph_count", c.c_uint64), ("line_spacing", c.c_int32),
        ("spacing", c.c_float), ("default_character", c.c_uint16),
        ("has_default_character", c.c_uint8), ("reserved", c.c_uint8 * 5),
    ]


class CNA_SpriteFontInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("character_count", c.c_uint64), ("line_spacing", c.c_int32),
        ("spacing", c.c_float), ("default_character", c.c_uint16),
        ("has_default_character", c.c_uint8), ("reserved", c.c_uint8 * 5),
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


class CNA_Texture3DCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("depth", c.c_uint32),
        ("mip_map", c.c_uint8), ("reserved0", c.c_uint8 * 3),
        ("format", c.c_uint32), ("reserved1", c.c_uint32),
    ]


class CNA_Texture3DInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("depth", c.c_uint32),
        ("level_count", c.c_uint32), ("format", c.c_uint32),
        ("reserved", c.c_uint32),
    ]


class CNA_Texture3DTransfer(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("level", c.c_int32), ("left", c.c_int32), ("top", c.c_int32),
        ("right", c.c_int32), ("bottom", c.c_int32), ("front", c.c_int32),
        ("back", c.c_int32), ("reserved", c.c_uint32),
        ("start_index", c.c_uint64), ("element_count", c.c_uint64),
    ]


class CNA_TextureCubeCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("size", c.c_uint32), ("mip_map", c.c_uint8),
        ("reserved0", c.c_uint8 * 3), ("format", c.c_uint32),
        ("reserved1", c.c_uint32),
    ]


class CNA_TextureCubeInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("size", c.c_uint32), ("level_count", c.c_uint32),
        ("format", c.c_uint32), ("reserved", c.c_uint32),
    ]


class CNA_TextureCubeTransfer(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("face", c.c_uint32), ("level", c.c_int32),
        ("has_rectangle", c.c_uint8), ("reserved0", c.c_uint8 * 3),
        ("rectangle", CNA_Rectangle), ("reserved1", c.c_uint32),
        ("start_index", c.c_uint64), ("element_count", c.c_uint64),
    ]


class CNA_TouchLocation(c.Structure):
    _fields_ = [
        ("id", c.c_int32), ("state", c.c_uint32), ("position", CNA_Vector2),
        ("previous_state", c.c_uint32), ("previous_position", CNA_Vector2),
        ("pressure", c.c_float),
    ]


class CNA_TouchCapabilities(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("is_connected", c.c_uint8), ("reserved", c.c_uint8 * 3),
        ("maximum_touch_count", c.c_uint32),
    ]


class CNA_TouchState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("is_connected", c.c_uint8), ("reserved", c.c_uint8 * 3),
        ("touch_count", c.c_uint32), ("touches", CNA_TouchLocation * 8),
    ]


class CNA_GestureSample(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("gesture_type", c.c_uint32), ("finger_id_ext", c.c_int32),
        ("finger_id2_ext", c.c_int32), ("reserved", c.c_uint32),
        ("timestamp_ticks", c.c_int64), ("position", CNA_Vector2),
        ("position2", CNA_Vector2), ("delta", CNA_Vector2), ("delta2", CNA_Vector2),
    ]


class CNA_EffectParameterCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("name", CNA_StringView), ("semantic", CNA_StringView),
        ("row_count", c.c_int32), ("column_count", c.c_int32),
        ("parameter_class", c.c_uint32), ("parameter_type", c.c_uint32),
    ]


class CNA_EffectParameterInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("row_count", c.c_int32), ("column_count", c.c_int32),
        ("parameter_class", c.c_uint32), ("parameter_type", c.c_uint32),
    ]


class CNA_EffectAnnotationCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("name", CNA_StringView), ("semantic", CNA_StringView),
        ("row_count", c.c_int32), ("column_count", c.c_int32),
        ("parameter_class", c.c_uint32), ("parameter_type", c.c_uint32),
        ("data", c.POINTER(c.c_float)), ("data_count", c.c_uint64),
        ("cached_string", CNA_StringView),
    ]


class CNA_EffectAnnotationInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("row_count", c.c_int32), ("column_count", c.c_int32),
        ("parameter_class", c.c_uint32), ("parameter_type", c.c_uint32),
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


class CNA_GamePadCapabilities(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("gamepad_type", c.c_uint32), ("is_connected", c.c_uint8),
        ("has_a_button", c.c_uint8), ("has_b_button", c.c_uint8),
        ("has_x_button", c.c_uint8), ("has_y_button", c.c_uint8),
        ("has_back_button", c.c_uint8), ("has_start_button", c.c_uint8),
        ("has_big_button", c.c_uint8), ("has_dpad_up_button", c.c_uint8),
        ("has_dpad_down_button", c.c_uint8), ("has_dpad_left_button", c.c_uint8),
        ("has_dpad_right_button", c.c_uint8), ("has_left_shoulder_button", c.c_uint8),
        ("has_right_shoulder_button", c.c_uint8), ("has_left_stick_button", c.c_uint8),
        ("has_right_stick_button", c.c_uint8), ("has_left_x_thumb_stick", c.c_uint8),
        ("has_left_y_thumb_stick", c.c_uint8), ("has_right_x_thumb_stick", c.c_uint8),
        ("has_right_y_thumb_stick", c.c_uint8), ("has_left_trigger", c.c_uint8),
        ("has_right_trigger", c.c_uint8), ("has_left_vibration_motor", c.c_uint8),
        ("has_right_vibration_motor", c.c_uint8), ("has_voice_support", c.c_uint8),
        ("has_light_bar_ext", c.c_uint8), ("has_trigger_vibration_motors_ext", c.c_uint8),
        ("has_misc1_ext", c.c_uint8), ("has_paddle1_ext", c.c_uint8),
        ("has_paddle2_ext", c.c_uint8), ("has_paddle3_ext", c.c_uint8),
        ("has_paddle4_ext", c.c_uint8), ("has_touchpad_ext", c.c_uint8),
        ("has_gyro_ext", c.c_uint8), ("has_accelerometer_ext", c.c_uint8),
        ("reserved", c.c_uint8 * 1),
    ]
