"""The typed asset codecs: textures, sound, fonts, media, curves, clips.

An encoder/decoder pair is not allowed to be its own oracle here. A mirrored bug
-- a face swap in both directions, a kerning field written and read in the same
wrong order -- round-trips perfectly. So every codec is checked three ways:

* against the **chunk structure** the format specifies, read out of the document
  rather than through the codec;
* against a **hand-computed expectation**, such as a block-compressed level's
  byte size or a texture level's exact payload;
* with **asymmetric fixtures**, so a swap is a different value rather than the
  same one twice.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import unittest

from Microsoft.Xna.Framework import (
    Curve, CurveContinuity, CurveKey, CurveLoopType, Rectangle, Vector3,
)
from Microsoft.Xna.Framework.Graphics import SurfaceFormat
from Microsoft.Xna.Framework.Media import VideoSoundtrackType

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class TextureFormatTests(unittest.TestCase):
    def test_a_known_format_is_known_and_a_stray_value_is_not(self) -> None:
        self.assertTrue(cnb.is_known_texture_format(int(cnb.TextureFormat.Rgba8)))
        self.assertFalse(cnb.is_known_texture_format(0))
        self.assertFalse(cnb.is_known_texture_format(9999))

    def test_a_format_renders_by_name_or_by_hexadecimal(self) -> None:
        self.assertEqual(cnb.texture_format_name(cnb.TextureFormat.Rgba8), "Rgba8")
        self.assertEqual(cnb.texture_format_name(9999),
                         "unknown texture format 0x0000270F")

    def test_unit_bytes_are_per_texel_or_per_block(self) -> None:
        self.assertEqual(cnb.texture_format_unit_bytes(cnb.TextureFormat.Rgba8), 4)
        self.assertEqual(cnb.texture_format_unit_bytes(cnb.TextureFormat.Bgr565), 2)
        self.assertEqual(cnb.texture_format_unit_bytes(cnb.TextureFormat.Bc1), 8)
        self.assertEqual(cnb.texture_format_unit_bytes(cnb.TextureFormat.Bc7), 16)
        self.assertEqual(cnb.texture_format_unit_bytes(9999), 0)

    def test_only_the_block_formats_are_block_compressed(self) -> None:
        for value in (cnb.TextureFormat.Bc1, cnb.TextureFormat.Bc2, cnb.TextureFormat.Bc3,
                      cnb.TextureFormat.Bc3Srgb, cnb.TextureFormat.Bc7,
                      cnb.TextureFormat.Bc7Srgb):
            self.assertTrue(cnb.is_block_compressed(value), value)
        for value in (cnb.TextureFormat.Rgba8, cnb.TextureFormat.Bgr565,
                      cnb.TextureFormat.Rgba32Float):
            self.assertFalse(cnb.is_block_compressed(value), value)

    def test_a_level_byte_size_follows_the_block_rounding_rule(self) -> None:
        # Computed here from the rule, not read back from CNA: a level rounds
        # each dimension up to a whole 4-texel block, which is what makes a 1x1
        # BC7 level a full 16-byte block rather than a fraction of one.
        for width, height in ((1, 1), (3, 5), (4, 4), (16, 16), (17, 1)):
            blocks = ((width + 3) // 4) * ((height + 3) // 4)
            self.assertEqual(
                cnb.texture_level_byte_size(cnb.TextureFormat.Bc7, width, height),
                blocks * 16, (width, height))
            self.assertEqual(
                cnb.texture_level_byte_size(cnb.TextureFormat.Rgba8, width, height),
                width * height * 4, (width, height))

    def test_a_zero_dimension_or_unknown_format_is_refused(self) -> None:
        with self.assertRaises(cnb.CnbFormatError):
            cnb.texture_level_byte_size(cnb.TextureFormat.Rgba8, 0, 4)
        with self.assertRaises(cnb.CnbFormatError):
            cnb.texture_level_byte_size(9999, 4, 4)

    def test_the_surface_format_mapping_is_a_bijection_over_what_it_covers(self) -> None:
        # These identifiers exist precisely so a `.cnb` does not depend on the
        # declaration order of a runtime enum; the mapping between them has to be
        # a deliberate function in both directions.
        for value in cnb.TextureFormat:
            if value is cnb.TextureFormat.Unknown:
                continue
            surface = cnb.texture_format_to_surface_format(value)
            self.assertIsInstance(surface, cnb.CnaSurfaceFormat)
            self.assertEqual(cnb.texture_format_from_surface_format(surface), value,
                             value.name)

    def test_the_two_numberings_are_genuinely_different(self) -> None:
        # If they happened to agree everywhere, the mapping would be untested by
        # anything above; they do not, and this pins that.
        differences = [value for value in cnb.TextureFormat
                       if value is not cnb.TextureFormat.Unknown
                       and int(cnb.texture_format_to_surface_format(value)) != int(value)]
        self.assertTrue(differences, "the two numberings coincide; this test is stale")

    def test_the_seven_cna_only_formats_have_no_xna_counterpart(self) -> None:
        """The measured profile boundary, stated rather than papered over.

        CNA has 27 surface formats; the selected XNA 4.0 projection has the
        first 20. Seven `.cnb` texture formats therefore map to identities
        ``Microsoft.Xna.Framework.Graphics.SurfaceFormat`` deliberately does not
        contain -- a name in that namespace is a claim about XNA. The bridge
        answers None for exactly those, rather than inventing a member or
        substituting a nearby format that would change someone's pixels.
        """
        cna_only = {cnb.CnaSurfaceFormat.ColorBgraExt, cnb.CnaSurfaceFormat.ColorSrgbExt,
                    cnb.CnaSurfaceFormat.Dxt5SrgbExt, cnb.CnaSurfaceFormat.Bc7Ext,
                    cnb.CnaSurfaceFormat.Bc7SrgbExt, cnb.CnaSurfaceFormat.ByteExt,
                    cnb.CnaSurfaceFormat.UShortExt}
        without = set()
        for value in cnb.TextureFormat:
            if value is cnb.TextureFormat.Unknown:
                continue
            surface = cnb.texture_format_to_surface_format(value)
            strict = cnb.xna_surface_format(surface)
            if strict is None:
                without.add(surface)
            else:
                self.assertIsInstance(strict, SurfaceFormat)
                self.assertEqual(int(strict), int(surface), surface.name)
        self.assertEqual(without, cna_only)
        # And the twenty that do have one are exactly the strict enum.
        self.assertEqual(
            {int(value) for value in cnb.CnaSurfaceFormat if int(value) < 20},
            {int(value) for value in SurfaceFormat})


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class Texture2DCodecTests(unittest.TestCase):
    def _pixels(self, width: int, height: int) -> bytes:
        return bytes(((x * 37 + y * 11 + channel * 3 + 1) & 0xFF)
                     for y in range(height) for x in range(width) for channel in range(4))

    def test_the_encoded_document_has_the_chunks_the_schema_specifies(self) -> None:
        pixels = self._pixels(4, 3)
        with cnb.CnbTextureData.from_rgba8(4, 3, pixels) as texture:
            image = cnb.encode_texture2d(texture, content_name="ui/panel")
        with cnb.CnbDocument.parse(image, origin="panel.cnb") as document:
            self.assertEqual(document.asset_type, cnb.AssetType.Texture2D)
            self.assertEqual(document.asset_schema_version, cnb.TEXTURE_SCHEMA_VERSION)
            self.assertEqual(document.metadata.content_name, "ui/panel")
            # The three chunks, each present exactly once, read from the table of
            # contents rather than through the decoder.
            for identity in cnb.TextureChunk:
                self.assertIsNotNone(document.find_single(int(identity)), identity.name)
            header = document.chunk(document.require_single(int(cnb.TextureChunk.Header)))
            self.assertEqual(header.uncompressed_size, 24)
            self.assertTrue(header.is_mandatory)
            # The header chunk's own fields, decoded by hand from the format.
            with document.open_chunk(header.index) as reader:
                self.assertEqual(reader.read_u32(), 4)   # width
                self.assertEqual(reader.read_u32(), 3)   # height
                self.assertEqual(reader.read_u32(), 1)   # depth
                self.assertEqual(reader.read_u32(), 1)   # faces
                self.assertEqual(reader.read_u32(), 1)   # mips
                self.assertEqual(reader.read_u32(), 1)   # representations
                reader.require_exhausted()
            # And the payload chunk holds the pixels verbatim.
            payload = document.require_single(int(cnb.TextureChunk.Payload))
            self.assertEqual(document.chunk_data(payload), pixels)

    def test_a_decoded_texture_reports_the_shape_and_the_exact_bytes(self) -> None:
        pixels = self._pixels(4, 3)
        with cnb.CnbTextureData.from_rgba8(4, 3, pixels) as texture:
            image = cnb.encode_texture2d(texture)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_texture2d(document) as decoded:
                info = decoded.info
                self.assertEqual((info.width, info.height, info.depth), (4, 3, 1))
                self.assertEqual((info.face_count, info.mip_count), (1, 1))
                self.assertEqual(info.representation_count, 1)
                self.assertEqual(decoded.representation_format(0), cnb.TextureFormat.Rgba8)
                self.assertEqual(decoded.level_count(0), 1)
                self.assertEqual(decoded.level(0, 0), pixels)

    def test_a_mip_chain_keeps_each_level_distinct_and_in_order(self) -> None:
        # Distinct fill values per level, so an off-by-one in level indexing is a
        # different byte rather than the same one twice.
        with cnb.CnbTextureData.create(4, 4, mip_count=3) as texture:
            representation = texture.add_representation(cnb.TextureFormat.Rgba8)
            for level in range(3):
                width, height, depth = texture.level_dimensions(level)
                self.assertEqual((width, height, depth),
                                 (max(4 >> level, 1), max(4 >> level, 1), 1))
                texture.set_level(representation, level,
                                  bytes([level + 1]) * (width * height * 4))
            image = cnb.encode_texture2d(texture)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_texture2d(document) as decoded:
                self.assertEqual(decoded.info.mip_count, 3)
                for level in range(3):
                    width, height, _depth = decoded.level_dimensions(level)
                    self.assertEqual(decoded.level(0, level),
                                     bytes([level + 1]) * (width * height * 4),
                                     f"level {level}")

    def test_a_payload_of_the_wrong_length_is_refused(self) -> None:
        with self.assertRaises(cnb.CnbFormatError):
            cnb.CnbTextureData.from_rgba8(4, 4, b"far too few bytes")

    def test_a_zero_dimension_is_refused_where_the_caller_can_act_on_it(self) -> None:
        # CNA's documented contract says every dimension is at least 1; its
        # implementation accepts a zero and refuses at encode time instead. The
        # wrapper enforces the stated contract at the call that got it wrong.
        for arguments in ((0, 4), (4, 0)):
            with self.assertRaises(ValueError):
                cnb.CnbTextureData.create(*arguments)
        with self.assertRaises(ValueError):
            cnb.CnbTextureData.create(4, 4, mip_count=0)

    def test_representation_selection_walks_preference_order(self) -> None:
        with cnb.CnbTextureData.create(4, 4) as texture:
            first = texture.add_representation(cnb.TextureFormat.Bc7)
            second = texture.add_representation(cnb.TextureFormat.Rgba8)
            self.assertEqual((first, second), (0, 1))
            self.assertEqual(texture.representation_count, 2)
            seen: list[cnb.TextureFormat] = []

            def supports_everything(value: cnb.TextureFormat) -> bool:
                seen.append(value)
                return True

            self.assertEqual(texture.select_representation(supports_everything), 0)
            self.assertEqual(seen, [cnb.TextureFormat.Bc7])
            self.assertEqual(
                texture.select_representation(lambda f: f == cnb.TextureFormat.Rgba8), 1)
            self.assertIsNone(texture.select_representation(lambda f: False))

    def test_a_level_is_read_from_the_representation_it_was_asked_for(self) -> None:
        # Two representations with different level bytes: reading from the wrong
        # one is a different payload rather than the same one twice.
        with cnb.CnbTextureData.create(4, 4) as texture:
            first = texture.add_representation(cnb.TextureFormat.Rgba8)
            second = texture.add_representation(cnb.TextureFormat.Bgra8)
            texture.set_level(first, 0, bytes([0xA1]) * 64)
            texture.set_level(second, 0, bytes([0xB2]) * 64)
            self.assertEqual(texture.representation_format(first), cnb.TextureFormat.Rgba8)
            self.assertEqual(texture.representation_format(second), cnb.TextureFormat.Bgra8)
            self.assertEqual(texture.level(first, 0), bytes([0xA1]) * 64)
            self.assertEqual(texture.level(second, 0), bytes([0xB2]) * 64)

    def test_an_exception_in_the_predicate_reaches_the_caller_after_native_return(self) -> None:
        # A Python exception unwinding through a C frame is undefined behaviour;
        # it is captured, the predicate answers "no", and it is re-raised here.
        with cnb.CnbTextureData.create(4, 4) as texture:
            texture.add_representation(cnb.TextureFormat.Rgba8)

            def explodes(_value: cnb.TextureFormat) -> bool:
                raise KeyError("the caller's own bug")

            with self.assertRaises(KeyError):
                texture.select_representation(explodes)
            # And the object is still usable, which it would not be after an
            # unwind through native frames.
            self.assertEqual(texture.representation_count, 1)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class TextureCubeAndVolumeCodecTests(unittest.TestCase):
    FACE_FILLS = (0x11, 0x22, 0x33, 0x44, 0x55, 0x66)

    def test_six_asymmetric_faces_survive_in_their_declared_order(self) -> None:
        # Each face is a different constant, so a face swap is a different byte
        # rather than an identical one; a symmetric fixture could not tell.
        with cnb.CnbTextureData.create(2, 2, face_count=cnb.CUBE_FACE_COUNT) as texture:
            representation = texture.add_representation(cnb.TextureFormat.Rgba8)
            for face, fill in enumerate(self.FACE_FILLS):
                texture.set_level(representation, face, bytes([fill]) * 16)
            image = cnb.encode_texture_cube(texture, content_name="sky")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.TextureCube)
            with cnb.decode_texture_cube(document) as decoded:
                self.assertEqual(decoded.info.face_count, cnb.CUBE_FACE_COUNT)
                self.assertEqual(decoded.level_count(0), cnb.CUBE_FACE_COUNT)
                for face, fill in enumerate(self.FACE_FILLS):
                    self.assertEqual(decoded.level(0, face), bytes([fill]) * 16,
                                     f"face {face}")

    def test_faces_and_mips_are_ordered_face_major(self) -> None:
        # index = face * mip_count + mip. A transposed ordering would put face 1
        # mip 0 where face 0 mip 1 belongs, which distinct fills expose.
        mips = 2
        with cnb.CnbTextureData.create(2, 2, face_count=6, mip_count=mips) as texture:
            representation = texture.add_representation(cnb.TextureFormat.Rgba8)
            for face in range(6):
                for mip in range(mips):
                    width, height, _ = texture.level_dimensions(mip)
                    texture.set_level(representation, face * mips + mip,
                                      bytes([face * 16 + mip]) * (width * height * 4))
            image = cnb.encode_texture_cube(texture)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_texture_cube(document) as decoded:
                for face in range(6):
                    for mip in range(mips):
                        width, height, _ = decoded.level_dimensions(mip)
                        self.assertEqual(
                            decoded.level(0, face * mips + mip),
                            bytes([face * 16 + mip]) * (width * height * 4),
                            f"face {face} mip {mip}")

    def test_a_cube_face_must_be_square(self) -> None:
        with cnb.CnbTextureData.create(4, 2, face_count=6) as texture:
            representation = texture.add_representation(cnb.TextureFormat.Rgba8)
            for face in range(6):
                texture.set_level(representation, face, bytes(32))
            with self.assertRaises(cnb.CnbFormatError):
                cnb.encode_texture_cube(texture)

    def test_a_volume_texture_keeps_its_depth_and_halves_it_per_level(self) -> None:
        with cnb.CnbTextureData.create(4, 4, depth=4, mip_count=2) as texture:
            representation = texture.add_representation(cnb.TextureFormat.Rgba8)
            for mip in range(2):
                width, height, depth = texture.level_dimensions(mip)
                self.assertEqual((width, height, depth),
                                 (max(4 >> mip, 1),) * 3)
                texture.set_level(representation, mip,
                                  bytes([0xA0 + mip]) * (width * height * depth * 4))
            image = cnb.encode_texture3d(texture, content_name="fog")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.Texture3D)
            with cnb.decode_texture3d(document) as decoded:
                self.assertEqual(decoded.info.depth, 4)
                self.assertEqual(decoded.level(0, 1), bytes([0xA1]) * (2 * 2 * 2 * 4))

    def test_a_texture_embedded_in_another_schema_reads_back(self) -> None:
        pixels = bytes(range(16))
        with cnb.CnbTextureData.from_rgba8(2, 2, pixels) as atlas:
            with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
                writer.set_metadata("Test.Asset", "")
                writer.append_embedded_texture2d(atlas, "Preview")
                image = writer.build()
        with cnb.CnbDocument.parse(image) as document:
            # The embedded texture uses exactly the standalone texture chunks.
            for identity in cnb.TextureChunk:
                self.assertIsNotNone(document.find_single(int(identity)), identity.name)
            with document.read_embedded_texture2d("Preview") as back:
                self.assertEqual((back.info.width, back.info.height), (2, 2))
                self.assertEqual(back.level(0, 0), pixels)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class SoundEffectCodecTests(unittest.TestCase):
    def _samples(self, frames: int, channels: int) -> bytes:
        return b"".join(struct.pack("<h", (index * 61) % 20000 - 10000)
                        for index in range(frames * channels))

    def test_frame_bytes_follow_from_the_format_and_the_channel_count(self) -> None:
        self.assertEqual(cnb.audio_frame_bytes(cnb.AudioFormat.Pcm16, 1), 2)
        self.assertEqual(cnb.audio_frame_bytes(cnb.AudioFormat.Pcm16, 2), 4)
        self.assertEqual(cnb.audio_format_name(cnb.AudioFormat.Pcm16), "Pcm16")

    def test_the_encoded_document_has_the_chunks_and_the_header_fields(self) -> None:
        samples = self._samples(20, 2)
        info = cnb.CnbSoundEffectInfo(cnb.AudioFormat.Pcm16, 22050, 2, 20, 4, 8)
        with cnb.CnbSoundEffectData.create(info, samples) as sound:
            image = cnb.encode_sound_effect(sound, content_name="sfx/step")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.SoundEffect)
            self.assertEqual(document.asset_schema_version,
                             cnb.SOUND_EFFECT_SCHEMA_VERSION)
            header = document.chunk(
                document.require_single(int(cnb.SoundEffectChunk.Header)))
            self.assertEqual(header.uncompressed_size, 28)
            with document.open_chunk(header.index) as reader:
                self.assertEqual(reader.read_u32(), int(cnb.AudioFormat.Pcm16))
                self.assertEqual(reader.read_u32(), 22050)
                self.assertEqual(reader.read_u32(), 2)
                self.assertEqual(reader.read_u32(), 20)
                self.assertEqual(reader.read_u32(), 4)
                self.assertEqual(reader.read_u32(), 8)
            data = document.require_single(int(cnb.SoundEffectChunk.Data))
            self.assertEqual(document.chunk_data(data), samples)

    def test_the_decoded_metadata_and_payload_are_exact(self) -> None:
        samples = self._samples(20, 2)
        info = cnb.CnbSoundEffectInfo(cnb.AudioFormat.Pcm16, 22050, 2, 20, 4, 8)
        with cnb.CnbSoundEffectData.create(info, samples) as sound:
            image = cnb.encode_sound_effect(sound)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_sound_effect(document) as decoded:
                self.assertEqual(decoded.info, info)
                self.assertEqual(decoded.samples, samples)
                # Duration is derived from the two numbers the file stores, so it
                # cannot disagree with them.
                self.assertAlmostEqual(decoded.info.duration_seconds, 20 / 22050)

    def test_the_sample_rate_and_the_channel_count_are_not_interchangeable(self) -> None:
        # A swap would keep the byte count identical, so only the metadata
        # distinguishes them.
        samples = self._samples(4, 2)
        info = cnb.CnbSoundEffectInfo(cnb.AudioFormat.Pcm16, 8000, 2, 4)
        with cnb.CnbSoundEffectData.create(info, samples) as sound:
            image = cnb.encode_sound_effect(sound)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_sound_effect(document) as decoded:
                self.assertEqual(decoded.info.sample_rate, 8000)
                self.assertEqual(decoded.info.channels, 2)

    def test_a_payload_that_does_not_match_the_declared_shape_is_refused(self) -> None:
        # 20 frames of stereo PCM16 need exactly 80 bytes. CNA accepts the
        # mismatch and refuses at encode; the wrapper refuses at the call that
        # built the mismatched pair, and says both numbers.
        info = cnb.CnbSoundEffectInfo(cnb.AudioFormat.Pcm16, 22050, 2, 20)
        with self.assertRaises(ValueError) as caught:
            cnb.CnbSoundEffectData.create(info, b"\x00\x00")
        self.assertIn("80", str(caught.exception))
        self.assertIn("2", str(caught.exception))

    def test_an_impossible_sample_rate_is_refused_when_the_file_is_written(self) -> None:
        # The ceiling is a file-format rule, so it applies where the file is
        # produced. Measured: CNA holds the value until then rather than at
        # construction.
        info = cnb.CnbSoundEffectInfo(cnb.AudioFormat.Pcm16,
                                      cnb.MAX_AUDIO_SAMPLE_RATE + 1, 1, 1)
        with cnb.CnbSoundEffectData.create(info, b"\x00\x00") as sound:
            self.assertEqual(sound.info.sample_rate, cnb.MAX_AUDIO_SAMPLE_RATE + 1)
            with self.assertRaises(cnb.CnbFormatError):
                cnb.encode_sound_effect(sound)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class SpriteFontCodecTests(unittest.TestCase):
    GLYPHS = (
        cnb.CnbGlyph("A", Rectangle(0, 0, 3, 4), Rectangle(1, 2, 3, 4),
                     Vector3(0.5, 3.0, -0.25)) if HAS_NATIVE else None,
    )

    def _font(self):
        font = cnb.CnbSpriteFontData.create()
        font.set_info(line_spacing=17, spacing=1.5, default_character="A")
        # Deliberately asymmetric: no two rectangles and no two kerning triples
        # share a value, so a field swap is a different number.
        font.add_glyph(cnb.CnbGlyph("A", Rectangle(0, 0, 3, 4), Rectangle(1, 2, 5, 6),
                                    Vector3(0.5, 3.0, -0.25)))
        font.add_glyph(cnb.CnbGlyph("B", Rectangle(3, 7, 8, 9), Rectangle(10, 11, 12, 13),
                                    Vector3(-1.5, 2.0, 4.75)))
        font.add_glyph(cnb.CnbGlyph("C", Rectangle(14, 15, 16, 17),
                                    Rectangle(18, 19, 20, 21),
                                    Vector3(6.25, 7.5, 8.125)))
        return font

    def test_the_encoded_document_carries_all_five_font_chunks(self) -> None:
        with cnb.CnbTextureData.from_rgba8(2, 2, bytes(range(16))) as atlas:
            with self._font() as font:
                font.set_atlas(atlas)
                image = cnb.encode_sprite_font(font, content_name="fonts/body")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.SpriteFont)
            for identity in cnb.SpriteFontChunk:
                self.assertIsNotNone(document.find_single(int(identity)), identity.name)
            # The stride rules, checked against the glyph count rather than
            # against the decoder.
            for identity, stride in ((cnb.SpriteFontChunk.GlyphBounds, 16),
                                     (cnb.SpriteFontChunk.Cropping, 16),
                                     (cnb.SpriteFontChunk.Kerning, 12),
                                     (cnb.SpriteFontChunk.Characters, 4)):
                chunk = document.chunk(document.require_single(int(identity)))
                self.assertEqual(chunk.uncompressed_size, stride * 3, identity.name)

    def test_every_glyph_field_survives_and_stays_in_its_own_place(self) -> None:
        with cnb.CnbTextureData.from_rgba8(2, 2, bytes(range(16))) as atlas:
            with self._font() as font:
                font.set_atlas(atlas)
                image = cnb.encode_sprite_font(font)
                expected = font.glyphs
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_sprite_font(document) as decoded:
                info = decoded.info
                self.assertEqual(info.glyph_count, 3)
                self.assertEqual(info.line_spacing, 17)
                self.assertEqual(info.spacing, 1.5)
                self.assertEqual(info.default_character, "A")
                self.assertTrue(info.has_default_character)
                self.assertEqual(decoded.glyphs, expected)
                # And spelled out once, so the comparison above cannot be two
                # identical mistakes.
                second = decoded.glyph(1)
                self.assertEqual(second.character, "B")
                self.assertEqual((second.bounds.X, second.bounds.Y,
                                  second.bounds.Width, second.bounds.Height),
                                 (3, 7, 8, 9))
                self.assertEqual((second.cropping.X, second.cropping.Y,
                                  second.cropping.Width, second.cropping.Height),
                                 (10, 11, 12, 13))
                self.assertEqual((second.kerning.X, second.kerning.Y, second.kerning.Z),
                                 (-1.5, 2.0, 4.75))

    def test_the_atlas_travels_with_the_font_and_is_independently_owned(self) -> None:
        pixels = bytes(range(16))
        with cnb.CnbTextureData.from_rgba8(2, 2, pixels) as atlas:
            with self._font() as font:
                font.set_atlas(atlas)
                image = cnb.encode_sprite_font(font)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_sprite_font(document) as decoded:
                first = decoded.atlas()
                second = decoded.atlas()
                try:
                    self.assertEqual(first.level(0, 0), pixels)
                    first.close()
                    # Closing one copy must not disturb the other or the font.
                    self.assertEqual(second.level(0, 0), pixels)
                    self.assertEqual(decoded.info.glyph_count, 3)
                finally:
                    second.close()

    def test_a_font_without_a_default_character_says_so(self) -> None:
        with cnb.CnbTextureData.from_rgba8(2, 2, bytes(16)) as atlas:
            with self._font() as font:
                font.set_info(line_spacing=10, spacing=0.0, default_character=None)
                font.set_atlas(atlas)
                image = cnb.encode_sprite_font(font)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_sprite_font(document) as decoded:
                self.assertIsNone(decoded.info.default_character)
                self.assertFalse(decoded.info.has_default_character)

    def test_a_default_character_with_no_glyph_is_refused(self) -> None:
        # It would name a fallback the font cannot draw.
        with cnb.CnbTextureData.from_rgba8(2, 2, bytes(16)) as atlas:
            with self._font() as font:
                font.set_info(line_spacing=10, spacing=0.0, default_character="Z")
                font.set_atlas(atlas)
                with self.assertRaises(cnb.CnbFormatError):
                    cnb.encode_sprite_font(font)

    def test_replacing_a_glyph_replaces_only_that_glyph(self) -> None:
        with self._font() as font:
            font.set_glyph(1, cnb.CnbGlyph("B", Rectangle(99, 98, 97, 96),
                                           Rectangle(95, 94, 93, 92),
                                           Vector3(1.0, 2.0, 3.0)))
            self.assertEqual(font.glyph(1).bounds.X, 99)
            self.assertEqual(font.glyph(0).bounds.X, 0)
            self.assertEqual(font.glyph(2).bounds.X, 14)

    def test_a_character_outside_the_basic_plane_is_refused_by_name(self) -> None:
        # The character map stores UTF-16 code units, so an astral character has
        # no representation; saying so beats storing half of one.
        with self._font() as font:
            with self.assertRaises(ValueError):
                font.add_glyph(cnb.CnbGlyph("\U0001F389", Rectangle(0, 0, 1, 1),
                                            Rectangle(0, 0, 1, 1), Vector3(0, 1, 0)))


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class MediaCodecTests(unittest.TestCase):
    def test_a_song_stores_its_name_duration_and_stream_reference(self) -> None:
        song = cnb.CnbSongData(stream_reference="Music/theme.ogg", name="Main Theme",
                               duration_milliseconds=185000)
        image = cnb.encode_song(song, content_name="music/theme")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.Song)
            self.assertEqual(document.asset_schema_version, cnb.MEDIA_SCHEMA_VERSION)
            self.assertIsNotNone(
                document.find_single(int(cnb.MediaChunk.SongHeader)))
            # The stream is an external reference, not embedded media: the .ogg
            # stays one asset rather than being copied into every .cnb.
            self.assertEqual([r.name for r in document.external_references],
                             ["Music/theme.ogg"])
            self.assertEqual(cnb.decode_song(document), song)

    def test_a_song_duration_the_compiler_could_not_determine_is_zero(self) -> None:
        song = cnb.CnbSongData(stream_reference="Music/x.ogg", name="", duration_milliseconds=0)
        with cnb.CnbDocument.parse(cnb.encode_song(song)) as document:
            decoded = cnb.decode_song(document)
            self.assertEqual(decoded.duration_milliseconds, 0)
            self.assertEqual(decoded.name, "")

    def test_a_video_stores_its_frame_metadata_and_soundtrack_type(self) -> None:
        video = cnb.CnbVideoData(
            stream_reference="Movies/intro.mp4", duration_milliseconds=5000,
            width=1920, height=1080, frames_per_second=29.97,
            soundtrack_type=VideoSoundtrackType.MusicAndDialog)
        image = cnb.encode_video(video, content_name="movies/intro")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.Video)
            header = document.chunk(
                document.require_single(int(cnb.MediaChunk.VideoHeader)))
            self.assertEqual(header.uncompressed_size, 24)
            self.assertEqual([r.name for r in document.external_references],
                             ["Movies/intro.mp4"])
            decoded = cnb.decode_video(document)
            self.assertEqual(decoded.stream_reference, "Movies/intro.mp4")
            self.assertEqual((decoded.width, decoded.height), (1920, 1080))
            self.assertEqual(decoded.duration_milliseconds, 5000)
            self.assertAlmostEqual(decoded.frames_per_second, 29.97, places=5)
            self.assertEqual(decoded.soundtrack_type, VideoSoundtrackType.MusicAndDialog)

    def test_the_width_and_the_height_are_not_interchangeable(self) -> None:
        video = cnb.CnbVideoData("Movies/x.mp4", 1, 320, 240, 30.0,
                                 VideoSoundtrackType.Music)
        with cnb.CnbDocument.parse(cnb.encode_video(video)) as document:
            decoded = cnb.decode_video(document)
            self.assertEqual(decoded.width, 320)
            self.assertEqual(decoded.height, 240)

    def test_an_impossible_frame_size_is_refused(self) -> None:
        video = cnb.CnbVideoData("Movies/x.mp4", 1, cnb.MAX_VIDEO_DIMENSION + 1, 240,
                                 30.0, VideoSoundtrackType.Music)
        with self.assertRaises(cnb.CnbFormatError):
            cnb.encode_video(video)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class CurveCodecTests(unittest.TestCase):
    def _curve(self) -> Curve:
        curve = Curve()
        curve.PreLoop = CurveLoopType.Oscillate
        curve.PostLoop = CurveLoopType.CycleOffset
        curve.Keys.Add(CurveKey(0.0, 1.0, 0.25, 0.5, CurveContinuity.Smooth))
        curve.Keys.Add(CurveKey(2.0, -3.0, 1.5, -1.5, CurveContinuity.Step))
        curve.Keys.Add(CurveKey(5.5, 7.25, -0.75, 2.5, CurveContinuity.Smooth))
        return curve

    def test_the_encoded_document_carries_the_curve_chunks_and_the_key_stride(self) -> None:
        image = cnb.encode_curve(self._curve(), content_name="curves/ease")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.Curve)
            self.assertEqual(document.asset_schema_version, cnb.CURVE_SCHEMA_VERSION)
            keys = document.chunk(document.require_single(int(cnb.CurveChunk.Keys)))
            # Three keys at the schema's own 20-byte stride.
            self.assertEqual(keys.uncompressed_size, 3 * 20)
            header = document.chunk(document.require_single(int(cnb.CurveChunk.Header)))
            with document.open_chunk(header.index) as reader:
                self.assertEqual(reader.read_u32(), int(CurveLoopType.Oscillate))
                self.assertEqual(reader.read_u32(), int(CurveLoopType.CycleOffset))

    def test_every_key_field_and_both_loop_types_survive(self) -> None:
        original = self._curve()
        with cnb.CnbDocument.parse(cnb.encode_curve(original)) as document:
            decoded = cnb.decode_curve(document)
        self.assertIsInstance(decoded, Curve)
        self.assertEqual(decoded.PreLoop, CurveLoopType.Oscillate)
        self.assertEqual(decoded.PostLoop, CurveLoopType.CycleOffset)
        self.assertEqual(len(decoded.Keys), 3)
        for expected, actual in zip(original.Keys, decoded.Keys):
            self.assertEqual(
                (actual.Position, actual.Value, actual.TangentIn, actual.TangentOut,
                 actual.Continuity),
                (expected.Position, expected.Value, expected.TangentIn,
                 expected.TangentOut, expected.Continuity))

    def test_the_decoded_curve_is_managed_with_nothing_left_to_close(self) -> None:
        # The native curve CNA produced is read out and destroyed before the
        # decode returns, so the caller gets an ordinary XNA value.
        with cnb.CnbDocument.parse(cnb.encode_curve(self._curve())) as document:
            decoded = cnb.decode_curve(document)
        self.assertFalse(hasattr(decoded, "close"))
        self.assertEqual(decoded.Evaluate(0.0), 1.0)

    def test_an_empty_curve_round_trips_as_an_empty_curve(self) -> None:
        empty = Curve()
        with cnb.CnbDocument.parse(cnb.encode_curve(empty)) as document:
            decoded = cnb.decode_curve(document)
        self.assertEqual(len(decoded.Keys), 0)
        self.assertEqual(decoded.PreLoop, CurveLoopType.Constant)

    def test_something_that_is_not_a_curve_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            cnb.encode_curve("not a curve")


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class AnimationClipCodecTests(unittest.TestCase):
    def _tracks(self) -> tuple:
        # Non-symmetric transforms: an identity-only fixture cannot detect a
        # translation/scale swap or a quaternion component reorder.
        return (
            cnb.CnbAnimationTrack(2, (
                cnb.CnbKeyframe(0.0, (1.0, 2.0, 3.0), (0.0, 0.0, 0.0, 1.0), (1.5, 2.5, 3.5)),
                cnb.CnbKeyframe(0.5, (4.0, 5.0, 6.0), (0.5, -0.5, 0.5, 0.5), (2.0, 4.0, 8.0)),
            )),
            cnb.CnbAnimationTrack(7, (
                cnb.CnbKeyframe(0.25, (-7.0, 8.0, -9.0), (1.0, 0.0, 0.0, 0.0),
                                (0.25, 0.5, 0.75)),
            )),
        )

    def test_the_encoded_document_carries_the_clip_chunks_and_the_key_stride(self) -> None:
        image = cnb.encode_animation_clip(
            1.5, self._tracks(), target_space=cnb.ClipTargetSpace.SceneNode,
            content_name="clips/walk")
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(document.asset_type, cnb.AssetType.AnimationClip)
            tracks = document.chunk(
                document.require_single(int(cnb.AnimationClipChunk.Tracks)))
            keys = document.chunk(
                document.require_single(int(cnb.AnimationClipChunk.Keys)))
            # Two tracks at 12 bytes, three keyframes at 48 -- the schema's own
            # strides, times counts this test set.
            self.assertEqual(tracks.uncompressed_size, 2 * 12)
            self.assertEqual(keys.uncompressed_size, 3 * 48)

    def test_every_track_and_keyframe_survives_in_order(self) -> None:
        tracks = self._tracks()
        image = cnb.encode_animation_clip(
            1.5, tracks, target_space=cnb.ClipTargetSpace.SceneNode)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_animation_clip(document) as clip:
                self.assertEqual(clip.duration_seconds, 1.5)
                self.assertEqual(clip.track_count, 2)
                self.assertEqual(clip.target_space, cnb.ClipTargetSpace.SceneNode)
                self.assertEqual(clip.tracks, tracks)

    def test_the_target_space_is_content_and_is_not_guessed(self) -> None:
        # A joint palette slot and a scene node index are different spaces; a
        # decoder that assumed one would animate the wrong thing.
        for space in (cnb.ClipTargetSpace.JointPalette, cnb.ClipTargetSpace.SceneNode):
            image = cnb.encode_animation_clip(1.0, self._tracks(), target_space=space)
            with cnb.CnbDocument.parse(image) as document:
                with cnb.decode_animation_clip(document) as clip:
                    self.assertEqual(clip.target_space, space)

    def test_a_keyframe_survives_the_byte_writer_and_the_reader_too(self) -> None:
        keyframe = cnb.CnbKeyframe(0.75, (1.0, -2.0, 3.0), (0.5, 0.5, -0.5, 0.5),
                                   (4.0, 5.0, 6.0))
        with cnb.CnbByteWriter() as writer:
            writer.write_keyframe(keyframe)
            payload = writer.copy_bytes()
        # 48 bytes: the schema's own keyframe stride.
        self.assertEqual(len(payload), 48)
        with cnb.CnbReader.over_bytes(payload) as reader:
            self.assertEqual(reader.read_keyframe(), keyframe)
            reader.require_exhausted()

    def test_a_duration_is_read_back_as_seconds(self) -> None:
        with cnb.CnbByteWriter() as writer:
            writer.write_f64(2.5)
            payload = writer.copy_bytes()
        with cnb.CnbReader.over_bytes(payload) as reader:
            self.assertEqual(reader.read_seconds("clip duration"), 2.5)

    def test_a_clip_with_no_tracks_is_still_a_clip(self) -> None:
        image = cnb.encode_animation_clip(
            0.0, (), target_space=cnb.ClipTargetSpace.JointPalette)
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_animation_clip(document) as clip:
                self.assertEqual(clip.track_count, 0)
                self.assertEqual(clip.tracks, ())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
