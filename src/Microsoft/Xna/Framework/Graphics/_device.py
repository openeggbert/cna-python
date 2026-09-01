"""Graphics-device values and callback-scoped CNA device projection."""

from __future__ import annotations

import ctypes as c
from enum import IntEnum, IntFlag
import math
from typing import MutableSequence, Sequence

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from .._geometry import Color, Rectangle
from .._language import Event
from .._math import Matrix, Vector3, Vector4
from .._numeric import add32, div32, f32, mul32, sub32, int32


class SurfaceFormat(IntEnum):
    Color = 0
    Bgr565 = 1
    Bgra5551 = 2
    Bgra4444 = 3
    Dxt1 = 4
    Dxt3 = 5
    Dxt5 = 6
    NormalizedByte2 = 7
    NormalizedByte4 = 8
    Rgba1010102 = 9
    Rg32 = 10
    Rgba64 = 11
    Alpha8 = 12
    Single = 13
    Vector2 = 14
    Vector4 = 15
    HalfSingle = 16
    HalfVector2 = 17
    HalfVector4 = 18
    HdrBlendable = 19


class Blend(IntEnum):
    One = 0; Zero = 1; SourceColor = 2; InverseSourceColor = 3
    SourceAlpha = 4; InverseSourceAlpha = 5
    DestinationColor = 6; InverseDestinationColor = 7
    DestinationAlpha = 8; InverseDestinationAlpha = 9
    BlendFactor = 10; InverseBlendFactor = 11; SourceAlphaSaturation = 12


class BlendFunction(IntEnum):
    Add = 0; Subtract = 1; ReverseSubtract = 2; Min = 3; Max = 4


class ColorWriteChannels(IntFlag):
    None_ = 0; Red = 1; Green = 2; Blue = 4; Alpha = 8; All = 15


class CompareFunction(IntEnum):
    Always = 0; Never = 1; Less = 2; LessEqual = 3
    Equal = 4; GreaterEqual = 5; Greater = 6; NotEqual = 7


class StencilOperation(IntEnum):
    Keep = 0; Zero = 1; Replace = 2; Increment = 3; Decrement = 4
    IncrementSaturation = 5; DecrementSaturation = 6; Invert = 7


class CullMode(IntEnum):
    None_ = 0; CullClockwiseFace = 1; CullCounterClockwiseFace = 2


class FillMode(IntEnum):
    Solid = 0; WireFrame = 1


class TextureAddressMode(IntEnum):
    Wrap = 0; Clamp = 1; Mirror = 2


class TextureFilter(IntEnum):
    Linear = 0; Point = 1; Anisotropic = 2; LinearMipPoint = 3; PointMipLinear = 4
    MinLinearMagPointMipLinear = 5; MinLinearMagPointMipPoint = 6
    MinPointMagLinearMipLinear = 7; MinPointMagLinearMipPoint = 8


class PrimitiveType(IntEnum):
    TriangleList = 0; TriangleStrip = 1; LineList = 2; LineStrip = 3


class BufferUsage(IntFlag):
    None_ = 0; WriteOnly = 1


class SetDataOptions(IntFlag):
    None_ = 0; Discard = 1; NoOverwrite = 2


class IndexElementSize(IntEnum):
    SixteenBits = 0; ThirtyTwoBits = 1


class CubeMapFace(IntEnum):
    PositiveX = 0; NegativeX = 1; PositiveY = 2
    NegativeY = 3; PositiveZ = 4; NegativeZ = 5


class RenderTargetUsage(IntEnum):
    DiscardContents = 0; PreserveContents = 1; PlatformContents = 2


class PresentInterval(IntEnum):
    Default = 0; One = 1; Two = 2; Immediate = 3


class ClearOptions(IntFlag):
    Target = 1; DepthBuffer = 2; Stencil = 4


class GraphicsDeviceStatus(IntEnum):
    Normal = 0; Lost = 1; NotReset = 2


class VertexElementFormat(IntEnum):
    Single = 0; Vector2 = 1; Vector3 = 2; Vector4 = 3; Color = 4; Byte4 = 5
    Short2 = 6; Short4 = 7; NormalizedShort2 = 8; NormalizedShort4 = 9
    HalfVector2 = 10; HalfVector4 = 11


class VertexElementUsage(IntEnum):
    Position = 0; Color = 1; TextureCoordinate = 2; Normal = 3; Binormal = 4
    Tangent = 5; BlendIndices = 6; BlendWeight = 7; Depth = 8; Fog = 9
    PointSize = 10; Sample = 11; TessellateFactor = 12


class DepthFormat(IntEnum):
    None_ = 0
    Depth16 = 1
    Depth24 = 2
    Depth24Stencil8 = 3


class GraphicsProfile(IntEnum):
    Reach = 0
    HiDef = 1


class IGraphicsDeviceService:
    DeviceCreated = Event()
    DeviceDisposing = Event()
    DeviceReset = Event()
    DeviceResetting = Event()

    @property
    def GraphicsDevice(self):
        raise NotImplementedError


class SpriteSortMode(IntEnum):
    Deferred = 0
    Immediate = 1
    Texture = 2
    BackToFront = 3
    FrontToBack = 4


class SpriteEffects(IntFlag):
    None_ = 0
    FlipHorizontally = 1
    FlipVertically = 2


