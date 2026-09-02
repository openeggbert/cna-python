"""Physically based materials, their glTF extensions and the effects that draw them.

XNA 4.0's shading model is ``BasicEffect``: diffuse, specular power, three
directional lights. There is no metallic-roughness workflow, no normal map slot,
no emissive factor, and nothing to hang them on, so all of this lives here.

The material is a value
-----------------------

:class:`PbrMaterial` is an immutable value, and every default in it comes from
``cna_pbr_material_ext_init`` rather than being written down. That matters more
here than anywhere else in this package: a material has twenty-seven fields, and
a Python-side transcription of "roughness defaults to one half" would drift the
day CNA changed its mind, silently, in the direction of looking almost right.

**The seven texture slots are not in the structure's field order.** CNA's slot
numbering runs base colour, normal, metallic-roughness, emissive, occlusion,
specular, specular colour; the structure declares occlusion *before* emissive.
So ``texture_coordinate_sets[3]`` is the emissive slot's, not occlusion's. This
module maps slot to field through an explicit table rather than by position, and
a test walks all seven with distinct values, because getting that wrong swaps
two maps in a way that renders.

Ownership
---------

A material holds textures the caller owns; CNA copies handles, never resources,
and compares two materials by handle identity rather than by content.
:class:`PbrMaterialExtensions` is the one thing here with a handle of its own,
and it needs no device -- it is a value in a box, boxed only because C cannot
return a growing structure by value.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import TYPE_CHECKING, Mapping, Sequence

from Microsoft.Xna.Framework import Color, Vector2, Vector3, Vector4

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .values import _native_vector, _vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import Effect, GraphicsDevice, Texture2D

__all__ = [
    "PbrTextureSlot",
    "AlphaMode",
    "TransparencyMode",
    "TextureTransform",
    "PbrMaterial",
    "PbrMaterialExtensions",
    "PbrEffect",
    "SkinnedPbrEffect",
    "GltfMaterialSource",
    "GltfMaterialExtensionSource",
    "build_material",
    "build_extensions",
    "thin_film_iridescence",
    "thin_film_iridescence_glsl",
    "PBR_TEXTURE_SLOT_COUNT",
]

#: How many texture slots a PBR material carries, from the canonical header.
PBR_TEXTURE_SLOT_COUNT = _engine.CNA_PBR_TEXTURE_SLOT_COUNT


class PbrTextureSlot(IntEnum):
    """Which map a texture is, and the index its coordinate set and transform use.

    The numbering is CNA's. It is **not** the order the native structure
    declares its texture fields in, which is why nothing here indexes by
    position.
    """

    BaseColor = _engine.CNA_PBR_TEXTURE_BASE_COLOR
    Normal = _engine.CNA_PBR_TEXTURE_NORMAL
    MetallicRoughness = _engine.CNA_PBR_TEXTURE_METALLIC_ROUGHNESS
    Emissive = _engine.CNA_PBR_TEXTURE_EMISSIVE
    Occlusion = _engine.CNA_PBR_TEXTURE_OCCLUSION
    Specular = _engine.CNA_PBR_TEXTURE_SPECULAR_EXT
    SpecularColor = _engine.CNA_PBR_TEXTURE_SPECULAR_COLOR_EXT


#: Slot -> the native structure field that holds it. Written out because the two
#: orders differ, and a mapping by position would swap emissive with occlusion.
_SLOT_FIELDS: dict[PbrTextureSlot, str] = {
    PbrTextureSlot.BaseColor: "albedo_texture",
    PbrTextureSlot.Normal: "normal_texture",
    PbrTextureSlot.MetallicRoughness: "metallic_roughness_texture",
    PbrTextureSlot.Emissive: "emissive_texture",
    PbrTextureSlot.Occlusion: "ambient_occlusion_texture",
    PbrTextureSlot.Specular: "specular_texture",
    PbrTextureSlot.SpecularColor: "specular_color_texture",
}


class AlphaMode(IntEnum):
    """How a material's alpha is resolved."""

    Opaque = _engine.CNA_ALPHA_MODE_OPAQUE_EXT
    Mask = _engine.CNA_ALPHA_MODE_MASK_EXT
    Blend = _engine.CNA_ALPHA_MODE_BLEND_EXT


class TransparencyMode(IntEnum):
    """How a renderer resolves transparent geometry as a whole."""

    Nothing = _engine.CNA_TRANSPARENCY_MODE_NONE
    Sorted = _engine.CNA_TRANSPARENCY_MODE_SORTED
    OrderIndependent = _engine.CNA_TRANSPARENCY_MODE_ORDER_INDEPENDENT


