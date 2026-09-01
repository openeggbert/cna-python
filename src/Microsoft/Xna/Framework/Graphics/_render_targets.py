"""Owned two-dimensional render targets and immutable binding values."""

from __future__ import annotations

import ctypes as c

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from .._language import Event
from .._numeric import int32
from ._device import (
    CubeMapFace, DepthFormat, GraphicsDevice, RenderTargetUsage, SurfaceFormat,
)
from ._resources import Texture, Texture2D, _release
from ._texture_volume import TextureCube


class _ContentLostSubscription:
    """Native ContentLost delivery shared by both render-target kinds.

    CNA raises this only when a renderer reports that it lost and recreated its
    device, which destroys the contents of default-pool resources.  Only renderer
    families whose API can lose a device raise it at all; on the rest the
    subscription is valid and simply silent, and no event is synthesized to make
    it look otherwise.
    """

    def _subscribe_content_lost(self) -> None:
        target = self

        @abi.CNA_RenderTargetContentLostCallback
        def callback(render_target: int, context: object) -> None:
            try:
                target.ContentLost(target, None)
            except BaseException as error:
                target._dispose_error = error

        registration = c.c_uint64()
        library = get_library()
        library.check(
            library.cna_render_target_subscribe_content_lost(
                self._require_handle(), callback, None, c.byref(registration)),
            "cna_render_target_subscribe_content_lost")
        self._content_lost_registration = int(registration.value)
        # CNA keeps the trampoline until unsubscription or destruction, and the
        # owning handle outlives this facade.
        self._native.retain_for_registration(callback)

    def _release_content_lost(self) -> None:
        registration, self._content_lost_registration = self._content_lost_registration, 0
        if not registration:
            return
        library = get_library()
        library.check(library.cna_render_target_unsubscribe_content_lost(registration),
                      "cna_render_target_unsubscribe_content_lost")


class RenderTarget2D(Texture2D, _ContentLostSubscription):
    __slots__ = ("_depth_format", "_multi_sample_count", "_usage",
                 "_is_content_lost", "_renderer_available", "_content_lost_registration")
    ContentLost = Event()

    def _before_dispose(self) -> None:
        self._release_content_lost()
        if self.GraphicsDevice is not None:
            self.GraphicsDevice._ensure_render_target_unbound_for_dispose(self)
        super()._before_dispose()

    def __init__(self, *args: object) -> None:
        if len(args) == 3:
            graphicsDevice, width, height = args
            mipMap, format, depth, samples, usage = (
                False, SurfaceFormat.Color, DepthFormat.None_, 0,
                RenderTargetUsage.DiscardContents,
            )
        elif len(args) == 6:
            graphicsDevice, width, height, mipMap, format, depth = args
            samples, usage = 0, RenderTargetUsage.DiscardContents
        elif len(args) == 8:
            graphicsDevice, width, height, mipMap, format, depth, samples, usage = args
        else:
            raise TypeError("no matching RenderTarget2D constructor")
        if not isinstance(graphicsDevice, GraphicsDevice):
            raise TypeError("graphicsDevice must be GraphicsDevice")
        width, height = int32(width, name="width"), int32(height, name="height")
        samples = int32(samples, name="preferredMultiSampleCount")
        if width <= 0 or height <= 0 or samples < 0:
            raise ValueError("dimensions must be positive and sample count nonnegative")
        info = abi.CNA_RenderTarget2DCreateInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        info.width, info.height, info.mip_map = width, height, bool(mipMap)
        info.format, info.depth_format = int(SurfaceFormat(format)), int(DepthFormat(depth))
        info.multi_sample_count, info.usage = samples, int(RenderTargetUsage(usage))
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_render_target2d_create(
            graphicsDevice._require_handle(), c.byref(info), c.byref(output)),
            "cna_render_target2d_create")
        self._init_resource(graphicsDevice, int(output.value), _release("cna_render_target_destroy"))
        self._content_lost_registration = 0
        self._subscribe_content_lost()
        self._read_render_target_info()

    def _read_render_target_info(self) -> None:
        value = abi.CNA_RenderTargetInfo()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_render_target_get_info(
            self._require_handle(), c.byref(value)), "cna_render_target_get_info")
        self._width, self._height = int(value.width), int(value.height)
        self._level_count, self._format = int(value.level_count), SurfaceFormat(value.format)
        self._depth_format = DepthFormat(value.depth_format)
        self._multi_sample_count = int(value.multi_sample_count)
        self._usage = RenderTargetUsage(value.usage)
        self._is_content_lost = value.is_content_lost != 0
        self._renderer_available = value.renderer_available != 0

    @property
    def IsContentLost(self) -> bool:
        self._read_render_target_info(); return self._is_content_lost
    @property
    def RenderTargetUsage(self) -> RenderTargetUsage:
        self._require_handle(); return self._usage
    @property
    def MultiSampleCount(self) -> int:
        self._require_handle(); return self._multi_sample_count
    @property
    def DepthStencilFormat(self) -> DepthFormat:
        self._require_handle(); return self._depth_format


