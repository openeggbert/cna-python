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

    __slots__ = ("_handle", "_ownership", "_release", "_parent_ref", "_disposed",
                 "_retained", "_before_release", "__weakref__")

    def __init__(self, handle: int, ownership: Ownership, release: Callable[[int], None] | None,
                 parent: object | None = None) -> None:
        if handle == 0:
            raise ValueError("native handle zero is invalid")
        self._handle = handle
        self._ownership = ownership
        self._release = release
        self._parent_ref = weakref.ref(parent) if parent is not None else None
        self._disposed = False
        self._retained: list[object] = []
        self._before_release: Callable[[], None] | None = None
        if parent is not None and hasattr(parent, "_register_native_child"):
            parent._register_native_child(self)

    def retain_for_registration(self, value: object) -> None:
        """Roots one object for exactly as long as this handle's registrations live.

        A ctypes callback handed to CNA stays caller-owned until unregistration or
        resource destruction.  Rooting it only on the public facade is not enough:
        the facade and its closure form a cycle that the collector may reclaim while
        CNA still holds the raw trampoline pointer, so the next native event would
        call freed memory.  The owning handle outlives the facade, so the callback
        is rooted here instead.
        """
        self._retained.append(value)

    def set_before_release(self, hook: Callable[[], None]) -> None:
        """Registers the owning facade's teardown so every release path runs it.

        A facade may own further native views that must be released before its own
        handle.  Its ``Dispose`` does that, but shutdown releases the handle through
        this object, which the owning generation retains rather than the facade.
        Without the hook that path would free the handle while its views were still
        live, and the runtime would refuse to destroy the game.  The hook must be
        idempotent, because both paths may reach it.
        """
        self._before_release = hook

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
        if self._before_release is not None:
            self._before_release()
        if self._ownership is Ownership.OWNED and self._release is not None:
            self._release(self._handle)
        self._disposed = True
        self._handle = 0
        # The native registrations died with the handle, so nothing rooted for them
        # can still be reached from C.
        self._retained.clear()
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
