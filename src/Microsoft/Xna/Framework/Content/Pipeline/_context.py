"""What an importer and a processor are handed by the build that runs them.

Both are abstract in XNA and abstract here: the build tool owns the output
directories, the dependency list and the nested-build machinery, so a context is
something a *build* provides rather than something the pipeline library can
construct on its own. ``Tasks.BuildContent`` provides the concrete pair, and
that is where the real behaviour lives.

Projecting them as abstract is not a gap. A processor is written against these
two types and is tested by being handed a context; making the abstract shape
public and the concrete one internal is exactly XNA's arrangement, and it is
what lets a caller supply a context of their own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._collections import OpaqueDataDictionary
from ._logging import ContentBuildLogger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...Graphics import GraphicsProfile
    from ._identity import ExternalReferenceOfT
    from ._target import TargetPlatform


class ContentImporterContext:
    """The services an importer may use while reading a file."""

    __slots__ = ()

    @property
    def Logger(self) -> ContentBuildLogger:
        raise NotImplementedError(
            f"{type(self).__name__}.Logger must be overridden")

    @property
    def OutputDirectory(self) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.OutputDirectory must be overridden")

    @property
    def IntermediateDirectory(self) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.IntermediateDirectory must be overridden")

    def AddDependency(self, filename: str) -> None:
        """Records that the imported asset must be rebuilt if ``filename`` changes.

        An importer that reads a second file -- a material library beside a
        model, an include beside an effect -- has to say so, or the build will
        not notice when that file is edited.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.AddDependency must be overridden")


class ContentProcessorContext:
    """The services a processor may use, including running other processors.

    ``BuildAsset``, ``BuildAndLoadAsset`` and ``Convert`` are the three ways a
    processor reaches other content, and the difference between them is where
    the result ends up: ``BuildAsset`` builds a *separate* asset and answers a
    reference to it, ``BuildAndLoadAsset`` builds it and hands back the object,
    and ``Convert`` runs a processor on an object already in hand with no file
    involved at all.
    """

    __slots__ = ()

    @property
    def Logger(self) -> ContentBuildLogger:
        raise NotImplementedError(
            f"{type(self).__name__}.Logger must be overridden")

    @property
    def Parameters(self) -> OpaqueDataDictionary:
        raise NotImplementedError(
            f"{type(self).__name__}.Parameters must be overridden")

    @property
    def TargetPlatform(self) -> "TargetPlatform":
        raise NotImplementedError(
            f"{type(self).__name__}.TargetPlatform must be overridden")

    @property
    def TargetProfile(self) -> "GraphicsProfile":
        raise NotImplementedError(
            f"{type(self).__name__}.TargetProfile must be overridden")

    @property
    def BuildConfiguration(self) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.BuildConfiguration must be overridden")

    @property
    def OutputFilename(self) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.OutputFilename must be overridden")

    @property
    def OutputDirectory(self) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.OutputDirectory must be overridden")

    @property
    def IntermediateDirectory(self) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.IntermediateDirectory must be overridden")

    def AddDependency(self, filename: str) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.AddDependency must be overridden")

    def AddOutputFile(self, filename: str) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.AddOutputFile must be overridden")

    def BuildAsset(self, sourceAsset: "ExternalReferenceOfT",
                   processorName: str, *rest: object):
        """XNA's two ``BuildAsset`` overloads, arity 2 and arity 5."""
        raise NotImplementedError(
            f"{type(self).__name__}.BuildAsset must be overridden")

    def BuildAndLoadAsset(self, sourceAsset: "ExternalReferenceOfT",
                          processorName: str, *rest: object):
        """XNA's two ``BuildAndLoadAsset`` overloads, arity 2 and arity 4."""
        raise NotImplementedError(
            f"{type(self).__name__}.BuildAndLoadAsset must be overridden")

    def Convert(self, input: object, processorName: str, *rest: object):
        """XNA's two ``Convert`` overloads, arity 2 and arity 3."""
        raise NotImplementedError(
            f"{type(self).__name__}.Convert must be overridden")


ContentImporterContext.__xna_arities__ = {"__init__": {0}}
ContentProcessorContext.__xna_arities__ = {
    "__init__": {0}, "BuildAsset": {2, 5}, "BuildAndLoadAsset": {2, 4},
    "Convert": {2, 3},
}
