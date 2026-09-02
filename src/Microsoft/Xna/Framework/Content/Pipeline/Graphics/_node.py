"""The scene graph an importer builds and a processor walks.

A ``NodeContent`` is a named transform with children. A ``MeshContent`` is a
node that also has geometry; a ``BoneContent`` is a node that a skinned mesh
weights vertices against. That is the whole hierarchy, and every importer in the
pipeline produces exactly it.

Two things are worth pointing at:

* **Positions belong to the mesh, not to the geometry.** One list per mesh,
  shared by every ``GeometryContent`` under it, which is what lets two materials
  meet along an edge without duplicating the corner.
* **The parent pointer is maintained by the collection, not by the caller.**
  Adding a node to ``Children`` sets its ``Parent``; removing it clears it; and
  adding a node that already has a different parent is refused rather than
  silently stealing it.
"""

from __future__ import annotations

from typing import Iterable

from .... import Matrix, Vector3
from .._collections import ChildCollectionOfT, _Collection
from .._identity import ContentItem
from ._animation import AnimationContentDictionary
from ._material import MaterialContent
from ._vertex import VertexContent


class BoneWeight:
    """One bone's influence on one vertex."""

    __slots__ = ("_bone_name", "_weight")

    def __init__(self, boneName: str = "", weight: float = 0.0) -> None:
        if not isinstance(boneName, str):
            raise TypeError(
                f"boneName must be a str, not {type(boneName).__name__}")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise TypeError(
                f"weight must be a real number, not {type(weight).__name__}")
        self._bone_name = boneName
        self._weight = float(weight)

    @property
    def BoneName(self) -> str:
        return self._bone_name

    @property
    def Weight(self) -> float:
        return self._weight

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, BoneWeight) and other._bone_name == self._bone_name
                and other._weight == self._weight)

    def __hash__(self) -> int:
        return hash((self._bone_name, self._weight))

    def __copy__(self) -> "BoneWeight":
        return BoneWeight(self._bone_name, self._weight)

    def __deepcopy__(self, memo: dict) -> "BoneWeight":
        # A bone weight holds a string and a float, both immutable, so a deep
        # copy has nothing deeper to copy than the shallow one does.
        return BoneWeight(self._bone_name, self._weight)

    def __repr__(self) -> str:
        return f"BoneWeight({self._bone_name!r}, {self._weight})"


BoneWeight.__xna_arities__ = {"__init__": {0, 2}}


class BoneWeightCollection(_Collection[BoneWeight]):
    """Every bone influencing one vertex."""

    __slots__ = ()
    _element_type = BoneWeight

    def NormalizeWeights(self, maxWeights: int | None = None) -> None:
        """Keeps the ``maxWeights`` largest influences and rescales them to sum to one.

        Both halves matter. Dropping the small influences is what makes a mesh
        fit a four-weight skinned effect; rescaling what is left is what stops
        the vertex from shrinking towards the origin once they are gone.

        A vertex with no influences at all is a content error and says so: a
        skinned vertex that no bone moves would collapse to the origin, and
        silently giving it a weight of one on some arbitrary bone would hide
        that in the geometry rather than report it.
        """
        limit = len(self._items) if maxWeights is None else maxWeights
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError(f"maxWeights must be positive, got {maxWeights}")
        if not self._items:
            raise ValueError(
                "a vertex with no bone weights cannot be normalized: nothing "
                "moves it, and inventing an influence would hide that")
        ordered = sorted(self._items, key=lambda weight: -weight.Weight)[:limit]
        total = sum(weight.Weight for weight in ordered)
        if total <= 0.0:
            raise ValueError(
                "a vertex whose bone weights sum to zero cannot be normalized")
        self.ClearItems()
        for weight in ordered:
            self._items.append(BoneWeight(weight.BoneName, weight.Weight / total))


BoneWeightCollection.__xna_arities__ = {
    "NormalizeWeights": {0, 1}, "__init__": {0},
}


class IndexCollection(_Collection[int]):
    """A geometry's triangle indices, three per triangle."""

    __slots__ = ()
    _element_type = int

    def AddRange(self, indices: Iterable[int]) -> None:
        for index in indices:
            if isinstance(index, bool):
                # ``bool`` is an ``int`` in Python, and an index that came from
                # a comparison by accident would silently become 0 or 1.
                raise TypeError("an index must be an int, not bool")
            self.Add(index)


IndexCollection.__xna_arities__ = {"__init__": {0}}


class PositionCollection(_Collection[Vector3]):
    """A mesh's positions, shared by every geometry under it."""

    __slots__ = ()
    _element_type = Vector3


