"""What a frame draws besides opaque geometry.

Particles, projected decals, the depth/normal prepass every screen-space effect
reads, and both ways of resolving transparency. They are one module because a
frame uses them together: the prepass produces the depth a decal projects onto
and a soft particle fades against, and transparency is what happens after both.

Pure helpers, and why they are here
-----------------------------------

Several of these routes are pure functions with no object behind them --
:func:`pack_depth`, :func:`transparency_weight`, :func:`particle_random`,
:meth:`ParticleSystem.step`, :func:`sort_key`. CNA publishes them beside the
GLSL that computes the same thing on the GPU, so a caller writing their own
shader can check the two against each other rather than reimplementing a
formula from a paper. That is also what makes them testable without a
rasterizer.

Callbacks
---------

:meth:`TransparentDrawList.submit` is the one place in this family where CNA
calls back into Python. The callable is rooted by the list for as long as CNA
can invoke it, a Python exception is caught and re-raised after the native call
returns rather than unwinding through C, and clearing or closing the list drops
the roots. Nothing relies on the caller keeping a reference.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Callable

from Microsoft.Xna.Framework import Color, Matrix, Vector3, Vector4
from Microsoft.Xna.Framework.Graphics import RenderTarget2D

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .values import _native_matrix, _native_vector, _vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework import BoundingBox
    from Microsoft.Xna.Framework.Graphics import Effect, GraphicsDevice, Texture2D

__all__ = [
    "DepthEncoding",
    "ParticleEmitterSettings",
    "Particle",
    "ParticleSystem",
    "particle_random",
    "particle_lookup_glsl",
    "DecalPass",
    "is_inside_decal_box",
    "DepthNormalPrepass",
    "uses_packed_depth",
    "pack_depth",
    "unpack_depth",
    "has_velocity",
    "decode_velocity",
    "depth_decode_glsl",
    "velocity_decode_glsl",
    "TransparentDrawList",
    "sort_key",
    "camera_position_of",
    "WeightedBlendedTransparency",
    "transparency_weight",
    "transparency_accumulation_glsl",
    "PARTICLE_SYSTEM_DEFAULT_CAPACITY",
    "PARTICLE_STORAGE_BINDING",
]

#: How many particles a system holds when no capacity is given.
PARTICLE_SYSTEM_DEFAULT_CAPACITY = _engine.CNA_PARTICLE_SYSTEM_DEFAULT_CAPACITY
#: The storage-buffer binding a compute particle system writes through.
PARTICLE_STORAGE_BINDING = _engine.CNA_PARTICLE_BINDING


class DepthEncoding(IntEnum):
    """How the prepass stores linear depth.

    ``HalfFloat`` is documented as defeating this layer's own screen-space
    effects, which is why it is a choice rather than a default: ``Automatic``
    lets the prepass pick what the renderer can actually read back.
    """

    Automatic = _engine.CNA_DEPTH_ENCODING_AUTOMATIC
    Packed = _engine.CNA_DEPTH_ENCODING_PACKED
    HalfFloat = _engine.CNA_DEPTH_ENCODING_HALF_FLOAT


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


def _bounds(value: "BoundingBox") -> _engine.CNA_BoundingBox:
    if not hasattr(value, "Min") or not hasattr(value, "Max"):
        raise TypeError("bounds must be a Microsoft.Xna.Framework.BoundingBox")
    native = _engine.CNA_BoundingBox()
    native.min = _native_vector(value.Min)
    native.max = _native_vector(value.Max)
    return native


def _vector4(value: _abi.CNA_Vector4) -> Vector4:
    return Vector4(float(value.x), float(value.y), float(value.z), float(value.w))


def _native_vector4(value: Vector4) -> _abi.CNA_Vector4:
    if not isinstance(value, Vector4):
        raise TypeError("expected a Microsoft.Xna.Framework.Vector4")
    return _abi.CNA_Vector4(float(value.X), float(value.Y), float(value.Z),
                            float(value.W))


def _colour(value: Color) -> _abi.CNA_Color:
    """A ``Color`` as CNA's own byte quadruple, for the two routes that take one."""
    if not isinstance(value, Color):
        raise TypeError("expected a Microsoft.Xna.Framework.Color")
    return _abi.CNA_Color(int(value.R), int(value.G), int(value.B), int(value.A))


