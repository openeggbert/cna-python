"""The post-process passes a frame ends with, and the display it ends on.

Bloom, tonemapping, colour grading, FXAA, chromatic aberration, film grain, lens
flare, ASCII, spatial upscaling, HDR output and auto exposure. Each is a
:class:`~cna.extensions.engine.postprocess.PostProcessPass` and is driven through
the shared pass vocabulary; what each class adds is the state that pass reads.

Properties, not transcriptions
------------------------------

Almost every one of these is a get/set pair over one scalar, so the properties
are built by a factory that takes the two route names as literals. That keeps the
route names greppable and visible to the reachability gate, which a name built
from an f-string would not be, and it keeps forty of these from being forty
copies of the same six lines.

The pure helpers -- :func:`bloom_extract_channel`, :func:`tonemap_channel`,
:func:`encode_pq`, :func:`roll_off` and the rest -- are the CPU twins of what the
shaders do. CNA publishes them so a caller can check a pass against arithmetic
rather than against a screenshot, and they need no device.
"""

from __future__ import annotations

import ctypes as c
from enum import IntEnum
from typing import TYPE_CHECKING

from Microsoft.Xna.Framework import Vector3
from Microsoft.Xna.Framework.Graphics import Texture2D, Texture3D

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .pipeline import TonemappingMode
from .postprocess import PostProcessPass
from .values import RenderQuality, _native_vector, _vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    import os

    from Microsoft.Xna.Framework.Graphics import GraphicsDevice, Texture

__all__ = [
    "LutInterpolation",
    "DisplayColorSpace",
    "AsciiQuantizeMode",
    "BloomPass",
    "ToneMapPass",
    "ColorGradePass",
    "FxaaPass",
    "ChromaticAberrationPass",
    "FilmGrainPass",
    "LensFlarePass",
    "AsciiPass",
    "AsciiEffect",
    "SpatialUpscalePass",
    "CubeLut",
    "HdrDisplayOutput",
    "AutoExposure",
    "bloom_extract_channel",
    "bloom_iterations_for",
    "fxaa_edge_threshold_for",
    "fxaa_fragment_glsl",
    "tonemap_channel",
    "lut_size_for_strip",
    "create_identity_lut",
    "is_identity_scale",
    "encode_pq",
    "decode_pq",
    "rec709_to_rec2020",
    "roll_off",
    "encode_for_display",
    "COLOR_GRADE_MAXIMUM_LUT_SIZE",
    "CUBE_LUT_MINIMUM_SIZE",
    "CUBE_LUT_MAXIMUM_SIZE",
    "HDR_DEFAULT_PAPER_WHITE_NITS",
    "HDR_DEFAULT_PEAK_NITS",
    "LENS_FLARE_GHOST_COUNT",
    "MOTION_BLUR_SAMPLE_COUNT",
]

#: The largest lookup table a colour grade will sample.
COLOR_GRADE_MAXIMUM_LUT_SIZE = _engine.CNA_COLOR_GRADE_MAX_LUT_SIZE_EXT
#: The size bounds a ``.cube`` file's table has to fall inside.
CUBE_LUT_MINIMUM_SIZE = _engine.CNA_CUBE_LUT_MIN_SIZE_EXT
CUBE_LUT_MAXIMUM_SIZE = _engine.CNA_CUBE_LUT_MAX_SIZE_EXT
#: What a display is assumed to be until it says otherwise, in nits.
HDR_DEFAULT_PAPER_WHITE_NITS = _engine.CNA_HDR_DISPLAY_DEFAULT_PAPER_WHITE_NITS_EXT
HDR_DEFAULT_PEAK_NITS = _engine.CNA_HDR_DISPLAY_DEFAULT_PEAK_NITS_EXT
#: How many ghosts a lens flare draws, and how many samples motion blur takes.
LENS_FLARE_GHOST_COUNT = _engine.CNA_LENS_FLARE_GHOST_COUNT_EXT
MOTION_BLUR_SAMPLE_COUNT = _engine.CNA_MOTION_BLUR_SAMPLE_COUNT_EXT


class LutInterpolation(IntEnum):
    """How a colour grade samples between lookup-table entries."""

    Trilinear = _engine.CNA_LUT_INTERPOLATION_TRILINEAR
    Tetrahedral = _engine.CNA_LUT_INTERPOLATION_TETRAHEDRAL