@dataclass(frozen=True)
class TextureTransform:
    """One slot's texture-coordinate transform, applied scale then rotate then offset."""

    offset: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    scale: Vector2 = field(default_factory=lambda: Vector2(1.0, 1.0))
    rotation: float = 0.0

    @classmethod
    def _from_native(cls, value) -> "TextureTransform":
        return cls(Vector2(float(value.offset.x), float(value.offset.y)),
                   Vector2(float(value.scale.x), float(value.scale.y)),
                   float(value.rotation))

    def _fill(self, value) -> None:
        value.struct_size = c.sizeof(_engine.CNA_TextureTransformEXT)
        value.struct_version = 1
        value.offset = _abi.CNA_Vector2(float(self.offset.X), float(self.offset.Y))
        value.scale = _abi.CNA_Vector2(float(self.scale.X), float(self.scale.Y))
        value.rotation = _support.real(self.rotation, "rotation")


def _initialised(structure: type, route: str):
    """A caller-owned value structure filled with CNA's defaults, not with zeroes.

    Zero-filling would be equivalent today for the texture tables -- an invalid
    handle is zero -- and would stop being equivalent the moment CNA adds a
    field whose default is not zero. Asking costs one call and cannot drift.
    """
    value = structure()
    _support.call(route, c.byref(value))
    return value


def _texture_handle(value: object, what: str) -> int:
    if value is None:
        return 0
    if not hasattr(value, "_require_handle"):
        raise TypeError(f"{what} must be a graphics texture or None")
    return int(value._require_handle())


def _effect_handle(effect: object) -> c.c_uint64:
    if not hasattr(effect, "_require_handle"):
        raise TypeError("effect must be a Microsoft.Xna.Framework.Graphics.Effect")
    return c.c_uint64(effect._require_handle())


def _device_handle(device: "GraphicsDevice") -> c.c_uint64:
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(device._require_handle())


def _colour(value: _abi.CNA_Color) -> Color:
    return Color(int(value.r), int(value.g), int(value.b), int(value.a))


def _vector4(value: _abi.CNA_Vector4) -> Vector4:
    return Vector4(float(value.x), float(value.y), float(value.z), float(value.w))


def _native_vector4(value: Vector4) -> _abi.CNA_Vector4:
    if not isinstance(value, Vector4):
        raise TypeError("expected a Microsoft.Xna.Framework.Vector4")
    return _abi.CNA_Vector4(float(value.X), float(value.Y), float(value.Z),
                            float(value.W))


def _native_colour(value: Color) -> _abi.CNA_Color:
    if not isinstance(value, Color):
        raise TypeError("expected a Microsoft.Xna.Framework.Color")
    return _abi.CNA_Color(int(value.R), int(value.G), int(value.B), int(value.A))


