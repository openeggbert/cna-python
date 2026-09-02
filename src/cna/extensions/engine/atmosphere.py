"""The screen-space effects that read the prepass, and the sky a frame sits in.

Ambient occlusion, reflections, motion blur, depth of field and contact shadows
all reconstruct world positions from the depth and normals the prepass wrote, so
they belong together; the sky, aerial perspective and the three kinds of fog are
here for the same reason, because they are what fills the space between the
camera and the geometry.

Every one of them is a
:class:`~cna.extensions.engine.postprocess.PostProcessPass` except the two that
draw a background rather than filter an image -- :class:`AtmosphericSky` and
:class:`Skybox` take a camera and a size and draw to whatever target is bound.

The pure helpers are the point
------------------------------

A screen-space effect is hard to check by looking at it: SSAO on a flat scene
looks like SSAO on a broken one. So CNA publishes the arithmetic each shader
runs -- :func:`circle_of_confusion_millimetres`, :func:`is_occluded`,
:func:`combine_visibility`, :func:`air_mass_for_distance`,
:func:`transmittance`, :func:`optical_depth`, :func:`sky_radiance` -- and those
are what the tests predict, because they can be predicted.
"""

from __future__ import annotations

import ctypes as c
from typing import TYPE_CHECKING

from Microsoft.Xna.Framework import Matrix, Vector2, Vector3

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .passes import _boolean, _device_handle, _float, _integer, _texture_handle
from .postprocess import PostProcessPass
from .values import RenderQuality, _native_matrix, _native_vector, _vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import GraphicsDevice, TextureCube

    from .shadows import ShadowMap

__all__ = [
    "SsaoPass",
    "SsrPass",
    "MotionBlurPass",
    "DepthOfFieldPass",
    "ContactShadowPass",
    "AerialPerspectivePass",
    "HeightFogPass",
    "LightShaftPass",
    "VolumetricFogPass",
    "AtmosphericSky",
    "Skybox",
    "ssao_sample_count_for",
    "ssao_occlusion_glsl",
    "circle_of_confusion_millimetres",
    "is_occluded",
    "combine_visibility",
    "contact_shadow_occlusion_glsl",
    "air_mass_for_distance",
    "transmittance",
    "optical_depth",
    "sky_radiance",
    "sky_model_glsl",
    "compute_skybox_view_ray",
    "SSR_MINIMUM_STEP_COUNT",
    "SSR_MAXIMUM_STEP_COUNT",
    "DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES",
    "VOLUMETRIC_FOG_SLICE_COUNT",
    "VOLUMETRIC_FOG_SLICE_RESOLUTION",
    "LIGHT_SHAFT_STEP_COUNT",
]

#: The bounds CNA clamps a reflection trace's step count into, whatever it is told.
SSR_MINIMUM_STEP_COUNT = _engine.CNA_SSR_PASS_MIN_STEP_COUNT_EXT
SSR_MAXIMUM_STEP_COUNT = _engine.CNA_SSR_PASS_MAX_STEP_COUNT_EXT
#: The sensor the depth-of-field maths assumes, which is what turns an f-number
#: into a blur radius at all.
DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES = (
    _engine.CNA_DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES_EXT)
#: The froxel grid volumetric fog marches through.
VOLUMETRIC_FOG_SLICE_COUNT = _engine.CNA_VOLUMETRIC_FOG_SLICE_COUNT_EXT
VOLUMETRIC_FOG_SLICE_RESOLUTION = _engine.CNA_VOLUMETRIC_FOG_SLICE_RESOLUTION_EXT
#: How many samples a light shaft takes along each ray.
LIGHT_SHAFT_STEP_COUNT = _engine.CNA_LIGHT_SHAFT_STEP_COUNT_EXT


def _vector3_property(getter: str, setter: str, doc: str):
    """One ``Vector3`` the object reads and writes straight through."""
    def read(self) -> Vector3:
        value = _abi.CNA_Vector3()
        _support.call(getter, self._handle.argument, c.byref(value))
        return _vector(value)

    def write(self, value: Vector3) -> None:
        native = _native_vector(value)
        _support.call(setter, self._handle.argument, c.byref(native))

    return property(read, write, doc=doc)


class _ScreenSpacePass(PostProcessPass):
    """A pass created by its own constructor and driven through the shared ones."""

    __slots__ = ()
    _CREATE: str = ""

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle(self._CREATE, _device_handle(device)),
            "cna_post_process_pass_destroy", type(self).__name__))
        self._effect = None


