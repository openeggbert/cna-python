// SPDX-License-Identifier: MS-PL
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdalign.h>

#include "CNA/C/core.h"
#include "CNA/C/runtime.h"
#include "CNA/C/graphics.h"
#include "CNA/C/graphics_device.h"
#include "CNA/C/texture.h"
#include "CNA/C/input.h"
#include "CNA/C/input_gamepad.h"
#include "CNA/C/input_touch.h"
#include "CNA/C/display.h"
#include "CNA/C/graphics_state.h"
#include "CNA/C/graphics_resource.h"
#include "CNA/C/vertex_resources.h"
#include "CNA/C/index_resources.h"
#include "CNA/C/render_target.h"
#include "CNA/C/sprite_font.h"
#include "CNA/C/runtime_graphics_manager.h"
#include "CNA/C/effects.h"
#include "CNA/C/texture_volume.h"
#include "CNA/C/audio.h"
#include "CNA/C/xact.h"
#include "CNA/C/storage.h"
#include "CNA/C/media.h"
#include "CNA/C/media_library.h"
#include "CNA/C/media_player.h"
#include "CNA/C/video.h"

#define TYPE(T) do { \
    printf("TYPE %s %zu %zu\n", #T, sizeof(T), alignof(T)); \
} while (0)
#define FIELD(T, F) do { \
    printf("FIELD %s %s %zu\n", #T, #F, offsetof(T, F)); \
} while (0)

static CNA_Result lifecycle_callback(
    CNA_Handle game, const CNA_GameTime* game_time, void* context, CNA_CallbackError* out_error)
{
    (void)game; (void)game_time; (void)context; (void)out_error;
    return CNA_RESULT_SUCCESS;
}

static CNA_Result begin_draw_callback(
    CNA_Handle game, const CNA_GameTime* game_time, void* context,
    CNA_Bool* out_should_draw, CNA_CallbackError* out_error)
{
    (void)game; (void)game_time; (void)context; (void)out_should_draw; (void)out_error;
    return CNA_RESULT_SUCCESS;
}

static void audio_event_callback(void* context) { (void)context; }
static void media_player_event_callback(void* context) { (void)context; }

