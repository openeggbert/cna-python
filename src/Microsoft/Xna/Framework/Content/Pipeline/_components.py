"""Importers, processors, and the scanner that finds them.

An importer turns a *file* into an object. A processor turns an object into
another object. The build runs one of each and hands the result to the compiler,
and neither half knows about the other -- which is why a texture importer can
feed a model processor's nested build without either being written for it.

The scanner is the part that makes a content project work at all: a build names
its importer and processor as *strings*, and something has to turn those strings
into classes. In .NET that is assembly reflection. Here it is module import,
which is the same operation spelled the way Python spells it, and the two
outcomes a build tool depends on are the same: a list of the components found,
and a list of the errors that stopped others from being found.
"""

from __future__ import annotations

from enum import Enum
import importlib
import inspect
from typing import Generic, Iterable, TypeVar

from ._attributes import (
    ContentImporterAttribute, ContentProcessorAttribute,
    importer_attribute, processor_attribute,
)
from ._collections import _ReadOnlyCollection
from ._context import ContentImporterContext, ContentProcessorContext

T = TypeVar("T")
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class IContentImporter:
    """Anything the build can call to read a file."""

    def Import(self, filename: str, context: ContentImporterContext) -> object:
        raise NotImplementedError


class IContentProcessor:
    """Anything the build can call to transform imported content.

    ``InputType`` and ``OutputType`` are how a build tool decides which
    processors it may offer for a given importer's output, so they are part of
    the interface rather than something read off the class by reflection.
    """

    def Process(self, input: object, context: ContentProcessorContext) -> object:
        raise NotImplementedError

    @property
    def InputType(self) -> type:
        raise NotImplementedError

    @property
    def OutputType(self) -> type:
        raise NotImplementedError


class ContentImporterOfT(IContentImporter, Generic[T]):
    """The base every importer derives from.

    XNA's ``ContentImporter<T>`` implements ``IContentImporter`` by calling the
    typed ``Import``; there is only one method here because the typed and
    untyped halves are the same method in Python.
    """

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> T:
        raise NotImplementedError(
            f"{type(self).__name__}.Import must be overridden")


class ContentProcessorOfT(IContentProcessor, Generic[TInput, TOutput]):
    """The base every processor derives from.

    ``InputType`` and ``OutputType`` are answered from the class's own generic
    arguments, so a processor that declares
    ``ContentProcessorOfT[TextureContent, TextureContent]`` gets both for free
    and cannot get them wrong. A processor written without them has to say so:
    a class that closes neither argument has nothing to report, and reporting
    ``object`` would tell a build tool that every processor accepts everything.
    """

    __slots__ = ()

    def Process(self, input: TInput, context: ContentProcessorContext) -> TOutput:
        raise NotImplementedError(
            f"{type(self).__name__}.Process must be overridden")

    @property
    def InputType(self) -> type:
        return self._closed_argument(0, "InputType")

    @property
    def OutputType(self) -> type:
        return self._closed_argument(1, "OutputType")

    @classmethod
    def _closed_argument(cls, position: int, what: str) -> type:
        for base in getattr(cls, "__orig_bases__", ()):
            origin = getattr(base, "__origin__", None)
            if origin is None or not (isinstance(origin, type)
                                      and issubclass(origin, ContentProcessorOfT)):
                continue
            arguments = getattr(base, "__args__", ())
            if position < len(arguments) and isinstance(arguments[position], type):
                return arguments[position]
        raise NotImplementedError(
            f"{cls.__name__} does not close ContentProcessorOfT's type "
            f"arguments, so {what} has no answer to give")