class _EngineObject:
    """Common lifetime for an owned engine handle and its counted views."""

    __slots__ = ("_handle", "_device", "_views", "_retained")

    _DESTROY: str = ""

    def _attach(self, handle: int, device: "GraphicsDevice | None" = None) -> None:
        self._handle = _support.NativeHandle(handle, self._DESTROY, type(self).__name__)
        self._device = device
        self._views: dict[str, object] = {}
        self._retained: list[object] = []

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Disposes every view handed out, then releases the object."""
        if self._handle.closed:
            return
        for view in reversed(list(self._views.values())):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        self._handle.close()
        self._retained.clear()

    def __enter__(self):
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def _view(self, key: str, route: str, factory):
        existing = self._views.get(key)
        if existing is not None and not getattr(existing, "IsDisposed", False):
            return existing
        handle = _support.out_handle(route, self._handle.argument)
        if handle == 0:
            return None
        view = factory(handle)
        self._views[key] = view
        return view

    def _render_target_view(self, key: str, route: str):
        return self._view(key, route,
                          lambda handle: RenderTarget2D._view_of(self._device, handle))

    def _effect_view(self, key: str, route: str):
        from Microsoft.Xna.Framework.Graphics import Effect

        def build(handle: int):
            effect = Effect.__new__(Effect)
            effect._initialize_native(self._device, handle)
            return effect

        return self._view(key, route, build)


# --- particles ---------------------------------------------------------------


@dataclass(frozen=True)
class ParticleEmitterSettings:
    """Everything a particle system emits by.

    Angles are radians, times are seconds, and the two ``*_variance`` fields are
    fractions: a speed variance of 0.25 spreads speed over plus or minus a
    quarter of :attr:`speed`. The two colours are linear RGBA quadruples rather
    than byte ``Color`` values, which is what CNA stores and what a particle is
    tinted with in the shader.
    """

    position: Vector3
    direction: Vector3
    gravity: Vector3
    start_color: Vector4
    end_color: Vector4
    cone_angle: float
    speed: float
    speed_variance: float
    lifetime: float
    lifetime_variance: float
    drag: float
    emission_rate: float
    start_size: float
    end_size: float

    @classmethod
    def default(cls) -> "ParticleEmitterSettings":
        """CNA's own canonical defaults, read rather than transcribed."""
        value = _engine.CNA_ParticleEmitterSettings()
        _support.call("cna_particle_emitter_settings_init", c.byref(value))
        return cls._from_native(value)

    @classmethod
    def _from_native(cls, value) -> "ParticleEmitterSettings":
        return cls(_vector(value.position), _vector(value.direction),
                   _vector(value.gravity), _vector4(value.start_color),
                   _vector4(value.end_color), float(value.cone_angle),
                   float(value.speed), float(value.speed_variance),
                   float(value.lifetime), float(value.lifetime_variance),
                   float(value.drag), float(value.emission_rate),
                   float(value.start_size), float(value.end_size))

    def _native(self) -> _engine.CNA_ParticleEmitterSettings:
        value = _support.in_struct(_engine.CNA_ParticleEmitterSettings, 1)
        value.position = _native_vector(self.position)
        value.direction = _native_vector(self.direction)
        value.gravity = _native_vector(self.gravity)
        value.start_color = _native_vector4(self.start_color)
        value.end_color = _native_vector4(self.end_color)
        value.cone_angle = _support.real(self.cone_angle, "cone_angle")
        value.speed = _support.real(self.speed, "speed")
        value.speed_variance = _support.real(self.speed_variance, "speed_variance")
        value.lifetime = _support.real(self.lifetime, "lifetime")
        value.lifetime_variance = _support.real(self.lifetime_variance,
                                                "lifetime_variance")
        value.drag = _support.real(self.drag, "drag")
        value.emission_rate = _support.real(self.emission_rate, "emission_rate")
        value.start_size = _support.real(self.start_size, "start_size")
        value.end_size = _support.real(self.end_size, "end_size")
        return value


@dataclass(frozen=True)
class Particle:
    """One particle: where it is, where it is going, and how old it is.

    ``state`` packs age, lifetime, a spare and a generation counter, in that
    order; the generation is what makes a respawned particle draw a different
    random direction from the one it had before.
    """

    position: Vector4
    velocity: Vector4
    state: Vector4

    @classmethod
    def default(cls) -> "Particle":
        """CNA's own canonical initial particle, read rather than transcribed."""
        value = _engine.CNA_Particle()
        _support.call("cna_particle_init", c.byref(value))
        return cls._from_native(value)

    @classmethod
    def _from_native(cls, value) -> "Particle":
        return cls(_vector4(value.position), _vector4(value.velocity),
                   _vector4(value.state))

    def _native(self) -> _engine.CNA_Particle:
        value = _engine.CNA_Particle()
        value.position = _native_vector4(self.position)
        value.velocity = _native_vector4(self.velocity)
        value.state = _native_vector4(self.state)
        return value

    @property
    def age(self) -> float:
        """Seconds since this particle was last respawned."""
        return float(self.state.X)

    @property
    def lifetime(self) -> float:
        """Seconds this particle lives before respawning."""
        return float(self.state.Y)

    @property
    def generation(self) -> float:
        """How many times this slot has respawned; it seeds the random draw."""
        return float(self.state.W)