class Viewport:
    __slots__ = ("_x", "_y", "_width", "_height", "_min_depth", "_max_depth")

    def __init__(self, *args: object) -> None:
        if not args:
            x, y, width, height = 0, 0, 0, 0
        elif len(args) == 1 and isinstance(args[0], Rectangle):
            x, y, width, height = args[0].X, args[0].Y, args[0].Width, args[0].Height
        elif len(args) == 4:
            x, y, width, height = args
        else:
            raise TypeError("Viewport expects (), Rectangle, or x, y, width, height")
        self.X, self.Y, self.Width, self.Height = x, y, width, height
        self.MinDepth, self.MaxDepth = 0.0, 1.0

    def _integer(name: str):
        private = "_" + name.lower()
        return property(lambda self: getattr(self, private),
                        lambda self, value: setattr(self, private, int32(value, name=name)))
    X = _integer("X"); Y = _integer("Y"); Width = _integer("Width"); Height = _integer("Height")
    @property
    def MinDepth(self) -> float: return self._min_depth
    @MinDepth.setter
    def MinDepth(self, value: float) -> None: self._min_depth = f32(value)
    @property
    def MaxDepth(self) -> float: return self._max_depth
    @MaxDepth.setter
    def MaxDepth(self, value: float) -> None: self._max_depth = f32(value)
    @property
    def Bounds(self) -> Rectangle: return Rectangle(self.X, self.Y, self.Width, self.Height)
    @Bounds.setter
    def Bounds(self, value: Rectangle) -> None: self.X, self.Y, self.Width, self.Height = tuple(value)
    @property
    def AspectRatio(self) -> float:
        return f32(self.Width / self.Height) if self.Width != 0 and self.Height != 0 else 0.0
    @property
    def TitleSafeArea(self) -> Rectangle:
        output = abi.CNA_Rectangle()
        library = get_library()
        library.check(library.cna_viewport_get_title_safe_area(self._native(), c.byref(output)),
                      "cna_viewport_get_title_safe_area")
        return Rectangle(output.x, output.y, output.width, output.height)
    def _native(self) -> abi.CNA_Viewport:
        return abi.CNA_Viewport(self.X, self.Y, self.Width, self.Height, self.MinDepth, self.MaxDepth)
    @staticmethod
    def _validate_projection(source: Vector3, projection: Matrix, view: Matrix,
                             world: Matrix) -> None:
        if not isinstance(source, Vector3):
            raise TypeError("source must be Vector3")
        if not all(isinstance(value, Matrix) for value in (projection, view, world)):
            raise TypeError("projection, view, and world must be Matrix values")
    @staticmethod
    def _perspective_divisor(source: Vector3, matrix: Matrix) -> float:
        value = mul32(source.X, matrix.M14)
        value = add32(value, mul32(source.Y, matrix.M24))
        value = add32(value, mul32(source.Z, matrix.M34))
        return add32(value, matrix.M44)
    @staticmethod
    def _within_epsilon(left: float, right: float) -> bool:
        return abs(sub32(left, right)) <= 1.401298464324817e-45
    def Project(self, source: Vector3, projection: Matrix, view: Matrix,
                world: Matrix) -> Vector3:
        self._validate_projection(source, projection, view, world)
        transform = (world * view) * projection
        result = Vector3.Transform(source, transform)
        divisor = self._perspective_divisor(source, transform)
        if not self._within_epsilon(divisor, 1.0):
            result = result / divisor
        result.X = add32(mul32(mul32(add32(result.X, 1.0), 0.5), self.Width), self.X)
        result.Y = add32(mul32(mul32(add32(f32(-result.Y), 1.0), 0.5), self.Height), self.Y)
        result.Z = add32(mul32(result.Z, sub32(self.MaxDepth, self.MinDepth)), self.MinDepth)
        return result
    def Unproject(self, source: Vector3, projection: Matrix, view: Matrix,
                  world: Matrix) -> Vector3:
        self._validate_projection(source, projection, view, world)
        transform = Matrix.Invert((world * view) * projection)
        x = sub32(source.X, self.X)
        x = div32(x, self.Width)
        x = sub32(mul32(x, 2.0), 1.0)
        y = sub32(source.Y, self.Y)
        y = div32(y, self.Height)
        y = f32(-sub32(mul32(y, 2.0), 1.0))
        z = div32(sub32(source.Z, self.MinDepth), sub32(self.MaxDepth, self.MinDepth))
        normalized = Vector3(x, y, z)
        result = Vector3.Transform(normalized, transform)
        divisor = self._perspective_divisor(normalized, transform)
        if not self._within_epsilon(divisor, 1.0):
            result = result / divisor
        return result
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Viewport) and tuple(self) == tuple(other)
    def __iter__(self): return iter((self.X, self.Y, self.Width, self.Height, self.MinDepth, self.MaxDepth))
    def __copy__(self):
        result = Viewport(self.X, self.Y, self.Width, self.Height)
        result.MinDepth, result.MaxDepth = self.MinDepth, self.MaxDepth
        return result
    __deepcopy__ = lambda self, memo: self.__copy__()
    def ToString(self) -> str:
        return f"{{X:{self.X} Y:{self.Y} Width:{self.Width} Height:{self.Height} MinDepth:{self.MinDepth:g} MaxDepth:{self.MaxDepth:g}}}"
    __str__ = ToString


