"""The compiled `.cnb` model graph: bones, meshes, parts, materials, skin, morphs.

:class:`CnbModelData` is the neutral, fully decoded description of a compiled
model. It is the seam between the three pieces of the model pipeline and exists
so none of them has to know the others' representations: a compiler front end
produces one, the codec turns it into `.cnb` bytes and back, and a content
manager turns it into a real runtime model. Everything in it is plain data -- no
pointers into a source file, no GPU objects, no graphics device -- which is what
lets the whole encode/decode half be exercised with no display and no renderer.

**This is not a ``Microsoft.Xna.Framework.Graphics.Model``** and does not become
one. External assets -- textures and an effect named by asset path -- are held as
**logical asset names** rather than embedded bytes, so a texture shared by a
hundred models stays one shared asset.

One handle holds the whole graph, and its nodes are reached by index. A bone,
part, mesh, animation or light has no lifetime of its own, and every
cross-reference in the format is already an index, so indexed accessors keep the
Python shape and the file's shape the same.
"""

from __future__ import annotations

import ctypes as c
import os
from dataclasses import dataclass
from enum import IntEnum
from typing import Sequence

from Microsoft.Xna.Framework import Matrix, Vector3

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .animation import ClipTargetSpace, CnbAnimationTrack
from .primitives import CnbKeyframe

__all__ = [
    "MODEL_SCHEMA_VERSION",
    "NO_INDEX",
    "TEXTURE_SLOT_COUNT",
    "CnbBone",
    "CnbMaterial",
    "CnbMesh",
    "CnbModelAnimation",
    "CnbModelData",
    "CnbModelFromCnj",
    "CnbModelInfo",
    "CnbModelLight",
    "CnbMorphInfo",
    "CnbMorphWeightKey",
    "CnbPart",
    "CnbSamplerState",
    "CnbSkeleton",
    "CnbTextureTransform",
    "EffectKind",
    "MaterialTextureSlot",
    "ModelChunk",
    "MorphDeltaStream",
    "MorphKeyStream",
    "SkeletonMatrixSet",
    "build_model_from_cnj",
    "decode_model",
    "encode_model",
]

#: Highest model schema version this CNA generation understands.
MODEL_SCHEMA_VERSION = _abi.CNA_CNB_MODEL_SCHEMA_VERSION
#: Sentinel for "no index", as the format writes it.
NO_INDEX = _abi.CNA_CNB_NO_INDEX
#: Texture slots a compiled material carries per-slot state for.
TEXTURE_SLOT_COUNT = _abi.CNA_CNB_TEXTURE_SLOT_COUNT


class EffectKind(IntEnum):
    """Which effect a compiled mesh part is drawn with."""

    Basic = _abi.CNA_CNB_EFFECT_KIND_BASIC
    Skinned = _abi.CNA_CNB_EFFECT_KIND_SKINNED
    DualTexture = _abi.CNA_CNB_EFFECT_KIND_DUAL_TEXTURE
    Pbr = _abi.CNA_CNB_EFFECT_KIND_PBR
    SkinnedPbr = _abi.CNA_CNB_EFFECT_KIND_SKINNED_PBR
    External = _abi.CNA_CNB_EFFECT_KIND_EXTERNAL


class MaterialTextureSlot(IntEnum):
    """Which of a material's eight texture **names** an operation is addressing.

    **These are not the same slots as the per-slot state arrays, and the
    difference is a real trap.** The names here are CNA's own effect slots and
    include ``DualTextureEffect``'s second layer -- eight of them. The coordinate
    sets, transforms and samplers are seven-element arrays in the importer's own
    slot order, addressed by a plain index below :data:`TEXTURE_SLOT_COUNT`. The
    two index spaces are deliberately kept apart.
    """

    BaseColor = _abi.CNA_CNB_MATERIAL_TEXTURE_BASE_COLOR
    Second = _abi.CNA_CNB_MATERIAL_TEXTURE_SECOND
    Normal = _abi.CNA_CNB_MATERIAL_TEXTURE_NORMAL
    MetallicRoughness = _abi.CNA_CNB_MATERIAL_TEXTURE_METALLIC_ROUGHNESS
    Emissive = _abi.CNA_CNB_MATERIAL_TEXTURE_EMISSIVE
    Occlusion = _abi.CNA_CNB_MATERIAL_TEXTURE_OCCLUSION
    Specular = _abi.CNA_CNB_MATERIAL_TEXTURE_SPECULAR
    SpecularColor = _abi.CNA_CNB_MATERIAL_TEXTURE_SPECULAR_COLOR


class MorphDeltaStream(IntEnum):
    """Which of a morph target's three delta streams, XYZ per vertex."""

    Position = _abi.CNA_CNB_MORPH_DELTA_POSITION
    Normal = _abi.CNA_CNB_MORPH_DELTA_NORMAL
    Tangent = _abi.CNA_CNB_MORPH_DELTA_TANGENT


class MorphKeyStream(IntEnum):
    """Which of a morph weight key's three float streams."""

    Weights = _abi.CNA_CNB_MORPH_KEY_WEIGHTS
    InTangent = _abi.CNA_CNB_MORPH_KEY_IN_TANGENT
    OutTangent = _abi.CNA_CNB_MORPH_KEY_OUT_TANGENT


class SkeletonMatrixSet(IntEnum):
    """Which of a skeleton's three matrix arrays."""

    BindPose = _abi.CNA_CNB_SKELETON_MATRIX_BIND_POSE
    InverseBindPose = _abi.CNA_CNB_SKELETON_MATRIX_INVERSE_BIND_POSE
    RootPrefix = _abi.CNA_CNB_SKELETON_MATRIX_ROOT_PREFIX


