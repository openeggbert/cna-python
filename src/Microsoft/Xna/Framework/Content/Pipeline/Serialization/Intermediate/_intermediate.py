"""The intermediate XML format: content, written so a human can read it.

A content project keeps intermediate XML for two reasons, and both matter. It is
what an artist edits by hand -- a ``.spritefont`` is one of these -- and it is
what a build caches so that the expensive half of a build can be skipped when
nothing changed.

The format is XNA's:

.. code-block:: xml

    <?xml version="1.0" encoding="utf-8"?>
    <XnaContent xmlns:Graphics="Microsoft.Xna.Framework.Content.Pipeline.Graphics">
      <Asset Type="Graphics:BasicMaterialContent">
        <DiffuseColor>1 0 0</DiffuseColor>
      </Asset>
    </XnaContent>

Every value is an element named after the member it came from; a type that is
not obvious from context names itself in a ``Type`` attribute. Shared resources
and external references are written once at the end and referred to by an id,
which is what keeps a graph a graph.

The serializers are looked up by type and are extensible: a caller registers one
for a type of their own and the whole format follows, which is what
``ContentTypeSerializerAttribute`` is for.
"""

from __future__ import annotations

import re
from enum import Enum as _Enum
from typing import Any, Callable, Generic, Iterable, TypeVar
from xml.etree import ElementTree

from ..... import Color, Matrix, Point, Quaternion, Rectangle, Vector2, Vector3, Vector4
from .... import ContentSerializerAttribute
from ..._errors import InvalidContentException
from ..._identity import ExternalReferenceOfT

T = TypeVar("T")

#: The element every intermediate file has at its root.
_ROOT = "XnaContent"


class ContentTypeSerializer:
    """Reads and writes one type as intermediate XML."""

    __slots__ = ("_target_type", "_xml_type_name", "_serializer")

    def __init__(self, targetType: type, xmlTypeName: str | None = None) -> None:
        if not isinstance(targetType, type):
            raise TypeError(
                f"targetType must be a type, not {type(targetType).__name__}")
        self._target_type = targetType
        self._xml_type_name = xmlTypeName or targetType.__name__
        self._serializer: "IntermediateSerializer | None" = None

    def Initialize(self, serializer: "IntermediateSerializer") -> None:
        """Called once, with the serializer that will drive this one."""
        self._serializer = serializer

    @property
    def TargetType(self) -> type:
        return self._target_type

    @property
    def XmlTypeName(self) -> str:
        return self._xml_type_name

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return False

    def Serialize(self, output: "IntermediateWriter", value: object,
                  format: ContentSerializerAttribute) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.Serialize must be overridden")

    def Deserialize(self, input: "IntermediateReader",
                    format: ContentSerializerAttribute,
                    existingInstance: object) -> object:
        raise NotImplementedError(
            f"{type(self).__name__}.Deserialize must be overridden")

    def ObjectIsEmpty(self, value: object) -> bool:
        """Whether ``value`` may be left out of the file entirely.

        An empty collection is the case this exists for: writing
        ``<Children />`` for every leaf node of a scene graph triples the size of
        the file and says nothing.
        """
        return False

    def ScanChildren(self, serializer: "IntermediateSerializer",
                     callback: "ContentTypeSerializerChildCallback",
                     value: object) -> None:
        """Visits every child of ``value``, so shared references can be found.

        The first pass over a graph is a scan: anything reachable twice has to
        be written once and referred to twice, and that cannot be known until
        the whole graph has been walked.
        """
        return None


class ContentTypeSerializerOfT(ContentTypeSerializer, Generic[T]):
    """A serializer whose target type is its closed generic argument."""

    __slots__ = ()

    def __init__(self, xmlTypeName: str | None = None) -> None:
        super().__init__(self._closed_target(), xmlTypeName)

    @classmethod
    def _closed_target(cls) -> type:
        for base in getattr(cls, "__orig_bases__", ()):
            arguments = getattr(base, "__args__", ())
            if arguments and isinstance(arguments[0], type):
                return arguments[0]
        raise TypeError(
            f"{cls.__name__} does not close ContentTypeSerializerOfT's type "
            "argument, so it has no target type")


