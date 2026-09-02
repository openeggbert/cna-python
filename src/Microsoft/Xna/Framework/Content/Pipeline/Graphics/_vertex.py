"""Vertices, and the channels that describe them.

A ``VertexContent`` is a list of *position indices* plus any number of named
channels running alongside. Storing an index rather than a position is what lets
a mesh share one position between the several vertices that use it -- a cube has
eight corners and twenty-four vertices, because each corner carries three
different normals -- and it is why ``Positions`` is an *indirect* collection: it
reads through the indices into the mesh's own position list, so moving a vertex
moves it for every face that uses it.

Channel names are encoded: ``TEXCOORD0``, ``NORMAL0``, ``BLENDWEIGHT0``. The
encoding is not decorative -- the name is what a vertex declaration's usage and
usage-index are built from, so a channel named anything else cannot become a
vertex element at all. :class:`VertexChannelNames` is both halves of that
encoding, and the qualification checks that they invert each other.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, Iterable, Iterator, TypeVar

from .... import Vector3
from ....Graphics import VertexElementUsage
from ._vectors import PIXEL_KINDS, VERTEX_FORMATS, from_vector4, to_vector4

T = TypeVar("T")

#: XNA's channel-name prefixes, by the vertex-element usage they encode.
_USAGE_NAMES = {
    VertexElementUsage.Position: "POSITION",
    VertexElementUsage.Color: "COLOR",
    VertexElementUsage.TextureCoordinate: "TEXCOORD",
    VertexElementUsage.Normal: "NORMAL",
    VertexElementUsage.Binormal: "BINORMAL",
    VertexElementUsage.Tangent: "TANGENT",
    VertexElementUsage.BlendIndices: "BLENDINDICES",
    VertexElementUsage.BlendWeight: "BLENDWEIGHT",
    VertexElementUsage.Depth: "DEPTH",
    VertexElementUsage.Fog: "FOG",
    VertexElementUsage.PointSize: "PSIZE",
    VertexElementUsage.Sample: "SAMPLE",
    VertexElementUsage.TessellateFactor: "TESSFACTOR",
}
_NAME_USAGES = {name: usage for usage, name in _USAGE_NAMES.items()}


class VertexChannelNames:
    """The encoding between a channel's name and what it means.

    XNA spells the base names as methods rather than constants because most of
    them take a usage index, and a caller almost always wants the encoded form
    rather than the bare word.
    """

    __slots__ = ()

    @staticmethod
    def Normal(usageIndex: int | None = None) -> str:
        return VertexChannelNames.EncodeName(
            VertexElementUsage.Normal, 0 if usageIndex is None else usageIndex)

    @staticmethod
    def Color(usageIndex: int) -> str:
        return VertexChannelNames.EncodeName(VertexElementUsage.Color, usageIndex)

    @staticmethod
    def TextureCoordinate(usageIndex: int) -> str:
        return VertexChannelNames.EncodeName(
            VertexElementUsage.TextureCoordinate, usageIndex)

    @staticmethod
    def Tangent(usageIndex: int) -> str:
        return VertexChannelNames.EncodeName(VertexElementUsage.Tangent, usageIndex)

    @staticmethod
    def Binormal(usageIndex: int) -> str:
        return VertexChannelNames.EncodeName(VertexElementUsage.Binormal, usageIndex)

    @staticmethod
    def Weights(usageIndex: int | None = None) -> str:
        return VertexChannelNames.EncodeName(
            VertexElementUsage.BlendWeight, 0 if usageIndex is None else usageIndex)

    @staticmethod
    def EncodeName(baseName: object, usageIndex: int) -> str:
        """XNA's two overloads: from a base name, or from a usage.

        Both end in the same string, because the usage overload is exactly the
        base-name one with the usage's own spelling substituted in.
        """
        if isinstance(baseName, VertexElementUsage):
            base = _USAGE_NAMES[baseName]
        elif isinstance(baseName, str):
            base = baseName
        else:
            raise TypeError(
                "baseName must be a str or a VertexElementUsage, not "
                f"{type(baseName).__name__}")
        if not isinstance(usageIndex, int) or isinstance(usageIndex, bool):
            raise TypeError(
                f"usageIndex must be an int, not {type(usageIndex).__name__}")
        if usageIndex < 0:
            raise ValueError(f"usageIndex must not be negative, got {usageIndex}")
        return f"{base}{usageIndex}"

    @staticmethod
    def DecodeBaseName(encodedName: str) -> str:
        base, _index = _split(encodedName)
        return base

    @staticmethod
    def DecodeUsageIndex(encodedName: str) -> int:
        _base, index = _split(encodedName)
        return index

    @staticmethod
    def TryDecodeUsage(encodedName: str) -> tuple[bool, VertexElementUsage | None]:
        """XNA's ``out VertexElementUsage`` becomes the second half."""
        base, _index = _split(encodedName)
        usage = _NAME_USAGES.get(base)
        return (usage is not None), usage