class ModelChunk(IntEnum):
    """The eleven chunk identifiers the model schema writes."""

    Header = _abi.CNA_CNB_MODEL_CHUNK_HEADER
    Strings = _abi.CNA_CNB_MODEL_CHUNK_STRINGS
    Bones = _abi.CNA_CNB_MODEL_CHUNK_BONES
    Meshes = _abi.CNA_CNB_MODEL_CHUNK_MESHES
    Materials = _abi.CNA_CNB_MODEL_CHUNK_MATERIALS
    VertexData = _abi.CNA_CNB_MODEL_CHUNK_VERTEX_DATA
    IndexData = _abi.CNA_CNB_MODEL_CHUNK_INDEX_DATA
    MorphData = _abi.CNA_CNB_MODEL_CHUNK_MORPH_DATA
    Skeleton = _abi.CNA_CNB_MODEL_CHUNK_SKELETON
    Animations = _abi.CNA_CNB_MODEL_CHUNK_ANIMATIONS
    Lights = _abi.CNA_CNB_MODEL_CHUNK_LIGHTS


def _matrix_from_floats(values: Sequence[float]) -> Matrix:
    return Matrix(*(float(value) for value in values))


def _matrix_floats(matrix: Matrix) -> tuple[float, ...]:
    return tuple(float(getattr(matrix, f"M{row}{column}"))
                 for row in range(1, 5) for column in range(1, 5))


@dataclass(frozen=True)
class CnbModelInfo:
    """A model's counts and the two flags that are content rather than inference.

    ``applies_gltf_lighting_policy`` travels with the content because a
    glTF-imported model expects the importer's lighting rig, including its "no
    light was declared, so light it by default" fallback, while a hand-authored
    one expects XNA's defaults where ``BasicEffect`` starts unlit. The two look
    different, so which applies is stated rather than guessed from the presence
    of lights.

    ``has_bone_hierarchy`` is equivalent to more than one bone but is stated
    rather than inferred, because the runtime behaviour it selects is a real
    fork: attach meshes to their named bone, or give every mesh its own child of
    the root.
    """

    bone_count: int
    part_count: int
    mesh_count: int
    animation_count: int
    light_count: int
    has_skeleton: bool
    applies_gltf_lighting_policy: bool
    has_bone_hierarchy: bool


@dataclass(frozen=True)
class CnbBone:
    """One node of a compiled model's scene graph.

    ``parent`` is ``-1`` for the root. ``transform`` is the bone-local transform
    as a strict XNA ``Matrix``, which is exactly what the file's sixteen floats
    in ``M11``..``M44`` order mean.
    """

    index: int
    name: str
    parent: int
    transform: Matrix


@dataclass(frozen=True)
class CnbTextureTransform:
    """One texture slot's ``KHR_texture_transform``-shaped UV transform.

    Scale is applied first, then rotation (counter-clockwise, radians), then the
    offset.
    """

    offset_x: float = 0.0
    offset_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0


@dataclass(frozen=True)
class CnbSamplerState:
    """One texture slot's sampler state.

    ``declared`` records *why* the values are what they are: the numbers are
    identical whether the source asset chose them or they are defaults, and a
    source that distinguishes "the author chose repeat" from "the author said
    nothing" needs that difference kept.
    """

    filter: int = 0
    address_u: int = 0
    address_v: int = 0
    declared: bool = False


@dataclass(frozen=True)
class CnbMaterial:
    """A compiled material: its numeric state, its eight texture names, per-slot arrays.

    ``textures`` maps a :class:`MaterialTextureSlot` to the referenced asset's
    **logical name**, omitting slots the material does not use. The three
    per-slot tuples are :data:`TEXTURE_SLOT_COUNT` long and are indexed in the
    importer's own slot order, which is *not* the same space as the texture
    names.
    """

    base_color_factor: tuple[float, float, float, float]
    emissive_factor: tuple[float, float, float]
    specular_color_factor: tuple[float, float, float]
    metallic_factor: float
    roughness_factor: float
    ior: float
    specular_factor: float
    normal_scale: float
    occlusion_strength: float
    alpha_cutoff: float
    alpha_mode: int
    double_sided: bool
    textures: dict
    coordinate_sets: tuple[int, ...]
    transforms: tuple[CnbTextureTransform, ...]
    samplers: tuple[CnbSamplerState, ...]


@dataclass(frozen=True)
class CnbPart:
    """One renderable part: its geometry bytes, its topology and its material.

    ``index_element_size`` is 2 or 4 and is **declared, not inferred**: the
    `.cnj` pipeline derived it from the vertex count, which meant a truncated
    sidecar silently decoded as a shorter mesh.

    ``vertex_bytes`` and ``index_bytes`` are copies of native memory, so for a
    large part reading them repeatedly copies repeatedly.
    """

    index: int
    name: str
    external_effect: str
    vertex_stride: int
    vertex_count: int
    index_count: int
    index_element_size: int
    primitive_topology: int
    primitive_count: int
    effect_kind: EffectKind
    vertex_color_enabled: bool
    unlit: bool
    vertex_bytes: bytes
    index_bytes: bytes
    material: CnbMaterial


@dataclass(frozen=True)
class CnbMorphInfo:
    """A part's morph-target state, without its delta streams, weights or keys."""

    vertex_count: int
    target_count: int
    weight_count: int
    weight_track_key_count: int
    recompute_flat_normals: bool
    weight_track_step_interpolation: bool
    weight_track_cubic_spline: bool


@dataclass(frozen=True)
class CnbMorphWeightKey:
    """One morph weight key: its time and its three float streams.

    ``in_tangents`` and ``out_tangents`` are empty unless the track is
    cubic-spline interpolated.
    """

    time_seconds: float
    weights: tuple[float, ...]
    in_tangents: tuple[float, ...]
    out_tangents: tuple[float, ...]


@dataclass(frozen=True)
class CnbMesh:
    """One mesh: its name, its parent bone and its part indices in draw order.

    ``parent_bone`` is ``-1`` when the model carries no hierarchy.
    """

    index: int
    name: str
    parent_bone: int
    part_indices: tuple[int, ...]