class ContentTypeSerializerChildCallback:
    """XNA's ``ContentTypeSerializer.ChildCallback`` delegate.

    A .NET delegate is a target object plus a method, and that is exactly what
    the constructor takes. ``BeginInvoke`` and ``EndInvoke`` are the asynchronous
    pattern every delegate carries; a scan is a synchronous walk of an object
    graph in one thread, so ``BeginInvoke`` performs the call and hands back a
    completed result. That is a legal implementation of the pattern and it is
    the honest one here -- pretending to be asynchronous would mean a scan whose
    order depended on scheduling.
    """

    __slots__ = ("_target", "_method")

    def __init__(self, object: object, method: Callable) -> None:
        if not callable(method):
            raise TypeError(
                f"method must be callable, not {type(method).__name__}")
        self._target = object
        self._method = method

    def Invoke(self, typeSerializer: ContentTypeSerializer, value: object) -> None:
        self._method(typeSerializer, value)

    def BeginInvoke(self, typeSerializer: ContentTypeSerializer, value: object,
                    callback: Callable | None = None,
                    object: object = None) -> object:
        self.Invoke(typeSerializer, value)
        result = _CompletedResult(object)
        if callback is not None:
            callback(result)
        return result

    def EndInvoke(self, result: object) -> None:
        if not isinstance(result, _CompletedResult):
            raise ValueError(
                "EndInvoke takes the result BeginInvoke answered")

    def __call__(self, typeSerializer: ContentTypeSerializer,
                 value: object) -> None:
        self.Invoke(typeSerializer, value)


ContentTypeSerializer.__xna_arities__ = {"__init__": {1, 2}}
ContentTypeSerializerOfT.__xna_arities__ = {"__init__": {0, 1}}
ContentTypeSerializerChildCallback.__xna_arities__ = {"BeginInvoke": {4}}


class _CompletedResult:
    """``IAsyncResult`` for a call that finished before it was handed back."""

    __slots__ = ("AsyncState",)

    def __init__(self, state: object) -> None:
        self.AsyncState = state


class ContentTypeSerializerAttribute:
    """Marks a class as a serializer the intermediate serializer should find."""

    __slots__ = ()

    def __call__(self, target: type) -> type:
        setattr(target, "_xna_content_type_serializer", True)
        return target


ContentTypeSerializerAttribute.__xna_arities__ = {"__init__": {0}}


class IntermediateWriter:
    """Writes objects into an XML tree."""

    __slots__ = ("_serializer", "_xml", "_element", "_shared", "_shared_ids",
                 "_external", "_relocation")

    def __init__(self, serializer: "IntermediateSerializer", element,
                 referenceRelocationPath: str | None) -> None:
        self._serializer = serializer
        self._xml = element
        self._element = element
        self._shared: list[object] = []
        self._shared_ids: dict[int, int] = {}
        self._external: list[tuple[int, ExternalReferenceOfT]] = []
        self._relocation = referenceRelocationPath or ""

    @property
    def Serializer(self) -> "IntermediateSerializer":
        return self._serializer

    @property
    def Xml(self):
        return self._xml

    def WriteObject(self, value: object, format: ContentSerializerAttribute,
                    typeSerializer: ContentTypeSerializer | None = None) -> None:
        """Writes ``value`` under an element named by ``format``.

        The element carries a ``Type`` attribute only when the value's type is
        not the one the field declares -- a derived material where the field
        says ``MaterialContent``. Writing it always would make every file
        longer and no file clearer.
        """
        name = format.ElementName or "Item"
        if value is None:
            if format.AllowNull:
                ElementTree.SubElement(self._element, name).set("Null", "true")
                return
            raise InvalidContentException(
                f"{name} is null and its ContentSerializerAttribute does not "
                "allow null")
        serializer = typeSerializer or self._serializer.GetTypeSerializer(type(value))
        if format.Optional and serializer.ObjectIsEmpty(value):
            return
        element = ElementTree.SubElement(self._element, name)
        if not format.FlattenContent:
            element.set("Type", serializer.XmlTypeName)
        previous, self._element = self._element, element
        try:
            serializer.Serialize(self, value, format)
        finally:
            self._element = previous

    def WriteRawObject(self, value: object, format: ContentSerializerAttribute,
                       typeSerializer: ContentTypeSerializer | None = None) -> None:
        """Writes ``value``'s contents into the element already open.

        Which is what makes ``<DiffuseColor>1 0 0</DiffuseColor>`` a single
        element rather than an element containing three.
        """
        serializer = typeSerializer or self._serializer.GetTypeSerializer(type(value))
        serializer.Serialize(self, value, format)

    def WriteSharedResource(self, value: object,
                            format: ContentSerializerAttribute) -> None:
        """Writes a reference to an object written once at the end of the file."""
        name = format.ElementName or "Item"
        element = ElementTree.SubElement(self._element, name)
        if value is None:
            element.set("Null", "true")
            return
        key = id(value)
        identifier = self._shared_ids.get(key)
        if identifier is None:
            self._shared.append(value)
            identifier = len(self._shared)
            self._shared_ids[key] = identifier
        element.text = f"#Resource{identifier}"

    def WriteExternalReference(self, value: ExternalReferenceOfT | None) -> None:
        """Writes a reference to content built separately."""
        element = ElementTree.SubElement(self._element, "Reference")
        if value is None or not value.Filename:
            element.set("Null", "true")
            return
        identifier = len(self._external) + 1
        self._external.append((identifier, value))
        element.text = f"#External{identifier}"

    def WriteTypeName(self, type_: type) -> None:
        self._element.set("Type", self._serializer.GetTypeSerializer(
            type_).XmlTypeName)

    def _text(self, text: str) -> None:
        self._element.text = text

    def _child(self, name: str):
        return ElementTree.SubElement(self._element, name)