class DisplayColorSpace(IntEnum):
    """What the display expects the final image to be encoded in."""

    Srgb = _engine.CNA_DISPLAY_COLOR_SPACE_SRGB
    ScRgb = _engine.CNA_DISPLAY_COLOR_SPACE_SCRGB
    Hdr10 = _engine.CNA_DISPLAY_COLOR_SPACE_HDR10


class AsciiQuantizeMode(IntEnum):
    """Whether the ASCII pass keeps colour or reduces to black and white."""

    BlackAndWhite = _engine.CNA_ASCII_QUANTIZE_MODE_BLACK_WHITE
    Color = _engine.CNA_ASCII_QUANTIZE_MODE_COLOR


def _device_handle(device: "GraphicsDevice") -> c.c_uint64:
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(device._require_handle())


def _texture_handle(value: object, what: str) -> c.c_uint64:
    if value is None:
        return c.c_uint64(0)
    if not hasattr(value, "_require_handle"):
        raise TypeError(f"{what} must be a graphics texture or None")
    return c.c_uint64(value._require_handle())


def _float(getter: str, setter: str, doc: str):
    """One float the object reads and writes straight through."""
    return property(
        lambda self: _support.out_f32(getter, self._handle.argument),
        lambda self, value: _support.call(
            setter, self._handle.argument, c.c_float(_support.real(value, "value"))),
        doc=doc)


def _integer(getter: str, setter: str, doc: str):
    """One signed integer the object reads and writes straight through."""
    return property(
        lambda self: _support.out_i32(getter, self._handle.argument),
        lambda self, value: _support.call(
            setter, self._handle.argument,
            c.c_int32(_support.checked(value, "int32", "value"))),
        doc=doc)


def _boolean(getter: str, setter: str, doc: str):
    """One flag the object reads and writes straight through."""
    return property(
        lambda self: _support.out_bool(getter, self._handle.argument),
        lambda self, value: _support.call(
            setter, self._handle.argument, c.c_uint8(1 if value else 0)),
        doc=doc)


def _identity(getter: str, setter: str, enum: type, doc: str):
    """One enum the object reads and writes straight through."""
    return property(
        lambda self: enum(_support.out_u32(getter, self._handle.argument)),
        lambda self, value: _support.call(
            setter, self._handle.argument, c.c_uint32(int(enum(value)))),
        doc=doc)


class _ConfiguredPass(PostProcessPass):
    """A pass created by its own constructor and driven through the shared ones.

    Everything a concrete pass adds is state; the applying, the naming and the
    support query all come from :class:`PostProcessPass`.
    """

    __slots__ = ()
    _CREATE: str = ""

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle(self._CREATE, _device_handle(device)),
            "cna_post_process_pass_destroy", type(self).__name__))
        self._effect = None


class BloomPass(_ConfiguredPass):
    """Extracts what is brighter than a threshold, blurs it, and adds it back."""

    __slots__ = ()
    _CREATE = "cna_bloom_pass_create"

    threshold = _float("cna_bloom_pass_get_threshold", "cna_bloom_pass_set_threshold",
                       "How bright a texel has to be before it blooms at all.")
    intensity = _float("cna_bloom_pass_get_intensity", "cna_bloom_pass_set_intensity",
                       "How much of the blurred result is added back.")
    iterations = _integer("cna_bloom_pass_get_iterations",
                          "cna_bloom_pass_set_iterations",
                          "How many blur steps the pyramid takes; more is wider.")

    def reset_targets(self) -> None:
        """Releases the pass's own blur pyramid."""
        _support.call("cna_bloom_pass_reset_targets", self._handle.argument)


class ToneMapPass(_ConfiguredPass):
    """Maps scene-referred light onto a display, with optional debanding."""

    __slots__ = ()
    _CREATE = "cna_tonemap_pass_create"

    mode = _identity("cna_tonemap_pass_get_mode", "cna_tonemap_pass_set_mode",
                     TonemappingMode, "Which curve the pass applies.")
    exposure = _float("cna_tonemap_pass_get_exposure", "cna_tonemap_pass_set_exposure",
                      "The multiplier applied before the curve.")
    gamma = _float("cna_tonemap_pass_get_gamma", "cna_tonemap_pass_set_gamma",
                   "The display gamma applied after the curve, as a reciprocal power.")
    deband_enabled = _boolean("cna_tonemap_pass_is_deband_enabled",
                              "cna_tonemap_pass_set_deband_enabled",
                              "Whether triangular dither is added to break up banding.")
    deband_strength = _float("cna_tonemap_pass_get_deband_strength",
                             "cna_tonemap_pass_set_deband_strength",
                             "How much dither, in quantisation steps.")