PositionCollection.__xna_arities__ = {"__init__": {0}}


class NodeContent(ContentItem):
    """A named transform in the scene graph."""

    __slots__ = ("_parent", "_transform", "_children", "_animations")

    def __init__(self) -> None:
        super().__init__()
        self._parent: "NodeContent | None" = None
        self._transform = Matrix.Identity
        self._children = NodeContentCollection(self)
        self._animations = AnimationContentDictionary()

    @property
    def Parent(self) -> "NodeContent | None":
        return self._parent

    @property
    def Transform(self) -> Matrix:
        return self._transform

    @Transform.setter
    def Transform(self, value: Matrix) -> None:
        if not isinstance(value, Matrix):
            raise TypeError(f"Transform must be a Matrix, not {type(value).__name__}")
        self._transform = value

    @property
    def AbsoluteTransform(self) -> Matrix:
        """This node's transform composed with every parent's, up to the root.

        Computed rather than cached: a node's transform can change at any point
        in a processor, and a cached absolute transform would be wrong from then
        on with nothing to notice it.
        """
        result = self._transform
        node = self._parent
        while node is not None:
            result = result * node.Transform
            node = node.Parent
        return result

    @property
    def Children(self) -> "NodeContentCollection":
        return self._children

    @property
    def Animations(self) -> AnimationContentDictionary:
        return self._animations


class NodeContentCollection(ChildCollectionOfT["NodeContent", "NodeContent"]):
    """One node's children."""

    __slots__ = ()

    def GetParent(self, child: NodeContent) -> "NodeContent | None":
        return child._parent

    def SetParent(self, child: NodeContent, parent: "NodeContent | None") -> None:
        child._parent = parent


class BoneContent(NodeContent):
    """A node a skinned mesh weights vertices against."""

    __slots__ = ()


class GeometryContent(ContentItem):
    """One material's worth of triangles inside a mesh."""

    __slots__ = ("_parent", "_material", "_indices", "_vertices")

    def __init__(self) -> None:
        super().__init__()
        self._parent: "MeshContent | None" = None
        self._material: MaterialContent | None = None
        self._indices = IndexCollection()
        self._vertices = VertexContent(PositionCollection())

    @property
    def Parent(self) -> "MeshContent | None":
        return self._parent

    @property
    def Material(self) -> MaterialContent | None:
        return self._material

    @Material.setter
    def Material(self, value: MaterialContent | None) -> None:
        if value is not None and not isinstance(value, MaterialContent):
            raise TypeError(
                f"Material must be a MaterialContent or None, not "
                f"{type(value).__name__}")
        self._material = value

    @property
    def Indices(self) -> IndexCollection:
        return self._indices

    @property
    def Vertices(self) -> VertexContent:
        return self._vertices

    def _attach(self, mesh: "MeshContent | None") -> None:
        """Rebinds the vertices onto the owning mesh's position list.

        A geometry created on its own carries a position list of its own, so it
        is usable before it joins a mesh; joining one replaces that list with the
        mesh's, which is what makes positions shared. Any positions already in
        the private list move across, and the indices are rewritten to match.
        """
        self._parent = mesh
        if mesh is None:
            return
        existing = self._vertices._positions
        if existing is mesh.Positions:
            return
        mapping = {}
        for index, position in enumerate(existing):
            mapping[index] = len(mesh.Positions)
            mesh.Positions.Add(position)
        indices = self._vertices.PositionIndices
        rebased = [mapping.get(value, value) for value in indices]
        moved = VertexContent(mesh.Positions)
        for value in rebased:
            moved.Add(value)
        for channel in self._vertices.Channels:
            moved.Channels.Add(channel.Name, channel.ElementType, list(channel))
        self._vertices = moved


class GeometryContentCollection(
        ChildCollectionOfT["MeshContent", GeometryContent]):
    """Every piece of geometry under one mesh."""

    __slots__ = ()

    def GetParent(self, child: GeometryContent) -> "MeshContent | None":
        return child._parent

    def SetParent(self, child: GeometryContent,
                  parent: "MeshContent | None") -> None:
        child._attach(parent)


class MeshContent(NodeContent):
    """A node with geometry, and the positions that geometry indexes."""

    __slots__ = ("_positions", "_geometry")

    def __init__(self) -> None:
        super().__init__()
        self._positions = PositionCollection()
        self._geometry = GeometryContentCollection(self)

    @property
    def Positions(self) -> PositionCollection:
        return self._positions

    @property
    def Geometry(self) -> GeometryContentCollection:
        return self._geometry