# --- the screen-space effects ------------------------------------------------


class SsaoPass(_ScreenSpacePass):
    """Darkens creases by sampling the prepass depth around each texel."""

    __slots__ = ()
    _CREATE = "cna_ssao_pass_create"

    radius = _float("cna_ssao_pass_get_radius", "cna_ssao_pass_set_radius",
                    "How far, in world units, a texel looks for occluders.")
    intensity = _float("cna_ssao_pass_get_intensity", "cna_ssao_pass_set_intensity",
                       "How dark a fully occluded texel becomes.")
    sample_count = _integer("cna_ssao_pass_get_sample_count",
                            "cna_ssao_pass_set_sample_count",
                            "How many points around each texel are sampled.")
    half_resolution = _boolean("cna_ssao_pass_get_half_resolution",
                               "cna_ssao_pass_set_half_resolution",
                               "Whether occlusion is computed at half size and upscaled.")

    def reset_targets(self) -> None:
        """Releases the pass's own intermediates."""
        _support.call("cna_ssao_pass_reset_targets", self._handle.argument)

    def kernel(self) -> tuple[Vector3, ...]:
        """The sample offsets the pass uses, as values.

        Exposed because a kernel is the one part of SSAO a caller can check
        without rendering: the points have to be inside the unit hemisphere and
        clustered toward its centre, and a kernel that is neither produces
        occlusion that looks plausible and is wrong.
        """
        # The two-call protocol, because the kernel's length is CNA's and is
        # not the sample count: asking for `sample_count` offsets answers
        # BUFFER_TOO_SMALL rather than truncating.
        offsets, written = _support.copied_values(
            _abi.CNA_Vector3, "cna_ssao_pass_copy_kernel", (self._handle.argument,))
        return tuple(_vector(offsets[index]) for index in range(written))


class SsrPass(_ScreenSpacePass):
    """Reflects the scene into itself by marching the prepass depth."""

    __slots__ = ()
    _CREATE = "cna_ssr_pass_create"

    max_distance = _float("cna_ssr_pass_get_max_distance",
                          "cna_ssr_pass_set_max_distance",
                          "How far, in world units, a reflection ray travels. "
                          "CNA ignores a value that is not positive rather than "
                          "refusing it, so read it back to see what it kept.")
    step_count = _integer("cna_ssr_pass_get_step_count", "cna_ssr_pass_set_step_count",
                          "How many steps the ray march takes. Stored as given; "
                          "the trace itself clamps into "
                          "SSR_MINIMUM_STEP_COUNT..SSR_MAXIMUM_STEP_COUNT when it "
                          "runs, so reading this back does not show the clamp.")
    thickness = _float("cna_ssr_pass_get_thickness", "cna_ssr_pass_set_thickness",
                       "How deep a surface is assumed to be when testing a hit.")
    depth_bias = _float("cna_ssr_pass_get_depth_bias", "cna_ssr_pass_set_depth_bias",
                        "The offset that stops a surface reflecting itself.")
    roughness_blur = _float("cna_ssr_pass_get_roughness_blur",
                            "cna_ssr_pass_set_roughness_blur",
                            "How much rougher surfaces blur their reflection. "
                            "Clamped to 0..0.25 by CNA; read it back to see what "
                            "a larger value became.")
    edge_fade = _float("cna_ssr_pass_get_edge_fade", "cna_ssr_pass_set_edge_fade",
                       "How far from the screen edge a reflection fades out. "
                       "Clamped to 0..0.5 by CNA.")
    intensity = _float("cna_ssr_pass_get_intensity", "cna_ssr_pass_set_intensity",
                       "How strongly the reflection is composited back.")


class MotionBlurPass(_ScreenSpacePass):
    """Smears along the velocity the prepass wrote."""

    __slots__ = ()
    _CREATE = "cna_motion_blur_pass_create"

    strength = _float("cna_motion_blur_pass_get_strength",
                      "cna_motion_blur_pass_set_strength",
                      "How far along its velocity a texel is smeared.")
    max_distance = _float("cna_motion_blur_pass_get_max_distance",
                          "cna_motion_blur_pass_set_max_distance",
                          "The furthest a smear reaches, in screen units.")