class ColorGradePass(_ConfiguredPass):
    """Remaps colour through a lookup table.

    Two shapes of table, because renderers differ: a strip texture laid out as
    slices side by side, and a volume texture. The tables are borrowed, so the
    caller keeps them alive.
    """

    __slots__ = ("_lut", "_volume_lut")

    _CREATE = "cna_color_grade_pass_create"

    def __init__(self, device: "GraphicsDevice") -> None:
        super().__init__(device)
        self._lut = None
        self._volume_lut = None

    interpolation = _identity("cna_color_grade_pass_get_interpolation",
                              "cna_color_grade_pass_set_interpolation",
                              LutInterpolation,
                              "How the pass samples between table entries.")
    strength = _float("cna_color_grade_pass_get_strength",
                      "cna_color_grade_pass_set_strength",
                      "How far toward the graded colour the result moves.")

    @property
    def lut(self) -> "Texture2D | None":
        """The strip lookup table, or ``None``.

        The object handed back is the one that was assigned; CNA answers with
        the handle it already holds rather than a new borrow.
        """
        handle = _support.out_handle("cna_color_grade_pass_get_lut",
                                     self._handle.argument)
        return self._lut if handle else None

    @lut.setter
    def lut(self, value: "Texture2D | None") -> None:
        _support.call("cna_color_grade_pass_set_lut", self._handle.argument,
                      _texture_handle(value, "lut"))
        self._lut = value

    @property
    def volume_lut(self) -> "Texture3D | None":
        """The volume lookup table, or ``None``."""
        handle = _support.out_handle("cna_color_grade_pass_get_volume_lut",
                                     self._handle.argument)
        return self._volume_lut if handle else None

    @volume_lut.setter
    def volume_lut(self, value: "Texture3D | None") -> None:
        _support.call("cna_color_grade_pass_set_volume_lut", self._handle.argument,
                      _texture_handle(value, "volume_lut"))
        self._volume_lut = value


class FxaaPass(_ConfiguredPass):
    """Fast approximate anti-aliasing, over the finished image."""

    __slots__ = ()
    _CREATE = "cna_fxaa_pass_create"

    edge_threshold = _float("cna_fxaa_pass_get_edge_threshold",
                            "cna_fxaa_pass_set_edge_threshold",
                            "How much local contrast counts as an edge worth filtering.")


class ChromaticAberrationPass(_ConfiguredPass):
    """Offsets the colour channels radially, as a lens does."""

    __slots__ = ()
    _CREATE = "cna_chromatic_aberration_pass_create"

    strength = _float("cna_chromatic_aberration_pass_get_strength",
                      "cna_chromatic_aberration_pass_set_strength",
                      "How far apart the channels are pulled at the edge of frame.")


class FilmGrainPass(_ConfiguredPass):
    """Adds grain.

    The grain is stochastic, so a test that pinned one frame's pixels would pin
    noise. What is stable is that the intensity reaches the pass and that a zero
    intensity leaves the image alone.
    """

    __slots__ = ()
    _CREATE = "cna_film_grain_pass_create"

    intensity = _float("cna_film_grain_pass_get_intensity",
                       "cna_film_grain_pass_set_intensity",
                       "How much grain; zero leaves the image untouched.")


class LensFlarePass(_ConfiguredPass):
    """Ghosts and a halo from whatever is brighter than a threshold."""

    __slots__ = ()
    _CREATE = "cna_lens_flare_pass_create"

    threshold = _float("cna_lens_flare_pass_get_threshold",
                       "cna_lens_flare_pass_set_threshold",
                       "How bright a texel has to be before it produces a ghost.")
    intensity = _float("cna_lens_flare_pass_get_intensity",
                       "cna_lens_flare_pass_set_intensity",
                       "How strong the ghosts and the halo are.")
    dispersal = _float("cna_lens_flare_pass_get_dispersal",
                       "cna_lens_flare_pass_set_dispersal",
                       "How far apart the ghosts are spaced along the flare axis.")


