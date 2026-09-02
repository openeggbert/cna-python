"""The `.cnb` container: identities, limits, checksums, codecs, documents, cursors.

Every assertion here states an exact expected value rather than "it worked".
Where a round trip is the obvious check it is not the only one: the CRC has a
published check value, the container header has a fixed layout that can be read
by hand, and a chunk's stored checksum is recomputed independently from its
bytes. A mirrored bug passes an encoder/decoder pair; it does not pass those.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import tempfile
import unittest

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ContainerIdentityTests(unittest.TestCase):
    def test_the_magic_is_the_four_bytes_the_format_defines(self) -> None:
        # Read from CNA, then checked against the value the format document
        # states, so a change on either side is visible rather than absorbed.
        self.assertEqual(cnb.format_magic(), b"CNB\x1a")
        self.assertEqual(len(cnb.format_magic()), cnb.FORMAT_MAGIC_SIZE)

    def test_has_magic_answers_only_about_the_first_four_bytes(self) -> None:
        self.assertTrue(cnb.has_magic(b"CNB\x1a followed by rubbish"))
        self.assertFalse(cnb.has_magic(b"CNB"))
        self.assertFalse(cnb.has_magic(b""))
        self.assertFalse(cnb.has_magic(b"XNB\x1a"))

    def test_a_chunk_identifier_packs_little_endian_and_renders_back(self) -> None:
        # The identifier is packed so its bytes read left-to-right in a hex dump,
        # which is what makes 'TEXH' 0x48584554 rather than 0x54455848.
        self.assertEqual(cnb.chunk_id("TEXH"), 0x48584554)
        self.assertEqual(cnb.chunk_id_text(0x48584554), "TEXH")
        self.assertTrue(cnb.is_well_formed_chunk_id(cnb.chunk_id("TEXH")))

    def test_a_corrupt_identifier_renders_without_control_characters(self) -> None:
        rendered = cnb.chunk_id_text(0x00010203)
        self.assertEqual(rendered, "????")
        self.assertFalse(cnb.is_well_formed_chunk_id(0x00010203))

    def test_a_chunk_identifier_must_be_four_ascii_characters(self) -> None:
        for bad in ("TEX", "TEXHX", "TEéH"):
            with self.assertRaises(ValueError):
                cnb.chunk_id(bad)

    def test_a_built_in_asset_type_names_itself_and_a_custom_one_hashes(self) -> None:
        self.assertEqual(cnb.asset_type_name(cnb.AssetType.Curve), "Curve")
        self.assertFalse(cnb.is_custom_asset_type_id(cnb.AssetType.Curve))
        minted = cnb.asset_type_id_from_name("MyGame.Level")
        self.assertTrue(cnb.is_custom_asset_type_id(minted))
        # The identifier is FNV-1a-32 of the name with the custom bit set; the
        # hash is computed here independently rather than compared to itself.
        expected = 0x811C9DC5
        for byte in b"MyGame.Level":
            expected = ((expected ^ byte) * 0x01000193) & 0xFFFFFFFF
        self.assertEqual(minted, expected | 0x80000000)

    def test_minting_from_an_empty_name_is_refused(self) -> None:
        with self.assertRaises(cnb.CnbFormatError):
            cnb.asset_type_id_from_name("")


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class LogicalNameTests(unittest.TestCase):
    def test_an_acceptable_name_has_no_problem(self) -> None:
        self.assertIsNone(cnb.logical_name_problem("textures/atlas"))

    def test_every_rule_the_format_states_is_reported_by_name(self) -> None:
        for name, expected in (
            ("", "is empty"),
            ("../escape", "contains a '..' segment"),
            ("a/../b", "contains a '..' segment"),
            ("/absolute", "is an absolute path"),
            ("C:/drive", "is a drive-qualified absolute path"),
            ("back\\slash", "contains a backslash; .cnb logical names use '/' only"),
        ):
            self.assertEqual(cnb.logical_name_problem(name), expected, name)

    def test_malformed_utf8_is_a_verdict_rather_than_a_refusal(self) -> None:
        # This route deliberately does not validate its input as UTF-8, because
        # malformed UTF-8 is one of the answers it exists to give.
        problem = cnb.logical_name_problem(b"bad\xff\xfename")
        self.assertIsNotNone(problem)
        self.assertIn("UTF-8", problem)

    def test_utf8_validation_agrees_with_python(self) -> None:
        for raw in (b"", b"plain", "café".encode("utf-8"), b"\xf0\x9f\x8e\x89"):
            self.assertTrue(cnb.is_well_formed_utf8(raw), raw)
        for raw in (b"\xff", b"\xc3", b"\xed\xa0\x80"):
            self.assertFalse(cnb.is_well_formed_utf8(raw), raw)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ChecksumTests(unittest.TestCase):
    #: The published CRC-32C check value for the ASCII string "123456789". An
    #: independent oracle: it comes from the algorithm's own specification, not
    #: from CNA and not from this binding.
    CHECK_VALUE = 0xE3069283

    def test_the_published_check_value_is_reproduced(self) -> None:
        self.assertEqual(cnb.crc32c(b"123456789"), self.CHECK_VALUE)

    def test_the_portable_path_agrees_with_whatever_path_is_in_use(self) -> None:
        # If the build folded with SSE4.2 and the two disagreed, a stored
        # checksum would depend on the machine that wrote it.
        for data in (b"", b"a", b"123456789", bytes(range(256)) * 4):
            self.assertEqual(cnb.crc32c(data), cnb.crc32c(data, portable=True), data[:8])

    def test_a_running_checksum_over_two_buffers_equals_one_over_the_join(self) -> None:
        left, right = b"the quick brown ", b"fox jumps over it"
        running = cnb.crc32c(left, previous=cnb.CRC32C_SEED)
        running = cnb.crc32c(right, previous=running)
        self.assertEqual(running, cnb.crc32c(left + right))

    def test_hardware_acceleration_is_reported_as_a_fact_not_a_promise(self) -> None:
        self.assertIsInstance(cnb.uses_hardware_crc32c(), bool)

    def test_the_portable_path_has_no_continuation_and_says_so(self) -> None:
        with self.assertRaises(ValueError):
            cnb.crc32c(b"x", previous=0, portable=True)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class CompressionTests(unittest.TestCase):
    def test_storing_uncompressed_is_always_available_and_is_a_copy(self) -> None:
        self.assertTrue(cnb.is_compression_supported(cnb.Compression.NoCompression))
        payload = bytes(range(64))
        self.assertEqual(cnb.compress(payload, cnb.Compression.NoCompression), payload)
        self.assertEqual(
            cnb.compressed_size(payload, cnb.Compression.NoCompression), len(payload))

    def test_a_codec_identity_renders_even_when_unimplemented(self) -> None:
        self.assertEqual(cnb.compression_name(cnb.Compression.NoCompression), "none")
        self.assertEqual(cnb.compression_name(cnb.Compression.Zstd), "Zstandard")
        self.assertIn("unknown", cnb.compression_name(99))

    def test_an_unimplemented_codec_refuses_rather_than_storing_plainly(self) -> None:
        # Lz4 has a frozen wire identity and no implementation in this build; a
        # silent fallback to stored bytes would produce a file claiming Lz4.
        self.assertFalse(cnb.is_compression_supported(cnb.Compression.Lz4))
        with self.assertRaises(cnb.CnbUnsupportedError):
            cnb.compress(b"payload", cnb.Compression.Lz4)

    @unittest.skipUnless(HAS_NATIVE, "native")
    def test_a_zstd_round_trip_reproduces_the_exact_bytes(self) -> None:
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        payload = (b"repeat me " * 200) + bytes(range(256))
        stored = cnb.compress(payload, cnb.Compression.Zstd, level=3)
        self.assertLess(len(stored), len(payload))
        self.assertEqual(len(stored), cnb.compressed_size(payload, cnb.Compression.Zstd))
        self.assertEqual(
            cnb.decompress(stored, cnb.Compression.Zstd, len(payload)), payload)

    def test_decompressing_to_a_different_size_is_a_corrupt_file(self) -> None:
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        payload = b"exactly this" * 40
        stored = cnb.compress(payload, cnb.Compression.Zstd)
        with self.assertRaises(cnb.CnbFormatError):
            cnb.decompress(stored, cnb.Compression.Zstd, len(payload) + 1)

    def test_an_oversized_expansion_is_refused_before_anything_is_allocated(self) -> None:
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        stored = cnb.compress(b"small", cnb.Compression.Zstd)
        with self.assertRaises(cnb.CnbFormatError):
            cnb.decompress(stored, cnb.Compression.Zstd, 1 << 40, max_uncompressed_size=1024)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ReadLimitsTests(unittest.TestCase):
    def test_the_defaults_come_from_cna_and_are_internally_consistent(self) -> None:
        limits = cnb.CnbReadLimits.defaults()
        self.assertGreater(limits.max_file_size, 0)
        # The aggregate expansion budget is deliberately larger than one file, so
        # compression can genuinely expand rather than being cancelled out.
        self.assertGreater(limits.max_total_uncompressed_size, limits.max_file_size)
        self.assertGreater(limits.max_chunk_count, 0)

    def test_narrowing_a_limit_keeps_every_other_one(self) -> None:
        limits = cnb.CnbReadLimits.defaults()
        tightened = limits.replace(max_chunk_count=4)
        self.assertEqual(tightened.max_chunk_count, 4)
        self.assertEqual(tightened.max_file_size, limits.max_file_size)

    def test_a_limit_that_cannot_fit_its_native_width_is_refused(self) -> None:
        limits = cnb.CnbReadLimits.defaults().replace(max_chunk_count=1 << 40)
        with self.assertRaises(ValueError):
            cnb.CnbDocument.parse(b"", limits=limits)


def _document(*, asset_type=None, chunks=(), metadata=("Test.Asset", "test/one"),
              references=(), schema_version=1, compression=None) -> bytes:
    """Builds one `.cnb` image from an explicit description of what it should hold."""
    asset_type = cnb.AssetType.Curve if asset_type is None else asset_type
    with cnb.CnbWriter(int(asset_type), schema_version) as writer:
        if metadata is not None:
            writer.set_metadata(*metadata)
        for name, expected in references:
            writer.add_external_reference(name, expected_asset_type_id=int(expected))
        if compression is not None:
            writer.set_compression(compression)
        for identifier, payload, flags, alignment in chunks:
            writer.add_chunk(cnb.chunk_id(identifier), payload,
                             flags=flags, alignment=alignment)
        return writer.build()


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class WriterTests(unittest.TestCase):
    def test_a_built_image_has_the_header_the_format_specifies(self) -> None:
        image = _document(chunks=[("mych", b"payload!", cnb.ChunkFlags.NoFlags, 1)])
        # Read by hand from the format's own constants rather than through the
        # parser, so the parser is not proving its own input well-formed.
        self.assertEqual(image[:4], cnb.format_magic())
        major, minor = struct.unpack_from("<HH", image, 4)
        self.assertEqual((major, minor), (cnb.CONTAINER_MAJOR, cnb.CONTAINER_MINOR))
        self.assertGreaterEqual(len(image), cnb.FORMAT_HEADER_SIZE)

    def test_building_twice_gives_byte_identical_output(self) -> None:
        # Determinism is what makes a compiled asset cacheable and diffable: no
        # clock, no random source, no pointer value reaches the file.
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_metadata("Test.Asset", "test/one")
            writer.add_chunk(cnb.chunk_id("mych"), b"payload!")
            self.assertEqual(writer.build(), writer.build())

    def test_the_container_chunks_are_emitted_before_the_schema_chunks(self) -> None:
        image = _document(
            chunks=[("aaaa", b"1", cnb.ChunkFlags.NoFlags, 1)],
            references=[("tex/one", cnb.AssetType.Texture2D)])
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual([chunk.type_text for chunk in document.chunks],
                             ["CMET", "XREF", "aaaa"])

    def test_a_container_chunk_identifier_is_refused_as_a_schema_chunk(self) -> None:
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            with self.assertRaises(cnb.CnbFormatError):
                writer.add_chunk(int(cnb.ContainerChunk.Metadata), b"x")

    def test_an_illegal_external_reference_name_is_refused_when_the_file_is_built(self) -> None:
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.add_external_reference("../escape")
            with self.assertRaises(cnb.CnbFormatError):
                writer.build()

    def test_clearing_the_reference_table_empties_it(self) -> None:
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.add_external_reference("tex/one")
            writer.clear_external_references()
            writer.add_external_reference("tex/two")
            image = writer.build()
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual([r.name for r in document.external_references], ["tex/two"])

    def test_the_schema_chunk_count_excludes_the_container_chunks(self) -> None:
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_metadata("Test.Asset", "")
            writer.add_external_reference("tex/one")
            self.assertEqual(writer.schema_chunk_count, 0)
            writer.add_chunk(cnb.chunk_id("aaaa"), b"1")
            writer.add_chunk(cnb.chunk_id("bbbb"), b"2")
            self.assertEqual(writer.schema_chunk_count, 2)

    def test_a_writer_bounded_by_limits_refuses_what_a_reader_would(self) -> None:
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_limits(cnb.CnbReadLimits.defaults().replace(max_chunk_size=4))
            self.assertEqual(writer.limits.max_chunk_size, 4)
            writer.add_chunk(cnb.chunk_id("aaaa"), b"far too long for four bytes")
            with self.assertRaises(cnb.CnbFormatError):
                writer.build()

    def test_an_invalid_asset_type_is_refused_at_construction(self) -> None:
        with self.assertRaises(cnb.CnbFormatError):
            cnb.CnbWriter(int(cnb.AssetType.Invalid), 1)

    def test_writing_to_a_file_produces_the_same_bytes_as_building(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.cnb"
            with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
                writer.set_metadata("Test.Asset", "")
                writer.add_chunk(cnb.chunk_id("aaaa"), b"payload")
                writer.write_to_file(path)
                self.assertEqual(path.read_bytes(), writer.build())


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class DocumentTests(unittest.TestCase):
    def test_a_valid_minimal_document_reports_exactly_what_it_holds(self) -> None:
        image = _document(
            asset_type=cnb.AssetType.Curve, schema_version=1,
            metadata=("Microsoft.Xna.Framework.Curve", "levels/one"),
            references=[("textures/atlas", cnb.AssetType.Texture2D),
                        ("audio/step", cnb.AssetType.SoundEffect)],
            chunks=[("mych", b"payload!", cnb.ChunkFlags.Mandatory, 4)])
        with cnb.CnbDocument.parse(image, origin="fixture.cnb") as document:
            self.assertEqual(document.origin, "fixture.cnb")
            self.assertEqual(document.container_version,
                             (cnb.CONTAINER_MAJOR, cnb.CONTAINER_MINOR))
            self.assertEqual(document.asset_type, cnb.AssetType.Curve)
            self.assertEqual(document.asset_type_id, int(cnb.AssetType.Curve))
            self.assertEqual(document.asset_schema_version, 1)
            self.assertEqual(document.chunk_count, 3)

            metadata = document.metadata
            self.assertTrue(metadata.present)
            self.assertEqual(metadata.asset_type_name, "Microsoft.Xna.Framework.Curve")
            self.assertEqual(metadata.content_name, "levels/one")

            self.assertEqual(document.external_reference_count, 2)
            first, second = document.external_references
            self.assertEqual((first.index, first.name, first.expected_asset_type_id),
                             (0, "textures/atlas", int(cnb.AssetType.Texture2D)))
            self.assertEqual((second.index, second.name, second.expected_asset_type_id),
                             (1, "audio/step", int(cnb.AssetType.SoundEffect)))

            index = document.require_single(cnb.chunk_id("mych"))
            chunk = document.chunk(index)
            self.assertEqual(chunk.type_text, "mych")
            self.assertEqual(chunk.uncompressed_size, 8)
            self.assertEqual(chunk.stored_size, 8)
            self.assertEqual(chunk.compression, cnb.Compression.NoCompression)
            self.assertEqual(chunk.alignment, 4)
            self.assertEqual(chunk.offset % 4, 0)
            self.assertTrue(chunk.is_mandatory)
            self.assertEqual(document.chunk_data(index), b"payload!")
            # The stored checksum, recomputed here from the bytes rather than
            # believed: a mirrored bug in reader and writer would still fail.
            self.assertEqual(chunk.checksum, cnb.crc32c(b"payload!"))

    def test_an_absent_optional_metadata_field_is_empty_not_missing(self) -> None:
        image = _document(metadata=("Test.Asset", ""))
        with cnb.CnbDocument.parse(image) as document:
            self.assertTrue(document.metadata.present)
            self.assertEqual(document.metadata.content_name, "")

    def test_a_document_with_no_metadata_chunk_reports_it_absent(self) -> None:
        image = _document(metadata=None)
        with cnb.CnbDocument.parse(image) as document:
            self.assertFalse(document.metadata.present)
            self.assertEqual(document.metadata.asset_type_name, "")

    def test_find_all_returns_every_match_in_file_order(self) -> None:
        image = _document(chunks=[
            ("same", b"one", cnb.ChunkFlags.NoFlags, 1),
            ("othr", b"x", cnb.ChunkFlags.NoFlags, 1),
            ("same", b"three", cnb.ChunkFlags.NoFlags, 1)])
        with cnb.CnbDocument.parse(image) as document:
            matches = document.find_all(cnb.chunk_id("same"))
            self.assertEqual(len(matches), 2)
            self.assertEqual([document.chunk_data(index) for index in matches],
                             [b"one", b"three"])

    def test_find_single_reports_absence_as_an_answer_and_duplication_as_an_error(self) -> None:
        image = _document(chunks=[("same", b"1", cnb.ChunkFlags.NoFlags, 1),
                                  ("same", b"2", cnb.ChunkFlags.NoFlags, 1)])
        with cnb.CnbDocument.parse(image) as document:
            self.assertIsNone(document.find_single(cnb.chunk_id("gone")))
            with self.assertRaises(cnb.CnbFormatError):
                document.find_single(cnb.chunk_id("same"))
            with self.assertRaises(cnb.CnbFormatError):
                document.require_single(cnb.chunk_id("gone"))

    def test_an_unknown_mandatory_chunk_costs_the_whole_file(self) -> None:
        image = _document(chunks=[("must", b"x", cnb.ChunkFlags.Mandatory, 1),
                                  ("opt ", b"y", cnb.ChunkFlags.NoFlags, 1)])
        with cnb.CnbDocument.parse(image) as document:
            # Knowing the mandatory chunk is enough; the optional one may stay
            # unknown, which is what lets a newer writer add data safely.
            document.require_mandatory_chunks_understood([cnb.chunk_id("must")])
            with self.assertRaises(cnb.CnbFormatError):
                document.require_mandatory_chunks_understood([cnb.chunk_id("opt ")])

    def test_require_asset_checks_both_the_type_and_the_schema_version(self) -> None:
        image = _document(asset_type=cnb.AssetType.Curve, schema_version=1)
        with cnb.CnbDocument.parse(image) as document:
            document.require_asset(int(cnb.AssetType.Curve), 1)
            with self.assertRaises(cnb.CnbFormatError):
                document.require_asset(int(cnb.AssetType.Model), 1)

    def test_a_schema_version_above_the_ceiling_is_refused(self) -> None:
        image = _document(asset_type=cnb.AssetType.Curve, schema_version=3)
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_schema_version, 3)
            with self.assertRaises(cnb.CnbFormatError):
                document.require_asset(int(cnb.AssetType.Curve), 2)

    def test_the_limits_a_document_was_parsed_with_are_reported_back(self) -> None:
        limits = cnb.CnbReadLimits.defaults().replace(max_string_bytes=4096)
        with cnb.CnbDocument.parse(_document(), limits=limits) as document:
            self.assertEqual(document.limits.max_string_bytes, 4096)

    def test_a_document_read_from_disk_matches_one_parsed_from_bytes(self) -> None:
        image = _document(chunks=[("aaaa", b"disk", cnb.ChunkFlags.NoFlags, 1)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.cnb"
            path.write_bytes(image)
            with cnb.CnbDocument.parse_file(path) as document:
                self.assertEqual(document.origin, str(path))
                index = document.require_single(cnb.chunk_id("aaaa"))
                self.assertEqual(document.chunk_data(index), b"disk")

    def test_a_missing_file_is_a_missing_reference_not_a_malformed_one(self) -> None:
        with self.assertRaises(cnb.CnbMissingReferenceError):
            cnb.CnbDocument.parse_file("/definitely/not/here.cnb")

    def test_a_file_above_the_size_limit_is_refused_before_it_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "big.cnb"
            path.write_bytes(_document(chunks=[("aaaa", bytes(4096),
                                                cnb.ChunkFlags.NoFlags, 1)]))
            limits = cnb.CnbReadLimits.defaults().replace(max_file_size=64)
            with self.assertRaises(cnb.CnbMissingReferenceError):
                cnb.CnbDocument.parse_file(path, limits=limits)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class DocumentLifetimeTests(unittest.TestCase):
    def test_a_document_refuses_to_close_while_a_reader_borrows_it(self) -> None:
        image = _document(chunks=[("aaaa", b"borrowed", cnb.ChunkFlags.NoFlags, 1)])
        document = cnb.CnbDocument.parse(image)
        reader = document.open_chunk(document.require_single(cnb.chunk_id("aaaa")))
        with self.assertRaises(ValueError):
            document.close()
        self.assertFalse(document.closed)
        reader.close()
        document.close()
        self.assertTrue(document.closed)

    def test_a_closed_document_refuses_further_use(self) -> None:
        document = cnb.CnbDocument.parse(_document())
        document.close()
        with self.assertRaises(ValueError):
            _ = document.chunk_count
        # Closing twice is a no-op rather than a double free.
        document.close()

    def test_a_reader_over_bytes_does_not_need_its_source_to_outlive_it(self) -> None:
        source = bytearray(b"\x01\x00\x00\x00")
        reader = cnb.CnbReader.over_bytes(source, context="detached")
        source.clear()
        try:
            self.assertEqual(reader.read_u32(), 1)
        finally:
            reader.close()


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class PrimitiveRoundTripTests(unittest.TestCase):
    def test_every_primitive_survives_the_writer_and_the_reader(self) -> None:
        with cnb.CnbByteWriter() as writer:
            writer.write_u8(0xFE)
            writer.write_u16(0xBEEF)
            writer.write_u32(0xDEADBEEF)
            writer.write_u64(0x0123456789ABCDEF)
            writer.write_i32(-2000000000)
            writer.write_f32(1.5)
            writer.write_f64(-2.25)
            writer.write_string("café \U0001F389")
            writer.write_bytes(b"\x01\x02\x03")
            writer.write_zeros(3)
            payload = writer.copy_bytes()

        with cnb.CnbReader.over_bytes(payload, context="primitives") as reader:
            self.assertEqual(reader.read_u8(), 0xFE)
            self.assertEqual(reader.read_u16(), 0xBEEF)
            self.assertEqual(reader.read_u32(), 0xDEADBEEF)
            self.assertEqual(reader.read_u64(), 0x0123456789ABCDEF)
            self.assertEqual(reader.read_i32(), -2000000000)
            self.assertEqual(reader.read_f32(), 1.5)
            self.assertEqual(reader.read_f64(), -2.25)
            self.assertEqual(reader.read_string(), "café \U0001F389")
            self.assertEqual(reader.read_bytes(3), b"\x01\x02\x03")
            reader.skip(3)
            reader.require_exhausted()

    def test_the_encoding_is_little_endian_regardless_of_the_host(self) -> None:
        # Checked against bytes written out here, not against the reader: a
        # matched pair of byte-order bugs would round-trip perfectly.
        with cnb.CnbByteWriter() as writer:
            writer.write_u32(0x01020304)
            writer.write_f32(1.0)
            self.assertEqual(writer.copy_bytes(),
                             b"\x04\x03\x02\x01" + struct.pack("<f", 1.0))

    def test_a_string_is_a_byte_length_followed_by_its_utf8(self) -> None:
        with cnb.CnbByteWriter() as writer:
            writer.write_string("hi")
            self.assertEqual(writer.copy_bytes(), struct.pack("<I", 2) + b"hi")

    def test_copy_leaves_the_writer_alone_and_take_empties_it(self) -> None:
        with cnb.CnbByteWriter() as writer:
            writer.write_u32(7)
            self.assertEqual(writer.size, 4)
            self.assertEqual(writer.copy_bytes(), struct.pack("<I", 7))
            self.assertEqual(writer.size, 4, "copy_bytes must not consume")
            self.assertEqual(writer.copy_bytes(), struct.pack("<I", 7))
            taken = writer.take_bytes()
            self.assertEqual(taken, struct.pack("<I", 7))
            self.assertEqual(writer.size, 0, "take_bytes must consume")
            self.assertEqual(writer.take_bytes(), b"", "a second take has nothing to take")

    def test_a_writer_can_continue_from_existing_bytes(self) -> None:
        with cnb.CnbByteWriter(b"\xaa\xbb") as writer:
            writer.write_u8(0xCC)
            self.assertEqual(writer.copy_bytes(), b"\xaa\xbb\xcc")

    def test_a_reader_reports_its_position_and_its_context(self) -> None:
        with cnb.CnbReader.over_bytes(b"\x01\x02\x03\x04\x05",
                                      context="'x.cnb' chunk AAAA") as reader:
            self.assertEqual((reader.size, reader.position, reader.remaining), (5, 0, 5))
            reader.read_u8()
            self.assertEqual((reader.position, reader.remaining), (1, 4))
            self.assertEqual(reader.context, "'x.cnb' chunk AAAA")

    def test_reading_past_the_end_refuses_and_names_the_region(self) -> None:
        with cnb.CnbReader.over_bytes(b"\x01", context="'x.cnb' chunk AAAA") as reader:
            with self.assertRaises(cnb.CnbFormatError) as caught:
                reader.read_u32()
            self.assertIn("x.cnb", str(caught.exception))

    def test_trailing_bytes_are_an_error_rather_than_something_ignored(self) -> None:
        with cnb.CnbReader.over_bytes(b"\x01\x02") as reader:
            reader.read_u8()
            with self.assertRaises(cnb.CnbFormatError):
                reader.require_exhausted()

    def test_a_schema_decoder_can_fail_the_way_the_cursor_does(self) -> None:
        with cnb.CnbReader.over_bytes(b"\x01\x02", context="'x.cnb' chunk AAAA") as reader:
            reader.read_u8()
            with self.assertRaises(cnb.CnbFormatError) as caught:
                reader.fail("the level index is out of range")
            message = str(caught.exception)
            self.assertIn("x.cnb", message)
            self.assertIn("the level index is out of range", message)

    def test_an_element_count_is_checked_against_what_could_fit(self) -> None:
        # A count of 1000 four-byte elements cannot fit in four remaining bytes,
        # and is refused before anything is reserved for it.
        with cnb.CnbReader.over_bytes(struct.pack("<I", 1000) + b"\x00" * 4) as reader:
            with self.assertRaises(cnb.CnbFormatError):
                reader.read_count(4, what="tracks")
        with cnb.CnbReader.over_bytes(struct.pack("<I", 2) + b"\x00" * 8) as reader:
            self.assertEqual(reader.read_count(4, what="tracks"), 2)

    def test_a_string_longer_than_the_limit_is_refused_before_allocation(self) -> None:
        payload = struct.pack("<I", 1 << 20) + b"x" * 8
        limits = cnb.CnbReadLimits.defaults().replace(max_string_bytes=16)
        with cnb.CnbReader.over_bytes(payload, limits=limits) as reader:
            with self.assertRaises(cnb.CnbFormatError):
                reader.read_string()

    def test_a_string_that_is_not_utf8_is_refused_by_the_reader(self) -> None:
        payload = struct.pack("<I", 2) + b"\xff\xfe"
        with cnb.CnbReader.over_bytes(payload) as reader:
            with self.assertRaises(cnb.CnbFormatError):
                reader.read_string()

    def test_writing_a_string_that_is_not_a_string_is_a_type_error(self) -> None:
        with cnb.CnbByteWriter() as writer:
            with self.assertRaises(TypeError):
                writer.write_string(b"bytes are not a string")

    def test_an_integer_too_wide_for_its_field_is_refused_not_truncated(self) -> None:
        with cnb.CnbByteWriter() as writer:
            for method, value in ((writer.write_u8, 256), (writer.write_u16, 65536),
                                  (writer.write_u32, 1 << 32), (writer.write_i32, 1 << 31),
                                  (writer.write_u8, -1)):
                with self.assertRaises(ValueError):
                    method(value)
            with self.assertRaises(TypeError):
                writer.write_u32("7")
            self.assertEqual(writer.size, 0, "a refused write must append nothing")

    def test_a_chunk_reader_reads_exactly_the_chunk_the_writer_wrote(self) -> None:
        with cnb.CnbByteWriter() as inner:
            inner.write_u32(0xC0FFEE)
            inner.write_string("nested")
            payload = inner.copy_bytes()
        image = _document(chunks=[("mych", payload, cnb.ChunkFlags.NoFlags, 1)])
        with cnb.CnbDocument.parse(image) as document:
            index = document.require_single(cnb.chunk_id("mych"))
            with document.open_chunk(index) as reader:
                self.assertEqual(reader.size, len(payload))
                self.assertEqual(reader.read_u32(), 0xC0FFEE)
                self.assertEqual(reader.read_string(), "nested")
                reader.require_exhausted()


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class CompressedDocumentTests(unittest.TestCase):
    def test_a_compressed_chunk_expands_to_the_bytes_that_went_in(self) -> None:
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        payload = b"compress me " * 500
        image = _document(chunks=[("aaaa", payload, cnb.ChunkFlags.NoFlags, 1)],
                          compression=cnb.Compression.Zstd)
        with cnb.CnbDocument.parse(image) as document:
            index = document.require_single(cnb.chunk_id("aaaa"))
            chunk = document.chunk(index)
            self.assertEqual(chunk.compression, cnb.Compression.Zstd)
            self.assertLess(chunk.stored_size, chunk.uncompressed_size)
            self.assertEqual(chunk.uncompressed_size, len(payload))
            self.assertEqual(document.chunk_data(index), payload)

    def test_a_chunk_compression_would_grow_is_stored_instead(self) -> None:
        if not cnb.is_compression_supported(cnb.Compression.Zstd):
            self.skipTest("this CNA build was compiled without libzstd")
        payload = bytes(range(16))  # too small and too random to compress
        image = _document(chunks=[("aaaa", payload, cnb.ChunkFlags.NoFlags, 1)],
                          compression=cnb.Compression.Zstd)
        with cnb.CnbDocument.parse(image) as document:
            chunk = document.chunk(document.require_single(cnb.chunk_id("aaaa")))
            self.assertEqual(chunk.compression, cnb.Compression.NoCompression)
            self.assertEqual(chunk.stored_size, chunk.uncompressed_size)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