VertexChannelNames.__xna_arities__ = {
    "Normal": {0, 1}, "Weights": {0, 1}, "EncodeName": {2},
}


def _split(encoded: str) -> tuple[str, int]:
    if not isinstance(encoded, str):
        raise TypeError(
            f"encodedName must be a str, not {type(encoded).__name__}")
    digits = len(encoded)
    while digits > 0 and encoded[digits - 1].isdigit():
        digits -= 1
    if digits == len(encoded):
        raise ValueError(
            f"{encoded!r} is not an encoded channel name: it has no usage index")
    return encoded[:digits], int(encoded[digits:])


class VertexChannel:
    """One named run of per-vertex data, read as objects.

    Untyped at this level on purpose: a collection of channels holds channels of
    different element types, and something has to be able to hold them all.
    ``VertexChannelOfT`` is the typed view, and every channel really is one.
    """

    __slots__ = ("_name", "_element", "_items")

    def __init__(self, name: str, elementType: type,
                 items: Iterable[object] = ()) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("a vertex channel needs a name")
        if not isinstance(elementType, type):
            raise TypeError(
                f"elementType must be a type, not {type(elementType).__name__}")
        self._name = name
        self._element = elementType
        self._items: list[object] = list(items)

    @property
    def Name(self) -> str:
        return self._name

    @property
    def ElementType(self) -> type:
        return self._element

    @property
    def Count(self) -> int:
        return len(self._items)

    def ReadConvertedContent(self, *, targetType: type) -> list:
        """The channel's data, converted to ``targetType``.

        XNA's generic parameter has no argument to be inferred from, so it is
        spelled as a *keyword* argument: the positional signature stays XNA's --
        no positional parameters at all -- and the type argument is named at the
        call the way C# names it. Everything goes through the unpacked
        ``Vector4``, so any pixel-shaped type converts to any other, and a type
        that is not one of those says so.
        """
        if targetType is self._element:
            return list(self._items)
        if targetType not in PIXEL_KINDS or self._element not in PIXEL_KINDS:
            raise TypeError(
                f"a {self._element.__name__} channel cannot be read as "
                f"{getattr(targetType, '__name__', targetType)}")
        return [from_vector4(targetType, to_vector4(value))
                for value in self._items]

    def Contains(self, value: object) -> bool:
        return self.IndexOf(value) >= 0

    def IndexOf(self, value: object) -> int:
        for index, present in enumerate(self._items):
            if present is value or present == value:
                return index
        return -1

    def CopyTo(self, array, index: int) -> None:
        for offset, value in enumerate(self._items):
            array[index + offset] = value

    def GetEnumerator(self) -> Iterator[object]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[object]:
        return iter(self._items)

    def __getitem__(self, index: int):
        self._check(index)
        return self._items[index]

    def __setitem__(self, index: int, value: object) -> None:
        self._check(index)
        self._items[index] = value

    def __contains__(self, value: object) -> bool:
        return self.IndexOf(value) >= 0

    def __repr__(self) -> str:
        return f"VertexChannel({self._name!r}, {self._element.__name__})"

    def _check(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError(f"index must be an int, not {type(index).__name__}")
        if not 0 <= index < len(self._items):
            raise IndexError(f"index {index} is outside 0..{len(self._items) - 1}")

    # -- what the owning collection uses -------------------------------------

    def _insert(self, index: int, value: object) -> None:
        self._items.insert(index, value)

    def _remove_at(self, index: int) -> None:
        del self._items[index]


class VertexChannelOfT(VertexChannel, Generic[T]):
    """A channel whose element type is known statically as well as at run time."""

    __slots__ = ()


class VertexChannelCollection:
    """Every channel on one ``VertexContent``, in declaration order.

    Insertion order is the wire order: a vertex declaration is built by walking
    this collection, so moving a channel moves the bytes.
    """

    __slots__ = ("_owner", "_channels")

    def __init__(self, owner: "VertexContent") -> None:
        self._owner = owner
        self._channels: list[VertexChannel] = []

    def Add(self, name: str, *rest: object) -> VertexChannel:
        """XNA's two overloads: with an element type, or inferred from the data."""
        return self.Insert(len(self._channels), name, *rest)

    def Insert(self, index: int, name: str, *rest: object) -> VertexChannel:
        element, data = _channel_arguments(name, rest)
        if self.Contains(name):
            raise ValueError(f"a channel named {name!r} is already present")
        values = list(data)
        if len(values) not in (0, self._owner.VertexCount):
            raise ValueError(
                f"channel {name!r} has {len(values)} values and the vertex "
                f"content has {self._owner.VertexCount} vertices")
        if not values:
            values = [_blank(element)] * self._owner.VertexCount
        channel = VertexChannelOfT(name, element, values)
        self._channels.insert(index, channel)
        return channel

    def ConvertChannelContent(self, key: object, *,
                              targetType: type) -> VertexChannel:
        """Replaces a channel with the same data in another element type.

        ``targetType`` is XNA's type argument, keyword-spelled for the same
        reason as :meth:`VertexChannel.ReadConvertedContent`'s.
        """
        index = key if isinstance(key, int) and not isinstance(key, bool) \
            else self.IndexOf(key)
        if index < 0 or index >= len(self._channels):
            raise KeyError(key)
        existing = self._channels[index]
        converted = VertexChannelOfT(
            existing.Name, targetType,
            existing.ReadConvertedContent(targetType=targetType))
        self._channels[index] = converted
        return converted

    def Contains(self, value: object) -> bool:
        return self.IndexOf(value) >= 0

    def IndexOf(self, value: object) -> int:
        for index, channel in enumerate(self._channels):
            if channel is value or channel.Name == value:
                return index
        return -1

    def Remove(self, value: object) -> bool:
        index = self.IndexOf(value)
        if index < 0:
            return False
        del self._channels[index]
        return True

    def RemoveAt(self, index: int) -> None:
        self._check(index)
        del self._channels[index]

    def Clear(self) -> None:
        self._channels.clear()

    def Get(self, key: object) -> VertexChannel:
        """XNA's two overloads, by name or by index."""
        if isinstance(key, int) and not isinstance(key, bool):
            self._check(key)
            return self._channels[key]
        index = self.IndexOf(key)
        if index < 0:
            raise KeyError(key)
        return self._channels[index]

    def GetEnumerator(self) -> Iterator[VertexChannel]:
        return iter(self._channels)

    @property
    def Count(self) -> int:
        return len(self._channels)

    def __len__(self) -> int:
        return len(self._channels)

    def __iter__(self) -> Iterator[VertexChannel]:
        return iter(self._channels)

    def __getitem__(self, key: object) -> VertexChannel:
        return self.Get(key)

    def __setitem__(self, key: object, value: VertexChannel) -> None:
        if not isinstance(value, VertexChannel):
            raise TypeError(
                f"a channel collection holds VertexChannels, not "
                f"{type(value).__name__}")
        index = key if isinstance(key, int) and not isinstance(key, bool) \
            else self.IndexOf(key)
        if index < 0 or index >= len(self._channels):
            raise KeyError(key)
        self._channels[index] = value

    def __contains__(self, value: object) -> bool:
        return self.IndexOf(value) >= 0

    def _check(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError(f"index must be an int, not {type(index).__name__}")
        if not 0 <= index < len(self._channels):
            raise IndexError(
                f"index {index} is outside 0..{len(self._channels) - 1}")

    def _insert_vertex(self, position: int) -> None:
        for channel in self._channels:
            channel._insert(position, _blank(channel.ElementType))

    def _remove_vertex(self, position: int) -> None:
        for channel in self._channels:
            channel._remove_at(position)


VertexChannelCollection.__xna_arities__ = {
    "Add": {2, 3}, "Insert": {3, 4}, "ConvertChannelContent": {1},
    "Contains": {1}, "IndexOf": {1}, "Remove": {1}, "Get": {1},
}


class IndirectPositionCollection:
    """A vertex's positions, read through its position indices.

    Writing through it writes to the *mesh's* position, which is exactly what a
    caller wants: moving a vertex moves the corner, for every face that shares
    it. That is why this is not a list of positions.
    """

    __slots__ = ("_positions", "_indices")

    def __init__(self, positions, indices: VertexChannel) -> None:
        self._positions = positions
        self._indices = indices

    def GetEnumerator(self) -> Iterator[Vector3]:
        return iter(self)

    def IndexOf(self, item: Vector3) -> int:
        for index, value in enumerate(self):
            if value == item:
                return index
        return -1

    def Contains(self, item: Vector3) -> bool:
        return self.IndexOf(item) >= 0

    def CopyTo(self, array, arrayIndex: int) -> None:
        for offset, value in enumerate(self):
            array[arrayIndex + offset] = value

    @property
    def Count(self) -> int:
        return len(self._indices)

    def __len__(self) -> int:
        return len(self._indices)

    def __iter__(self) -> Iterator[Vector3]:
        return (self._positions[index] for index in self._indices)

    def __getitem__(self, index: int) -> Vector3:
        return self._positions[self._indices[index]]

    def __setitem__(self, index: int, value: Vector3) -> None:
        self._positions[self._indices[index]] = value

    def __contains__(self, item: object) -> bool:
        return self.IndexOf(item) >= 0  # type: ignore[arg-type]


class VertexContent:
    """The vertices of one piece of geometry.

    A vertex is a position index plus one value in every channel, and the three
    stay in step because every mutation goes through this object: adding a
    vertex appends a blank to every channel, and removing one removes from every
    channel. A caller cannot leave a channel a different length than the rest,
    which is what a vertex buffer would need to be built at all.
    """

    __slots__ = ("_positions", "_position_indices", "_channels", "_indirect")

    def __init__(self, positions) -> None:
        self._positions = positions
        self._position_indices = VertexChannelOfT("_PositionIndices", int, ())
        self._channels = VertexChannelCollection(self)
        self._indirect = IndirectPositionCollection(
            positions, self._position_indices)

    @property
    def PositionIndices(self) -> VertexChannelOfT:
        return self._position_indices

    @property
    def Positions(self) -> IndirectPositionCollection:
        return self._indirect

    @property
    def Channels(self) -> VertexChannelCollection:
        return self._channels

    @property
    def VertexCount(self) -> int:
        return len(self._position_indices)

    def Add(self, positionIndex: int) -> int:
        index = self.VertexCount
        self.Insert(index, positionIndex)
        return index

    def AddRange(self, positionIndexCollection: Iterable[int]) -> None:
        self.InsertRange(self.VertexCount, positionIndexCollection)

    def Insert(self, index: int, positionIndex: int) -> None:
        self.InsertRange(index, (positionIndex,))

    def InsertRange(self, index: int, positionIndexCollection: Iterable[int]) -> None:
        values = [_position_index(value, len(self._positions))
                  for value in positionIndexCollection]
        if not 0 <= index <= self.VertexCount:
            raise IndexError(f"index {index} is outside 0..{self.VertexCount}")
        for offset, value in enumerate(values):
            self._position_indices._insert(index + offset, value)
            self._channels._insert_vertex(index + offset)

    def RemoveAt(self, index: int) -> None:
        self.RemoveRange(index, 1)

    def RemoveRange(self, index: int, count: int) -> None:
        if count < 0:
            raise ValueError(f"count must not be negative, got {count}")
        if index < 0 or index + count > self.VertexCount:
            raise IndexError(
                f"{index}..{index + count} is outside 0..{self.VertexCount}")
        for _ in range(count):
            self._position_indices._remove_at(index)
            self._channels._remove_vertex(index)

    def CreateVertexBuffer(self):
        """Packs the positions and every channel into interleaved bytes.

        The declaration's first element is always the position, because that is
        what every effect this repository ships expects at offset zero; the
        channels follow in their own order, which is the order they were added.
        """
        from ..Processors import VertexBufferContent, VertexDeclarationContent

        declaration = VertexDeclarationContent()
        declaration._build(self._channels)
        buffer = VertexBufferContent()
        buffer.VertexDeclaration = declaration
        buffer._write(list(self.Positions), list(self._channels))
        return buffer


def _channel_arguments(name: str, rest: tuple[object, ...]
                       ) -> tuple[type, Iterable[object]]:
    if len(rest) == 2:
        element, data = rest
        if not isinstance(element, type):
            raise TypeError(
                f"elementType must be a type, not {type(element).__name__}")
        return element, data
    if len(rest) != 1:
        raise TypeError("no matching channel overload")
    data = list(rest[0])
    if not data:
        raise TypeError(
            f"channel {name!r} was given no element type and no data to infer "
            "one from")
    return type(data[0]), data


def _blank(element: type):
    if element is int:
        return 0
    if element is float:
        return 0.0
    kind = PIXEL_KINDS.get(element)
    if kind is None:
        raise TypeError(
            f"{getattr(element, '__name__', element)!r} is not a channel "
            "element type the content pipeline can create a blank value of")
    from .... import Vector4

    return from_vector4(element, Vector4(0.0, 0.0, 0.0, 0.0))


def _position_index(value: object, count: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"a position index must be an int, not {type(value).__name__}")
    if not 0 <= value < count:
        raise ValueError(
            f"position index {value} is outside 0..{count - 1}")
    return value