class AsciiEffect:
    """The cell size and quantisation an :class:`AsciiPass` draws with.

    A counted borrow of the pass's own effect. The pass hands it out once and
    releases it on close, so a caller never holds a second one.

    Its routes live in ``graphics_ext.h`` rather than in the engine layer, which
    is why they are a dependency slice: without them the pass would have a
    getter returning something nothing could read.
    """

    __slots__ = ("_handle",)

    def __init__(self) -> None:
        raise TypeError(
            "AsciiEffect is handed out by AsciiPass.ascii_effect and is not "
            "constructed directly")

    @classmethod
    def _wrap(cls, handle: "_support.NativeHandle") -> "AsciiEffect":
        self = cls.__new__(cls)
        self._handle = handle
        return self

    quantize_mode = _identity("cna_ascii_post_process_effect_get_quantize_mode",
                              "cna_ascii_post_process_effect_set_quantize_mode",
                              AsciiQuantizeMode,
                              "Whether the pass keeps colour or reduces to two tones.")

    @property
    def cell_size(self) -> tuple[int, int]:
        """The character cell, in pixels, as ``(width, height)``."""
        width, height = c.c_int32(), c.c_int32()
        _support.call("cna_ascii_post_process_effect_get_cell_size",
                      self._handle.argument, c.byref(width), c.byref(height))
        return int(width.value), int(height.value)

    @cell_size.setter
    def cell_size(self, value: tuple[int, int]) -> None:
        width, height = value
        _support.call("cna_ascii_post_process_effect_set_cell_size",
                      self._handle.argument,
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))

    @property
    def last_grid_dimensions(self) -> tuple[int, int]:
        """How many cells the last draw covered, as ``(columns, rows)``."""
        columns, rows = c.c_int32(), c.c_int32()
        _support.call("cna_ascii_post_process_effect_get_last_grid_dimensions",
                      self._handle.argument, c.byref(columns), c.byref(rows))
        return int(columns.value), int(rows.value)


class AsciiPass(_ConfiguredPass):
    """Redraws the image as characters on a grid."""

    __slots__ = ("_ascii_effect",)
    _CREATE = "cna_ascii_pass_create"

    def __init__(self, device: "GraphicsDevice") -> None:
        super().__init__(device)
        self._ascii_effect: AsciiEffect | None = None

    @property
    def ascii_effect(self) -> AsciiEffect:
        """The pass's cell size and quantisation, as one counted borrow.

        Handed out once and released when the pass closes, like every other
        counted view in this package.
        """
        if self._ascii_effect is None or self._ascii_effect._handle.closed:
            self._ascii_effect = AsciiEffect._wrap(_support.NativeHandle(
                _support.out_handle("cna_ascii_pass_get_effect",
                                    self._handle.argument),
                "cna_ascii_post_process_effect_destroy", "ASCII effect"))
        return self._ascii_effect

    def close(self) -> None:
        if self._ascii_effect is not None:
            self._ascii_effect._handle.close()
            self._ascii_effect = None
        super().close()


class SpatialUpscalePass:
    """Scales an image up with an edge-aware filter.

    Not a :class:`PostProcessPass`: it takes a source *size* and a target size
    rather than a frame context, because that is the whole operation. It has its
    own handle and its own draw.
    """

    __slots__ = ("_handle",)

    def __init__(self, device: "GraphicsDevice") -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_spatial_upscale_pass_create",
                                _device_handle(device)),
            "cna_spatial_upscale_pass_destroy", "spatial upscale pass")

    sharpness = _float("cna_spatial_upscale_pass_get_sharpness",
                       "cna_spatial_upscale_pass_set_sharpness",
                       "How much the filter sharpens as it scales.")
    edge_adaptive = _boolean("cna_spatial_upscale_pass_get_edge_adaptive",
                             "cna_spatial_upscale_pass_set_edge_adaptive",
                             "Whether the filter follows edges rather than the grid.")

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the pass. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self) -> "SpatialUpscalePass":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def draw(self, source: "Texture", source_width: int, source_height: int,
             target_width: int, target_height: int) -> None:
        """Scales ``source`` onto whatever target is bound."""
        _support.call(
            "cna_spatial_upscale_pass_draw", self._handle.argument,
            _texture_handle(source, "source"),
            c.c_int32(_support.checked(source_width, "int32", "source_width")),
            c.c_int32(_support.checked(source_height, "int32", "source_height")),
            c.c_int32(_support.checked(target_width, "int32", "target_width")),
            c.c_int32(_support.checked(target_height, "int32", "target_height")))


