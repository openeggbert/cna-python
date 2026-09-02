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

#: Every engine route this binding imports, in one tuple for the loader.
ENGINE_FUNCTION_MANIFEST: tuple[tuple[str, object, list[object], str], ...] = (
    ENGINE_IDENTITY_MANIFEST
    + ENGINE_COMPUTE_MANIFEST
)

# ``engine`` is imported for the structures later slices pass by pointer; the
# reference keeps the module a declared dependency of this manifest rather than
# an accident of import order.
_STRUCTURES = engine.ENGINE_STRUCTURES