class RenderTargetCube(TextureCube, _ContentLostSubscription):
    __slots__ = ("_depth_format", "_multi_sample_count", "_usage",
                 "_is_content_lost", "_renderer_available", "_content_lost_registration")
    ContentLost = Event()

    def _before_dispose(self) -> None:
        self._release_content_lost()
        super()._before_dispose()

    def __init__(self, *args: object) -> None:
        if len(args) == 5:
            graphicsDevice, size, mipMap, preferredFormat, preferredDepthFormat = args
            preferredMultiSampleCount, usage = 0, RenderTargetUsage.DiscardContents
        elif len(args) == 7:
            (graphicsDevice, size, mipMap, preferredFormat, preferredDepthFormat,
             preferredMultiSampleCount, usage) = args
        else:
            raise TypeError("no matching RenderTargetCube constructor")
        if not isinstance(graphicsDevice, GraphicsDevice):
            raise TypeError("graphicsDevice must be GraphicsDevice")
        if type(mipMap) is not bool:
            raise TypeError("mipMap must be bool")
        size = int32(size, name="size")
        samples = int32(preferredMultiSampleCount, name="preferredMultiSampleCount")
        if size <= 0 or samples < 0:
            raise ValueError("size must be positive and sample count nonnegative")
        try:
            selected_format = SurfaceFormat(preferredFormat)
            selected_depth = DepthFormat(preferredDepthFormat)
            selected_usage = RenderTargetUsage(usage)
        except (TypeError, ValueError) as error:
            raise ValueError("render-target format, depth format, or usage is invalid") from error
        info = abi.CNA_RenderTargetCubeCreateInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        info.size, info.mip_map = size, bool(mipMap)
        info.format, info.depth_format = int(selected_format), int(selected_depth)
        info.multi_sample_count, info.usage = samples, int(selected_usage)
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_render_target_cube_create(
            graphicsDevice._require_handle(), c.byref(info), c.byref(output)),
            "cna_render_target_cube_create")
        self._init_resource(graphicsDevice, int(output.value), _release("cna_render_target_destroy"))
        self._content_lost_registration = 0
        self._subscribe_content_lost()
        self._read_render_target_info()

    def _before_dispose(self) -> None:
        if self.GraphicsDevice is not None:
            self.GraphicsDevice._ensure_render_target_unbound_for_dispose(self)
        super()._before_dispose()

    def _read_render_target_info(self) -> None:
        value = abi.CNA_RenderTargetInfo()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_render_target_get_info(
            self._require_handle(), c.byref(value)), "cna_render_target_get_info")
        self._size, self._level_count, self._format = (
            int(value.width), int(value.level_count), SurfaceFormat(value.format))
        self._depth_format = DepthFormat(value.depth_format)
        self._multi_sample_count = int(value.multi_sample_count)
        self._usage = RenderTargetUsage(value.usage)
        self._is_content_lost = value.is_content_lost != 0
        self._renderer_available = value.renderer_available != 0

    @property
    def IsContentLost(self) -> bool:
        self._read_render_target_info(); return self._is_content_lost
    @property
    def RenderTargetUsage(self) -> RenderTargetUsage:
        self._require_handle(); return self._usage
    @property
    def MultiSampleCount(self) -> int:
        self._require_handle(); return self._multi_sample_count
    @property
    def DepthStencilFormat(self) -> DepthFormat:
        self._require_handle(); return self._depth_format


class RenderTargetBinding:
    __slots__ = ("_render_target", "_cube_map_face")
    def __init__(self, *args: object) -> None:
        if len(args) == 0:
            self._render_target, self._cube_map_face = None, CubeMapFace.PositiveX
        elif len(args) == 1 and isinstance(args[0], RenderTarget2D):
            self._render_target, self._cube_map_face = args[0], CubeMapFace.PositiveX
        elif len(args) == 2 and isinstance(args[0], RenderTargetCube):
            try: face = CubeMapFace(args[1])
            except (TypeError, ValueError) as error: raise ValueError("cubeMapFace is invalid") from error
            self._render_target, self._cube_map_face = args[0], face
        else:
            raise TypeError("RenderTargetBinding expects RenderTarget2D or RenderTargetCube, face")
    @property
    def RenderTarget(self) -> Texture: return self._render_target
    @property
    def CubeMapFace(self) -> CubeMapFace: return self._cube_map_face
    def _native(self) -> abi.CNA_RenderTargetBinding:
        value = abi.CNA_RenderTargetBinding()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.render_target = self._render_target._require_handle()
        value.array_slice, value.cube_map_face = 0, int(self._cube_map_face)
        return value
    def __copy__(self):
        if self._render_target is None: return RenderTargetBinding()
        if isinstance(self._render_target, RenderTargetCube):
            return RenderTargetBinding(self._render_target, self._cube_map_face)
        return RenderTargetBinding(self._render_target)
    __deepcopy__ = lambda self, memo: self.__copy__()


RenderTarget2D.__xna_arities__ = {"__init__": {3, 6, 8}, "Dispose": {0, 1}}
RenderTargetCube.__xna_arities__ = {"__init__": {5, 7}, "Dispose": {0, 1}}
RenderTargetBinding.__xna_arities__ = {"__init__": {0, 1, 2}}
