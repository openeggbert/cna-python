"""Graphics adapter, display-mode, and presentation value facades."""

from __future__ import annotations

import ctypes as c

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library
from _cna_native.runtime_context import current_game

from .._game import DisplayOrientation
from .._geometry import Rectangle
from .._language import classproperty, staticproperty, staticpropertymeta
from .._numeric import f32, int32
from ._device import (
    DepthFormat, GraphicsProfile, PresentInterval, RenderTargetUsage, SurfaceFormat,
)


def _active_device():
    game = current_game()
    return game.GraphicsDevice


class DisplayMode:
    def __init__(self, value: abi.CNA_DisplayMode, _token: object = None) -> None:
        if _token is not DisplayMode:
            raise TypeError("DisplayMode values are provided by GraphicsAdapter")
        self._width = int(value.width); self._height = int(value.height)
        self._aspect_ratio = f32(value.aspect_ratio); self._format = SurfaceFormat(value.format)

    @classmethod
    def _from_native(cls, value: abi.CNA_DisplayMode) -> "DisplayMode":
        return cls(value, cls)

    @property
    def Format(self) -> SurfaceFormat: return self._format
    @property
    def Height(self) -> int: return self._height
    @property
    def Width(self) -> int: return self._width
    @property
    def AspectRatio(self) -> float: return self._aspect_ratio
    @property
    def TitleSafeArea(self) -> Rectangle:
        return Rectangle(self.Width // 10, self.Height // 10,
                         self.Width - self.Width // 5, self.Height - self.Height // 5)
    def ToString(self) -> str:
        return (f"{{Width:{self.Width} Height:{self.Height} Format:{self.Format.name} "
                f"AspectRatio:{self.AspectRatio:g}}}")
    __str__ = ToString


class DisplayModeCollection:
    def __init__(self, adapter: "GraphicsAdapter", _token: object = None) -> None:
        if _token is not adapter:
            raise TypeError("DisplayModeCollection instances are provided by GraphicsAdapter")
        self._adapter = adapter

    def _modes(self, format: SurfaceFormat | None = None) -> tuple[DisplayMode, ...]:
        device = self._adapter._device
        handle = device._require_handle()
        library = get_library()
        count = c.c_uint64()
        filtered = format is not None
        selected = SurfaceFormat.Color if format is None else SurfaceFormat(format)
        library.check(library.cna_graphics_adapter_get_display_mode_count(
            handle, self._adapter._index, filtered, int(selected), c.byref(count)),
            "cna_graphics_adapter_get_display_mode_count")
        if count.value == 0: return ()
        values = (abi.CNA_DisplayMode * count.value)()
        for value in values:
            value.struct_size, value.struct_version = c.sizeof(value), 1
        written = c.c_uint64()
        library.check(library.cna_graphics_adapter_copy_display_modes(
            handle, self._adapter._index, filtered, int(selected), values, count.value,
            c.byref(written)), "cna_graphics_adapter_copy_display_modes")
        return tuple(DisplayMode._from_native(values[index]) for index in range(written.value))

    def GetEnumerator(self): return iter(self._modes())
    def __iter__(self): return self.GetEnumerator()
    def __getitem__(self, format: SurfaceFormat): return self._modes(SurfaceFormat(format))


class GraphicsAdapter(metaclass=staticpropertymeta):
    def __init__(self, device, index: int, _token: object = None) -> None:
        if _token is not device:
            raise TypeError("GraphicsAdapter instances are provided by the active GraphicsDevice")
        self._device, self._index = device, index
        self._supported_modes = DisplayModeCollection(self, self)

    @classmethod
    def _for_device(cls, device, index: int):
        cached = device._adapter_cache.get(index)
        if cached is None:
            cached = cls(device, index, device)
            device._adapter_cache[index] = cached
        return cached

    def _info(self) -> abi.CNA_GraphicsAdapterInfo:
        value = abi.CNA_GraphicsAdapterInfo()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_graphics_adapter_get_info(
            self._device._require_handle(), self._index, c.byref(value)),
            "cna_graphics_adapter_get_info")
        return value

    def _string(self, operation: str, size: int) -> str:
        if size == 0: return ""
        buffer = c.create_string_buffer(size)
        written = c.c_uint64()
        library = get_library()
        library.check(getattr(library, operation)(
            self._device._require_handle(), self._index, buffer, size, c.byref(written)), operation)
        return bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict")

    @classproperty
    def DefaultAdapter(cls):
        device = _active_device()
        adapters = cls.Adapters
        if not adapters: raise RuntimeError("CNA reported no graphics adapters")
        return next((value for value in adapters if value.IsDefaultAdapter), adapters[0])

    @classproperty
    def Adapters(cls):
        device = _active_device()
        count = c.c_uint64(); library = get_library()
        library.check(library.cna_graphics_adapter_get_count(
            device._require_handle(), c.byref(count)), "cna_graphics_adapter_get_count")
        return tuple(cls._for_device(device, index) for index in range(count.value))

    @classmethod
    def _get_use_null_device(cls): return cls.DefaultAdapter._info().use_null_device != 0
    @classmethod
    def _set_use_null_device(cls, value):
        if type(value) is not bool: raise TypeError("UseNullDevice must be bool")
        adapter = cls.DefaultAdapter; info = adapter._info(); library = get_library()
        library.check(library.cna_graphics_adapter_set_device_preferences(
            adapter._device._require_handle(), adapter._index, value,
            info.use_reference_device != 0), "cna_graphics_adapter_set_device_preferences")

    @classmethod
    def _get_use_reference_device(cls): return cls.DefaultAdapter._info().use_reference_device != 0
    @classmethod
    def _set_use_reference_device(cls, value):
        if type(value) is not bool: raise TypeError("UseReferenceDevice must be bool")
        adapter = cls.DefaultAdapter; info = adapter._info(); library = get_library()
        library.check(library.cna_graphics_adapter_set_device_preferences(
            adapter._device._require_handle(), adapter._index, info.use_null_device != 0,
            value), "cna_graphics_adapter_set_device_preferences")

    UseNullDevice = staticproperty(
        lambda cls: cls._get_use_null_device(),
        lambda cls, value: cls._set_use_null_device(value),
    )
    UseReferenceDevice = staticproperty(
        lambda cls: cls._get_use_reference_device(),
        lambda cls, value: cls._set_use_reference_device(value),
    )

    @property
    def MonitorHandle(self) -> int:
        self._info()
        raise NativeCapabilityError(
            "GraphicsAdapter.MonitorHandle", 6, None,
            "CNA ABI 0.7 deliberately does not expose native monitor handles",
        )
    @property
    def SupportedDisplayModes(self) -> DisplayModeCollection: return self._supported_modes
    @property
    def CurrentDisplayMode(self) -> DisplayMode:
        value = abi.CNA_DisplayMode(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_graphics_adapter_get_current_display_mode(
            self._device._require_handle(), self._index, c.byref(value)),
            "cna_graphics_adapter_get_current_display_mode")
        return DisplayMode._from_native(value)
    @property
    def IsWideScreen(self) -> bool: return self._info().is_wide_screen != 0
    @property
    def IsDefaultAdapter(self) -> bool: return self._info().is_default_adapter != 0
    @property
    def Revision(self) -> int: return int(self._info().revision)
    @property
    def SubSystemId(self) -> int: return int(self._info().subsystem_id)
    @property
    def DeviceId(self) -> int: return int(self._info().device_id)
    @property
    def VendorId(self) -> int: return int(self._info().vendor_id)
    @property
    def DeviceName(self) -> str:
        info = self._info(); return self._string("cna_graphics_adapter_copy_device_name", info.device_name_byte_length)
    @property
    def Description(self) -> str:
        info = self._info(); return self._string("cna_graphics_adapter_copy_description", info.description_byte_length)

    def IsProfileSupported(self, graphicsProfile: GraphicsProfile) -> bool:
        profile = GraphicsProfile(graphicsProfile); value = c.c_uint8(); library = get_library()
        library.check(library.cna_graphics_adapter_is_profile_supported(
            self._device._require_handle(), self._index, int(profile), c.byref(value)),
            "cna_graphics_adapter_is_profile_supported")
        return value.value != 0

    def _query(self, operation: str, graphicsProfile, format, depthFormat, multiSampleCount):
        profile, surface, depth = GraphicsProfile(graphicsProfile), SurfaceFormat(format), DepthFormat(depthFormat)
        count = int32(multiSampleCount, name="multiSampleCount")
        if count < 0: raise ValueError("multiSampleCount cannot be negative")
        value = abi.CNA_GraphicsFormatSelection(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(getattr(library, operation)(self._device._require_handle(), self._index,
                      int(profile), int(surface), int(depth), count, c.byref(value)), operation)
        return (value.exact_match != 0, SurfaceFormat(value.format),
                DepthFormat(value.depth_format), int(value.multi_sample_count))

    def QueryBackBufferFormat(self, graphicsProfile, format, depthFormat, multiSampleCount):
        return self._query("cna_graphics_adapter_query_backbuffer_format", graphicsProfile, format,
                           depthFormat, multiSampleCount)
    def QueryRenderTargetFormat(self, graphicsProfile, format, depthFormat, multiSampleCount):
        return self._query("cna_graphics_adapter_query_render_target_format", graphicsProfile, format,
                           depthFormat, multiSampleCount)


class PresentationParameters:
    def __init__(self) -> None:
        self._BackBufferWidth = 0; self._BackBufferHeight = 0
        self._BackBufferFormat = SurfaceFormat.Color; self._DepthStencilFormat = DepthFormat.None_
        self._MultiSampleCount = 0; self._DisplayOrientation = DisplayOrientation.Default
        self._PresentationInterval = PresentInterval.Default
        self._RenderTargetUsage = RenderTargetUsage.DiscardContents
        self._DeviceWindowHandle = 0; self._IsFullScreen = True

    def _property(name, converter):
        private = "_" + name
        return property(lambda self: getattr(self, private),
                        lambda self, value: setattr(self, private, converter(value)))
    BackBufferWidth = _property("BackBufferWidth", lambda value: int32(value, name="BackBufferWidth"))
    BackBufferHeight = _property("BackBufferHeight", lambda value: int32(value, name="BackBufferHeight"))
    BackBufferFormat = _property("BackBufferFormat", SurfaceFormat)
    DepthStencilFormat = _property("DepthStencilFormat", DepthFormat)
    MultiSampleCount = _property("MultiSampleCount", lambda value: int32(value, name="MultiSampleCount"))
    DisplayOrientation = _property("DisplayOrientation", DisplayOrientation)
    PresentationInterval = _property("PresentationInterval", PresentInterval)
    RenderTargetUsage = _property("RenderTargetUsage", RenderTargetUsage)
    DeviceWindowHandle = _property("DeviceWindowHandle", lambda value: int(value) if isinstance(value, int) and not isinstance(value, bool) else (_ for _ in ()).throw(TypeError("DeviceWindowHandle must be int")))
    IsFullScreen = _property("IsFullScreen", lambda value: value if type(value) is bool else (_ for _ in ()).throw(TypeError("IsFullScreen must be bool")))
    @property
    def Bounds(self) -> Rectangle: return Rectangle(0, 0, self.BackBufferWidth, self.BackBufferHeight)
    def Clone(self) -> "PresentationParameters":
        result = PresentationParameters()
        for name in ("BackBufferWidth", "BackBufferHeight", "BackBufferFormat", "DepthStencilFormat",
                     "MultiSampleCount", "DisplayOrientation", "PresentationInterval",
                     "RenderTargetUsage", "DeviceWindowHandle", "IsFullScreen"):
            setattr(result, name, getattr(self, name))
        return result
    def _native_value(self) -> abi.CNA_PresentationParameters:
        value = abi.CNA_PresentationParameters(); value.struct_size, value.struct_version = c.sizeof(value), 1
        value.back_buffer_format = int(self.BackBufferFormat); value.back_buffer_width = self.BackBufferWidth
        value.back_buffer_height = self.BackBufferHeight; value.depth_stencil_format = int(self.DepthStencilFormat)
        value.multi_sample_count = self.MultiSampleCount; value.presentation_interval = int(self.PresentationInterval)
        value.display_orientation = int(self.DisplayOrientation); value.render_target_usage = int(self.RenderTargetUsage)
        value.is_full_screen = self.IsFullScreen
        return value
    @classmethod
    def _from_native(cls, value):
        result = cls(); result._BackBufferFormat = SurfaceFormat(value.back_buffer_format)
        result._BackBufferWidth = int(value.back_buffer_width); result._BackBufferHeight = int(value.back_buffer_height)
        result._DepthStencilFormat = DepthFormat(value.depth_stencil_format)
        result._MultiSampleCount = int(value.multi_sample_count)
        result._PresentationInterval = PresentInterval(value.presentation_interval)
        result._DisplayOrientation = DisplayOrientation(value.display_orientation)
        result._RenderTargetUsage = RenderTargetUsage(value.render_target_usage)
        result._IsFullScreen = bool(value.is_full_screen)
        return result


class _GraphicsException(Exception):
    def __init__(self, *args: object) -> None:
        if not args: super().__init__()
        elif len(args) == 1 and isinstance(args[0], str): super().__init__(args[0])
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], Exception):
            super().__init__(args[0]); self.__cause__ = args[1]
        else: raise TypeError(f"{type(self).__name__} expects (), message, or message and inner")

class NoSuitableGraphicsDeviceException(_GraphicsException): pass
class DeviceLostException(_GraphicsException): pass
class DeviceNotResetException(_GraphicsException): pass

for _value in (NoSuitableGraphicsDeviceException, DeviceLostException, DeviceNotResetException):
    _value.__xna_arities__ = {"__init__": {0, 1, 2}}
