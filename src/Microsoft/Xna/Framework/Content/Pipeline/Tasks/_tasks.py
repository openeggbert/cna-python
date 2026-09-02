"""The four build tasks: what a content project actually runs.

In XNA these are MSBuild tasks, and MSBuild is what drives them. There is no
MSBuild here, and there does not need to be: a task is an object with settable
inputs, an ``Execute`` that does the work and answers whether it succeeded, and
readable outputs afterwards. That contract is the whole of ``ITask`` that
matters, and it is what is projected.

The one place MSBuild's shape shows through is ``ITaskItem``. An item is a file
name plus named metadata, so it is projected as a mapping with an ``ItemSpec``
key -- and a plain string is accepted anywhere an item is, because most items
are only a file name. :class:`TaskItem` is the small record that results, and it
is what the output properties answer.

``BuildContent`` is a real incremental build. It reads a cache of what each
asset depended on last time, rebuilds an asset whose source or dependencies are
newer than its output, and leaves the rest alone -- which is the behaviour the
whole design of ``ContentImporterContext.AddDependency`` exists to support.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Iterable, Sequence

from .... import Color
from ....Graphics import GraphicsProfile
from .._collections import OpaqueDataDictionary
from .._components import PipelineComponentScanner
from .._context import ContentImporterContext, ContentProcessorContext
from .._errors import InvalidContentException, PipelineException
from .._identity import ExternalReferenceOfT
from .._logging import ContentBuildLogger
from .._target import TargetPlatform
from ..Serialization.Compiler import ContentCompiler

#: The file a build writes its dependency cache into, inside the intermediate
#: directory. One file per content project, named by its GUID.
_CACHE_NAME = "{0}.contentcache.json"


class TaskItem:
    """A file name with named metadata: MSBuild's ``ITaskItem``, projected.

    Accepts a bare string, a mapping, or another item, because that is what the
    three ways a caller supplies one look like. ``ItemSpec`` is the file name;
    everything else is metadata a task reads by name.
    """

    __slots__ = ("_spec", "_metadata")

    def __init__(self, value: object) -> None:
        if isinstance(value, TaskItem):
            self._spec = value._spec
            self._metadata = dict(value._metadata)
            return
        if isinstance(value, str):
            self._spec = value
            self._metadata = {}
            return
        if hasattr(value, "keys"):
            metadata = {str(key): value[key] for key in value.keys()}
            spec = metadata.pop("ItemSpec", None)
            if spec is None:
                raise ValueError(
                    "a task item mapping needs an 'ItemSpec' naming the file")
            self._spec = str(spec)
            self._metadata = metadata
            return
        raise TypeError(
            "a task item is a file name, a mapping with an ItemSpec, or "
            f"another item, not {type(value).__name__}")

    @property
    def ItemSpec(self) -> str:
        return self._spec

    def GetMetadata(self, name: str, default: object = None) -> object:
        return self._metadata.get(name, default)

    def SetMetadata(self, name: str, value: object) -> None:
        self._metadata[name] = value

    def __repr__(self) -> str:
        return f"TaskItem({self._spec!r}, {self._metadata!r})"


class _Task:
    """What every task shares: string inputs, and an ``Execute`` that reports.

    Not public: XNA's four tasks derive from ``Microsoft.Build.Utilities.Task``,
    which has no Python counterpart, so this stands in as the composition base
    and never appears in the surface.
    """

    __slots__ = ("_values", "_logger")

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._logger: ContentBuildLogger | None = None

    def Execute(self) -> bool:
        raise NotImplementedError(f"{type(self).__name__}.Execute must be overridden")

    # -- the shared string inputs -------------------------------------------

    def _text(self, name: str) -> str:
        return self._values.get(name, "")

    def _set_text(self, name: str, value: object) -> None:
        if value is None:
            self._values[name] = ""
            return
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a str, not {type(value).__name__}")
        self._values[name] = value

    def _flag(self, name: str) -> bool:
        return bool(self._values.get(name, False))

    def _set_flag(self, name: str, value: object) -> None:
        if type(value) is not bool:
            raise TypeError(f"{name} must be a bool")
        self._values[name] = value

    def _items(self, name: str) -> tuple[TaskItem, ...]:
        return tuple(self._values.get(name, ()))

    def _set_items(self, name: str, value: object) -> None:
        if value is None:
            self._values[name] = ()
            return
        self._values[name] = tuple(TaskItem(entry) for entry in value)

    def _platform(self) -> TargetPlatform:
        text = self._text("TargetPlatform") or "Windows"
        try:
            return TargetPlatform[text]
        except KeyError:
            raise PipelineException(
                f"TargetPlatform {text!r} is not one of "
                + ", ".join(member.name for member in TargetPlatform)) from None

    def _profile(self) -> GraphicsProfile:
        text = self._text("TargetProfile") or "Reach"
        try:
            return GraphicsProfile[text]
        except KeyError:
            raise PipelineException(
                f"TargetProfile {text!r} is not one of "
                + ", ".join(member.name for member in GraphicsProfile)) from None

    def _cache_path(self) -> str:
        return os.path.join(
            self._text("IntermediateDirectory"),
            _CACHE_NAME.format(self._text("ContentProjectGUID") or "content"))


def _string_property(name: str) -> property:
    return property(lambda self: self._text(name),
                    lambda self, value: self._set_text(name, value))


def _flag_property(name: str) -> property:
    return property(lambda self: self._flag(name),
                    lambda self, value: self._set_flag(name, value))


def _item_property(name: str) -> property:
    return property(lambda self: self._items(name),
                    lambda self, value: self._set_items(name, value))


def _readonly_item_property(name: str) -> property:
    return property(lambda self: self._items(name))


class _CollectingLogger(ContentBuildLogger):
    """A logger that keeps what it was told, so a task can report it."""

    __slots__ = ("messages", "warnings")

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []
        self.warnings: list[str] = []

    def LogMessage(self, message: str, *messageArgs: object) -> None:
        self.messages.append(_format(message, messageArgs))

    def LogImportantMessage(self, message: str, *messageArgs: object) -> None:
        self.messages.append(_format(message, messageArgs))

    def LogWarning(self, helpLink: str, contentIdentity, message: str,
                   *messageArgs: object) -> None:
        where = self.GetCurrentFilename(contentIdentity)
        text = _format(message, messageArgs)
        self.warnings.append(f"{where}: {text}" if where else text)


_CollectingLogger.__xna_arities__ = {
    "LogMessage": {2}, "LogImportantMessage": {2}, "LogWarning": {4},
}


def _format(message: str, arguments: tuple[object, ...]) -> str:
    if not arguments:
        return message
    try:
        return message.format(*arguments)
    except (IndexError, KeyError, ValueError):
        return message


class _ImporterContext(ContentImporterContext):
    """The context a ``BuildContent`` gives an importer."""

    __slots__ = ("_logger", "_output", "_intermediate", "dependencies")

    def __init__(self, logger: ContentBuildLogger, output: str,
                 intermediate: str) -> None:
        self._logger = logger
        self._output = output
        self._intermediate = intermediate
        self.dependencies: list[str] = []

    @property
    def Logger(self) -> ContentBuildLogger:
        return self._logger

    @property
    def OutputDirectory(self) -> str:
        return self._output

    @property
    def IntermediateDirectory(self) -> str:
        return self._intermediate

    def AddDependency(self, filename: str) -> None:
        path = os.path.abspath(filename)
        if path not in self.dependencies:
            self.dependencies.append(path)


class _ProcessorContext(ContentProcessorContext):
    """The context a ``BuildContent`` gives a processor.

    It is the build: ``BuildAsset`` really builds a nested asset and writes it,
    ``BuildAndLoadAsset`` builds one and hands back the object, and ``Convert``
    runs another processor on an object already in hand. All three record what
    they touched, which is how a model's textures become the model's
    dependencies.
    """

    __slots__ = ("_build", "_logger", "_parameters", "_platform", "_profile",
                 "_configuration", "_output_filename", "_output", "_intermediate",
                 "dependencies", "outputs")

    def __init__(self, build: "BuildContent", logger: ContentBuildLogger,
                 parameters: OpaqueDataDictionary, outputFilename: str) -> None:
        self._build = build
        self._logger = logger
        self._parameters = parameters
        self._platform = build._platform()
        self._profile = build._profile()
        self._configuration = build.BuildConfiguration
        self._output_filename = outputFilename
        self._output = build.OutputDirectory
        self._intermediate = build.IntermediateDirectory
        self.dependencies: list[str] = []
        self.outputs: list[str] = []

    @property
    def Logger(self) -> ContentBuildLogger:
        return self._logger

    @property
    def Parameters(self) -> OpaqueDataDictionary:
        return self._parameters

    @property
    def TargetPlatform(self) -> TargetPlatform:
        return self._platform

    @property
    def TargetProfile(self) -> GraphicsProfile:
        return self._profile

    @property
    def BuildConfiguration(self) -> str:
        return self._configuration

    @property
    def OutputFilename(self) -> str:
        return self._output_filename

    @property
    def OutputDirectory(self) -> str:
        return self._output

    @property
    def IntermediateDirectory(self) -> str:
        return self._intermediate

    def AddDependency(self, filename: str) -> None:
        path = os.path.abspath(filename)
        if path not in self.dependencies:
            self.dependencies.append(path)

    def AddOutputFile(self, filename: str) -> None:
        path = os.path.abspath(filename)
        if path not in self.outputs:
            self.outputs.append(path)

    def BuildAsset(self, sourceAsset, processorName: str, *rest: object):
        parameters, importer_name, asset_name = _build_arguments(rest)
        self.AddDependency(sourceAsset.Filename)
        built = self._build._build_one(
            sourceAsset.Filename, importer_name, processorName, parameters,
            asset_name or self._build._asset_name(sourceAsset.Filename), self)
        self.AddOutputFile(built)
        reference = ExternalReferenceOfT()
        reference.Filename = built
        return reference

    def BuildAndLoadAsset(self, sourceAsset, processorName: str, *rest: object):
        parameters, importer_name, _asset = _build_arguments(rest + (None,))
        self.AddDependency(sourceAsset.Filename)
        return self._build._import_and_process(
            sourceAsset.Filename, importer_name, processorName, parameters, self)

    def Convert(self, input: object, processorName: str, *rest: object):
        parameters = rest[0] if rest else OpaqueDataDictionary()
        processor = self._build._processor(processorName, parameters)
        return processor.Process(input, self)


def _build_arguments(rest: tuple[object, ...]):
    """``(parameters, importerName, assetName)`` from XNA's two overloads."""
    if not rest:
        return OpaqueDataDictionary(), None, None
    if len(rest) == 3:
        return (rest[0] or OpaqueDataDictionary(), rest[1], rest[2])
    if len(rest) == 4:
        return (rest[0] or OpaqueDataDictionary(), rest[1], rest[2])
    raise TypeError("no matching BuildAsset overload")