class CubeLut:
    """A ``.cube`` colour lookup table, parsed.

    Needs no graphics device to parse or inspect -- it is a file format -- and
    one only to turn into a texture a pass can sample.
    """

    __slots__ = ("_handle",)

    def __init__(self) -> None:
        raise TypeError(
            "a CubeLut comes from CubeLut.parse or CubeLut.load and is not "
            "constructed directly")

    @classmethod
    def _wrap(cls, handle: int) -> "CubeLut":
        self = cls.__new__(cls)
        self._handle = _support.NativeHandle(handle, "cna_cube_lut_destroy", "cube LUT")
        return self

    @classmethod
    def parse(cls, text: str) -> "CubeLut":
        """Parses a ``.cube`` document from text."""
        view, keep = _support.string_view(text, "text")
        handle = _support.out_handle("cna_cube_lut_parse", view)
        del keep
        return cls._wrap(handle)

    @classmethod
    def load(cls, path: "str | os.PathLike[str]") -> "CubeLut":
        """Reads and parses a ``.cube`` file."""
        import os as _os

        view, keep = _support.string_view(_os.fspath(path), "path")
        handle = _support.out_handle("cna_cube_lut_load_from_file", view)
        del keep
        return cls._wrap(handle)

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the table. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self) -> "CubeLut":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def size(self) -> int:
        """The table's edge length; it holds ``size ** 3`` entries."""
        return _support.out_i32("cna_cube_lut_get_size", self._handle.argument)

    @property
    def title(self) -> str:
        """The ``TITLE`` the file declared, or the empty string."""
        return _support.copied_text("cna_cube_lut_copy_title",
                                    (self._handle.argument,), "cube LUT title")

    @property
    def domain_minimum(self) -> Vector3:
        """The input value the first entry corresponds to."""
        value = _abi.CNA_Vector3()
        _support.call("cna_cube_lut_get_domain_min", self._handle.argument,
                      c.byref(value))
        return _vector(value)

    @property
    def domain_maximum(self) -> Vector3:
        """The input value the last entry corresponds to."""
        value = _abi.CNA_Vector3()
        _support.call("cna_cube_lut_get_domain_max", self._handle.argument,
                      c.byref(value))
        return _vector(value)

    @property
    def is_unit_domain(self) -> bool:
        """Whether the domain is the usual ``0..1``, which most shaders assume."""
        return _support.out_bool("cna_cube_lut_is_unit_domain", self._handle.argument)

    def entry(self, red: int, green: int, blue: int) -> Vector3:
        """One entry of the table, by its three indices."""
        value = _abi.CNA_Vector3()
        _support.call("cna_cube_lut_get_entry", self._handle.argument,
                      c.c_int32(_support.checked(red, "int32", "red")),
                      c.c_int32(_support.checked(green, "int32", "green")),
                      c.c_int32(_support.checked(blue, "int32", "blue")),
                      c.byref(value))
        return _vector(value)

    def create_strip_texture(self, device: "GraphicsDevice") -> Texture2D:
        """Builds the strip texture a colour grade samples. The caller owns it."""
        return Texture2D._from_handle(device, _support.out_handle(
            "cna_cube_lut_create_strip_texture", self._handle.argument,
            _device_handle(device)))

    def create_volume_texture(self, device: "GraphicsDevice") -> Texture3D:
        """Builds the volume texture a colour grade samples. The caller owns it."""
        return Texture3D._from_handle(device, _support.out_handle(
            "cna_cube_lut_create_volume_texture", self._handle.argument,
            _device_handle(device)))