@dataclass(frozen=True)
class PbrMaterial:
    """A metallic-roughness material, as one immutable value.

    ``textures`` is a mapping from :class:`PbrTextureSlot` to the caller's own
    texture, and a slot absent from it has none. ``coordinate_sets`` and
    ``transforms`` are also keyed by slot, so nothing depends on the order the
    native structure happens to declare its fields in.

    Build one from :meth:`default` and adjust it with
    :func:`dataclasses.replace`; every default is CNA's, read through
    ``cna_pbr_material_ext_init``.
    """

    albedo_color: Color
    emissive_factor: Vector3
    specular_color_factor: Vector3
    metallic_factor: float
    roughness_factor: float
    normal_scale: float
    occlusion_strength: float
    ior: float
    specular_factor: float
    alpha_cutoff: float
    alpha_mode: AlphaMode
    double_sided: bool
    base_color_texture_srgb: bool
    emissive_texture_srgb: bool
    specular_color_texture_srgb: bool
    output_encoded_to_srgb: bool
    textures: Mapping[PbrTextureSlot, object] = field(default_factory=dict)
    coordinate_sets: Mapping[PbrTextureSlot, int] = field(default_factory=dict)
    transforms: Mapping[PbrTextureSlot, TextureTransform] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "PbrMaterial":
        """CNA's own canonical defaults, read rather than transcribed."""
        value = _engine.CNA_PbrMaterialEXT()
        _support.call("cna_pbr_material_ext_init", c.byref(value))
        return cls._from_native(value)

    @classmethod
    def _from_native(cls, value, textures: Mapping | None = None) -> "PbrMaterial":
        """Rebuilds the value; texture objects are the caller's, never new facades."""
        supplied = dict(textures or {})
        return cls(
            albedo_color=_colour(value.albedo_color),
            emissive_factor=_vector(value.emissive_factor),
            specular_color_factor=_vector(value.specular_color_factor),
            metallic_factor=float(value.metallic_factor),
            roughness_factor=float(value.roughness_factor),
            normal_scale=float(value.normal_scale),
            occlusion_strength=float(value.occlusion_strength),
            ior=float(value.ior),
            specular_factor=float(value.specular_factor),
            alpha_cutoff=float(value.alpha_cutoff),
            alpha_mode=AlphaMode(int(value.alpha_mode)),
            double_sided=bool(value.double_sided),
            base_color_texture_srgb=bool(value.base_color_texture_srgb),
            emissive_texture_srgb=bool(value.emissive_texture_srgb),
            specular_color_texture_srgb=bool(value.specular_color_texture_srgb),
            output_encoded_to_srgb=bool(value.output_encoded_to_srgb),
            textures={slot: supplied[slot] for slot in PbrTextureSlot
                      if slot in supplied
                      and getattr(value, _SLOT_FIELDS[slot]) != 0},
            coordinate_sets={slot: int(value.texture_coordinate_sets[int(slot)])
                             for slot in PbrTextureSlot},
            transforms={slot: TextureTransform._from_native(
                value.texture_transforms[int(slot)]) for slot in PbrTextureSlot})

    def _native(self) -> _engine.CNA_PbrMaterialEXT:
        value = _support.in_struct(_engine.CNA_PbrMaterialEXT, 1)
        value.albedo_color = _native_colour(self.albedo_color)
        value.emissive_factor = _native_vector(self.emissive_factor)
        value.specular_color_factor = _native_vector(self.specular_color_factor)
        value.metallic_factor = _support.real(self.metallic_factor, "metallic_factor")
        value.roughness_factor = _support.real(self.roughness_factor, "roughness_factor")
        value.normal_scale = _support.real(self.normal_scale, "normal_scale")
        value.occlusion_strength = _support.real(self.occlusion_strength,
                                                 "occlusion_strength")
        value.ior = _support.real(self.ior, "ior")
        value.specular_factor = _support.real(self.specular_factor, "specular_factor")
        value.alpha_cutoff = _support.real(self.alpha_cutoff, "alpha_cutoff")
        value.alpha_mode = int(AlphaMode(self.alpha_mode))
        value.double_sided = 1 if self.double_sided else 0
        value.base_color_texture_srgb = 1 if self.base_color_texture_srgb else 0
        value.emissive_texture_srgb = 1 if self.emissive_texture_srgb else 0
        value.specular_color_texture_srgb = 1 if self.specular_color_texture_srgb else 0
        value.output_encoded_to_srgb = 1 if self.output_encoded_to_srgb else 0
        for slot in PbrTextureSlot:
            setattr(value, _SLOT_FIELDS[slot],
                    _texture_handle(self.textures.get(slot), f"textures[{slot.name}]"))
            value.texture_coordinate_sets[int(slot)] = _support.checked(
                self.coordinate_sets.get(slot, 0), "int32",
                f"coordinate_sets[{slot.name}]")
            transform = self.transforms.get(slot)
            (transform if transform is not None
             else TextureTransform())._fill(value.texture_transforms[int(slot)])
        return value

    def matches(self, other: "PbrMaterial") -> bool:
        """CNA's own equality, which compares textures by handle identity.

        Different from ``==``, which is Python's field comparison: two facades
        over one native texture are the same texture to CNA and different
        objects to Python. Both answers are correct about different questions,
        so both are available and neither is silently substituted for the other.
        """
        if not isinstance(other, PbrMaterial):
            raise TypeError("other must be a PbrMaterial")
        first, second = self._native(), other._native()
        return _support.out_bool("cna_pbr_material_ext_equals", c.byref(first),
                                 c.byref(second))

    def cna_hash(self) -> int:
        """CNA's canonical hash, consistent with :meth:`matches` rather than ``==``."""
        value = self._native()
        return _support.out_u64("cna_pbr_material_ext_get_hash_code", c.byref(value))

    def describe(self) -> str:
        """CNA's own ``ToString`` text for the material."""
        value = self._native()
        return _support.copied_text("cna_pbr_material_ext_copy_to_string",
                                    (c.byref(value),), "material text")

    def apply_state(self, device: "GraphicsDevice") -> None:
        """Sets the blending, depth write and culling the material implies.

        Alpha mode and double-sidedness are material properties that only take
        effect as device state, so CNA turns one into the other rather than
        leaving a caller to work out the mapping.
        """
        value = self._native()
        _support.call("cna_pbr_material_apply_state", c.byref(value),
                      _device_handle(device))


def _scalar_property(getter: str, setter: str, doc: str):
    """One float field of the extensions object, read and written straight through."""
    def read(self) -> float:
        return _support.out_f32(getter, self._handle.argument)

    def write(self, value: float) -> None:
        _support.call(setter, self._handle.argument,
                      c.c_float(_support.real(value, "value")))

    return property(read, write, doc=doc)


def _vector_property(getter: str, setter: str, doc: str):
    """One ``Vector3`` field of the extensions object."""
    def read(self) -> Vector3:
        value = _abi.CNA_Vector3()
        _support.call(getter, self._handle.argument, c.byref(value))
        return _vector(value)

    def write(self, value: Vector3) -> None:
        native = _native_vector(value)
        _support.call(setter, self._handle.argument, c.byref(native))

    return property(read, write, doc=doc)


def _texture_property(getter: str, setter: str, key: str, doc: str):
    """One texture slot of the extensions object.

    CNA stores the handle; this keeps the caller's object beside it, so reading
    the property back gives the same object rather than a second facade over one
    native texture.
    """
    def read(self):
        handle = _support.out_handle(getter, self._handle.argument)
        return self._textures.get(key) if handle else None

    def write(self, value) -> None:
        _support.call(setter, self._handle.argument,
                      c.c_uint64(_texture_handle(value, key)))
        self._textures[key] = value

    return property(read, write, doc=doc)