IntermediateWriter.__xna_arities__ = {
    "WriteObject": {2, 3}, "WriteRawObject": {2, 3}, "WriteSharedResource": {2},
    "WriteExternalReference": {1},
}


class IntermediateReader:
    """Reads objects back out of an XML tree."""

    __slots__ = ("_serializer", "_xml", "_element", "_shared", "_fixups",
                 "_external", "_relocation")

    def __init__(self, serializer: "IntermediateSerializer", element,
                 referenceRelocationPath: str | None) -> None:
        self._serializer = serializer
        self._xml = element
        self._element = element
        self._shared: dict[str, object] = {}
        self._fixups: list[tuple[str, Callable[[object], None]]] = []
        self._external: dict[str, ExternalReferenceOfT] = {}
        self._relocation = referenceRelocationPath or ""

    @property
    def Serializer(self) -> "IntermediateSerializer":
        return self._serializer

    @property
    def Xml(self):
        return self._xml

    def ReadObject(self, format: ContentSerializerAttribute, *rest: object):
        """XNA's four overloads, distinguished by what the extra arguments are.

        A ``ContentTypeSerializer`` says which serializer to use; anything else
        is an existing instance to read into. They cannot be confused, because
        one is a serializer and the other is not.
        """
        serializer, existing = _reader_arguments(rest)
        name = format.ElementName or "Item"
        element = self._find(name)
        if element is None:
            if format.Optional:
                return existing
            raise InvalidContentException(
                f"the intermediate XML has no <{name}> element")
        return self._read_element(element, format, serializer, existing)

    def ReadRawObject(self, format: ContentSerializerAttribute, *rest: object):
        """Reads from the element already open, without looking for a child."""
        serializer, existing = _reader_arguments(rest)
        if serializer is None:
            raise InvalidContentException(
                "ReadRawObject needs a ContentTypeSerializer or an existing "
                "instance to know what it is reading")
        return serializer.Deserialize(self, format, existing)

    def ReadSharedResource(self, format: ContentSerializerAttribute,
                           fixup: Callable[[object], None]) -> None:
        """Records that ``fixup`` wants whatever the referenced resource is.

        The reference cannot be resolved when it is read, because the resource
        may be written after it. Recording the fixup and running it once the
        whole file is read is the only order that works for a graph.
        """
        name = format.ElementName or "Item"
        element = self._find(name)
        if element is None or element.get("Null") == "true":
            fixup(None)
            return
        self._fixups.append(((element.text or "").strip(), fixup))

    def ReadExternalReference(self, existingInstance: ExternalReferenceOfT) -> None:
        """Fills ``existingInstance`` with the referenced file name."""
        element = self._find("Reference")
        if element is None or element.get("Null") == "true":
            return
        key = (element.text or "").strip()
        reference = self._external.get(key)
        if reference is not None:
            existingInstance.Filename = reference.Filename

    def ReadTypeName(self) -> type:
        """The type the open element names, resolved through the serializers."""
        name = self._element.get("Type")
        if not name:
            raise InvalidContentException(
                f"<{self._element.tag}> has no Type attribute to read")
        return self._serializer._type_named(name)

    def MoveToElement(self, elementName: str) -> bool:
        """Makes ``elementName`` the open element, if it is there."""
        element = self._find(elementName)
        if element is None:
            return False
        self._element = element
        return True

    # -- internals -----------------------------------------------------------

    def _find(self, name: str):
        return self._element.find(name)

    def _read_element(self, element, format: ContentSerializerAttribute,
                      serializer: ContentTypeSerializer | None, existing):
        if element.get("Null") == "true":
            return None
        if serializer is None:
            declared = element.get("Type")
            if declared:
                serializer = self._serializer._serializer_named(declared)
            elif existing is not None:
                serializer = self._serializer.GetTypeSerializer(type(existing))
            else:
                raise InvalidContentException(
                    f"<{element.tag}> has no Type attribute and no existing "
                    "instance, so nothing says what it holds")
        previous, self._element = self._element, element
        try:
            return serializer.Deserialize(self, format, existing)
        finally:
            self._element = previous


