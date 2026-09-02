"""Compiling one `.cnj` source document, and the sidecars it names, into `.cnb`.

`.cnj` is CNA's *source* content document: a small JSON file naming an asset's
type and the binary sidecars that hold its bulk. Compiling one produces the
finished `.cnb` byte image plus two lists a build system needs -- which files
were **absorbed** into the output, and which assets it still **references** by
logical name.

There is no second `.cnj` parser here. CNA's compiler is the authority for what a
`.cnj` means, including which sidecar paths it will and will not resolve; this
module hands it a path and reports what it produced.

Path handling is deliberately thin: the wrapper adds no normalisation, no ``..``
collapsing and no symlink resolution of its own, because any of those would widen
the trust boundary CNA defines rather than honour it.

**``content_root`` is a containment boundary, not a resolution base.** A sidecar
always resolves relative to the `.cnj` document's own directory; ``content_root``
is the directory the resolved path must stay inside, and an empty one means the
document's parent. Measured against CNA 0.21, whose ``cnb.h`` prose says
"directory sidecar references resolve against" -- the implementation
(``ResolveCnjSourceFileSafely``) joins to the referring document and then checks
containment, and that is what is documented here.
"""

from __future__ import annotations

import ctypes as c
import os

from _cna_native import cnb_support as _support

__all__ = ["CnjCompilation", "compile_cnj"]


class CnjCompilation:
    """What compiling one `.cnj` produced.

    Owns native memory -- the compiled bytes and both file lists -- so it has an
    explicit :meth:`close` and works as a context manager. Every property is a
    plain Python value; no handle and no native identity is exposed.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the result and the bytes it holds."""
        self._handle.close()

    def __enter__(self) -> "CnjCompilation":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    @property
    def asset_type_id(self) -> int:
        """The asset type identifier the compiled file declares."""
        return _support.out_u32("cna_cnb_cnj_result_get_asset_type_id", self._value)

    @property
    def asset_type_name(self) -> str:
        """The asset type's canonical name, as the compiler recorded it."""
        return _support.sized_text(
            "cna_cnb_cnj_result_get_asset_type_name_size",
            "cna_cnb_cnj_result_copy_asset_type_name",
            (self._value,), "compiled asset type name")

    @property
    def cnb_bytes(self) -> bytes:
        """The complete `.cnb` image, ready to write or to parse.

        This copies native memory each time it is read. Bind it once rather than
        reading it in a loop.
        """
        return _support.two_call_bytes("cna_cnb_cnj_result_copy_bytes", (self._value,))

    @property
    def absorbed_files(self) -> tuple[str, ...]:
        """The sidecar files whose contents went **into** the output, in order.

        A build system uses these as the compiled asset's input dependencies:
        change one and the `.cnb` is stale.
        """
        count = _support.out_u64(
            "cna_cnb_cnj_result_get_absorbed_file_count", self._value)
        return tuple(
            _support.sized_text(
                "cna_cnb_cnj_result_get_absorbed_file_size",
                "cna_cnb_cnj_result_copy_absorbed_file",
                (self._value, c.c_uint64(index)), "absorbed file")
            for index in range(count))

    @property
    def external_references(self) -> tuple[str, ...]:
        """The assets the output still refers to by **logical name**, in order.

        These are not paths on this machine: they are content names the loading
        side resolves. Order is the order the schema's own indices expect.
        """
        count = _support.out_u64(
            "cna_cnb_cnj_result_get_external_reference_count", self._value)
        return tuple(
            _support.sized_text(
                "cna_cnb_cnj_result_get_external_reference_size",
                "cna_cnb_cnj_result_copy_external_reference",
                (self._value, c.c_uint64(index)), "external reference")
            for index in range(count))

    def write_to(self, path: "str | os.PathLike[str]") -> int:
        """Writes the compiled image to ``path`` and returns the byte count."""
        data = self.cnb_bytes
        with open(os.fspath(path), "wb") as handle:
            handle.write(data)
        return len(data)

    def __repr__(self) -> str:
        if self.closed:
            return "<CnjCompilation closed>"
        return f"<CnjCompilation {self.asset_type_name}>"


def compile_cnj(cnj_path: "str | os.PathLike[str]", *,
                content_root: "str | os.PathLike[str] | None" = None,
                content_name: str = "") -> CnjCompilation:
    """Compiles one `.cnj` document and the binary sidecars it names.

    All eight compilable types are supported -- ``Curve``, ``AnimationClip``,
    ``Model``, ``Texture2D``, ``Texture3D``, ``TextureCube``, ``SpriteFont`` and
    ``SoundEffect``. Any other type is refused by name rather than silently
    producing an empty file.

    ``content_root`` is the **containment boundary**: a sidecar resolves relative
    to the document's own directory either way, and the resolved path must end up
    inside this root. ``None`` means the document's own parent directory, which
    is where every CNA content tool writes sidecars and which therefore refuses
    every ``..`` that leaves it. Passing a wider root is how a project whose
    documents and sources live in sibling directories opts into that layout,
    deliberately and once.

    ``content_name`` is the logical asset name recorded in the debug ``CMET``
    chunk, defaulting to the document's stem -- it is a *content* name, so
    passing an absolute machine path here would bake this machine's layout into a
    shipped file.
    """
    path_view, keep_path = _support.string_view(os.fspath(cnj_path), "cnj_path")
    root_view, keep_root = _support.string_view(
        "" if content_root is None else os.fspath(content_root), "content_root")
    name_view, keep_name = _support.string_view(content_name, "content_name")
    handle = _support.out_handle(
        "cna_cnb_compile_cnj", path_view, root_view, name_view)
    del keep_path, keep_root, keep_name
    return CnjCompilation(_support.NativeHandle(
        handle, "cna_cnb_cnj_result_destroy", "cnj compilation"))
