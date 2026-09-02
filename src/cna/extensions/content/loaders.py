"""Registering a Python loader for a game-defined `.cnb` asset type, and running it.

CNA's `.cnb` loader registry is **process-wide** and outlives any content
manager, matching how the ``.xnb`` reader table already works. It accepts a
**custom** asset type identifier only -- one minted by
:func:`asset_type_id_from_name <cna.extensions.content.asset_type_id_from_name>`
-- because CNA's built-in and reserved identifiers belong to CNA and there is
deliberately no parameter by which a caller can claim one.

How a Python loader returns its object
--------------------------------------

CNA's loader contract hands back a ``void*`` that the ABI never dereferences,
copies or frees. Python has no safe raw pointer to give it, so this module gives
CNA an opaque **token** instead: a small integer that is a key into a table here,
never a Python object address. :meth:`CnbLoader.invoke` reads the token back out
and returns the real object. The pointer is meaningless outside this process and
is never dereferenced by anyone, which is exactly what the ABI promises.

That is the honest boundary, not a general one. A loader registered here produces
something only Python can unbox; CNA's own built-in loaders construct C++ objects
and refuse to hand them across the C boundary at all, which :meth:`CnbLoader.invoke`
reports as :class:`CnbUnsupportedError <cna.extensions.content.CnbUnsupportedError>`
rather than papering over.

Callback safety
---------------

The Python callable is held by a **strong** reference for the registration's whole
lifetime -- never a weak one, because CNA holds a raw function pointer and a
collected callable would be a dangling call. No Python exception is allowed to
unwind through a C frame: one raised inside a loader is captured, turned into a
failed load in CNA's own vocabulary, and re-raised on the Python side after CNA
has returned through its own frames.

The native content manager
--------------------------

Invoking a loader needs a :class:`NativeContentManager` because CNA's loader
signature takes one by reference -- there is no "no manager" to pass. That is a
**separate cache domain** from ``Microsoft.Xna.Framework.Content.ContentManager``:
nothing is shared between them, there is no fallback in either direction, and the
strict manager keeps reading only ``.xnb``.
"""

from __future__ import annotations

import ctypes as c
import itertools
import os
import threading
from typing import Callable

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .document import CnbDocument
from .errors import CnbError, CnbInternalError

__all__ = [
    "CnbLoader",
    "LoaderRegistration",
    "NativeContentManager",
    "clear_loader_registry",
    "find_loader",
    "is_loader_registered",
    "register_builtin_loaders",
    "register_loader",
    "registered_type_name",
    "resolve_loader",
]

_LOCK = threading.Lock()
_TOKENS = itertools.count(1)
#: Objects Python loaders have produced but nothing has collected yet, keyed by
#: the token handed to CNA.  Process-wide because a token may be handed back
#: through any of the invoke paths, not only the one that registered it.
_PENDING: dict[int, object] = {}
#: Exceptions raised inside a Python loader, waiting to be re-raised once CNA has
#: returned through its own frames.
_FAILURES: list[BaseException] = []


