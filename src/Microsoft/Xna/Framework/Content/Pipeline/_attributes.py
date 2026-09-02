"""The two attributes that make a class findable by the build.

.NET finds importers and processors by *attribute*: a class is a content
importer because it carries ``[ContentImporter(".fbx")]``, not because it is
named something. Python has decorators, and a decorator is exactly an attribute
that runs, so both of these are usable in either shape:

    @ContentImporterAttribute(".wav", DisplayName="Wav Importer")
    class MyImporter(ContentImporterOfT): ...

and the scanner reads the attribute back off the class. Applying one records it
on the class under a private name and returns the class unchanged, so a
decorated importer is still exactly the class that was written.
"""

from __future__ import annotations

from typing import Sequence

#: Where an applied attribute is recorded on the class it decorates.
_IMPORTER_ATTRIBUTE = "_xna_content_importer_attribute"
_PROCESSOR_ATTRIBUTE = "_xna_content_processor_attribute"


class ContentImporterAttribute:
    """Declares that a class imports files with the given extensions.

    ``CacheImportedData`` asks the build to keep the imported object between
    builds rather than re-importing it; ``DefaultProcessor`` names the processor
    a build tool should offer first for content this importer produced.
    """

    __slots__ = ("_file_extensions", "_cache_imported_data", "_display_name",
                 "_default_processor")

    def __init__(self, *fileExtensions: object, **options: object) -> None:
        extensions = _extensions(fileExtensions)
        if not extensions:
            raise ValueError("a content importer needs at least one file extension")
        self._file_extensions = extensions
        self._cache_imported_data = False
        self._display_name = ""
        self._default_processor = ""
        for name, value in options.items():
            if name not in ("CacheImportedData", "DisplayName", "DefaultProcessor"):
                raise TypeError(f"unknown ContentImporterAttribute option {name!r}")
            setattr(self, name, value)

    def __call__(self, target: type) -> type:
        setattr(target, _IMPORTER_ATTRIBUTE, self)
        return target

    @property
    def FileExtensions(self) -> tuple[str, ...]:
        return self._file_extensions

    @property
    def CacheImportedData(self) -> bool:
        return self._cache_imported_data

    @CacheImportedData.setter
    def CacheImportedData(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("CacheImportedData must be a bool")
        self._cache_imported_data = value

    @property
    def DisplayName(self) -> str:
        return self._display_name

    @DisplayName.setter
    def DisplayName(self, value: str) -> None:
        self._display_name = _name(value, "DisplayName")

    @property
    def DefaultProcessor(self) -> str:
        return self._default_processor

    @DefaultProcessor.setter
    def DefaultProcessor(self, value: str) -> None:
        self._default_processor = _name(value, "DefaultProcessor")

    def __repr__(self) -> str:
        return f"ContentImporterAttribute({list(self._file_extensions)!r})"


class ContentProcessorAttribute:
    """Declares that a class is a content processor a build tool may offer."""

    __slots__ = ("_display_name",)

    def __init__(self, **options: object) -> None:
        self._display_name = ""
        for name, value in options.items():
            if name != "DisplayName":
                raise TypeError(f"unknown ContentProcessorAttribute option {name!r}")
            setattr(self, name, value)

    def __call__(self, target: type) -> type:
        setattr(target, _PROCESSOR_ATTRIBUTE, self)
        return target

    @property
    def DisplayName(self) -> str:
        return self._display_name

    @DisplayName.setter
    def DisplayName(self, value: str) -> None:
        self._display_name = _name(value, "DisplayName")

    def __repr__(self) -> str:
        return f"ContentProcessorAttribute(DisplayName={self._display_name!r})"


def _extensions(values: Sequence[object]) -> tuple[str, ...]:
    """XNA's two constructors -- one extension, or a sequence of them.

    A sequence passed as the single argument is the array overload; separate
    arguments are the ``params`` spelling of the same thing. Both arrive here.
    """
    if len(values) == 1 and not isinstance(values[0], str):
        candidate = values[0]
        if not isinstance(candidate, (list, tuple)):
            raise TypeError(
                "fileExtensions must be a string or a sequence of strings, not "
                f"{type(candidate).__name__}")
        values = tuple(candidate)
    result = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError(
                f"a file extension must be a str, not {type(value).__name__}")
        if not value.startswith("."):
            raise ValueError(f"a file extension must begin with a dot: {value!r}")
        result.append(value.lower())
    return tuple(result)


def _name(value: object, what: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a str, not {type(value).__name__}")
    return value


def importer_attribute(target: type) -> ContentImporterAttribute | None:
    """The ``ContentImporterAttribute`` applied to ``target``, if any.

    Read off the class itself rather than its bases: an importer that derives
    from another importer does not inherit its file extensions, because two
    importers claiming the same extension is exactly the ambiguity the scanner
    reports as an error.
    """
    return target.__dict__.get(_IMPORTER_ATTRIBUTE)


def processor_attribute(target: type) -> ContentProcessorAttribute | None:
    """The ``ContentProcessorAttribute`` applied to ``target``, if any."""
    return target.__dict__.get(_PROCESSOR_ATTRIBUTE)


ContentImporterAttribute.__xna_arities__ = {"__init__": {1}}
ContentProcessorAttribute.__xna_arities__ = {"__init__": {0}}