class DepthOfFieldPass(_ScreenSpacePass):
    """Blurs by how far each texel is from the focus plane.

    The four settings are a camera's: where it is focused, its focal length, its
    f-number and a ceiling on the blur. :func:`circle_of_confusion_millimetres`
    is the lens equation they feed, so a caller can work out what a setting will
    do before applying it.
    """

    __slots__ = ()
    _CREATE = "cna_depth_of_field_pass_create"

    focus_distance = _float("cna_depth_of_field_pass_get_focus_distance",
                            "cna_depth_of_field_pass_set_focus_distance",
                            "How far away the plane in focus is, in world units. "
                            "CNA ignores a value that is not positive rather than "
                            "refusing it.")
    focal_length = _float("cna_depth_of_field_pass_get_focal_length",
                          "cna_depth_of_field_pass_set_focal_length",
                          "The lens's focal length in millimetres.")
    f_number = _float("cna_depth_of_field_pass_get_f_number",
                      "cna_depth_of_field_pass_set_f_number",
                      "The aperture as an f-number; smaller is a shallower focus.")
    max_radius = _float("cna_depth_of_field_pass_get_max_radius",
                        "cna_depth_of_field_pass_set_max_radius",
                        "The largest blur radius, as a fraction of the screen. "
                        "Clamped to 0..0.25 by CNA, so it is a fraction rather "
                        "than a pixel count.")


class ContactShadowPass(_ScreenSpacePass):
    """Short shadows a shadow map is too coarse to resolve.

    A shadow map at any resolution loses contact between an object and what it
    is standing on; this marches the prepass depth toward the light for a few
    steps to put it back.
    """

    __slots__ = ()
    _CREATE = "cna_contact_shadow_pass_create"

    light_direction = _vector3_property(
        "cna_contact_shadow_pass_get_light_direction",
        "cna_contact_shadow_pass_set_light_direction",
        "The direction the light travels, which the ray marches against.")
    max_distance = _float("cna_contact_shadow_pass_get_max_distance",
                          "cna_contact_shadow_pass_set_max_distance",
                          "How far the ray marches, in world units.")
    step_count = _integer("cna_contact_shadow_pass_get_step_count",
                          "cna_contact_shadow_pass_set_step_count",
                          "How many samples the march takes.")
    thickness = _float("cna_contact_shadow_pass_get_thickness",
                       "cna_contact_shadow_pass_set_thickness",
                       "How deep a surface is assumed to be when testing a hit.")
    intensity = _float("cna_contact_shadow_pass_get_intensity",
                       "cna_contact_shadow_pass_set_intensity",
                       "How dark a fully occluded texel becomes.")
    bias = _float("cna_contact_shadow_pass_get_bias", "cna_contact_shadow_pass_set_bias",
                  "The offset that stops a surface shadowing itself.")

    @property
    def fallback_reason(self) -> str:
        """Why the pass fell back, or the empty string when it did not."""
        return _support.copied_text("cna_contact_shadow_pass_copy_fallback_reason",
                                    (self._handle.argument,), "fallback reason")


# --- the atmosphere ----------------------------------------------------------


class AerialPerspectivePass(_ScreenSpacePass):
    """Tints distant geometry the colour of the air in front of it."""

    __slots__ = ()
    _CREATE = "cna_aerial_perspective_pass_create"

    sun_direction = _vector3_property(
        "cna_aerial_perspective_pass_get_sun_direction",
        "cna_aerial_perspective_pass_set_sun_direction",
        "Where the sun is, which decides which way the haze is scattered.")
    turbidity = _float("cna_aerial_perspective_pass_get_turbidity",
                       "cna_aerial_perspective_pass_set_turbidity",
                       "How hazy the air is; higher is thicker and yellower.")
    intensity = _float("cna_aerial_perspective_pass_get_intensity",
                       "cna_aerial_perspective_pass_set_intensity",
                       "How strongly the haze is composited back.")
    scale_height = _float("cna_aerial_perspective_pass_get_scale_height",
                          "cna_aerial_perspective_pass_set_scale_height",
                          "The height over which the air thins, in world units.")

    @property
    def fallback_reason(self) -> str:
        """Why the pass fell back, or the empty string when it did not."""
        return _support.copied_text("cna_aerial_perspective_pass_copy_fallback_reason",
                                    (self._handle.argument,), "fallback reason")


class HeightFogPass(_ScreenSpacePass):
    """Fog that thins with height, as real fog does."""

    __slots__ = ()
    _CREATE = "cna_height_fog_pass_create"

    color = _vector3_property("cna_height_fog_pass_get_color",
                              "cna_height_fog_pass_set_color",
                              "The fog's linear RGB colour.")
    density = _float("cna_height_fog_pass_get_density", "cna_height_fog_pass_set_density",
                     "How thick the fog is at its base height.")
    falloff = _float("cna_height_fog_pass_get_falloff", "cna_height_fog_pass_set_falloff",
                     "How quickly it thins with height; zero is uniform fog.")
    base_height = _float("cna_height_fog_pass_get_base_height",
                         "cna_height_fog_pass_set_base_height",
                         "The world height the density is quoted at.")


