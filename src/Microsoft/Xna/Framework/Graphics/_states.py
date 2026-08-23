"""Graphics state descriptors and fixed-size device collections."""

from __future__ import annotations

import ctypes as c

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from .._geometry import Color
from .._numeric import f32, int32
from ._device import (
    Blend, BlendFunction, ColorWriteChannels, CompareFunction, CullMode, FillMode,
    StencilOperation, TextureAddressMode, TextureFilter,
)
from ._resources import GraphicsResource, Texture


def _bool(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError("value must be bool")
    return value


def _copy_color(value: object) -> Color:
    if not isinstance(value, Color):
        raise TypeError("value must be Color")
    return Color(*tuple(value))


def _state_property(name: str, converter, *, copied: bool = False):
    private = "_" + name
    def get(self):
        value = getattr(self, private)
        return _copy_color(value) if copied else value
    def set(self, value):
        self._ensure_mutable()
        setattr(self, private, converter(value))
    return property(get, set)


class _StateResource:
    def _init_state(self) -> None:
        self._init_managed_resource()
        self._frozen = False
        self._stock = False

    def _ensure_mutable(self) -> None:
        if self.IsDisposed:
            raise RuntimeError(f"{type(self).__name__} is disposed")
        if self._frozen:
            raise RuntimeError(f"{type(self).__name__} cannot be modified after binding")

    def _bind(self, device) -> None:
        if self.IsDisposed:
            raise RuntimeError(f"{type(self).__name__} is disposed")
        if not self._stock and self._graphics_device not in (None, device):
            raise ValueError("graphics state belongs to a different GraphicsDevice")
        if not self._stock:
            if self._graphics_device is None:
                device._game._register_native_child(self)
                self._game = device._game
            self._graphics_device = device
        self._frozen = True

    def _make_stock(self, name: str) -> "_StateResource":
        self._name = name
        self._stock = True
        self._frozen = True
        return self


def _blend_function_to_native(value: BlendFunction) -> int:
    # CNA's native enum retains the C++ Max/Min ordering (3/4), whereas XNA
    # metadata is Min/Max (3/4).  The public enum remains XNA-authoritative.
    return {BlendFunction.Min: 4, BlendFunction.Max: 3}.get(value, int(value))


def _blend_function_from_native(value: int) -> BlendFunction:
    return BlendFunction({4: 3, 3: 4}.get(value, value))


class BlendState(GraphicsResource, _StateResource):
    def __init__(self) -> None:
        self._init_state()
        self._AlphaBlendFunction = BlendFunction.Add
        self._AlphaDestinationBlend = Blend.Zero
        self._AlphaSourceBlend = Blend.One
        self._ColorBlendFunction = BlendFunction.Add
        self._ColorDestinationBlend = Blend.Zero
        self._ColorSourceBlend = Blend.One
        self._ColorWriteChannels = ColorWriteChannels.All
        self._ColorWriteChannels1 = ColorWriteChannels.All
        self._ColorWriteChannels2 = ColorWriteChannels.All
        self._ColorWriteChannels3 = ColorWriteChannels.All
        self._BlendFactor = Color.White
        self._MultiSampleMask = -1

    AlphaBlendFunction = _state_property("AlphaBlendFunction", BlendFunction)
    AlphaDestinationBlend = _state_property("AlphaDestinationBlend", Blend)
    AlphaSourceBlend = _state_property("AlphaSourceBlend", Blend)
    ColorBlendFunction = _state_property("ColorBlendFunction", BlendFunction)
    ColorDestinationBlend = _state_property("ColorDestinationBlend", Blend)
    ColorSourceBlend = _state_property("ColorSourceBlend", Blend)
    ColorWriteChannels = _state_property("ColorWriteChannels", ColorWriteChannels)
    ColorWriteChannels1 = _state_property("ColorWriteChannels1", ColorWriteChannels)
    ColorWriteChannels2 = _state_property("ColorWriteChannels2", ColorWriteChannels)
    ColorWriteChannels3 = _state_property("ColorWriteChannels3", ColorWriteChannels)
    BlendFactor = _state_property("BlendFactor", _copy_color, copied=True)
    MultiSampleMask = _state_property("MultiSampleMask", lambda value: int32(value, name="MultiSampleMask"))

    def _native_value(self) -> abi.CNA_BlendState:
        value = abi.CNA_BlendState()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.alpha_blend_function = _blend_function_to_native(self.AlphaBlendFunction)
        value.alpha_destination_blend = int(self.AlphaDestinationBlend)
        value.alpha_source_blend = int(self.AlphaSourceBlend)
        value.color_blend_function = _blend_function_to_native(self.ColorBlendFunction)
        value.color_destination_blend = int(self.ColorDestinationBlend)
        value.color_source_blend = int(self.ColorSourceBlend)
        value.color_write_channels = int(self.ColorWriteChannels)
        value.color_write_channels1 = int(self.ColorWriteChannels1)
        value.color_write_channels2 = int(self.ColorWriteChannels2)
        value.color_write_channels3 = int(self.ColorWriteChannels3)
        value.blend_factor = abi.CNA_Color(*tuple(self.BlendFactor))
        value.multi_sample_mask = self.MultiSampleMask
        return value

    @classmethod
    def _from_native(cls, value: abi.CNA_BlendState, device, current=None):
        signature = (
            _blend_function_from_native(value.alpha_blend_function), Blend(value.alpha_destination_blend),
            Blend(value.alpha_source_blend), _blend_function_from_native(value.color_blend_function),
            Blend(value.color_destination_blend), Blend(value.color_source_blend),
            ColorWriteChannels(value.color_write_channels), ColorWriteChannels(value.color_write_channels1),
            ColorWriteChannels(value.color_write_channels2), ColorWriteChannels(value.color_write_channels3),
            Color(value.blend_factor.r, value.blend_factor.g,
                  value.blend_factor.b, value.blend_factor.a),
            int(value.multi_sample_mask),
        )
        if current is not None and not current.IsDisposed and current._signature() == signature:
            return current
        result = cls()
        (result._AlphaBlendFunction, result._AlphaDestinationBlend, result._AlphaSourceBlend,
         result._ColorBlendFunction, result._ColorDestinationBlend, result._ColorSourceBlend,
         result._ColorWriteChannels, result._ColorWriteChannels1, result._ColorWriteChannels2,
         result._ColorWriteChannels3, result._BlendFactor, result._MultiSampleMask) = signature
        result._bind(device)
        return result

    def _signature(self):
        return (self.AlphaBlendFunction, self.AlphaDestinationBlend, self.AlphaSourceBlend,
                self.ColorBlendFunction, self.ColorDestinationBlend, self.ColorSourceBlend,
                self.ColorWriteChannels, self.ColorWriteChannels1, self.ColorWriteChannels2,
                self.ColorWriteChannels3, self.BlendFactor, self.MultiSampleMask)


class DepthStencilState(GraphicsResource, _StateResource):
    def __init__(self) -> None:
        self._init_state()
        self._DepthBufferEnable = True; self._DepthBufferWriteEnable = True
        self._DepthBufferFunction = CompareFunction.LessEqual
        self._StencilEnable = False; self._StencilFunction = CompareFunction.Always
        self._StencilPass = StencilOperation.Keep; self._StencilFail = StencilOperation.Keep
        self._StencilDepthBufferFail = StencilOperation.Keep
        self._TwoSidedStencilMode = False
        self._CounterClockwiseStencilFunction = CompareFunction.Always
        self._CounterClockwiseStencilPass = StencilOperation.Keep
        self._CounterClockwiseStencilFail = StencilOperation.Keep
        self._CounterClockwiseStencilDepthBufferFail = StencilOperation.Keep
        self._StencilMask = 2_147_483_647; self._StencilWriteMask = 2_147_483_647
        self._ReferenceStencil = 0

    DepthBufferEnable = _state_property("DepthBufferEnable", _bool)
    DepthBufferWriteEnable = _state_property("DepthBufferWriteEnable", _bool)
    DepthBufferFunction = _state_property("DepthBufferFunction", CompareFunction)
    StencilEnable = _state_property("StencilEnable", _bool)
    StencilFunction = _state_property("StencilFunction", CompareFunction)
    StencilPass = _state_property("StencilPass", StencilOperation)
    StencilFail = _state_property("StencilFail", StencilOperation)
    StencilDepthBufferFail = _state_property("StencilDepthBufferFail", StencilOperation)
    TwoSidedStencilMode = _state_property("TwoSidedStencilMode", _bool)
    CounterClockwiseStencilFunction = _state_property("CounterClockwiseStencilFunction", CompareFunction)
    CounterClockwiseStencilPass = _state_property("CounterClockwiseStencilPass", StencilOperation)
    CounterClockwiseStencilFail = _state_property("CounterClockwiseStencilFail", StencilOperation)
    CounterClockwiseStencilDepthBufferFail = _state_property("CounterClockwiseStencilDepthBufferFail", StencilOperation)
    StencilMask = _state_property("StencilMask", lambda value: int32(value, name="StencilMask"))
    StencilWriteMask = _state_property("StencilWriteMask", lambda value: int32(value, name="StencilWriteMask"))
    ReferenceStencil = _state_property("ReferenceStencil", lambda value: int32(value, name="ReferenceStencil"))

    def _native_value(self) -> abi.CNA_DepthStencilState:
        value = abi.CNA_DepthStencilState()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.depth_buffer_enable = self.DepthBufferEnable
        value.depth_buffer_write_enable = self.DepthBufferWriteEnable
        value.stencil_enable = self.StencilEnable
        value.two_sided_stencil_mode = self.TwoSidedStencilMode
        value.depth_buffer_function = int(self.DepthBufferFunction)
        value.stencil_function = int(self.StencilFunction)
        value.stencil_mask = self.StencilMask; value.stencil_write_mask = self.StencilWriteMask
        value.reference_stencil = self.ReferenceStencil
        value.stencil_fail = int(self.StencilFail)
        value.stencil_depth_buffer_fail = int(self.StencilDepthBufferFail)
        value.stencil_pass = int(self.StencilPass)
        value.counter_clockwise_stencil_function = int(self.CounterClockwiseStencilFunction)
        value.counter_clockwise_stencil_fail = int(self.CounterClockwiseStencilFail)
        value.counter_clockwise_stencil_depth_buffer_fail = int(self.CounterClockwiseStencilDepthBufferFail)
        value.counter_clockwise_stencil_pass = int(self.CounterClockwiseStencilPass)
        return value

    @classmethod
    def _from_native(cls, value, device, current=None):
        result = cls()
        result._DepthBufferEnable = bool(value.depth_buffer_enable)
        result._DepthBufferWriteEnable = bool(value.depth_buffer_write_enable)
        result._StencilEnable = bool(value.stencil_enable)
        result._TwoSidedStencilMode = bool(value.two_sided_stencil_mode)
        result._DepthBufferFunction = CompareFunction(value.depth_buffer_function)
        result._StencilFunction = CompareFunction(value.stencil_function)
        result._StencilMask = int(value.stencil_mask); result._StencilWriteMask = int(value.stencil_write_mask)
        result._ReferenceStencil = int(value.reference_stencil)
        result._StencilFail = StencilOperation(value.stencil_fail)
        result._StencilDepthBufferFail = StencilOperation(value.stencil_depth_buffer_fail)
        result._StencilPass = StencilOperation(value.stencil_pass)
        result._CounterClockwiseStencilFunction = CompareFunction(value.counter_clockwise_stencil_function)
        result._CounterClockwiseStencilFail = StencilOperation(value.counter_clockwise_stencil_fail)
        result._CounterClockwiseStencilDepthBufferFail = StencilOperation(value.counter_clockwise_stencil_depth_buffer_fail)
        result._CounterClockwiseStencilPass = StencilOperation(value.counter_clockwise_stencil_pass)
        if current is not None and not current.IsDisposed and current._native_bytes() == bytes(value):
            return current
        result._bind(device)
        return result

    def _native_bytes(self): return bytes(self._native_value())


class RasterizerState(GraphicsResource, _StateResource):
    def __init__(self) -> None:
        self._init_state()
        self._CullMode = CullMode.CullCounterClockwiseFace; self._FillMode = FillMode.Solid
        self._DepthBias = 0.0; self._SlopeScaleDepthBias = 0.0
        self._MultiSampleAntiAlias = True; self._ScissorTestEnable = False

    CullMode = _state_property("CullMode", CullMode)
    FillMode = _state_property("FillMode", FillMode)
    DepthBias = _state_property("DepthBias", f32)
    SlopeScaleDepthBias = _state_property("SlopeScaleDepthBias", f32)
    MultiSampleAntiAlias = _state_property("MultiSampleAntiAlias", _bool)
    ScissorTestEnable = _state_property("ScissorTestEnable", _bool)

    def _native_value(self):
        value = abi.CNA_RasterizerState()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.cull_mode = int(self.CullMode); value.fill_mode = int(self.FillMode)
        value.depth_bias = self.DepthBias; value.slope_scale_depth_bias = self.SlopeScaleDepthBias
        value.multi_sample_anti_alias = self.MultiSampleAntiAlias
        value.scissor_test_enable = self.ScissorTestEnable
        return value

    @classmethod
    def _from_native(cls, value, device, current=None):
        if current is not None and not current.IsDisposed and bytes(current._native_value()) == bytes(value):
            return current
        result = cls()
        result._CullMode = CullMode(value.cull_mode); result._FillMode = FillMode(value.fill_mode)
        result._DepthBias = f32(value.depth_bias); result._SlopeScaleDepthBias = f32(value.slope_scale_depth_bias)
        result._MultiSampleAntiAlias = bool(value.multi_sample_anti_alias)
        result._ScissorTestEnable = bool(value.scissor_test_enable)
        result._bind(device)
        return result


class SamplerState(GraphicsResource, _StateResource):
    def __init__(self) -> None:
        self._init_state()
        self._AddressU = TextureAddressMode.Wrap; self._AddressV = TextureAddressMode.Wrap
        self._AddressW = TextureAddressMode.Wrap; self._Filter = TextureFilter.Linear
        self._MaxAnisotropy = 4; self._MaxMipLevel = 0; self._MipMapLevelOfDetailBias = 0.0

    AddressU = _state_property("AddressU", TextureAddressMode)
    AddressV = _state_property("AddressV", TextureAddressMode)
    AddressW = _state_property("AddressW", TextureAddressMode)
    Filter = _state_property("Filter", TextureFilter)
    MaxAnisotropy = _state_property("MaxAnisotropy", lambda value: int32(value, name="MaxAnisotropy"))
    MaxMipLevel = _state_property("MaxMipLevel", lambda value: int32(value, name="MaxMipLevel"))
    MipMapLevelOfDetailBias = _state_property("MipMapLevelOfDetailBias", f32)

    def _native_value(self):
        value = abi.CNA_SamplerState()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        value.address_u = int(self.AddressU); value.address_v = int(self.AddressV)
        value.address_w = int(self.AddressW); value.filter = int(self.Filter)
        value.max_anisotropy = self.MaxAnisotropy; value.max_mip_level = self.MaxMipLevel
        value.mip_map_level_of_detail_bias = self.MipMapLevelOfDetailBias
        return value

    @classmethod
    def _from_native(cls, value, device, current=None):
        if current is not None and not current.IsDisposed and bytes(current._native_value()) == bytes(value):
            return current
        result = cls()
        result._AddressU = TextureAddressMode(value.address_u); result._AddressV = TextureAddressMode(value.address_v)
        result._AddressW = TextureAddressMode(value.address_w); result._Filter = TextureFilter(value.filter)
        result._MaxAnisotropy = int(value.max_anisotropy); result._MaxMipLevel = int(value.max_mip_level)
        result._MipMapLevelOfDetailBias = f32(value.mip_map_level_of_detail_bias)
        result._bind(device)
        return result


def _blend_preset(name, source, destination):
    value = BlendState(); value._ColorSourceBlend = source; value._ColorDestinationBlend = destination
    value._AlphaSourceBlend = source; value._AlphaDestinationBlend = destination
    return value._make_stock(name)


BlendState.Opaque = _blend_preset("BlendState.Opaque", Blend.One, Blend.Zero)
BlendState.AlphaBlend = _blend_preset("BlendState.AlphaBlend", Blend.One, Blend.InverseSourceAlpha)
BlendState.Additive = _blend_preset("BlendState.Additive", Blend.SourceAlpha, Blend.One)
BlendState.NonPremultiplied = _blend_preset("BlendState.NonPremultiplied", Blend.SourceAlpha, Blend.InverseSourceAlpha)

DepthStencilState.Default = DepthStencilState()._make_stock("DepthStencilState.Default")
DepthStencilState.DepthRead = DepthStencilState()
DepthStencilState.DepthRead._DepthBufferWriteEnable = False
DepthStencilState.DepthRead._make_stock("DepthStencilState.DepthRead")
DepthStencilState.None_ = DepthStencilState()
DepthStencilState.None_._DepthBufferEnable = False; DepthStencilState.None_._DepthBufferWriteEnable = False
DepthStencilState.None_._make_stock("DepthStencilState.None")

def _rasterizer_preset(name, mode):
    value = RasterizerState(); value._CullMode = mode; return value._make_stock(name)
RasterizerState.CullClockwise = _rasterizer_preset("RasterizerState.CullClockwise", CullMode.CullClockwiseFace)
RasterizerState.CullCounterClockwise = _rasterizer_preset("RasterizerState.CullCounterClockwise", CullMode.CullCounterClockwiseFace)
RasterizerState.CullNone = _rasterizer_preset("RasterizerState.CullNone", CullMode.None_)

def _sampler_preset(name, filter_value, address):
    value = SamplerState(); value._Filter = filter_value
    value._AddressU = value._AddressV = value._AddressW = address
    return value._make_stock(name)
SamplerState.LinearWrap = _sampler_preset("SamplerState.LinearWrap", TextureFilter.Linear, TextureAddressMode.Wrap)
SamplerState.LinearClamp = _sampler_preset("SamplerState.LinearClamp", TextureFilter.Linear, TextureAddressMode.Clamp)
SamplerState.PointWrap = _sampler_preset("SamplerState.PointWrap", TextureFilter.Point, TextureAddressMode.Wrap)
SamplerState.PointClamp = _sampler_preset("SamplerState.PointClamp", TextureFilter.Point, TextureAddressMode.Clamp)
SamplerState.AnisotropicWrap = _sampler_preset("SamplerState.AnisotropicWrap", TextureFilter.Anisotropic, TextureAddressMode.Wrap)
SamplerState.AnisotropicClamp = _sampler_preset("SamplerState.AnisotropicClamp", TextureFilter.Anisotropic, TextureAddressMode.Clamp)


class _FixedCollection:
    @property
    def Count(self) -> int:
        if self._stage == 0: return 16
        return 0 if self._device.GraphicsProfile.value == 0 else 4
    def __len__(self) -> int: return self.Count
    def _index(self, index: int) -> int:
        value = int32(index, name="index")
        if value < 0 or value >= self.Count:
            raise IndexError(f"sampler index is outside 0..{self.Count - 1}")
        return value


class SamplerStateCollection(_FixedCollection):
    def __init__(self, device, stage: int, _token: object = None) -> None:
        if _token is not device:
            raise TypeError("SamplerStateCollection instances are created by GraphicsDevice")
        self._device, self._stage = device, stage
        self._states: list[SamplerState | None] = [None] * 16

    def __getitem__(self, index: int) -> SamplerState:
        index = self._index(index)
        value = abi.CNA_SamplerState(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_graphics_device_get_sampler_state(
            self._device._require_handle(), self._stage, index, c.byref(value)),
            "cna_graphics_device_get_sampler_state")
        result = SamplerState._from_native(value, self._device, self._states[index])
        self._states[index] = result
        return result

    def __setitem__(self, index: int, state: SamplerState) -> None:
        index = self._index(index)
        if not isinstance(state, SamplerState): raise TypeError("state must be SamplerState")
        if state.IsDisposed: raise RuntimeError("SamplerState is disposed")
        if state._graphics_device not in (None, self._device) and not state._stock:
            raise ValueError("SamplerState belongs to a different GraphicsDevice")
        native = state._native_value()
        library = get_library()
        library.check(library.cna_graphics_device_set_sampler_state(
            self._device._require_handle(), self._stage, index, c.byref(native)),
            "cna_graphics_device_set_sampler_state")
        state._bind(self._device)
        self._states[index] = state


class TextureCollection(_FixedCollection):
    def __init__(self, device, stage: int, _token: object = None) -> None:
        if _token is not device:
            raise TypeError("TextureCollection instances are created by GraphicsDevice")
        self._device, self._stage = device, stage
        self._textures: list[Texture | None] = [None] * 16

    def __getitem__(self, index: int) -> Texture:
        index = self._index(index)
        info = abi.CNA_TextureSlotInfo(); info.struct_size, info.struct_version = c.sizeof(info), 1
        library = get_library()
        library.check(library.cna_graphics_device_get_texture(
            self._device._require_handle(), self._stage, index, c.byref(info)),
            "cna_graphics_device_get_texture")
        cached = self._textures[index]
        if not info.bound:
            self._textures[index] = None
            return None
        if cached is not None and not cached.IsDisposed and int(info.texture) == cached._require_handle():
            return cached
        raise NativeCapabilityError(
            "TextureCollection.__getitem__", 6, None,
            "CNA reports a canonically bound texture without a stable C resource identity",
        )

    def __setitem__(self, index: int, texture: Texture | None) -> None:
        index = self._index(index)
        if texture is not None:
            if not isinstance(texture, Texture): raise TypeError("texture must be Texture or None")
            if texture.IsDisposed: raise RuntimeError("Texture is disposed")
            if texture.GraphicsDevice is not self._device:
                raise ValueError("Texture belongs to a different GraphicsDevice")
        handle = 0 if texture is None else texture._require_handle()
        library = get_library()
        library.check(library.cna_graphics_device_set_texture(
            self._device._require_handle(), self._stage, index, handle),
            "cna_graphics_device_set_texture")
        self._textures[index] = texture
