"""The serializers the intermediate format ships with.

Three shapes. A **scalar** is written as text and parsed back -- a number, a
string, a vector written as its components separated by spaces, which is XNA's
spelling and is why ``<DiffuseColor>1 0 0</DiffuseColor>`` is one element.
A **collection** writes an ``<Item>`` per entry. Everything else is
**reflective**: every public property with a setter is written as an element
named after it, and read back the same way.

Reflection is what makes the format work for the pipeline's own types without a
serializer per type, and it is also what makes it work for a caller's types. A
property that should not be written says so with a
``ContentSerializerIgnoreAttribute``, exactly as it does in XNA.
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Callable
from xml.etree import ElementTree

from ..... import Color, Matrix, Point, Quaternion, Rectangle, Vector2, Vector3, Vector4
from .... import (
    ContentSerializerAttribute, ContentSerializerIgnoreAttribute,
)
from ..._collections import NamedValueDictionaryOfT, _Collection
from ..._errors import InvalidContentException
from ._intermediate import ContentTypeSerializer

#: Where a property records that it must not be serialized.
_IGNORED = "_xna_content_serializer_ignored"


class _ScalarSerializer(ContentTypeSerializer):
    """A value written as the text of its own element."""

    __slots__ = ("_to_text", "_from_text")

    def __init__(self, targetType: type, xmlTypeName: str,
                 to_text: Callable[[Any], str],
                 from_text: Callable[[str], Any]) -> None:
        super().__init__(targetType, xmlTypeName)
        self._to_text = to_text
        self._from_text = from_text

    def Serialize(self, output, value: object,
                  format: ContentSerializerAttribute) -> None:
        output._text(self._to_text(value))

    def Deserialize(self, input, format: ContentSerializerAttribute,
                    existingInstance: object) -> object:
        return self._from_text((input._element.text or "").strip())

    def ObjectIsEmpty(self, value: object) -> bool:
        return value is None


class _CollectionSerializer(ContentTypeSerializer):
    """A list-shaped value, written one ``<Item>`` per entry."""

    __slots__ = ("_build",)

    def __init__(self, targetType: type, xmlTypeName: str,
                 build: Callable[[list], Any]) -> None:
        super().__init__(targetType, xmlTypeName)
        self._build = build

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return True

    def Serialize(self, output, value: object,
                  format: ContentSerializerAttribute) -> None:
        item = ContentSerializerAttribute()
        item.ElementName = format.CollectionItemName or "Item"
        # A set has no order of its own, and a file that came out different
        # every time would defeat the build cache that compares these texts and
        # would make two identical projects diff.
        entries = sorted(value) if isinstance(value, (set, frozenset)) else value
        for entry in entries:
            output.WriteObject(entry, item)

    def Deserialize(self, input, format: ContentSerializerAttribute,
                    existingInstance: object) -> object:
        name = format.CollectionItemName or "Item"
        values = []
        for element in input._element.findall(name):
            values.append(input._read_element(
                element, ContentSerializerAttribute(), None, None))
        if existingInstance is not None:
            add = getattr(existingInstance, "Add", None) or existingInstance.add
            for value in values:
                add(value)
            return existingInstance
        return self._build(values)

    def ObjectIsEmpty(self, value: object) -> bool:
        return not len(value)

    def ScanChildren(self, serializer, callback, value: object) -> None:
        for entry in value:
            if entry is not None:
                callback(serializer.GetTypeSerializer(type(entry)), entry)


class _DictionarySerializer(ContentTypeSerializer):
    """A ``NamedValueDictionary``, written one element per key."""

    __slots__ = ()

    def Deserialize(self, input, format: ContentSerializerAttribute,
                    existingInstance: object) -> object:
        target = existingInstance if existingInstance is not None \
            else self.TargetType()
        for element in list(input._element):
            target[element.tag] = input._read_element(
                element, ContentSerializerAttribute(), None, None)
        return target

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return True

    def Serialize(self, output, value: object,
                  format: ContentSerializerAttribute) -> None:
        for key in sorted(value.Keys):
            item = ContentSerializerAttribute()
            item.ElementName = key
            output.WriteObject(value[key], item)

    def ObjectIsEmpty(self, value: object) -> bool:
        return not len(value)

    def ScanChildren(self, serializer, callback, value: object) -> None:
        for key in value.Keys:
            entry = value[key]
            if entry is not None:
                callback(serializer.GetTypeSerializer(type(entry)), entry)


class _ReflectiveSerializer(ContentTypeSerializer):
    """A type's serialized state, as one element per property.

    Which properties those are is the whole of the rule, and it is XNA's: a
    property a caller can *set*, and a property whose value can be read *into*
    -- a collection or a dictionary the type owns and hands out. Everything else
    is derived: a ``Count`` written into a file would be read back and thrown
    away, or worse, disagree with what follows it.

    Each property's declared type is resolved once, from the getter's return
    annotation, and it is what lets an element leave its ``Type`` attribute out:
    a ``Vector3`` in a ``Vector3`` property says nothing the reader does not
    already know, and a file full of redundant attributes is a file nobody wants
    to edit by hand.
    """

    __slots__ = ("_properties", "_declared")

    def __init__(self, targetType: type) -> None:
        super().__init__(targetType, targetType.__name__)
        self._properties = _serializable_properties(targetType)
        self._declared = {name: _declared_type(targetType, member)
                          for name, member in self._properties}

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return True

    def Serialize(self, output, value: object,
                  format: ContentSerializerAttribute) -> None:
        for name, member in self._properties:
            entry = getattr(value, name)
            if entry is None:
                continue
            item = ContentSerializerAttribute()
            item.ElementName = name
            item.Optional = True
            # ``FlattenContent`` is what suppresses the Type attribute, and the
            # declared type is exactly when it may be suppressed.
            item.FlattenContent = type(entry) is self._declared.get(name)
            output.WriteObject(entry, item)

    def Deserialize(self, input, format: ContentSerializerAttribute,
                    existingInstance: object) -> object:
        target = existingInstance if existingInstance is not None \
            else _construct(self, input)
        for name, member in self._properties:
            element = input._element.find(name)
            if element is None:
                continue
            existing = getattr(target, name, None)
            into = existing if _reads_into_existing(input, existing) else None
            serializer = None
            if element.get("Type") is None:
                declared = self._declared.get(name)
                if declared is None:
                    raise InvalidContentException(
                        f"<{name}> has no Type attribute and "
                        f"{self.TargetType.__name__}.{name} declares no type, "
                        "so nothing says what it holds")
                serializer = input.Serializer.GetTypeSerializer(declared)
            value = input._read_element(
                element, ContentSerializerAttribute(), serializer, into)
            if member.fset is not None:
                setattr(target, name, value)
        return target

    def ScanChildren(self, serializer, callback, value: object) -> None:
        for name, _member in self._properties:
            entry = getattr(value, name)
            if entry is not None:
                callback(serializer.GetTypeSerializer(type(entry)), entry)


def _declared_type(owner: type, member: property) -> type | None:
    """The property's declared type, from its getter's return annotation.

    ``None`` when it cannot be resolved -- a forward reference to something not
    imported, or an annotation that is not a type at all. That is not a failure:
    it means the element carries its ``Type`` attribute, which is what a file
    written before annotations existed would look like anyway.
    """
    import typing

    getter = member.fget
    if getter is None:
        return None
    try:
        hints = typing.get_type_hints(getter)
    except Exception:  # noqa: BLE001 - an unresolvable annotation is not an error
        return None
    annotation = hints.get("return")
    if isinstance(annotation, type):
        return annotation
    origin = typing.get_origin(annotation)
    if isinstance(origin, type) and origin not in (typing.Union,):
        # ``set[str]`` and ``list[int]`` are generic aliases rather than types:
        # what they *are* is the origin, and that is what decides whether the
        # value can be read into.
        return origin
    candidates = [value for value in typing.get_args(annotation)
                  if isinstance(value, type) and value is not type(None)]
    return candidates[0] if len(candidates) == 1 else None


def _reads_into_existing(input, existing: object) -> bool:
    if existing is None:
        return False
    try:
        serializer = input.Serializer.GetTypeSerializer(type(existing))
    except Exception:  # noqa: BLE001 - an unknown type simply is not one
        return False
    return serializer.CanDeserializeIntoExistingObject


def _construct(serializer: "_ReflectiveSerializer", input):
    """Builds a fresh instance, or says why it cannot.

    A constructor with required arguments is met halfway: the *file* holds the
    values, under the names of the properties they set, so the arguments are
    taken from there. That is what lets a ``FontDescription`` -- whose
    constructor requires a name, a size and a spacing -- be read back at all,
    and it is exactly what a caller would otherwise have to write by hand.

    An argument the file does not carry is a content error, and says which.
    """
    target = serializer.TargetType
    try:
        return target()
    except TypeError:
        pass
    import inspect

    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError) as error:  # pragma: no cover - exotic types
        raise InvalidContentException(
            f"{target.__name__} cannot be deserialized: {error}") from error
    arguments = []
    for name, parameter in signature.parameters.items():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        property_name = _capitalised(name)
        element = input._element.find(property_name)
        if element is None:
            if parameter.default is not parameter.empty:
                continue
            raise InvalidContentException(
                f"{target.__name__} cannot be deserialized: its constructor "
                f"needs {name!r} and the file has no <{property_name}> "
                "element to take it from")
        declared = serializer._declared.get(property_name)
        inner = None if declared is None \
            else input.Serializer.GetTypeSerializer(declared)
        arguments.append(input._read_element(
            element, ContentSerializerAttribute(), inner, None))
    try:
        return target(*arguments)
    except Exception as error:  # noqa: BLE001 - reported as content
        raise InvalidContentException(
            f"{target.__name__} cannot be deserialized: {error}") from error


def _capitalised(name: str) -> str:
    """A constructor parameter's name, as the property it sets is spelled.

    XNA's constructors take ``fontName`` for a ``FontName`` property, which is
    C#'s convention throughout; the file carries the property's spelling.
    """
    return name[:1].upper() + name[1:]


def _serializable_properties(target: type) -> list[tuple[str, property]]:
    """Every public property that is part of the type's serialized state.

    Declaration order, base classes first, which is what makes a file's elements
    appear in the order a reader of the class would expect. A property with no
    setter is kept only when its value is a collection or dictionary the type
    owns -- those *can* be read back into -- and dropped otherwise, because a
    derived value has nowhere to go on the way back in.
    """
    from ..._collections import NamedValueDictionaryOfT, _Collection

    readable_into = (NamedValueDictionaryOfT, _Collection, list, set)
    result: list[tuple[str, property]] = []
    seen: set[str] = set()
    for klass in reversed(target.__mro__):
        for name, member in vars(klass).items():
            if name.startswith("_") or name in seen \
                    or not isinstance(member, property):
                continue
            seen.add(name)
            if getattr(member.fget, _IGNORED, False):
                continue
            if member.fset is None:
                declared = _declared_type(target, member)
                if declared is None or not issubclass(declared, readable_into):
                    continue
            result.append((name, member))
    return result


def reflective_serializer(target: type) -> ContentTypeSerializer:
    """A serializer for a type nothing else claims."""
    if isinstance(target, type) and issubclass(target, Enum):
        return _ScalarSerializer(
            target, target.__name__, lambda value: value.name,
            lambda text: target[text])
    return _ReflectiveSerializer(target)


def builtin_serializers() -> list[ContentTypeSerializer]:
    """Every serializer the format ships with."""
    return [
        _ScalarSerializer(bool, "boolean", lambda value: "true" if value else "false",
                          lambda text: text.strip().lower() == "true"),
        _ScalarSerializer(int, "int", str, int),
        _ScalarSerializer(float, "float", _real_text, float),
        _ScalarSerializer(str, "string", lambda value: value, lambda text: text),
        _ScalarSerializer(Vector2, "Vector2",
                          lambda value: _numbers(value.X, value.Y),
                          lambda text: Vector2(*_floats(text, 2))),
        _ScalarSerializer(Vector3, "Vector3",
                          lambda value: _numbers(value.X, value.Y, value.Z),
                          lambda text: Vector3(*_floats(text, 3))),
        _ScalarSerializer(Vector4, "Vector4",
                          lambda value: _numbers(value.X, value.Y, value.Z, value.W),
                          lambda text: Vector4(*_floats(text, 4))),
        _ScalarSerializer(Quaternion, "Quaternion",
                          lambda value: _numbers(value.X, value.Y, value.Z, value.W),
                          lambda text: Quaternion(*_floats(text, 4))),
        _ScalarSerializer(Matrix, "Matrix", _matrix_text, _matrix_value),
        _ScalarSerializer(Color, "Color",
                          lambda value: _numbers(value.R, value.G, value.B, value.A),
                          lambda text: Color(*[int(part) for part
                                               in _floats(text, 4)])),
        _ScalarSerializer(Point, "Point",
                          lambda value: _numbers(value.X, value.Y),
                          lambda text: Point(*[int(part) for part
                                               in _floats(text, 2)])),
        _ScalarSerializer(Rectangle, "Rectangle",
                          lambda value: _numbers(value.X, value.Y, value.Width,
                                                 value.Height),
                          lambda text: Rectangle(*[int(part) for part
                                                   in _floats(text, 4)])),
        _CollectionSerializer(list, "List", list),
        # Every pipeline collection and dictionary, by their shared bases: the
        # serializer lookup walks the MRO, so one entry each covers all of them.
        # Without these the reflective serializer would write a dictionary's
        # ``Count`` and ``Keys`` -- derived values that are not its state.
        _CollectionSerializer(_Collection, "Collection", list),
        # A set is a collection too, and ``FontDescription.Characters`` is one:
        # without this a font description would serialize without the characters
        # it is a description *of*.
        _CollectionSerializer(set, "Set", set),
        _DictionarySerializer(NamedValueDictionaryOfT, "Dictionary"),
    ]


def _numbers(*values: object) -> str:
    return " ".join(_real_text(value) for value in values)


def _real_text(value: object) -> str:
    """A number as short a string as round-trips exactly.

    ``repr`` of a Python float is the shortest string that reads back as the
    same double, which is exactly the property an intermediate file needs -- a
    rounded one would change the value every time the file was rewritten.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


def _floats(text: str, count: int) -> list[float]:
    parts = text.split()
    if len(parts) != count:
        raise InvalidContentException(
            f"expected {count} numbers in the intermediate XML, found "
            f"{len(parts)}: {text!r}")
    return [float(part) for part in parts]


def _matrix_text(value: Matrix) -> str:
    return _numbers(*[getattr(value, f"M{row}{column}")
                      for row in range(1, 5) for column in range(1, 5)])


def _matrix_value(text: str) -> Matrix:
    return Matrix(*_floats(text, 16))