def _flag_property(getter: str, doc: str):
    """One derived flag of the extensions object; CNA decides it, nothing sets it."""
    return property(lambda self: _support.out_bool(getter, self._handle.argument),
                    doc=doc)


class PbrMaterialExtensions:
    """The glTF material extensions a PBR material can carry.

    Clearcoat, sheen, transmission, volume, iridescence and subsurface, each
    with its factors and its own texture. A handle rather than a value because
    the canonical type keeps growing and C cannot return a growing structure by
    value; it needs no graphics device, so it can be built anywhere the engine
    layer is.

    The ``is_*`` flags are CNA's own decisions about whether a feature is
    active, derived from the factors rather than set: a transmission factor of
    zero means transmission is off, and nothing has to remember to say so.
    """

    __slots__ = ("_handle", "_textures")

    def __init__(self) -> None:
        self._handle = _support.NativeHandle(
            _support.out_handle("cna_pbr_material_extensions_create"),
            "cna_pbr_material_extensions_destroy", "PBR material extensions")
        #: The caller's texture objects, beside the handles CNA stores.
        self._textures: dict[str, object] = {}

    @classmethod
    def _wrap(cls, handle: _support.NativeHandle) -> "PbrMaterialExtensions":
        """Adopts a handle this class did not create.

        Private, and not part of the public surface: a public signature naming a
        handle would publish a private native type. Used for the counted view an
        owner hands out onto its own extensions, which this object then owns and
        releases -- see ENGINE-002.
        """
        self = cls.__new__(cls)
        self._handle = handle
        self._textures = {}
        return self

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the extensions. Calling it twice is not an error."""
        self._handle.close()
        self._textures.clear()

    def __enter__(self) -> "PbrMaterialExtensions":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def copy_from(self, source: "PbrMaterialExtensions") -> None:
        """Copies every field of ``source`` into this one."""
        if not isinstance(source, PbrMaterialExtensions):
            raise TypeError("source must be a PbrMaterialExtensions")
        _support.call("cna_pbr_material_extensions_copy_from", self._handle.argument,
                      source._handle.argument)
        self._textures = dict(source._textures)

    def matches(self, other: "PbrMaterialExtensions") -> bool:
        """CNA's own equality across every field."""
        if not isinstance(other, PbrMaterialExtensions):
            raise TypeError("other must be a PbrMaterialExtensions")
        return _support.out_bool("cna_pbr_material_extensions_equals",
                                 self._handle.argument, other._handle.argument)

    def cna_hash(self) -> int:
        """CNA's canonical hash, consistent with :meth:`matches`."""
        return _support.out_u64("cna_pbr_material_extensions_get_hash_code",
                                self._handle.argument)

    def describe(self) -> str:
        """CNA's own ``ToString`` text."""
        return _support.copied_text("cna_pbr_material_extensions_copy_to_string",
                                    (self._handle.argument,), "extensions text")

    clearcoat_factor = _scalar_property(
        "cna_pbr_material_extensions_get_clearcoat_factor",
        "cna_pbr_material_extensions_set_clearcoat_factor",
        "How strong the clearcoat layer is; zero turns it off.")
    clearcoat_roughness = _scalar_property(
        "cna_pbr_material_extensions_get_clearcoat_roughness",
        "cna_pbr_material_extensions_set_clearcoat_roughness",
        "The clearcoat layer's own roughness, separate from the base material's.")
    clearcoat_normal_scale = _scalar_property(
        "cna_pbr_material_extensions_get_clearcoat_normal_scale",
        "cna_pbr_material_extensions_set_clearcoat_normal_scale",
        "How strongly the clearcoat normal map perturbs the layer.")
    sheen_roughness = _scalar_property(
        "cna_pbr_material_extensions_get_sheen_roughness",
        "cna_pbr_material_extensions_set_sheen_roughness",
        "The sheen lobe's width, which is what makes cloth look like cloth.")
    transmission_factor = _scalar_property(
        "cna_pbr_material_extensions_get_transmission_factor",
        "cna_pbr_material_extensions_set_transmission_factor",
        "How much light passes through rather than reflecting.")
    thickness_factor = _scalar_property(
        "cna_pbr_material_extensions_get_thickness_factor",
        "cna_pbr_material_extensions_set_thickness_factor",
        "The volume's thickness in local units; zero is a thin surface.")
    attenuation_distance = _scalar_property(
        "cna_pbr_material_extensions_get_attenuation_distance",
        "cna_pbr_material_extensions_set_attenuation_distance",
        "How far light travels inside the volume before it is fully absorbed.")
    iridescence_factor = _scalar_property(
        "cna_pbr_material_extensions_get_iridescence_factor",
        "cna_pbr_material_extensions_set_iridescence_factor",
        "How strong the thin-film interference is.")
    iridescence_ior = _scalar_property(
        "cna_pbr_material_extensions_get_iridescence_ior",
        "cna_pbr_material_extensions_set_iridescence_ior",
        "The thin film's index of refraction.")
    iridescence_thickness_minimum = _scalar_property(
        "cna_pbr_material_extensions_get_iridescence_thickness_minimum",
        "cna_pbr_material_extensions_set_iridescence_thickness_minimum",
        "The film's thickness in nanometres where its texture reads zero.")
    iridescence_thickness_maximum = _scalar_property(
        "cna_pbr_material_extensions_get_iridescence_thickness_maximum",
        "cna_pbr_material_extensions_set_iridescence_thickness_maximum",
        "The film's thickness in nanometres where its texture reads one.")
    subsurface_wrap = _scalar_property(
        "cna_pbr_material_extensions_get_subsurface_wrap",
        "cna_pbr_material_extensions_set_subsurface_wrap",
        "How far light wraps around the terminator into shadow.")

    sheen_color_factor = _vector_property(
        "cna_pbr_material_extensions_get_sheen_color_factor",
        "cna_pbr_material_extensions_set_sheen_color_factor",
        "The sheen lobe's linear RGB colour.")
    attenuation_color = _vector_property(
        "cna_pbr_material_extensions_get_attenuation_color",
        "cna_pbr_material_extensions_set_attenuation_color",
        "The colour light becomes as it is absorbed through the volume.")
    subsurface_color = _vector_property(
        "cna_pbr_material_extensions_get_subsurface_color",
        "cna_pbr_material_extensions_set_subsurface_color",
        "The linear RGB tint of light scattered under the surface.")

    clearcoat_texture = _texture_property(
        "cna_pbr_material_extensions_get_clearcoat_texture",
        "cna_pbr_material_extensions_set_clearcoat_texture",
        "clearcoat_texture", "Per-texel clearcoat strength.")
    clearcoat_roughness_texture = _texture_property(
        "cna_pbr_material_extensions_get_clearcoat_roughness_texture",
        "cna_pbr_material_extensions_set_clearcoat_roughness_texture",
        "clearcoat_roughness_texture", "Per-texel clearcoat roughness.")
    clearcoat_normal_texture = _texture_property(
        "cna_pbr_material_extensions_get_clearcoat_normal_texture",
        "cna_pbr_material_extensions_set_clearcoat_normal_texture",
        "clearcoat_normal_texture", "The clearcoat layer's own normal map.")
    sheen_color_texture = _texture_property(
        "cna_pbr_material_extensions_get_sheen_color_texture",
        "cna_pbr_material_extensions_set_sheen_color_texture",
        "sheen_color_texture", "Per-texel sheen colour.")
    sheen_roughness_texture = _texture_property(
        "cna_pbr_material_extensions_get_sheen_roughness_texture",
        "cna_pbr_material_extensions_set_sheen_roughness_texture",
        "sheen_roughness_texture", "Per-texel sheen roughness.")
    transmission_texture = _texture_property(
        "cna_pbr_material_extensions_get_transmission_texture",
        "cna_pbr_material_extensions_set_transmission_texture",
        "transmission_texture", "Per-texel transmission.")
    thickness_texture = _texture_property(
        "cna_pbr_material_extensions_get_thickness_texture",
        "cna_pbr_material_extensions_set_thickness_texture",
        "thickness_texture", "Per-texel volume thickness.")
    iridescence_texture = _texture_property(
        "cna_pbr_material_extensions_get_iridescence_texture",
        "cna_pbr_material_extensions_set_iridescence_texture",
        "iridescence_texture", "Per-texel iridescence strength.")
    iridescence_thickness_texture = _texture_property(
        "cna_pbr_material_extensions_get_iridescence_thickness_texture",
        "cna_pbr_material_extensions_set_iridescence_thickness_texture",
        "iridescence_thickness_texture",
        "Per-texel film thickness, between the minimum and the maximum.")

    is_subsurface_enabled = _flag_property(
        "cna_pbr_material_extensions_is_subsurface_enabled",
        "Whether subsurface scattering contributes anything, as CNA decides it.")
    is_iridescence_enabled = _flag_property(
        "cna_pbr_material_extensions_is_iridescence_enabled",
        "Whether thin-film interference contributes anything.")
    is_transmission_enabled = _flag_property(
        "cna_pbr_material_extensions_is_transmission_enabled",
        "Whether any light passes through the material.")
    is_sheen_enabled = _flag_property(
        "cna_pbr_material_extensions_is_sheen_enabled",
        "Whether the sheen lobe contributes anything.")
    is_neutral = _flag_property(
        "cna_pbr_material_extensions_is_neutral",
        "Whether every extension is off, so the material shades as plain PBR.")