class HdrDisplayOutput:
    """Encodes the finished image for whatever the display expects.

    Not a post-process pass: it is the last step, drawn straight to the back
    buffer, and it takes a source and a destination rather than a frame context.
    """

    __slots__ = ("_handle",)

    def __init__(self, device: "GraphicsDevice") -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_hdr_display_output_create",
                                _device_handle(device)),
            "cna_hdr_display_output_destroy", "HDR display output")

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can present in a wide colour space at all."""
        return _support.out_bool("cna_hdr_display_output_is_supported",
                                 self._handle.argument)

    color_space = _identity("cna_hdr_display_output_get_color_space",
                            "cna_hdr_display_output_set_color_space",
                            DisplayColorSpace,
                            "What the display expects the image encoded in.")
    paper_white_nits = _float("cna_hdr_display_output_get_paper_white_nits",
                              "cna_hdr_display_output_set_paper_white_nits",
                              "How bright diffuse white should be, in nits.")
    peak_nits = _float("cna_hdr_display_output_get_peak_nits",
                       "cna_hdr_display_output_set_peak_nits",
                       "The brightest the display can go, in nits.")

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the output. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self) -> "HdrDisplayOutput":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def draw(self, source: "Texture", destination: object, width: int,
             height: int) -> None:
        """Encodes ``source`` onto ``destination``; ``None`` is the back buffer."""
        _support.call("cna_hdr_display_output_draw", self._handle.argument,
                      _texture_handle(source, "source"),
                      _texture_handle(destination, "destination"),
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))


class AutoExposure:
    """Measures how bright the scene is and moves the exposure toward it.

    Adaptation is time-based, so the exposure a caller reads depends on how much
    time they said had passed. That is what makes it testable: feed it a known
    scene and a known delta and the direction of the move is predictable, even
    though the exact value depends on the curve.
    """

    __slots__ = ("_handle",)

    def __init__(self, device: "GraphicsDevice") -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_auto_exposure_ext_create",
                                _device_handle(device)),
            "cna_auto_exposure_ext_destroy", "auto exposure")

    exposure = _float("cna_auto_exposure_ext_get_exposure",
                      "cna_auto_exposure_ext_set_exposure",
                      "The exposure right now; assigning it skips the adaptation.")
    key_value = _float("cna_auto_exposure_ext_get_key_value",
                       "cna_auto_exposure_ext_set_key_value",
                       "The middle grey the measured luminance is aimed at.")

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases it. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self) -> "AutoExposure":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def brightening_speed(self) -> float:
        """How fast the exposure falls when the scene gets brighter, per second."""
        return _support.out_f32("cna_auto_exposure_ext_get_brightening_speed",
                                self._handle.argument)

    @property
    def darkening_speed(self) -> float:
        """How fast the exposure rises when the scene gets darker, per second."""
        return _support.out_f32("cna_auto_exposure_ext_get_darkening_speed",
                                self._handle.argument)

    def set_adaptation_speeds(self, brightening_per_second: float,
                              darkening_per_second: float) -> None:
        """Both speeds at once, because CNA sets them together.

        The eye adapts to darkness far more slowly than to light, so the two are
        deliberately separate numbers rather than one.
        """
        _support.call("cna_auto_exposure_ext_set_adaptation_speeds",
                      self._handle.argument,
                      c.c_float(_support.real(brightening_per_second,
                                              "brightening_per_second")),
                      c.c_float(_support.real(darkening_per_second,
                                              "darkening_per_second")))

    def set_exposure_range(self, minimum: float, maximum: float) -> None:
        """The bounds adaptation stays inside."""
        _support.call("cna_auto_exposure_ext_set_exposure_range", self._handle.argument,
                      c.c_float(_support.real(minimum, "minimum")),
                      c.c_float(_support.real(maximum, "maximum")))

    def measure_average_luminance(self, scene: "Texture") -> float:
        """How bright the scene is, without moving the exposure."""
        return _support.out_f32("cna_auto_exposure_ext_measure_average_luminance",
                                self._handle.argument,
                                _texture_handle(scene, "scene"))

    def update(self, scene: "Texture", delta_seconds: float) -> float:
        """Measures the scene, moves the exposure toward it, and returns it."""
        return _support.out_f32(
            "cna_auto_exposure_ext_update", self._handle.argument,
            _texture_handle(scene, "scene"),
            c.c_float(_support.real(delta_seconds, "delta_seconds")))

    def apply_to(self, settings) -> None:
        """Writes the current exposure into a render pipeline's settings."""
        from .pipeline import RenderPipelineSettings

        if not isinstance(settings, RenderPipelineSettings):
            raise TypeError("settings must be a RenderPipelineSettings")
        _support.call("cna_auto_exposure_ext_apply_to", self._handle.argument,
                      c.byref(settings._value))


# --- the pure helpers --------------------------------------------------------


def bloom_extract_channel(value: float, threshold: float) -> float:
    """What one channel contributes to bloom, above a threshold. Pure."""
    return _support.out_f32("cna_bloom_pass_extract_channel",
                            c.c_float(_support.real(value, "value")),
                            c.c_float(_support.real(threshold, "threshold")))


def bloom_iterations_for(quality: RenderQuality) -> int:
    """How many blur steps a quality preset asks bloom for. Pure."""
    return _support.out_i32("cna_bloom_pass_iterations_for_quality",
                            c.c_uint32(int(RenderQuality(quality))))