class LightShaftPass(_ScreenSpacePass):
    """Radial shafts from a bright point on screen."""

    __slots__ = ()
    _CREATE = "cna_light_shaft_pass_create"

    threshold = _float("cna_light_shaft_pass_get_threshold",
                       "cna_light_shaft_pass_set_threshold",
                       "How bright a texel has to be to start a shaft.")
    intensity = _float("cna_light_shaft_pass_get_intensity",
                       "cna_light_shaft_pass_set_intensity",
                       "How strongly the shafts are composited back.")
    decay = _float("cna_light_shaft_pass_get_decay", "cna_light_shaft_pass_set_decay",
                   "How quickly a shaft fades along its length.")

    @property
    def light_screen_position(self) -> Vector2:
        """Where the light is on screen, in normalised coordinates."""
        value = _abi.CNA_Vector2()
        _support.call("cna_light_shaft_pass_get_light_screen_position",
                      self._handle.argument, c.byref(value))
        return Vector2(float(value.x), float(value.y))

    @light_screen_position.setter
    def light_screen_position(self, value: Vector2) -> None:
        if not isinstance(value, Vector2):
            raise TypeError("light_screen_position must be a Vector2")
        native = _abi.CNA_Vector2(float(value.X), float(value.Y))
        _support.call("cna_light_shaft_pass_set_light_screen_position",
                      self._handle.argument, c.byref(native))


class VolumetricFogPass(_ScreenSpacePass):
    """Fog lit by one shadowed light, marched through a froxel grid."""

    __slots__ = ("_shadow_map",)
    _CREATE = "cna_volumetric_fog_pass_create"

    def __init__(self, device: "GraphicsDevice") -> None:
        super().__init__(device)
        self._shadow_map = None

    density = _float("cna_volumetric_fog_pass_get_density",
                     "cna_volumetric_fog_pass_set_density",
                     "How much light the fog scatters per unit distance.")
    anisotropy = _float("cna_volumetric_fog_pass_get_anisotropy",
                        "cna_volumetric_fog_pass_set_anisotropy",
                        "How forward-scattering the fog is; zero is isotropic.")
    range_ = _float("cna_volumetric_fog_pass_get_range",
                    "cna_volumetric_fog_pass_set_range",
                    "How far from the camera the froxel grid reaches.")

    def set_light(self, shadow_map: "ShadowMap | None", light_direction: Vector3,
                  light_color: Vector3) -> None:
        """The light the fog is lit by, and the shadow that shapes the shafts.

        The shadow map is borrowed for every later apply, so the pass keeps it
        alive; passing ``None`` lights the fog with no shadow at all.
        """
        direction = _native_vector(light_direction)
        colour = _native_vector(light_color)
        handle = c.c_uint64(0 if shadow_map is None
                            else shadow_map._handle.value)
        _support.call("cna_volumetric_fog_pass_set_light", self._handle.argument,
                      handle, c.byref(direction), c.byref(colour))
        self._shadow_map = shadow_map


