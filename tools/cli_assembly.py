#!/usr/bin/env python3
"""Reads a managed assembly's identity, and what it was built against.

Enough of the PE and CLI metadata formats to answer one question: *which
platform is this assembly for?* The answer is in two places and this reads both
-- the assembly's own name and version, and the version of ``mscorlib`` it
references, which is what separates a desktop .NET assembly (4.0.0.0) from a
Compact Framework or Silverlight one (2.0.5.0).

Written here rather than reached for because it runs where the rest of this
repository runs, and because a file-name search that cannot identify what it
found is a search that misleads.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

#: The metadata tables this reader needs, by their table number.
_MODULE, _TYPE_REF, _TYPE_DEF = 0x00, 0x01, 0x02
_ASSEMBLY, _ASSEMBLY_REF = 0x20, 0x23


@dataclass(frozen=True)
class AssemblyIdentity:
    """One assembly's name and version."""

    name: str
    version: tuple[int, int, int, int]

    def __str__(self) -> str:
        return f"{self.name}, Version={'.'.join(str(v) for v in self.version)}"


@dataclass
class Assembly:
    """What this reader can say about a managed assembly."""

    identity: AssemblyIdentity | None
    references: list[AssemblyIdentity] = field(default_factory=list)

    def core_reference(self) -> AssemblyIdentity | None:
        """The ``mscorlib`` this assembly was compiled against, if it names one."""
        for reference in self.references:
            if reference.name == "mscorlib":
                return reference
        return None


class NotManaged(ValueError):
    """The file is not a managed assembly this reader can read."""


def read(path: Path) -> Assembly:
    data = path.read_bytes()
    metadata, sections = _metadata_root(data)
    streams = _streams(data, metadata)
    tables = streams.get("#~") or streams.get("#-")
    if tables is None:
        raise NotManaged(f"{path} has no metadata table stream")
    strings = streams.get("#Strings")
    if strings is None:
        raise NotManaged(f"{path} has no string heap")
    return _tables(data, tables, strings)


# -- PE and CLI headers ------------------------------------------------------


def _metadata_root(data: bytes) -> tuple[int, list[tuple[int, int, int]]]:
    if data[:2] != b"MZ":
        raise NotManaged("not a PE file")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise NotManaged("not a PE file")
    sections_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    # The CLI header is data directory 14; where the directories start depends
    # on whether the optional header is PE32 or PE32+.
    directories = optional + (96 if magic == 0x10B else 112)
    cli_rva = struct.unpack_from("<I", data, directories + 14 * 8)[0]
    if not cli_rva:
        raise NotManaged("no CLI header: this is a native binary")
    table = []
    for index in range(sections_count):
        entry = optional + optional_size + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, entry + 8)
        table.append((virtual_address, virtual_size or raw_size, raw_pointer))
    cli = _offset(cli_rva, table)
    metadata_rva = struct.unpack_from("<I", data, cli + 8)[0]
    return _offset(metadata_rva, table), table


def _offset(rva: int, sections: list[tuple[int, int, int]]) -> int:
    for virtual_address, size, raw in sections:
        if virtual_address <= rva < virtual_address + size:
            return raw + (rva - virtual_address)
    raise NotManaged(f"RVA {rva:#x} is outside every section")


def _streams(data: bytes, root: int) -> dict[str, tuple[int, int]]:
    if data[root:root + 4] != b"BSJB":
        raise NotManaged("metadata root signature is not BSJB")
    version_length = struct.unpack_from("<I", data, root + 12)[0]
    position = root + 16 + version_length
    position += 2  # flags
    count = struct.unpack_from("<H", data, position)[0]
    position += 2
    result: dict[str, tuple[int, int]] = {}
    for _ in range(count):
        offset, size = struct.unpack_from("<II", data, position)
        position += 8
        end = data.index(b"\0", position)
        name = data[position:end].decode("ascii")
        position = end + 1
        position += (-(position - root)) % 4
        result[name] = (root + offset, size)
    return result


# -- the two tables this reader needs ----------------------------------------


def _tables(data: bytes, stream: tuple[int, int],
            strings: tuple[int, int]) -> Assembly:
    base, _size = stream
    heap_sizes = data[base + 6]
    valid = struct.unpack_from("<Q", data, base + 8)[0]
    sorted_mask = struct.unpack_from("<Q", data, base + 16)[0]  # noqa: F841
    position = base + 24
    rows: dict[int, int] = {}
    for table in range(64):
        if valid >> table & 1:
            rows[table] = struct.unpack_from("<I", data, position)[0]
            position += 4

    string_width = 4 if heap_sizes & 0x01 else 2
    guid_width = 4 if heap_sizes & 0x02 else 2
    blob_width = 4 if heap_sizes & 0x04 else 2

    def read_string(offset: int) -> str:
        start = strings[0] + offset
        end = data.index(b"\0", start)
        return data[start:end].decode("utf-8")

    #: Row widths for every table that can appear before the two this reads.
    widths = _row_widths(rows, string_width, guid_width, blob_width)
    identity: AssemblyIdentity | None = None
    references: list[AssemblyIdentity] = []
    for table in range(64):
        count = rows.get(table, 0)
        if not count:
            continue
        width = widths.get(table)
        if width is None:
            raise NotManaged(
                f"metadata table {table:#x} has no width in this reader")
        if table == _ASSEMBLY:
            major, minor, build, revision = struct.unpack_from(
                "<HHHH", data, position + 4)
            name_offset = _heap(data, position + 4 + 8 + 4 + blob_width,
                                string_width)
            identity = AssemblyIdentity(read_string(name_offset),
                                        (major, minor, build, revision))
        elif table == _ASSEMBLY_REF:
            for index in range(count):
                row = position + index * width
                major, minor, build, revision = struct.unpack_from("<HHHH", data, row)
                name_offset = _heap(data, row + 8 + 4 + blob_width, string_width)
                references.append(AssemblyIdentity(
                    read_string(name_offset), (major, minor, build, revision)))
        position += width * count
    return Assembly(identity, references)