def particle_random(seed: int) -> float:
    """CNA's own hash-based random draw for one seed, in ``[0, 1)``.

    Deterministic and stateless: the same seed always gives the same number,
    which is what lets a particle system be reproduced rather than merely
    sampled.
    """
    return _support.out_f32("cna_particle_system_random",
                            c.c_uint32(_support.checked(seed, "uint32", "seed")))


def particle_lookup_glsl() -> str:
    """The GLSL declaration a custom shader reads the particle buffer with."""
    return _support.copied_text("cna_particle_system_copy_particle_lookup_glsl", (),
                                "particle lookup GLSL")


class ParticleSystem(_EngineObject):
    """A pool of particles, simulated on the GPU where it can be and on the CPU where not.

    Which one it uses is CNA's decision and :attr:`uses_compute` reports it;
    :attr:`simulation_on_cpu` forces the CPU path, which is what makes the
    simulation inspectable through :meth:`particles` on any renderer.
    """

    __slots__ = ()
    _DESTROY = "cna_particle_system_destroy"

    def __init__(self, device: "GraphicsDevice", capacity: int | None = None) -> None:
        if capacity is None:
            handle = _support.out_handle("cna_particle_system_create",
                                         _device_handle(device))
        else:
            handle = _support.out_handle(
                "cna_particle_system_create_with_capacity", _device_handle(device),
                c.c_int32(_support.checked(capacity, "int32", "capacity")))
        self._attach(handle, device)

    @property
    def capacity(self) -> int:
        """How many particles the pool holds."""
        return _support.out_i32("cna_particle_system_get_capacity",
                                self._handle.argument)

    @property
    def active_count(self) -> int:
        """How many particles are alive right now."""
        return _support.out_i32("cna_particle_system_get_active_count",
                                self._handle.argument)

    @property
    def settings(self) -> ParticleEmitterSettings:
        """What the system emits by."""
        value = _support.out_struct(_engine.CNA_ParticleEmitterSettings, 1,
                                    "cna_particle_system_get_settings",
                                    self._handle.argument)
        return ParticleEmitterSettings._from_native(value)

    @settings.setter
    def settings(self, value: ParticleEmitterSettings) -> None:
        if not isinstance(value, ParticleEmitterSettings):
            raise TypeError("settings must be a ParticleEmitterSettings")
        native = value._native()
        _support.call("cna_particle_system_set_settings", self._handle.argument,
                      c.byref(native))

    @property
    def uses_compute(self) -> bool:
        """Whether the simulation runs on the GPU."""
        return _support.out_bool("cna_particle_system_uses_compute",
                                 self._handle.argument)

    @property
    def unsupported_reason(self) -> str:
        """Why the GPU path is unavailable, or the empty string when it is not."""
        return _support.copied_text("cna_particle_system_copy_unsupported_reason",
                                    (self._handle.argument,), "unsupported reason")

    @property
    def simulation_on_cpu(self) -> bool:
        """Whether the CPU path has been forced."""
        return _support.out_bool("cna_particle_system_is_simulation_on_cpu_ext",
                                 self._handle.argument)

    @simulation_on_cpu.setter
    def simulation_on_cpu(self, value: bool) -> None:
        _support.call("cna_particle_system_set_simulation_on_cpu_ext",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    @property
    def emission_rate_clamped(self) -> bool:
        """Whether the emitter is asking for more particles than the pool holds."""
        return _support.out_bool("cna_particle_system_is_emission_rate_clamped",
                                 self._handle.argument)

    @property
    def softness(self) -> float:
        """How far from a surface a particle starts fading, in world units."""
        return _support.out_f32("cna_particle_system_get_softness_ext",
                                self._handle.argument)

    @softness.setter
    def softness(self, value: float) -> None:
        _support.call("cna_particle_system_set_softness_ext", self._handle.argument,
                      c.c_float(_support.real(value, "softness")))

    def set_depth_input(self, depth: "Texture2D | None", far_plane: float) -> None:
        """Gives the system the depth it fades against, for soft particles.

        The texture is borrowed for every later draw, so the system keeps it
        alive; passing ``None`` clears it and turns the fade off.
        """
        _support.call("cna_particle_system_set_depth_input_ext", self._handle.argument,
                      _optional_texture(depth, "depth"),
                      c.c_float(_support.real(far_plane, "far_plane")))
        self._retained = [depth] if depth is not None else []

    def reset(self) -> None:
        """Kills every particle and restarts emission."""
        _support.call("cna_particle_system_reset", self._handle.argument)

    def update(self, elapsed_seconds: float) -> None:
        """Advances the simulation."""
        _support.call("cna_particle_system_update", self._handle.argument,
                      c.c_float(_support.real(elapsed_seconds, "elapsed_seconds")))

    def draw(self, view: Matrix, projection: Matrix,
             texture: "Texture2D | None" = None) -> None:
        """Draws every live particle as a camera-facing quad."""
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_particle_system_draw", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection),
                      _optional_texture(texture, "texture"))

    def particles(self) -> tuple[Particle, ...]:
        """Every particle the pool holds, as values.

        Copies rather than views: a particle is three vectors, and handing out
        something that aliased the simulation would be a window into memory the
        next update rewrites.
        """
        capacity = self.capacity
        if capacity == 0:
            return ()
        destination = (_engine.CNA_Particle * capacity)()
        written = c.c_uint64()
        _support.call("cna_particle_system_copy_particles_ext", self._handle.argument,
                      destination, c.c_uint64(capacity), c.byref(written))
        return tuple(Particle._from_native(destination[index])
                     for index in range(int(written.value)))

    @staticmethod
    def step(particle: Particle, index: int, settings: ParticleEmitterSettings,
             elapsed_seconds: float) -> Particle:
        """Advances one particle by one step, exactly as the simulation does.

        Pure, and the same function the CPU path runs per particle: gravity,
        drag, integration, and a respawn with a fresh random direction when the
        particle outlives its lifetime. Exposed because a caller can then
        predict what a system will do rather than watch it.
        """
        if not isinstance(particle, Particle):
            raise TypeError("particle must be a Particle")
        if not isinstance(settings, ParticleEmitterSettings):
            raise TypeError("settings must be a ParticleEmitterSettings")
        native = particle._native()
        native_settings = settings._native()
        _support.call("cna_particle_system_step", c.byref(native),
                      c.c_int32(_support.checked(index, "int32", "index")),
                      c.byref(native_settings),
                      c.c_float(_support.real(elapsed_seconds, "elapsed_seconds")))
        return Particle._from_native(native)