class AtmosphericSky:
    """An analytic sky: sun direction, turbidity, intensity, drawn as a background.

    Not a post-process pass. It draws over whatever target is bound rather than
    filtering a source, which is why it takes a camera and a size instead of a
    frame context.
    """

    __slots__ = ("_handle",)

    def __init__(self, device: "GraphicsDevice") -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_atmospheric_sky_create", _device_handle(device)),
            "cna_atmospheric_sky_destroy", "atmospheric sky")

    sun_direction = _vector3_property("cna_atmospheric_sky_get_sun_direction",
                                      "cna_atmospheric_sky_set_sun_direction",
                                      "Which way the sun is; a unit vector.")
    turbidity = _float("cna_atmospheric_sky_get_turbidity",
                       "cna_atmospheric_sky_set_turbidity",
                       "How hazy the air is; higher is thicker and yellower.")
    intensity = _float("cna_atmospheric_sky_get_intensity",
                       "cna_atmospheric_sky_set_intensity",
                       "A scalar multiplier on the whole sky.")

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can compile and link the sky shader."""
        return _support.out_bool("cna_atmospheric_sky_is_supported",
                                 self._handle.argument)

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the sky. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self) -> "AtmosphericSky":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def draw(self, view: Matrix, projection: Matrix, width: int, height: int) -> None:
        """Draws the sky over whatever target is bound."""
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_atmospheric_sky_draw", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection),
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))


class Skybox:
    """A cube map drawn as the background, with a yaw, an intensity and a tint.

    The environment cube is **borrowed**: it must outlive the skybox, and the
    skybox keeps a reference to it for exactly that reason. CNA also offers a
    constructor that takes ownership of the cube; this binding does not use it,
    for the same reason it does not use the other ownership transfers -- Python's
    reference already guarantees the lifetime, and consuming the handle would
    leave the caller's ``TextureCube`` facade unusable.
    """

    __slots__ = ("_handle", "_environment")

    def __init__(self, device: "GraphicsDevice",
                 environment: "TextureCube | None" = None) -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_skybox_create", _device_handle(device),
                                _texture_handle(environment, "environment")),
            "cna_skybox_destroy", "skybox")
        self._environment = environment

    yaw = _float("cna_skybox_get_yaw", "cna_skybox_set_yaw",
                 "How far the cube is turned about the vertical axis, in radians.")
    intensity = _float("cna_skybox_get_intensity", "cna_skybox_set_intensity",
                       "A scalar multiplier on the cube's own colour.")
    tint = _vector3_property("cna_skybox_get_tint", "cna_skybox_set_tint",
                             "The linear RGB the cube's colour is multiplied by.")

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can compile and link the skybox shader."""
        return _support.out_bool("cna_skybox_is_supported", self._handle.argument)

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the skybox. The environment cube stays the caller's."""
        self._handle.close()
        self._environment = None

    def __enter__(self) -> "Skybox":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def environment(self) -> "TextureCube | None":
        """The cube the skybox draws, or ``None``.

        The object handed back is the one that was assigned. CNA answers with a
        **new** counted handle each time -- measured, three consecutive reads
        gave three handles -- so the view is released here and only the caller's
        own object is returned.
        """
        expected = (0 if self._environment is None
                    else int(self._environment._require_handle()))
        present = _support.borrowed_view("cna_skybox_get_environment",
                                         (self._handle.argument,), expected,
                                         "cna_texturecube_destroy")
        return self._environment if present else None

    @environment.setter
    def environment(self, value: "TextureCube | None") -> None:
        _support.call("cna_skybox_set_environment", self._handle.argument,
                      _texture_handle(value, "environment"))
        self._environment = value

    def draw(self, view: Matrix, projection: Matrix, width: int, height: int) -> None:
        """Draws the cube over whatever target is bound."""
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_skybox_draw", self._handle.argument, c.byref(native_view),
                      c.byref(native_projection),
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))


# --- the pure helpers --------------------------------------------------------


def ssao_sample_count_for(quality: RenderQuality) -> int:
    """How many samples a quality preset asks SSAO for. Pure."""
    return _support.out_i32("cna_ssao_pass_sample_count_for_quality",
                            c.c_uint32(int(RenderQuality(quality))))


def ssao_occlusion_glsl(packed: bool) -> str:
    """CNA's own occlusion GLSL, for the packed and unpacked depth encodings."""
    return _support.copied_text("cna_ssao_pass_copy_occlusion_glsl",
                                (c.c_uint8(1 if packed else 0),), "SSAO GLSL")


def circle_of_confusion_millimetres(depth: float, focus_distance: float,
                                    focal_length: float, f_number: float) -> float:
    """The lens equation depth of field is built on. Pure.

    How large a point at ``depth`` is smeared to, in millimetres on the sensor.
    Zero at the focus distance by definition, and it is what makes a depth of
    field predictable rather than a look.
    """
    return _support.out_f32(
        "cna_depth_of_field_pass_circle_of_confusion_millimetres",
        c.c_float(_support.real(depth, "depth")),
        c.c_float(_support.real(focus_distance, "focus_distance")),
        c.c_float(_support.real(focal_length, "focal_length")),
        c.c_float(_support.real(f_number, "f_number")))


def is_occluded(ray_view_depth: float, scene_view_depth: float, bias: float,
                thickness: float) -> bool:
    """Whether a contact-shadow ray sample hit something. Pure.

    The same test the shader runs at every step: the ray is behind the scene by
    more than the bias, but not by more than the surface is thick -- because a
    ray that passed far behind a surface went past it rather than into it.
    """
    return _support.out_bool(
        "cna_contact_shadow_pass_is_occluded",
        c.c_float(_support.real(ray_view_depth, "ray_view_depth")),
        c.c_float(_support.real(scene_view_depth, "scene_view_depth")),
        c.c_float(_support.real(bias, "bias")),
        c.c_float(_support.real(thickness, "thickness")))