class BuildContent(_Task):
    """Builds a content project: import, process, compile, write.

    Incremental by default. An asset is rebuilt when its ``.xnb`` is missing,
    when its source is newer than the ``.xnb``, when anything it recorded as a
    dependency is newer, or when ``RebuildAll`` is set. Everything else is left
    alone and still appears in ``OutputContentFiles``, because a build's outputs
    are its outputs whether this run produced them or a previous one did.
    """

    __slots__ = ("_scanner", "_logger")

    CancelEventNameFormat = \
        "Local\\Microsoft.Xna.GameStudio.ContentPipeline.CancelBuildEvent+{0}"

    def __init__(self) -> None:
        super().__init__()
        self._scanner = PipelineComponentScanner()
        self._logger = _CollectingLogger()

    PipelineAssemblies = _item_property("PipelineAssemblies")
    PipelineAssemblyDependencies = _item_property("PipelineAssemblyDependencies")
    SourceAssets = _item_property("SourceAssets")
    ContentProjectGUID = _string_property("ContentProjectGUID")
    TargetPlatform = _string_property("TargetPlatform")
    TargetProfile = _string_property("TargetProfile")
    BuildConfiguration = _string_property("BuildConfiguration")
    CompressContent = _flag_property("CompressContent")
    RootDirectory = _string_property("RootDirectory")
    LoggerRootDirectory = _string_property("LoggerRootDirectory")
    IntermediateDirectory = _string_property("IntermediateDirectory")
    OutputDirectory = _string_property("OutputDirectory")
    RebuildAll = _flag_property("RebuildAll")
    OutputContentFiles = _readonly_item_property("OutputContentFiles")
    RebuiltContentFiles = _readonly_item_property("RebuiltContentFiles")
    IntermediateFiles = _readonly_item_property("IntermediateFiles")

    def Execute(self) -> bool:
        # The platform and profile are project settings, not asset content, so
        # a bad one fails the build immediately rather than once per asset.
        self._platform()
        self._profile()
        self._logger = _CollectingLogger()
        self._logger.LoggerRootDirectory = \
            self.LoggerRootDirectory or self.RootDirectory
        modules = [item.ItemSpec for item in self.PipelineAssemblies]
        dependencies = [item.ItemSpec
                        for item in self.PipelineAssemblyDependencies]
        self._scanner.Update(modules, dependencies)
        if self._scanner.Errors:
            for error in self._scanner.Errors:
                self._logger.LogWarning("", None, "{0}", error)
        cache = self._read_cache()
        outputs: list[TaskItem] = []
        rebuilt: list[TaskItem] = []
        intermediates: list[TaskItem] = [TaskItem(self._cache_path())]
        succeeded = True
        for item in self.SourceAssets:
            source = os.path.abspath(item.ItemSpec)
            name = str(item.GetMetadata("Name")
                       or self._asset_name(source))
            target = os.path.join(self.OutputDirectory, name + ".xnb")
            entry = cache.get(name)
            if not self.RebuildAll and self._is_current(source, target, entry):
                outputs.append(TaskItem(target))
                continue
            try:
                context = self._build_asset(item, source, name, target)
            except Exception as error:  # noqa: BLE001 - reported, not raised
                succeeded = False
                self._logger.LogWarning("", None, "{0}: {1}", source, error)
                continue
            cache[name] = {
                "source": source,
                "output": target,
                "dependencies": context.dependencies,
                "outputs": context.outputs,
            }
            outputs.append(TaskItem(target))
            rebuilt.append(TaskItem(target))
            for extra in context.outputs:
                outputs.append(TaskItem(extra))
        self._write_cache(cache)
        self._values["OutputContentFiles"] = tuple(outputs)
        self._values["RebuiltContentFiles"] = tuple(rebuilt)
        self._values["IntermediateFiles"] = tuple(intermediates)
        return succeeded

    # ``_logger`` is deliberately not a public property. XNA's task logs
    # through MSBuild, which is not here, so the messages are kept on the task
    # for whatever ran it to read -- privately, because publishing them would
    # be claiming a member XNA's BuildContent does not have.

    # -- the build itself ----------------------------------------------------

    def _build_asset(self, item: TaskItem, source: str, name: str,
                     target: str) -> "_ProcessorContext":
        importer_name = item.GetMetadata("Importer")
        processor_name = item.GetMetadata("Processor")
        parameters = _parameters_of(item)
        context = _ProcessorContext(self, self._logger, parameters, target)
        self._logger.PushFile(source)
        try:
            value = self._import_and_process(
                source, importer_name, processor_name, parameters, context)
            self._write(value, target)
        finally:
            self._logger.PopFile()
        return context

    def _import_and_process(self, source: str, importerName: str | None,
                            processorName: str | None,
                            parameters: OpaqueDataDictionary,
                            context: "_ProcessorContext"):
        importer_context = _ImporterContext(
            self._logger, self.OutputDirectory, self.IntermediateDirectory)
        importer = self._importer(importerName, source)
        value = importer.Import(source, importer_context)
        for dependency in importer_context.dependencies:
            context.AddDependency(dependency)
        if processorName:
            processor = self._processor(processorName, parameters)
            value = processor.Process(value, context)
        return value

    def _build_one(self, source: str, importerName: str | None,
                   processorName: str, parameters: OpaqueDataDictionary,
                   assetName: str, parent: "_ProcessorContext") -> str:
        target = os.path.join(self.OutputDirectory, assetName + ".xnb")
        context = _ProcessorContext(self, self._logger, parameters, target)
        value = self._import_and_process(
            source, importerName, processorName, parameters, context)
        self._write(value, target)
        for dependency in context.dependencies:
            parent.AddDependency(dependency)
        return target

    def _write(self, value: object, target: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        compiler = ContentCompiler()
        with open(target, "wb") as stream:
            compiler._compile(stream, value, self._platform(), self._profile(),
                              self.CompressContent, self.RootDirectory,
                              self.OutputDirectory)

    def _importer(self, name: str | None, source: str):
        if not name:
            name = self._importer_for_extension(source)
        component = self._component(name, self._scanner.ImporterNames, "importer")
        return component()

    def _processor(self, name: str, parameters: OpaqueDataDictionary):
        component = self._component(name, self._scanner.ProcessorNames, "processor")
        processor = component()
        for key in parameters.Keys:
            if hasattr(type(processor), key):
                try:
                    setattr(processor, key, parameters[key])
                except AttributeError:
                    # A processor whose property is read-only has fixed that
                    # setting on purpose; a parameter that tries to change it
                    # is ignored rather than failing the build, which is what
                    # XNA does with a parameter a processor does not accept.
                    pass
        return processor

    def _component(self, name: str | None, known: Sequence[str], kind: str):
        if not name:
            raise PipelineException(f"no {kind} was named for this asset")
        if name not in known:
            raise PipelineException(
                f"no {kind} named {name!r} was found; the ones scanned are "
                + (", ".join(known) if known else "(none)"))
        return self._scanner_component(name, kind)

    def _scanner_component(self, name: str, kind: str):
        import importlib

        for module_name in [item.ItemSpec for item in self.PipelineAssemblies]:
            module = importlib.import_module(module_name)
            component = getattr(module, name, None)
            if isinstance(component, type):
                return component
        raise PipelineException(
            f"the {kind} {name!r} was scanned but is no longer importable")

    def _importer_for_extension(self, source: str) -> str:
        from .._attributes import importer_attribute

        extension = os.path.splitext(source)[1].lower()
        for name in self._scanner.ImporterNames:
            attribute = self._scanner.ImporterAttributes[name]
            if extension in attribute.FileExtensions:
                return name
        raise PipelineException(
            f"no scanned importer claims {extension!r}, and the asset names none")

    def _asset_name(self, source: str) -> str:
        root = os.path.abspath(self.RootDirectory or ".")
        try:
            relative = os.path.relpath(os.path.abspath(source), root)
        except ValueError:
            relative = os.path.basename(source)
        if relative.startswith(os.pardir):
            relative = os.path.basename(source)
        return os.path.splitext(relative)[0].replace(os.sep, "/")

    def _is_current(self, source: str, target: str, entry: dict | None) -> bool:
        if entry is None or not os.path.exists(target):
            return False
        built = os.path.getmtime(target)
        if not os.path.exists(source) or os.path.getmtime(source) > built:
            return False
        for dependency in entry.get("dependencies", ()):
            if not os.path.exists(dependency) \
                    or os.path.getmtime(dependency) > built:
                return False
        return True

    def _read_cache(self) -> dict:
        path = self._cache_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, ValueError):
            # A cache that cannot be read is a cache that says nothing, which
            # means a full rebuild -- never a failure.
            return {}

    def _write_cache(self, cache: dict) -> None:
        path = self._cache_path()
        if not path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(cache, stream, indent=1, sort_keys=True)