class _PbrEffectBase:
    """An effect that renders a PBR material, and the material it carries."""

    __slots__ = ("_effect", "_textures")

    _CREATE: str = ""
    _APPLY: str = ""
    _EXTRACT: str = ""

    def __init__(self, device: "GraphicsDevice") -> None:
        from Microsoft.Xna.Framework.Graphics import Effect

        handle = _support.out_handle(self._CREATE, _device_handle(device))
        effect = Effect.__new__(Effect)
        effect._initialize_native(device, handle)
        self._effect = effect
        #: The textures last applied, so reading the material back returns the
        #: caller's own objects rather than new facades over borrowed handles.
        self._textures: dict[PbrTextureSlot, object] = {}

    @property
    def effect(self) -> "Effect":
        """The underlying effect, for its parameters, techniques and ``Apply``.

        An ordinary ``Microsoft.Xna.Framework.Graphics.Effect``: this class adds
        the PBR material vocabulary beside it rather than replacing it, and
        disposing the effect is what releases the native object.
        """
        return self._effect

    @property
    def is_disposed(self) -> bool:
        """True once the underlying effect has been disposed."""
        return bool(self._effect.IsDisposed)

    def close(self) -> None:
        """Disposes the underlying effect."""
        if not self._effect.IsDisposed:
            self._effect.Dispose()
        self._textures.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def material(self) -> PbrMaterial:
        """The material the effect currently carries.

        Every field crosses. The texture objects are the ones that were applied;
        CNA answers with handles, and a second facade over a borrowed texture
        would be a second owner of one thing.
        """
        handle = _effect_handle(self._effect)
        value = _support.out_struct(_engine.CNA_PbrMaterialEXT, 1, self._EXTRACT, handle)
        # The extract route mirrors the apply route and reports no textures for
        # the same reason (ENGINE-005), so each slot is asked for separately.
        present = {}
        for slot in PbrTextureSlot:
            has = c.c_uint8()
            produced = c.c_uint64()
            _support.call("cna_pbr_effect_get_texture", handle, c.c_uint32(int(slot)),
                          c.byref(has), c.byref(produced))
            if has.value:
                setattr(value, _SLOT_FIELDS[slot], produced.value)
                present[slot] = self._textures.get(slot)
        return PbrMaterial._from_native(value, present)

    @material.setter
    def material(self, value: PbrMaterial) -> None:
        """Applies every field of the material, including its textures.

        **The texture slots are applied separately, and deliberately so.**
        ``cna_pbr_effect_apply_material`` is documented to carry every field and
        does carry every scalar, but on CNA 0.21.0 it drops all seven texture
        slots -- measured with ``cna_pbr_effect_get_texture``, which reports no
        texture in any slot afterwards. So each slot is assigned with
        ``cna_pbr_effect_set_texture``, which works. Nothing is hidden: the raw
        behaviour is recorded as ENGINE-005 in
        ``docs/engine-upstream-findings.md`` and pinned by a test, so when CNA
        carries them itself this becomes redundant rather than wrong.
        """
        if not isinstance(value, PbrMaterial):
            raise TypeError("material must be a PbrMaterial")
        native = value._native()
        handle = _effect_handle(self._effect)
        _support.call(self._APPLY, handle, c.byref(native))
        for slot in PbrTextureSlot:
            texture = value.textures.get(slot)
            _support.call("cna_pbr_effect_set_texture", handle,
                          c.c_uint32(int(slot)),
                          c.c_uint64(_texture_handle(texture, f"textures[{slot.name}]")))
        self._textures = {slot: texture for slot, texture in value.textures.items()
                          if texture is not None}

    def texture(self, slot: PbrTextureSlot):
        """The texture the effect holds in one slot, as CNA reports it.

        Asks CNA rather than trusting the Python reference, and hands back the
        object that was assigned. The handle CNA answers with is the one it
        retains, not a new borrow, so nothing is released here -- measured, like
        everything else about a handle in this package.
        """
        slot = PbrTextureSlot(slot)
        present = c.c_uint8()
        produced = c.c_uint64()
        _support.call("cna_pbr_effect_get_texture", _effect_handle(self._effect),
                      c.c_uint32(int(slot)), c.byref(present), c.byref(produced))
        return self._textures.get(slot) if present.value else None