@dataclass(frozen=True)
class CnbSkeleton:
    """The skinning skeleton: one parent per joint and its pose matrices.

    ``root_prefix`` is empty when the source carried no per-joint scene-ancestry
    prefix. The compiled form states that rather than signalling it by leftover
    bytes, which used to make "deliberately absent" and "file truncated" the same
    observation.
    """

    hierarchy: tuple[int, ...]
    bind_pose: tuple[Matrix, ...]
    inverse_bind_pose: tuple[Matrix, ...]
    root_prefix: tuple[Matrix, ...]

    @property
    def joint_count(self) -> int:
        """Number of joints; the hierarchy and both pose arrays are this long."""
        return len(self.hierarchy)


@dataclass(frozen=True)
class CnbModelAnimation:
    """One embedded animation clip: its name, duration, target space and tracks."""

    index: int
    name: str
    duration_seconds: float
    target_space: ClipTargetSpace
    tracks: tuple[CnbAnimationTrack, ...]


@dataclass(frozen=True)
class CnbModelLight:
    """One ``KHR_lights_punctual`` light, already reduced to XNA's directional form.

    ``direction`` is the world-space direction the light travels in;
    ``diffuse_color`` is clamped to 0..1 per channel.
    """

    direction: Vector3
    diffuse_color: Vector3