def _heap(data: bytes, offset: int, width: int) -> int:
    return struct.unpack_from("<I" if width == 4 else "<H", data, offset)[0]


def _row_widths(rows: dict[int, int], string: int, guid: int,
                blob: int) -> dict[int, int]:
    """How wide one row of each table is, given this file's heap and index sizes.

    Only the tables that can precede ``Assembly`` and ``AssemblyRef`` need a
    width, because the reader walks the stream in order; a table it does not
    know makes it stop rather than guess, which is what keeps it from reading
    nonsense out of a file it does not understand.
    """
    def index(*tables: int) -> int:
        """A coded index is four bytes once any of its targets exceeds its tag."""
        bits = max(1, (len(tables) - 1).bit_length())
        return 4 if any(rows.get(table, 0) >= (1 << (16 - bits))
                        for table in tables) else 2

    def simple(table: int) -> int:
        return 4 if rows.get(table, 0) >= (1 << 16) else 2

    type_def_or_ref = index(_TYPE_DEF, _TYPE_REF, 0x1B)
    resolution_scope = index(_MODULE, 0x1A, 0x23, _TYPE_REF)
    has_constant = index(0x04, 0x08, 0x17)
    has_custom_attribute = index(
        0x06, 0x04, 0x01, 0x02, 0x08, 0x09, 0x0A, 0x00, 0x0E, 0x17, 0x14,
        0x11, 0x1A, 0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x2A, 0x2C)
    has_field_marshal = index(0x04, 0x08)
    has_decl_security = index(0x02, 0x06, 0x20)
    member_ref_parent = index(_TYPE_DEF, _TYPE_REF, 0x1A, 0x06, 0x1B)
    has_semantics = index(0x14, 0x17)
    method_def_or_ref = index(0x06, 0x0A)
    member_forwarded = index(0x04, 0x06)
    implementation = index(0x26, 0x23, 0x27)
    custom_attribute_type = index(0x06, 0x0A, 0, 0, 0)
    type_or_method_def = index(_TYPE_DEF, 0x06)

    return {
        0x00: 2 + string + guid * 3,                       # Module
        0x01: resolution_scope + string * 2,               # TypeRef
        0x02: 4 + string * 2 + type_def_or_ref + simple(0x04) + simple(0x06),
        0x04: 2 + string + blob,                           # Field
        0x06: 4 + 2 + 2 + string + blob + simple(0x08),    # MethodDef
        0x08: 2 + string + blob,                           # Param
        0x09: simple(_TYPE_DEF) + type_def_or_ref,         # InterfaceImpl
        0x0A: member_ref_parent + string + blob,           # MemberRef
        0x0B: 1 + 1 + has_constant + blob,                 # Constant
        0x0C: has_custom_attribute + custom_attribute_type + blob,
        0x0D: has_field_marshal + blob,                    # FieldMarshal
        0x0E: 2 + has_decl_security + blob,                # DeclSecurity
        0x0F: 2 + 4 + simple(_TYPE_DEF),                   # ClassLayout
        0x10: 4 + simple(0x04),                            # FieldLayout
        0x11: blob,                                        # StandAloneSig
        0x12: simple(_TYPE_DEF) + simple(0x14),            # EventMap
        0x14: 2 + string + type_def_or_ref,                # Event
        0x15: simple(_TYPE_DEF) + simple(0x17),            # PropertyMap
        0x17: 2 + string + blob,                           # Property
        0x18: 2 + simple(0x06) + has_semantics,            # MethodSemantics
        0x19: simple(_TYPE_DEF) + method_def_or_ref * 2,   # MethodImpl
        0x1A: string,                                      # ModuleRef
        0x1B: blob,                                        # TypeSpec
        0x1C: 2 + member_forwarded + string + simple(0x1A),  # ImplMap
        0x1D: 4 + simple(0x04),                            # FieldRVA
        0x20: 4 + 8 + 4 + blob + string * 2,               # Assembly
        0x21: 4 + blob,                                    # AssemblyProcessor
        0x22: 4 + 4 + 4 + blob,                            # AssemblyOS
        0x23: 8 + 4 + blob + string * 2 + blob,            # AssemblyRef
        0x24: 4,                                           # AssemblyRefProcessor
        0x25: 4 + 4 + 4 + simple(0x23),                    # AssemblyRefOS
        0x26: 4 + string + implementation,                 # File
        0x27: 4 + 4 + string * 2 + implementation,         # ExportedType
        0x28: 4 + 4 + string + implementation,             # ManifestResource
        0x29: simple(_TYPE_DEF) * 2,                       # NestedClass
        0x2A: 2 + 2 + type_or_method_def + string,         # GenericParam
        0x2B: method_def_or_ref + blob,                    # MethodSpec
        0x2C: simple(0x2A) + type_def_or_ref,              # GenericParamConstraint
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    arguments = parser.parse_args()
    for value in arguments.paths:
        path = Path(value)
        try:
            assembly = read(path)
        except (NotManaged, ValueError, struct.error, IndexError) as error:
            print(f"{path}: not readable as a managed assembly ({error})")
            continue
        core = assembly.core_reference()
        print(f"{path}")
        print(f"  identity  {assembly.identity}")
        print(f"  mscorlib  {core if core else '(none referenced)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
