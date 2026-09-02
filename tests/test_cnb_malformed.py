"""Malformed and hostile `.cnb` bytes, including in a child process.

Parsing a `.cnb` is an untrusted-byte boundary: the file declares its own
offsets, sizes and counts, and every one of them is attacker-controlled. The
requirement is not that a corrupt file produces a particular message -- it is
that it produces an *exception* rather than a read out of range, and that the
process is still alive afterwards.

The mutation set is deterministic and bounded rather than a fuzz campaign: every
structural boundary of one tiny document is truncated, every field of its header
is perturbed, and each case is named. A campaign that finds a crash once and
never again is not a regression test.

The child-process cases exist because an in-process assertion cannot distinguish
"CNA refused" from "CNA corrupted something that happens not to matter yet".
Running the whole batch in a subprocess proves the interpreter survived every
one of them.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import subprocess
import sys
import textwrap
import unittest

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())
ROOT = Path(__file__).resolve().parents[1]

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb


def _fixture() -> bytes:
    """One small, entirely valid document with every container feature present."""
    with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
        writer.set_metadata("Microsoft.Xna.Framework.Curve", "levels/one")
        writer.add_external_reference("textures/atlas",
                                      expected_asset_type_id=int(cnb.AssetType.Texture2D))
        writer.add_chunk(cnb.chunk_id("mych"), b"payload!",
                         flags=cnb.ChunkFlags.Mandatory, alignment=4)
        return writer.build()


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class MalformedDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = _fixture()

    def _refuses(self, data: bytes, why: str) -> None:
        with self.assertRaises(cnb.CnbError, msg=why):
            cnb.CnbDocument.parse(data, origin="hostile.cnb").close()

    def test_the_fixture_itself_parses(self) -> None:
        # Without this the whole module could pass by refusing everything.
        with cnb.CnbDocument.parse(self.image) as document:
            self.assertEqual(document.chunk_count, 3)

    def test_empty_and_short_inputs_are_refused(self) -> None:
        for length in (0, 1, 3, 4, 8, 32, 63):
            self._refuses(self.image[:length], f"a {length}-byte file")

    def test_truncating_at_every_structural_boundary_is_refused(self) -> None:
        # Every boundary the format defines, plus one byte either side of each,
        # so an off-by-one in a bounds check has nowhere to hide.
        boundaries = {cnb.FORMAT_MAGIC_SIZE, cnb.FORMAT_HEADER_SIZE,
                      cnb.FORMAT_HEADER_SIZE + cnb.FORMAT_TOC_ENTRY_SIZE,
                      len(self.image) - 1}
        for boundary in sorted(boundaries):
            for offset in (-1, 0, 1):
                length = boundary + offset
                if 0 <= length < len(self.image):
                    self._refuses(self.image[:length], f"truncated at {length}")

    def test_a_flipped_magic_byte_is_refused(self) -> None:
        for index in range(cnb.FORMAT_MAGIC_SIZE):
            broken = bytearray(self.image)
            broken[index] ^= 0xFF
            self._refuses(bytes(broken), f"magic byte {index} flipped")

    def test_an_unsupported_container_version_is_refused(self) -> None:
        for offset, label in ((4, "major"), (6, "minor")):
            broken = bytearray(self.image)
            struct.pack_into("<H", broken, offset, 0x7FFF)
            self._refuses(bytes(broken), f"{label} version 0x7fff")

    def test_a_perturbed_header_field_is_caught_by_the_header_checksum(self) -> None:
        # Every byte the header checksum covers, one at a time. A parser that
        # trusted any of them would be trusting an attacker-supplied number.
        for index in range(cnb.FORMAT_MAGIC_SIZE, cnb.FORMAT_HEADER_CHECKSUM_COVERAGE):
            broken = bytearray(self.image)
            broken[index] ^= 0x01
            self._refuses(bytes(broken), f"header byte {index} perturbed")

    def test_a_perturbed_chunk_byte_is_caught_by_its_checksum(self) -> None:
        with cnb.CnbDocument.parse(self.image) as document:
            chunk = document.chunk(document.require_single(cnb.chunk_id("mych")))
        for index in range(chunk.offset, chunk.offset + chunk.stored_size):
            broken = bytearray(self.image)
            broken[index] ^= 0xFF
            self._refuses(bytes(broken), f"payload byte {index} perturbed")

    def test_a_reserved_field_that_is_not_zero_is_refused(self) -> None:
        # The reserved bytes are the format's own extension room; a file that
        # uses them is a file this build cannot claim to understand.
        first = cnb.FORMAT_HEADER_SIZE - cnb.FORMAT_HEADER_RESERVED_SIZE
        for index in range(first, cnb.FORMAT_HEADER_SIZE):
            broken = bytearray(self.image)
            broken[index] = 0xAA
            self._refuses(bytes(broken), f"reserved byte {index} non-zero")

    def test_every_single_byte_of_the_whole_file_is_either_ignored_or_refused(self) -> None:
        # The strongest structural statement available without a second parser:
        # flipping any byte anywhere either leaves a still-valid document or is
        # refused. What must never happen is a crash, a hang, or a document that
        # parses and then hands out bytes from outside itself.
        for index in range(len(self.image)):
            broken = bytearray(self.image)
            broken[index] ^= 0xFF
            try:
                document = cnb.CnbDocument.parse(bytes(broken), origin="flipped.cnb")
            except cnb.CnbError:
                continue
            with document:
                for chunk_index in range(document.chunk_count):
                    data = document.chunk_data(chunk_index)
                    entry = document.chunk(chunk_index)
                    self.assertEqual(len(data), entry.uncompressed_size, index)
                    self.assertLessEqual(entry.offset + entry.stored_size,
                                         len(broken), index)

    def test_an_impossible_chunk_count_is_refused_before_allocation(self) -> None:
        # The count sits in the header, so the header checksum has to be repaired
        # for the refusal to be about the count rather than about the checksum.
        for count in (0xFFFFFFFF, 0x7FFFFFFF, 1 << 20):
            broken = bytearray(self.image)
            struct.pack_into("<I", broken, 24, count)
            struct.pack_into(
                "<I", broken, cnb.FORMAT_HEADER_CHECKSUM_OFFSET,
                cnb.crc32c(bytes(broken[: cnb.FORMAT_HEADER_CHECKSUM_COVERAGE])))
            self._refuses(bytes(broken), f"chunk count {count}")

    def test_a_document_of_a_different_asset_type_is_refused_by_a_decoder(self) -> None:
        with cnb.CnbDocument.parse(self.image) as document:
            with self.assertRaises(cnb.CnbFormatError):
                cnb.decode_texture2d(document)
            with self.assertRaises(cnb.CnbFormatError):
                cnb.decode_model(document)
            with self.assertRaises(cnb.CnbFormatError):
                cnb.decode_sound_effect(document)

    def test_a_duplicate_singleton_container_chunk_is_refused(self) -> None:
        # The writer refuses to produce one, which is the first line of defence.
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            with self.assertRaises(cnb.CnbFormatError):
                writer.add_chunk(int(cnb.ContainerChunk.ExternalReferences), b"x")

    def test_a_truncated_compressed_payload_is_refused(self) -> None:
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        raw = b"compress me " * 200
        stored = cnb.compress(raw, cnb.Compression.Zstd)
        for length in (0, 1, len(stored) // 2, len(stored) - 1):
            with self.assertRaises(cnb.CnbError, msg=f"truncated to {length}"):
                cnb.decompress(stored[:length], cnb.Compression.Zstd, len(raw))

    def test_the_codec_alone_does_not_detect_every_corruption(self) -> None:
        """The measured limit of the codec, and why the container has a checksum.

        A flipped byte in a Zstandard frame is often refused, but not always: a
        frame can still decode to exactly the declared length with different
        contents. The exact-size rule is a bound on *allocation*, not an
        integrity check, and treating it as one would be the mistake this test
        exists to prevent. What actually catches content corruption is the
        chunk's own CRC-32C, which the next test proves.
        """
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        raw = b"compress me " * 200
        stored = cnb.compress(raw, cnb.Compression.Zstd)
        refused = wrong_contents = 0
        for index in range(len(stored)):
            broken = bytearray(stored)
            broken[index] ^= 0xFF
            try:
                decoded = cnb.decompress(bytes(broken), cnb.Compression.Zstd, len(raw))
            except cnb.CnbError:
                refused += 1
                continue
            self.assertEqual(len(decoded), len(raw), "the size rule must still hold")
            if decoded != raw:
                wrong_contents += 1
        self.assertGreater(refused, 0, "no corruption at all was detected")
        self.assertGreater(wrong_contents, 0,
                           "if the codec caught everything, this note is stale")

    def test_a_corrupted_compressed_chunk_is_caught_by_the_container(self) -> None:
        # Every byte of the stored payload, so the claim is about all of them
        # rather than about a lucky one.
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        payload = b"compress me " * 500
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_compression(cnb.Compression.Zstd)
            writer.add_chunk(cnb.chunk_id("aaaa"), payload)
            image = writer.build()
        with cnb.CnbDocument.parse(image) as document:
            chunk = document.chunk(document.require_single(cnb.chunk_id("aaaa")))
            self.assertEqual(chunk.compression, cnb.Compression.Zstd)
        for index in range(chunk.offset, chunk.offset + chunk.stored_size):
            broken = bytearray(image)
            broken[index] ^= 0xFF
            self._refuses(bytes(broken), f"compressed payload byte {index}")


_CHILD = textwrap.dedent(
    """
    import struct, sys
    from cna.extensions import content as cnb

    with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
        writer.set_metadata("Microsoft.Xna.Framework.Curve", "levels/one")
        writer.add_external_reference("textures/atlas")
        writer.add_chunk(cnb.chunk_id("mych"), b"payload!",
                         flags=cnb.ChunkFlags.Mandatory, alignment=4)
        image = writer.build()

    survived = 0
    for index in range(len(image)):
        for mask in (0x01, 0x80, 0xFF):
            broken = bytearray(image)
            broken[index] ^= mask
            try:
                document = cnb.CnbDocument.parse(bytes(broken), origin="fuzz.cnb")
            except cnb.CnbError:
                survived += 1
                continue
            with document:
                for chunk in range(document.chunk_count):
                    document.chunk_data(chunk)
                    document.chunk(chunk)
                document.metadata
                document.external_references
            survived += 1

    # Truncation at every length, which exercises a different set of bounds
    # checks from a byte flip: the reader runs out of input rather than reading
    # a wrong value.
    for length in range(len(image)):
        try:
            cnb.CnbDocument.parse(image[:length], origin="short.cnb").close()
        except cnb.CnbError:
            pass
        survived += 1

    print("SURVIVED", survived)
    """
)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ChildProcessSafetyTests(unittest.TestCase):
    def test_the_whole_mutation_batch_leaves_the_process_alive(self) -> None:
        """Every mutation, in a child, so a native abort is visible as one.

        An in-process test cannot tell a clean refusal from memory quietly
        scribbled on; a child that exits 0 having run the whole batch can.
        """
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src"), environment.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        completed = subprocess.run(
            [sys.executable, "-c", _CHILD], cwd=str(ROOT), env=environment,
            capture_output=True, text=True, timeout=600)
        self.assertEqual(completed.returncode, 0,
                         f"the child did not survive: {completed.stderr[-2000:]}")
        self.assertIn("SURVIVED", completed.stdout)
        survived = int(completed.stdout.split("SURVIVED")[1].split()[0])
        self.assertGreater(survived, 900, "the batch did not actually run")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