class GraphicsDevice:
    """A device this binding either borrows from a Game or owns outright.

    A Game's device is borrowed and its handle is valid only inside a native
    lifecycle callback; it is not the caller's to destroy. A device built through
    XNA's public constructor is owned, keeps its handle for its whole lifetime,
    and is released by its own Dispose. Resources on an owned device belong to
    that device rather than to a game, and are released with it.
    """

    __slots__ = (
        "_game", "_handle", "_owned", "_disposed", "_adapter_cache", "_blend_state",
        "_depth_stencil_state", "_rasterizer_state", "_sampler_states",
        "_vertex_sampler_states", "_textures", "_vertex_textures",
        "_device_event_callbacks", "_device_event_registrations", "_vertex_bindings",
        "_index_buffer", "_render_target_bindings", "__weakref__",
    )
    Disposing = Event()
    ResourceDestroyed = Event()
    ResourceCreated = Event()
    DeviceLost = Event()
    DeviceReset = Event()
    DeviceResetting = Event()

    def __init__(self, *args: object) -> None:
        owned_arguments = None
        if len(args) == 1:
            game = args[0]
        elif len(args) == 3:
            game, owned_arguments = None, args
        else:
            raise TypeError("GraphicsDevice expects adapter, graphicsProfile, presentationParameters")
        self._game = game
        self._handle = 0
        self._owned = owned_arguments is not None
        self._disposed = False
        self._adapter_cache = {}
        self._blend_state = self._depth_stencil_state = self._rasterizer_state = None
        from ._states import SamplerStateCollection, TextureCollection
        self._sampler_states = SamplerStateCollection(self, 0, self)
        self._vertex_sampler_states = SamplerStateCollection(self, 1, self)
        self._textures = TextureCollection(self, 0, self)
        self._vertex_textures = TextureCollection(self, 1, self)
        self._device_event_callbacks = []
        self._device_event_registrations = []
        self._vertex_bindings = []
        self._index_buffer = None
        self._render_target_bindings = []
        if owned_arguments is not None:
            self._create_owned(*owned_arguments)

    def _create_owned(self, adapter: object, graphicsProfile: object,
                      presentationParameters: object) -> None:
        from ._display import GraphicsAdapter, PresentationParameters
        if not isinstance(adapter, GraphicsAdapter):
            raise TypeError("adapter must be a GraphicsAdapter")
        if not isinstance(presentationParameters, PresentationParameters):
            raise TypeError("presentationParameters must be a PresentationParameters")
        profile = GraphicsProfile(graphicsProfile)
        index = adapter._index
        parameters = presentationParameters._native_value()
        output = c.c_uint64()
        library = get_library()
        library.check(library.cna_graphics_device_create(
            index, int(profile), c.byref(parameters), c.byref(output)),
            "cna_graphics_device_create")
        self._handle = int(output.value)
        self._subscribe_device_events()

    def _enter_native_callback(self, handle: int) -> None:
        self._handle = handle
        if not self._device_event_registrations:
            self._subscribe_device_events()

    def _leave_native_callback(self) -> None:
        self._handle = 0

    def _subscribe_device_events(self) -> None:
        events = ((0, self.Disposing), (1, self.DeviceLost),
                  (2, self.DeviceReset), (3, self.DeviceResetting))
        library = get_library()
        for identity, event in events:
            @abi.CNA_GraphicsDeviceEventCallback
            def callback(device_handle, context, selected=event):
                try:
                    selected(self, None)
                except BaseException as error:
                    host = self._game._host
                    if host is not None and host.pending_exception is None:
                        host.pending_exception = error
            self._device_event_callbacks.append(callback)
            registration = c.c_uint64()
            library.check(library.cna_graphics_device_subscribe_event(
                self._handle, identity, callback, None, c.byref(registration)),
                "cna_graphics_device_subscribe_event")
            self._device_event_registrations.append(int(registration.value))

    def _release_device_events(self, *, emit_disposing: bool = False) -> None:
        library = get_library()
        first_error = None
        if emit_disposing and not self._disposed:
            try:
                self.Disposing(self, None)
            except BaseException as error:
                first_error = error
        for registration in reversed(self._device_event_registrations):
            try:
                library.check(library.cna_graphics_device_unsubscribe(registration),
                              "cna_graphics_device_unsubscribe")
            except BaseException as error:
                first_error = first_error or error
        self._device_event_registrations.clear()
        self._device_event_callbacks.clear()
        if first_error is not None: raise first_error

    def _require_handle(self) -> int:
        if self._disposed:
            raise RuntimeError("GraphicsDevice is disposed")
        if self._handle == 0:
            raise RuntimeError("GraphicsDevice native access is only valid during a CNA lifecycle callback")
        return self._handle

    def _unbind_python_resources_for_shutdown(self) -> None:
        """Release every CNA raw binding before the Game destroys owned children."""
        handle = self._require_handle(); library = get_library(); first_error = None
        textures = []
        for collection in (self._textures, self._vertex_textures):
            for texture in collection._textures:
                if texture is not None and all(value is not texture for value in textures):
                    textures.append(texture)
        for texture in textures:
            if texture.IsDisposed:
                continue
            try:
                library.check(library.cna_graphics_device_unbind_texture(
                    handle, texture._require_handle()),
                    "cna_graphics_device_unbind_texture")
            except BaseException as error:
                first_error = first_error or error
        operations = (
            ("cna_graphics_device_set_vertex_buffers", (handle, None, 0)),
            ("cna_graphics_device_set_index_buffer", (handle, 0)),
            ("cna_graphics_device_set_render_targets", (handle, None, 0)),
        )
        for operation, arguments in operations:
            try: library.check(getattr(library, operation)(*arguments), operation)
            except BaseException as error: first_error = first_error or error
        self._vertex_bindings.clear(); self._index_buffer = None
        self._render_target_bindings.clear()
        self._textures._textures = [None] * 16
        self._vertex_textures._textures = [None] * 16
        if first_error is not None: raise first_error

    def _unbind_texture_resource(self, texture) -> None:
        collections = (self._textures, self._vertex_textures)
        if not any(value is texture for collection in collections
                   for value in collection._textures):
            return
        if self._handle == 0:
            raise RuntimeError("a bound Texture cannot be disposed outside a native callback")
        library = get_library()
        library.check(library.cna_graphics_device_unbind_texture(
            self._require_handle(), texture._require_handle()),
            "cna_graphics_device_unbind_texture")
        for collection in collections:
            collection._textures = [None if value is texture else value
                                    for value in collection._textures]

    def _ensure_render_target_unbound_for_dispose(self, target) -> None:
        if any(value.RenderTarget is target for value in self._render_target_bindings):
            raise NativeCapabilityError(
                f"{type(target).__name__}.Dispose", 6, None,
                "a currently bound render target cannot be destroyed; the runtime refuses it as well, "
                "so bind the backbuffer first and dispose the target afterwards",
            )

    @property
    def IsDisposed(self) -> bool: return self._disposed

    @property
    def Adapter(self):
        from ._display import GraphicsAdapter
        value = c.c_uint32(); library = get_library()
        library.check(library.cna_graphics_device_get_adapter_index(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_adapter_index")
        return GraphicsAdapter._for_device(self, value.value)

    @property
    def DisplayMode(self):
        from ._display import DisplayMode
        value = abi.CNA_DisplayMode(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_graphics_device_get_display_mode(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_display_mode")
        return DisplayMode._from_native(value)

    @property
    def GraphicsDeviceStatus(self) -> GraphicsDeviceStatus:
        value = c.c_uint32(); library = get_library()
        library.check(library.cna_graphics_device_get_status(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_status")
        return GraphicsDeviceStatus(value.value)

    @property
    def GraphicsProfile(self) -> GraphicsProfile:
        value = c.c_uint32(); library = get_library()
        library.check(library.cna_graphics_device_get_graphics_profile(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_graphics_profile")
        return GraphicsProfile(value.value)

    @property
    def PresentationParameters(self):
        from ._display import PresentationParameters
        value = abi.CNA_PresentationParameters(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_graphics_device_get_presentation_parameters(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_presentation_parameters")
        result = PresentationParameters._from_native(value)
        result.DeviceWindowHandle = self._game.Window.Handle
        return result

    @property
    def ScissorRectangle(self) -> Rectangle:
        value = abi.CNA_Rectangle(); library = get_library()
        library.check(library.cna_graphics_device_get_scissor_rectangle(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_scissor_rectangle")
        return Rectangle(value.x, value.y, value.width, value.height)
    @ScissorRectangle.setter
    def ScissorRectangle(self, value: Rectangle) -> None:
        if not isinstance(value, Rectangle): raise TypeError("ScissorRectangle must be Rectangle")
        library = get_library()
        library.check(library.cna_graphics_device_set_scissor_rectangle(
            self._require_handle(), abi.CNA_Rectangle(*tuple(value))),
            "cna_graphics_device_set_scissor_rectangle")

    @property
    def BlendFactor(self) -> Color:
        value = abi.CNA_Color(); library = get_library()
        library.check(library.cna_graphics_device_get_blend_factor(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_blend_factor")
        return Color(value.r, value.g, value.b, value.a)
    @BlendFactor.setter
    def BlendFactor(self, value: Color) -> None:
        if not isinstance(value, Color): raise TypeError("BlendFactor must be Color")
        library = get_library()
        library.check(library.cna_graphics_device_set_blend_factor(
            self._require_handle(), abi.CNA_Color(*tuple(value))), "cna_graphics_device_set_blend_factor")

    def _integer_state(name: str):
        def get(self):
            output = c.c_int32(); library = get_library(); operation = f"cna_graphics_device_get_{name}"
            library.check(getattr(library, operation)(self._require_handle(), c.byref(output)), operation)
            return int(output.value)
        def set(self, value):
            value = int32(value, name=name); library = get_library(); operation = f"cna_graphics_device_set_{name}"
            library.check(getattr(library, operation)(self._require_handle(), value), operation)
        return property(get, set)
    MultiSampleMask = _integer_state("multi_sample_mask")
    ReferenceStencil = _integer_state("reference_stencil")

    @property
    def BlendState(self):
        from ._states import BlendState
        value = abi.CNA_BlendState(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_graphics_device_get_blend_state(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_blend_state")
        self._blend_state = BlendState._from_native(value, self, self._blend_state)
        return self._blend_state
    @BlendState.setter
    def BlendState(self, state):
        from ._states import BlendState
        if not isinstance(state, BlendState): raise TypeError("BlendState must be BlendState")
        if state.IsDisposed: raise RuntimeError("BlendState is disposed")
        value = state._native_value(); library = get_library()
        library.check(library.cna_graphics_device_set_blend_state(
            self._require_handle(), c.byref(value)), "cna_graphics_device_set_blend_state")
        state._bind(self); self._blend_state = state

    @property
    def DepthStencilState(self):
        from ._states import DepthStencilState
        value = abi.CNA_DepthStencilState(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_graphics_device_get_depth_stencil_state(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_depth_stencil_state")
        self._depth_stencil_state = DepthStencilState._from_native(value, self, self._depth_stencil_state)
        return self._depth_stencil_state
    @DepthStencilState.setter
    def DepthStencilState(self, state):
        from ._states import DepthStencilState
        if not isinstance(state, DepthStencilState): raise TypeError("state must be DepthStencilState")
        if state.IsDisposed: raise RuntimeError("DepthStencilState is disposed")
        value = state._native_value(); library = get_library()
        library.check(library.cna_graphics_device_set_depth_stencil_state(
            self._require_handle(), c.byref(value)), "cna_graphics_device_set_depth_stencil_state")
        state._bind(self); self._depth_stencil_state = state

    @property
    def RasterizerState(self):
        from ._states import RasterizerState
        value = abi.CNA_RasterizerState(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_graphics_device_get_rasterizer_state(
            self._require_handle(), c.byref(value)), "cna_graphics_device_get_rasterizer_state")
        self._rasterizer_state = RasterizerState._from_native(value, self, self._rasterizer_state)
        return self._rasterizer_state
    @RasterizerState.setter
    def RasterizerState(self, state):
        from ._states import RasterizerState
        if not isinstance(state, RasterizerState): raise TypeError("state must be RasterizerState")
        if state.IsDisposed: raise RuntimeError("RasterizerState is disposed")
        value = state._native_value(); library = get_library()
        library.check(library.cna_graphics_device_set_rasterizer_state(
            self._require_handle(), c.byref(value)), "cna_graphics_device_set_rasterizer_state")
        state._bind(self); self._rasterizer_state = state

    @property
    def SamplerStates(self): self._require_handle(); return self._sampler_states
    @property
    def VertexSamplerStates(self): self._require_handle(); return self._vertex_sampler_states
    @property
    def Textures(self): self._require_handle(); return self._textures
    @property
    def VertexTextures(self): self._require_handle(); return self._vertex_textures

    @property
    def Viewport(self) -> Viewport:
        value = abi.CNA_Viewport()
        library = get_library()
        library.check(library.cna_graphics_device_get_viewport(self._require_handle(), c.byref(value)),
                      "cna_graphics_device_get_viewport")
        result = Viewport(value.x, value.y, value.width, value.height)
        result.MinDepth, result.MaxDepth = value.min_depth, value.max_depth
        return result

    @Viewport.setter
    def Viewport(self, value: Viewport) -> None:
        if not isinstance(value, Viewport):
            raise TypeError("Viewport must be a Viewport value")
        library = get_library()
        library.check(library.cna_graphics_device_set_viewport(self._require_handle(), value._native()),
                      "cna_graphics_device_set_viewport")

    def Clear(self, *args: object) -> None:
        if len(args) == 4 and isinstance(args[1], (Color, Vector4)):
            options, color, depth, stencil = ClearOptions(args[0]), args[1], f32(args[2]), int32(args[3], name="stencil")
            if isinstance(color, Vector4):
                channels = [max(0, min(255, round(f32(value) * 255))) for value in color]
                color = Color(*channels)
            library = get_library()
            library.check(library.cna_graphics_device_clear_options(
                self._require_handle(), int(options), abi.CNA_Color(*tuple(color)), depth, stencil),
                "cna_graphics_device_clear_options")
            return
        # Both XNA overloads are bound. Reaching here means the arguments match
        # neither, which is a caller type error rather than a missing capability.
        if len(args) != 1 or not isinstance(args[0], Color):
            raise TypeError(
                "Clear expects a Color, or ClearOptions, Color or Vector4, depth and stencil")
        color = args[0]
        channels = tuple(f32(channel / 255.0) for channel in color)
        library = get_library()
        library.check(library.cna_graphics_device_clear_rgba(self._require_handle(), *channels),
                      "cna_graphics_device_clear_rgba")

    def Present(self, *args: object) -> None:
        if args:
            if len(args) != 3: raise TypeError("Present expects zero or three arguments")
            source, destination, handle = args
            if source is not None and not isinstance(source, Rectangle): raise TypeError("sourceRectangle must be Rectangle or None")
            if destination is not None and not isinstance(destination, Rectangle): raise TypeError("destinationRectangle must be Rectangle or None")
            if not isinstance(handle, int) or isinstance(handle, bool): raise TypeError("overrideWindowHandle must be int")
            raise NativeCapabilityError("GraphicsDevice.Present", 6, None,
                                        "CNA's Present route takes only the device, with no source or destination "
                                        "rectangle and no target window")
        library = get_library(); library.check(library.cna_graphics_device_present(
            self._require_handle()), "cna_graphics_device_present")

    def Reset(self, *args: object) -> None:
        library = get_library(); handle = self._require_handle()
        if not args:
            library.check(library.cna_graphics_device_reset(handle), "cna_graphics_device_reset")
            return
        if len(args) not in (1, 2): raise TypeError("Reset expects zero, one, or two arguments")
        from ._display import GraphicsAdapter, PresentationParameters
        parameters = args[0]
        if not isinstance(parameters, PresentationParameters): raise TypeError("presentationParameters must be PresentationParameters")
        native = parameters._native_value(); adapter_pointer = None; adapter = c.c_uint32()
        if len(args) == 2:
            if not isinstance(args[1], GraphicsAdapter): raise TypeError("graphicsAdapter must be GraphicsAdapter")
            if args[1]._device is not self: raise ValueError("GraphicsAdapter belongs to a different GraphicsDevice")
            adapter.value = args[1]._index; adapter_pointer = c.byref(adapter)
        library.check(library.cna_graphics_device_reset_with_parameters(
            handle, c.byref(native), adapter_pointer), "cna_graphics_device_reset_with_parameters")

    @property
    def Indices(self):
        from ._vertices import IndexBuffer
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_graphics_device_get_index_buffer(
            self._require_handle(), c.byref(output)), "cna_graphics_device_get_index_buffer")
        if output.value == 0:
            self._index_buffer = None
        elif self._index_buffer is None or self._index_buffer.IsDisposed or self._index_buffer._require_handle() != output.value:
            raise NativeCapabilityError(
                "GraphicsDevice.Indices", 6, None,
                "the native binding was not created by this Python GraphicsDevice facade",
            )
        return self._index_buffer
    @Indices.setter
    def Indices(self, value) -> None:
        from ._vertices import IndexBuffer
        if value is not None and not isinstance(value, IndexBuffer):
            raise TypeError("Indices must be IndexBuffer or None")
        if value is not None:
            if value.IsDisposed: raise RuntimeError("IndexBuffer is disposed")
            if value.GraphicsDevice is not self: raise ValueError("IndexBuffer belongs to another GraphicsDevice")
        library = get_library(); library.check(library.cna_graphics_device_set_index_buffer(
            self._require_handle(), 0 if value is None else value._require_handle()),
            "cna_graphics_device_set_index_buffer")
        self._index_buffer = value

    def SetVertexBuffer(self, vertexBuffer, *args: object) -> None:
        from ._vertices import VertexBuffer, VertexBufferBinding
        if vertexBuffer is not None and not isinstance(vertexBuffer, VertexBuffer):
            raise TypeError("vertexBuffer must be VertexBuffer or None")
        if len(args) > 1: raise TypeError("SetVertexBuffer expects buffer and optional vertexOffset")
        offset = 0 if not args else int32(args[0], name="vertexOffset")
        if offset < 0: raise ValueError("vertexOffset cannot be negative")
        if vertexBuffer is not None:
            if vertexBuffer.IsDisposed: raise RuntimeError("VertexBuffer is disposed")
            if vertexBuffer.GraphicsDevice is not self: raise ValueError("VertexBuffer belongs to another GraphicsDevice")
        operation = "cna_graphics_device_set_vertex_buffer" if not args else "cna_graphics_device_set_vertex_buffer_offset"
        library = get_library(); handle = 0 if vertexBuffer is None else vertexBuffer._require_handle()
        result = getattr(library, operation)(self._require_handle(), handle, *(() if not args else (offset,)))
        library.check(result, operation)
        self._vertex_bindings = ([] if vertexBuffer is None else
                                 [VertexBufferBinding(vertexBuffer, offset)])

    def SetVertexBuffers(self, *vertexBuffers) -> None:
        from ._vertices import VertexBufferBinding
        values = tuple(vertexBuffers)
        if not all(isinstance(value, VertexBufferBinding) for value in values):
            raise TypeError("vertexBuffers must contain VertexBufferBinding values")
        for value in values:
            if value.VertexBuffer.IsDisposed: raise RuntimeError("VertexBuffer is disposed")
            if value.VertexBuffer.GraphicsDevice is not self: raise ValueError("VertexBuffer belongs to another GraphicsDevice")
        native = (abi.CNA_VertexBufferBinding * len(values))(
            *(value._native() for value in values)) if values else None
        library = get_library(); library.check(library.cna_graphics_device_set_vertex_buffers(
            self._require_handle(), native, len(values)), "cna_graphics_device_set_vertex_buffers")
        self._vertex_bindings = list(values)

    def GetVertexBuffers(self):
        from ._vertices import VertexBufferBinding
        count = c.c_uint64(); library = get_library()
        library.check(library.cna_graphics_device_get_vertex_buffer_count(
            self._require_handle(), c.byref(count)), "cna_graphics_device_get_vertex_buffer_count")
        if count.value == 0:
            self._vertex_bindings = []; return []
        native = (abi.CNA_VertexBufferBinding * count.value)(); written = c.c_uint64()
        library.check(library.cna_graphics_device_copy_vertex_buffers(
            self._require_handle(), native, count.value, c.byref(written)),
            "cna_graphics_device_copy_vertex_buffers")
        by_handle = {value.VertexBuffer._require_handle(): value.VertexBuffer
                     for value in self._vertex_bindings if not value.VertexBuffer.IsDisposed}
        result = []
        for value in native[:written.value]:
            buffer = by_handle.get(int(value.vertex_buffer))
            if buffer is None:
                raise NativeCapabilityError("GraphicsDevice.GetVertexBuffers", 6, None,
                                            "a native binding has no stable Python resource identity")
            result.append(VertexBufferBinding(buffer, value.vertex_offset, value.instance_frequency))
        self._vertex_bindings = result
        return list(result)

    def SetRenderTarget(self, renderTarget, *args: object) -> None:
        from ._render_targets import RenderTarget2D, RenderTargetBinding, RenderTargetCube
        if args:
            if len(args) != 1 or (renderTarget is not None and
                                  not isinstance(renderTarget, RenderTargetCube)):
                raise TypeError("cube render targets require RenderTargetCube and CubeMapFace")
            if renderTarget is None:
                library = get_library(); library.check(
                    library.cna_graphics_device_set_render_targets(
                        self._require_handle(), None, 0),
                    "cna_graphics_device_set_render_targets")
                self._render_target_bindings = []
                return
            try: face = CubeMapFace(args[0])
            except (TypeError, ValueError) as error: raise ValueError("cubeMapFace is invalid") from error
            if renderTarget.IsDisposed: raise RuntimeError("RenderTargetCube is disposed")
            if renderTarget.GraphicsDevice is not self: raise ValueError("RenderTargetCube belongs to another GraphicsDevice")
            library = get_library(); library.check(library.cna_graphics_device_set_render_target_cube(
                self._require_handle(), renderTarget._require_handle(), int(face)),
                "cna_graphics_device_set_render_target_cube")
            self._render_target_bindings = [RenderTargetBinding(renderTarget, face)]
            return
        if renderTarget is not None and not isinstance(renderTarget, RenderTarget2D):
            raise TypeError("renderTarget must be RenderTarget2D or None")
        if renderTarget is not None:
            if renderTarget.IsDisposed: raise RuntimeError("RenderTarget2D is disposed")
            if renderTarget.GraphicsDevice is not self: raise ValueError("RenderTarget2D belongs to another GraphicsDevice")
        library = get_library(); library.check(library.cna_graphics_device_set_render_target2d(
            self._require_handle(), 0 if renderTarget is None else renderTarget._require_handle()),
            "cna_graphics_device_set_render_target2d")
        self._render_target_bindings = ([] if renderTarget is None else
                                        [RenderTargetBinding(renderTarget)])

    def SetRenderTargets(self, *renderTargets) -> None:
        from ._render_targets import RenderTargetBinding
        values = tuple(renderTargets)
        if not all(isinstance(value, RenderTargetBinding) for value in values):
            raise TypeError("renderTargets must contain RenderTargetBinding values")
        for value in values:
            target = value.RenderTarget
            if target.IsDisposed: raise RuntimeError("render target is disposed")
            if target.GraphicsDevice is not self: raise ValueError("render target belongs to another GraphicsDevice")
        native = (abi.CNA_RenderTargetBinding * len(values))(
            *(value._native() for value in values)) if values else None
        library = get_library(); library.check(library.cna_graphics_device_set_render_targets(
            self._require_handle(), native, len(values)), "cna_graphics_device_set_render_targets")
        self._render_target_bindings = list(values)

    def GetRenderTargets(self):
        from ._render_targets import RenderTargetBinding, RenderTargetCube
        count = c.c_uint64(); library = get_library()
        library.check(library.cna_graphics_device_get_render_target_count(
            self._require_handle(), c.byref(count)), "cna_graphics_device_get_render_target_count")
        if count.value == 0:
            self._render_target_bindings = []; return []
        native = (abi.CNA_RenderTargetBinding * count.value)(); written = c.c_uint64()
        library.check(library.cna_graphics_device_copy_render_targets(
            self._require_handle(), native, count.value, c.byref(written)),
            "cna_graphics_device_copy_render_targets")
        by_handle = {value.RenderTarget._require_handle(): value.RenderTarget
                     for value in self._render_target_bindings if not value.RenderTarget.IsDisposed}
        result = []
        for value in native[:written.value]:
            target = by_handle.get(int(value.render_target))
            if target is None:
                raise NativeCapabilityError("GraphicsDevice.GetRenderTargets", 6, None,
                                            "a native binding has no stable Python resource identity")
            if isinstance(target, RenderTargetCube):
                result.append(RenderTargetBinding(target, CubeMapFace(value.cube_map_face)))
            else:
                result.append(RenderTargetBinding(target))
        self._render_target_bindings = result
        return list(result)

    @staticmethod
    def _draw_integers(values: tuple[object, ...], names: tuple[str, ...]) -> tuple[int, ...]:
        converted = tuple(int32(value, name=name) for value, name in zip(values, names))
        if any(value < 0 for value in converted): raise ValueError("draw ranges cannot be negative")
        return converted

    def DrawPrimitives(self, primitiveType, startVertex, primitiveCount) -> None:
        start, count = self._draw_integers((startVertex, primitiveCount), ("startVertex", "primitiveCount"))
        library = get_library(); library.check(library.cna_graphics_device_draw_primitives(
            self._require_handle(), int(PrimitiveType(primitiveType)), start, count),
            "cna_graphics_device_draw_primitives")

    def DrawIndexedPrimitives(self, primitiveType, baseVertex, minVertexIndex,
                              numVertices, startIndex, primitiveCount) -> None:
        base = int32(baseVertex, name="baseVertex")
        values = (base, *self._draw_integers(
            (minVertexIndex, numVertices, startIndex, primitiveCount),
            ("minVertexIndex", "numVertices", "startIndex", "primitiveCount")))
        library = get_library(); library.check(library.cna_graphics_device_draw_indexed_primitives(
            self._require_handle(), int(PrimitiveType(primitiveType)), *values),
            "cna_graphics_device_draw_indexed_primitives")

    def DrawInstancedPrimitives(self, primitiveType, baseVertex, minVertexIndex,
                                numVertices, startIndex, primitiveCount, instanceCount) -> None:
        base = int32(baseVertex, name="baseVertex")
        values = (base, *self._draw_integers(
            (minVertexIndex, numVertices, startIndex, primitiveCount, instanceCount),
            ("minVertexIndex", "numVertices", "startIndex", "primitiveCount", "instanceCount")))
        library = get_library(); library.check(library.cna_graphics_device_draw_instanced_primitives(
            self._require_handle(), int(PrimitiveType(primitiveType)), *values),
            "cna_graphics_device_draw_instanced_primitives")

    @staticmethod
    def _user_vertices(primitiveType, vertexData, vertexOffset, numVertices,
                       primitiveCount, declaration=None):
        from ._vertices import _VertexValue, _pack_vertex, VertexDeclaration
        if not isinstance(vertexData, Sequence) or not vertexData:
            raise ValueError("vertexData must be a non-empty sequence")
        kind = type(vertexData[0])
        if not issubclass(kind, _VertexValue) or not all(type(value) is kind for value in vertexData):
            raise TypeError("vertexData requires one supported built-in vertex type")
        offset, vertices, count = GraphicsDevice._draw_integers(
            (vertexOffset, numVertices, primitiveCount),
            ("vertexOffset", "numVertices", "primitiveCount"))
        if offset + vertices > len(vertexData): raise ValueError("vertex range is outside vertexData")
        if declaration is not None and not isinstance(declaration, VertexDeclaration):
            raise TypeError("vertexDeclaration must be VertexDeclaration")
        payload = b"".join(_pack_vertex(value) for value in vertexData)
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload)
        sources = {0: 1, 1: 2, 6: 3, 4: 4}
        info = abi.CNA_UserPrimitives(); info.struct_size, info.struct_version = c.sizeof(info), 1
        info.primitive_type, info.vertex_source = int(PrimitiveType(primitiveType)), sources[kind._vertex_type]
        info.vertex_data = c.cast(native, c.c_void_p)
        info.vertex_declaration = 0 if declaration is None else declaration._require_handle()
        info.vertex_offset, info.num_vertices, info.primitive_count = offset, vertices, count
        return info, native

    def DrawUserPrimitives(self, *args: object) -> None:
        if len(args) not in (4, 5): raise TypeError("no matching DrawUserPrimitives overload")
        primitive, data, offset, count = args[:4]
        count = self._draw_integers((count,), ("primitiveCount",))[0]
        required = {PrimitiveType.TriangleList: count * 3, PrimitiveType.TriangleStrip: count + 2,
                    PrimitiveType.LineList: count * 2, PrimitiveType.LineStrip: count + 1}[PrimitiveType(primitive)]
        info, keepalive = self._user_vertices(primitive, data, offset, required, count,
                                              None if len(args) == 4 else args[4])
        library = get_library(); library.check(library.cna_graphics_device_draw_user_primitives(
            self._require_handle(), c.byref(info)), "cna_graphics_device_draw_user_primitives")

    def DrawUserIndexedPrimitives(self, *args: object) -> None:
        if len(args) not in (7, 8): raise TypeError("no matching DrawUserIndexedPrimitives overload")
        primitive, vertexData, vertexOffset, numVertices, indexData, indexOffset, primitiveCount = args[:7]
        if not isinstance(indexData, Sequence) or not indexData: raise ValueError("indexData must be a non-empty sequence")
        indexOffset, primitiveCount = self._draw_integers((indexOffset, primitiveCount), ("indexOffset", "primitiveCount"))
        index_count = {PrimitiveType.TriangleList: primitiveCount * 3, PrimitiveType.TriangleStrip: primitiveCount + 2,
                       PrimitiveType.LineList: primitiveCount * 2, PrimitiveType.LineStrip: primitiveCount + 1}[PrimitiveType(primitive)]
        if indexOffset + index_count > len(indexData): raise ValueError("index range is outside indexData")
        selected = indexData[indexOffset:indexOffset+index_count]
        if not all(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 4294967295 for value in selected): raise ValueError("invalid index value")
        width = 0 if max(selected, default=0) <= 65535 else 1
        native_type = c.c_uint16 if width == 0 else c.c_uint32
        native_indices = (native_type * len(indexData))(*indexData)
        vertices, keepalive = self._user_vertices(primitive, vertexData, vertexOffset,
                                                  numVertices, primitiveCount,
                                                  None if len(args) == 7 else args[7])
        indices = abi.CNA_UserIndices(); indices.struct_size, indices.struct_version = c.sizeof(indices), 1
        indices.index_element_size, indices.index_offset = width, indexOffset
        indices.index_data = c.cast(native_indices, c.c_void_p)
        library = get_library(); library.check(library.cna_graphics_device_draw_user_indexed_primitives(
            self._require_handle(), c.byref(vertices), c.byref(indices)),
            "cna_graphics_device_draw_user_indexed_primitives")

    def GetBackBufferData(self, *args: object) -> None:
        if len(args) == 1: rectangle, data, start, count = None, args[0], 0, len(args[0])
        elif len(args) == 3: rectangle, data, start, count = None, *args
        elif len(args) == 4: rectangle, data, start, count = args
        else: raise TypeError("GetBackBufferData expects data; data,start,count; or rect,data,start,count")
        if rectangle is not None and not isinstance(rectangle, Rectangle): raise TypeError("rect must be Rectangle or None")
        if not isinstance(data, MutableSequence): raise TypeError("data must be mutable")
        start, count = self._draw_integers((start, count), ("startIndex", "elementCount"))
        if start + count > len(data): raise ValueError("destination range is outside data")
        readback = abi.CNA_BackBufferReadback(); readback.struct_size, readback.struct_version = c.sizeof(readback), 1
        readback.has_source_rectangle = rectangle is not None
        if rectangle is not None: readback.source_rectangle = abi.CNA_Rectangle(*tuple(rectangle))
        readback.start_index, readback.element_count = start, count
        native = (abi.CNA_Color * len(data))(); library = get_library()
        library.check(library.cna_graphics_device_get_backbuffer_data_window(
            self._require_handle(), c.byref(readback), native, len(data)),
            "cna_graphics_device_get_backbuffer_data_window")
        for index in range(start, start + count):
            value = native[index]; data[index] = Color(value.r, value.g, value.b, value.a)

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if not self._owned:
            # A Game's device is borrowed for the duration of a callback and is
            # released with its Game; the runtime refuses to destroy it here too.
            raise NativeCapabilityError(
                "GraphicsDevice.Dispose", 6, None,
                "a Game's GraphicsDevice is borrowed and is released with its Game; "
                "only a device built through the public constructor is the caller's to dispose")
        if self._disposed:
            return
        handle, self._handle = self._handle, 0
        self._disposed = True
        if handle:
            library = get_library()
            self._release_device_events(emit_disposing=False)
            library.check(library.cna_graphics_device_destroy(handle),
                          "cna_graphics_device_destroy")

    def __enter__(self) -> "GraphicsDevice":
        self._require_handle()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


Viewport.__xna_arities__ = {"__init__": {0, 1, 4}}
GraphicsDevice.__xna_arities__ = {
    "__init__": {3}, "Clear": {1, 4}, "Dispose": {0, 1},
    "Present": {0, 3}, "Reset": {0, 1, 2}, "SetVertexBuffer": {1, 2},
    "SetVertexBuffers": {1}, "SetRenderTarget": {1, 2}, "SetRenderTargets": {1},
    "DrawUserPrimitives": {4, 5}, "DrawUserIndexedPrimitives": {7, 8},
    "GetBackBufferData": {1, 3, 4},
}