class CnbModelData:
    """The decoded contents of a ``Model`` `.cnb`.

    Owns native memory, so it has an explicit :meth:`close` and works as a
    context manager. Build one with :meth:`create` and the ``add_*`` methods, or
    get one back from :func:`decode_model` or :func:`build_model_from_cnj`.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle

    @classmethod
    def _adopt(cls, handle: int) -> "CnbModelData":
        return cls(_support.NativeHandle(
            handle, "cna_cnb_model_destroy", "model data"))

    @classmethod
    def create(cls) -> "CnbModelData":
        """An empty model description."""
        return cls._adopt(_support.out_handle("cna_cnb_model_create"))

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the whole graph; no node has a lifetime of its own."""
        self._handle.close()

    def __enter__(self) -> "CnbModelData":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    # --- shape -------------------------------------------------------------

    @property
    def info(self) -> CnbModelInfo:
        """The model's counts and its two content flags."""
        value = _support.out_struct(
            _abi.CNA_CnbModelInfo, _abi.CNA_CNB_MODEL_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_info", self._value)
        return CnbModelInfo(
            bone_count=int(value.bone_count), part_count=int(value.part_count),
            mesh_count=int(value.mesh_count), animation_count=int(value.animation_count),
            light_count=int(value.light_count), has_skeleton=bool(value.has_skeleton),
            applies_gltf_lighting_policy=bool(value.applies_gltf_lighting_policy),
            has_bone_hierarchy=bool(value.has_bone_hierarchy))

    def set_flags(self, *, applies_gltf_lighting_policy: bool,
                  has_bone_hierarchy: bool) -> None:
        """Sets the two flags that are content rather than inference."""
        _support.call("cna_cnb_model_set_flags", self._value,
                      c.c_uint8(1 if applies_gltf_lighting_policy else 0),
                      c.c_uint8(1 if has_bone_hierarchy else 0))

    # --- bones -------------------------------------------------------------

    def add_bone(self, name: str, parent: int, transform: Matrix) -> int:
        """Appends one scene-graph node and returns its index."""
        view, keep = _support.string_view(name, "name")
        floats = _matrix_floats(transform)
        array = (c.c_float * 16)(*floats)
        index = _support.out_u64(
            "cna_cnb_model_add_bone", self._value, view,
            c.c_int32(_support.checked(parent, "int32", "parent")), array)
        del keep
        return index

    def bone(self, index: int) -> CnbBone:
        """The bone at ``index``, with its name and local transform."""
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        value = _support.out_struct(
            _abi.CNA_CnbModelBone, _abi.CNA_CNB_MODEL_BONE_STRUCT_VERSION,
            "cna_cnb_model_get_bone", self._value, position)
        name = _support.sized_text(
            "cna_cnb_model_get_bone_name_size", "cna_cnb_model_copy_bone_name",
            (self._value, position), "bone name")
        return CnbBone(index=int(index), name=name, parent=int(value.parent),
                       transform=_matrix_from_floats(value.transform))

    @property
    def bones(self) -> tuple[CnbBone, ...]:
        """Every bone, in file order."""
        return tuple(self.bone(index) for index in range(self.info.bone_count))

    # --- parts -------------------------------------------------------------

    def add_part(self, *, name: str = "", external_effect: str = "",
                 vertex_stride: int, vertex_count: int, index_count: int,
                 index_element_size: int, primitive_topology: int = 4,
                 primitive_count: int, effect_kind: EffectKind = EffectKind.Basic,
                 vertex_color_enabled: bool = False, unlit: bool = False) -> int:
        """Appends one renderable part and returns its index.

        ``primitive_topology`` defaults to 4, which is triangles and also glTF's
        default. The geometry bytes are set separately with
        :meth:`set_part_vertex_bytes` and :meth:`set_part_index_bytes`.
        """
        info = _abi.CNA_CnbModelPartInfo()
        info.struct_size = c.sizeof(_abi.CNA_CnbModelPartInfo)
        info.struct_version = _abi.CNA_CNB_MODEL_PART_INFO_STRUCT_VERSION
        info.vertex_stride = _support.checked(vertex_stride, "uint32", "vertex_stride")
        info.vertex_count = _support.checked(vertex_count, "uint32", "vertex_count")
        info.index_count = _support.checked(index_count, "uint32", "index_count")
        info.index_element_size = _support.checked(
            index_element_size, "uint32", "index_element_size")
        info.primitive_topology = _support.checked(
            primitive_topology, "uint32", "primitive_topology")
        info.primitive_count = _support.checked(
            primitive_count, "uint32", "primitive_count")
        info.effect_kind = _support.checked(int(effect_kind), "uint32", "effect_kind")
        info.vertex_color_enabled = 1 if vertex_color_enabled else 0
        info.unlit = 1 if unlit else 0
        name_view, keep_name = _support.string_view(name, "name")
        effect_view, keep_effect = _support.string_view(
            external_effect, "external_effect")
        index = _support.out_u64("cna_cnb_model_add_part", self._value, c.byref(info),
                                 name_view, effect_view)
        del keep_name, keep_effect
        return index

    def _part_info(self, index) -> _abi.CNA_CnbModelPartInfo:
        return _support.out_struct(
            _abi.CNA_CnbModelPartInfo, _abi.CNA_CNB_MODEL_PART_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_part", self._value, index)

    def set_part(self, index: int, *, vertex_stride: int | None = None,
                 vertex_count: int | None = None, index_count: int | None = None,
                 index_element_size: int | None = None,
                 primitive_topology: int | None = None,
                 primitive_count: int | None = None,
                 effect_kind: EffectKind | None = None,
                 vertex_color_enabled: bool | None = None,
                 unlit: bool | None = None) -> None:
        """Replaces the numeric state of an existing part, field by field.

        Only the named fields change; every other one is read back from the part
        and written unchanged, so a partial update cannot silently zero the rest.
        """
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        info = self._part_info(position)
        if vertex_stride is not None:
            info.vertex_stride = _support.checked(vertex_stride, "uint32", "vertex_stride")
        if vertex_count is not None:
            info.vertex_count = _support.checked(vertex_count, "uint32", "vertex_count")
        if index_count is not None:
            info.index_count = _support.checked(index_count, "uint32", "index_count")
        if index_element_size is not None:
            info.index_element_size = _support.checked(
                index_element_size, "uint32", "index_element_size")
        if primitive_topology is not None:
            info.primitive_topology = _support.checked(
                primitive_topology, "uint32", "primitive_topology")
        if primitive_count is not None:
            info.primitive_count = _support.checked(
                primitive_count, "uint32", "primitive_count")
        if effect_kind is not None:
            info.effect_kind = _support.checked(int(effect_kind), "uint32", "effect_kind")
        if vertex_color_enabled is not None:
            info.vertex_color_enabled = 1 if vertex_color_enabled else 0
        if unlit is not None:
            info.unlit = 1 if unlit else 0
        _support.call("cna_cnb_model_set_part", self._value, position, c.byref(info))

    def set_part_vertex_bytes(self, index: int, data: bytes) -> None:
        """Sets one part's interleaved vertex bytes; stride times count must match."""
        pointer, count, keep = _support.read_only_bytes(data, "data")
        _support.call("cna_cnb_model_set_part_vertex_bytes", self._value,
                      c.c_uint64(_support.checked(index, "uint64", "index")),
                      pointer, c.c_uint64(count))
        del keep

    def set_part_index_bytes(self, index: int, data: bytes) -> None:
        """Sets one part's index bytes; element size times count must match."""
        pointer, count, keep = _support.read_only_bytes(data, "data")
        _support.call("cna_cnb_model_set_part_index_bytes", self._value,
                      c.c_uint64(_support.checked(index, "uint64", "index")),
                      pointer, c.c_uint64(count))
        del keep

    def part_vertex_bytes(self, index: int) -> bytes:
        """A copy of one part's vertex bytes."""
        return _support.two_call_bytes(
            "cna_cnb_model_copy_part_vertex_bytes",
            (self._value, c.c_uint64(_support.checked(index, "uint64", "index"))))

    def part_index_bytes(self, index: int) -> bytes:
        """A copy of one part's index bytes."""
        return _support.two_call_bytes(
            "cna_cnb_model_copy_part_index_bytes",
            (self._value, c.c_uint64(_support.checked(index, "uint64", "index"))))

    def part(self, index: int) -> CnbPart:
        """One whole part: its numeric state, names, geometry bytes and material."""
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        info = self._part_info(position)
        return CnbPart(
            index=int(index),
            name=_support.sized_text(
                "cna_cnb_model_get_part_name_size", "cna_cnb_model_copy_part_name",
                (self._value, position), "part name"),
            external_effect=_support.sized_text(
                "cna_cnb_model_get_part_external_effect_size",
                "cna_cnb_model_copy_part_external_effect",
                (self._value, position), "part external effect"),
            vertex_stride=int(info.vertex_stride), vertex_count=int(info.vertex_count),
            index_count=int(info.index_count),
            index_element_size=int(info.index_element_size),
            primitive_topology=int(info.primitive_topology),
            primitive_count=int(info.primitive_count),
            effect_kind=EffectKind(int(info.effect_kind)),
            vertex_color_enabled=bool(info.vertex_color_enabled),
            unlit=bool(info.unlit),
            vertex_bytes=self.part_vertex_bytes(index),
            index_bytes=self.part_index_bytes(index),
            material=self.material(index),
        )

    @property
    def parts(self) -> tuple[CnbPart, ...]:
        """Every part, in file order, with its geometry bytes materialised."""
        return tuple(self.part(index) for index in range(self.info.part_count))

    # --- materials ---------------------------------------------------------

    def set_material(self, part: int, material: CnbMaterial) -> None:
        """Replaces a part's whole material: numeric state, names and per-slot state."""
        position = c.c_uint64(_support.checked(part, "uint64", "part"))
        info = _abi.CNA_CnbMaterialInfo()
        info.struct_size = c.sizeof(_abi.CNA_CnbMaterialInfo)
        info.struct_version = _abi.CNA_CNB_MATERIAL_INFO_STRUCT_VERSION
        for index, value in enumerate(material.base_color_factor):
            info.base_color_factor[index] = float(value)
        for index, value in enumerate(material.emissive_factor):
            info.emissive_factor[index] = float(value)
        for index, value in enumerate(material.specular_color_factor):
            info.specular_color_factor[index] = float(value)
        info.metallic_factor = float(material.metallic_factor)
        info.roughness_factor = float(material.roughness_factor)
        info.ior = float(material.ior)
        info.specular_factor = float(material.specular_factor)
        info.normal_scale = float(material.normal_scale)
        info.occlusion_strength = float(material.occlusion_strength)
        info.alpha_cutoff = float(material.alpha_cutoff)
        info.alpha_mode = _support.checked(material.alpha_mode, "uint32", "alpha_mode")
        info.double_sided = 1 if material.double_sided else 0
        _support.call("cna_cnb_model_set_material", self._value, position, c.byref(info))
        for slot, name in material.textures.items():
            self.set_material_texture(part, slot, name)
        for slot in range(TEXTURE_SLOT_COUNT):
            if slot < len(material.coordinate_sets):
                self.set_material_texture_coordinate_set(
                    part, slot, material.coordinate_sets[slot])
            if slot < len(material.transforms):
                self.set_material_texture_transform(part, slot, material.transforms[slot])
            if slot < len(material.samplers):
                self.set_material_sampler(part, slot, material.samplers[slot])

    def set_material_texture(self, part: int, slot: MaterialTextureSlot | int,
                             asset_name: str) -> None:
        """Sets one of the eight material texture **names**, a logical asset name."""
        view, keep = _support.string_view(asset_name, "asset_name")
        _support.call("cna_cnb_model_set_material_texture", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint32(_support.checked(int(slot), "uint32", "slot")), view)
        del keep

    def material_texture(self, part: int, slot: MaterialTextureSlot | int) -> str:
        """One material texture's logical asset name, empty when unused."""
        return _support.sized_text(
            "cna_cnb_model_get_material_texture_size",
            "cna_cnb_model_copy_material_texture",
            (self._value, c.c_uint64(_support.checked(part, "uint64", "part")),
             c.c_uint32(_support.checked(int(slot), "uint32", "slot"))),
            "material texture name")

    def set_material_texture_coordinate_set(self, part: int, slot: int,
                                            coordinate_set: int) -> None:
        """Sets one per-slot UV set index; ``slot`` is below :data:`TEXTURE_SLOT_COUNT`."""
        _support.call("cna_cnb_model_set_material_texture_coordinate_set", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint64(_support.checked(slot, "uint64", "slot")),
                      c.c_uint8(_support.checked(coordinate_set, "uint8",
                                                 "coordinate_set")))

    def material_texture_coordinate_set(self, part: int, slot: int) -> int:
        """One per-slot UV set index."""
        return _support.out_u8(
            "cna_cnb_model_get_material_texture_coordinate_set", self._value,
            c.c_uint64(_support.checked(part, "uint64", "part")),
            c.c_uint64(_support.checked(slot, "uint64", "slot")))

    def set_material_texture_transform(self, part: int, slot: int,
                                       transform: CnbTextureTransform) -> None:
        """Sets one per-slot UV transform."""
        value = _abi.CNA_CnbTextureTransform()
        value.offset_x = float(transform.offset_x)
        value.offset_y = float(transform.offset_y)
        value.scale_x = float(transform.scale_x)
        value.scale_y = float(transform.scale_y)
        value.rotation = float(transform.rotation)
        _support.call("cna_cnb_model_set_material_texture_transform", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint64(_support.checked(slot, "uint64", "slot")),
                      c.byref(value))

    def material_texture_transform(self, part: int, slot: int) -> CnbTextureTransform:
        """One per-slot UV transform."""
        value = _abi.CNA_CnbTextureTransform()
        _support.call("cna_cnb_model_get_material_texture_transform", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint64(_support.checked(slot, "uint64", "slot")),
                      c.byref(value))
        return CnbTextureTransform(
            offset_x=float(value.offset_x), offset_y=float(value.offset_y),
            scale_x=float(value.scale_x), scale_y=float(value.scale_y),
            rotation=float(value.rotation))

    def set_material_sampler(self, part: int, slot: int,
                             sampler: CnbSamplerState) -> None:
        """Sets one per-slot sampler state."""
        value = _abi.CNA_CnbSamplerState()
        value.filter = _support.checked(sampler.filter, "uint32", "filter")
        value.address_u = _support.checked(sampler.address_u, "uint32", "address_u")
        value.address_v = _support.checked(sampler.address_v, "uint32", "address_v")
        value.declared = 1 if sampler.declared else 0
        _support.call("cna_cnb_model_set_material_sampler", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint64(_support.checked(slot, "uint64", "slot")),
                      c.byref(value))

    def material_sampler(self, part: int, slot: int) -> CnbSamplerState:
        """One per-slot sampler state."""
        value = _abi.CNA_CnbSamplerState()
        _support.call("cna_cnb_model_get_material_sampler", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint64(_support.checked(slot, "uint64", "slot")),
                      c.byref(value))
        return CnbSamplerState(
            filter=int(value.filter), address_u=int(value.address_u),
            address_v=int(value.address_v), declared=bool(value.declared))

    def material(self, part: int) -> CnbMaterial:
        """One part's whole material, with every slot read back."""
        position = c.c_uint64(_support.checked(part, "uint64", "part"))
        info = _support.out_struct(
            _abi.CNA_CnbMaterialInfo, _abi.CNA_CNB_MATERIAL_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_material", self._value, position)
        textures = {}
        for slot in MaterialTextureSlot:
            name = self.material_texture(part, slot)
            if name:
                textures[slot] = name
        return CnbMaterial(
            base_color_factor=tuple(float(value) for value in info.base_color_factor),
            emissive_factor=tuple(float(value) for value in info.emissive_factor),
            specular_color_factor=tuple(
                float(value) for value in info.specular_color_factor),
            metallic_factor=float(info.metallic_factor),
            roughness_factor=float(info.roughness_factor),
            ior=float(info.ior), specular_factor=float(info.specular_factor),
            normal_scale=float(info.normal_scale),
            occlusion_strength=float(info.occlusion_strength),
            alpha_cutoff=float(info.alpha_cutoff), alpha_mode=int(info.alpha_mode),
            double_sided=bool(info.double_sided), textures=textures,
            coordinate_sets=tuple(self.material_texture_coordinate_set(part, slot)
                                  for slot in range(TEXTURE_SLOT_COUNT)),
            transforms=tuple(self.material_texture_transform(part, slot)
                             for slot in range(TEXTURE_SLOT_COUNT)),
            samplers=tuple(self.material_sampler(part, slot)
                           for slot in range(TEXTURE_SLOT_COUNT)),
        )

    # --- morph targets -----------------------------------------------------

    def has_morph(self, part: int) -> bool:
        """Whether a part carries morph-target data."""
        return _support.out_bool(
            "cna_cnb_model_has_morph", self._value,
            c.c_uint64(_support.checked(part, "uint64", "part")))

    def set_morph(self, part: int, *, vertex_count: int,
                  recompute_flat_normals: bool = False,
                  weight_track_step_interpolation: bool = False,
                  weight_track_cubic_spline: bool = False) -> None:
        """Gives a part morph data, or replaces the flags and vertex count of what it has.

        The counts are outputs of the routes that build the streams and are not
        settable here; setting them would let the declared shape disagree with
        the data.
        """
        info = _abi.CNA_CnbMorphInfo()
        info.struct_size = c.sizeof(_abi.CNA_CnbMorphInfo)
        info.struct_version = _abi.CNA_CNB_MORPH_INFO_STRUCT_VERSION
        info.vertex_count = _support.checked(vertex_count, "uint32", "vertex_count")
        info.recompute_flat_normals = 1 if recompute_flat_normals else 0
        info.weight_track_step_interpolation = (
            1 if weight_track_step_interpolation else 0)
        info.weight_track_cubic_spline = 1 if weight_track_cubic_spline else 0
        _support.call("cna_cnb_model_set_morph", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.byref(info))

    def clear_morph(self, part: int) -> None:
        """Removes a part's morph data; a part that has none is still a success."""
        _support.call("cna_cnb_model_clear_morph", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")))

    def morph(self, part: int) -> CnbMorphInfo:
        """A part's morph state; raises when the part carries none."""
        value = _support.out_struct(
            _abi.CNA_CnbMorphInfo, _abi.CNA_CNB_MORPH_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_morph", self._value,
            c.c_uint64(_support.checked(part, "uint64", "part")))
        return CnbMorphInfo(
            vertex_count=int(value.vertex_count), target_count=int(value.target_count),
            weight_count=int(value.weight_count),
            weight_track_key_count=int(value.weight_track_key_count),
            recompute_flat_normals=bool(value.recompute_flat_normals),
            weight_track_step_interpolation=bool(value.weight_track_step_interpolation),
            weight_track_cubic_spline=bool(value.weight_track_cubic_spline))

    def add_morph_target(self, part: int) -> int:
        """Appends one empty morph target to a part that already has morph data."""
        return _support.out_u64(
            "cna_cnb_model_add_morph_target", self._value,
            c.c_uint64(_support.checked(part, "uint64", "part")))

    def set_morph_target_deltas(self, part: int, target: int,
                                stream: MorphDeltaStream | int,
                                values: Sequence[float]) -> None:
        """Sets one morph target's delta stream, XYZ per vertex."""
        array, count = _support.float_array(values, "values")
        _support.call("cna_cnb_model_set_morph_target_deltas", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      c.c_uint64(_support.checked(target, "uint64", "target")),
                      c.c_uint32(_support.checked(int(stream), "uint32", "stream")),
                      array, c.c_uint64(count))

    def morph_target_deltas(self, part: int, target: int,
                            stream: MorphDeltaStream | int) -> tuple[float, ...]:
        """One morph target's delta stream."""
        return _support.two_call_floats(
            "cna_cnb_model_copy_morph_target_deltas",
            (self._value, c.c_uint64(_support.checked(part, "uint64", "part")),
             c.c_uint64(_support.checked(target, "uint64", "target")),
             c.c_uint32(_support.checked(int(stream), "uint32", "stream"))))

    def set_morph_weights(self, part: int, values: Sequence[float]) -> None:
        """Sets a part's default blend weights, one per morph target."""
        array, count = _support.float_array(values, "values")
        _support.call("cna_cnb_model_set_morph_weights", self._value,
                      c.c_uint64(_support.checked(part, "uint64", "part")),
                      array, c.c_uint64(count))

    def morph_weights(self, part: int) -> tuple[float, ...]:
        """A part's default blend weights."""
        return _support.two_call_floats(
            "cna_cnb_model_copy_morph_weights",
            (self._value, c.c_uint64(_support.checked(part, "uint64", "part"))))

    def add_morph_weight_key(self, part: int, time_seconds: float,
                             weights: Sequence[float], *,
                             in_tangents: Sequence[float] = (),
                             out_tangents: Sequence[float] = ()) -> int:
        """Appends one key to a part's morph weight track."""
        weight_array, weight_count = _support.float_array(weights, "weights")
        in_array, in_count = _support.float_array(in_tangents, "in_tangents")
        out_array, out_count = _support.float_array(out_tangents, "out_tangents")
        return _support.out_u64(
            "cna_cnb_model_add_morph_weight_key", self._value,
            c.c_uint64(_support.checked(part, "uint64", "part")),
            c.c_double(float(time_seconds)),
            weight_array, c.c_uint64(weight_count),
            in_array, c.c_uint64(in_count),
            out_array, c.c_uint64(out_count))

    def morph_weight_key(self, part: int, key: int) -> CnbMorphWeightKey:
        """One morph weight key: its time and its three streams."""
        position = c.c_uint64(_support.checked(part, "uint64", "part"))
        key_index = c.c_uint64(_support.checked(key, "uint64", "key"))
        info = _support.out_struct(
            _abi.CNA_CnbMorphWeightKeyInfo,
            _abi.CNA_CNB_MORPH_WEIGHT_KEY_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_morph_weight_key", self._value, position, key_index)

        def stream(which: MorphKeyStream) -> tuple[float, ...]:
            return _support.two_call_floats(
                "cna_cnb_model_copy_morph_weight_key_values",
                (self._value, position, key_index, c.c_uint32(int(which))))

        return CnbMorphWeightKey(
            time_seconds=float(info.time_seconds),
            weights=stream(MorphKeyStream.Weights),
            in_tangents=stream(MorphKeyStream.InTangent),
            out_tangents=stream(MorphKeyStream.OutTangent))

    # --- meshes ------------------------------------------------------------

    def add_mesh(self, name: str, parent_bone: int,
                 part_indices: Sequence[int]) -> int:
        """Appends one mesh, naming its parts in draw order."""
        view, keep = _support.string_view(name, "name")
        array, count = _support.uint32_array(part_indices, "part_indices")
        index = _support.out_u64(
            "cna_cnb_model_add_mesh", self._value, view,
            c.c_int32(_support.checked(parent_bone, "int32", "parent_bone")),
            array, c.c_uint64(count))
        del keep
        return index

    def mesh(self, index: int) -> CnbMesh:
        """One mesh: its name, parent bone and part indices."""
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        info = _support.out_struct(
            _abi.CNA_CnbMeshInfo, _abi.CNA_CNB_MESH_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_mesh", self._value, position)
        return CnbMesh(
            index=int(index),
            name=_support.sized_text(
                "cna_cnb_model_get_mesh_name_size", "cna_cnb_model_copy_mesh_name",
                (self._value, position), "mesh name"),
            parent_bone=int(info.parent_bone),
            part_indices=_support.two_call_uint32s(
                "cna_cnb_model_copy_mesh_part_indices", (self._value, position)))

    @property
    def meshes(self) -> tuple[CnbMesh, ...]:
        """Every mesh, in file order."""
        return tuple(self.mesh(index) for index in range(self.info.mesh_count))

    # --- skeleton ----------------------------------------------------------

    def set_skeleton(self, hierarchy: Sequence[int], bind_pose: Sequence[Matrix],
                     inverse_bind_pose: Sequence[Matrix], *,
                     root_prefix: Sequence[Matrix] | None = None) -> None:
        """Sets the skinning skeleton: one parent per joint plus its pose matrices.

        Every array must agree with the joint count. ``root_prefix`` is optional
        and stays *stated* absent rather than inferred from a short array.
        """
        joint_count = len(hierarchy)
        if len(bind_pose) != joint_count or len(inverse_bind_pose) != joint_count:
            raise ValueError("bind_pose and inverse_bind_pose must have one matrix per joint")
        if root_prefix is not None and len(root_prefix) != joint_count:
            raise ValueError("root_prefix must have one matrix per joint when present")
        hierarchy_array, _count = _support.int32_array(hierarchy, "hierarchy")

        def matrices(values):
            flat = [value for matrix in values for value in _matrix_floats(matrix)]
            return _support.float_array(flat, "matrices")[0]

        _support.call(
            "cna_cnb_model_set_skeleton", self._value, hierarchy_array,
            c.c_uint64(joint_count), matrices(bind_pose), matrices(inverse_bind_pose),
            None if root_prefix is None else matrices(root_prefix))

    def clear_skeleton(self) -> None:
        """Removes the skinning skeleton; a model that has none is still a success."""
        _support.call("cna_cnb_model_clear_skeleton", self._value)

    def skeleton(self) -> CnbSkeleton | None:
        """The skinning skeleton, or ``None`` when the model carries none."""
        if not self.info.has_skeleton:
            return None
        info = _support.out_struct(
            _abi.CNA_CnbSkeletonInfo, _abi.CNA_CNB_SKELETON_INFO_STRUCT_VERSION,
            "cna_cnb_model_get_skeleton", self._value)

        def matrices(which: SkeletonMatrixSet) -> tuple[Matrix, ...]:
            flat = _support.two_call_floats(
                "cna_cnb_model_copy_skeleton_matrices",
                (self._value, c.c_uint32(int(which))))
            return tuple(_matrix_from_floats(flat[start:start + 16])
                         for start in range(0, len(flat), 16))

        return CnbSkeleton(
            hierarchy=_support.two_call_int32s(
                "cna_cnb_model_copy_skeleton_hierarchy", (self._value,)),
            bind_pose=matrices(SkeletonMatrixSet.BindPose),
            inverse_bind_pose=matrices(SkeletonMatrixSet.InverseBindPose),
            root_prefix=(matrices(SkeletonMatrixSet.RootPrefix)
                         if info.has_root_prefix else ()))

    # --- animations --------------------------------------------------------

    def add_animation(self, name: str, duration_seconds: float,
                      tracks: Sequence[CnbAnimationTrack], *,
                      target_space: ClipTargetSpace) -> int:
        """Appends one embedded animation clip.

        ``target_space`` has no default: a compiled model may hold either space
        and the two must never be interchanged, so the caller states it.
        """
        from .animation import _clip_descriptor

        descriptor, keep = _clip_descriptor(duration_seconds, tuple(tracks))
        view, keep_name = _support.string_view(name, "name")
        index = _support.out_u64(
            "cna_cnb_model_add_animation", self._value, view, c.byref(descriptor),
            c.c_uint32(_support.checked(int(target_space), "uint32", "target_space")))
        del keep, keep_name
        return index

    def animation(self, index: int) -> CnbModelAnimation:
        """One embedded clip, with every track materialised."""
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        duration = c.c_double()
        track_count = c.c_uint64()
        target_space = c.c_uint32()
        _support.call("cna_cnb_model_get_animation", self._value, position,
                      c.byref(duration), c.byref(track_count), c.byref(target_space))
        tracks = []
        for track_index in range(int(track_count.value)):
            track_position = c.c_uint64(track_index)
            bone_index = c.c_int32()
            keyframe_count = c.c_uint64()
            _support.call("cna_cnb_model_get_animation_track", self._value, position,
                          track_position, c.byref(bone_index), c.byref(keyframe_count))
            frames = _support.two_call_structs(
                _abi.CNA_KeyframeEXT, "cna_cnb_model_copy_animation_keyframes",
                (self._value, position, track_position))
            tracks.append(CnbAnimationTrack(
                bone_index=int(bone_index.value),
                keyframes=tuple(CnbKeyframe._from_native(frame) for frame in frames)))
        return CnbModelAnimation(
            index=int(index),
            name=_support.sized_text(
                "cna_cnb_model_get_animation_name_size",
                "cna_cnb_model_copy_animation_name",
                (self._value, position), "animation name"),
            duration_seconds=float(duration.value),
            target_space=ClipTargetSpace(int(target_space.value)),
            tracks=tuple(tracks))

    @property
    def animations(self) -> tuple[CnbModelAnimation, ...]:
        """Every embedded clip, in file order."""
        return tuple(self.animation(index)
                     for index in range(self.info.animation_count))

    # --- lights ------------------------------------------------------------

    def add_light(self, light: CnbModelLight) -> int:
        """Appends one punctual light, already reduced to XNA's directional form."""
        value = _abi.CNA_CnbModelLight()
        value.direction[0] = float(light.direction.X)
        value.direction[1] = float(light.direction.Y)
        value.direction[2] = float(light.direction.Z)
        value.diffuse_color[0] = float(light.diffuse_color.X)
        value.diffuse_color[1] = float(light.diffuse_color.Y)
        value.diffuse_color[2] = float(light.diffuse_color.Z)
        return _support.out_u64("cna_cnb_model_add_light", self._value, c.byref(value))

    def light(self, index: int) -> CnbModelLight:
        """One punctual light."""
        value = _abi.CNA_CnbModelLight()
        _support.call("cna_cnb_model_get_light", self._value,
                      c.c_uint64(_support.checked(index, "uint64", "index")),
                      c.byref(value))
        return CnbModelLight(
            direction=Vector3(*(float(item) for item in value.direction)),
            diffuse_color=Vector3(*(float(item) for item in value.diffuse_color)))

    @property
    def lights(self) -> tuple[CnbModelLight, ...]:
        """Every punctual light, in file order."""
        return tuple(self.light(index) for index in range(self.info.light_count))

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbModelData closed>"
        info = self.info
        return (f"<CnbModelData bones {info.bone_count} meshes {info.mesh_count} "
                f"parts {info.part_count} animations {info.animation_count}>")


class CnbModelFromCnj:
    """What building a model straight from a `.cnj` produced.

    Holds the model plus the two file lists a build system needs. The model is
    **transferred out** with :meth:`take_model`, which succeeds exactly once:
    afterwards the result keeps none of it, so there is no path to destroying
    the same model twice.
    """

    __slots__ = ("_handle", "_taken")

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle
        self._taken = False

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the result; a model already taken out is unaffected."""
        self._handle.close()

    def __enter__(self) -> "CnbModelFromCnj":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    @property
    def model_taken(self) -> bool:
        """Whether :meth:`take_model` has already transferred the model out."""
        return self._taken

    def take_model(self) -> CnbModelData:
        """Transfers the model out of the result; the caller then owns and closes it.

        Calling this twice raises rather than handing out a second owner of the
        same native model.
        """
        if self._taken:
            raise ValueError("the model has already been taken out of this result")
        handle = _support.out_handle("cna_cnb_model_from_cnj_take_model", self._value)
        self._taken = True
        return CnbModelData._adopt(handle)

    @property
    def absorbed_files(self) -> tuple[str, ...]:
        """The sidecar files whose contents went into the model, in order."""
        count = _support.out_u64(
            "cna_cnb_model_from_cnj_get_absorbed_file_count", self._value)
        return tuple(
            _support.sized_text(
                "cna_cnb_model_from_cnj_get_absorbed_file_size",
                "cna_cnb_model_from_cnj_copy_absorbed_file",
                (self._value, c.c_uint64(index)), "absorbed file")
            for index in range(count))

    @property
    def external_references(self) -> tuple[str, ...]:
        """The assets the model still refers to by logical name, in order."""
        count = _support.out_u64(
            "cna_cnb_model_from_cnj_get_external_reference_count", self._value)
        return tuple(
            _support.sized_text(
                "cna_cnb_model_from_cnj_get_external_reference_size",
                "cna_cnb_model_from_cnj_copy_external_reference",
                (self._value, c.c_uint64(index)), "external reference")
            for index in range(count))

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbModelFromCnj closed>"
        return f"<CnbModelFromCnj taken={self._taken}>"


def encode_model(model: CnbModelData, *, content_name: str = "") -> bytes:
    """Encodes a model graph as a complete `.cnb` byte image."""
    view, keep = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes("cna_cnb_encode_model", (model._value, view))
    del keep
    return result


def decode_model(document) -> CnbModelData:
    """Decodes a model graph from a parsed container."""
    return CnbModelData._adopt(
        _support.out_handle("cna_cnb_decode_model", document._value))


def build_model_from_cnj(cnj_path: "str | os.PathLike[str]", *,
                         content_root: "str | os.PathLike[str] | None" = None
                         ) -> CnbModelFromCnj:
    """Builds a model graph straight from a `.cnj`, without going through `.cnb` bytes.

    Useful to a tool that wants the graph rather than the file -- to inspect it,
    to check its references, or to re-encode it with different settings.
    ``content_root`` is the directory sidecar references resolve against; ``None``
    means the document's own parent directory.
    """
    path_view, keep_path = _support.string_view(os.fspath(cnj_path), "cnj_path")
    root_view, keep_root = _support.string_view(
        "" if content_root is None else os.fspath(content_root), "content_root")
    handle = _support.out_handle(
        "cna_cnb_build_model_from_cnj", path_view, root_view)
    del keep_path, keep_root
    return CnbModelFromCnj(_support.NativeHandle(
        handle, "cna_cnb_model_from_cnj_destroy", "model from cnj"))
