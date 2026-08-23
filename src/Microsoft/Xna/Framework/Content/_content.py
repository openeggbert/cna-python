"""Honest ContentManager foundation; XNB loading is not yet implemented."""

from __future__ import annotations


class ContentLoadException(Exception):
    """Mapped XNA content-loading failure."""


class ContentManager:
    def __init__(self, serviceProvider: object, rootDirectory: str = "") -> None:
        self._disposed = False
        self._root_directory = str(rootDirectory)

    @property
    def RootDirectory(self) -> str:
        return self._root_directory

    @RootDirectory.setter
    def RootDirectory(self, value: str) -> None:
        if self._disposed:
            raise RuntimeError("ContentManager is disposed")
        if value is None:
            raise TypeError("RootDirectory cannot be None")
        self._root_directory = str(value)

    def Load(self, assetName: str):
        if self._disposed:
            raise RuntimeError("ContentManager is disposed")
        if not isinstance(assetName, str) or not assetName:
            raise ValueError("assetName must be a non-empty string")
        raise ContentLoadException(
            "ContentManager.Load/XNB is not implemented in the current CNA-Python slice; "
            "use Texture2D.FromStream for raw PNG/JPEG assets"
        )

    def Unload(self) -> None:
        if self._disposed:
            raise RuntimeError("ContentManager is disposed")

    def Dispose(self) -> None:
        self._disposed = True

    def __enter__(self) -> "ContentManager":
        if self._disposed:
            raise RuntimeError("ContentManager is disposed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()