def fxaa_edge_threshold_for(quality: RenderQuality) -> float:
    """The edge threshold a quality preset asks FXAA for. Pure."""
    return _support.out_f32("cna_fxaa_pass_edge_threshold_for_quality",
                            c.c_uint32(int(RenderQuality(quality))))


def fxaa_fragment_glsl() -> str:
    """CNA's own FXAA fragment shader, for a caller writing their own pass."""
    return _support.copied_text("cna_fxaa_pass_copy_fragment_glsl", (), "FXAA GLSL")


def tonemap_channel(mode: TonemappingMode, value: float, exposure: float,
                    gamma: float) -> float:
    """One channel through the tonemap curve. Pure.

    The CPU twin of the shader, so a caller can predict what a tonemap pass will
    do to a colour rather than compare screenshots.
    """
    return _support.out_f32("cna_tonemap_pass_tonemap_channel",
                            c.c_uint32(int(TonemappingMode(mode))),
                            c.c_float(_support.real(value, "value")),
                            c.c_float(_support.real(exposure, "exposure")),
                            c.c_float(_support.real(gamma, "gamma")))


def lut_size_for_strip(width: int, height: int) -> int:
    """The table edge a strip texture of this shape encodes. Pure."""
    return _support.out_i32("cna_color_grade_pass_lut_size_for_strip",
                            c.c_int32(_support.checked(width, "int32", "width")),
                            c.c_int32(_support.checked(height, "int32", "height")))


def create_identity_lut(device: "GraphicsDevice", size: int) -> Texture2D:
    """A strip lookup table that changes nothing, for a caller to modify.

    The caller owns the texture and disposes it.
    """
    return Texture2D._from_handle(device, _support.out_handle(
        "cna_color_grade_pass_create_identity_lut", _device_handle(device),
        c.c_int32(_support.checked(size, "int32", "size"))))


def is_identity_scale(source_width: int, source_height: int, target_width: int,
                      target_height: int) -> bool:
    """Whether an upscale would change nothing, so it can be skipped. Pure."""
    return _support.out_bool(
        "cna_spatial_upscale_pass_is_identity_scale",
        c.c_int32(_support.checked(source_width, "int32", "source_width")),
        c.c_int32(_support.checked(source_height, "int32", "source_height")),
        c.c_int32(_support.checked(target_width, "int32", "target_width")),
        c.c_int32(_support.checked(target_height, "int32", "target_height")))


def encode_pq(nits: float) -> float:
    """A luminance in nits through the PQ transfer function. Pure."""
    return _support.out_f32("cna_hdr_display_output_encode_pq",
                            c.c_float(_support.real(nits, "nits")))


def decode_pq(encoded: float) -> float:
    """A PQ-encoded value back to nits. Pure, and the inverse of :func:`encode_pq`."""
    return _support.out_f32("cna_hdr_display_output_decode_pq",
                            c.c_float(_support.real(encoded, "encoded")))


def rec709_to_rec2020(color: Vector3) -> Vector3:
    """A linear Rec.709 colour in the wider Rec.2020 primaries. Pure."""
    native = _native_vector(color)
    value = _abi.CNA_Vector3()
    _support.call("cna_hdr_display_output_rec709_to_rec2020", c.byref(native),
                  c.byref(value))
    return _vector(value)


def roll_off(nits: float, peak_nits: float) -> float:
    """Compresses a luminance toward what a display can actually show. Pure."""
    return _support.out_f32("cna_hdr_display_output_roll_off",
                            c.c_float(_support.real(nits, "nits")),
                            c.c_float(_support.real(peak_nits, "peak_nits")))


def encode_for_display(space: DisplayColorSpace, scene_linear: Vector3,
                       paper_white_nits: float, peak_nits: float) -> Vector3:
    """A scene-linear colour encoded for one display. Pure.

    The whole HDR output path in one function, so a caller can check what a
    pixel becomes without drawing anything.
    """
    native = _native_vector(scene_linear)
    value = _abi.CNA_Vector3()
    _support.call("cna_hdr_display_output_encode",
                  c.c_uint32(int(DisplayColorSpace(space))), c.byref(native),
                  c.c_float(_support.real(paper_white_nits, "paper_white_nits")),
                  c.c_float(_support.real(peak_nits, "peak_nits")), c.byref(value))
    return _vector(value)