# --- decals ------------------------------------------------------------------


def is_inside_decal_box(decal_local_position: Vector3) -> bool:
    """Whether a point in a decal's own space falls inside its unit box.

    Pure. The box is the unit cube centred on the origin, so a decal's world
    transform is what places and sizes it.
    """
    native = _native_vector(decal_local_position)
    return _support.out_bool("cna_decal_pass_is_inside_decal_box", c.byref(native))


class DecalPass(_EngineObject):
    """Projects a texture onto whatever the prepass already rendered.

    A decal needs depth to project onto and normals to reject surfaces it would
    smear across, so :meth:`set_prepass_inputs` comes before any draw.
    """

    __slots__ = ()
    _DESTROY = "cna_decal_pass_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.out_handle("cna_decal_pass_create",
                                         _device_handle(device)), device)

    @property
    def opacity(self) -> float:
        """How strongly the decal covers what is under it."""
        return _support.out_f32("cna_decal_pass_get_opacity", self._handle.argument)

    @opacity.setter
    def opacity(self, value: float) -> None:
        _support.call("cna_decal_pass_set_opacity", self._handle.argument,
                      c.c_float(_support.real(value, "opacity")))

    @property
    def tint(self) -> Vector3:
        """The linear RGB the decal's own colour is multiplied by."""
        value = _abi.CNA_Vector3()
        _support.call("cna_decal_pass_get_tint", self._handle.argument, c.byref(value))
        return _vector(value)

    @tint.setter
    def tint(self, value: Vector3) -> None:
        native = _native_vector(value)
        _support.call("cna_decal_pass_set_tint", self._handle.argument, c.byref(native))

    @property
    def max_slope_angle(self) -> float:
        """The steepest surface a decal will land on, in radians.

        Past it the decal is rejected rather than stretched along a wall, which
        is what stops a projected decal smearing.
        """
        return _support.out_f32("cna_decal_pass_get_max_slope_angle",
                                self._handle.argument)

    @max_slope_angle.setter
    def max_slope_angle(self, value: float) -> None:
        _support.call("cna_decal_pass_set_max_slope_angle", self._handle.argument,
                      c.c_float(_support.real(value, "max_slope_angle")))

    def set_prepass_inputs(self, depth: "Texture2D | None",
                           normals: "Texture2D | None") -> None:
        """Gives the pass the depth and normals it projects against.

        Both are borrowed for every later draw, so the pass keeps them alive.
        """
        _support.call("cna_decal_pass_set_prepass_inputs", self._handle.argument,
                      _optional_texture(depth, "depth"),
                      _optional_texture(normals, "normals"))
        self._retained = [value for value in (depth, normals) if value is not None]

    def set_camera(self, view: Matrix, projection: Matrix, far_plane: float) -> None:
        """Tells the pass which camera the depth it was given was rendered from."""
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_decal_pass_set_camera", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection),
                      c.c_float(_support.real(far_plane, "far_plane")))

    def draw(self, decal: "Texture2D", decal_world: Matrix, width: int,
             height: int) -> None:
        """Projects ``decal`` through its world transform onto the scene."""
        native = _native_matrix(decal_world)
        _support.call("cna_decal_pass_draw", self._handle.argument,
                      _optional_texture(decal, "decal"), c.byref(native),
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))


