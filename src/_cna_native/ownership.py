"""Single deterministic ownership state machine for native handles."""

from __future__ import annotations

from enum import Enum
from typing import Callable
import weakref


class Ownership(Enum):
    OWNED = "owned"
    BORROWED = "borrowed"
    PARENT_OWNED = "parent-owned"


class NativeResource:
    """Private base for explicitly disposed native XNA resources.

    No finalizer calls CNA: interpreter shutdown may already have unloaded the
    dynamic library. Explicit ``Dispose`` and context management are primary.
    """

    __slots__ = ("_handle", "_ownership", "_release", "_parent_ref", "_disposed", "__weakref__")

    def __init__(self, handle: int, ownership: Ownership, release: Callable[[int], None] | None,
                 parent: object | None = None) -> None:
        if handle == 0:
            raise ValueError("native handle zero is invalid")
        self._handle = handle
        self._ownership = ownership
        self._release = release
        self._parent_ref = weakref.ref(parent) if parent is not None else None
        self._disposed = False
        if parent is not None and hasattr(parent, "_register_native_child"):
            parent._register_native_child(self)

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def _require_handle(self) -> int:
        if self._disposed:
            raise RuntimeError(f"{type(self).__name__} is disposed")
        if self._parent_ref is not None:
            parent = self._parent_ref()
            if parent is None or getattr(parent, "_disposed", False):
                raise RuntimeError(f"{type(self).__name__}'s parent is disposed")
        return self._handle

    def Dispose(self) -> None:
        if self._disposed:
            return
        if self._ownership is Ownership.OWNED and self._release is not None:
            self._release(self._handle)
        self._disposed = True
        self._handle = 0
        parent = self._parent_ref() if self._parent_ref is not None else None
        if parent is not None and hasattr(parent, "_unregister_native_child"):
            parent._unregister_native_child(self)

    def __enter__(self):
        self._require_handle()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


class ChildRegistry:
    __slots__ = ("_native_children",)

    def _init_child_registry(self) -> None:
        self._native_children: list[weakref.ReferenceType[NativeResource]] = []

    def _register_native_child(self, child: NativeResource) -> None:
        self._native_children.append(weakref.ref(child))

    def _unregister_native_child(self, child: NativeResource) -> None:
        self._native_children = [reference for reference in self._native_children if reference() not in (None, child)]

    def _dispose_native_children(self) -> None:
        first_error: BaseException | None = None
        for reference in reversed(self._native_children):
            child = reference()
            if child is None or child.IsDisposed:
                continue
            try:
                child.Dispose()
            except BaseException as error:
                if first_error is None:
                    first_error = error
        self._native_children.clear()
        if first_error is not None:
            raise first_error