class PbrEffect(_PbrEffectBase):
    """The effect that renders rigid geometry with a PBR material."""

    __slots__ = ()
    _CREATE = "cna_pbr_effect_create"
    _APPLY = "cna_pbr_effect_apply_material"
    _EXTRACT = "cna_pbr_effect_extract_material"


class SkinnedPbrEffect(_PbrEffectBase):
    """The effect that renders skinned geometry with a PBR material."""

    __slots__ = ()
    _CREATE = "cna_skinned_pbr_effect_create"
    _APPLY = "cna_skinned_pbr_effect_apply_material"
    _EXTRACT = "cna_skinned_pbr_effect_extract_material"


@dataclass(frozen=True)
class GltfMaterialSource:
    """A glTF material's core factors, as the importer read them.

    The bridge turns one of these plus the textures it resolved into a
    :class:`PbrMaterial`. Keeping the two apart is what lets an importer read a
    file without a graphics device and resolve its textures later.
    """

    base_color_factor: Vector4
    metallic_factor: float
    roughness_factor: float
    emissive_factor: Vector3
    normal_scale: float
    occlusion_strength: float
    ior: float
    specular_factor: float
    specular_color_factor: Vector3
    alpha_mode: AlphaMode
    alpha_cutoff: float
    double_sided: bool
    coordinate_sets: Mapping[PbrTextureSlot, int] = field(default_factory=dict)
    transforms: Mapping[PbrTextureSlot, TextureTransform] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "GltfMaterialSource":
        """glTF's own published defaults, read from CNA."""
        value = _engine.CNA_GltfMaterialSourceEXT()
        _support.call("cna_gltf_material_source_ext_init", c.byref(value))
        return cls(
            base_color_factor=_vector4(value.base_color_factor),
            metallic_factor=float(value.metallic_factor),
            roughness_factor=float(value.roughness_factor),
            emissive_factor=_vector(value.emissive_factor),
            normal_scale=float(value.normal_scale),
            occlusion_strength=float(value.occlusion_strength),
            ior=float(value.ior_ext),
            specular_factor=float(value.specular_factor_ext),
            specular_color_factor=_vector(value.specular_color_factor_ext),
            alpha_mode=AlphaMode(int(value.alpha_mode)),
            alpha_cutoff=float(value.alpha_cutoff),
            double_sided=bool(value.double_sided),
            coordinate_sets={slot: int(value.texture_coordinate_sets_ext[int(slot)])
                             for slot in PbrTextureSlot},
            transforms={slot: TextureTransform._from_native(
                value.texture_transforms_ext[int(slot)]) for slot in PbrTextureSlot})

    def _native(self) -> _engine.CNA_GltfMaterialSourceEXT:
        value = _support.in_struct(_engine.CNA_GltfMaterialSourceEXT, 1)
        value.base_color_factor = _native_vector4(self.base_color_factor)
        value.metallic_factor = _support.real(self.metallic_factor, "metallic_factor")
        value.roughness_factor = _support.real(self.roughness_factor, "roughness_factor")
        value.emissive_factor = _native_vector(self.emissive_factor)
        value.normal_scale = _support.real(self.normal_scale, "normal_scale")
        value.occlusion_strength = _support.real(self.occlusion_strength,
                                                 "occlusion_strength")
        value.ior_ext = _support.real(self.ior, "ior")
        value.specular_factor_ext = _support.real(self.specular_factor,
                                                  "specular_factor")
        value.specular_color_factor_ext = _native_vector(self.specular_color_factor)
        value.alpha_mode = int(AlphaMode(self.alpha_mode))
        value.alpha_cutoff = _support.real(self.alpha_cutoff, "alpha_cutoff")
        value.double_sided = 1 if self.double_sided else 0
        for slot in PbrTextureSlot:
            value.texture_coordinate_sets_ext[int(slot)] = _support.checked(
                self.coordinate_sets.get(slot, 0), "int32",
                f"coordinate_sets[{slot.name}]")
            transform = self.transforms.get(slot)
            (transform if transform is not None
             else TextureTransform())._fill(value.texture_transforms_ext[int(slot)])
        return value