def _parameters_of(item: TaskItem) -> OpaqueDataDictionary:
    """A source asset's ``ProcessorParameters`` metadata, as a dictionary.

    MSBuild spells them as one metadata entry per parameter, prefixed; a
    mapping supplied directly is taken as it is, which is what a caller driving
    the task from Python will pass.
    """
    parameters = OpaqueDataDictionary()
    direct = item.GetMetadata("ProcessorParameters")
    if direct is not None:
        if not hasattr(direct, "keys"):
            raise TypeError(
                "ProcessorParameters is a mapping of parameter names to values, "
                f"not {type(direct).__name__}")
        for key in direct.keys():
            parameters[str(key)] = direct[key]
    for key in tuple(item._metadata):
        if key.startswith("ProcessorParameters_"):
            parameters[key[len("ProcessorParameters_"):]] = item._metadata[key]
    return parameters


class CleanContent(_Task):
    """Deletes what a build produced, and the cache that recorded it."""

    __slots__ = ()

    ContentProjectGUID = _string_property("ContentProjectGUID")
    TargetPlatform = _string_property("TargetPlatform")
    TargetProfile = _string_property("TargetProfile")
    BuildConfiguration = _string_property("BuildConfiguration")
    RootDirectory = _string_property("RootDirectory")
    IntermediateDirectory = _string_property("IntermediateDirectory")
    OutputDirectory = _string_property("OutputDirectory")

    def Execute(self) -> bool:
        """Removes every file the cache says the last build wrote.

        The cache and not a wildcard: deleting ``*.xnb`` under the output
        directory would delete files another project put there, and a clean
        that removes someone else's output is worse than one that leaves a
        stale file behind.
        """
        path = self._cache_path()
        if not os.path.exists(path):
            return True
        try:
            with open(path, "r", encoding="utf-8") as stream:
                cache = json.load(stream)
        except (OSError, ValueError):
            os.remove(path)
            return True
        for entry in cache.values():
            for name in [entry.get("output")] + list(entry.get("outputs", ())):
                if name and os.path.exists(name):
                    os.remove(name)
        os.remove(path)
        return True