class ProcessorParameter:
    """One knob a processor exposes to a build tool.

    A build tool draws these: the display name is the label, the description is
    the tooltip, and ``PossibleEnumValues`` fills the drop-down when the
    parameter is an enum. Everything here is read off the processor's own
    property, so a processor cannot advertise a parameter it does not have.
    """

    __slots__ = ("_property_name", "_display_name", "_property_type",
                 "_default_value", "_description", "_possible_enum_values")

    def __init__(self, propertyName: str, propertyType: type,
                 defaultValue: object, displayName: str = "",
                 description: str = "") -> None:
        self._property_name = propertyName
        self._property_type = propertyType
        self._default_value = defaultValue
        self._display_name = displayName or propertyName
        self._description = description
        values: tuple[str, ...] = ()
        if isinstance(propertyType, type) and issubclass(propertyType, Enum):
            values = tuple(member.name for member in propertyType)
        self._possible_enum_values = values

    @property
    def PropertyName(self) -> str:
        return self._property_name

    @property
    def DisplayName(self) -> str:
        return self._display_name

    @property
    def PropertyType(self) -> type:
        return self._property_type

    @property
    def DefaultValue(self) -> object:
        return self._default_value

    @property
    def Description(self) -> str:
        return self._description

    @property
    def PossibleEnumValues(self) -> tuple[str, ...]:
        return self._possible_enum_values

    @property
    def IsEnum(self) -> bool:
        return bool(self._possible_enum_values)

    def __repr__(self) -> str:
        return f"ProcessorParameter({self._property_name!r})"


class ProcessorParameterCollection(_ReadOnlyCollection[ProcessorParameter]):
    """Every parameter one processor exposes, in declaration order."""

    __slots__ = ()


class PipelineComponentScanner:
    """Finds the importers and processors in a set of modules.

    ``Update`` answers whether anything *changed* since the last call, which is
    what a build tool polls: rescanning is cheap and redrawing its component
    list is not.

    The names are Python module names rather than assembly paths, because that
    is what identifies a body of loadable code here. A module that cannot be
    imported is not a crash: it goes in :attr:`Errors` with the reason, and the
    other modules are still scanned -- one broken pipeline extension must not
    take a whole content project down with it.
    """

    __slots__ = ("_importer_names", "_importer_attributes", "_importer_outputs",
                 "_processor_names", "_processor_attributes", "_processor_inputs",
                 "_processor_outputs", "_processor_parameters", "_errors",
                 "_scanned")

    def __init__(self) -> None:
        self._importer_names: tuple[str, ...] = ()
        self._importer_attributes: dict[str, ContentImporterAttribute] = {}
        self._importer_outputs: dict[str, type] = {}
        self._processor_names: tuple[str, ...] = ()
        self._processor_attributes: dict[str, ContentProcessorAttribute] = {}
        self._processor_inputs: dict[str, type] = {}
        self._processor_outputs: dict[str, type] = {}
        self._processor_parameters: dict[str, ProcessorParameterCollection] = {}
        self._errors: tuple[str, ...] = ()
        self._scanned: tuple[str, ...] | None = None

    def Update(self, pipelineAssemblies: Iterable[str],
               pipelineAssemblyDependencies: Iterable[str] | None = None) -> bool:
        """Scans ``pipelineAssemblies``; answers whether the result changed.

        ``pipelineAssemblyDependencies`` are modules that must be importable for
        the scan to succeed but that are not themselves scanned -- a shared
        library a pipeline extension imports. They are imported first, so a
        dependency that is missing is reported as one error rather than as an
        error against every module that needed it.
        """
        modules = tuple(dict.fromkeys(_names(pipelineAssemblies, "pipelineAssemblies")))
        dependencies = tuple(dict.fromkeys(_names(
            pipelineAssemblyDependencies or (), "pipelineAssemblyDependencies")))
        errors: list[str] = []
        for name in dependencies:
            try:
                importlib.import_module(name)
            except Exception as error:  # noqa: BLE001 - reported, never raised
                errors.append(f"{name}: {error}")

        importers: dict[str, tuple[ContentImporterAttribute, type]] = {}
        processors: dict[str, tuple[ContentProcessorAttribute, type]] = {}
        for name in modules:
            try:
                module = importlib.import_module(name)
            except Exception as error:  # noqa: BLE001 - reported, never raised
                errors.append(f"{name}: {error}")
                continue
            for member in vars(module).values():
                if not isinstance(member, type):
                    continue
                attribute = importer_attribute(member)
                if attribute is not None and issubclass(member, IContentImporter):
                    _claim(importers, member, attribute, "importer", errors)
                attribute = processor_attribute(member)
                if attribute is not None and issubclass(member, IContentProcessor):
                    _claim(processors, member, attribute, "processor", errors)

        state = (tuple(sorted(importers)), tuple(sorted(processors)), tuple(errors))
        previous = (self._importer_names, self._processor_names, self._errors)
        self._importer_names = tuple(sorted(importers))
        self._importer_attributes = {
            name: value[0] for name, value in importers.items()}
        self._importer_outputs = {
            name: _importer_output(value[1]) for name, value in importers.items()}
        self._processor_names = tuple(sorted(processors))
        self._processor_attributes = {
            name: value[0] for name, value in processors.items()}
        self._processor_inputs = {}
        self._processor_outputs = {}
        self._processor_parameters = {}
        for name, (_attribute, component) in processors.items():
            instance = component()
            self._processor_inputs[name] = instance.InputType
            self._processor_outputs[name] = instance.OutputType
            self._processor_parameters[name] = _parameters_of(component)
        self._errors = tuple(errors)
        self._scanned = modules
        return state != previous

    @property
    def ImporterNames(self) -> tuple[str, ...]:
        return self._importer_names

    @property
    def ImporterAttributes(self):
        return dict(self._importer_attributes)

    @property
    def ImporterOutputTypes(self):
        return dict(self._importer_outputs)

    @property
    def ProcessorNames(self) -> tuple[str, ...]:
        return self._processor_names

    @property
    def ProcessorAttributes(self):
        return dict(self._processor_attributes)

    @property
    def ProcessorInputTypes(self):
        return dict(self._processor_inputs)

    @property
    def ProcessorOutputTypes(self):
        return dict(self._processor_outputs)

    @property
    def ProcessorParameters(self):
        return dict(self._processor_parameters)

    @property
    def Errors(self) -> tuple[str, ...]:
        return self._errors


