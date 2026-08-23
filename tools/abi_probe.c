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

    TYPE(CNA_StringView); FIELD(CNA_StringView, data); FIELD(CNA_StringView, byte_length);
    TYPE(CNA_ErrorInfo); FIELD(CNA_ErrorInfo, struct_size); FIELD(CNA_ErrorInfo, struct_version); FIELD(CNA_ErrorInfo, result); FIELD(CNA_ErrorInfo, category); FIELD(CNA_ErrorInfo, message_byte_length);
    TYPE(CNA_GameTime); FIELD(CNA_GameTime, total_game_time_ticks); FIELD(CNA_GameTime, elapsed_game_time_ticks); FIELD(CNA_GameTime, is_running_slowly); FIELD(CNA_GameTime, reserved);
    TYPE(CNA_CallbackError); FIELD(CNA_CallbackError, struct_size); FIELD(CNA_CallbackError, struct_version); FIELD(CNA_CallbackError, message);
    TYPE(CNA_GameCallbacks); FIELD(CNA_GameCallbacks, struct_size); FIELD(CNA_GameCallbacks, struct_version); FIELD(CNA_GameCallbacks, load_content); FIELD(CNA_GameCallbacks, update); FIELD(CNA_GameCallbacks, draw); FIELD(CNA_GameCallbacks, unload_content); FIELD(CNA_GameCallbacks, exiting); FIELD(CNA_GameCallbacks, context);
    TYPE(CNA_GameFrameHooks); FIELD(CNA_GameFrameHooks, struct_size); FIELD(CNA_GameFrameHooks, struct_version); FIELD(CNA_GameFrameHooks, initialize); FIELD(CNA_GameFrameHooks, begin_run); FIELD(CNA_GameFrameHooks, end_run); FIELD(CNA_GameFrameHooks, begin_draw); FIELD(CNA_GameFrameHooks, end_draw); FIELD(CNA_GameFrameHooks, context);
    TYPE(CNA_GameCreateInfo); FIELD(CNA_GameCreateInfo, struct_size); FIELD(CNA_GameCreateInfo, struct_version); FIELD(CNA_GameCreateInfo, is_fixed_time_step); FIELD(CNA_GameCreateInfo, reserved); FIELD(CNA_GameCreateInfo, target_elapsed_time_ticks); FIELD(CNA_GameCreateInfo, window_title); FIELD(CNA_GameCreateInfo, callbacks);
    TYPE(CNA_Color); FIELD(CNA_Color, r); FIELD(CNA_Color, g); FIELD(CNA_Color, b); FIELD(CNA_Color, a);
    TYPE(CNA_Vector2); FIELD(CNA_Vector2, x); FIELD(CNA_Vector2, y);
    TYPE(CNA_Rectangle); FIELD(CNA_Rectangle, x); FIELD(CNA_Rectangle, y); FIELD(CNA_Rectangle, width); FIELD(CNA_Rectangle, height);
    TYPE(CNA_Viewport); FIELD(CNA_Viewport, x); FIELD(CNA_Viewport, y); FIELD(CNA_Viewport, width); FIELD(CNA_Viewport, height); FIELD(CNA_Viewport, min_depth); FIELD(CNA_Viewport, max_depth);
    TYPE(CNA_Texture2DInfo); FIELD(CNA_Texture2DInfo, struct_size); FIELD(CNA_Texture2DInfo, struct_version); FIELD(CNA_Texture2DInfo, width); FIELD(CNA_Texture2DInfo, height); FIELD(CNA_Texture2DInfo, level_count); FIELD(CNA_Texture2DInfo, format);
    TYPE(CNA_Texture2DCreateInfo); FIELD(CNA_Texture2DCreateInfo, struct_size); FIELD(CNA_Texture2DCreateInfo, struct_version); FIELD(CNA_Texture2DCreateInfo, width); FIELD(CNA_Texture2DCreateInfo, height); FIELD(CNA_Texture2DCreateInfo, mip_map); FIELD(CNA_Texture2DCreateInfo, reserved); FIELD(CNA_Texture2DCreateInfo, format);
    TYPE(CNA_Texture2DTransfer); FIELD(CNA_Texture2DTransfer, struct_size); FIELD(CNA_Texture2DTransfer, struct_version); FIELD(CNA_Texture2DTransfer, level); FIELD(CNA_Texture2DTransfer, has_rectangle); FIELD(CNA_Texture2DTransfer, reserved); FIELD(CNA_Texture2DTransfer, rectangle); FIELD(CNA_Texture2DTransfer, start_index); FIELD(CNA_Texture2DTransfer, element_count);
    TYPE(CNA_Texture2DDecodeInfo); FIELD(CNA_Texture2DDecodeInfo, struct_size); FIELD(CNA_Texture2DDecodeInfo, struct_version); FIELD(CNA_Texture2DDecodeInfo, width); FIELD(CNA_Texture2DDecodeInfo, height); FIELD(CNA_Texture2DDecodeInfo, zoom); FIELD(CNA_Texture2DDecodeInfo, reserved);
    TYPE(CNA_SpriteBatchBeginInfo); FIELD(CNA_SpriteBatchBeginInfo, struct_size); FIELD(CNA_SpriteBatchBeginInfo, struct_version); FIELD(CNA_SpriteBatchBeginInfo, sort_mode); FIELD(CNA_SpriteBatchBeginInfo, reserved);
    TYPE(CNA_SpriteScaledCommand); FIELD(CNA_SpriteScaledCommand, struct_size); FIELD(CNA_SpriteScaledCommand, struct_version); FIELD(CNA_SpriteScaledCommand, texture); FIELD(CNA_SpriteScaledCommand, position); FIELD(CNA_SpriteScaledCommand, source); FIELD(CNA_SpriteScaledCommand, color); FIELD(CNA_SpriteScaledCommand, rotation); FIELD(CNA_SpriteScaledCommand, origin); FIELD(CNA_SpriteScaledCommand, scale); FIELD(CNA_SpriteScaledCommand, effects); FIELD(CNA_SpriteScaledCommand, layer_depth);
    TYPE(CNA_KeyboardState); FIELD(CNA_KeyboardState, struct_size); FIELD(CNA_KeyboardState, struct_version); FIELD(CNA_KeyboardState, pressed_key_words);
    TYPE(CNA_MouseState); FIELD(CNA_MouseState, struct_size); FIELD(CNA_MouseState, struct_version); FIELD(CNA_MouseState, x); FIELD(CNA_MouseState, y); FIELD(CNA_MouseState, scroll_wheel); FIELD(CNA_MouseState, horizontal_scroll_wheel); FIELD(CNA_MouseState, pressed_buttons); FIELD(CNA_MouseState, reserved);
    TYPE(CNA_GamePadAnalogState); FIELD(CNA_GamePadAnalogState, left_thumb_stick); FIELD(CNA_GamePadAnalogState, right_thumb_stick); FIELD(CNA_GamePadAnalogState, left_trigger); FIELD(CNA_GamePadAnalogState, right_trigger);
    TYPE(CNA_GamePadState); FIELD(CNA_GamePadState, struct_size); FIELD(CNA_GamePadState, struct_version); FIELD(CNA_GamePadState, is_connected); FIELD(CNA_GamePadState, reserved0); FIELD(CNA_GamePadState, packet_number); FIELD(CNA_GamePadState, pressed_buttons); FIELD(CNA_GamePadState, reserved1); FIELD(CNA_GamePadState, analog);
    return 0;
}
