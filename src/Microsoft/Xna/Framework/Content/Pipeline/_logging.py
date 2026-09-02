"""Where a build says what it is doing.

``ContentBuildLogger`` is abstract in spirit and concrete in shape: XNA's own
methods are ``abstract``, and the file stack around them is not. A build tool
subclasses this and implements the three message methods; the stack of files
being processed is kept here so that every subclass reports the same thing.

The stack is the part worth explaining. A processor that builds a texture on
behalf of a model pushes the texture's file name; a warning raised while it is
pushed names the texture, and one raised after the pop names the model again.
``GetCurrentFilename`` is what a subclass calls to find out which is which, and
its answer is *relative to* ``LoggerRootDirectory`` so that the message a user
reads is not an absolute path from the build machine.
"""

from __future__ import annotations

import os

from ._identity import ContentIdentity


class ContentBuildLogger:
    """The build's message sink and its stack of files."""

    __slots__ = ("_files", "_logger_root_directory")

    def __init__(self) -> None:
        self._files: list[str] = []
        self._logger_root_directory = ""

    @property
    def LoggerRootDirectory(self) -> str:
        return self._logger_root_directory

    @LoggerRootDirectory.setter
    def LoggerRootDirectory(self, value: str) -> None:
        if value is None:
            self._logger_root_directory = ""
            return
        if not isinstance(value, str):
            raise TypeError(
                f"LoggerRootDirectory must be a str, not {type(value).__name__}")
        self._logger_root_directory = value

    def LogMessage(self, message: str, *messageArgs: object) -> None:
        """An ordinary progress message. Abstract in XNA, and abstract here."""
        raise NotImplementedError(
            f"{type(self).__name__}.LogMessage must be overridden")

    def LogImportantMessage(self, message: str, *messageArgs: object) -> None:
        """A message a build tool should show even when messages are hidden."""
        raise NotImplementedError(
            f"{type(self).__name__}.LogImportantMessage must be overridden")

    def LogWarning(self, helpLink: str, contentIdentity: ContentIdentity | None,
                   message: str, *messageArgs: object) -> None:
        """A warning about one piece of content."""
        raise NotImplementedError(
            f"{type(self).__name__}.LogWarning must be overridden")

    def PushFile(self, filename: str) -> None:
        if not isinstance(filename, str):
            raise TypeError(f"filename must be a str, not {type(filename).__name__}")
        self._files.append(filename)

    def PopFile(self) -> None:
        if not self._files:
            raise RuntimeError("PopFile without a matching PushFile")
        self._files.pop()

    def GetCurrentFilename(self, contentIdentity: ContentIdentity | None) -> str | None:
        """The file a message belongs to, relative to the logger's root.

        The identity wins when it names a source file, because it is the more
        specific answer -- it is the file the *content* came from rather than
        the file the build happens to be inside. Otherwise the top of the stack
        is the answer, and an empty stack means there is no file to name.
        """
        source = contentIdentity.SourceFilename if contentIdentity is not None else None
        if not source:
            if not self._files:
                return None
            source = self._files[-1]
        return self._relative(source)

    def _relative(self, filename: str) -> str:
        root = self._logger_root_directory
        if not root:
            return filename
        try:
            relative = os.path.relpath(filename, root)
        except ValueError:
            # Different drives on Windows: there is no relative path, and the
            # absolute one is a true answer where a fabricated one would not be.
            return filename
        if relative.startswith(os.pardir + os.sep) or relative == os.pardir:
            return filename
        return relative


ContentBuildLogger.__xna_arities__ = {
    "LogMessage": {2}, "LogImportantMessage": {2}, "LogWarning": {4},
}