# --- the depth/normal prepass ------------------------------------------------


def uses_packed_depth(device: "GraphicsDevice") -> bool:
    """Whether a prepass on this device stores depth packed across four channels.

    A device with no readable float render target has to pack, and the shader
    that reads the result has to know which it is getting -- which is what
    :func:`depth_decode_glsl` is for.
    """
    return _support.out_bool("cna_depth_normal_prepass_uses_packed_depth_ext",
                             _device_handle(device))


def pack_depth(value: float) -> tuple[float, float, float, float]:
    """Splits a normalised depth across four channels. Pure.

    The same arithmetic the prepass shader runs, so a caller can check a texel
    they read back rather than trusting it. It stops one texel short of 1.0 on
    purpose: ``fract(1.0)`` is zero, so an unclamped far-plane depth would read
    back as the nearest possible surface.
    """
    red, green, blue, alpha = (c.c_float(), c.c_float(), c.c_float(), c.c_float())
    _support.call("cna_depth_normal_prepass_pack_depth",
                  c.c_float(_support.real(value, "value")), c.byref(red),
                  c.byref(green), c.byref(blue), c.byref(alpha))
    return (float(red.value), float(green.value), float(blue.value),
            float(alpha.value))


def unpack_depth(red: float, green: float, blue: float, alpha: float) -> float:
    """Reassembles a normalised depth from four packed channels. Pure."""
    return _support.out_f32(
        "cna_depth_normal_prepass_unpack_depth",
        c.c_float(_support.real(red, "red")), c.c_float(_support.real(green, "green")),
        c.c_float(_support.real(blue, "blue")), c.c_float(_support.real(alpha, "alpha")))


def has_velocity(texel: Color) -> bool:
    """Whether a velocity texel holds a velocity at all. Pure.

    The alpha channel is the marker, so a texel that was never written is not
    read as a zero velocity -- which would be a real answer rather than an
    absent one.
    """
    return _support.out_bool("cna_depth_normal_prepass_has_velocity_ext",
                             _colour(texel))


def decode_velocity(texel: Color) -> "Vector2":
    """The screen-space velocity a texel encodes, or zero when it holds none. Pure."""
    from Microsoft.Xna.Framework import Vector2

    value = _abi.CNA_Vector2()
    _support.call("cna_depth_normal_prepass_decode_velocity_ext", _colour(texel),
                  c.byref(value))
    return Vector2(float(value.x), float(value.y))


def depth_decode_glsl(packed: bool) -> str:
    """CNA's own GLSL for reading the prepass depth back, packed or not."""
    return _support.copied_text("cna_depth_normal_prepass_copy_depth_decode_glsl",
                                (c.c_uint8(1 if packed else 0),), "depth decode GLSL")


def velocity_decode_glsl() -> str:
    """CNA's own GLSL for reading the prepass velocity back."""
    return _support.copied_text("cna_depth_normal_prepass_copy_velocity_decode_glsl",
                                (), "velocity decode GLSL")