@dataclass(frozen=True)
class GltfMaterialExtensionSource:
    """A glTF material's extension factors, as the importer read them."""

    clearcoat_factor: float
    clearcoat_roughness_factor: float
    sheen_color_factor: Vector3
    sheen_roughness_factor: float
    transmission_factor: float
    thickness_factor: float
    attenuation_distance: float
    attenuation_color: Vector3
    iridescence_factor: float
    iridescence_ior: float
    iridescence_thickness_minimum: float
    iridescence_thickness_maximum: float

    @classmethod
    def default(cls) -> "GltfMaterialExtensionSource":
        """glTF's own published extension defaults, read from CNA."""
        value = _engine.CNA_GltfMaterialExtensionSourceEXT()
        _support.call("cna_gltf_material_extension_source_ext_init", c.byref(value))
        return cls(
            clearcoat_factor=float(value.clearcoat_factor_ext),
            clearcoat_roughness_factor=float(value.clearcoat_roughness_factor_ext),
            sheen_color_factor=_vector(value.sheen_color_factor_ext),
            sheen_roughness_factor=float(value.sheen_roughness_factor_ext),
            transmission_factor=float(value.transmission_factor_ext),
            thickness_factor=float(value.thickness_factor_ext),
            attenuation_distance=float(value.attenuation_distance_ext),
            attenuation_color=_vector(value.attenuation_color_ext),
            iridescence_factor=float(value.iridescence_factor_ext),
            iridescence_ior=float(value.iridescence_ior_ext),
            iridescence_thickness_minimum=float(value.iridescence_thickness_minimum_ext),
            iridescence_thickness_maximum=float(value.iridescence_thickness_maximum_ext))

    def _native(self) -> _engine.CNA_GltfMaterialExtensionSourceEXT:
        value = _support.in_struct(_engine.CNA_GltfMaterialExtensionSourceEXT, 1)
        value.clearcoat_factor_ext = _support.real(self.clearcoat_factor,
                                                   "clearcoat_factor")
        value.clearcoat_roughness_factor_ext = _support.real(
            self.clearcoat_roughness_factor, "clearcoat_roughness_factor")
        value.sheen_color_factor_ext = _native_vector(self.sheen_color_factor)
        value.sheen_roughness_factor_ext = _support.real(self.sheen_roughness_factor,
                                                         "sheen_roughness_factor")
        value.transmission_factor_ext = _support.real(self.transmission_factor,
                                                      "transmission_factor")
        value.thickness_factor_ext = _support.real(self.thickness_factor,
                                                   "thickness_factor")
        value.attenuation_distance_ext = _support.real(self.attenuation_distance,
                                                       "attenuation_distance")
        value.attenuation_color_ext = _native_vector(self.attenuation_color)
        value.iridescence_factor_ext = _support.real(self.iridescence_factor,
                                                     "iridescence_factor")
        value.iridescence_ior_ext = _support.real(self.iridescence_ior,
                                                  "iridescence_ior")
        value.iridescence_thickness_minimum_ext = _support.real(
            self.iridescence_thickness_minimum, "iridescence_thickness_minimum")
        value.iridescence_thickness_maximum_ext = _support.real(
            self.iridescence_thickness_maximum, "iridescence_thickness_maximum")
        return value