def combine_visibility(shadow_map_visibility: float,
                       contact_visibility: float) -> float:
    """How a shadow map's visibility and a contact shadow's combine. Pure.

    They are not added: two shadows over one point still leave it in shadow
    once, and this is CNA's own rule for saying so.
    """
    return _support.out_f32(
        "cna_contact_shadow_pass_combine_visibility",
        c.c_float(_support.real(shadow_map_visibility, "shadow_map_visibility")),
        c.c_float(_support.real(contact_visibility, "contact_visibility")))


def contact_shadow_occlusion_glsl() -> str:
    """CNA's own occlusion test in GLSL, the twin of :func:`is_occluded`."""
    return _support.copied_text("cna_contact_shadow_pass_copy_occlusion_test_glsl",
                                (), "contact shadow GLSL")


def air_mass_for_distance(view_direction: Vector3, distance: float,
                          scale_height: float) -> float:
    """How much air a ray passes through. Pure.

    A ray along the horizon crosses more atmosphere than one straight up, which
    is why the direction is an argument and not just the distance.
    """
    native = _native_vector(view_direction)
    return _support.out_f32("cna_aerial_perspective_pass_air_mass_for_distance",
                            c.byref(native),
                            c.c_float(_support.real(distance, "distance")),
                            c.c_float(_support.real(scale_height, "scale_height")))


def transmittance(turbidity: float, air_mass: float) -> Vector3:
    """How much of each channel survives that much air. Pure.

    Blue scatters most, so the transmitted light reddens with distance -- which
    is why the answer is three numbers rather than one.
    """
    value = _abi.CNA_Vector3()
    _support.call("cna_aerial_perspective_pass_transmittance",
                  c.c_float(_support.real(turbidity, "turbidity")),
                  c.c_float(_support.real(air_mass, "air_mass")), c.byref(value))
    return _vector(value)


def optical_depth(camera_height: float, ray_height_step: float, distance: float,
                  density: float, falloff: float, base_height: float) -> float:
    """How much height fog a ray accumulates. Pure.

    The closed form of the integral through an exponentially thinning medium,
    which is what makes height fog cost the same whatever the distance.
    """
    return _support.out_f32(
        "cna_height_fog_pass_optical_depth",
        c.c_float(_support.real(camera_height, "camera_height")),
        c.c_float(_support.real(ray_height_step, "ray_height_step")),
        c.c_float(_support.real(distance, "distance")),
        c.c_float(_support.real(density, "density")),
        c.c_float(_support.real(falloff, "falloff")),
        c.c_float(_support.real(base_height, "base_height")))


def sky_radiance(view_direction: Vector3, sun_direction: Vector3,
                 turbidity: float) -> Vector3:
    """What the analytic sky is, in one direction. Pure.

    The model the sky shader evaluates per pixel, available per direction so a
    caller can check the sky against arithmetic rather than a screenshot.
    """
    view = _native_vector(view_direction)
    sun = _native_vector(sun_direction)
    value = _abi.CNA_Vector3()
    _support.call("cna_atmospheric_sky_radiance", c.byref(view), c.byref(sun),
                  c.c_float(_support.real(turbidity, "turbidity")), c.byref(value))
    return _vector(value)


def sky_model_glsl() -> str:
    """CNA's own sky model in GLSL, the twin of :func:`sky_radiance`."""
    return _support.copied_text("cna_atmospheric_sky_copy_model_glsl", (),
                                "sky model GLSL")


def compute_skybox_view_ray(view: Matrix, projection: Matrix, ndc_x: float,
                            ndc_y: float, yaw: float) -> Vector3:
    """The direction one screen point looks in, with the skybox's yaw. Pure."""
    native_view, native_projection = _native_matrix(view), _native_matrix(projection)
    value = _abi.CNA_Vector3()
    _support.call("cna_skybox_compute_view_ray", c.byref(native_view),
                  c.byref(native_projection),
                  c.c_float(_support.real(ndc_x, "ndc_x")),
                  c.c_float(_support.real(ndc_y, "ndc_y")),
                  c.c_float(_support.real(yaw, "yaw")), c.byref(value))
    return _vector(value)
