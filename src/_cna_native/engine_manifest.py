"""ctypes manifest for CNA's ``engine_layer.h`` family.

Split out of :mod:`_cna_native.loader` because it is a family of its own,
imported because ``cna.extensions.engine`` projects it rather than because the
XNA profile needs any of it. Every entry is proven against the canonical C
declaration by ``tools/verify_prototypes.py``, and the fourth column states the
ownership contract the Python wrapper has to keep.

Routes are added as their consumers land, never speculatively: an imported route
with no caller is dead native surface, and ``tools/verify_route_reachability.py``
fails on one.
"""

from __future__ import annotations

import ctypes as c

from . import abi
from . import engine_abi as engine

#: The engine layer's own identity. These two are the only routes in the family
#: that answer meaningfully in a build with no engine layer, which is what makes
#: them the ones that tell the two kinds of "not supported" apart.
ENGINE_IDENTITY_MANIFEST: tuple[tuple[str, object, list[object], str], ...] = (
    ("cna_engine_layer_get_version", c.c_uint32, [c.POINTER(c.c_int32)],
     "pure function over caller-owned output; nothing is retained"),
    ("cna_engine_layer_copy_version_string", c.c_uint32,
     [c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol"),
)

#: GPU compute: the barrier mask, storage buffers, compute programs and timers.
ENGINE_COMPUTE_MANIFEST: tuple[tuple[str, object, list[object], str], ...] = (
    ("cna_graphics_memory_barrier_has", c.c_uint32,
     [c.c_uint32, c.c_uint32, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),

    ("cna_storage_buffer_create", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)],
     "owned storage buffer; borrows the graphics device for the call"),
    ("cna_storage_buffer_create_typed", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)],
     "owned storage buffer; borrows the graphics device for the call"),
    ("cna_storage_buffer_set_bytes", c.c_uint32, [c.c_uint64, c.c_void_p, c.c_uint64],
     "borrowed buffer; copies the bytes, retains nothing"),
    ("cna_storage_buffer_get_bytes", c.c_uint32, [c.c_uint64, c.c_void_p, c.c_uint64],
     "caller output; borrowed buffer"),
    ("cna_storage_buffer_get_byte_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; borrowed buffer"),
    ("cna_storage_buffer_set_elements", c.c_uint32,
     [c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64],
     "borrowed buffer; copies the elements, retains nothing"),
    ("cna_storage_buffer_get_elements", c.c_uint32,
     [c.c_uint64, c.c_void_p, c.c_uint64, c.c_uint64],
     "caller output; borrowed buffer"),
    ("cna_storage_buffer_get_element_count", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)], "caller output; borrowed buffer"),
    ("cna_storage_buffer_get_element_byte_size", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)], "caller output; borrowed buffer"),
    ("cna_storage_buffer_destroy", c.c_uint32, [c.c_uint64],
     "consumes storage buffer"),

    ("cna_compute_shader_create", c.c_uint32,
     [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)],
     "owned compute shader; borrows the device and the source for the call"),
    ("cna_compute_shader_set_uniform_int", c.c_uint32,
     [c.c_uint64, abi.CNA_StringView, c.c_int32],
     "borrowed shader; copies the value"),
    ("cna_compute_shader_set_uniform_float", c.c_uint32,
     [c.c_uint64, abi.CNA_StringView, c.c_float],
     "borrowed shader; copies the value"),
    ("cna_compute_shader_bind_storage_buffer", c.c_uint32,
     [c.c_uint64, c.c_int32, c.c_uint64],
     "borrowed shader; the buffer is BORROWED and must outlive every dispatch"),
    ("cna_compute_shader_bind_texture", c.c_uint32,
     [c.c_uint64, c.c_int32, abi.CNA_StringView, c.c_uint64],
     "borrowed shader; the texture is BORROWED and must outlive every dispatch"),
    ("cna_compute_shader_is_image_binding_supported", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint8)], "caller output; borrowed shader"),
    ("cna_compute_shader_bind_image", c.c_uint32,
     [c.c_uint64, c.c_int32, c.c_uint64, c.c_uint32],
     "borrowed shader; the texture is BORROWED and must outlive every dispatch"),
    ("cna_compute_shader_dispatch", c.c_uint32,
     [c.c_uint64, c.c_int32, c.c_int32, c.c_int32], "borrowed shader"),
    ("cna_compute_shader_barrier", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed shader"),
    ("cna_compute_shader_is_valid", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed shader"),
    ("cna_compute_shader_copy_compile_error", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol"),
    ("cna_compute_shader_destroy", c.c_uint32, [c.c_uint64],
     "consumes compute shader"),

    ("cna_gpu_timer_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned GPU timer; borrows the graphics device for the call"),
    ("cna_gpu_timer_is_supported", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed timer"),
    ("cna_gpu_timer_copy_unsupported_reason", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol"),
    ("cna_gpu_timer_begin", c.c_uint32, [c.c_uint64], "borrowed timer"),
    ("cna_gpu_timer_end", c.c_uint32, [c.c_uint64], "borrowed timer"),
    ("cna_gpu_timer_is_result_available", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed timer"),
    ("cna_gpu_timer_poll", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed timer"),
    ("cna_gpu_timer_get_last_milliseconds", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_double)], "caller output; borrowed timer"),
    ("cna_gpu_timer_get_sample_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int32)],
     "caller output; borrowed timer"),
    ("cna_gpu_timer_is_open", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed timer"),
    ("cna_gpu_timer_destroy", c.c_uint32, [c.c_uint64], "consumes GPU timer"),
)

#: The post-process foundation: pooled intermediates, the named shader-effect
#: cache, the render-target save/restore bracket, full-screen drawing, the pass
#: vocabulary and the chain that orders passes.
ENGINE_POSTPROCESS_MANIFEST: tuple[tuple[str, object, list[object], str], ...] = (
    ("cna_render_target_pool_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned pool; borrows the graphics device for the call"),
    ("cna_render_target_pool_acquire", c.c_uint32,
     [c.c_uint64, c.c_int32, c.c_int32, c.c_uint32, c.c_uint32, c.c_int32,
      c.POINTER(c.c_uint64)],
     "owned VIEW of a pool-owned target; released with cna_render_target_destroy, "
     "which does not dispose the pooled target. The pool refuses reset and "
     "destruction while any view is outstanding"),
    ("cna_render_target_pool_reset", c.c_uint32, [c.c_uint64],
     "borrowed pool; refused while a borrowed view is outstanding"),
    ("cna_render_target_pool_get_target_count", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)], "caller output; borrowed pool"),
    ("cna_render_target_pool_get_estimated_bytes", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)], "caller output; borrowed pool"),
    ("cna_render_target_pool_destroy", c.c_uint32, [c.c_uint64],
     "consumes pool; refused while a borrowed view is outstanding"),

    ("cna_shader_effect_factory_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned factory; borrows the graphics device for the call"),
    ("cna_shader_effect_factory_acquire", c.c_uint32,
     [c.c_uint64, abi.CNA_StringView, abi.CNA_StringView, abi.CNA_StringView,
      c.POINTER(c.c_uint64)],
     "owned VIEW of a factory-owned effect; released with cna_effect_destroy. "
     "The factory refuses clear and destruction while any view is outstanding"),
    ("cna_shader_effect_factory_contains", c.c_uint32,
     [c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint8)],
     "caller output; borrowed factory"),
    ("cna_shader_effect_factory_get_compile_count", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)], "caller output; borrowed factory"),
    ("cna_shader_effect_factory_clear", c.c_uint32, [c.c_uint64],
     "borrowed factory; refused while a borrowed effect view is outstanding"),
    ("cna_shader_effect_factory_destroy", c.c_uint32, [c.c_uint64],
     "consumes factory; refused while a borrowed effect view is outstanding"),

    ("cna_scoped_render_target_begin", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint64)],
     "owned active scope; borrows the device and the destination"),
    ("cna_scoped_render_target_get_has_recorded_previous", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint8)], "caller output; borrowed scope"),
    ("cna_scoped_render_target_end", c.c_uint32, [c.c_uint64],
     "consumes scope; must be the innermost scope on its device"),

    ("cna_fullscreen_pass_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned full-screen pass; borrows the graphics device for the call"),
    ("cna_fullscreen_pass_draw", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.c_uint64, c.c_uint64, c.c_int32, c.c_int32,
      c.POINTER(abi.CNA_SamplerState)],
     "borrowed pass; source, destination and effect are borrowed for the call"),
    ("cna_fullscreen_pass_draw_over_current_target", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.c_uint64, c.c_int32, c.c_int32,
      c.POINTER(abi.CNA_SamplerState)],
     "borrowed pass; source and effect are borrowed for the call"),
    ("cna_fullscreen_pass_destroy", c.c_uint32, [c.c_uint64],
     "consumes full-screen pass"),

    ("cna_post_process_context_init", c.c_uint32,
     [c.POINTER(engine.CNA_PostProcessContext)],
     "fills a caller-owned value structure with CNA's own defaults"),
    ("cna_blit_pass_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned pass; borrows the graphics device for the call"),
    ("cna_post_process_effect_pass_create", c.c_uint32,
     [c.c_uint64, c.c_uint64, abi.CNA_StringView, c.POINTER(c.c_uint64)],
     "owned pass; the effect is BORROWED and must outlive the pass"),
    ("cna_post_process_effect_pass_get_effect", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; the effect is borrowed from the pass and must not be destroyed"),
    ("cna_post_process_effect_pass_set_effect", c.c_uint32, [c.c_uint64, c.c_uint64],
     "borrowed pass; the new effect is BORROWED and the old one is not released"),
    ("cna_post_process_pass_apply", c.c_uint32,
     [c.c_uint64, c.POINTER(engine.CNA_PostProcessContext)],
     "borrowed pass; every handle in the context is borrowed for the call"),
    ("cna_post_process_pass_copy_name", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol"),
    ("cna_post_process_pass_is_supported", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed pass and device"),
    ("cna_post_process_pass_destroy", c.c_uint32, [c.c_uint64],
     "consumes pass, and the effect it owns if it owns one"),

    ("cna_post_process_chain_create", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned chain; borrows the graphics device for the call"),
    ("cna_post_process_chain_destroy", c.c_uint32, [c.c_uint64],
     "consumes chain and every pass it owns; borrowed passes survive it"),
    ("cna_post_process_chain_add_pass", c.c_uint32, [c.c_uint64, c.c_uint64],
     "borrowed chain; the pass stays the caller's and must outlive its membership"),
    ("cna_post_process_chain_clear", c.c_uint32, [c.c_uint64],
     "borrowed chain; drops every pass it borrows, and would release any it owned"),
    ("cna_post_process_chain_get_pass_count", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_int32)], "caller output; borrowed chain"),
    ("cna_post_process_chain_apply", c.c_uint32,
     [c.c_uint64, c.POINTER(engine.CNA_PostProcessContext)],
     "borrowed chain; every handle in the context is borrowed for the call"),
    ("cna_post_process_chain_reset_targets", c.c_uint32, [c.c_uint64],
     "borrowed chain; releases its pooled intermediates"),
    ("cna_post_process_chain_get_target_pool", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)],
     "COUNTED BORROW of the chain's pool; the chain refuses destruction while it is out"),
    ("cna_post_process_chain_is_gpu_timing_enabled", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint8)], "caller output; borrowed chain"),
    ("cna_post_process_chain_set_gpu_timing_enabled", c.c_uint32, [c.c_uint64, c.c_uint8],
     "borrowed chain; a renderer without timers accepts and stays off"),
    ("cna_post_process_chain_get_pass_timing_count", c.c_uint32,
     [c.c_uint64, c.POINTER(c.c_uint64)], "caller output; borrowed chain"),
    ("cna_post_process_chain_get_pass_timing", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.POINTER(engine.CNA_PassTimingEXT)],
     "caller output; borrowed chain"),
    ("cna_post_process_chain_copy_pass_timing_name", c.c_uint32,
     [c.c_uint64, c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol"),
)


#: Every engine route this binding imports, in one tuple for the loader.
ENGINE_FUNCTION_MANIFEST: tuple[tuple[str, object, list[object], str], ...] = (
    ENGINE_IDENTITY_MANIFEST
    + ENGINE_COMPUTE_MANIFEST
    + ENGINE_POSTPROCESS_MANIFEST
)

# ``engine`` is imported for the structures later slices pass by pointer; the
# reference keeps the module a declared dependency of this manifest rather than
# an accident of import order.
_STRUCTURES = engine.ENGINE_STRUCTURES
