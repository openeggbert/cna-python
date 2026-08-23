"""Honest ContentManager foundation; XNB loading is not yet implemented."""

from __future__ import annotations


class ContentLoadException(Exception):
    """Mapped XNA content-loading failure."""

    def __init__(self, *args: object) -> None:
        if not args:
            super().__init__()
        elif len(args) == 1 and isinstance(args[0], str):
            super().__init__(args[0])
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], Exception):
            super().__init__(args[0])
            self.__cause__ = args[1]
        elif len(args) == 2:
            raise TypeError("serialization-info construction is not available in the Python projection")
        else:
            raise TypeError("ContentLoadException expects (), message, or message and innerException")


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

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        self._disposed = True

    def __enter__(self) -> "ContentManager":
        if self._disposed:
            raise RuntimeError("ContentManager is disposed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


ContentLoadException.__xna_arities__ = {"__init__": {0, 1, 2}}
ContentManager.__xna_arities__ = {"Dispose": {0, 1}}