IntermediateReader.__xna_arities__ = {
    "ReadObject": {1, 2, 3}, "ReadRawObject": {1, 2, 3},
    "ReadSharedResource": {2}, "ReadExternalReference": {1},
}


def _reader_arguments(rest: tuple[object, ...]):
    if not rest:
        return None, None
    if len(rest) == 1:
        if isinstance(rest[0], ContentTypeSerializer):
            return rest[0], None
        return None, rest[0]
    if len(rest) == 2 and isinstance(rest[0], ContentTypeSerializer):
        return rest[0], rest[1]
    raise TypeError("no matching Read overload")


class IntermediateSerializer:
    """The registry, and the two ends of the format."""

    __slots__ = ("_by_type", "_by_name")

    def __init__(self) -> None:
        from ._serializers import builtin_serializers

        self._by_type: dict[type, ContentTypeSerializer] = {}
        self._by_name: dict[str, ContentTypeSerializer] = {}
        for serializer in builtin_serializers():
            self._register(serializer)

    def GetTypeSerializer(self, type_: type) -> ContentTypeSerializer:
        """The serializer for ``type_``, or the nearest one its bases provide."""
        serializer = self._by_type.get(type_)
        if serializer is not None:
            return serializer
        if isinstance(type_, type) and issubclass(type_, _Enum):
            # An enum is an int in Python, so walking its bases would find the
            # integer serializer and write ``0`` where XNA writes ``Regular``.
            # Its own serializer is built first, and it writes the name.
            from ._serializers import reflective_serializer

            serializer = reflective_serializer(type_)
            self._register(serializer)
            return serializer
        for base in getattr(type_, "__mro__", ())[1:]:
            candidate = self._by_type.get(base)
            if candidate is not None:
                self._by_type[type_] = candidate
                return candidate
        from ._serializers import reflective_serializer

        serializer = reflective_serializer(type_)
        self._register(serializer)
        return serializer

    @staticmethod
    def Serialize(output, value: object,
                  referenceRelocationPath: str | None) -> None:
        """Writes ``value`` to ``output`` as a complete intermediate file."""
        serializer = IntermediateSerializer()
        root = ElementTree.Element(_ROOT)
        writer = IntermediateWriter(serializer, root, referenceRelocationPath)
        asset = ContentSerializerAttribute()
        asset.ElementName = "Asset"
        writer.WriteObject(value, asset)
        index = 0
        while index < len(writer._shared):
            resource = writer._shared[index]
            index += 1
            element = ElementTree.SubElement(root, "Resources")
            element.set("ID", f"#Resource{index}")
            previous, writer._element = writer._element, element
            try:
                inner = ContentSerializerAttribute()
                inner.ElementName = "Value"
                writer.WriteObject(resource, inner)
            finally:
                writer._element = previous
        for identifier, reference in writer._external:
            element = ElementTree.SubElement(root, "ExternalReferences")
            element.set("ID", f"#External{identifier}")
            element.set("TargetType", "Object")
            element.text = reference.Filename
        _indent(root)
        text = ElementTree.tostring(root, encoding="unicode")
        document = '<?xml version="1.0" encoding="utf-8"?>\n' + text + "\n"
        if hasattr(output, "write"):
            output.write(document)
        else:
            raise TypeError(
                "Serialize writes to a text stream; XNA's XmlWriter has no "
                "Python counterpart and a file object is what takes its place")

    @staticmethod
    def Deserialize(input, referenceRelocationPath: str | None, *,
                    targetType: type):
        """Reads a complete intermediate file back into an object.

        ``targetType`` is XNA's type argument, keyword-spelled: the file names
        the type it holds, so the argument is a *check* rather than the answer,
        and a file holding something else says so instead of being coerced.
        """
        text = input.read() if hasattr(input, "read") else input
        root = ElementTree.fromstring(text)
        if root.tag != _ROOT:
            raise InvalidContentException(
                f"an intermediate file's root element is <{_ROOT}>, not "
                f"<{root.tag}>")
        serializer = IntermediateSerializer()
        reader = IntermediateReader(serializer, root, referenceRelocationPath)
        for element in root.findall("ExternalReferences"):
            identifier = element.get("ID") or ""
            reader._external[identifier] = ExternalReferenceOfT(
                (element.text or "").strip())
        asset = ContentSerializerAttribute()
        asset.ElementName = "Asset"
        value = reader.ReadObject(asset)
        for element in root.findall("Resources"):
            identifier = element.get("ID") or ""
            previous, reader._element = reader._element, element
            try:
                inner = ContentSerializerAttribute()
                inner.ElementName = "Value"
                reader._shared[identifier] = reader.ReadObject(inner)
            finally:
                reader._element = previous
        for key, fixup in reader._fixups:
            fixup(reader._shared.get(key))
        if value is not None and not isinstance(value, targetType):
            raise InvalidContentException(
                f"the file holds a {type(value).__name__}, and a "
                f"{targetType.__name__} was asked for")
        return value

    # -- internals -----------------------------------------------------------

    def _register(self, serializer: ContentTypeSerializer) -> None:
        serializer.Initialize(self)
        self._by_type[serializer.TargetType] = serializer
        self._by_name[serializer.XmlTypeName] = serializer

    def _serializer_named(self, name: str) -> ContentTypeSerializer:
        """The serializer for a type named in a file.

        Reading is the harder direction: writing starts from an object and can
        ask its type, while reading starts from a *name*. XNA resolves one
        through assembly reflection; the same question here is answered by the
        pipeline's own public namespaces, which are what a content project's
        types come from, plus anything a caller has registered.

        A namespace prefix -- ``Graphics:BasicMaterialContent`` -- is dropped:
        XNA writes one when the file declares an XML namespace for it, and the
        type name after the colon is what identifies the type.
        """
        simple = name.split(":")[-1]
        serializer = self._by_name.get(simple)
        if serializer is not None:
            return serializer
        target = _pipeline_type(simple)
        if target is None:
            raise InvalidContentException(
                f"the intermediate XML names a type this serializer does not "
                f"know: {name!r}")
        return self.GetTypeSerializer(target)

    def _type_named(self, name: str) -> type:
        return self._serializer_named(name).TargetType

    @staticmethod
    def _opaque_data_xml(data) -> str:
        """Every entry of an ``OpaqueDataDictionary``, as stable XML.

        Sorted by key rather than written in insertion order, because the build
        cache compares this text to decide whether a processor's parameters
        changed and insertion order is not part of what changed.
        """
        serializer = IntermediateSerializer()
        root = ElementTree.Element("Data")
        writer = IntermediateWriter(serializer, root, None)
        for key in sorted(data.Keys):
            format = ContentSerializerAttribute()
            format.ElementName = key
            writer.WriteObject(data[key], format)
        _indent(root)
        return ElementTree.tostring(root, encoding="unicode")


