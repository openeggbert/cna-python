"""Source importers, `.cnj` compilation, sidecar containment, and loaders.

The importers are checked against pixels and samples this file generated, so a
decoder that transposed an image or resampled audio produces different numbers
rather than a different file size. The compiler is checked the same way, plus on
the two lists a build system actually needs -- what was absorbed and what is
still referenced.

Sidecar containment gets its own class. A compiler that resolved paths more
permissively than the runtime would be the soft way into a file the runtime
refuses to open, so traversal, absolute paths and missing files are each
asserted to be refusals rather than assumed to be.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())

from tests.cnb_fixtures import cube_dds, distinct_rgba, pcm16, png, wav  # noqa: E402

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb

#: Six faces whose channels are already 0 or 255, so the DXT1 round trip through
#: RGB565 is exact and the test can assert precise texels.
FACE_COLORS = ((255, 0, 0), (0, 255, 0), (0, 0, 255),
               (255, 255, 0), (255, 0, 255), (0, 255, 255))


class _Scratch(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="cnb-pipeline-")
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_cnj(self, name: str, document: dict) -> Path:
        return self.write(name, json.dumps(document).encode("utf-8"))


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ImageImportTests(_Scratch):
    def test_a_png_decodes_to_its_exact_pixels(self) -> None:
        # Asserted against the bytes this file put into the PNG, not against a
        # file size: a transposed or reversed image is a different assertion.
        pixels = distinct_rgba(3, 2)
        path = self.write("hero.png", png(3, 2, pixels))
        with cnb.import_image_as_texture2d(path) as texture:
            info = texture.info
            self.assertEqual((info.width, info.height), (3, 2))
            self.assertEqual((info.face_count, info.mip_count, info.depth), (1, 1, 1))
            self.assertEqual(texture.representation_format(0), cnb.TextureFormat.Rgba8)
            self.assertEqual(texture.level(0, 0), pixels)

    def test_a_colour_key_clears_only_the_alpha_of_matching_pixels(self) -> None:
        # The keyed pixel keeps its RGB and gets alpha 0, which is what the
        # runtime path does; every other pixel is untouched.
        pixels = bytearray(distinct_rgba(2, 1))
        key = (pixels[0], pixels[1], pixels[2])
        path = self.write("keyed.png", png(2, 1, bytes(pixels)))
        with cnb.import_image_as_texture2d(path, color_key=key) as texture:
            decoded = texture.level(0, 0)
            self.assertEqual(decoded[0:3], bytes(pixels[0:3]))
            self.assertEqual(decoded[3], 0)
            self.assertEqual(decoded[4:8], bytes(pixels[4:8]))

    def test_no_colour_key_is_applied_unless_one_is_asked_for(self) -> None:
        pixels = distinct_rgba(2, 1)
        path = self.write("plain.png", png(2, 1, pixels))
        with cnb.import_image_as_texture2d(path) as texture:
            self.assertEqual(texture.level(0, 0), pixels)

    def test_a_file_that_is_not_there_is_a_missing_reference(self) -> None:
        with self.assertRaises(cnb.CnbMissingReferenceError):
            cnb.import_image_as_texture2d(self.root / "absent.png")

    def test_a_file_that_is_not_an_image_is_refused(self) -> None:
        path = self.write("not-an-image.png", b"this is not a PNG at all")
        with self.assertRaises(cnb.CnbError):
            cnb.import_image_as_texture2d(path)

    def test_a_colour_key_must_be_a_triple_of_bytes(self) -> None:
        path = self.write("hero.png", png(1, 1, b"\x01\x02\x03\xff"))
        with self.assertRaises(ValueError):
            cnb.import_image_as_texture2d(path, color_key=(1, 2))
        with self.assertRaises(ValueError):
            cnb.import_image_as_texture2d(path, color_key=(1, 2, 256))


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class DdsImportTests(_Scratch):
    def test_a_cube_map_decodes_to_six_faces_in_the_declared_order(self) -> None:
        # Six different colours: a face swap is a different texel, which a
        # single-colour cube could never show.
        path = self.write("sky.dds", cube_dds(8, FACE_COLORS))
        with cnb.import_dds_as_texture_cube(path) as texture:
            info = texture.info
            self.assertEqual(info.face_count, cnb.CUBE_FACE_COUNT)
            self.assertEqual((info.width, info.height, info.depth), (8, 8, 1))
            self.assertEqual(info.mip_count, 1)
            # RGBA8, not the original DXT1 blocks: the runtime DDS path already
            # decompresses on the CPU and schema 1's contract is RGBA8.
            self.assertEqual(texture.representation_format(0), cnb.TextureFormat.Rgba8)
            for face, (red, green, blue) in enumerate(FACE_COLORS):
                level = texture.level(0, face)
                self.assertEqual(len(level), 8 * 8 * 4, f"face {face}")
                self.assertEqual(tuple(level[0:4]), (red, green, blue, 255), f"face {face}")
                # Solid, so the last texel matches the first.
                self.assertEqual(tuple(level[-4:]), (red, green, blue, 255), f"face {face}")

    def test_a_mip_chain_keeps_each_face_colour_at_every_level(self) -> None:
        path = self.write("sky.dds", cube_dds(8, FACE_COLORS, mip_count=3))
        with cnb.import_dds_as_texture_cube(path) as texture:
            self.assertEqual(texture.info.mip_count, 3)
            self.assertEqual(texture.level_count(0), 6 * 3)
            for face, (red, green, blue) in enumerate(FACE_COLORS):
                for mip in range(3):
                    width, height, _ = texture.level_dimensions(mip)
                    level = texture.level(0, face * 3 + mip)
                    self.assertEqual(len(level), width * height * 4, (face, mip))
                    self.assertEqual(tuple(level[0:4]), (red, green, blue, 255),
                                     (face, mip))

    def test_the_same_bytes_import_the_same_whether_from_a_path_or_memory(self) -> None:
        data = cube_dds(4, FACE_COLORS)
        path = self.write("sky.dds", data)
        with cnb.import_dds_as_texture_cube(path) as from_file:
            with cnb.decode_dds_as_texture_cube(data, origin="sky.dds") as from_memory:
                self.assertEqual(from_file.info, from_memory.info)
                for face in range(6):
                    self.assertEqual(from_file.level(0, face),
                                     from_memory.level(0, face), face)

    def test_a_dds_that_is_not_a_cube_map_is_refused(self) -> None:
        data = cube_dds(4, FACE_COLORS, as_cube_map=False)
        with self.assertRaises(cnb.CnbError):
            cnb.decode_dds_as_texture_cube(data, origin="flat.dds")

    def test_an_unsupported_block_format_is_refused_rather_than_guessed(self) -> None:
        data = cube_dds(4, FACE_COLORS, four_cc=b"DX10")
        with self.assertRaises(cnb.CnbError):
            cnb.decode_dds_as_texture_cube(data, origin="dx10.dds")

    def test_truncated_and_empty_dds_bytes_are_refused(self) -> None:
        data = cube_dds(4, FACE_COLORS)
        for length in (0, 4, 64, len(data) - 1):
            with self.assertRaises(cnb.CnbError, msg=f"truncated to {length}"):
                cnb.decode_dds_as_texture_cube(data[:length], origin="short.dds")


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class WavImportTests(_Scratch):
    def test_a_wav_decodes_to_its_exact_pcm_and_metadata(self) -> None:
        samples = pcm16(40)
        path = self.write("beep.wav", wav(samples, sample_rate=22050, channels=1))
        with cnb.import_wav_as_sound_effect(path) as sound:
            info = sound.info
            self.assertEqual(info.format, cnb.AudioFormat.Pcm16)
            self.assertEqual(info.sample_rate, 22050)
            self.assertEqual(info.channels, 1)
            self.assertEqual(info.frame_count, 40)
            self.assertEqual(info.loop_length, 0)
            self.assertEqual(sound.samples, samples)
            self.assertAlmostEqual(info.duration_seconds, 40 / 22050)

    def test_a_stereo_wav_keeps_its_frame_count_rather_than_its_sample_count(self) -> None:
        # 40 frames of stereo is 80 samples and 160 bytes; a frame/sample mix-up
        # would halve or double the duration.
        samples = pcm16(40, channels=2)
        path = self.write("stereo.wav", wav(samples, sample_rate=8000, channels=2))
        with cnb.import_wav_as_sound_effect(path) as sound:
            self.assertEqual(sound.info.channels, 2)
            self.assertEqual(sound.info.frame_count, 40)
            self.assertEqual(len(sound.samples), 160)
            self.assertEqual(sound.samples, samples)

    def test_a_smpl_chunk_becomes_the_sounds_loop_region(self) -> None:
        samples = pcm16(40)
        path = self.write("loop.wav", wav(samples, loop=(4, 12)))
        with cnb.import_wav_as_sound_effect(path) as sound:
            self.assertEqual(sound.info.loop_start, 4)
            self.assertGreater(sound.info.loop_length, 0)

    def test_eight_bit_pcm_is_widened_exactly(self) -> None:
        # 8-bit unsigned PCM is one of the two encodings that convert to PCM16
        # exactly; the importer widens rather than resampling.
        samples = bytes(range(0, 32))
        path = self.write("eight.wav", wav(samples, bits_per_sample=8))
        with cnb.import_wav_as_sound_effect(path) as sound:
            self.assertEqual(sound.info.format, cnb.AudioFormat.Pcm16)
            self.assertEqual(sound.info.frame_count, 32)
            widened = sound.samples
            self.assertEqual(len(widened), 64)
            for index, value in enumerate(samples):
                expected = (value - 128) * 256
                self.assertEqual(struct.unpack_from("<h", widened, index * 2)[0],
                                 expected, index)

    def test_an_encoding_the_importer_refuses_is_refused_by_name(self) -> None:
        # 24-bit is an authoring decision rather than a compiler's; silently
        # truncating someone's audio would be worse than saying so.
        samples = bytes(30)
        path = self.write("wide.wav", wav(samples, bits_per_sample=24))
        with self.assertRaises(cnb.CnbError):
            cnb.import_wav_as_sound_effect(path)

    def test_bytes_that_are_not_a_wav_are_refused(self) -> None:
        for data in (b"", b"RIFF", b"not a riff file at all"):
            with self.assertRaises(cnb.CnbError):
                cnb.decode_wav_as_sound_effect(data, origin="bad.wav")

    def test_a_truncated_wav_is_refused(self) -> None:
        data = wav(pcm16(40))
        for length in (0, 4, 20, len(data) - 4):
            with self.assertRaises(cnb.CnbError, msg=f"truncated to {length}"):
                cnb.decode_wav_as_sound_effect(data[:length], origin="short.wav")


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class CnjCompilationTests(_Scratch):
    def test_a_self_contained_curve_compiles_to_a_loadable_asset(self) -> None:
        self.write_cnj("ease.cnj", {
            "cnjVersion": 1, "type": "Curve", "preLoop": "Constant", "postLoop": "Linear",
            "keys": [{"position": 0, "value": 2.5},
                     {"position": 1, "value": 7.5, "continuity": "Step"}]})
        with cnb.compile_cnj(self.root / "ease.cnj") as result:
            self.assertEqual(result.asset_type_id, int(cnb.AssetType.Curve))
            self.assertEqual(result.asset_type_name, "Microsoft.Xna.Framework.Curve")
            # The document itself is an input dependency; it has no sidecars.
            self.assertEqual(result.absorbed_files, ("ease.cnj",))
            self.assertEqual(result.external_references, ())
            with cnb.CnbDocument.parse(result.cnb_bytes) as document:
                self.assertEqual(document.asset_type, cnb.AssetType.Curve)
                # The logical name defaults to the document's stem, not a path.
                self.assertEqual(document.metadata.content_name, "ease")
                curve = cnb.decode_curve(document)
                self.assertEqual([(key.Position, key.Value) for key in curve.Keys],
                                 [(0.0, 2.5), (1.0, 7.5)])
                self.assertEqual(curve.Keys[1].Continuity, 1)

    def test_a_texture_document_absorbs_its_sidecar_and_keeps_its_pixels(self) -> None:
        pixels = distinct_rgba(4, 3)
        self.write("hero.png", png(4, 3, pixels))
        self.write_cnj("hero.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                    "sourceFile": "hero.png"})
        with cnb.compile_cnj(self.root / "hero.cnj", content_name="ui/hero") as result:
            self.assertEqual(result.asset_type_id, int(cnb.AssetType.Texture2D))
            # Both the document and the image it named are inputs: change either
            # and the compiled file is stale.
            self.assertEqual(result.absorbed_files, ("hero.cnj", "hero.png"))
            self.assertEqual(result.external_references, ())
            with cnb.CnbDocument.parse(result.cnb_bytes) as document:
                self.assertEqual(document.metadata.content_name, "ui/hero")
                with cnb.decode_texture2d(document) as texture:
                    self.assertEqual(texture.level(0, 0), pixels)

    def test_a_sound_document_absorbs_its_wav_and_keeps_its_samples(self) -> None:
        samples = pcm16(24)
        self.write("beep.wav", wav(samples))
        self.write_cnj("beep.cnj", {"cnjVersion": 1, "type": "SoundEffect",
                                    "sourceFile": "beep.wav"})
        with cnb.compile_cnj(self.root / "beep.cnj") as result:
            self.assertEqual(result.absorbed_files, ("beep.cnj", "beep.wav"))
            with cnb.CnbDocument.parse(result.cnb_bytes) as document:
                with cnb.decode_sound_effect(document) as sound:
                    self.assertEqual(sound.samples, samples)

    def test_compiling_twice_gives_byte_identical_output(self) -> None:
        self.write_cnj("ease.cnj", {"cnjVersion": 1, "type": "Curve",
                                    "keys": [{"position": 0, "value": 1}]})
        with cnb.compile_cnj(self.root / "ease.cnj") as first:
            with cnb.compile_cnj(self.root / "ease.cnj") as second:
                self.assertEqual(first.cnb_bytes, second.cnb_bytes)

    def test_a_sidecar_resolves_against_the_documents_own_directory(self) -> None:
        pixels = distinct_rgba(2, 2)
        self.write("docs/assets/hero.png", png(2, 2, pixels))
        self.write_cnj("docs/hero.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                         "sourceFile": "assets/hero.png"})
        with cnb.compile_cnj(self.root / "docs/hero.cnj") as result:
            self.assertEqual(result.absorbed_files, ("hero.cnj", "assets/hero.png"))
            with cnb.CnbDocument.parse(result.cnb_bytes) as document:
                with cnb.decode_texture2d(document) as texture:
                    self.assertEqual(texture.level(0, 0), pixels)

    def test_the_content_root_is_a_containment_boundary_not_a_resolution_base(self) -> None:
        """The measured meaning of ``content_root``.

        ``cnb.h``'s prose calls it "the directory sidecar references resolve
        against"; the implementation joins the reference to the *document's* own
        directory and then requires the result to stay inside this root. The two
        readings differ exactly here, so this pins the one that is true: the same
        ``../`` reference is refused under the default root and accepted under a
        wider one.
        """
        pixels = distinct_rgba(2, 2)
        self.write("assets/hero.png", png(2, 2, pixels))
        self.write_cnj("docs/hero.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                         "sourceFile": "../assets/hero.png"})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "docs/hero.cnj").close()
        with cnb.compile_cnj(self.root / "docs/hero.cnj",
                             content_root=self.root) as result:
            # The absorbed list records the *authored* reference, not a resolved
            # machine path, so it stays portable.
            self.assertEqual(result.absorbed_files, ("hero.cnj", "../assets/hero.png"))
            with cnb.CnbDocument.parse(result.cnb_bytes) as document:
                with cnb.decode_texture2d(document) as texture:
                    self.assertEqual(texture.level(0, 0), pixels)

    def test_writing_the_result_to_a_file_writes_exactly_the_compiled_bytes(self) -> None:
        self.write_cnj("ease.cnj", {"cnjVersion": 1, "type": "Curve",
                                    "keys": [{"position": 0, "value": 1}]})
        with cnb.compile_cnj(self.root / "ease.cnj") as result:
            written = result.write_to(self.root / "ease.cnb")
            self.assertEqual(written, len(result.cnb_bytes))
            self.assertEqual((self.root / "ease.cnb").read_bytes(), result.cnb_bytes)
            with cnb.CnbDocument.parse_file(self.root / "ease.cnb") as document:
                self.assertEqual(document.asset_type, cnb.AssetType.Curve)

    def test_a_type_the_compiler_does_not_support_is_refused_by_name(self) -> None:
        # Effect has a reserved identifier and no schema by design: CNA has many
        # renderers, so one API's bytecode would be useless on the others.
        self.write_cnj("fx.cnj", {"cnjVersion": 1, "type": "Effect",
                                  "sourceFile": "fx.fx"})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "fx.cnj").close()

    def test_a_cnj_version_above_the_ceiling_is_refused(self) -> None:
        self.write_cnj("m3.cnj", {"cnjVersion": 3, "type": "Model", "meshes": []})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "m3.cnj").close()

    def test_a_document_that_is_not_json_is_refused(self) -> None:
        self.write("broken.cnj", b"{not json at all")
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "broken.cnj").close()

    def test_a_missing_document_is_a_missing_reference(self) -> None:
        with self.assertRaises(cnb.CnbMissingReferenceError):
            cnb.compile_cnj(self.root / "absent.cnj").close()


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class SidecarContainmentTests(_Scratch):
    """A compiler that resolved paths more permissively than the runtime would be
    the soft way into a file the runtime refuses to open."""

    def test_a_parent_traversal_is_refused(self) -> None:
        self.write_cnj("bad.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                   "sourceFile": "../../etc/passwd"})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "bad.cnj").close()

    def test_a_traversal_that_would_resolve_to_a_real_file_is_still_refused(self) -> None:
        # The refusal has to be about the shape of the name, not about whether
        # the target happens to exist -- otherwise it is a race, not a rule.
        self.write("outside.png", png(1, 1, b"\x01\x02\x03\xff"))
        self.write_cnj("inner/bad.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                         "sourceFile": "../outside.png"})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "inner/bad.cnj").close()

    def test_an_absolute_path_is_refused(self) -> None:
        target = self.write("target.png", png(1, 1, b"\x01\x02\x03\xff"))
        self.write_cnj("abs.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                   "sourceFile": str(target)})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "abs.cnj").close()

    def test_a_missing_sidecar_is_refused_rather_than_producing_an_empty_asset(self) -> None:
        self.write_cnj("gone.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                    "sourceFile": "nope.png"})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "gone.cnj").close()

    def test_a_truncated_sidecar_is_refused(self) -> None:
        full = png(4, 4, distinct_rgba(4, 4))
        self.write("short.png", full[: len(full) // 2])
        self.write_cnj("short.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                     "sourceFile": "short.png"})
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(self.root / "short.cnj").close()

    def test_no_absolute_path_reaches_the_compiled_file(self) -> None:
        """A compiled asset must not carry this machine's directory layout.

        Everything a `.cnb` records is a *logical* name; a build tree path baked
        into a shipped file would be both a leak and a broken reference on any
        other machine.
        """
        pixels = distinct_rgba(2, 2)
        self.write("hero.png", png(2, 2, pixels))
        self.write_cnj("hero.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                    "sourceFile": "hero.png"})
        with cnb.compile_cnj(self.root / "hero.cnj",
                             content_root=self.root) as result:
            image = result.cnb_bytes
        self.assertNotIn(str(self.root).encode("utf-8"), image)
        self.assertNotIn(b"/tmp/", image)
        with cnb.CnbDocument.parse(image) as document:
            self.assertNotIn("/", document.metadata.content_name)
            for reference in document.external_references:
                self.assertIsNone(cnb.logical_name_problem(reference.name))


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ModelFromCnjTests(_Scratch):
    def test_an_empty_model_document_builds_a_graph_directly(self) -> None:
        self.write_cnj("empty.cnj", {"cnjVersion": 2, "type": "Model",
                                     "meshes": [], "bones": []})
        with cnb.build_model_from_cnj(self.root / "empty.cnj") as result:
            # Measured: unlike compile_cnj, this route does not list the document
            # itself among its absorbed files.
            self.assertEqual(result.absorbed_files, ())
            self.assertEqual(result.external_references, ())
            self.assertFalse(result.model_taken)
            with result.take_model() as model:
                self.assertEqual(model.info.part_count, 0)
                self.assertEqual(model.info.mesh_count, 0)
                # A model with no bones still gets a root: CNA normalises the
                # graph so a runtime always has something to attach to.
                self.assertEqual([bone.name for bone in model.bones], ["Root"])
                self.assertEqual(model.bones[0].parent, -1)
                self.assertFalse(model.info.has_bone_hierarchy)
            self.assertTrue(result.model_taken)

    def test_the_compiler_lists_the_document_and_the_direct_builder_does_not(self) -> None:
        # Both read the same file; only compile_cnj records it as an input.
        self.write_cnj("empty.cnj", {"cnjVersion": 2, "type": "Model",
                                     "meshes": [], "bones": []})
        with cnb.compile_cnj(self.root / "empty.cnj") as compiled:
            self.assertEqual(compiled.absorbed_files, ("empty.cnj",))
        with cnb.build_model_from_cnj(self.root / "empty.cnj") as built:
            self.assertEqual(built.absorbed_files, ())

    def test_taking_the_model_twice_is_refused_rather_than_freed_twice(self) -> None:
        self.write_cnj("empty.cnj", {"cnjVersion": 2, "type": "Model",
                                     "meshes": [], "bones": []})
        with cnb.build_model_from_cnj(self.root / "empty.cnj") as result:
            model = result.take_model()
            try:
                with self.assertRaises(ValueError):
                    result.take_model()
            finally:
                model.close()

    def test_a_taken_model_outlives_the_result_it_came_from(self) -> None:
        self.write_cnj("empty.cnj", {"cnjVersion": 2, "type": "Model",
                                     "meshes": [], "bones": []})
        result = cnb.build_model_from_cnj(self.root / "empty.cnj")
        model = result.take_model()
        result.close()
        try:
            # Readable after its source is gone: the transfer really moved it.
            self.assertEqual(model.info.bone_count, 1)
            self.assertEqual(model.bone(0).name, "Root")
        finally:
            model.close()

    def test_a_missing_document_is_a_missing_reference(self) -> None:
        with self.assertRaises(cnb.CnbMissingReferenceError):
            cnb.build_model_from_cnj(self.root / "absent.cnj").close()


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class LoaderRegistryTests(_Scratch):
    TYPE_NAME = "CnaPythonTests.Level"

    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(cnb.clear_loader_registry)
        cnb.clear_loader_registry()

    def _document(self, type_name: str | None = None, payload: bytes = b"\x2a\x00\x00\x00"):
        name = self.TYPE_NAME if type_name is None else type_name
        identifier = cnb.asset_type_id_from_name(name)
        with cnb.CnbWriter(identifier, 1) as writer:
            writer.set_metadata(name, "levels/one")
            writer.add_chunk(cnb.chunk_id("lvlh"), payload)
            return writer.build()

    def test_the_builtins_cna_can_register_alone_are_curve_and_animation_clip(self) -> None:
        # Not every built-in type: the other eight construct a runtime object
        # that needs a device or the manager itself.
        cnb.register_builtin_loaders()
        self.assertTrue(cnb.is_loader_registered(int(cnb.AssetType.Curve)))
        self.assertTrue(cnb.is_loader_registered(int(cnb.AssetType.AnimationClip)))
        for absent in (cnb.AssetType.Texture2D, cnb.AssetType.Model,
                       cnb.AssetType.SpriteFont, cnb.AssetType.SoundEffect,
                       cnb.AssetType.Song, cnb.AssetType.Video,
                       cnb.AssetType.Texture3D, cnb.AssetType.TextureCube):
            self.assertFalse(cnb.is_loader_registered(int(absent)), absent.name)
        self.assertEqual(cnb.registered_type_name(int(cnb.AssetType.Curve)),
                         "Microsoft.Xna.Framework.Curve")
        # Idempotent.
        cnb.register_builtin_loaders()
        self.assertTrue(cnb.is_loader_registered(int(cnb.AssetType.Curve)))

    def test_registering_a_python_loader_makes_it_findable_and_resolvable(self) -> None:
        with cnb.register_loader(self.TYPE_NAME, lambda document, name: None) as reg:
            self.assertEqual(reg.asset_type_id,
                             cnb.asset_type_id_from_name(self.TYPE_NAME))
            self.assertTrue(cnb.is_loader_registered(reg.asset_type_id))
            self.assertEqual(cnb.registered_type_name(reg.asset_type_id), self.TYPE_NAME)
            found = cnb.find_loader(reg.asset_type_id)
            self.assertIsNotNone(found)
            found.close()
            with cnb.CnbDocument.parse(self._document()) as document:
                with cnb.resolve_loader(document) as loader:
                    self.assertIsNotNone(loader)
        self.assertFalse(cnb.is_loader_registered(
            cnb.asset_type_id_from_name(self.TYPE_NAME)))

    def test_finding_a_loader_that_is_not_registered_is_an_ordinary_answer(self) -> None:
        self.assertIsNone(cnb.find_loader(cnb.asset_type_id_from_name("Nothing.Here")))
        self.assertFalse(cnb.is_loader_registered(
            cnb.asset_type_id_from_name("Nothing.Here")))
        self.assertEqual(cnb.registered_type_name(
            cnb.asset_type_id_from_name("Nothing.Here")), "")

    def test_only_a_custom_identifier_may_be_claimed(self) -> None:
        # CNA's built-in and reserved identifiers belong to CNA, and there is
        # deliberately no parameter by which a caller can take one.
        for name in ("Microsoft.Xna.Framework.Curve", "anything"):
            identifier = cnb.asset_type_id_from_name(name)
            self.assertTrue(cnb.is_custom_asset_type_id(identifier), name)

    def test_registering_the_same_name_twice_is_accepted(self) -> None:
        first = cnb.register_loader(self.TYPE_NAME, lambda d, n: None)
        second = cnb.register_loader(self.TYPE_NAME, lambda d, n: None)
        try:
            self.assertEqual(first.asset_type_id, second.asset_type_id)
        finally:
            second.close()
            first.close()

    def test_the_writer_refuses_to_produce_a_file_that_would_collide(self) -> None:
        """A custom identifier is a 31-bit hash, so a collision is possible.

        The measured guard is stronger than "resolution checks the name": the
        *writer* refuses a custom-typed file whose canonical name does not hash
        to its own identifier, so there is no path through this API to producing
        a file its own loader would have to refuse.
        """
        identifier = cnb.asset_type_id_from_name(self.TYPE_NAME)
        with cnb.CnbWriter(identifier, 1) as writer:
            writer.set_metadata("SomeoneElse.Level", "levels/one")
            writer.add_chunk(cnb.chunk_id("lvlh"), b"\x00")
            with self.assertRaises(cnb.CnbFormatError) as caught:
                writer.build()
            self.assertIn("collision", str(caught.exception))
        # And a custom-typed file carrying no canonical name at all is refused
        # too: for a custom type the name is identity, not a label.
        with cnb.CnbWriter(identifier, 1) as writer:
            writer.add_chunk(cnb.chunk_id("lvlh"), b"\x00")
            with self.assertRaises(cnb.CnbError):
                writer.build()

    def test_resolution_refuses_a_document_with_no_registered_loader(self) -> None:
        with cnb.register_loader(self.TYPE_NAME, lambda d, n: None):
            other = self._document(type_name="SomeoneElse.Level")
            with cnb.CnbDocument.parse(other) as document:
                self.assertNotEqual(document.asset_type_id,
                                    cnb.asset_type_id_from_name(self.TYPE_NAME))
                with self.assertRaises(cnb.CnbError):
                    cnb.resolve_loader(document).close()

    def test_clearing_the_registry_withdraws_everything(self) -> None:
        cnb.register_builtin_loaders()
        registration = cnb.register_loader(self.TYPE_NAME, lambda d, n: None)
        try:
            cnb.clear_loader_registry()
            self.assertFalse(cnb.is_loader_registered(int(cnb.AssetType.Curve)))
            self.assertFalse(cnb.is_loader_registered(registration.asset_type_id))
        finally:
            registration.close()

    def test_a_closed_registration_refuses_further_loads(self) -> None:
        registration = cnb.register_loader(self.TYPE_NAME, lambda d, n: None)
        registration.close()
        registration.close()  # idempotent
        with cnb.CnbDocument.parse(self._document()) as document:
            with self.assertRaises(ValueError):
                registration.load(document, None)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