class DepthNormalPrepass(_EngineObject):
    """Linear depth, view-space normals and optionally velocity, for one frame.

    Every screen-space effect in this layer reads it. How many passes it takes
    is the renderer's business, not the caller's: :attr:`pass_count` says, and a
    frame drives :meth:`render` once per pass.
    """

    __slots__ = ()
    _DESTROY = "cna_depth_normal_prepass_destroy"

    def __init__(self, device: "GraphicsDevice", width: int, height: int,
                 encoding: DepthEncoding = DepthEncoding.Automatic) -> None:
        self._attach(_support.out_handle(
            "cna_depth_normal_prepass_create", _device_handle(device),
            c.c_int32(_support.checked(width, "int32", "width")),
            c.c_int32(_support.checked(height, "int32", "height")),
            c.c_uint32(int(DepthEncoding(encoding)))), device)

    def is_supported(self, device: "GraphicsDevice") -> bool:
        """Whether the prepass can do its real work on ``device``."""
        return _support.out_bool("cna_depth_normal_prepass_is_supported",
                                 self._handle.argument, _device_handle(device))

    @property
    def pass_count(self) -> int:
        """How many passes a frame has to drive.

        One where the renderer can write depth and normals to two targets at
        once, more where it cannot. :attr:`uses_multiple_render_targets` says
        which case this is.
        """
        return _support.out_i32("cna_depth_normal_prepass_get_pass_count",
                                self._handle.argument)

    @property
    def uses_multiple_render_targets(self) -> bool:
        """Whether depth and normals are written in one pass rather than two."""
        return _support.out_bool(
            "cna_depth_normal_prepass_is_using_multiple_render_targets",
            self._handle.argument)

    @property
    def is_depth_packed(self) -> bool:
        """Whether this prepass packed depth across four channels."""
        return _support.out_bool("cna_depth_normal_prepass_is_depth_packed",
                                 self._handle.argument)

    @property
    def roughness(self) -> float:
        """The roughness the prepass writes for geometry that carries none."""
        return _support.out_f32("cna_depth_normal_prepass_get_roughness",
                                self._handle.argument)

    @roughness.setter
    def roughness(self, value: float) -> None:
        _support.call("cna_depth_normal_prepass_set_roughness", self._handle.argument,
                      c.c_float(_support.real(value, "roughness")))

    @property
    def velocity_enabled(self) -> bool:
        """Whether the prepass also writes screen-space velocity."""
        return _support.out_bool("cna_depth_normal_prepass_is_velocity_enabled_ext",
                                 self._handle.argument)

    @velocity_enabled.setter
    def velocity_enabled(self, value: bool) -> None:
        _support.call("cna_depth_normal_prepass_set_velocity_enabled_ext",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    def set_previous_world(self, previous_world: Matrix) -> None:
        """The transform this object had last frame, for its velocity."""
        native = _native_matrix(previous_world)
        _support.call("cna_depth_normal_prepass_set_previous_world_ext",
                      self._handle.argument, c.byref(native))

    def set_previous_camera(self, previous_view: Matrix,
                            previous_projection: Matrix) -> None:
        """The camera last frame had, for reprojection."""
        view, projection = (_native_matrix(previous_view),
                            _native_matrix(previous_projection))
        _support.call("cna_depth_normal_prepass_set_previous_camera_ext",
                      self._handle.argument, c.byref(view), c.byref(projection))

    def resize(self, width: int, height: int) -> None:
        """Resizes the prepass targets, releasing the views handed out so far."""
        for view in list(self._views.values()):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        _support.call("cna_depth_normal_prepass_resize", self._handle.argument,
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))

    @property
    def depth_texture(self) -> "RenderTarget2D | None":
        """The linear depth the prepass rendered, as a counted borrow."""
        return self._render_target_view("depth",
                                        "cna_depth_normal_prepass_get_depth_texture")

    @property
    def normal_texture(self) -> "RenderTarget2D | None":
        """The view-space normals the prepass rendered, as a counted borrow."""
        return self._render_target_view("normals",
                                        "cna_depth_normal_prepass_get_normal_texture")

    @property
    def velocity_texture(self) -> "RenderTarget2D | None":
        """The screen-space velocity, or ``None`` when velocity is off."""
        return self._render_target_view(
            "velocity", "cna_depth_normal_prepass_get_velocity_texture_ext")

    @property
    def prepass_effect(self) -> "Effect | None":
        """The effect rigid geometry is drawn with during the prepass."""
        return self._effect_view("effect",
                                 "cna_depth_normal_prepass_get_prepass_effect")

    @property
    def skinned_prepass_effect(self) -> "Effect | None":
        """The effect skinned geometry is drawn with during the prepass."""
        return self._effect_view(
            "skinned_effect", "cna_depth_normal_prepass_get_skinned_prepass_effect")

    def render(self, pass_index: int, view: Matrix, projection: Matrix,
               near_plane: float, far_plane: float) -> "_PrepassScope":
        """The bracket that renders one prepass pass."""
        return _PrepassScope(self, pass_index, view, projection, near_plane, far_plane)

    def _begin(self, pass_index: int, view: Matrix, projection: Matrix,
               near_plane: float, far_plane: float) -> None:
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        _support.call("cna_depth_normal_prepass_begin", self._handle.argument,
                      c.c_int32(_support.checked(pass_index, "int32", "pass_index")),
                      c.byref(native_view), c.byref(native_projection),
                      c.c_float(_support.real(near_plane, "near_plane")),
                      c.c_float(_support.real(far_plane, "far_plane")))

    def _end(self) -> None:
        _support.call("cna_depth_normal_prepass_end", self._handle.argument)