PipelineComponentScanner.__xna_arities__ = {"Update": {1, 2}}
#: Every importer and processor is default-constructible, and none of them
#: declares an ``__init__`` of its own; the metadata is inherited so that each
#: subclass reports the arity XNA declares rather than ``object``'s.
ContentImporterOfT.__xna_arities__ = {"__init__": {0}}
ContentProcessorOfT.__xna_arities__ = {"__init__": {0}}


def _names(values: Iterable[str], what: str) -> list[str]:
    result = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError(f"{what} holds module names, not {type(value).__name__}")
        result.append(value)
    return result


def _claim(found: dict, component: type, attribute: object, kind: str,
           errors: list[str]) -> None:
    name = component.__name__
    existing = found.get(name)
    if existing is not None and existing[1] is not component:
        errors.append(
            f"{name}: two {kind}s share the name "
            f"({existing[1].__module__} and {component.__module__})")
        return
    found[name] = (attribute, component)


def _importer_output(component: type) -> type:
    for base in getattr(component, "__orig_bases__", ()):
        arguments = getattr(base, "__args__", ())
        if arguments and isinstance(arguments[0], type):
            return arguments[0]
    return object


def _parameters_of(component: type) -> ProcessorParameterCollection:
    """Every settable property a processor declares, as a parameter.

    Read from the class rather than from an attribute list, so a processor
    cannot advertise a parameter it does not have or forget one it does. The
    default value comes from a fresh instance, which is the same answer a build
    tool would get by constructing the processor and reading the property.
    """
    instance = component()
    parameters: list[ProcessorParameter] = []
    for name, member in _declared_properties(component):
        if member.fset is None:
            continue
        try:
            default = getattr(instance, name)
        except Exception:  # noqa: BLE001 - a property that needs a build is not a knob
            continue
        annotation = getattr(member.fget, "__annotations__", {}).get("return")
        parameters.append(ProcessorParameter(
            name, _resolve(annotation, default), default,
            description=(inspect.getdoc(member) or "").strip()))
    return ProcessorParameterCollection(parameters)


def _declared_properties(component: type):
    seen: set[str] = set()
    for klass in component.__mro__:
        for name, member in vars(klass).items():
            if name.startswith("_") or name in seen or not isinstance(member, property):
                continue
            seen.add(name)
            yield name, member


def _resolve(annotation: object, default: object) -> type:
    if isinstance(annotation, type):
        return annotation
    return type(default)
