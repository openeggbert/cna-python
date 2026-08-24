"""Owned native XNA occlusion query."""

from __future__ import annotations

import ctypes as c

from _cna_native.loader import get_library

from ._device import GraphicsDevice
from ._resources import GraphicsResource, _release


class OcclusionQuery(GraphicsResource):
    __slots__ = ("_in_pair", "_has_begun", "_completion_queried")

    def __init__(self, graphicsDevice: GraphicsDevice) -> None:
        if not isinstance(graphicsDevice, GraphicsDevice):
            raise TypeError("graphicsDevice must be GraphicsDevice")
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_occlusion_query_create(
            graphicsDevice._require_handle(), c.byref(output)), "cna_occlusion_query_create")
        self._init_resource(graphicsDevice, int(output.value), _release("cna_occlusion_query_destroy"),
                            native_dispose_event=False)
        self._in_pair, self._has_begun, self._completion_queried = False, False, True

    def Begin(self) -> None:
        if self._in_pair:
            raise RuntimeError("Begin cannot be called again before End")
        if not self._completion_queried:
            raise RuntimeError("IsComplete must be queried before beginning another query")
        library = get_library(); library.check(
            library.cna_occlusion_query_begin(self._require_handle()), "cna_occlusion_query_begin")
        self._in_pair, self._has_begun, self._completion_queried = True, True, False

    def End(self) -> None:
        if not self._in_pair:
            raise RuntimeError("End requires a matching Begin")
        library = get_library(); library.check(
            library.cna_occlusion_query_end(self._require_handle()), "cna_occlusion_query_end")
        self._in_pair = False

    @property
    def IsComplete(self) -> bool:
        handle = self._require_handle()
        self._completion_queried = True
        if not self._has_begun:
            return False
        library = get_library(); renderer = c.c_uint8()
        library.check(library.cna_occlusion_query_has_renderer(handle, c.byref(renderer)),
                      "cna_occlusion_query_has_renderer")
        if renderer.value == 0:
            return False
        value = c.c_uint8(); library.check(
            library.cna_occlusion_query_get_is_complete(handle, c.byref(value)),
            "cna_occlusion_query_get_is_complete")
        return value.value != 0

    @property
    def PixelCount(self) -> int:
        if not self.IsComplete:
            raise RuntimeError("PixelCount is unavailable until the query is complete")
        value = c.c_int32(); library = get_library(); library.check(
            library.cna_occlusion_query_get_pixel_count(self._require_handle(), c.byref(value)),
            "cna_occlusion_query_get_pixel_count")
        return int(value.value)


OcclusionQuery.__xna_arities__ = {"Dispose": {0, 1}}