int main(void) {
    printf("VALUE CNA_ABI_VERSION %u\n", (unsigned)CNA_ABI_VERSION);
    printf("VALUE POINTER_WIDTH %zu\n", sizeof(void *));
    printf("VALUE CNA_Bool %zu\n", sizeof(CNA_Bool));
    printf("VALUE CNA_Result %zu\n", sizeof(CNA_Result));
    printf("VALUE CNA_Handle %zu\n", sizeof(CNA_Handle));
    printf("VALUE CNA_FALSE %u\n", (unsigned)CNA_FALSE);
    printf("VALUE CNA_TRUE %u\n", (unsigned)CNA_TRUE);
    CNA_GameLifecycleCallback checked_lifecycle = lifecycle_callback;
    CNA_GameBeginDrawCallback checked_begin_draw = begin_draw_callback;
    printf("VALUE CNA_GameLifecycleCallback %zu\n", sizeof(checked_lifecycle));
    printf("VALUE CNA_GameBeginDrawCallback %zu\n", sizeof(checked_begin_draw));
    printf("VALUE CNA_GameEventCallback %zu\n", sizeof(CNA_GameEventCallback));
    printf("VALUE CNA_GraphicsResourceDisposingCallback %zu\n", sizeof(CNA_GraphicsResourceDisposingCallback));
    printf("VALUE CNA_GraphicsDeviceEventCallback %zu\n", sizeof(CNA_GraphicsDeviceEventCallback));
    printf("VALUE CNA_PreparingDeviceSettingsMutatorEXT %zu\n", sizeof(CNA_PreparingDeviceSettingsMutatorEXT));
    CNA_AudioEventCallback checked_audio_event = audio_event_callback;
    printf("VALUE CNA_AudioEventCallback %zu\n", sizeof(checked_audio_event));
    printf("VALUE CNA_StorageCompletionCallback %zu\n", sizeof(CNA_StorageCompletionCallback));
    CNA_MediaPlayerEventCallback checked_media_event = media_player_event_callback;
    printf("VALUE CNA_MediaPlayerEventCallback %zu\n", sizeof(checked_media_event));
    printf("VALUE CNA_MediaState %zu\n", sizeof(CNA_MediaState));
    printf("VALUE CNA_MediaSourceType %zu\n", sizeof(CNA_MediaSourceType));
    printf("VALUE CNA_VideoSoundtrackType %zu\n", sizeof(CNA_VideoSoundtrackType));
    printf("VALUE CNA_VISUALIZATION_DATA_SIZE %u\n", (unsigned)CNA_VISUALIZATION_DATA_SIZE);
    printf("VALUE CNA_MEDIA_STATE_STOPPED %u\n", (unsigned)CNA_MEDIA_STATE_STOPPED);
    printf("VALUE CNA_MEDIA_STATE_PLAYING %u\n", (unsigned)CNA_MEDIA_STATE_PLAYING);
    printf("VALUE CNA_MEDIA_STATE_PAUSED %u\n", (unsigned)CNA_MEDIA_STATE_PAUSED);
    printf("VALUE CNA_MEDIA_SOURCE_TYPE_LOCAL_DEVICE %u\n", (unsigned)CNA_MEDIA_SOURCE_TYPE_LOCAL_DEVICE);
    printf("VALUE CNA_MEDIA_SOURCE_TYPE_WINDOWS_MEDIA_CONNECT %u\n", (unsigned)CNA_MEDIA_SOURCE_TYPE_WINDOWS_MEDIA_CONNECT);
    printf("VALUE CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC %u\n", (unsigned)CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC);
    printf("VALUE CNA_VIDEO_SOUNDTRACK_TYPE_DIALOG %u\n", (unsigned)CNA_VIDEO_SOUNDTRACK_TYPE_DIALOG);
    printf("VALUE CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC_AND_DIALOG %u\n", (unsigned)CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC_AND_DIALOG);

    TYPE(CNA_StringView); FIELD(CNA_StringView, data); FIELD(CNA_StringView, byte_length);
    TYPE(CNA_ErrorInfo); FIELD(CNA_ErrorInfo, struct_size); FIELD(CNA_ErrorInfo, struct_version); FIELD(CNA_ErrorInfo, result); FIELD(CNA_ErrorInfo, category); FIELD(CNA_ErrorInfo, message_byte_length);
    TYPE(CNA_GameTime); FIELD(CNA_GameTime, total_game_time_ticks); FIELD(CNA_GameTime, elapsed_game_time_ticks); FIELD(CNA_GameTime, is_running_slowly); FIELD(CNA_GameTime, reserved);
    TYPE(CNA_CallbackError); FIELD(CNA_CallbackError, struct_size); FIELD(CNA_CallbackError, struct_version); FIELD(CNA_CallbackError, message);
    TYPE(CNA_GameCallbacks); FIELD(CNA_GameCallbacks, struct_size); FIELD(CNA_GameCallbacks, struct_version); FIELD(CNA_GameCallbacks, load_content); FIELD(CNA_GameCallbacks, update); FIELD(CNA_GameCallbacks, draw); FIELD(CNA_GameCallbacks, unload_content); FIELD(CNA_GameCallbacks, exiting); FIELD(CNA_GameCallbacks, context);
    TYPE(CNA_GameFrameHooks); FIELD(CNA_GameFrameHooks, struct_size); FIELD(CNA_GameFrameHooks, struct_version); FIELD(CNA_GameFrameHooks, initialize); FIELD(CNA_GameFrameHooks, begin_run); FIELD(CNA_GameFrameHooks, end_run); FIELD(CNA_GameFrameHooks, begin_draw); FIELD(CNA_GameFrameHooks, end_draw); FIELD(CNA_GameFrameHooks, context);
    TYPE(CNA_GameCreateInfo); FIELD(CNA_GameCreateInfo, struct_size); FIELD(CNA_GameCreateInfo, struct_version); FIELD(CNA_GameCreateInfo, is_fixed_time_step); FIELD(CNA_GameCreateInfo, reserved); FIELD(CNA_GameCreateInfo, target_elapsed_time_ticks); FIELD(CNA_GameCreateInfo, window_title); FIELD(CNA_GameCreateInfo, callbacks);
    TYPE(CNA_Color); FIELD(CNA_Color, r); FIELD(CNA_Color, g); FIELD(CNA_Color, b); FIELD(CNA_Color, a);
    TYPE(CNA_Vector2); FIELD(CNA_Vector2, x); FIELD(CNA_Vector2, y);
    TYPE(CNA_Vector3); FIELD(CNA_Vector3, x); FIELD(CNA_Vector3, y); FIELD(CNA_Vector3, z);
    TYPE(CNA_Vector4); FIELD(CNA_Vector4, x); FIELD(CNA_Vector4, y); FIELD(CNA_Vector4, z); FIELD(CNA_Vector4, w);
    TYPE(CNA_AudioCapabilities); FIELD(CNA_AudioCapabilities, struct_size); FIELD(CNA_AudioCapabilities, struct_version); FIELD(CNA_AudioCapabilities, is_playback_available); FIELD(CNA_AudioCapabilities, reserved0); FIELD(CNA_AudioCapabilities, reserved1);
    TYPE(CNA_SoundEffectCreateInfo); FIELD(CNA_SoundEffectCreateInfo, struct_size); FIELD(CNA_SoundEffectCreateInfo, struct_version); FIELD(CNA_SoundEffectCreateInfo, sample_rate); FIELD(CNA_SoundEffectCreateInfo, channels); FIELD(CNA_SoundEffectCreateInfo, reserved);
    TYPE(CNA_SoundEffectInstanceInfo); FIELD(CNA_SoundEffectInstanceInfo, struct_size); FIELD(CNA_SoundEffectInstanceInfo, struct_version); FIELD(CNA_SoundEffectInstanceInfo, state); FIELD(CNA_SoundEffectInstanceInfo, is_looped); FIELD(CNA_SoundEffectInstanceInfo, reserved0); FIELD(CNA_SoundEffectInstanceInfo, volume); FIELD(CNA_SoundEffectInstanceInfo, pitch); FIELD(CNA_SoundEffectInstanceInfo, pan); FIELD(CNA_SoundEffectInstanceInfo, reserved1);
    TYPE(CNA_AudioEmitter); FIELD(CNA_AudioEmitter, struct_size); FIELD(CNA_AudioEmitter, struct_version); FIELD(CNA_AudioEmitter, doppler_scale); FIELD(CNA_AudioEmitter, forward); FIELD(CNA_AudioEmitter, position); FIELD(CNA_AudioEmitter, up); FIELD(CNA_AudioEmitter, velocity);
    TYPE(CNA_AudioListener); FIELD(CNA_AudioListener, struct_size); FIELD(CNA_AudioListener, struct_version); FIELD(CNA_AudioListener, forward); FIELD(CNA_AudioListener, position); FIELD(CNA_AudioListener, up); FIELD(CNA_AudioListener, velocity);
    TYPE(CNA_CueInfo); FIELD(CNA_CueInfo, struct_size); FIELD(CNA_CueInfo, struct_version); FIELD(CNA_CueInfo, is_created); FIELD(CNA_CueInfo, is_disposed); FIELD(CNA_CueInfo, is_paused); FIELD(CNA_CueInfo, is_playing); FIELD(CNA_CueInfo, is_prepared); FIELD(CNA_CueInfo, is_preparing); FIELD(CNA_CueInfo, is_stopped); FIELD(CNA_CueInfo, is_stopping);
    TYPE(CNA_VisualizationData); FIELD(CNA_VisualizationData, struct_size); FIELD(CNA_VisualizationData, struct_version); FIELD(CNA_VisualizationData, frequencies); FIELD(CNA_VisualizationData, samples);
    TYPE(CNA_VideoFrameEXT); FIELD(CNA_VideoFrameEXT, struct_size); FIELD(CNA_VideoFrameEXT, struct_version); FIELD(CNA_VideoFrameEXT, texture); FIELD(CNA_VideoFrameEXT, generation); FIELD(CNA_VideoFrameEXT, presentation_time); FIELD(CNA_VideoFrameEXT, available);
    printf("VALUE CNA_VIDEO_FRAME_EXT_STRUCT_VERSION %u\n", (unsigned)CNA_VIDEO_FRAME_EXT_STRUCT_VERSION);
    TYPE(CNA_Quaternion); FIELD(CNA_Quaternion, x); FIELD(CNA_Quaternion, y); FIELD(CNA_Quaternion, z); FIELD(CNA_Quaternion, w);
    TYPE(CNA_Matrix); FIELD(CNA_Matrix, m11); FIELD(CNA_Matrix, m12); FIELD(CNA_Matrix, m13); FIELD(CNA_Matrix, m14); FIELD(CNA_Matrix, m21); FIELD(CNA_Matrix, m22); FIELD(CNA_Matrix, m23); FIELD(CNA_Matrix, m24); FIELD(CNA_Matrix, m31); FIELD(CNA_Matrix, m32); FIELD(CNA_Matrix, m33); FIELD(CNA_Matrix, m34); FIELD(CNA_Matrix, m41); FIELD(CNA_Matrix, m42); FIELD(CNA_Matrix, m43); FIELD(CNA_Matrix, m44);
    TYPE(CNA_Rectangle); FIELD(CNA_Rectangle, x); FIELD(CNA_Rectangle, y); FIELD(CNA_Rectangle, width); FIELD(CNA_Rectangle, height);
    TYPE(CNA_Viewport); FIELD(CNA_Viewport, x); FIELD(CNA_Viewport, y); FIELD(CNA_Viewport, width); FIELD(CNA_Viewport, height); FIELD(CNA_Viewport, min_depth); FIELD(CNA_Viewport, max_depth);
    TYPE(CNA_DisplayMode); FIELD(CNA_DisplayMode, struct_size); FIELD(CNA_DisplayMode, struct_version); FIELD(CNA_DisplayMode, width); FIELD(CNA_DisplayMode, height); FIELD(CNA_DisplayMode, aspect_ratio); FIELD(CNA_DisplayMode, format);
    TYPE(CNA_GraphicsAdapterInfo); FIELD(CNA_GraphicsAdapterInfo, struct_size); FIELD(CNA_GraphicsAdapterInfo, struct_version); FIELD(CNA_GraphicsAdapterInfo, adapter_index); FIELD(CNA_GraphicsAdapterInfo, is_default_adapter); FIELD(CNA_GraphicsAdapterInfo, is_wide_screen); FIELD(CNA_GraphicsAdapterInfo, use_null_device); FIELD(CNA_GraphicsAdapterInfo, use_reference_device); FIELD(CNA_GraphicsAdapterInfo, vendor_id); FIELD(CNA_GraphicsAdapterInfo, device_id); FIELD(CNA_GraphicsAdapterInfo, revision); FIELD(CNA_GraphicsAdapterInfo, subsystem_id); FIELD(CNA_GraphicsAdapterInfo, description_byte_length); FIELD(CNA_GraphicsAdapterInfo, device_name_byte_length);
    TYPE(CNA_GraphicsFormatSelection); FIELD(CNA_GraphicsFormatSelection, struct_size); FIELD(CNA_GraphicsFormatSelection, struct_version); FIELD(CNA_GraphicsFormatSelection, exact_match); FIELD(CNA_GraphicsFormatSelection, reserved); FIELD(CNA_GraphicsFormatSelection, format); FIELD(CNA_GraphicsFormatSelection, depth_format); FIELD(CNA_GraphicsFormatSelection, multi_sample_count);
    TYPE(CNA_PresentationParameters); FIELD(CNA_PresentationParameters, struct_size); FIELD(CNA_PresentationParameters, struct_version); FIELD(CNA_PresentationParameters, back_buffer_format); FIELD(CNA_PresentationParameters, back_buffer_width); FIELD(CNA_PresentationParameters, back_buffer_height); FIELD(CNA_PresentationParameters, depth_stencil_format); FIELD(CNA_PresentationParameters, multi_sample_count); FIELD(CNA_PresentationParameters, presentation_interval); FIELD(CNA_PresentationParameters, display_orientation); FIELD(CNA_PresentationParameters, render_target_usage); FIELD(CNA_PresentationParameters, is_full_screen); FIELD(CNA_PresentationParameters, headless_ext); FIELD(CNA_PresentationParameters, reserved);
    TYPE(CNA_GraphicsDeviceInformation); FIELD(CNA_GraphicsDeviceInformation, struct_size); FIELD(CNA_GraphicsDeviceInformation, struct_version); FIELD(CNA_GraphicsDeviceInformation, adapter_index); FIELD(CNA_GraphicsDeviceInformation, graphics_profile); FIELD(CNA_GraphicsDeviceInformation, presentation_parameters);
    TYPE(CNA_BlendState); FIELD(CNA_BlendState, struct_size); FIELD(CNA_BlendState, struct_version); FIELD(CNA_BlendState, alpha_blend_function); FIELD(CNA_BlendState, alpha_destination_blend); FIELD(CNA_BlendState, alpha_source_blend); FIELD(CNA_BlendState, color_blend_function); FIELD(CNA_BlendState, color_destination_blend); FIELD(CNA_BlendState, color_source_blend); FIELD(CNA_BlendState, color_write_channels); FIELD(CNA_BlendState, color_write_channels1); FIELD(CNA_BlendState, color_write_channels2); FIELD(CNA_BlendState, color_write_channels3); FIELD(CNA_BlendState, blend_factor); FIELD(CNA_BlendState, multi_sample_mask);
    TYPE(CNA_DepthStencilState); FIELD(CNA_DepthStencilState, struct_size); FIELD(CNA_DepthStencilState, struct_version); FIELD(CNA_DepthStencilState, depth_buffer_enable); FIELD(CNA_DepthStencilState, depth_buffer_write_enable); FIELD(CNA_DepthStencilState, stencil_enable); FIELD(CNA_DepthStencilState, two_sided_stencil_mode); FIELD(CNA_DepthStencilState, depth_buffer_function); FIELD(CNA_DepthStencilState, stencil_function); FIELD(CNA_DepthStencilState, stencil_mask); FIELD(CNA_DepthStencilState, stencil_write_mask); FIELD(CNA_DepthStencilState, reference_stencil); FIELD(CNA_DepthStencilState, stencil_fail); FIELD(CNA_DepthStencilState, stencil_depth_buffer_fail); FIELD(CNA_DepthStencilState, stencil_pass); FIELD(CNA_DepthStencilState, counter_clockwise_stencil_function); FIELD(CNA_DepthStencilState, counter_clockwise_stencil_fail); FIELD(CNA_DepthStencilState, counter_clockwise_stencil_depth_buffer_fail); FIELD(CNA_DepthStencilState, counter_clockwise_stencil_pass); FIELD(CNA_DepthStencilState, reserved);
    TYPE(CNA_RasterizerState); FIELD(CNA_RasterizerState, struct_size); FIELD(CNA_RasterizerState, struct_version); FIELD(CNA_RasterizerState, cull_mode); FIELD(CNA_RasterizerState, fill_mode); FIELD(CNA_RasterizerState, depth_bias); FIELD(CNA_RasterizerState, slope_scale_depth_bias); FIELD(CNA_RasterizerState, multi_sample_anti_alias); FIELD(CNA_RasterizerState, scissor_test_enable); FIELD(CNA_RasterizerState, reserved);
    TYPE(CNA_SamplerState); FIELD(CNA_SamplerState, struct_size); FIELD(CNA_SamplerState, struct_version); FIELD(CNA_SamplerState, address_u); FIELD(CNA_SamplerState, address_v); FIELD(CNA_SamplerState, address_w); FIELD(CNA_SamplerState, filter); FIELD(CNA_SamplerState, max_anisotropy); FIELD(CNA_SamplerState, max_mip_level); FIELD(CNA_SamplerState, mip_map_level_of_detail_bias); FIELD(CNA_SamplerState, reserved);
    TYPE(CNA_TextureSlotInfo); FIELD(CNA_TextureSlotInfo, struct_size); FIELD(CNA_TextureSlotInfo, struct_version); FIELD(CNA_TextureSlotInfo, bound); FIELD(CNA_TextureSlotInfo, reserved); FIELD(CNA_TextureSlotInfo, texture);
    TYPE(CNA_VertexElement); FIELD(CNA_VertexElement, offset); FIELD(CNA_VertexElement, format); FIELD(CNA_VertexElement, usage); FIELD(CNA_VertexElement, usage_index);
    TYPE(CNA_VertexBufferCreateInfo); FIELD(CNA_VertexBufferCreateInfo, struct_size); FIELD(CNA_VertexBufferCreateInfo, struct_version); FIELD(CNA_VertexBufferCreateInfo, vertex_declaration); FIELD(CNA_VertexBufferCreateInfo, vertex_count); FIELD(CNA_VertexBufferCreateInfo, buffer_usage); FIELD(CNA_VertexBufferCreateInfo, dynamic); FIELD(CNA_VertexBufferCreateInfo, reserved);
    TYPE(CNA_VertexBufferInfo); FIELD(CNA_VertexBufferInfo, struct_size); FIELD(CNA_VertexBufferInfo, struct_version); FIELD(CNA_VertexBufferInfo, vertex_count); FIELD(CNA_VertexBufferInfo, buffer_usage); FIELD(CNA_VertexBufferInfo, dynamic); FIELD(CNA_VertexBufferInfo, is_content_lost); FIELD(CNA_VertexBufferInfo, has_renderer); FIELD(CNA_VertexBufferInfo, reserved0); FIELD(CNA_VertexBufferInfo, vertex_stride); FIELD(CNA_VertexBufferInfo, vertex_element_count);
    TYPE(CNA_VertexBufferTransfer); FIELD(CNA_VertexBufferTransfer, struct_size); FIELD(CNA_VertexBufferTransfer, struct_version); FIELD(CNA_VertexBufferTransfer, vertex_type); FIELD(CNA_VertexBufferTransfer, options); FIELD(CNA_VertexBufferTransfer, start_index); FIELD(CNA_VertexBufferTransfer, element_count);
    TYPE(CNA_VertexPositionColor); FIELD(CNA_VertexPositionColor, position); FIELD(CNA_VertexPositionColor, color);
    TYPE(CNA_VertexPositionColorTexture); FIELD(CNA_VertexPositionColorTexture, position); FIELD(CNA_VertexPositionColorTexture, color); FIELD(CNA_VertexPositionColorTexture, texture_coordinate);
    TYPE(CNA_VertexPositionNormalTexture); FIELD(CNA_VertexPositionNormalTexture, position); FIELD(CNA_VertexPositionNormalTexture, normal); FIELD(CNA_VertexPositionNormalTexture, texture_coordinate);
    TYPE(CNA_VertexPositionTexture); FIELD(CNA_VertexPositionTexture, position); FIELD(CNA_VertexPositionTexture, texture_coordinate);
    TYPE(CNA_VertexBufferBinding); FIELD(CNA_VertexBufferBinding, vertex_buffer); FIELD(CNA_VertexBufferBinding, vertex_offset); FIELD(CNA_VertexBufferBinding, instance_frequency);
    TYPE(CNA_IndexBufferCreateInfo); FIELD(CNA_IndexBufferCreateInfo, struct_size); FIELD(CNA_IndexBufferCreateInfo, struct_version); FIELD(CNA_IndexBufferCreateInfo, index_count); FIELD(CNA_IndexBufferCreateInfo, index_element_size); FIELD(CNA_IndexBufferCreateInfo, buffer_usage); FIELD(CNA_IndexBufferCreateInfo, dynamic); FIELD(CNA_IndexBufferCreateInfo, reserved);
    TYPE(CNA_IndexBufferInfo); FIELD(CNA_IndexBufferInfo, struct_size); FIELD(CNA_IndexBufferInfo, struct_version); FIELD(CNA_IndexBufferInfo, index_count); FIELD(CNA_IndexBufferInfo, index_element_size); FIELD(CNA_IndexBufferInfo, buffer_usage); FIELD(CNA_IndexBufferInfo, dynamic); FIELD(CNA_IndexBufferInfo, is_content_lost); FIELD(CNA_IndexBufferInfo, has_renderer); FIELD(CNA_IndexBufferInfo, reserved);
    TYPE(CNA_IndexBufferTransfer); FIELD(CNA_IndexBufferTransfer, struct_size); FIELD(CNA_IndexBufferTransfer, struct_version); FIELD(CNA_IndexBufferTransfer, index_element_size); FIELD(CNA_IndexBufferTransfer, options); FIELD(CNA_IndexBufferTransfer, start_index); FIELD(CNA_IndexBufferTransfer, element_count);
    TYPE(CNA_RenderTarget2DCreateInfo); FIELD(CNA_RenderTarget2DCreateInfo, struct_size); FIELD(CNA_RenderTarget2DCreateInfo, struct_version); FIELD(CNA_RenderTarget2DCreateInfo, width); FIELD(CNA_RenderTarget2DCreateInfo, height); FIELD(CNA_RenderTarget2DCreateInfo, mip_map); FIELD(CNA_RenderTarget2DCreateInfo, reserved0); FIELD(CNA_RenderTarget2DCreateInfo, format); FIELD(CNA_RenderTarget2DCreateInfo, depth_format); FIELD(CNA_RenderTarget2DCreateInfo, multi_sample_count); FIELD(CNA_RenderTarget2DCreateInfo, usage); FIELD(CNA_RenderTarget2DCreateInfo, reserved1);
    TYPE(CNA_RenderTargetCubeCreateInfo); FIELD(CNA_RenderTargetCubeCreateInfo, struct_size); FIELD(CNA_RenderTargetCubeCreateInfo, struct_version); FIELD(CNA_RenderTargetCubeCreateInfo, size); FIELD(CNA_RenderTargetCubeCreateInfo, mip_map); FIELD(CNA_RenderTargetCubeCreateInfo, reserved); FIELD(CNA_RenderTargetCubeCreateInfo, format); FIELD(CNA_RenderTargetCubeCreateInfo, depth_format); FIELD(CNA_RenderTargetCubeCreateInfo, multi_sample_count); FIELD(CNA_RenderTargetCubeCreateInfo, usage);
    TYPE(CNA_RenderTargetInfo); FIELD(CNA_RenderTargetInfo, struct_size); FIELD(CNA_RenderTargetInfo, struct_version); FIELD(CNA_RenderTargetInfo, kind); FIELD(CNA_RenderTargetInfo, width); FIELD(CNA_RenderTargetInfo, height); FIELD(CNA_RenderTargetInfo, level_count); FIELD(CNA_RenderTargetInfo, format); FIELD(CNA_RenderTargetInfo, depth_format); FIELD(CNA_RenderTargetInfo, multi_sample_count); FIELD(CNA_RenderTargetInfo, usage); FIELD(CNA_RenderTargetInfo, is_content_lost); FIELD(CNA_RenderTargetInfo, renderer_available); FIELD(CNA_RenderTargetInfo, reserved);
    TYPE(CNA_RenderTargetBinding); FIELD(CNA_RenderTargetBinding, struct_size); FIELD(CNA_RenderTargetBinding, struct_version); FIELD(CNA_RenderTargetBinding, render_target); FIELD(CNA_RenderTargetBinding, array_slice); FIELD(CNA_RenderTargetBinding, cube_map_face);
    TYPE(CNA_BackBufferReadback); FIELD(CNA_BackBufferReadback, struct_size); FIELD(CNA_BackBufferReadback, struct_version); FIELD(CNA_BackBufferReadback, has_source_rectangle); FIELD(CNA_BackBufferReadback, reserved); FIELD(CNA_BackBufferReadback, source_rectangle); FIELD(CNA_BackBufferReadback, start_index); FIELD(CNA_BackBufferReadback, element_count);
    TYPE(CNA_UserPrimitives); FIELD(CNA_UserPrimitives, struct_size); FIELD(CNA_UserPrimitives, struct_version); FIELD(CNA_UserPrimitives, primitive_type); FIELD(CNA_UserPrimitives, vertex_source); FIELD(CNA_UserPrimitives, vertex_data); FIELD(CNA_UserPrimitives, vertex_declaration); FIELD(CNA_UserPrimitives, vertex_offset); FIELD(CNA_UserPrimitives, num_vertices); FIELD(CNA_UserPrimitives, primitive_count); FIELD(CNA_UserPrimitives, reserved);
    TYPE(CNA_UserIndices); FIELD(CNA_UserIndices, struct_size); FIELD(CNA_UserIndices, struct_version); FIELD(CNA_UserIndices, index_element_size); FIELD(CNA_UserIndices, index_offset); FIELD(CNA_UserIndices, index_data);
    TYPE(CNA_SpriteFontGlyph); FIELD(CNA_SpriteFontGlyph, struct_size); FIELD(CNA_SpriteFontGlyph, struct_version); FIELD(CNA_SpriteFontGlyph, glyph_bounds); FIELD(CNA_SpriteFontGlyph, cropping); FIELD(CNA_SpriteFontGlyph, character); FIELD(CNA_SpriteFontGlyph, reserved); FIELD(CNA_SpriteFontGlyph, kerning);
    TYPE(CNA_SpriteFontCreateInfo); FIELD(CNA_SpriteFontCreateInfo, struct_size); FIELD(CNA_SpriteFontCreateInfo, struct_version); FIELD(CNA_SpriteFontCreateInfo, texture); FIELD(CNA_SpriteFontCreateInfo, glyphs); FIELD(CNA_SpriteFontCreateInfo, glyph_count); FIELD(CNA_SpriteFontCreateInfo, line_spacing); FIELD(CNA_SpriteFontCreateInfo, spacing); FIELD(CNA_SpriteFontCreateInfo, default_character); FIELD(CNA_SpriteFontCreateInfo, has_default_character); FIELD(CNA_SpriteFontCreateInfo, reserved);
    TYPE(CNA_SpriteFontInfo); FIELD(CNA_SpriteFontInfo, struct_size); FIELD(CNA_SpriteFontInfo, struct_version); FIELD(CNA_SpriteFontInfo, character_count); FIELD(CNA_SpriteFontInfo, line_spacing); FIELD(CNA_SpriteFontInfo, spacing); FIELD(CNA_SpriteFontInfo, default_character); FIELD(CNA_SpriteFontInfo, has_default_character); FIELD(CNA_SpriteFontInfo, reserved);
    TYPE(CNA_Texture2DInfo); FIELD(CNA_Texture2DInfo, struct_size); FIELD(CNA_Texture2DInfo, struct_version); FIELD(CNA_Texture2DInfo, width); FIELD(CNA_Texture2DInfo, height); FIELD(CNA_Texture2DInfo, level_count); FIELD(CNA_Texture2DInfo, format);
    TYPE(CNA_Texture2DCreateInfo); FIELD(CNA_Texture2DCreateInfo, struct_size); FIELD(CNA_Texture2DCreateInfo, struct_version); FIELD(CNA_Texture2DCreateInfo, width); FIELD(CNA_Texture2DCreateInfo, height); FIELD(CNA_Texture2DCreateInfo, mip_map); FIELD(CNA_Texture2DCreateInfo, reserved); FIELD(CNA_Texture2DCreateInfo, format);
    TYPE(CNA_Texture2DTransfer); FIELD(CNA_Texture2DTransfer, struct_size); FIELD(CNA_Texture2DTransfer, struct_version); FIELD(CNA_Texture2DTransfer, level); FIELD(CNA_Texture2DTransfer, has_rectangle); FIELD(CNA_Texture2DTransfer, reserved); FIELD(CNA_Texture2DTransfer, rectangle); FIELD(CNA_Texture2DTransfer, start_index); FIELD(CNA_Texture2DTransfer, element_count);
    TYPE(CNA_Texture2DDecodeInfo); FIELD(CNA_Texture2DDecodeInfo, struct_size); FIELD(CNA_Texture2DDecodeInfo, struct_version); FIELD(CNA_Texture2DDecodeInfo, width); FIELD(CNA_Texture2DDecodeInfo, height); FIELD(CNA_Texture2DDecodeInfo, zoom); FIELD(CNA_Texture2DDecodeInfo, reserved);
    TYPE(CNA_Texture3DCreateInfo); FIELD(CNA_Texture3DCreateInfo, struct_size); FIELD(CNA_Texture3DCreateInfo, struct_version); FIELD(CNA_Texture3DCreateInfo, width); FIELD(CNA_Texture3DCreateInfo, height); FIELD(CNA_Texture3DCreateInfo, depth); FIELD(CNA_Texture3DCreateInfo, mip_map); FIELD(CNA_Texture3DCreateInfo, reserved0); FIELD(CNA_Texture3DCreateInfo, format); FIELD(CNA_Texture3DCreateInfo, reserved1);
    TYPE(CNA_Texture3DInfo); FIELD(CNA_Texture3DInfo, struct_size); FIELD(CNA_Texture3DInfo, struct_version); FIELD(CNA_Texture3DInfo, width); FIELD(CNA_Texture3DInfo, height); FIELD(CNA_Texture3DInfo, depth); FIELD(CNA_Texture3DInfo, level_count); FIELD(CNA_Texture3DInfo, format); FIELD(CNA_Texture3DInfo, reserved);
    TYPE(CNA_Texture3DTransfer); FIELD(CNA_Texture3DTransfer, struct_size); FIELD(CNA_Texture3DTransfer, struct_version); FIELD(CNA_Texture3DTransfer, level); FIELD(CNA_Texture3DTransfer, left); FIELD(CNA_Texture3DTransfer, top); FIELD(CNA_Texture3DTransfer, right); FIELD(CNA_Texture3DTransfer, bottom); FIELD(CNA_Texture3DTransfer, front); FIELD(CNA_Texture3DTransfer, back); FIELD(CNA_Texture3DTransfer, reserved); FIELD(CNA_Texture3DTransfer, start_index); FIELD(CNA_Texture3DTransfer, element_count);
    TYPE(CNA_TextureCubeCreateInfo); FIELD(CNA_TextureCubeCreateInfo, struct_size); FIELD(CNA_TextureCubeCreateInfo, struct_version); FIELD(CNA_TextureCubeCreateInfo, size); FIELD(CNA_TextureCubeCreateInfo, mip_map); FIELD(CNA_TextureCubeCreateInfo, reserved0); FIELD(CNA_TextureCubeCreateInfo, format); FIELD(CNA_TextureCubeCreateInfo, reserved1);
    TYPE(CNA_TextureCubeInfo); FIELD(CNA_TextureCubeInfo, struct_size); FIELD(CNA_TextureCubeInfo, struct_version); FIELD(CNA_TextureCubeInfo, size); FIELD(CNA_TextureCubeInfo, level_count); FIELD(CNA_TextureCubeInfo, format); FIELD(CNA_TextureCubeInfo, reserved);
    TYPE(CNA_TextureCubeTransfer); FIELD(CNA_TextureCubeTransfer, struct_size); FIELD(CNA_TextureCubeTransfer, struct_version); FIELD(CNA_TextureCubeTransfer, face); FIELD(CNA_TextureCubeTransfer, level); FIELD(CNA_TextureCubeTransfer, has_rectangle); FIELD(CNA_TextureCubeTransfer, reserved0); FIELD(CNA_TextureCubeTransfer, rectangle); FIELD(CNA_TextureCubeTransfer, reserved1); FIELD(CNA_TextureCubeTransfer, start_index); FIELD(CNA_TextureCubeTransfer, element_count);
    TYPE(CNA_EffectParameterCreateInfo); FIELD(CNA_EffectParameterCreateInfo, struct_size); FIELD(CNA_EffectParameterCreateInfo, struct_version); FIELD(CNA_EffectParameterCreateInfo, name); FIELD(CNA_EffectParameterCreateInfo, semantic); FIELD(CNA_EffectParameterCreateInfo, row_count); FIELD(CNA_EffectParameterCreateInfo, column_count); FIELD(CNA_EffectParameterCreateInfo, parameter_class); FIELD(CNA_EffectParameterCreateInfo, parameter_type);
    TYPE(CNA_EffectParameterInfo); FIELD(CNA_EffectParameterInfo, struct_size); FIELD(CNA_EffectParameterInfo, struct_version); FIELD(CNA_EffectParameterInfo, row_count); FIELD(CNA_EffectParameterInfo, column_count); FIELD(CNA_EffectParameterInfo, parameter_class); FIELD(CNA_EffectParameterInfo, parameter_type);
    TYPE(CNA_EffectAnnotationCreateInfo); FIELD(CNA_EffectAnnotationCreateInfo, struct_size); FIELD(CNA_EffectAnnotationCreateInfo, struct_version); FIELD(CNA_EffectAnnotationCreateInfo, name); FIELD(CNA_EffectAnnotationCreateInfo, semantic); FIELD(CNA_EffectAnnotationCreateInfo, row_count); FIELD(CNA_EffectAnnotationCreateInfo, column_count); FIELD(CNA_EffectAnnotationCreateInfo, parameter_class); FIELD(CNA_EffectAnnotationCreateInfo, parameter_type); FIELD(CNA_EffectAnnotationCreateInfo, data); FIELD(CNA_EffectAnnotationCreateInfo, data_count); FIELD(CNA_EffectAnnotationCreateInfo, cached_string);
    TYPE(CNA_EffectAnnotationInfo); FIELD(CNA_EffectAnnotationInfo, struct_size); FIELD(CNA_EffectAnnotationInfo, struct_version); FIELD(CNA_EffectAnnotationInfo, row_count); FIELD(CNA_EffectAnnotationInfo, column_count); FIELD(CNA_EffectAnnotationInfo, parameter_class); FIELD(CNA_EffectAnnotationInfo, parameter_type);
    TYPE(CNA_SpriteBatchBeginInfo); FIELD(CNA_SpriteBatchBeginInfo, struct_size); FIELD(CNA_SpriteBatchBeginInfo, struct_version); FIELD(CNA_SpriteBatchBeginInfo, sort_mode); FIELD(CNA_SpriteBatchBeginInfo, reserved);
    TYPE(CNA_SpriteCommand); FIELD(CNA_SpriteCommand, struct_size); FIELD(CNA_SpriteCommand, struct_version); FIELD(CNA_SpriteCommand, texture); FIELD(CNA_SpriteCommand, destination); FIELD(CNA_SpriteCommand, source); FIELD(CNA_SpriteCommand, color); FIELD(CNA_SpriteCommand, rotation); FIELD(CNA_SpriteCommand, origin); FIELD(CNA_SpriteCommand, effects); FIELD(CNA_SpriteCommand, layer_depth);
    TYPE(CNA_SpriteScaledCommand); FIELD(CNA_SpriteScaledCommand, struct_size); FIELD(CNA_SpriteScaledCommand, struct_version); FIELD(CNA_SpriteScaledCommand, texture); FIELD(CNA_SpriteScaledCommand, position); FIELD(CNA_SpriteScaledCommand, source); FIELD(CNA_SpriteScaledCommand, color); FIELD(CNA_SpriteScaledCommand, rotation); FIELD(CNA_SpriteScaledCommand, origin); FIELD(CNA_SpriteScaledCommand, scale); FIELD(CNA_SpriteScaledCommand, effects); FIELD(CNA_SpriteScaledCommand, layer_depth);
    TYPE(CNA_KeyboardState); FIELD(CNA_KeyboardState, struct_size); FIELD(CNA_KeyboardState, struct_version); FIELD(CNA_KeyboardState, pressed_key_words);
    TYPE(CNA_MouseState); FIELD(CNA_MouseState, struct_size); FIELD(CNA_MouseState, struct_version); FIELD(CNA_MouseState, x); FIELD(CNA_MouseState, y); FIELD(CNA_MouseState, scroll_wheel); FIELD(CNA_MouseState, horizontal_scroll_wheel); FIELD(CNA_MouseState, pressed_buttons); FIELD(CNA_MouseState, reserved);
    TYPE(CNA_GamePadAnalogState); FIELD(CNA_GamePadAnalogState, left_thumb_stick); FIELD(CNA_GamePadAnalogState, right_thumb_stick); FIELD(CNA_GamePadAnalogState, left_trigger); FIELD(CNA_GamePadAnalogState, right_trigger);
    TYPE(CNA_GamePadState); FIELD(CNA_GamePadState, struct_size); FIELD(CNA_GamePadState, struct_version); FIELD(CNA_GamePadState, is_connected); FIELD(CNA_GamePadState, reserved0); FIELD(CNA_GamePadState, packet_number); FIELD(CNA_GamePadState, pressed_buttons); FIELD(CNA_GamePadState, reserved1); FIELD(CNA_GamePadState, analog);
    TYPE(CNA_GamePadCapabilities); FIELD(CNA_GamePadCapabilities, struct_size); FIELD(CNA_GamePadCapabilities, struct_version); FIELD(CNA_GamePadCapabilities, gamepad_type); FIELD(CNA_GamePadCapabilities, is_connected); FIELD(CNA_GamePadCapabilities, has_a_button); FIELD(CNA_GamePadCapabilities, has_b_button); FIELD(CNA_GamePadCapabilities, has_x_button); FIELD(CNA_GamePadCapabilities, has_y_button); FIELD(CNA_GamePadCapabilities, has_back_button); FIELD(CNA_GamePadCapabilities, has_start_button); FIELD(CNA_GamePadCapabilities, has_big_button); FIELD(CNA_GamePadCapabilities, has_dpad_up_button); FIELD(CNA_GamePadCapabilities, has_dpad_down_button); FIELD(CNA_GamePadCapabilities, has_dpad_left_button); FIELD(CNA_GamePadCapabilities, has_dpad_right_button); FIELD(CNA_GamePadCapabilities, has_left_shoulder_button); FIELD(CNA_GamePadCapabilities, has_right_shoulder_button); FIELD(CNA_GamePadCapabilities, has_left_stick_button); FIELD(CNA_GamePadCapabilities, has_right_stick_button); FIELD(CNA_GamePadCapabilities, has_left_x_thumb_stick); FIELD(CNA_GamePadCapabilities, has_left_y_thumb_stick); FIELD(CNA_GamePadCapabilities, has_right_x_thumb_stick); FIELD(CNA_GamePadCapabilities, has_right_y_thumb_stick); FIELD(CNA_GamePadCapabilities, has_left_trigger); FIELD(CNA_GamePadCapabilities, has_right_trigger); FIELD(CNA_GamePadCapabilities, has_left_vibration_motor); FIELD(CNA_GamePadCapabilities, has_right_vibration_motor); FIELD(CNA_GamePadCapabilities, has_voice_support); FIELD(CNA_GamePadCapabilities, has_light_bar_ext); FIELD(CNA_GamePadCapabilities, has_trigger_vibration_motors_ext); FIELD(CNA_GamePadCapabilities, has_misc1_ext); FIELD(CNA_GamePadCapabilities, has_paddle1_ext); FIELD(CNA_GamePadCapabilities, has_paddle2_ext); FIELD(CNA_GamePadCapabilities, has_paddle3_ext); FIELD(CNA_GamePadCapabilities, has_paddle4_ext); FIELD(CNA_GamePadCapabilities, has_touchpad_ext); FIELD(CNA_GamePadCapabilities, has_gyro_ext); FIELD(CNA_GamePadCapabilities, has_accelerometer_ext); FIELD(CNA_GamePadCapabilities, reserved);
    TYPE(CNA_TouchLocation); FIELD(CNA_TouchLocation, id); FIELD(CNA_TouchLocation, state); FIELD(CNA_TouchLocation, position); FIELD(CNA_TouchLocation, previous_state); FIELD(CNA_TouchLocation, previous_position); FIELD(CNA_TouchLocation, pressure);
    TYPE(CNA_TouchCapabilities); FIELD(CNA_TouchCapabilities, struct_size); FIELD(CNA_TouchCapabilities, struct_version); FIELD(CNA_TouchCapabilities, is_connected); FIELD(CNA_TouchCapabilities, reserved); FIELD(CNA_TouchCapabilities, maximum_touch_count);
    TYPE(CNA_TouchState); FIELD(CNA_TouchState, struct_size); FIELD(CNA_TouchState, struct_version); FIELD(CNA_TouchState, is_connected); FIELD(CNA_TouchState, reserved); FIELD(CNA_TouchState, touch_count); FIELD(CNA_TouchState, touches);
    TYPE(CNA_GestureSample); FIELD(CNA_GestureSample, struct_size); FIELD(CNA_GestureSample, struct_version); FIELD(CNA_GestureSample, gesture_type); FIELD(CNA_GestureSample, finger_id_ext); FIELD(CNA_GestureSample, finger_id2_ext); FIELD(CNA_GestureSample, reserved); FIELD(CNA_GestureSample, timestamp_ticks); FIELD(CNA_GestureSample, position); FIELD(CNA_GestureSample, position2); FIELD(CNA_GestureSample, delta); FIELD(CNA_GestureSample, delta2);
    return 0;
}