IntermediateSerializer.__xna_arities__ = {"Serialize": {3}, "Deserialize": {2}}


#: The public pipeline packages a type name may come from, and a cache of the
#: names they hold. Built on first use, because importing them all eagerly would
#: make the *writer* pay for something only the reader needs.
_TYPE_PACKAGES = (
    "Microsoft.Xna.Framework.Content.Pipeline",
    "Microsoft.Xna.Framework.Content.Pipeline.Audio",
    "Microsoft.Xna.Framework.Content.Pipeline.Graphics",
    "Microsoft.Xna.Framework.Content.Pipeline.Processors",
)
_TYPES_BY_NAME: dict[str, type] | None = None


def _pipeline_type(name: str) -> type | None:
    global _TYPES_BY_NAME

    if _TYPES_BY_NAME is None:
        import importlib

        found: dict[str, type] = {}
        for package in _TYPE_PACKAGES:
            module = importlib.import_module(package)
            for exported in getattr(module, "__all__", ()):
                value = getattr(module, exported)
                if isinstance(value, type):
                    found.setdefault(exported, value)
        _TYPES_BY_NAME = found
    return _TYPES_BY_NAME.get(name)


def _indent(element, level: int = 0) -> None:
    """Two-space indentation, so a written file is one a human can read."""
    padding = "\n" + "  " * level
    if len(element):
        if not (element.text or "").strip():
            element.text = padding + "  "
        for child in element:
            _indent(child, level + 1)
            if not (child.tail or "").strip():
                child.tail = padding + "  "
        if not (element[-1].tail or "").strip():
            element[-1].tail = padding
    elif level and not (element.tail or "").strip():
        element.tail = padding