class _PrepassScope:
    """The ``begin``/``end`` bracket of one prepass pass."""

    __slots__ = ("_prepass", "_arguments")

    def __init__(self, prepass: DepthNormalPrepass, *arguments) -> None:
        self._prepass = prepass
        self._arguments = arguments

    def __enter__(self) -> DepthNormalPrepass:
        self._prepass._begin(*self._arguments)
        return self._prepass

    def __exit__(self, *_exception: object) -> None:
        self._prepass._end()


# --- transparency ------------------------------------------------------------


def sort_key(bounds: "BoundingBox", camera_position: Vector3) -> float:
    """The distance from a camera to the nearest point of a box. Pure.

    Zero on every axis the camera is already between, which is what makes a
    box containing the camera sort first rather than by its centre.
    """
    native_bounds = _bounds(bounds)
    native_position = _native_vector(camera_position)
    return _support.out_f32("cna_transparent_draw_list_sort_key",
                            c.byref(native_bounds), c.byref(native_position))


def camera_position_of(view: Matrix) -> Vector3:
    """The eye a view matrix looks from. Pure.

    Taken through a full inverse rather than by negating the translation row,
    because that shortcut is only right for a rigid view and a game may hand
    over one with a scale in it.
    """
    native = _native_matrix(view)
    value = _abi.CNA_Vector3()
    _support.call("cna_transparent_draw_list_camera_position_of", c.byref(native),
                  c.byref(value))
    return _vector(value)


class TransparentDrawList(_EngineObject):
    """Draw callbacks with bounds, replayed back to front.

    Sorted transparency, done the only way it can be from outside: the caller
    says how to draw each thing and where it is, and the list decides the order.

    **The callbacks are rooted here.** CNA holds a trampoline, not a Python
    object, so a callable nothing else refers to would otherwise be collected
    while CNA could still call it. :meth:`clear` and :meth:`close` drop the
    roots. A Python exception inside a callback is caught, turned into a failure
    result for CNA, and re-raised once the native call has returned, so nothing
    unwinds through C.
    """

    __slots__ = ("_callbacks", "_failure")

    _DESTROY = "cna_transparent_draw_list_destroy"

    def __init__(self) -> None:
        self._attach(_support.out_handle("cna_transparent_draw_list_create"))
        #: Trampolines and the Python callables behind them, rooted together.
        self._callbacks: list[tuple[object, object]] = []
        self._failure: BaseException | None = None

    def submit(self, bounds: "BoundingBox", draw: Callable[[], None]) -> None:
        """Adds one thing to draw, with the bounds its order is decided by."""
        if not callable(draw):
            raise TypeError("draw must be callable")
        native_bounds = _bounds(bounds)

        def invoke(_context) -> int:
            try:
                draw()
            except BaseException as error:  # re-raised after the native call
                if self._failure is None:
                    self._failure = error
                return 12  # CNA_RESULT_INTERNAL: fail the draw that asked for it
            return 0

        trampoline = _engine.CNA_TransparentDrawCallback(invoke)
        _support.call("cna_transparent_draw_list_submit", self._handle.argument,
                      c.byref(native_bounds), trampoline, None)
        # Rooted only after CNA accepted it; a refused submit holds nothing.
        self._callbacks.append((trampoline, draw))

    @property
    def count(self) -> int:
        """How many entries the list holds."""
        return _support.out_u64("cna_transparent_draw_list_get_count",
                                self._handle.argument)

    def clear(self) -> None:
        """Empties the list and drops every rooted callback."""
        _support.call("cna_transparent_draw_list_clear", self._handle.argument)
        self._callbacks.clear()

    def sorted_order(self, view: Matrix) -> tuple[int, ...]:
        """The order the entries would be drawn in, without drawing them."""
        count = self.count
        native = _native_matrix(view)
        if count == 0:
            return ()
        destination = (c.c_int32 * count)()
        written = c.c_uint64()
        _support.call("cna_transparent_draw_list_copy_sorted_order_ext",
                      self._handle.argument, c.byref(native), destination,
                      c.c_uint64(count), c.byref(written))
        return tuple(int(destination[index]) for index in range(int(written.value)))

    def draw_sorted(self, view: Matrix) -> None:
        """Invokes every callback, furthest first.

        A Python exception raised inside a callback surfaces here, after CNA has
        returned, rather than unwinding through native frames.
        """
        native = _native_matrix(view)
        self._failure = None
        try:
            _support.call("cna_transparent_draw_list_draw_sorted",
                          self._handle.argument, c.byref(native))
        finally:
            failure, self._failure = self._failure, None
            if failure is not None:
                raise failure

    def close(self) -> None:
        super().close()
        self._callbacks.clear()