#: Extension texture slot name -> the native field that carries it.
_EXTENSION_TEXTURE_FIELDS = (
    "clearcoat", "clearcoat_roughness", "clearcoat_normal", "sheen_color",
    "sheen_roughness", "transmission", "thickness", "iridescence",
    "iridescence_thickness",
)


def build_material(source: GltfMaterialSource,
                   textures: Mapping[PbrTextureSlot, object] | None = None
                   ) -> PbrMaterial:
    """Turns a glTF material and its resolved textures into a PBR material.

    Pure: nothing is created and nothing is retained. The textures stay the
    caller's, and the material names them by handle.
    """
    if not isinstance(source, GltfMaterialSource):
        raise TypeError("source must be a GltfMaterialSource")
    supplied = dict(textures or {})
    native_source = source._native()
    native_textures = _initialised(_engine.CNA_GltfMaterialTexturesEXT,
                                   "cna_gltf_material_textures_ext_init")
    for slot in PbrTextureSlot:
        native_textures.slots[int(slot)] = _texture_handle(
            supplied.get(slot), f"textures[{slot.name}]")
    produced = _engine.CNA_PbrMaterialEXT()
    _support.call("cna_gltf_material_bridge_build_material", c.byref(native_source),
                  c.byref(native_textures), c.byref(produced))
    return PbrMaterial._from_native(produced, supplied)


def build_extensions(source: GltfMaterialExtensionSource,
                     destination: PbrMaterialExtensions,
                     textures: Mapping[str, object] | None = None) -> None:
    """Fills ``destination`` from a glTF extension source and its textures.

    ``textures`` is keyed by extension slot name -- ``"clearcoat"``,
    ``"sheen_color"``, ``"iridescence_thickness"`` and the rest; an unknown key
    is refused rather than ignored, because a misspelled slot that silently did
    nothing is exactly the failure this shape invites.
    """
    if not isinstance(source, GltfMaterialExtensionSource):
        raise TypeError("source must be a GltfMaterialExtensionSource")
    if not isinstance(destination, PbrMaterialExtensions):
        raise TypeError("destination must be a PbrMaterialExtensions")
    supplied = dict(textures or {})
    unknown = sorted(set(supplied) - set(_EXTENSION_TEXTURE_FIELDS))
    if unknown:
        raise ValueError(f"unknown extension texture slots: {', '.join(unknown)}; "
                         f"expected any of {', '.join(_EXTENSION_TEXTURE_FIELDS)}")
    native_source = source._native()
    native_textures = _initialised(_engine.CNA_GltfMaterialExtensionTexturesEXT,
                                   "cna_gltf_material_extension_textures_ext_init")
    for name in _EXTENSION_TEXTURE_FIELDS:
        setattr(native_textures, name, _texture_handle(supplied.get(name), name))
    _support.call("cna_gltf_material_bridge_build_extensions", c.byref(native_source),
                  c.byref(native_textures), destination._handle.argument)
    for name, value in supplied.items():
        destination._textures[f"{name}_texture"] = value


def thin_film_iridescence(outside_ior: float, film_ior: float, cos_theta: float,
                          thickness_nm: float, base_f0: Vector3) -> Vector3:
    """The iridescent Fresnel term for a thin film, evaluated on the CPU.

    The same function the shader runs, exposed so a caller can check a material
    against it without drawing. Pure.
    """
    native_f0 = _native_vector(base_f0)
    value = _abi.CNA_Vector3()
    _support.call("cna_thin_film_iridescence_evaluate",
                  c.c_float(_support.real(outside_ior, "outside_ior")),
                  c.c_float(_support.real(film_ior, "film_ior")),
                  c.c_float(_support.real(cos_theta, "cos_theta")),
                  c.c_float(_support.real(thickness_nm, "thickness_nm")),
                  c.byref(native_f0), c.byref(value))
    return _vector(value)


def thin_film_iridescence_glsl() -> str:
    """CNA's own GLSL for the term above, for a caller writing their own shader.

    The point of publishing it is that a custom shader and the CPU evaluation
    agree by construction rather than by two people implementing the same paper.
    """
    return _support.copied_text("cna_thin_film_iridescence_copy_glsl", (),
                                "thin-film GLSL")
