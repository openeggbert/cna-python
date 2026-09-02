"""Building meshes, and the operations every model processor needs.

``MeshBuilder`` is the write-only front door: an importer declares the positions
and the channels once, then streams triangle vertices at it, and the builder
takes care of splitting geometry by material and merging vertices that agree in
every channel. Building a mesh by hand is possible and nobody should have to.

``MeshHelper`` is the read-write toolbox a processor reaches for afterwards.
Its operations are the ones a model actually needs and that an importer usually
cannot provide: normals a format did not store, tangent frames a normal-mapped
effect requires, a winding order the wrong way round.
"""

from __future__ import annotations

import math
from typing import Iterable

from .... import Matrix, Vector2, Vector3
from .._collections import OpaqueDataDictionary
from .._errors import InvalidContentException
from ._material import MaterialContent
from ._node import (
    BoneContent, GeometryContent, MeshContent, NodeContent, PositionCollection,
)
from ._vectors import to_vector4
from ._vertex import VertexChannel, VertexChannelNames

class MeshBuilder:
    """Streams triangles into a :class:`MeshContent`.

    The order is fixed and the builder enforces it: create every position and
    every channel first, then set a material, then add triangle vertices three
    at a time. Adding a position after the first triangle would renumber
    nothing, but adding a *channel* would leave every vertex so far without a
    value in it, so it is refused.
    """

    __slots__ = ("_mesh", "_channels", "_material", "_opaque_data", "_pending",
                 "_geometry", "_swap_winding_order", "_merge_duplicate_positions",
                 "_merge_position_tolerance", "_current", "_started")

    def __init__(self, name: str) -> None:
        self._mesh = MeshContent()
        self._mesh.Name = name
        self._channels: list[tuple[str, type]] = []
        self._material: MaterialContent | None = None
        self._opaque_data = OpaqueDataDictionary()
        self._pending: list[dict[str, object]] = []
        self._geometry: dict[int, GeometryContent] = {}
        self._swap_winding_order = False
        self._merge_duplicate_positions = False
        self._merge_position_tolerance = 1e-12
        self._current: dict[str, object] = {}
        self._started = False

    @staticmethod
    def StartMesh(name: str) -> "MeshBuilder":
        if not isinstance(name, str):
            raise TypeError(f"name must be a str, not {type(name).__name__}")
        return MeshBuilder(name)

    # -- declaring the mesh --------------------------------------------------

    def CreatePosition(self, *args: object) -> int:
        """XNA's two overloads: three floats, or one ``Vector3``.

        Answers the index the position landed at, which is what
        :meth:`AddTriangleVertex` takes. With ``MergeDuplicatePositions`` set, a
        position within the tolerance of one already present answers *that*
        index instead of adding a second -- which is how a format that stores
        each triangle's corners separately still produces a shared mesh.
        """
        if len(args) == 3:
            position = Vector3(*(_real(value, "position") for value in args))
        elif len(args) == 1 and isinstance(args[0], Vector3):
            position = args[0]
        else:
            raise TypeError("no matching CreatePosition overload")
        if self._merge_duplicate_positions:
            tolerance = self._merge_position_tolerance
            for index, present in enumerate(self._mesh.Positions):
                if _within(present, position, tolerance):
                    return index
        self._mesh.Positions.Add(position)
        return self._mesh.Positions.Count - 1

    def CreateVertexChannel(self, usage: str, *, elementType: type) -> int:
        """Declares a channel every vertex will carry.

        ``elementType`` is XNA's type argument, spelled as a keyword because a
        Python call carries no type arguments and there is nothing here to infer
        one from. It is required, exactly as C# requires it: guessing from the
        usage name would be right for the channels this repository happens to
        use and wrong for a ``TEXCOORD`` an artist authored as three-component.
        """
        if self._started:
            raise RuntimeError(
                "a vertex channel must be created before the first triangle "
                "vertex: the vertices already added have no value in it")
        VertexChannelNames.DecodeBaseName(usage)
        if not isinstance(elementType, type):
            raise TypeError(
                f"elementType must be a type, not {type(elementType).__name__}")
        if any(name == usage for name, _kind in self._channels):
            raise ValueError(f"a channel named {usage!r} is already present")
        self._channels.append((usage, elementType))
        return len(self._channels) - 1

    def SetMaterial(self, material: MaterialContent | None) -> None:
        """Every triangle from here on belongs to ``material``'s geometry."""
        if material is not None and not isinstance(material, MaterialContent):
            raise TypeError(
                f"material must be a MaterialContent or None, not "
                f"{type(material).__name__}")
        self._material = material

    def SetOpaqueData(self, opaqueData: OpaqueDataDictionary | None) -> None:
        self._opaque_data = opaqueData if opaqueData is not None \
            else OpaqueDataDictionary()

    def SetVertexChannelData(self, vertexDataIndex: int, channelData: object) -> None:
        """The value the *next* triangle vertex will carry in one channel."""
        if not 0 <= vertexDataIndex < len(self._channels):
            raise IndexError(
                f"channel {vertexDataIndex} is outside "
                f"0..{len(self._channels) - 1}")
        self._current[self._channels[vertexDataIndex][0]] = channelData

    def AddTriangleVertex(self, indexIntoVertexCollection: int) -> None:
        """Adds one corner. Three of these make a triangle."""
        self._started = True
        if not 0 <= indexIntoVertexCollection < self._mesh.Positions.Count:
            raise IndexError(
                f"position index {indexIntoVertexCollection} is outside "
                f"0..{self._mesh.Positions.Count - 1}")
        entry = dict(self._current)
        entry["_position"] = indexIntoVertexCollection
        entry["_material"] = self._material
        self._pending.append(entry)
        self._current = {}

    def FinishMesh(self) -> MeshContent:
        """Turns everything streamed in into geometry, split by material.

        Vertices that agree in their position index *and* every channel become
        one vertex with two indices pointing at it, which is what makes a
        smooth-shaded mesh smaller than its triangle list. Two vertices at the
        same position with different normals stay separate, because they are
        different vertices.
        """
        if len(self._pending) % 3:
            raise InvalidContentException(
                f"{len(self._pending)} triangle vertices is not a whole number "
                "of triangles", self._mesh.Identity)
        for start in range(0, len(self._pending), 3):
            corners = self._pending[start:start + 3]
            if self._swap_winding_order:
                corners = [corners[0], corners[2], corners[1]]
            material = corners[0]["_material"]
            geometry = self._geometry_for(material)
            for corner in corners:
                geometry.Indices.Add(self._vertex_for(geometry, corner))
        mesh = self._mesh
        mesh.OpaqueData.Clear()
        for key, value in self._opaque_data:
            mesh.OpaqueData[key] = value
        self._pending = []
        self._geometry = {}
        return mesh

    # -- knobs ---------------------------------------------------------------

    @property
    def SwapWindingOrder(self) -> bool:
        return self._swap_winding_order

    @SwapWindingOrder.setter
    def SwapWindingOrder(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("SwapWindingOrder must be a bool")
        self._swap_winding_order = value

    @property
    def MergeDuplicatePositions(self) -> bool:
        return self._merge_duplicate_positions

    @MergeDuplicatePositions.setter
    def MergeDuplicatePositions(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("MergeDuplicatePositions must be a bool")
        self._merge_duplicate_positions = value

    @property
    def MergePositionTolerance(self) -> float:
        return self._merge_position_tolerance

    @MergePositionTolerance.setter
    def MergePositionTolerance(self, value: float) -> None:
        tolerance = _real(value, "MergePositionTolerance")
        if tolerance < 0.0:
            raise ValueError(
                f"MergePositionTolerance must not be negative, got {tolerance}")
        self._merge_position_tolerance = tolerance

    @property
    def Name(self) -> str:
        return self._mesh.Name

    @Name.setter
    def Name(self, value: str) -> None:
        self._mesh.Name = value

    # -- internals -----------------------------------------------------------

    def _geometry_for(self, material: MaterialContent | None) -> GeometryContent:
        key = id(material)
        existing = self._geometry.get(key)
        if existing is not None:
            return existing
        geometry = GeometryContent()
        geometry.Material = material
        self._mesh.Geometry.Add(geometry)
        for name, element in self._channels:
            geometry.Vertices.Channels.Add(name, element, ())
        self._geometry[key] = geometry
        return geometry

    def _vertex_for(self, geometry: GeometryContent, corner: dict) -> int:
        position = corner["_position"]
        values = [corner.get(name, _blank_for(element))
                  for name, element in self._channels]
        indices = geometry.Vertices.PositionIndices
        for index in range(geometry.Vertices.VertexCount):
            if indices[index] != position:
                continue
            if all(channel[index] == value
                   for channel, value in zip(geometry.Vertices.Channels, values)):
                return index
        index = geometry.Vertices.Add(position)
        for channel, value in zip(geometry.Vertices.Channels, values):
            channel[index] = value
        return index


MeshBuilder.__xna_arities__ = {
    "__init__": {1}, "CreatePosition": {1, 3}, "CreateVertexChannel": {1},
}


class MeshHelper:
    """The operations a model processor performs on an imported mesh."""

    __slots__ = ()

    @staticmethod
    def CalculateNormals(mesh: MeshContent, overwriteExistingNormals: bool) -> None:
        """Area-weighted vertex normals, from the triangles that share a position.

        Area-weighted rather than uniformly averaged: a corner where one large
        triangle meets three slivers should mostly face the way the large one
        does, and the cross product's own length *is* twice the triangle's area,
        so weighting is what you get by not normalising too early.

        Normals are accumulated per *position*, not per vertex, so two vertices
        at the same corner of two different geometries -- the seam between two
        materials -- come out with the same normal and the seam does not show.
        """
        _require_mesh(mesh)
        if type(overwriteExistingNormals) is not bool:
            raise TypeError("overwriteExistingNormals must be a bool")
        name = VertexChannelNames.Normal()
        totals = [Vector3(0.0, 0.0, 0.0)] * mesh.Positions.Count
        for geometry in mesh.Geometry:
            indices = geometry.Vertices.PositionIndices
            triangle_indices = list(geometry.Indices)
            for start in range(0, len(triangle_indices) - 2, 3):
                corners = [indices[triangle_indices[start + offset]]
                           for offset in range(3)]
                first = mesh.Positions[corners[1]] - mesh.Positions[corners[0]]
                second = mesh.Positions[corners[2]] - mesh.Positions[corners[0]]
                weighted = Vector3.Cross(first, second)
                for corner in corners:
                    totals[corner] = totals[corner] + weighted
        for geometry in mesh.Geometry:
            channels = geometry.Vertices.Channels
            if channels.Contains(name):
                if not overwriteExistingNormals:
                    continue
                channels.Remove(name)
            channels.Add(name, Vector3,
                         [_normalized(totals[index])
                          for index in geometry.Vertices.PositionIndices])

    @staticmethod
    def CalculateTangentFrames(mesh: MeshContent, textureCoordinateChannelName: str,
                               tangentChannelName: str | None,
                               binormalChannelName: str | None) -> None:
        """The tangent basis a normal-mapped effect needs.

        The tangent points along increasing *u* and the binormal along
        increasing *v*, both projected to be perpendicular to the vertex normal
        -- Gram-Schmidt, which is what makes the three vectors a basis rather
        than three directions that happen to be nearby.

        A degenerate triangle in texture space -- three corners on one *uv*
        point, which is what an untextured face imported with a texture channel
        looks like -- contributes nothing rather than a division by zero.
        """
        _require_mesh(mesh)
        if tangentChannelName is None and binormalChannelName is None:
            raise ValueError(
                "CalculateTangentFrames was asked for neither a tangent channel "
                "nor a binormal one")
        normal_name = VertexChannelNames.Normal()
        for geometry in mesh.Geometry:
            channels = geometry.Vertices.Channels
            if not channels.Contains(textureCoordinateChannelName):
                raise InvalidContentException(
                    f"geometry has no {textureCoordinateChannelName} channel to "
                    "build a tangent frame from", geometry.Identity)
            if not channels.Contains(normal_name):
                raise InvalidContentException(
                    "geometry has no normals; call CalculateNormals first",
                    geometry.Identity)
            texture = list(channels.Get(textureCoordinateChannelName))
            normals = list(channels.Get(normal_name))
            positions = list(geometry.Vertices.Positions)
            count = geometry.Vertices.VertexCount
            tangents = [Vector3(0.0, 0.0, 0.0)] * count
            binormals = [Vector3(0.0, 0.0, 0.0)] * count
            triangle_indices = list(geometry.Indices)
            for start in range(0, len(triangle_indices) - 2, 3):
                corners = triangle_indices[start:start + 3]
                tangent, binormal = _triangle_frame(
                    [positions[index] for index in corners],
                    [texture[index] for index in corners])
                if tangent is None:
                    continue
                for corner in corners:
                    tangents[corner] = tangents[corner] + tangent
                    binormals[corner] = binormals[corner] + binormal
            for index in range(count):
                normal = normals[index]
                tangents[index] = _orthogonalized(tangents[index], normal)
                binormals[index] = _orthogonalized(binormals[index], normal)
            if tangentChannelName:
                _replace(channels, tangentChannelName, Vector3, tangents)
            if binormalChannelName:
                _replace(channels, binormalChannelName, Vector3, binormals)

    @staticmethod
    def OptimizeForCache(mesh: MeshContent) -> None:
        """Reorders vertices so that a triangle's corners are near each other.

        A vertex cache holds the last handful of transformed vertices, so a
        triangle list that walks its vertices in order re-uses them and one that
        jumps around does not. Renumbering the vertices into first-use order is
        the part of that a content pipeline can do without knowing the hardware:
        it makes the reference pattern local, and it is exactly reversible, so
        nothing about the mesh changes except the numbering.
        """
        _require_mesh(mesh)
        for geometry in mesh.Geometry:
            order: list[int] = []
            seen: dict[int, int] = {}
            for index in geometry.Indices:
                if index not in seen:
                    seen[index] = len(order)
                    order.append(index)
            if len(order) != geometry.Vertices.VertexCount:
                # A vertex no triangle uses would be dropped by renumbering,
                # which is a different operation than the one asked for.
                for index in range(geometry.Vertices.VertexCount):
                    if index not in seen:
                        seen[index] = len(order)
                        order.append(index)
            _renumber(geometry, order, seen)

    @staticmethod
    def SwapWindingOrder(mesh: MeshContent) -> None:
        """Reverses every triangle, turning the mesh inside out.

        Which is what an importer needs when the source format's coordinate
        system is the mirror of XNA's: mirroring the positions alone would leave
        every triangle facing backwards.
        """
        _require_mesh(mesh)
        for geometry in mesh.Geometry:
            indices = list(geometry.Indices)
            geometry.Indices.Clear()
            for start in range(0, len(indices) - 2, 3):
                first, second, third = indices[start:start + 3]
                geometry.Indices.AddRange((first, third, second))

    @staticmethod
    def MergeDuplicatePositions(mesh: MeshContent, tolerance: float) -> None:
        """Collapses positions within ``tolerance`` of each other into one."""
        _require_mesh(mesh)
        limit = _real(tolerance, "tolerance")
        if limit < 0.0:
            raise ValueError(f"tolerance must not be negative, got {limit}")
        kept: list[Vector3] = []
        mapping: list[int] = []
        for position in mesh.Positions:
            for index, present in enumerate(kept):
                if _within(present, position, limit):
                    mapping.append(index)
                    break
            else:
                mapping.append(len(kept))
                kept.append(position)
        if len(kept) == mesh.Positions.Count:
            return
        mesh.Positions.Clear()
        for position in kept:
            mesh.Positions.Add(position)
        for geometry in mesh.Geometry:
            indices = geometry.Vertices.PositionIndices
            for index in range(len(indices)):
                indices[index] = mapping[indices[index]]

    @staticmethod
    def MergeDuplicateVertices(target) -> None:
        """XNA's two overloads: a whole mesh, or one geometry.

        Two vertices merge when their position index and every channel agree.
        Comparing the position *index* rather than the position is deliberate:
        two corners that happen to coincide are only the same vertex if they
        are the same corner, and :meth:`MergeDuplicatePositions` is the
        operation that decides that.
        """
        if isinstance(target, MeshContent):
            for geometry in target.Geometry:
                MeshHelper.MergeDuplicateVertices(geometry)
            return
        if not isinstance(target, GeometryContent):
            raise TypeError(
                "MergeDuplicateVertices takes a MeshContent or a "
                f"GeometryContent, not {type(target).__name__}")
        geometry = target
        channels = list(geometry.Vertices.Channels)
        indices = geometry.Vertices.PositionIndices
        signatures: dict[tuple, int] = {}
        order: list[int] = []
        mapping: dict[int, int] = {}
        for index in range(geometry.Vertices.VertexCount):
            signature = (indices[index],) + tuple(
                _hashable(channel[index]) for channel in channels)
            existing = signatures.get(signature)
            if existing is None:
                signatures[signature] = len(order)
                mapping[index] = len(order)
                order.append(index)
            else:
                mapping[index] = existing
        if len(order) == geometry.Vertices.VertexCount:
            return
        _renumber(geometry, order, mapping)

    @staticmethod
    def TransformScene(scene: NodeContent, transform: Matrix) -> None:
        """Applies ``transform`` to a subtree, positions and normals alike.

        The positions go through the whole matrix; the direction channels --
        normals, tangents, binormals -- go through its rotation only and are
        renormalised, because a translation moves a point and does nothing to a
        direction.
        """
        if not isinstance(scene, NodeContent):
            raise TypeError(
                f"scene must be a NodeContent, not {type(scene).__name__}")
        if not isinstance(transform, Matrix):
            raise TypeError(
                f"transform must be a Matrix, not {type(transform).__name__}")
        for node in _walk(scene):
            if isinstance(node, MeshContent):
                positions = list(node.Positions)
                node.Positions.Clear()
                for position in positions:
                    node.Positions.Add(Vector3.Transform(position, transform))
                for geometry in node.Geometry:
                    for channel in geometry.Vertices.Channels:
                        base = VertexChannelNames.DecodeBaseName(channel.Name)
                        if base not in ("NORMAL", "TANGENT", "BINORMAL"):
                            continue
                        for index in range(len(channel)):
                            channel[index] = _normalized(
                                Vector3.TransformNormal(channel[index], transform))
            else:
                node.Transform = node.Transform * transform

    @staticmethod
    def FindSkeleton(node: NodeContent) -> BoneContent | None:
        """The root bone of the skeleton ``node`` belongs to, if it has one.

        Searched upwards first and then down, which is XNA's order and the one
        that finds the skeleton a mesh is skinned to rather than some other
        skeleton in the same scene.
        """
        if not isinstance(node, NodeContent):
            raise TypeError(
                f"node must be a NodeContent, not {type(node).__name__}")
        current: NodeContent | None = node
        while current is not None:
            if isinstance(current, BoneContent):
                root = current
                while isinstance(root.Parent, BoneContent):
                    root = root.Parent
                return root
            found = _find_bone(current)
            if found is not None:
                return found
            current = current.Parent
        return None

    @staticmethod
    def FlattenSkeleton(skeleton: BoneContent) -> list[BoneContent]:
        """A skeleton in depth-first order, which is the order a model writes it.

        The order is the contract: a ``ModelContent``'s bone indices are indices
        into this list, so a processor that flattened differently would produce
        a model whose animations move the wrong bones.
        """
        if not isinstance(skeleton, BoneContent):
            raise TypeError(
                f"skeleton must be a BoneContent, not {type(skeleton).__name__}")
        result: list[BoneContent] = []
        pending = [skeleton]
        while pending:
            bone = pending.pop()
            result.append(bone)
            pending.extend(reversed(
                [child for child in bone.Children if isinstance(child, BoneContent)]))
        return result


MeshHelper.__xna_arities__ = {"MergeDuplicateVertices": {1}}


# -- helpers ------------------------------------------------------------------


def _require_mesh(mesh: object) -> None:
    if not isinstance(mesh, MeshContent):
        raise TypeError(f"mesh must be a MeshContent, not {type(mesh).__name__}")


def _real(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{what} must be a real number, not {type(value).__name__}")
    return float(value)


def _within(first: Vector3, second: Vector3, tolerance: float) -> bool:
    return (abs(first.X - second.X) <= tolerance
            and abs(first.Y - second.Y) <= tolerance
            and abs(first.Z - second.Z) <= tolerance)


def _normalized(value: Vector3) -> Vector3:
    length = math.sqrt(value.X * value.X + value.Y * value.Y + value.Z * value.Z)
    if length <= 0.0:
        # A vertex no triangle touched, or one whose triangles cancelled out.
        # Zero is the honest answer: there is no direction to report.
        return Vector3(0.0, 0.0, 0.0)
    return Vector3(value.X / length, value.Y / length, value.Z / length)


def _orthogonalized(value: Vector3, normal: Vector3) -> Vector3:
    projection = Vector3.Dot(value, normal)
    return _normalized(Vector3(value.X - normal.X * projection,
                               value.Y - normal.Y * projection,
                               value.Z - normal.Z * projection))


def _triangle_frame(positions: list[Vector3], texture: list
                    ) -> tuple[Vector3 | None, Vector3 | None]:
    first = positions[1] - positions[0]
    second = positions[2] - positions[0]
    zero = _uv(texture[0])
    du1, dv1 = _uv(texture[1])[0] - zero[0], _uv(texture[1])[1] - zero[1]
    du2, dv2 = _uv(texture[2])[0] - zero[0], _uv(texture[2])[1] - zero[1]
    determinant = du1 * dv2 - du2 * dv1
    if determinant == 0.0:
        return None, None
    scale = 1.0 / determinant
    tangent = Vector3((dv2 * first.X - dv1 * second.X) * scale,
                      (dv2 * first.Y - dv1 * second.Y) * scale,
                      (dv2 * first.Z - dv1 * second.Z) * scale)
    binormal = Vector3((du1 * second.X - du2 * first.X) * scale,
                       (du1 * second.Y - du2 * first.Y) * scale,
                       (du1 * second.Z - du2 * first.Z) * scale)
    return tangent, binormal


def _uv(value: object) -> tuple[float, float]:
    if isinstance(value, Vector2):
        return value.X, value.Y
    unpacked = to_vector4(value)
    return unpacked.X, unpacked.Y


def _replace(channels, name: str, element: type, values: list) -> None:
    if channels.Contains(name):
        channels.Remove(name)
    channels.Add(name, element, values)


def _renumber(geometry: GeometryContent, order: list[int], mapping) -> None:
    """Rebuilds a geometry's vertices in ``order``, rewriting its indices."""
    channels = [(channel.Name, channel.ElementType, list(channel))
                for channel in geometry.Vertices.Channels]
    indices = list(geometry.Vertices.PositionIndices)
    triangles = list(geometry.Indices)
    vertices = geometry.Vertices
    vertices.RemoveRange(0, vertices.VertexCount)
    vertices.Channels.Clear()
    for old in order:
        vertices.Add(indices[old])
    for name, element, values in channels:
        vertices.Channels.Add(name, element, [values[old] for old in order])
    geometry.Indices.Clear()
    geometry.Indices.AddRange(mapping[index] for index in triangles)


def _hashable(value: object):
    if isinstance(value, (int, float, str, bytes)):
        return value
    unpacked = to_vector4(value)
    return (unpacked.X, unpacked.Y, unpacked.Z, unpacked.W)


def _blank_for(element: type):
    from ._vertex import _blank

    return _blank(element)


def _walk(node: NodeContent) -> Iterable[NodeContent]:
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(current.Children)


def _find_bone(node: NodeContent) -> BoneContent | None:
    for child in node.Children:
        if isinstance(child, BoneContent):
            return child
        found = _find_bone(child)
        if found is not None:
            return found
    return None