class NativeContentManager:
    """CNA's own native content manager, opened only so a `.cnb` loader can run.

    **This is not, and does not touch,**
    ``Microsoft.Xna.Framework.Content.ContentManager``. The two are separate
    objects with separate caches: nothing loaded through one appears in the
    other, neither falls back to the other, and the strict manager still reads
    only ``.xnb``. This one exists because :meth:`CnbLoader.invoke` must pass a
    manager and CNA requires a real one.

    It must be created and closed on the thread that created the ``Game``, and
    closed before that ``Game`` is disposed -- CNA's rule, restated here because
    breaking it is a crash rather than an exception.
    """

    __slots__ = ("_handle",)

    def __init__(self, graphics_device, *,
                 root_directory: "str | os.PathLike[str]" = "") -> None:
        """Opens a manager against a live ``GraphicsDevice``.

        ``root_directory`` is prepended to asset names when a loader resolves an
        external reference through this manager; an empty root is valid.
        """
        device_handle = getattr(graphics_device, "_handle", 0)
        if not device_handle:
            raise ValueError(
                "a live Microsoft.Xna.Framework.Graphics.GraphicsDevice is required")
        info = _abi.CNA_ContentManagerCreateInfo()
        info.struct_size = c.sizeof(_abi.CNA_ContentManagerCreateInfo)
        info.struct_version = _abi.CNA_CONTENT_MANAGER_CREATE_INFO_STRUCT_VERSION
        view, keep = _support.string_view(os.fspath(root_directory), "root_directory")
        info.root_directory = view
        info.reserved = 0
        handle = _support.out_handle(
            "cna_content_manager_create", c.c_uint64(int(device_handle)), c.byref(info))
        del keep
        self._handle = _support.NativeHandle(
            handle, "cna_content_manager_destroy", "native content manager")

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the manager; must run on the game creation thread."""
        self._handle.close()

    def __enter__(self) -> "NativeContentManager":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    def __repr__(self) -> str:
        return ("<NativeContentManager closed>" if self.closed
                else "<NativeContentManager open>")


class CnbLoader:
    """A resolved copy of one registered `.cnb` loader, ready to invoke.

    CNA hands the loader back **by value** on purpose: a pointer into the
    registry would be invalidated by any later registration that rehashes it, and
    the caller would have no way to know. This holds that copy, so it stays valid
    across registrations and can be invoked on a document other than the one it
    was resolved from.

    Owns a native handle: close it, or use it as a context manager.
    """

    __slots__ = ("_handle",)

    def __init__(self) -> None:
        raise TypeError(
            "CnbLoader is produced by this module's own operations and is not "
            "constructed directly")

    @classmethod
    def _wrap(cls, handle: _support.NativeHandle) -> "CnbLoader":
        """Builds the facade around an already-owned handle.

        Private, and it bypasses ``__init__`` deliberately: the public
        signature a caller reads must not name a native type, and there is
        no owned handle a caller could supply anyway.
        """
        self = cls.__new__(cls)
        self._handle = handle
        return self

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the resolved loader copy."""
        self._handle.close()

    def __enter__(self) -> "CnbLoader":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def invoke(self, document: CnbDocument, manager: NativeContentManager, *,
               asset_name: str = "") -> object:
        """Runs the loader on ``document`` and returns what it produced.

        Only a loader registered from Python produces something Python can hold.
        CNA's own built-in loaders construct C++ objects, and this reports that
        as :class:`CnbUnsupportedError
        <cna.extensions.content.CnbUnsupportedError>` rather than handing back a
        pointer nothing here could name. That is the same boundary a
        caller-supplied ``.xnb`` reader has, from the other side.
        """
        view, keep = _support.string_view(asset_name, "asset_name")
        pointer = c.c_void_p()
        del _FAILURES[:]
        try:
            _support.call("cna_cnb_loader_invoke", c.c_uint64(self._handle.value),
                          document._value, manager._value, view, c.byref(pointer))
        except CnbError:
            # A Python loader's own exception is the truer cause than the result
            # code CNA turned it into, so it wins.
            if _FAILURES:
                raise _FAILURES[0]
            raise
        finally:
            del keep
        token = int(pointer.value or 0)
        if token not in _PENDING:
            raise CnbInternalError(
                "cna_cnb_loader_invoke", 0, None,
                "the loader produced an object this process did not create")
        return _PENDING.pop(token)

    def __repr__(self) -> str:
        return "<CnbLoader closed>" if self.closed else "<CnbLoader resolved>"