class GetLastOutputs(_Task):
    """Answers what the last build wrote, without building anything."""

    __slots__ = ()

    ContentProjectGUID = _string_property("ContentProjectGUID")
    IntermediateDirectory = _string_property("IntermediateDirectory")
    OutputContentFiles = _readonly_item_property("OutputContentFiles")

    def Execute(self) -> bool:
        path = self._cache_path()
        if not os.path.exists(path):
            self._values["OutputContentFiles"] = ()
            return True
        try:
            with open(path, "r", encoding="utf-8") as stream:
                cache = json.load(stream)
        except (OSError, ValueError):
            self._values["OutputContentFiles"] = ()
            return True
        names: list[str] = []
        for entry in cache.values():
            for name in [entry.get("output")] + list(entry.get("outputs", ())):
                if name and name not in names:
                    names.append(name)
        self._values["OutputContentFiles"] = tuple(
            TaskItem(name) for name in names)
        return True


class BuildXact(_Task):
    """Would build XACT audio projects. Refuses, and says what would let it.

    BLOCKED_FIXTURE: an ``.xap`` is compiled by Microsoft's XACT tool into a
    wave bank and a sound bank. The tool is Windows-only, is not redistributable,
    and CNA's ``xact.h`` reads banks rather than building them. Writing a
    partial compiler would produce banks that disagree with the ones the artist
    hears in the XACT authoring tool, which is worse than not building them.

    Unblocked by: a CNA route that compiles an XACT project, or an explicitly
    redistributable compiler this build may invoke. ``SoundEffectProcessor``
    builds ordinary sound effects and is fully implemented, so audio content
    reaches the runtime today by the other path.
    """

    __slots__ = ()

    XactProjects = _item_property("XactProjects")
    XnaFrameworkVersion = _string_property("XnaFrameworkVersion")
    ContentProjectGUID = _string_property("ContentProjectGUID")
    TargetPlatform = _string_property("TargetPlatform")
    TargetProfile = _string_property("TargetProfile")
    BuildConfiguration = _string_property("BuildConfiguration")
    RootDirectory = _string_property("RootDirectory")
    LoggerRootDirectory = _string_property("LoggerRootDirectory")
    OutputDirectory = _string_property("OutputDirectory")
    IntermediateDirectory = _string_property("IntermediateDirectory")
    RebuildAll = _flag_property("RebuildAll")
    OutputXactFiles = _readonly_item_property("OutputXactFiles")
    RebuiltXactFiles = _readonly_item_property("RebuiltXactFiles")
    IntermediateFiles = _readonly_item_property("IntermediateFiles")

    def Execute(self) -> bool:
        if not self.XactProjects:
            # Nothing to build is a successful build, and is the case a content
            # project with no XACT content is in.
            self._values["OutputXactFiles"] = ()
            self._values["RebuiltXactFiles"] = ()
            self._values["IntermediateFiles"] = ()
            return True
        names = ", ".join(item.ItemSpec for item in self.XactProjects)
        raise NotImplementedError(
            f"BuildXact cannot compile {names}: an .xap is built by Microsoft's "
            "XACT tool, which is Windows-only and not redistributable, and "
            "CNA's xact.h reads wave and sound banks rather than building them. "
            "SoundEffectProcessor builds ordinary sound effects and is fully "
            "implemented. Unblocked by a CNA route that compiles an XACT "
            "project.")
