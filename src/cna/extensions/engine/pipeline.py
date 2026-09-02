"""The render pipeline: one object that draws a whole frame.

Everything else in this package is a piece a caller assembles. This is the
assembled thing: bracket a frame, hand it a camera, a shadow scene and a
transparent scene, and it runs the prepass, the shadow pass, the skybox, the
screen-space effects and the post-process chain in the order they have to happen
in, then reports what it did.

Settings are projected, not transcribed
---------------------------------------

``CNA_RenderPipelineSettingsEXT`` has fifty fields. A hand-written dataclass of
fifty names, fifty types and fifty one-line summaries would be wrong within one
CNA revision and would look right for much longer than that, so
:class:`RenderPipelineSettings` builds its properties from the *measured* layout
and documents each one with CNA's own ``@brief`` for that field. A field CNA adds
appears here with its documentation and no edit; a field CNA removes stops
existing rather than silently reading a neighbour.

The one thing that does have to be written down is which fields are enums rather
than plain integers, and a test asserts that table names only fields that exist.

Callbacks
---------

A pipeline calls back into Python twice per frame: once to draw shadow casters
and once to draw transparent geometry. Both are rooted for as long as CNA holds
them, a Python exception is caught and re-raised after the frame returns rather
than unwinding through C, and replacing a callback drops the previous root.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Callable

from Microsoft.Xna.Framework import Color, Matrix
from Microsoft.Xna.Framework.Graphics import RenderTarget2D, SurfaceFormat

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .pbr import TransparencyMode
from .values import RenderQuality, ShadowQuality, _native_matrix, _native_vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework import BoundingBox
    from Microsoft.Xna.Framework.Graphics import GraphicsDevice, Texture2D

    from .postprocess import PassTiming, PostProcessPass
    from .shadows import ShadowMap
    from .values import DirectionalLight

__all__ = [
    "TonemappingMode",
    "RenderPipelineSettings",
    "FrameStatistics",
    "RenderPipeline",
    "MINIMUM_GAMMA",
    "MINIMUM_FXAA_EDGE_THRESHOLD",
]

#: The floor CNA applies to gamma; it is used as a reciprocal power, so zero is
#: a division by zero rather than a look.
MINIMUM_GAMMA = _engine.CNA_RENDER_PIPELINE_MINIMUM_GAMMA_EXT
#: The floor CNA applies to the FXAA edge threshold.
MINIMUM_FXAA_EDGE_THRESHOLD = _engine.CNA_RENDER_PIPELINE_MINIMUM_FXAA_EDGE_THRESHOLD_EXT


class TonemappingMode(IntEnum):
    """Which curve maps scene-referred light onto a display."""

    Nothing = _engine.CNA_TONEMAPPING_MODE_NONE
    Reinhard = _engine.CNA_TONEMAPPING_MODE_REINHARD
    Filmic = _engine.CNA_TONEMAPPING_MODE_FILMIC
    Aces = _engine.CNA_TONEMAPPING_MODE_ACES
    Uncharted2 = _engine.CNA_TONEMAPPING_MODE_UNCHARTED2


#: Settings fields whose integer is an identity rather than a number. Everything
#: not named here is a plain value of its own C type. A test asserts every name
#: is a real field, so a renamed field fails rather than quietly losing its enum.
_SETTINGS_ENUMS: dict[str, type] = {
    "tonemapping_mode": TonemappingMode,
    "transparency_mode": TransparencyMode,
    "render_quality": RenderQuality,
    "shadow_quality": ShadowQuality,
}

#: Fields that carry the structure's own bookkeeping rather than a setting.
#: ``struct_size`` and ``struct_version`` are the versioning header this binding
#: fills itself, and ``reserved`` is padding CNA documents as write-zero.
_SETTINGS_INTERNAL = frozenset({"struct_size", "struct_version", "reserved"})


def _device_handle(device: "GraphicsDevice") -> c.c_uint64:
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(device._require_handle())


def _optional_texture(value: object, what: str) -> c.c_uint64:
    if value is None:
        return c.c_uint64(0)
    if not hasattr(value, "_require_handle"):
        raise TypeError(f"{what} must be a graphics texture or None")
    return c.c_uint64(value._require_handle())


def _settings_property(name: str, ctype: type, enum: type | None, doc: str):
    """One settings field, read and written through the native structure."""
    if enum is not None:
        def read(self):
            return enum(int(getattr(self._value, name)))

        def write(self, value) -> None:
            setattr(self._value, name, int(enum(value)))
    elif ctype is c.c_uint8:
        def read(self) -> bool:
            return bool(getattr(self._value, name))

        def write(self, value: bool) -> None:
            setattr(self._value, name, 1 if value else 0)
    elif ctype is c.c_float:
        def read(self) -> float:
            return float(getattr(self._value, name))

        def write(self, value: float) -> None:
            setattr(self._value, name, _support.real(value, name))
    else:
        width = "int32" if ctype is c.c_int32 else "uint32"

        def read(self) -> int:
            return int(getattr(self._value, name))

        def write(self, value: int) -> None:
            setattr(self._value, name, _support.checked(value, width, name))

    return property(read, write, doc=doc)


class _SettingsMeta(type):
    """Builds one property per measured field of the settings structure.

    A metaclass rather than a loop after the class body, because the properties
    have to exist before anything introspects the class -- including the
    extension-surface gate, which walks ``dir()``.
    """

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        structure = _engine.CNA_RenderPipelineSettingsEXT
        documentation = _engine.ENGINE_FIELD_DOCUMENTATION[
            "CNA_RenderPipelineSettingsEXT"]
        fields = []
        for field_name, ctype in structure._fields_:
            if field_name in _SETTINGS_INTERNAL:
                continue
            setattr(cls, field_name, _settings_property(
                field_name, ctype, _SETTINGS_ENUMS.get(field_name),
                documentation.get(field_name, "")))
            fields.append(field_name)
        cls.FIELDS = tuple(fields)
        return cls


class RenderPipelineSettings(metaclass=_SettingsMeta):
    """How a pipeline draws a frame: fifty settings, in one mutable value.

    Every property here is generated from the canonical structure's measured
    layout and carries CNA's own documentation for that field, so what a caller
    reads is what the header says rather than a second summary of it.
    :data:`FIELDS` names them all.

    CNA stores what it is given and corrects on use, which is why
    :meth:`normalize` exists: it applies the same floors and clamps the engine
    would, so a caller can see what their settings will become instead of
    discovering it in the picture.
    """

    __slots__ = ("_value",)

    #: Every setting, in the order the canonical structure declares them.
    FIELDS: tuple[str, ...] = ()

    def __init__(self) -> None:
        self._value = _engine.CNA_RenderPipelineSettingsEXT()
        _support.call("cna_render_pipeline_settings_ext_init", c.byref(self._value))

    @classmethod
    def _from_native(cls, value) -> "RenderPipelineSettings":
        self = cls.__new__(cls)
        self._value = value
        return self

    def copy(self) -> "RenderPipelineSettings":
        """An independent copy, sharing nothing with this one."""
        duplicate = _engine.CNA_RenderPipelineSettingsEXT()
        c.memmove(c.byref(duplicate), c.byref(self._value), c.sizeof(duplicate))
        return type(self)._from_native(duplicate)

    def normalize(self) -> None:
        """Applies the floors and clamps the engine would, in place.

        The header records which field gets which correction, and those
        summaries are on the properties. Calling this is how a caller sees the
        result before a frame does.
        """
        _support.call("cna_render_pipeline_settings_ext_normalize", c.byref(self._value))

    def apply_render_quality_preset(self) -> None:
        """Rewrites the quality-derived settings from :attr:`render_quality`."""
        _support.call("cna_render_pipeline_settings_ext_apply_render_quality_preset",
                      c.byref(self._value))

    def apply_from_string(self, text: str) -> int:
        """Applies ``name=value`` settings from text, returning how many were applied.

        The count is the point: a misspelled name is not applied and is not an
        error either, so the number is how a caller finds out that four of their
        five settings landed.
        """
        view, keep = _support.string_view(text, "text")
        applied = c.c_int32()
        _support.call("cna_render_pipeline_settings_ext_apply_from_string",
                      c.byref(self._value), view, c.byref(applied))
        del keep
        return int(applied.value)

    def as_dict(self) -> dict:
        """Every setting by name, for logging or comparison."""
        return {name: getattr(self, name) for name in self.FIELDS}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RenderPipelineSettings):
            return NotImplemented
        return self.as_dict() == other.as_dict()

    def __repr__(self) -> str:
        return f"RenderPipelineSettings({self.as_dict()})"


@dataclass(frozen=True)
class FrameStatistics:
    """What the pipeline did in the frame that just ended."""

    passes_run: int
    target_switches: int
    used_scene_target: bool
    drew_skybox: bool
    gpu_memory_estimate_bytes: int

    @classmethod
    def _from_native(cls, value) -> "FrameStatistics":
        return cls(int(value.passes_run), int(value.target_switches),
                   bool(value.used_scene_target), bool(value.drew_skybox),
                   int(value.gpu_memory_estimate_bytes))


class _FrameScope:
    """The ``begin``/``end`` bracket of one pipeline frame."""

    __slots__ = ("_pipeline", "_clear_color")

    def __init__(self, pipeline: "RenderPipeline", clear_color: Color | None) -> None:
        self._pipeline = pipeline
        self._clear_color = clear_color

    def __enter__(self) -> "RenderPipeline":
        self._pipeline._begin(self._clear_color)
        return self._pipeline

    def __exit__(self, *_exception: object) -> None:
        self._pipeline._end()


class RenderPipeline:
    """Draws a frame: prepass, shadows, skybox, scene, effects, post-process.

    The vertical slice a caller can actually run::

        with RenderPipeline(device) as pipeline:
            pipeline.settings = settings
            pipeline.resize(width, height)
            pipeline.set_camera(view, projection, 0.1, 100.0)
            pipeline.set_shadow_scene(shadow_map, sun, bounds, draw_casters)
            pipeline.set_transparent_scene(draw_transparent)
            with pipeline.frame(Color.CornflowerBlue):
                ...draw opaque geometry...
            statistics = pipeline.statistics

    What it did is not inferred from the settings: :attr:`statistics`,
    :attr:`did_draw_skybox` and :attr:`did_run_shadow_pass` report it.
    """

    __slots__ = ("_handle", "_device", "_views", "_passes", "_inputs", "_skybox",
                 "_shadow_map", "_callbacks", "_failure")

    def __init__(self, device: "GraphicsDevice") -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_render_pipeline_create", _device_handle(device)),
            "cna_render_pipeline_destroy", "render pipeline")
        self._device = device
        self._views: dict[str, object] = {}
        #: Passes the caller still owns; CNA borrows them.
        self._passes: list["PostProcessPass"] = []
        #: Textures CNA borrows for every later frame.
        self._inputs: list[object] = []
        self._skybox: object = None
        self._shadow_map: object = None
        #: Trampolines and the Python callables behind them, rooted together.
        self._callbacks: dict[str, tuple[object, object]] = {}
        self._failure: BaseException | None = None

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Disposes every view handed out, then releases the pipeline."""
        if self._handle.closed:
            return
        for view in reversed(list(self._views.values())):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        self._handle.close()
        self._passes.clear()
        self._inputs.clear()
        self._callbacks.clear()
        self._skybox = self._shadow_map = None

    def __enter__(self) -> "RenderPipeline":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    # --- configuration -----------------------------------------------------

    @property
    def settings(self) -> RenderPipelineSettings:
        """The settings the pipeline is currently drawing with.

        A copy: changing what comes back does not change the pipeline until it
        is assigned again, which is what CNA's own get/set pair means.
        """
        value = _support.out_struct(_engine.CNA_RenderPipelineSettingsEXT, 1,
                                    "cna_render_pipeline_get_settings",
                                    self._handle.argument)
        return RenderPipelineSettings._from_native(value)

    @settings.setter
    def settings(self, value: RenderPipelineSettings) -> None:
        if not isinstance(value, RenderPipelineSettings):
            raise TypeError("settings must be a RenderPipelineSettings")
        _support.call("cna_render_pipeline_set_settings", self._handle.argument,
                      c.byref(value._value))

    def resize(self, width: int, height: int) -> None:
        """Resizes every intermediate the pipeline owns."""
        for view in list(self._views.values()):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        _support.call("cna_render_pipeline_resize", self._handle.argument,
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))

    def set_camera(self, view: Matrix, projection: Matrix, near_plane: float,
                   far_plane: float) -> None:
        """The camera every depth-dependent effect reconstructs positions with."""
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_render_pipeline_set_camera", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection),
                      c.c_float(_support.real(near_plane, "near_plane")),
                      c.c_float(_support.real(far_plane, "far_plane")))

    def set_skybox_camera(self, view: Matrix, projection: Matrix) -> None:
        """The camera the skybox is drawn with, which usually drops translation."""
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_render_pipeline_set_skybox_camera", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection))

    def set_depth_normal_inputs(self, depth: "Texture2D | None",
                                normals: "Texture2D | None") -> None:
        """The prepass results the screen-space effects read.

        Both are borrowed for every later frame, so the pipeline keeps them
        alive.
        """
        _support.call("cna_render_pipeline_set_depth_normal_inputs",
                      self._handle.argument, _optional_texture(depth, "depth"),
                      _optional_texture(normals, "normals"))
        self._inputs = [value for value in (depth, normals) if value is not None]

    def set_velocity_input(self, velocity: "Texture2D | None") -> None:
        """The prepass velocity motion blur reads."""
        _support.call("cna_render_pipeline_set_velocity_input_ext",
                      self._handle.argument, _optional_texture(velocity, "velocity"))
        if velocity is not None:
            self._inputs.append(velocity)

    def add_user_pass(self, pass_: "PostProcessPass") -> None:
        """Appends a caller's own post-process pass after the built-in ones.

        Borrowed: the caller keeps owning it, and the pipeline holds a reference
        so it cannot be collected while CNA could still apply it.
        """
        from .postprocess import PostProcessPass

        if not isinstance(pass_, PostProcessPass):
            raise TypeError("pass_ must be a PostProcessPass")
        _support.call("cna_render_pipeline_add_user_pass", self._handle.argument,
                      pass_._handle.argument)
        self._passes.append(pass_)

    def clear_user_passes(self) -> None:
        """Removes every pass the caller added. They stay the caller's."""
        _support.call("cna_render_pipeline_clear_user_passes", self._handle.argument)
        self._passes.clear()

    @property
    def skybox(self):
        """The skybox the pipeline draws, or ``None``.

        The object handed back is the one that was assigned; CNA answers with
        the handle it already holds rather than a new borrow.
        """
        handle = _support.out_handle("cna_render_pipeline_get_skybox",
                                     self._handle.argument)
        return self._skybox if handle else None

    @skybox.setter
    def skybox(self, value) -> None:
        handle = 0 if value is None else value._handle.value
        _support.call("cna_render_pipeline_set_skybox", self._handle.argument,
                      c.c_uint64(handle))
        self._skybox = value

    @property
    def shadow_map(self) -> "ShadowMap | None":
        """The shadow map :meth:`set_shadow_scene` was given, or ``None``."""
        handle = _support.out_handle("cna_render_pipeline_get_shadow_map",
                                     self._handle.argument)
        return self._shadow_map if handle else None

    def _root(self, key: str, draw: Callable[[], None]):
        """Wraps a caller's draw as a trampoline and roots both."""
        def invoke(_context) -> int:
            try:
                draw()
            except BaseException as error:  # re-raised once the frame returns
                if self._failure is None:
                    self._failure = error
                return 12  # CNA_RESULT_INTERNAL
            return 0

        trampoline = _engine.CNA_RenderPipelineDrawCallback(invoke)
        self._callbacks[key] = (trampoline, draw)
        return trampoline

    def set_transparent_scene(self, draw: Callable[[], None] | None) -> None:
        """The callback that draws transparent geometry, after the opaque pass."""
        if draw is None:
            self._callbacks.pop("transparent", None)
            _support.call("cna_render_pipeline_set_transparent_scene",
                          self._handle.argument,
                          _engine.CNA_RenderPipelineDrawCallback(), None)
            return
        if not callable(draw):
            raise TypeError("draw must be callable or None")
        _support.call("cna_render_pipeline_set_transparent_scene",
                      self._handle.argument, self._root("transparent", draw), None)

    def set_shadow_scene(self, shadow_map: "ShadowMap", light: "DirectionalLight",
                         scene_bounds: "BoundingBox",
                         draw_casters: Callable[[], None]) -> None:
        """The shadow map, its light, the scene it covers, and how to draw casters.

        The shadow map is borrowed for every later frame, so the pipeline keeps
        it alive; the callback is rooted the same way as the transparent one.
        """
        from .shadows import ShadowMap, _bounds

        if not isinstance(shadow_map, ShadowMap):
            raise TypeError("shadow_map must be a ShadowMap")
        if not callable(draw_casters):
            raise TypeError("draw_casters must be callable")
        native_light = light._native()
        box = _bounds(scene_bounds)
        _support.call("cna_render_pipeline_set_shadow_scene", self._handle.argument,
                      shadow_map._handle.argument, c.byref(native_light), c.byref(box),
                      self._root("shadow", draw_casters), None)
        self._shadow_map = shadow_map

    @property
    def gpu_timing_enabled(self) -> bool:
        """Whether the pipeline times its passes on the GPU."""
        return _support.out_bool("cna_render_pipeline_is_gpu_timing_enabled_ext",
                                 self._handle.argument)

    @gpu_timing_enabled.setter
    def gpu_timing_enabled(self, value: bool) -> None:
        _support.call("cna_render_pipeline_set_gpu_timing_enabled_ext",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    # --- the frame ---------------------------------------------------------

    def frame(self, clear_color: Color | None = None) -> _FrameScope:
        """The bracket one frame is drawn inside."""
        return _FrameScope(self, clear_color)

    def _begin(self, clear_color: Color | None) -> None:
        self._failure = None
        if clear_color is None:
            _support.call("cna_render_pipeline_begin", self._handle.argument, None)
            return
        if not isinstance(clear_color, Color):
            raise TypeError("clear_color must be a Microsoft.Xna.Framework.Color")
        native = _abi.CNA_Color(int(clear_color.R), int(clear_color.G),
                                int(clear_color.B), int(clear_color.A))
        _support.call("cna_render_pipeline_begin", self._handle.argument,
                      c.byref(native))

    def _end(self) -> None:
        try:
            _support.call("cna_render_pipeline_end", self._handle.argument)
        finally:
            failure, self._failure = self._failure, None
            if failure is not None:
                raise failure

    # --- what it did -------------------------------------------------------

    @property
    def statistics(self) -> FrameStatistics:
        """What the last frame actually did, from CNA rather than from settings."""
        value = _support.out_struct(_engine.CNA_RenderPipelineFrameStatisticsEXT, 1,
                                    "cna_render_pipeline_get_statistics",
                                    self._handle.argument)
        return FrameStatistics._from_native(value)

    @property
    def did_draw_skybox(self) -> bool:
        """Whether the last frame drew a skybox."""
        return _support.out_bool("cna_render_pipeline_did_skybox_draw",
                                 self._handle.argument)

    @property
    def did_run_shadow_pass(self) -> bool:
        """Whether the last frame ran the shadow pass."""
        return _support.out_bool("cna_render_pipeline_did_shadow_pass_run",
                                 self._handle.argument)

    @property
    def last_frame_pass_count(self) -> int:
        """How many passes the last frame ran."""
        return _support.out_i32("cna_render_pipeline_get_last_frame_pass_count",
                                self._handle.argument)

    @property
    def gpu_memory_estimate_bytes(self) -> int:
        """CNA's estimate of what the pipeline's intermediates cost."""
        return _support.out_u64("cna_render_pipeline_get_gpu_memory_estimate_bytes",
                                self._handle.argument)

    @property
    def uses_scene_target(self) -> bool:
        """Whether the pipeline renders into its own target rather than the back buffer.

        It does when anything downstream needs to read the scene -- a
        post-process pass, HDR, or transparency that resolves.
        """
        return _support.out_bool("cna_render_pipeline_is_using_scene_target",
                                 self._handle.argument)

    @property
    def scene_target_format(self) -> SurfaceFormat:
        """The format the scene target has, which HDR decides."""
        return SurfaceFormat(_support.out_u32(
            "cna_render_pipeline_get_scene_target_format", self._handle.argument))

    @property
    def scene_target(self) -> "RenderTarget2D | None":
        """The pipeline's own scene target, as a counted borrow.

        Handed out once and disposed with the pipeline, like every other counted
        view in this package. ``None`` when the pipeline is drawing straight to
        the back buffer.
        """
        existing = self._views.get("scene")
        if existing is not None and not getattr(existing, "IsDisposed", False):
            return existing
        handle = _support.out_handle("cna_render_pipeline_get_scene_target",
                                     self._handle.argument)
        if handle == 0:
            return None
        view = RenderTarget2D._view_of(self._device, handle)
        self._views["scene"] = view
        return view

    @property
    def transparency_fallback_reason(self) -> str:
        """Why order-independent transparency fell back, or the empty string.

        A pipeline asked for weighted-blended transparency on a renderer that
        cannot accumulate falls back to sorting rather than failing, and this is
        how a caller finds out which one they got.
        """
        return _support.copied_text(
            "cna_render_pipeline_copy_transparency_fallback_reason_ext",
            (self._handle.argument,), "transparency fallback reason")

    @property
    def pass_timings(self) -> tuple["PassTiming", ...]:
        """Every GPU timing the pipeline's own chain recorded, in pass order."""
        from .postprocess import PassTiming

        count = _support.out_u64("cna_render_pipeline_get_pass_timing_count_ext",
                                 self._handle.argument)
        timings = []
        for index in range(count):
            value = _support.out_struct(
                _engine.CNA_PassTimingEXT, 1, "cna_render_pipeline_get_pass_timing_ext",
                self._handle.argument, c.c_uint64(index))
            name = _support.copied_text(
                "cna_render_pipeline_copy_pass_timing_name_ext",
                (self._handle.argument, c.c_uint64(index)), "pass timing name")
            timings.append(PassTiming(name, int(value.sample_count),
                                      float(value.milliseconds)))
        return tuple(timings)

    def release_device_resources(self) -> None:
        """Releases every device resource the pipeline allocated.

        The views it handed out go with them, so they are disposed here rather
        than left pointing at storage that no longer exists.
        """
        for view in list(self._views.values()):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        _support.call("cna_render_pipeline_release_device_resources_ext",
                      self._handle.argument)