def transparency_weight(view_depth: float, alpha: float, far_plane: float) -> float:
    """The weight an order-independent blend gives one fragment. Pure.

    The CPU twin of the shader's own function, arithmetic in the same order, so
    the two agree in the last bits. Near fragments weigh more than far ones,
    which is what makes an unsorted blend approximate a sorted one.
    """
    return _support.out_f32(
        "cna_weighted_blended_transparency_weight",
        c.c_float(_support.real(view_depth, "view_depth")),
        c.c_float(_support.real(alpha, "alpha")),
        c.c_float(_support.real(far_plane, "far_plane")))


def transparency_accumulation_glsl() -> str:
    """CNA's own GLSL for the weighted blend, for a caller writing their own shader."""
    return _support.copied_text(
        "cna_weighted_blended_transparency_copy_accumulation_glsl", (),
        "accumulation GLSL")


class WeightedBlendedTransparency(_EngineObject):
    """Order-independent transparency, accumulated and then resolved.

    Two targets: one accumulates weighted colour, the other how much light gets
    through. :meth:`accumulate` brackets the transparent geometry and
    :meth:`resolve` composites the result over the scene.
    """

    __slots__ = ()
    _DESTROY = "cna_weighted_blended_transparency_destroy"

    def __init__(self, device: "GraphicsDevice", width: int, height: int) -> None:
        self._attach(_support.out_handle(
            "cna_weighted_blended_transparency_create", _device_handle(device),
            c.c_int32(_support.checked(width, "int32", "width")),
            c.c_int32(_support.checked(height, "int32", "height"))), device)

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can accumulate into two float targets at once."""
        return _support.out_bool("cna_weighted_blended_transparency_is_supported",
                                 self._handle.argument)

    @property
    def unsupported_reason(self) -> str:
        """CNA's reason, or the empty string when it is supported."""
        return _support.copied_text(
            "cna_weighted_blended_transparency_copy_unsupported_reason",
            (self._handle.argument,), "unsupported reason")

    @property
    def is_accumulating(self) -> bool:
        """Whether the accumulation bracket is currently open."""
        return _support.out_bool("cna_weighted_blended_transparency_is_accumulating",
                                 self._handle.argument)

    @property
    def accumulation_texture(self) -> "RenderTarget2D | None":
        """The weighted colour target, as a counted borrow."""
        return self._render_target_view(
            "accumulation",
            "cna_weighted_blended_transparency_get_accumulation_texture_ext")

    @property
    def revealage_texture(self) -> "RenderTarget2D | None":
        """The how-much-gets-through target, as a counted borrow."""
        return self._render_target_view(
            "revealage",
            "cna_weighted_blended_transparency_get_revealage_texture_ext")

    def resize(self, width: int, height: int) -> None:
        """Resizes both targets, releasing the views handed out so far."""
        for view in list(self._views.values()):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        _support.call("cna_weighted_blended_transparency_resize", self._handle.argument,
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))

    def accumulate(self, far_plane: float) -> "_AccumulationScope":
        """The bracket transparent geometry is drawn inside."""
        return _AccumulationScope(self, far_plane)

    def resolve(self, width: int, height: int) -> None:
        """Composites the accumulated transparency over whatever is bound."""
        _support.call("cna_weighted_blended_transparency_resolve",
                      self._handle.argument,
                      c.c_int32(_support.checked(width, "int32", "width")),
                      c.c_int32(_support.checked(height, "int32", "height")))

    def _begin(self, far_plane: float) -> None:
        _support.call("cna_weighted_blended_transparency_begin", self._handle.argument,
                      c.c_float(_support.real(far_plane, "far_plane")))

    def _end(self) -> None:
        _support.call("cna_weighted_blended_transparency_end", self._handle.argument)


class _AccumulationScope:
    """The ``begin``/``end`` bracket of one transparency accumulation."""

    __slots__ = ("_transparency", "_far_plane")

    def __init__(self, transparency: WeightedBlendedTransparency,
                 far_plane: float) -> None:
        self._transparency = transparency
        self._far_plane = far_plane

    def __enter__(self) -> WeightedBlendedTransparency:
        self._transparency._begin(self._far_plane)
        return self._transparency

    def __exit__(self, *_exception: object) -> None:
        self._transparency._end()