class LoaderRegistration:
    """One live Python loader registration for a custom `.cnb` asset type.

    Registration is **process-wide**: it is not scoped to a content manager, and
    it lasts until :meth:`close` withdraws it. Use it as a context manager so
    withdrawal is deterministic rather than left to the garbage collector, which
    would leave CNA holding a pointer to a callable Python had freed.
    """

    __slots__ = ("_asset_type_id", "_type_name", "_loader", "_bridge", "_closed")

    def __init__(self, asset_type_id: int, type_name: str,
                 loader: Callable[[CnbDocument, str], object]) -> None:
        self._asset_type_id = int(asset_type_id)
        self._type_name = type_name
        # Strong references, deliberately: CNA holds a raw function pointer, so a
        # weakly-held callable or trampoline would be a dangling call the moment
        # Python collected it.
        self._loader = loader
        self._closed = False
        self._bridge = _abi.CNA_CnbLoaderCallback(self._dispatch)

    def _dispatch(self, _context, document_handle, _manager_handle, asset_name,
                  out_object) -> int:
        """The C entry point. No exception may leave this frame."""
        try:
            name = (bytes(asset_name.data[: asset_name.byte_length]).decode("utf-8")
                    if asset_name.data and asset_name.byte_length else "")
            # A callback-scoped borrow: CNA invalidates it before this returns, so
            # the wrapper gives the handle up rather than destroying memory that
            # belongs to whoever called the loader.
            borrowed = CnbDocument._wrap(_support.NativeHandle(
                int(document_handle), "cna_cnb_document_destroy", "document"))
            try:
                value = self._loader(borrowed, name)
            finally:
                borrowed._handle.release()
            with _LOCK:
                token = next(_TOKENS)
                _PENDING[token] = value
            out_object[0] = c.c_void_p(token)
            return 0
        except BaseException as error:  # noqa: BLE001 - re-raised after native return
            _FAILURES.append(error)
            return 5  # CNA_RESULT_IO: the load failed, in CNA's own vocabulary.

    @property
    def asset_type_id(self) -> int:
        """The custom asset type identifier this loader is registered for."""
        return self._asset_type_id

    @property
    def type_name(self) -> str:
        """The canonical type name the registration was made under."""
        return self._type_name

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Withdraws the registration.

        After this, CNA no longer holds a pointer to the Python callable. Any
        object a loader produced that nothing collected is dropped with it.
        """
        if self._closed:
            return
        self._closed = True
        removed = c.c_uint8()
        _support.call("cna_cnb_loader_registry_remove",
                      c.c_uint32(self._asset_type_id), c.byref(removed))

    def __enter__(self) -> "LoaderRegistration":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def load(self, document: CnbDocument, manager: NativeContentManager, *,
             asset_name: str = "") -> object:
        """Resolves this registration's loader for ``document`` and runs it.

        The convenience path: :func:`resolve_loader` then
        :meth:`CnbLoader.invoke`, with the resolved copy released either way.
        """
        if self._closed:
            raise ValueError("this loader registration is closed")
        with resolve_loader(document) as loader:
            return loader.invoke(document, manager, asset_name=asset_name)

    def __repr__(self) -> str:
        state = "closed" if self._closed else "open"
        return f"<LoaderRegistration {self._type_name} {state}>"


def register_loader(type_name: str,
                    loader: Callable[[CnbDocument, str], object]) -> LoaderRegistration:
    """Registers ``loader`` for the custom asset type ``type_name`` names.

    The identifier is minted from ``type_name`` the same way
    :func:`asset_type_id_from_name <cna.extensions.content.asset_type_id_from_name>`
    mints it, so the name a file carries and the name the loader is registered
    under are the same string by construction.

    ``loader`` is called as ``loader(document, asset_name)`` and returns any
    Python object. The document it receives is **callback-scoped**: CNA
    invalidates it before the callback returns, so read what is needed and do not
    keep it.

    Registering the same identifier twice under the same name is accepted and has
    no effect. Under a *different* name it is refused -- that is the
    hash-collision case a 31-bit identifier space makes possible, and letting the
    second registration win would mean loading one game type's file with
    another's loader.
    """
    from .format import asset_type_id_from_name

    asset_type_id = asset_type_id_from_name(type_name)
    registration = LoaderRegistration(asset_type_id, type_name, loader)
    view, keep = _support.string_view(type_name, "type_name")
    with _LOCK:
        _support.call("cna_cnb_loader_registry_register",
                      c.c_uint32(asset_type_id), view, registration._bridge, None)
    del keep
    return registration


def resolve_loader(document: CnbDocument) -> CnbLoader:
    """The loader that may decode ``document``, proving identity as well as number.

    For a **built-in** asset type the number is authoritative: CNA assigns those
    and they are frozen, so a match is proof of identity and the file's ``CMET``
    type name is not consulted.

    For a **custom** one it is not. A custom identifier is a 31-bit hash, so two
    unrelated game types can legitimately collide. This therefore also requires
    the file to carry a canonical type name equal to the registered one. A file
    whose number matches but whose name does not is refused: it is a different
    type that happens to collide, and decoding it with this loader would silently
    misinterpret someone's content.
    """
    return CnbLoader._wrap(_support.NativeHandle(
        _support.out_handle(
            "cna_cnb_loader_registry_resolve_for_document", document._value),
        "cna_cnb_loader_destroy", "loader"))


def find_loader(asset_type_id: int) -> CnbLoader | None:
    """The loader registered for an identifier, looked up **by number alone**.

    This performs no type-name check, so it is the wrong entry point for loading
    a file -- use :func:`resolve_loader` for that. It exists for tooling that
    wants to ask what is registered without holding a document, and it answers
    with a real invocable loader rather than only a boolean, which is what
    separates it from :func:`is_loader_registered`.

    Absence is an ordinary answer: ``None``, not a refusal.
    """
    found = c.c_uint8()
    handle = c.c_uint64()
    _support.call("cna_cnb_loader_registry_find",
                  c.c_uint32(_support.checked(int(asset_type_id), "uint32",
                                              "asset_type_id")),
                  c.byref(found), c.byref(handle))
    if not found.value:
        return None
    return CnbLoader._wrap(_support.NativeHandle(
        int(handle.value), "cna_cnb_loader_destroy", "loader"))


def is_loader_registered(asset_type_id: int) -> bool:
    """Whether any loader is registered for an asset type identifier."""
    return _support.out_bool(
        "cna_cnb_loader_registry_is_registered",
        c.c_uint32(_support.checked(int(asset_type_id), "uint32", "asset_type_id")))


def registered_type_name(asset_type_id: int) -> str:
    """The canonical type name an identifier was registered under, or ``""``."""
    return _support.sized_text(
        "cna_cnb_loader_registry_get_registered_type_name_size",
        "cna_cnb_loader_registry_copy_registered_type_name",
        (c.c_uint32(_support.checked(int(asset_type_id), "uint32", "asset_type_id")),),
        "registered type name")


def register_builtin_loaders() -> None:
    """Registers the built-in loaders that need nothing but their own codec.

    ``Curve`` and ``AnimationClip`` -- **not** every built-in type. The other
    eight construct a runtime object that needs a graphics device or the content
    manager itself, and are registered by a content manager instead. Idempotent.
    """
    _support.call("cna_cnb_loader_registry_register_builtins")


def clear_loader_registry() -> None:
    """Withdraws **every** registration, this process's and CNA's own.

    Primarily for test isolation, and blunt on purpose. A caller that clears the
    table and wants the whole of it back must construct a content manager: eight
    of the built-in loaders construct a runtime object and are installed by the
    manager, so :func:`register_builtin_loaders` alone does not restore them.
    Any :class:`LoaderRegistration` still open is left holding a registration
    that no longer exists; close it as usual.
    """
    _support.call("cna_cnb_loader_registry_clear")
    with _LOCK:
        _PENDING.clear()
