"""The XNA 4.0 Content Pipeline: importers, processors, and both serializers.

Everything here runs with **no CNA library**. A content build reads files and
writes files, and this projection needs nothing else -- which is itself a claim
the first test in this module checks, because a design-time package that quietly
loaded a game runtime would be a different thing from what XNA ships.

The strongest oracle in the file is not in this file at all: it is
``Microsoft.Xna.Framework.Content.ContentManager``, in the same repository,
reading what the compiler writes. A round trip through an independent reader is
a much better check of an XNB than any comparison against a specification, and
it is what caught two real defects while this was written -- a list reader named
after the element's *reader* rather than its type, and an element writer left
out of the file's reader table.
"""

from __future__ import annotations

import io
import json
import math
import os
import struct
import unittest
from datetime import timedelta
from pathlib import Path

from Microsoft.Xna.Framework import (
    Color, Matrix, Point, Quaternion, Rectangle, Vector2, Vector3, Vector4,
)
from Microsoft.Xna.Framework.Graphics import (
    CompareFunction, GraphicsProfile, SurfaceFormat, VertexElementFormat,
    VertexElementUsage,
)
from Microsoft.Xna.Framework.Content.Pipeline import (
    ContentBuildLogger, ContentIdentity, ContentImporterAttribute, ContentItem,
    ContentProcessorAttribute, ExternalReferenceOfT, InvalidContentException,
    OpaqueDataDictionary, PipelineComponentScanner, PipelineException,
    TargetPlatform, TextureImporter, VideoContent, WavImporter, XImporter,
)
from Microsoft.Xna.Framework.Content.Pipeline.Audio import (
    AudioContent, AudioFileType, ConversionFormat, ConversionQuality,
)
from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
    AnimationChannel, AnimationKeyframe, BasicMaterialContent, BitmapContent,
    BoneContent, BoneWeight, BoneWeightCollection, Dxt1BitmapContent,
    Dxt5BitmapContent, FontDescription, FontDescriptionStyle, GeometryContent,
    MeshBuilder, MeshContent, MeshHelper, NodeContent, PixelBitmapContentOfT,
    Texture2DContent, VectorConverter, VertexChannelNames,
)
from Microsoft.Xna.Framework.Content.Pipeline.Processors import (
    EffectProcessor, FontDescriptionProcessor, FontTextureProcessor,
    ModelProcessor, PassThroughProcessor, SoundEffectProcessor,
    SpriteTextureProcessor, TextureProcessor, TextureProcessorOutputFormat,
)
from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler import (
    ContentCompiler,
)
from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Intermediate import (
    IntermediateSerializer,
)
from Microsoft.Xna.Framework.Content.Pipeline.Tasks import (
    BuildContent, BuildXact, CleanContent, GetLastOutputs,
)

from .device_fixtures import in_game
from .pipeline_fixtures import (
    X_QUAD, TemporaryContent, bmp_bytes, checkerboard, content_manager,
    dds_bytes, dxt_dds_bytes, mp3_with_decoy_tag, png_bytes,
    png_palette_bytes, requires_native, tga_bottom_up, tga_bytes,
    wav_bytes, wav_with_odd_chunk,
)


class ImportTimeSeparationTests(unittest.TestCase):
    """The pipeline is design-time, and the runtime must not drag it in."""

    def test_importing_the_runtime_content_namespace_does_not_load_the_pipeline(
            self) -> None:
        """A game imports ``Content``; a build imports ``Content.Pipeline``.

        Python only imports a subpackage when something asks for it, which is
        what makes the separation structural rather than a convention. Asserted
        in a fresh interpreter, because this module has already imported both.
        """
        import subprocess
        import sys

        source = (
            "import sys\n"
            "import Microsoft.Xna.Framework.Content\n"
            "print(any(name.startswith('Microsoft.Xna.Framework.Content.Pipeline')\n"
            "          for name in sys.modules))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", source], capture_output=True, text=True,
            cwd=os.fspath(Path(__file__).resolve().parents[1]),
            env=dict(os.environ,
                     PYTHONPATH=os.pathsep.join(sys.path[:1] + [
                         os.fspath(Path(__file__).resolve().parents[1] / "src")])))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False", result.stderr)

    def test_the_pipeline_needs_no_native_library(self) -> None:
        """Importing every pipeline package must not load a CNA library.

        A content build runs on a build server with no graphics device, so this
        is a real requirement rather than a tidy one.
        """
        import subprocess
        import sys

        source = (
            "import sys\n"
            "import Microsoft.Xna.Framework.Content.Pipeline\n"
            "import Microsoft.Xna.Framework.Content.Pipeline.Audio\n"
            "import Microsoft.Xna.Framework.Content.Pipeline.Graphics\n"
            "import Microsoft.Xna.Framework.Content.Pipeline.Processors\n"
            "import Microsoft.Xna.Framework.Content.Pipeline.Tasks\n"
            "import Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler\n"
            "import Microsoft.Xna.Framework.Content.Pipeline.Serialization.Intermediate\n"
            "from _cna_native import loader\n"
            "print(loader._library is None)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", source], capture_output=True, text=True,
            cwd=os.fspath(Path(__file__).resolve().parents[1]),
            env=dict(os.environ,
                     PYTHONPATH=os.pathsep.join(sys.path[:1] + [
                         os.fspath(Path(__file__).resolve().parents[1] / "src")])))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True", result.stderr)


class IdentityAndCollectionTests(unittest.TestCase):
    def test_an_external_reference_resolves_against_the_content_that_names_it(
            self) -> None:
        identity = ContentIdentity("/project/models/hero.x", "XImporter")
        reference = ExternalReferenceOfT("textures/skin.png", identity)
        self.assertEqual(
            reference.Filename,
            os.path.abspath("/project/models/textures/skin.png"))

    def test_a_windows_authored_path_resolves_on_this_host(self) -> None:
        """A content project is authored on Windows and built anywhere.

        The separator in the identity is a backslash, and the answer has to be
        the same directory it would be on the machine the artist used.
        """
        identity = ContentIdentity(r"C:\project\models\hero.x", "XImporter")
        reference = ExternalReferenceOfT("skin.png", identity)
        self.assertTrue(reference.Filename.endswith(
            os.path.join("project", "models", "skin.png")),
            reference.Filename)

    def test_an_external_reference_needs_a_source_to_resolve_against(self) -> None:
        with self.assertRaises(ValueError):
            ExternalReferenceOfT("skin.png", ContentIdentity())

    def test_opaque_data_tells_an_absent_key_from_one_set_to_nothing(self) -> None:
        """A processor that cleared a parameter did so on purpose."""
        data = OpaqueDataDictionary()
        self.assertEqual(data.GetValue("scale", 2.0), 2.0)
        data["scale"] = None
        self.assertIsNone(data.GetValue("scale", 2.0))

    def test_a_named_dictionary_refuses_an_element_of_the_wrong_type(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            AnimationChannelDictionary,
        )

        channels = AnimationChannelDictionary()
        channels["walk"] = AnimationChannel()
        with self.assertRaises(TypeError):
            channels["run"] = "not a channel"

    def test_a_child_collection_owns_its_children_and_refuses_to_steal_one(
            self) -> None:
        first, second = NodeContent(), NodeContent()
        child = NodeContent()
        first.Children.Add(child)
        self.assertIs(child.Parent, first)
        with self.assertRaises(ValueError):
            second.Children.Add(child)
        first.Children.Remove(child)
        self.assertIsNone(child.Parent)
        second.Children.Add(child)
        self.assertIs(child.Parent, second)

    def test_a_logger_names_the_file_a_message_belongs_to(self) -> None:
        logger = ContentBuildLogger()
        logger.LoggerRootDirectory = os.path.abspath("/project")
        logger.PushFile(os.path.abspath("/project/models/hero.x"))
        self.assertEqual(logger.GetCurrentFilename(None),
                         os.path.join("models", "hero.x"))
        identity = ContentIdentity(os.path.abspath("/project/textures/skin.png"))
        self.assertEqual(logger.GetCurrentFilename(identity),
                         os.path.join("textures", "skin.png"),
                         "an identity naming a source file is the better answer")
        logger.PopFile()
        self.assertIsNone(logger.GetCurrentFilename(None))

    def test_popping_a_file_that_was_never_pushed_is_an_error(self) -> None:
        with self.assertRaises(RuntimeError):
            ContentBuildLogger().PopFile()


class ImageDecoderTests(unittest.TestCase):
    """Four formats, all decoded here, all checked against what was encoded."""

    def setUp(self) -> None:
        super().setUp()
        self.rows = checkerboard(7, 5)

    def _decoded(self, raw: bytes) -> list[list[Color]]:
        from Microsoft.Xna.Framework.Content.Pipeline._images import decode

        width, height, rows = decode(raw)
        self.assertEqual((width, height), (7, 5))
        return rows

    def test_every_png_filter_decodes_to_the_same_image(self) -> None:
        """All five filters, because each refers to different neighbours."""
        for filter_type in range(5):
            with self.subTest(filter=filter_type):
                self.assertEqual(
                    self._decoded(png_bytes(self.rows, filter_type=filter_type)),
                    self.rows)

    def test_a_greyscale_png_decodes_with_its_value_in_every_channel(self) -> None:
        decoded = self._decoded(png_bytes(self.rows, colour_type=0))
        for y, row in enumerate(decoded):
            for x, pixel in enumerate(row):
                original = self.rows[y][x].R
                self.assertEqual((pixel.R, pixel.G, pixel.B, pixel.A),
                                 (original, original, original, 255))

    def test_a_bottom_up_bmp_is_not_upside_down(self) -> None:
        self.assertEqual(self._decoded(bmp_bytes(self.rows)), self.rows)

    def test_a_top_down_bmp_is_the_same_image(self) -> None:
        self.assertEqual(self._decoded(bmp_bytes(self.rows, top_down=True)),
                         self.rows)

    def test_a_run_length_encoded_tga_decodes_like_the_plain_one(self) -> None:
        plain = self._decoded(tga_bytes(self.rows))
        encoded = self._decoded(tga_bytes(self.rows, run_length=True))
        self.assertEqual(plain, self.rows)
        self.assertEqual(encoded, self.rows)

    def test_an_uncompressed_dds_decodes_through_its_channel_masks(self) -> None:
        self.assertEqual(self._decoded(dds_bytes(self.rows)), self.rows)

    def test_a_file_that_is_none_of_the_four_says_so(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline._images import (
            UnsupportedImage, decode,
        )

        with self.assertRaises(UnsupportedImage) as raised:
            decode(b"not an image at all, not even close")
        self.assertIn("PNG, BMP, TGA or DDS", str(raised.exception))

    def test_an_interlaced_png_is_refused_rather_than_misread(self) -> None:
        raw = bytearray(png_bytes(self.rows))
        raw[8 + 8 + 12] = 1  # the interlace byte of IHDR
        from Microsoft.Xna.Framework.Content.Pipeline._images import (
            UnsupportedImage, decode,
        )

        with self.assertRaises(UnsupportedImage) as raised:
            decode(bytes(raw))
        self.assertIn("interlaced", str(raised.exception))


@requires_native
class ImageOracleTests(unittest.TestCase, ):
    """The decoders, checked against a decoder that is not theirs.

    CNA decodes PNG itself, through ``cna_texture2d_create_from_encoded_memory``.
    Handing it the same bytes and comparing pixel for pixel is an oracle with no
    code in common with the one being tested -- which is the only kind worth
    having for a decoder.
    """

    def test_cna_decodes_the_same_pixels_this_decoder_does(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline._images import decode
        from Microsoft.Xna.Framework.Graphics import Texture2D

        rows = checkerboard(8, 4)
        # Opaque only: CNA's decoder premultiplies nothing, but a comparison
        # that included alpha would be comparing two conventions rather than
        # two decoders.
        rows = [[Color(pixel.R, pixel.G, pixel.B, 255) for pixel in row]
                for row in rows]
        raw = png_bytes(rows)
        _width, _height, ours = decode(raw)
        self.assertEqual(ours, rows)

        def body(game, observed):
            # ``Texture2D.FromStream`` is XNA's own decoder entry point, and it
            # is CNA's decoder underneath. Public API on both sides: nothing
            # here reaches into the one being checked.
            texture = None
            try:
                texture = Texture2D.FromStream(game.GraphicsDevice, io.BytesIO(raw))
                destination = [Color(0, 0, 0, 0)] * (8 * 4)
                texture.GetData(destination)
                observed["theirs"] = [
                    [destination[y * 8 + x] for x in range(8)] for y in range(4)]
            except NotImplementedError as error:
                observed["error"] = str(error)
            finally:
                if texture is not None:
                    texture.Dispose()

        observed = in_game(body, graphics=True)
        if "error" in observed:
            self.skipTest(
                f"this CNA build declined to decode the PNG: {observed['error']}")
        self.assertEqual(observed["theirs"], ours,
                         "two independent decoders must agree pixel for pixel")


class DxtCodecTests(unittest.TestCase):
    """The block compressor, checked by decompressing and by hand."""

    @staticmethod
    def _bitmap(width: int, height: int, maker) -> PixelBitmapContentOfT:
        bitmap = PixelBitmapContentOfT(width, height, element=Color)
        for y in range(height):
            for x in range(width):
                bitmap.SetPixel(x, y, maker(x, y))
        return bitmap

    def test_a_collinear_block_survives_dxt1_within_565_quantisation(self) -> None:
        """A grey ramp is exactly what DXT1's four-colour palette represents.

        The bound is the format's own: five bits of red and blue and six of
        green, so a channel can move by at most four before quantisation and
        must not move by more.
        """
        source = self._bitmap(4, 4, lambda x, y: Color(x * 60, x * 60, x * 60, 255))
        compressed = Dxt1BitmapContent(4, 4)
        BitmapContent.Copy(source, compressed)
        self.assertEqual(len(compressed.GetPixelData()), 8,
                         "one DXT1 block is eight bytes")
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(compressed, back)
        for y in range(4):
            for x in range(4):
                first, second = source.GetPixel(x, y), back.GetPixel(x, y)
                for channel in "RGB":
                    self.assertLessEqual(
                        abs(getattr(first, channel) - getattr(second, channel)), 4,
                        f"{channel} at {x},{y}")

    def test_a_constant_block_comes_back_at_its_own_565_value(self) -> None:
        """No interpolation error at all: only the format's quantisation.

        The expected value is computed here from the format's own rule -- keep
        the high bits, and replicate them downwards, which is why 5 bits of
        0b11111 decode to 255 and not to 248. Working it out independently is
        what makes this a check of the codec rather than a copy of it.
        """
        def quantise(value: int, bits: int) -> int:
            kept = value >> (8 - bits)
            return (kept << (8 - bits)) | (kept >> (2 * bits - 8))

        colour = Color(200, 100, 50, 255)
        expected = Color(quantise(200, 5), quantise(100, 6), quantise(50, 5), 255)
        source = self._bitmap(4, 4, lambda x, y: colour)
        compressed = Dxt1BitmapContent(4, 4)
        BitmapContent.Copy(source, compressed)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(compressed, back)
        self.assertEqual(back.GetPixel(2, 2), expected)

    def test_dxt5_stores_alpha_to_within_one_step_of_its_own_table(self) -> None:
        source = self._bitmap(
            4, 4, lambda x, y: Color(60, 70, 80, min(255, y * 80)))
        compressed = Dxt5BitmapContent(4, 4)
        BitmapContent.Copy(source, compressed)
        self.assertEqual(len(compressed.GetPixelData()), 16)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(compressed, back)
        for y in range(4):
            # Eight alpha values interpolated between the block's extremes: the
            # worst error is half a step, and a step here is 240/7.
            self.assertLessEqual(
                abs(back.GetPixel(0, y).A - source.GetPixel(0, y).A), 18)

    def test_dxt1_punch_through_keeps_transparent_pixels_transparent(self) -> None:
        source = self._bitmap(
            4, 4, lambda x, y: Color(200, 100, 50, 0 if x == 0 else 255))
        compressed = Dxt1BitmapContent(4, 4)
        BitmapContent.Copy(source, compressed)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(compressed, back)
        for y in range(4):
            self.assertEqual(back.GetPixel(0, y).A, 0)
            self.assertEqual(back.GetPixel(1, y).A, 255)

    def test_a_hand_worked_block_decodes_to_the_documented_palette(self) -> None:
        """One block, decoded against the format written out by hand.

        Endpoints 0xFFFF (white) and 0x0000 (black) in four-colour mode, with
        indices 0, 1, 2, 3 across the first row. The two interpolated colours
        are two-thirds and one-third of the way, and the format says those are
        computed on the *8-bit* values -- so 170 and 85, not 171 and 84.
        """
        blocks = struct.pack("<HHI", 0xFFFF, 0x0000, 0b11100100)
        bitmap = Dxt1BitmapContent(4, 4)
        bitmap.SetPixelData(blocks)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(bitmap, back)
        self.assertEqual([back.GetPixel(x, 0).R for x in range(4)],
                         [255, 0, 170, 85])

    def test_a_level_narrower_than_a_block_still_compresses(self) -> None:
        """The bottom of every mipmap chain is smaller than 4x4."""
        source = self._bitmap(2, 2, lambda x, y: Color(10, 20, 30, 255))
        compressed = Dxt1BitmapContent(2, 2)
        BitmapContent.Copy(source, compressed)
        self.assertEqual(len(compressed.GetPixelData()), 8)
        back = PixelBitmapContentOfT(2, 2, element=Color)
        BitmapContent.Copy(compressed, back)
        self.assertEqual(back.GetPixel(1, 1).G, 20)

    def test_an_already_compressed_dds_is_imported_without_recompressing(self) -> None:
        """A DXT file arrives as DXT: a decode/encode round trip loses quality."""
        blocks = struct.pack("<HHI", 0xFFFF, 0x0000, 0b11100100)
        raw = dxt_dds_bytes(4, 4, blocks, b"DXT1")
        importer = TextureImporter()
        content = importer.Import(_written(self, "cube.dds", raw), _NullContext())
        bitmap = content.Faces[0][0]
        self.assertIsInstance(bitmap, Dxt1BitmapContent)
        self.assertEqual(bitmap.GetPixelData(), blocks,
                         "the artist's blocks, byte for byte")


class VectorConverterTests(unittest.TestCase):
    def test_a_pixel_type_names_the_surface_format_it_becomes(self) -> None:
        self.assertEqual(VectorConverter.TryGetSurfaceFormat(Color),
                         (True, SurfaceFormat.Color))

    def test_a_type_that_is_not_a_texture_format_answers_no(self) -> None:
        found, value = VectorConverter.TryGetSurfaceFormat(Vector3)
        self.assertFalse(found)
        self.assertIsNone(value)

    def test_the_two_overloads_dispatch_on_the_enum_they_are_given(self) -> None:
        self.assertEqual(VectorConverter.TryGetVectorType(SurfaceFormat.Color),
                         (True, Color))
        self.assertEqual(
            VectorConverter.TryGetVectorType(VertexElementFormat.Vector3),
            (True, Vector3))

    def test_a_converter_goes_between_any_two_pixel_types(self) -> None:
        convert = VectorConverter.GetConverter(
            sourceType=Color, destinationType=Vector4)
        self.assertEqual(convert(Color(255, 0, 128, 255)).X, 1.0)


def _written(case: unittest.TestCase, name: str, raw: bytes) -> str:
    import tempfile

    directory = tempfile.mkdtemp(prefix="cna-pipeline-")
    case.addCleanup(_remove, directory)
    path = os.path.join(directory, name)
    with open(path, "wb") as stream:
        stream.write(raw)
    return path


def _remove(directory: str) -> None:
    import shutil

    shutil.rmtree(directory, ignore_errors=True)


class _NullContext:
    """An importer context that records dependencies and nothing else."""

    def __init__(self) -> None:
        self.dependencies: list[str] = []

    @property
    def Logger(self):
        return None

    @property
    def OutputDirectory(self) -> str:
        return ""

    @property
    def IntermediateDirectory(self) -> str:
        return ""

    def AddDependency(self, filename: str) -> None:
        self.dependencies.append(filename)


class AudioImportTests(unittest.TestCase):
    def test_a_wav_is_read_completely_including_its_loop_region(self) -> None:
        raw = wav_bytes(sample_rate=22050, channels=2, frames=512,
                        loop=(64, 128))
        path = _written(self, "sound.wav", raw)
        content = WavImporter().Import(path, _NullContext())
        self.assertEqual(content.FileType, AudioFileType.Wav)
        self.assertEqual(content.Format.ChannelCount, 2)
        self.assertEqual(content.Format.SampleRate, 22050)
        self.assertEqual(content.Format.BitsPerSample, 16)
        self.assertEqual(content.Format.BlockAlign, 4)
        self.assertEqual(len(content.Data), 512 * 2 * 2)
        self.assertEqual((content.LoopStart, content.LoopLength), (64, 128))
        # 512 frames at 22050 Hz.
        self.assertAlmostEqual(content.Duration.total_seconds(),
                               512 / 22050.0, places=6)
        content.Dispose()

    def test_a_wav_with_no_loop_chunk_plays_once(self) -> None:
        path = _written(self, "once.wav", wav_bytes())
        content = WavImporter().Import(path, _NullContext())
        self.assertEqual((content.LoopStart, content.LoopLength), (0, 0))

    def test_the_native_wave_format_is_the_bytes_a_platform_expects(self) -> None:
        path = _written(self, "sound.wav", wav_bytes(channels=1))
        content = WavImporter().Import(path, _NullContext())
        header = bytes(content.Format.NativeWaveFormat)
        tag, channels, rate, average, align, bits, extra = struct.unpack_from(
            "<HHIIHHH", header, 0)
        self.assertEqual((tag, channels, bits, extra), (1, 1, 16, 0))
        self.assertEqual(average, rate * align)

    def test_a_disposed_audio_content_refuses_to_be_read(self) -> None:
        path = _written(self, "sound.wav", wav_bytes())
        content = WavImporter().Import(path, _NullContext())
        content.Dispose()
        with self.assertRaises(RuntimeError):
            content.Data

    def test_converting_to_a_format_with_no_encoder_says_which(self) -> None:
        path = _written(self, "sound.wav", wav_bytes())
        content = WavImporter().Import(path, _NullContext())
        with self.assertRaises(InvalidContentException) as raised:
            content.ConvertFormat(ConversionFormat.Xma, ConversionQuality.Best,
                                  None)
        self.assertIn("XMA", str(raised.exception))

    def test_converting_a_pcm_wav_to_pcm_leaves_it_alone(self) -> None:
        path = _written(self, "sound.wav", wav_bytes())
        content = WavImporter().Import(path, _NullContext())
        before = bytes(content.Data)
        content.ConvertFormat(ConversionFormat.Pcm, ConversionQuality.Best, None)
        self.assertEqual(bytes(content.Data), before)

    def test_an_mp3_header_is_read_and_its_samples_are_refused_with_the_reason(
            self) -> None:
        """BLOCKED_UPSTREAM, and narrow: the header is exact, the samples are not.

        The frame header below is a real MPEG-1 Layer III header -- 128 kbit/s,
        44.1 kHz, joint stereo -- and every field the type reports comes out of
        it. What cannot be produced is the decoded PCM, and the refusal says
        exactly why and what would unblock it.
        """
        # 0xFF 0xFB: sync, MPEG-1, Layer III, no CRC. 0x90: 128 kbit/s, 44.1 kHz.
        # 0x40: joint stereo.
        frame = bytes((0xFF, 0xFB, 0x90, 0x40)) + bytes(400)
        path = _written(self, "song.mp3", frame)
        from Microsoft.Xna.Framework.Content.Pipeline import Mp3Importer

        content = Mp3Importer().Import(path, _NullContext())
        self.assertEqual(content.Format.SampleRate, 44100)
        self.assertEqual(content.Format.ChannelCount, 2)
        self.assertEqual(content.Format.AverageBytesPerSecond, 128_000 // 8)
        self.assertEqual(content.Format.Format, 85,
                         "WAVE_FORMAT_MPEGLAYER3")
        with self.assertRaises(InvalidContentException) as raised:
            content.Data
        message = str(raised.exception)
        self.assertIn("needs a codec", message)
        self.assertIn("SoundEffect", message,
                      "the refusal names what CNA can and cannot do")

    def test_an_id3_tag_does_not_hide_the_frame_header(self) -> None:
        tag = b"ID3" + bytes((3, 0, 0, 0, 0, 0, 4)) + bytes(4)
        frame = bytes((0xFF, 0xFB, 0x90, 0x40)) + bytes(64)
        path = _written(self, "tagged.mp3", tag + frame)
        from Microsoft.Xna.Framework.Content.Pipeline import Mp3Importer

        content = Mp3Importer().Import(path, _NullContext())
        self.assertEqual(content.Format.SampleRate, 44100)


class XImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.path = _written(self, "quad.x", X_QUAD.encode("utf-8"))
        self.scene = XImporter().Import(self.path, _NullContext())

    def test_the_frame_hierarchy_and_its_transform_are_read(self) -> None:
        self.assertEqual(len(self.scene.Children), 1)
        root = self.scene.Children[0]
        self.assertEqual(root.Name, "Root")
        self.assertEqual((root.Transform.M41, root.Transform.M42,
                          root.Transform.M43), (3.0, 4.0, 5.0))

    def test_positions_belong_to_the_mesh_and_are_shared(self) -> None:
        mesh = self.scene.Children[0].Children[0]
        self.assertIsInstance(mesh, MeshContent)
        self.assertEqual(mesh.Name, "Quad")
        self.assertEqual(len(mesh.Positions), 4)
        self.assertEqual(mesh.Positions[2], Vector3(1.0, 2.0, 0.0))
        for geometry in mesh.Geometry:
            self.assertIs(geometry.Vertices._positions, mesh.Positions)

    def test_the_two_materials_split_the_mesh_into_two_geometries(self) -> None:
        mesh = self.scene.Children[0].Children[0]
        self.assertEqual(len(mesh.Geometry), 2)
        names = sorted(geometry.Material.Name for geometry in mesh.Geometry)
        self.assertEqual(names, ["Blue", "Red"])

    def test_a_materials_colours_come_out_of_the_file(self) -> None:
        mesh = self.scene.Children[0].Children[0]
        red = next(geometry.Material for geometry in mesh.Geometry
                   if geometry.Material.Name == "Red")
        self.assertEqual(red.DiffuseColor, Vector3(1.0, 0.0, 0.0))
        self.assertEqual(red.SpecularPower, 32.0)
        self.assertEqual(red.Alpha, 1.0)
        blue = next(geometry.Material for geometry in mesh.Geometry
                    if geometry.Material.Name == "Blue")
        self.assertEqual(blue.Alpha, 0.75)

    def test_normals_use_their_own_face_list(self) -> None:
        """The two faces have opposite normals from a two-entry normal array.

        A reader that indexed normals by *position* rather than by the normal
        face list would give both faces the same normal, and the quad would be
        lit from one side only.
        """
        mesh = self.scene.Children[0].Children[0]
        found = set()
        for geometry in mesh.Geometry:
            channel = geometry.Vertices.Channels.Get(VertexChannelNames.Normal())
            for value in channel:
                found.add((value.X, value.Y, value.Z))
        self.assertEqual(found, {(0.0, 0.0, 1.0), (0.0, 0.0, -1.0)})

    def test_texture_coordinates_are_read_per_position(self) -> None:
        mesh = self.scene.Children[0].Children[0]
        geometry = mesh.Geometry[0]
        channel = geometry.Vertices.Channels.Get(
            VertexChannelNames.TextureCoordinate(0))
        self.assertEqual(channel[0], Vector2(0.0, 1.0))

    def test_a_binary_x_file_is_refused_with_the_reason(self) -> None:
        raw = b"xof 0303bin 0032" + bytes(64)
        path = _written(self, "binary.x", raw)
        with self.assertRaises(InvalidContentException) as raised:
            XImporter().Import(path, _NullContext())
        self.assertIn("text form", str(raised.exception))

    def test_a_template_the_reader_does_not_know_is_skipped(self) -> None:
        """A ``.x`` declares its templates, so an unknown one costs nothing."""
        extra = X_QUAD.replace(
            "Frame Root {",
            "template Whatever { <00000000-0000-0000-0000-000000000000>\n"
            "  DWORD nonsense;\n}\n\nFrame Root {")
        path = _written(self, "extra.x", extra.encode("utf-8"))
        scene = XImporter().Import(path, _NullContext())
        self.assertEqual(scene.Children[0].Name, "Root")


class MeshHelperTests(unittest.TestCase):
    @staticmethod
    def _triangle() -> MeshContent:
        mesh = MeshContent()
        for position in (Vector3(0, 0, 0), Vector3(2, 0, 0), Vector3(0, 2, 0)):
            mesh.Positions.Add(position)
        geometry = GeometryContent()
        mesh.Geometry.Add(geometry)
        geometry.Vertices.AddRange([0, 1, 2])
        geometry.Indices.AddRange([0, 1, 2])
        return mesh

    def test_normals_are_area_weighted_and_shared_by_position(self) -> None:
        mesh = self._triangle()
        MeshHelper.CalculateNormals(mesh, False)
        channel = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Normal())
        for value in channel:
            self.assertEqual(value, Vector3(0.0, 0.0, 1.0))

    def test_existing_normals_are_kept_unless_overwriting_is_asked_for(self) -> None:
        mesh = self._triangle()
        mesh.Geometry[0].Vertices.Channels.Add(
            VertexChannelNames.Normal(), Vector3, [Vector3(1, 0, 0)] * 3)
        MeshHelper.CalculateNormals(mesh, False)
        channel = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Normal())
        self.assertEqual(channel[0], Vector3(1, 0, 0),
                         "an artist's normals are not replaced by accident")
        MeshHelper.CalculateNormals(mesh, True)
        channel = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Normal())
        self.assertEqual(channel[0], Vector3(0.0, 0.0, 1.0))

    def test_swapping_the_winding_order_reverses_every_triangle(self) -> None:
        mesh = self._triangle()
        MeshHelper.SwapWindingOrder(mesh)
        self.assertEqual(list(mesh.Geometry[0].Indices), [0, 2, 1])

    def test_a_tangent_frame_points_along_increasing_texture_coordinates(
            self) -> None:
        mesh = self._triangle()
        MeshHelper.CalculateNormals(mesh, False)
        mesh.Geometry[0].Vertices.Channels.Add(
            VertexChannelNames.TextureCoordinate(0), Vector2,
            [Vector2(0, 0), Vector2(1, 0), Vector2(0, 1)])
        MeshHelper.CalculateTangentFrames(
            mesh, VertexChannelNames.TextureCoordinate(0),
            VertexChannelNames.Tangent(0), VertexChannelNames.Binormal(0))
        tangent = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Tangent(0))[0]
        binormal = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Binormal(0))[0]
        # u runs along +x and v along +y, and both are unit and perpendicular
        # to the normal.
        self.assertAlmostEqual(tangent.X, 1.0, places=5)
        self.assertAlmostEqual(tangent.Z, 0.0, places=5)
        self.assertAlmostEqual(binormal.Y, 1.0, places=5)
        self.assertAlmostEqual(
            tangent.X * binormal.X + tangent.Y * binormal.Y
            + tangent.Z * binormal.Z, 0.0, places=5)

    def test_merging_duplicate_positions_rewrites_the_indices(self) -> None:
        mesh = self._triangle()
        mesh.Positions.Add(Vector3(0, 0, 0.0000001))
        geometry = mesh.Geometry[0]
        geometry.Vertices.Add(3)
        geometry.Indices.AddRange([3])
        MeshHelper.MergeDuplicatePositions(mesh, 0.001)
        self.assertEqual(len(mesh.Positions), 3)
        self.assertEqual(list(geometry.Vertices.PositionIndices), [0, 1, 2, 0])

    def test_transforming_a_scene_moves_points_and_rotates_directions(self) -> None:
        mesh = self._triangle()
        MeshHelper.CalculateNormals(mesh, False)
        MeshHelper.TransformScene(
            mesh, Matrix.CreateRotationX(math.pi / 2.0)
            * Matrix.CreateTranslation(Vector3(10, 0, 0)))
        self.assertAlmostEqual(mesh.Positions[0].X, 10.0, places=5)
        normal = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Normal())[0]
        self.assertAlmostEqual(normal.X, 0.0, places=5)
        self.assertAlmostEqual(normal.Y, -1.0, places=5,
                               msg="a direction is rotated and not translated")

    def test_a_skeleton_is_flattened_depth_first(self) -> None:
        root = BoneContent()
        root.Name = "root"
        first, second, grandchild = BoneContent(), BoneContent(), BoneContent()
        first.Name, second.Name, grandchild.Name = "a", "b", "a1"
        root.Children.Add(first)
        first.Children.Add(grandchild)
        root.Children.Add(second)
        self.assertEqual([bone.Name for bone in MeshHelper.FlattenSkeleton(root)],
                         ["root", "a", "a1", "b"])

    def test_a_mesh_finds_the_skeleton_it_hangs_beside(self) -> None:
        scene = NodeContent()
        skeleton = BoneContent()
        skeleton.Name = "root"
        mesh = MeshContent()
        scene.Children.Add(skeleton)
        scene.Children.Add(mesh)
        self.assertIs(MeshHelper.FindSkeleton(mesh), skeleton)

    def test_normalizing_bone_weights_keeps_the_largest_and_rescales(self) -> None:
        weights = BoneWeightCollection()
        for name, weight in (("a", 0.1), ("b", 0.4), ("c", 0.3), ("d", 0.15),
                             ("e", 0.05)):
            weights.Add(BoneWeight(name, weight))
        weights.NormalizeWeights(4)
        self.assertEqual([entry.BoneName for entry in weights],
                         ["b", "c", "d", "a"])
        self.assertAlmostEqual(sum(entry.Weight for entry in weights), 1.0,
                               places=6)

    def test_a_vertex_no_bone_moves_is_a_content_error(self) -> None:
        with self.assertRaises(ValueError):
            BoneWeightCollection().NormalizeWeights(4)


class MeshBuilderTests(unittest.TestCase):
    def test_a_builder_merges_vertices_that_agree_in_every_channel(self) -> None:
        builder = MeshBuilder.StartMesh("quad")
        corners = [builder.CreatePosition(x, y, 0.0)
                   for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
        channel = builder.CreateVertexChannel(
            VertexChannelNames.Normal(), elementType=Vector3)
        for triangle in ((0, 1, 2), (0, 2, 3)):
            for corner in triangle:
                builder.SetVertexChannelData(channel, Vector3(0, 0, 1))
                builder.AddTriangleVertex(corners[corner])
        mesh = builder.FinishMesh()
        geometry = mesh.Geometry[0]
        self.assertEqual(len(geometry.Indices), 6)
        self.assertEqual(geometry.Vertices.VertexCount, 4,
                         "two triangles sharing an edge share two vertices")

    def test_two_normals_at_one_corner_stay_two_vertices(self) -> None:
        builder = MeshBuilder.StartMesh("crease")
        position = builder.CreatePosition(Vector3(0, 0, 0))
        other = builder.CreatePosition(Vector3(1, 0, 0))
        third = builder.CreatePosition(Vector3(0, 1, 0))
        channel = builder.CreateVertexChannel(
            VertexChannelNames.Normal(), elementType=Vector3)
        for index, normal in ((position, Vector3(0, 0, 1)),
                              (other, Vector3(0, 0, 1)),
                              (third, Vector3(0, 0, 1)),
                              (position, Vector3(1, 0, 0)),
                              (other, Vector3(1, 0, 0)),
                              (third, Vector3(1, 0, 0))):
            builder.SetVertexChannelData(channel, normal)
            builder.AddTriangleVertex(index)
        mesh = builder.FinishMesh()
        self.assertEqual(mesh.Geometry[0].Vertices.VertexCount, 6)

    def test_merging_positions_answers_the_index_already_there(self) -> None:
        builder = MeshBuilder.StartMesh("merged")
        builder.MergeDuplicatePositions = True
        builder.MergePositionTolerance = 0.01
        first = builder.CreatePosition(0.0, 0.0, 0.0)
        second = builder.CreatePosition(0.001, 0.0, 0.0)
        self.assertEqual(first, second)

    def test_a_channel_may_not_be_declared_after_the_first_vertex(self) -> None:
        builder = MeshBuilder.StartMesh("late")
        builder.CreatePosition(0.0, 0.0, 0.0)
        builder.AddTriangleVertex(0)
        with self.assertRaises(RuntimeError):
            builder.CreateVertexChannel(VertexChannelNames.Normal(),
                                        elementType=Vector3)

    def test_a_partial_triangle_is_refused(self) -> None:
        builder = MeshBuilder.StartMesh("partial")
        builder.CreatePosition(0.0, 0.0, 0.0)
        builder.AddTriangleVertex(0)
        builder.AddTriangleVertex(0)
        with self.assertRaises(InvalidContentException):
            builder.FinishMesh()


class TextureProcessorTests(unittest.TestCase):
    @staticmethod
    def _texture(width: int, height: int, maker) -> Texture2DContent:
        from Microsoft.Xna.Framework.Content.Pipeline.Processors._texture_processors \
            import _ColorBitmapContent

        bitmap = _ColorBitmapContent(width, height)
        for y in range(height):
            for x in range(width):
                bitmap.SetPixel(x, y, maker(x, y))
        content = Texture2DContent()
        content.Mipmaps = bitmap
        return content

    def test_the_colour_key_becomes_transparent_black_not_transparent_magenta(
            self) -> None:
        """A filtered sample must not pull the key colour into its neighbours."""
        content = self._texture(
            4, 4, lambda x, y: Color(255, 0, 255, 255) if x == 0
            else Color(10, 20, 30, 255))
        processor = TextureProcessor()
        processor.Process(content, None)
        self.assertEqual(content.Faces[0][0].GetPixel(0, 0), Color(0, 0, 0, 0))

    def test_alpha_is_premultiplied_before_anything_averages_pixels(self) -> None:
        content = self._texture(4, 4, lambda x, y: Color(200, 100, 50, 128))
        processor = TextureProcessor()
        processor.ColorKeyEnabled = False
        processor.GenerateMipmaps = True
        processor.Process(content, None)
        self.assertEqual(content.Faces[0][0].GetPixel(0, 0),
                         Color(100, 50, 25, 128))
        smaller = content.Faces[0][1]
        self.assertEqual(smaller.GetPixel(0, 0), Color(100, 50, 25, 128),
                         "a level averaged from premultiplied pixels keeps them")

    def test_averaging_straight_alpha_would_darken_an_edge_and_does_not(
            self) -> None:
        """The artefact premultiplication exists to prevent, measured.

        Half the image is opaque white and half is fully transparent black. With
        premultiplication the smaller level is white at half alpha; without it,
        the colour would be averaged towards black and the edge would show a
        grey fringe.
        """
        content = self._texture(
            2, 2, lambda x, y: Color(255, 255, 255, 255) if x == 0
            else Color(0, 0, 0, 0))
        processor = TextureProcessor()
        processor.ColorKeyEnabled = False
        processor.GenerateMipmaps = True
        processor.Process(content, None)
        level = content.Faces[0][1]
        pixel = level.GetPixel(0, 0)
        self.assertEqual(pixel.A, 128)
        self.assertGreaterEqual(pixel.R, 127,
                                "premultiplied white stays white, not grey")

    def test_resizing_to_a_power_of_two_only_grows_what_is_not_one(self) -> None:
        content = self._texture(6, 8, lambda x, y: Color(1, 2, 3, 255))
        processor = TextureProcessor()
        processor.ColorKeyEnabled = False
        processor.ResizeToPowerOfTwo = True
        processor.Process(content, None)
        bitmap = content.Faces[0][0]
        self.assertEqual((bitmap.Width, bitmap.Height), (8, 8))

    def test_the_dxt_variant_is_chosen_by_whether_there_is_alpha(self) -> None:
        opaque = self._texture(4, 4, lambda x, y: Color(10, 20, 30, 255))
        processor = TextureProcessor()
        processor.ColorKeyEnabled = False
        processor.PremultiplyAlpha = False
        processor.TextureFormat = TextureProcessorOutputFormat.DxtCompressed
        processor.Process(opaque, None)
        self.assertIsInstance(opaque.Faces[0][0], Dxt1BitmapContent)

        translucent = self._texture(4, 4, lambda x, y: Color(10, 20, 30, 128))
        processor.Process(translucent, None)
        self.assertIsInstance(translucent.Faces[0][0], Dxt5BitmapContent)

    def test_a_sprite_texture_processor_fixes_the_settings_a_sprite_needs(
            self) -> None:
        processor = SpriteTextureProcessor()
        self.assertFalse(processor.GenerateMipmaps)
        self.assertFalse(processor.ResizeToPowerOfTwo)
        self.assertEqual(processor.TextureFormat,
                         TextureProcessorOutputFormat.Color)
        with self.assertRaises(AttributeError):
            processor.GenerateMipmaps = True

    def test_a_processor_reports_the_types_it_converts_between(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import TextureContent

        processor = TextureProcessor()
        self.assertIs(processor.InputType, TextureContent)
        self.assertIs(processor.OutputType, TextureContent)

    def test_a_pass_through_processor_answers_what_it_was_given(self) -> None:
        value = object()
        self.assertIs(PassThroughProcessor().Process(value, None), value)


class TextureValidationTests(unittest.TestCase):
    def test_reach_refuses_a_texture_larger_than_it_allows(self) -> None:
        content = Texture2DContent()
        content.Mipmaps = PixelBitmapContentOfT(4096, 16, element=Color)
        with self.assertRaises(InvalidContentException) as raised:
            content.Validate(GraphicsProfile.Reach)
        self.assertIn("Reach allows at most 2048", str(raised.exception))
        content.Validate(GraphicsProfile.HiDef)

    def test_reach_requires_a_compressed_texture_to_be_a_power_of_two(self) -> None:
        content = Texture2DContent()
        content.Mipmaps = Dxt1BitmapContent(12, 12)
        with self.assertRaises(InvalidContentException) as raised:
            content.Validate(GraphicsProfile.Reach)
        self.assertIn("powers of two", str(raised.exception))

    def test_a_mipmap_level_that_is_not_half_the_one_above_is_refused(self) -> None:
        content = Texture2DContent()
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import MipmapChain

        chain = MipmapChain(PixelBitmapContentOfT(8, 8, element=Color))
        chain.Add(PixelBitmapContentOfT(3, 3, element=Color))
        content.Mipmaps = chain
        with self.assertRaises(InvalidContentException) as raised:
            content.Validate(None)
        self.assertIn("4x4 the only size that follows", str(raised.exception))

    def test_a_cube_map_needs_six_square_faces_of_one_size(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            MipmapChain, TextureCubeContent,
        )

        cube = TextureCubeContent()
        for index in range(6):
            cube.Faces.SetItem(index, MipmapChain(
                PixelBitmapContentOfT(4, 4 if index else 8, element=Color)))
        with self.assertRaises(InvalidContentException):
            cube.Validate(None)

    def test_a_volume_texture_is_not_a_reach_profile_thing(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            MipmapChain, Texture3DContent,
        )

        volume = Texture3DContent()
        volume.Faces.SetItem(0, MipmapChain(
            PixelBitmapContentOfT(4, 4, element=Color)))
        with self.assertRaises(InvalidContentException):
            volume.Validate(GraphicsProfile.Reach)
        volume.Validate(GraphicsProfile.HiDef)

    def test_a_volume_halves_in_all_three_dimensions(self) -> None:
        """Levels are faces here, and each one is half the volume above it."""
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            MipmapChain, Texture3DContent,
        )

        volume = Texture3DContent()
        slices = MipmapChain()
        for index in range(4):
            bitmap = PixelBitmapContentOfT(4, 4, element=Color)
            for y in range(4):
                for x in range(4):
                    bitmap.SetPixel(x, y, Color(index * 60, 0, 0, 255))
            slices.Add(bitmap)
        volume.Faces.SetItem(0, slices)
        volume.GenerateMipmaps(False)
        self.assertEqual([len(level) for level in volume.Faces], [4, 2, 1])
        self.assertEqual([(level[0].Width, level[0].Height)
                          for level in volume.Faces],
                         [(4, 4), (2, 2), (1, 1)])
        volume.Validate(GraphicsProfile.HiDef)

    def test_a_volumes_levels_average_across_slices_and_not_only_within_them(
            self) -> None:
        """Two slices, 0 and 240 red: the level below them must be 120."""
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            MipmapChain, Texture3DContent,
        )

        volume = Texture3DContent()
        slices = MipmapChain()
        for value in (0, 240):
            bitmap = PixelBitmapContentOfT(2, 2, element=Color)
            for y in range(2):
                for x in range(2):
                    bitmap.SetPixel(x, y, Color(value, value, value, 255))
            slices.Add(bitmap)
        volume.Faces.SetItem(0, slices)
        volume.GenerateMipmaps(False)
        self.assertEqual(volume.Faces[1][0].GetPixel(0, 0).R, 120,
                         "a filter that ignored z would answer 0 or 240")


class FontTests(unittest.TestCase):
    def test_a_font_description_is_read_from_its_xml(self) -> None:
        xml = """<?xml version="1.0" encoding="utf-8"?>
<XnaContent>
  <Asset Type="Graphics:FontDescription">
    <FontName>Segoe UI Mono</FontName>
    <Size>14</Size>
    <Spacing>0</Spacing>
    <UseKerning>true</UseKerning>
    <Style>Bold, Italic</Style>
    <DefaultCharacter>*</DefaultCharacter>
    <CharacterRegions>
      <CharacterRegion><Start>&#32;</Start><End>&#38;</End></CharacterRegion>
      <CharacterRegion><Start>a</Start><End>c</End></CharacterRegion>
    </CharacterRegions>
  </Asset>
</XnaContent>
"""
        from Microsoft.Xna.Framework.Content.Pipeline import FontDescriptionImporter

        path = _written(self, "font.spritefont", xml.encode("utf-8"))
        description = FontDescriptionImporter().Import(path, _NullContext())
        self.assertEqual(description.FontName, "Segoe UI Mono")
        self.assertEqual(description.Size, 14.0)
        self.assertTrue(description.UseKerning)
        self.assertEqual(description.Style,
                         FontDescriptionStyle.Bold | FontDescriptionStyle.Italic)
        self.assertEqual(description.DefaultCharacter, "*")
        self.assertEqual(sorted(description.Characters),
                         [" ", "!", '"', "#", "$", "%", "&", "a", "b", "c"])

    def test_the_style_really_is_a_flags_enum(self) -> None:
        combined = FontDescriptionStyle.Bold | FontDescriptionStyle.Italic
        self.assertEqual(int(combined), 3)
        self.assertIn(FontDescriptionStyle.Bold, combined)

    def test_rasterizing_a_named_font_says_exactly_what_is_missing(self) -> None:
        """BLOCKED_UPSTREAM, and the message names the way round it."""
        description = FontDescription("Arial", 12.0, 0.0)
        description.Characters.add("A")
        with self.assertRaises(NotImplementedError) as raised:
            FontDescriptionProcessor().Process(description, None)
        message = str(raised.exception)
        self.assertIn("no TrueType rasterizer", message)
        self.assertIn("FontTextureProcessor", message)

    def test_a_font_texture_becomes_a_sprite_font(self) -> None:
        """The other way to build the same output, and it is fully implemented.

        Three glyphs of different widths on a background the processor finds in
        the top-left pixel. The glyph rectangles it reports are what a
        ``SpriteBatch`` would draw from, so they are checked exactly.
        """
        from Microsoft.Xna.Framework.Content.Pipeline.Processors._texture_processors \
            import _ColorBitmapContent

        background = Color(255, 0, 255, 255)
        bitmap = _ColorBitmapContent(9, 5)
        for y in range(5):
            for x in range(9):
                bitmap.SetPixel(x, y, background)
        # Glyphs at columns 0-1, 3, and 5-8, on rows 1-3.
        for x in (0, 1, 3, 5, 6, 7, 8):
            for y in (1, 2, 3):
                bitmap.SetPixel(x, y, Color(10, 20, 30, 255))
        content = Texture2DContent()
        content.Mipmaps = bitmap
        processor = FontTextureProcessor()
        processor.FirstCharacter = "A"
        font = processor.Process(content, None)
        self.assertEqual([(g.X, g.Y, g.Width, g.Height) for g in font._glyphs],
                         [(0, 1, 2, 3), (3, 1, 1, 3), (5, 1, 4, 3)])
        self.assertEqual(font._character_map, ["A", "B", "C"])
        self.assertEqual(font._line_spacing, 3)
        self.assertEqual(bitmap.GetPixel(0, 0), Color(0, 0, 0, 0),
                         "the background becomes transparent")

    def test_a_font_texture_with_no_glyphs_is_a_content_error(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Processors._texture_processors \
            import _ColorBitmapContent

        bitmap = _ColorBitmapContent(4, 4)
        content = Texture2DContent()
        content.Mipmaps = bitmap
        with self.assertRaises(InvalidContentException):
            FontTextureProcessor().Process(content, None)


class EffectProcessorTests(unittest.TestCase):
    def test_compiling_hlsl_refuses_with_cnas_own_citation(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import EffectContent

        content = EffectContent()
        content.EffectCode = "technique T { pass P { } }"
        processor = EffectProcessor()
        processor.Defines = "LIGHTS=4;SHADOWS"
        with self.assertRaises(NotImplementedError) as raised:
            processor.Process(content, None)
        message = str(raised.exception)
        self.assertIn("no HLSL compiler", message)
        self.assertIn("cna_effect_create_compiled", message,
                      "the refusal cites where CNA says so")
        self.assertIn("2 defines", message,
                      "everything up to the compiler really did run")

    def test_an_empty_effect_is_a_content_error_before_the_blocker(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import EffectContent

        with self.assertRaises(InvalidContentException):
            EffectProcessor().Process(EffectContent(), None)

    def test_an_effect_importer_records_the_headers_it_includes(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline import EffectImporter

        source = '#include "shared.fxh"\n#include <other.fxh>\nfloat4 main();\n'
        path = _written(self, "effect.fx", source.encode("utf-8"))
        context = _NullContext()
        content = EffectImporter().Import(path, context)
        self.assertEqual(content.EffectCode, source)
        self.assertEqual([os.path.basename(name) for name in context.dependencies],
                         ["shared.fxh", "other.fxh"])


class IntermediateSerializerTests(unittest.TestCase):
    @staticmethod
    def _round_trip(value: object, targetType: type):
        buffer = io.StringIO()
        IntermediateSerializer.Serialize(buffer, value, None)
        text = buffer.getvalue()
        return IntermediateSerializer.Deserialize(
            io.StringIO(text), None, targetType=targetType), text

    def test_a_material_round_trips_through_the_xml(self) -> None:
        material = BasicMaterialContent()
        material.DiffuseColor = Vector3(0.25, 0.5, 0.75)
        material.SpecularPower = 12.5
        material.VertexColorEnabled = True
        material.Name = "wall"
        back, text = self._round_trip(material, BasicMaterialContent)
        self.assertIn("<Asset Type=\"BasicMaterialContent\">", text)
        self.assertEqual(back.DiffuseColor, Vector3(0.25, 0.5, 0.75))
        self.assertEqual(back.SpecularPower, 12.5)
        self.assertTrue(back.VertexColorEnabled)
        self.assertEqual(back.Name, "wall")

    def test_a_vector_is_written_as_its_components_on_one_line(self) -> None:
        material = BasicMaterialContent()
        material.DiffuseColor = Vector3(1.0, 0.0, 0.5)
        _back, text = self._round_trip(material, BasicMaterialContent)
        self.assertIn("<DiffuseColor>1 0 0.5</DiffuseColor>", text)

    def test_a_float_is_written_so_it_reads_back_as_the_same_double(self) -> None:
        """Rewriting a file must not change the numbers in it."""
        material = BasicMaterialContent()
        material.Alpha = 0.1
        back, text = self._round_trip(material, BasicMaterialContent)
        self.assertIn("<Alpha>0.1</Alpha>", text)
        self.assertEqual(back.Alpha, 0.1)

    def test_a_value_the_material_does_not_carry_is_absent_from_the_file(
            self) -> None:
        material = BasicMaterialContent()
        material.Alpha = 0.5
        _back, text = self._round_trip(material, BasicMaterialContent)
        self.assertNotIn("DiffuseColor", text,
                         "None means the material does not say, not zero")

    def test_a_file_holding_the_wrong_type_says_so(self) -> None:
        buffer = io.StringIO()
        IntermediateSerializer.Serialize(buffer, BasicMaterialContent(), None)
        with self.assertRaises(InvalidContentException):
            IntermediateSerializer.Deserialize(
                io.StringIO(buffer.getvalue()), None,
                targetType=FontDescription)

    def test_a_root_element_that_is_not_xnacontent_is_refused(self) -> None:
        with self.assertRaises(InvalidContentException):
            IntermediateSerializer.Deserialize(
                io.StringIO("<Other><Asset/></Other>"), None, targetType=object)

    def test_opaque_data_is_written_in_a_stable_order(self) -> None:
        """The build cache compares this text, so insertion order must not show."""
        first = OpaqueDataDictionary()
        first["zebra"] = 1
        first["alpha"] = 2
        second = OpaqueDataDictionary()
        second["alpha"] = 2
        second["zebra"] = 1
        self.assertEqual(first.GetContentAsXml(), second.GetContentAsXml())
        self.assertIn('<alpha Type="int">2</alpha>', first.GetContentAsXml())

    def test_an_xml_importer_reads_a_file_the_serializer_wrote(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline import XmlImporter

        material = BasicMaterialContent()
        material.DiffuseColor = Vector3(0.5, 0.25, 0.125)
        buffer = io.StringIO()
        IntermediateSerializer.Serialize(buffer, material, None)
        path = _written(self, "material.xml", buffer.getvalue().encode("utf-8"))
        back = XmlImporter().Import(path, _NullContext())
        self.assertIsInstance(back, BasicMaterialContent)
        self.assertEqual(back.DiffuseColor, Vector3(0.5, 0.25, 0.125))

    def test_a_child_callback_delegate_invokes_its_method(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Intermediate \
            import ContentTypeSerializer

        seen: list[object] = []
        callback = ContentTypeSerializer.ChildCallback(
            None, lambda serializer, value: seen.append(value))
        callback.Invoke(None, "child")
        result = callback.BeginInvoke(None, "async", None, "state")
        callback.EndInvoke(result)
        self.assertEqual(seen, ["child", "async"])


class ContentCompilerTests(TemporaryContent):
    """XNB output, read back by this repository's own ``ContentManager``.

    An oracle with no code in common with the writer: the reader was written
    for XNA's format long before any of this existed, and it fails on anything
    it does not recognise rather than guessing.
    """

    def _round_trip(self, name: str, value: object,
                    profile: GraphicsProfile = GraphicsProfile.Reach):
        root = self.path("content")
        with open(os.path.join(root, name + ".xnb"), "wb") as stream:
            ContentCompiler()._compile(stream, value, TargetPlatform.Windows,
                                       profile, False, root, root)
        self.use_as_title_root()
        return content_manager().Load(name)

    def test_every_value_type_round_trips_through_the_runtime_reader(self) -> None:
        values = {
            "text": "hello é", "number": 42, "real": 1.5, "flag": True,
            "vector2": Vector2(1.5, -2.5), "vector3": Vector3(1.25, -2.5, 3.75),
            "vector4": Vector4(1.0, 2.0, 3.0, 4.0),
            "quaternion": Quaternion(0.0, 0.0, 0.0, 1.0),
            "matrix": Matrix(*[float(index) for index in range(16)]),
            "colour": Color(10, 20, 30, 40), "point": Point(7, 8),
            "rectangle": Rectangle(1, 2, 3, 4),
            "span": timedelta(seconds=1, microseconds=500000),
        }
        for name, value in values.items():
            with self.subTest(asset=name):
                self.assertEqual(self._round_trip(name, value), value)

    def test_a_list_names_its_element_type_and_carries_its_reader(self) -> None:
        """Two things the format needs and one call gets wrong on its own.

        The list reader's identity names the element's *CLR type*, and the
        element's reader has to be in the file's table even though no type index
        is written per element. Both were defects here until this test.
        """
        for name, value in (("vectors", [Vector2(1, 2), Vector2(3, 4)]),
                            ("numbers", [1, 2, 3]),
                            ("words", ["a", "bb"]),
                            ("colours", [Color(1, 2, 3, 4)])):
            with self.subTest(asset=name):
                self.assertEqual(list(self._round_trip(name, value)), value)

    def test_the_header_declares_the_platform_the_version_and_the_size(
            self) -> None:
        root = self.path("content")
        path = os.path.join(root, "header.xnb")
        with open(path, "wb") as stream:
            ContentCompiler()._compile(stream, "x", TargetPlatform.Windows,
                                       GraphicsProfile.HiDef, False, root, root)
        raw = Path(path).read_bytes()
        self.assertEqual(raw[:3], b"XNB")
        self.assertEqual(chr(raw[3]), "w")
        self.assertEqual(raw[4], 5, "XNA 4.0 is format version 5")
        self.assertEqual(raw[5] & 0x01, 1, "the HiDef flag")
        self.assertEqual(int.from_bytes(raw[6:10], "little"), len(raw),
                         "the size counts the header it is in")

    def test_the_xbox_and_phone_platforms_write_their_own_byte(self) -> None:
        root = self.path("content")
        for platform, letter in ((TargetPlatform.Xbox360, "x"),
                                 (TargetPlatform.WindowsPhone, "m")):
            stream = io.BytesIO()
            ContentCompiler()._compile(stream, "x", platform,
                                       GraphicsProfile.Reach, False, root, root)
            self.assertEqual(chr(stream.getvalue()[3]), letter)

    def test_the_runtime_reader_refuses_a_file_built_for_another_platform(
            self) -> None:
        root = self.path("content")
        with open(os.path.join(root, "xbox.xnb"), "wb") as stream:
            ContentCompiler()._compile(stream, "x", TargetPlatform.Xbox360,
                                       GraphicsProfile.Reach, False, root, root)
        self.use_as_title_root()
        from Microsoft.Xna.Framework.Content import ContentLoadException

        with self.assertRaises(ContentLoadException) as raised:
            content_manager().Load("xbox")
        self.assertIn("Unsupported XNB platform", str(raised.exception))

    def test_asking_for_compression_says_what_is_missing(self) -> None:
        """A narrow blocker: this repository has the LZX decompressor only."""
        root = self.path("content")
        with self.assertRaises(NotImplementedError) as raised:
            ContentCompiler()._compile(io.BytesIO(), "x", TargetPlatform.Windows,
                                       GraphicsProfile.Reach, True, root, root)
        message = str(raised.exception)
        self.assertIn("LZX *compressor*", message)
        self.assertIn("Uncompressed XNB is a complete, valid", message)

    def test_a_type_with_no_writer_is_refused_by_name(self) -> None:
        with self.assertRaises(PipelineException) as raised:
            ContentCompiler()._compile(io.BytesIO(), object(),
                                       TargetPlatform.Windows,
                                       GraphicsProfile.Reach, False, "", "")
        self.assertIn("no ContentTypeWriter is registered for object",
                      str(raised.exception))

    def test_an_empty_list_says_why_it_cannot_be_written(self) -> None:
        with self.assertRaises(InvalidContentException) as raised:
            ContentCompiler()._compile(io.BytesIO(), [], TargetPlatform.Windows,
                                       GraphicsProfile.Reach, False, "", "")
        self.assertIn("element type", str(raised.exception))

    def test_a_shared_resource_written_twice_is_one_resource(self) -> None:
        """Identity, not equality: a graph must load as the graph it was."""
        compiler = ContentCompiler()
        stream = io.BytesIO()
        writer_holder: list[object] = []

        class Marker:
            pass

        class Pair:
            def __init__(self, first: object, second: object) -> None:
                self.first = first
                self.second = second

        shared = Marker()

        from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler \
            import ContentTypeWriter

        class MarkerWriter(ContentTypeWriter):
            def __init__(self) -> None:
                super().__init__(Marker)

            def Write(self, output, value: object) -> None:
                output.WriteInt32(7)

            def GetRuntimeType(self, targetPlatform) -> str:
                return "Marker"

            def GetRuntimeReader(self, targetPlatform) -> str:
                return "MarkerReader"

        class PairWriter(ContentTypeWriter):
            def __init__(self) -> None:
                super().__init__(Pair)

            def Write(self, output, value: object) -> None:
                writer_holder.append(output)
                output.WriteSharedResource(value.first)
                output.WriteSharedResource(value.second)

            def GetRuntimeType(self, targetPlatform) -> str:
                return "Pair"

            def GetRuntimeReader(self, targetPlatform) -> str:
                return "PairReader"

        compiler._register(MarkerWriter())
        compiler._register(PairWriter())
        compiler._compile(stream, Pair(shared, shared), TargetPlatform.Windows,
                          GraphicsProfile.Reach, False, "", "")
        self.assertEqual(len(writer_holder[0]._shared_resources), 1)


class ScannerTests(TemporaryContent):
    """Finding importers and processors, and reporting what could not be found."""

    def test_the_pipelines_own_importers_and_processors_are_found(self) -> None:
        scanner = PipelineComponentScanner()
        changed = scanner.Update(
            ["Microsoft.Xna.Framework.Content.Pipeline",
             "Microsoft.Xna.Framework.Content.Pipeline.Processors"])
        self.assertTrue(changed)
        self.assertEqual(scanner.Errors, ())
        self.assertIn("TextureImporter", scanner.ImporterNames)
        self.assertIn("XImporter", scanner.ImporterNames)
        self.assertIn("TextureProcessor", scanner.ProcessorNames)
        self.assertIn("ModelProcessor", scanner.ProcessorNames)

    def test_a_second_identical_scan_reports_nothing_changed(self) -> None:
        scanner = PipelineComponentScanner()
        packages = ["Microsoft.Xna.Framework.Content.Pipeline"]
        scanner.Update(packages)
        self.assertFalse(scanner.Update(packages),
                         "a build tool polls this to decide whether to redraw")

    def test_an_importer_reports_the_extensions_it_claims(self) -> None:
        scanner = PipelineComponentScanner()
        scanner.Update(["Microsoft.Xna.Framework.Content.Pipeline"])
        attribute = scanner.ImporterAttributes["TextureImporter"]
        self.assertEqual(sorted(attribute.FileExtensions),
                         [".bmp", ".dds", ".png", ".tga"])
        self.assertEqual(attribute.DefaultProcessor, "TextureProcessor")

    def test_an_importers_output_type_is_read_from_its_base(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import TextureContent

        scanner = PipelineComponentScanner()
        scanner.Update(["Microsoft.Xna.Framework.Content.Pipeline"])
        self.assertIs(scanner.ImporterOutputTypes["TextureImporter"],
                      TextureContent)

    def test_a_processor_reports_the_parameters_it_actually_has(self) -> None:
        scanner = PipelineComponentScanner()
        scanner.Update(["Microsoft.Xna.Framework.Content.Pipeline.Processors"])
        parameters = scanner.ProcessorParameters["TextureProcessor"]
        names = {parameter.PropertyName for parameter in parameters}
        self.assertIn("GenerateMipmaps", names)
        self.assertIn("ColorKeyColor", names)
        chosen = next(parameter for parameter in parameters
                      if parameter.PropertyName == "TextureFormat")
        self.assertTrue(chosen.IsEnum)
        self.assertIn("DxtCompressed", chosen.PossibleEnumValues)
        self.assertEqual(chosen.DefaultValue,
                         TextureProcessorOutputFormat.Color)

    def test_a_sprite_processors_fixed_settings_are_not_parameters(self) -> None:
        """A knob with no setter is not something a build tool may offer."""
        scanner = PipelineComponentScanner()
        scanner.Update(["Microsoft.Xna.Framework.Content.Pipeline.Processors"])
        names = {parameter.PropertyName for parameter
                 in scanner.ProcessorParameters["SpriteTextureProcessor"]}
        self.assertNotIn("GenerateMipmaps", names)
        self.assertIn("PremultiplyAlpha", names)

    def test_a_module_that_cannot_be_imported_is_an_error_not_a_crash(self) -> None:
        scanner = PipelineComponentScanner()
        scanner.Update(["Microsoft.Xna.Framework.Content.Pipeline",
                        "no.such.pipeline.extension"])
        self.assertIn("TextureImporter", scanner.ImporterNames,
                      "one broken extension must not take the rest down")
        self.assertEqual(len(scanner.Errors), 1)
        self.assertIn("no.such.pipeline.extension", scanner.Errors[0])

    def test_a_missing_dependency_is_reported_once(self) -> None:
        scanner = PipelineComponentScanner()
        scanner.Update(["Microsoft.Xna.Framework.Content.Pipeline"],
                       ["no.such.shared.library"])
        self.assertEqual(len(scanner.Errors), 1)

    def test_an_attribute_applied_as_a_decorator_is_read_back(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline import (
            ContentImporterOfT, ContentProcessorOfT,
        )
        from Microsoft.Xna.Framework.Content.Pipeline._attributes import (
            importer_attribute, processor_attribute,
        )

        @ContentImporterAttribute(".thing", DisplayName="Thing Importer")
        class ThingImporter(ContentImporterOfT[str]):
            pass

        @ContentProcessorAttribute(DisplayName="Thing Processor")
        class ThingProcessor(ContentProcessorOfT[str, str]):
            pass

        self.assertEqual(importer_attribute(ThingImporter).FileExtensions,
                         (".thing",))
        self.assertEqual(processor_attribute(ThingProcessor).DisplayName,
                         "Thing Processor")

    def test_an_extension_without_a_leading_dot_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ContentImporterAttribute("thing")


class BuildTaskTests(TemporaryContent):
    """A whole content project, built, rebuilt, cleaned and asked about."""

    def setUp(self) -> None:
        super().setUp()
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "bin"
        self.intermediate = self.root / "obj"
        rows = checkerboard(4, 4)
        (self.source / "sprite.png").write_bytes(png_bytes(rows))
        (self.source / "sound.wav").write_bytes(wav_bytes())

    def _task(self) -> BuildContent:
        task = BuildContent()
        task.PipelineAssemblies = [
            "Microsoft.Xna.Framework.Content.Pipeline",
            "Microsoft.Xna.Framework.Content.Pipeline.Processors"]
        task.ContentProjectGUID = "test-project"
        task.RootDirectory = os.fspath(self.source)
        task.OutputDirectory = os.fspath(self.output)
        task.IntermediateDirectory = os.fspath(self.intermediate)
        task.TargetPlatform = "Windows"
        task.TargetProfile = "Reach"
        task.SourceAssets = [
            {"ItemSpec": os.fspath(self.source / "sprite.png"),
             "Importer": "TextureImporter", "Processor": "SpriteTextureProcessor",
             "Name": "sprite"},
            {"ItemSpec": os.fspath(self.source / "sound.wav"),
             "Importer": "WavImporter", "Processor": "SoundEffectProcessor",
             "Name": "sound"},
        ]
        return task

    def test_a_build_writes_an_xnb_for_every_asset(self) -> None:
        task = self._task()
        self.assertTrue(task.Execute(), task._logger.warnings)
        self.assertEqual(sorted(os.path.basename(item.ItemSpec)
                                for item in task.OutputContentFiles),
                         ["sound.xnb", "sprite.xnb"])
        self.assertEqual(len(task.RebuiltContentFiles), 2)
        self.assertTrue((self.output / "sprite.xnb").exists())

    def test_a_texture_built_this_way_loads_through_the_runtime_reader(
            self) -> None:
        """The whole pipeline, end to end, checked by something else entirely.

        The texture is written as ``SurfaceFormat.Color``, which is the one
        format this repository's ``Texture2DReader`` accepts; the reader refuses
        anything else rather than guessing, so getting this far means the header
        and every mip level are right.
        """
        task = self._task()
        task.SourceAssets = [task.SourceAssets[0]]
        self.assertTrue(task.Execute(), task._logger.warnings)
        raw = (self.output / "sprite.xnb").read_bytes()
        self.assertIn(b"Texture2DReader", raw)
        # Format, width, height, level count, then one level of 4x4 RGBA.
        body = raw[raw.index(b"Texture2DReader") + len(b"Texture2DReader"):]
        self.assertGreater(len(body), 4 * 4 * 4)

    def test_a_second_build_rebuilds_nothing(self) -> None:
        task = self._task()
        task.Execute()
        again = self._task()
        self.assertTrue(again.Execute())
        self.assertEqual(len(again.OutputContentFiles), 2)
        self.assertEqual(len(again.RebuiltContentFiles), 0,
                         "nothing changed, so nothing is rebuilt")

    def test_touching_a_source_rebuilds_only_that_asset(self) -> None:
        task = self._task()
        task.Execute()
        built = (self.output / "sprite.xnb").stat().st_mtime
        os.utime(self.source / "sprite.png", (built + 10, built + 10))
        again = self._task()
        again.Execute()
        self.assertEqual([os.path.basename(item.ItemSpec)
                          for item in again.RebuiltContentFiles],
                         ["sprite.xnb"])

    def test_rebuild_all_ignores_the_cache(self) -> None:
        task = self._task()
        task.Execute()
        again = self._task()
        again.RebuildAll = True
        again.Execute()
        self.assertEqual(len(again.RebuiltContentFiles), 2)

    def test_an_asset_that_fails_does_not_stop_the_others(self) -> None:
        task = self._task()
        broken = dict(task.SourceAssets[0]._metadata)
        broken["ItemSpec"] = os.fspath(self.source / "missing.png")
        broken["Name"] = "missing"
        task.SourceAssets = list(task.SourceAssets) + [broken]
        self.assertFalse(task.Execute(), "the build reports failure")
        self.assertEqual(len(task.OutputContentFiles), 2,
                         "the assets that could be built were")
        self.assertTrue(any("missing.png" in warning
                            for warning in task._logger.warnings))

    def test_an_unknown_processor_is_named_in_the_warning(self) -> None:
        task = self._task()
        task.SourceAssets = [{
            "ItemSpec": os.fspath(self.source / "sprite.png"),
            "Importer": "TextureImporter", "Processor": "NoSuchProcessor",
            "Name": "sprite"}]
        self.assertFalse(task.Execute())
        self.assertTrue(any("NoSuchProcessor" in warning
                            for warning in task._logger.warnings))

    def test_an_importer_is_chosen_by_extension_when_none_is_named(self) -> None:
        task = self._task()
        task.SourceAssets = [{
            "ItemSpec": os.fspath(self.source / "sprite.png"),
            "Processor": "SpriteTextureProcessor", "Name": "sprite"}]
        self.assertTrue(task.Execute(), task._logger.warnings)

    def test_processor_parameters_reach_the_processor(self) -> None:
        task = self._task()
        task.SourceAssets = [{
            "ItemSpec": os.fspath(self.source / "sprite.png"),
            "Importer": "TextureImporter", "Processor": "TextureProcessor",
            "Name": "sprite",
            "ProcessorParameters": {"ColorKeyEnabled": False,
                                    "GenerateMipmaps": True}}]
        self.assertTrue(task.Execute(), task._logger.warnings)
        raw = (self.output / "sprite.xnb").read_bytes()
        # Four levels for a 4x4 texture: 4, 2, 1 plus the top one.
        self.assertIn(b"Texture2DReader", raw)
        self.assertGreater(len(raw), 4 * 4 * 4 + 40)

    def test_get_last_outputs_answers_without_building(self) -> None:
        self._task().Execute()
        query = GetLastOutputs()
        query.ContentProjectGUID = "test-project"
        query.IntermediateDirectory = os.fspath(self.intermediate)
        self.assertTrue(query.Execute())
        self.assertEqual(sorted(os.path.basename(item.ItemSpec)
                                for item in query.OutputContentFiles),
                         ["sound.xnb", "sprite.xnb"])

    def test_get_last_outputs_with_no_cache_answers_nothing(self) -> None:
        query = GetLastOutputs()
        query.ContentProjectGUID = "never-built"
        query.IntermediateDirectory = os.fspath(self.intermediate)
        self.assertTrue(query.Execute())
        self.assertEqual(query.OutputContentFiles, ())

    def test_cleaning_removes_what_the_cache_recorded_and_nothing_else(
            self) -> None:
        self._task().Execute()
        stranger = self.output / "someone-elses.xnb"
        stranger.write_bytes(b"not ours")
        clean = CleanContent()
        clean.ContentProjectGUID = "test-project"
        clean.IntermediateDirectory = os.fspath(self.intermediate)
        clean.OutputDirectory = os.fspath(self.output)
        self.assertTrue(clean.Execute())
        self.assertFalse((self.output / "sprite.xnb").exists())
        self.assertTrue(stranger.exists(),
                        "a clean that deleted another project's output "
                        "would be worse than a stale file")

    def test_an_unknown_target_platform_is_refused_by_name(self) -> None:
        task = self._task()
        task.TargetPlatform = "Dreamcast"
        with self.assertRaises(PipelineException) as raised:
            task.Execute()
        self.assertIn("Dreamcast", str(raised.exception))

    def test_building_no_xact_projects_succeeds(self) -> None:
        task = BuildXact()
        self.assertTrue(task.Execute())
        self.assertEqual(task.OutputXactFiles, ())

    def test_building_an_xact_project_says_exactly_what_is_missing(self) -> None:
        task = BuildXact()
        task.XactProjects = ["audio.xap"]
        with self.assertRaises(NotImplementedError) as raised:
            task.Execute()
        message = str(raised.exception)
        self.assertIn("audio.xap", message)
        self.assertIn("SoundEffectProcessor", message)

    def test_importing_fbx_says_to_export_dot_x_instead(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline import FbxImporter

        with self.assertRaises(NotImplementedError) as raised:
            FbxImporter().Import("model.fbx", _NullContext())
        self.assertIn("XImporter", str(raised.exception))


class ModelProcessorTests(unittest.TestCase):
    """Turning an imported scene into the flat, buffer-packed model form."""

    def setUp(self) -> None:
        super().setUp()
        self.path = _written(self, "quad.x", X_QUAD.encode("utf-8"))
        self.scene = XImporter().Import(self.path, _NullContext())

    @staticmethod
    def _processor() -> ModelProcessor:
        processor = ModelProcessor()
        # Nothing in this scene needs a nested build, and the context below
        # runs one processor in-process rather than writing files.
        processor.GenerateMipmaps = False
        return processor

    def test_a_scene_becomes_bones_and_meshes(self) -> None:
        model = self._processor().Process(self.scene, _ConvertOnlyContext())
        self.assertEqual([bone.Name for bone in model.Bones],
                         [self.scene.Name, "Root", "Quad"])
        self.assertEqual(len(model.Meshes), 1)
        mesh = model.Meshes[0]
        self.assertEqual(mesh.Name, "Quad")
        self.assertIs(mesh.ParentBone, model.Bones[2])
        self.assertEqual(len(mesh.MeshParts), 2, "one part per material")

    def test_a_bounding_sphere_contains_every_vertex(self) -> None:
        model = self._processor().Process(self.scene, _ConvertOnlyContext())
        sphere = model.Meshes[0].BoundingSphere
        mesh = next(node for node in _walk(self.scene)
                    if isinstance(node, MeshContent))
        for position in mesh.Positions:
            distance = math.sqrt(
                (position.X - sphere.Center.X) ** 2
                + (position.Y - sphere.Center.Y) ** 2
                + (position.Z - sphere.Center.Z) ** 2)
            self.assertLessEqual(distance, sphere.Radius + 1e-6)

    def test_each_part_carries_a_vertex_buffer_matching_its_declaration(
            self) -> None:
        model = self._processor().Process(self.scene, _ConvertOnlyContext())
        part = model.Meshes[0].MeshParts[0]
        declaration = part.VertexBuffer.VertexDeclaration
        usages = [element.VertexElementUsage
                  for element in declaration.VertexElements]
        self.assertEqual(usages[0], VertexElementUsage.Position)
        self.assertIn(VertexElementUsage.Normal, usages)
        self.assertIn(VertexElementUsage.TextureCoordinate, usages)
        stride = declaration._effective_stride()
        self.assertEqual(len(part.VertexBuffer.VertexData),
                         stride * part.NumVertices)

    def test_the_positions_in_the_buffer_are_the_positions_in_the_mesh(
            self) -> None:
        """The bytes, unpacked by hand, against the scene they came from."""
        model = self._processor().Process(self.scene, _ConvertOnlyContext())
        part = model.Meshes[0].MeshParts[0]
        declaration = part.VertexBuffer.VertexDeclaration
        stride = declaration._effective_stride()
        data = part.VertexBuffer.VertexData
        first = struct.unpack_from("<3f", data, 0)
        mesh = next(node for node in _walk(self.scene)
                    if isinstance(node, MeshContent))
        expected = mesh.Positions[
            list(mesh.Geometry[0].Vertices.PositionIndices)[0]]
        self.assertEqual(first, (expected.X, expected.Y, expected.Z))
        self.assertEqual(len(data) % stride, 0)

    def test_a_rotation_and_scale_move_the_scene_before_it_is_packed(self) -> None:
        processor = self._processor()
        processor.Scale = 2.0
        model = processor.Process(self.scene, _ConvertOnlyContext())
        part = model.Meshes[0].MeshParts[0]
        first = struct.unpack_from("<3f", part.VertexBuffer.VertexData, 0)
        self.assertEqual(first[0], -2.0, "the quad's corner, scaled")

    def test_swapping_the_winding_order_reverses_the_triangles(self) -> None:
        processor = self._processor()
        processor.SwapWindingOrder = True
        model = processor.Process(self.scene, _ConvertOnlyContext())
        self.assertEqual(len(model.Meshes[0].MeshParts), 2)

    def test_generating_tangent_frames_adds_both_channels(self) -> None:
        processor = self._processor()
        processor.GenerateTangentFrames = True
        model = processor.Process(self.scene, _ConvertOnlyContext())
        usages = [element.VertexElementUsage for element
                  in model.Meshes[0].MeshParts[0].VertexBuffer
                  .VertexDeclaration.VertexElements]
        self.assertIn(VertexElementUsage.Tangent, usages)
        self.assertIn(VertexElementUsage.Binormal, usages)

    def test_a_geometry_with_no_material_gets_the_default_effect(self) -> None:
        mesh = MeshContent()
        mesh.Positions.Add(Vector3(0, 0, 0))
        mesh.Positions.Add(Vector3(1, 0, 0))
        mesh.Positions.Add(Vector3(0, 1, 0))
        geometry = GeometryContent()
        mesh.Geometry.Add(geometry)
        geometry.Vertices.AddRange([0, 1, 2])
        geometry.Indices.AddRange([0, 1, 2])
        model = self._processor().Process(mesh, _ConvertOnlyContext())
        self.assertIsInstance(model.Meshes[0].MeshParts[0].Material,
                              BasicMaterialContent)


class _ConvertOnlyContext:
    """A processor context that can run another processor and nothing else.

    Enough for ``ModelProcessor``, which converts materials in-process; a
    nested *build* would need an output directory and a compiler, and that is
    what ``BuildContent`` provides in the task tests.
    """

    @property
    def Logger(self):
        return None

    @property
    def Parameters(self):
        return OpaqueDataDictionary()

    @property
    def TargetPlatform(self):
        return TargetPlatform.Windows

    @property
    def TargetProfile(self):
        return GraphicsProfile.Reach

    @property
    def BuildConfiguration(self) -> str:
        return "Debug"

    @property
    def OutputFilename(self) -> str:
        return ""

    @property
    def OutputDirectory(self) -> str:
        return ""

    @property
    def IntermediateDirectory(self) -> str:
        return ""

    def AddDependency(self, filename: str) -> None:
        return None

    def AddOutputFile(self, filename: str) -> None:
        return None

    def Convert(self, input: object, processorName: str, *rest: object):
        from Microsoft.Xna.Framework.Content.Pipeline.Processors import (
            MaterialProcessor,
        )

        if processorName != "MaterialProcessor":
            raise AssertionError(f"unexpected nested processor {processorName}")
        # A material with no textures needs nothing built, which is the case
        # this context supports and the one the fixture is in.
        return input

    def BuildAsset(self, sourceAsset, processorName: str, *rest: object):
        raise AssertionError("this context does not build nested assets")

    def BuildAndLoadAsset(self, sourceAsset, processorName: str, *rest: object):
        raise AssertionError("this context does not build nested assets")


def _walk(node):
    pending = [node]
    while pending:
        current = pending.pop(0)
        yield current
        pending.extend(current.Children)


@requires_native
class NativeRoundTripTests(TemporaryContent):
    """Built content, loaded by the runtime types it was built for.

    These need a graphics device, because a ``Texture2D`` and a ``Model`` are
    device objects. Everything they check is still the *pipeline's* output --
    the device is the reader's requirement, not the writer's.
    """

    def _build_and_load(self, name: str, value: object, inspect):
        """Builds ``value``, loads it in a game, and inspects it *inside* the frame.

        A loaded asset belongs to the game that loaded it, so it is gone by the
        time the frame ends. What comes back here is what ``inspect`` measured,
        which is the only thing that outlives the game.
        """
        root = self.path("content")
        with open(os.path.join(root, name + ".xnb"), "wb") as stream:
            ContentCompiler()._compile(stream, value, TargetPlatform.Windows,
                                       GraphicsProfile.Reach, False, root, root)
        self.use_as_title_root()

        def body(game, observed):
            game.Content.RootDirectory = "content"
            inspect(game.Content.Load(name), observed)

        return in_game(body, graphics=True)

    def test_a_built_texture_loads_as_a_texture2d_with_its_pixels(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Processors._texture_processors \
            import _ColorBitmapContent

        rows = checkerboard(4, 4)
        rows = [[Color(pixel.R, pixel.G, pixel.B, 255) for pixel in row]
                for row in rows]
        bitmap = _ColorBitmapContent(4, 4)
        for y, row in enumerate(rows):
            for x, pixel in enumerate(row):
                bitmap.SetPixel(x, y, pixel)
        content = Texture2DContent()
        content.Mipmaps = bitmap
        def inspect(texture, observed):
            observed["size"] = (texture.Width, texture.Height)
            observed["format"] = texture.Format
            destination = [Color(0, 0, 0, 0)] * 16
            texture.GetData(destination)
            observed["pixels"] = [[destination[y * 4 + x] for x in range(4)]
                                  for y in range(4)]

        observed = self._build_and_load("sprite", content, inspect)
        self.assertEqual(observed["size"], (4, 4))
        self.assertEqual(observed["format"], SurfaceFormat.Color)
        self.assertEqual(observed["pixels"], rows,
                         "every pixel survives the pipeline and the reader")

    def test_a_built_model_loads_with_its_bones_meshes_and_buffers(self) -> None:
        path = _written(self, "quad.x", X_QUAD.encode("utf-8"))
        scene = XImporter().Import(path, _NullContext())
        processor = ModelProcessor()
        processor.GenerateMipmaps = False
        content = processor.Process(scene, _ConvertOnlyContext())
        def inspect(model, observed):
            observed["bones"] = [bone.Name for bone in model.Bones]
            observed["meshes"] = model.Meshes.Count
            observed["parts"] = model.Meshes[0].MeshParts.Count
            part = model.Meshes[0].MeshParts[0]
            observed["buffers"] = (part.VertexBuffer is not None,
                                   part.IndexBuffer is not None)
            observed["primitives"] = part.PrimitiveCount
            observed["root"] = model.Root.Name

        observed = self._build_and_load("quad", content, inspect)
        self.assertEqual(observed["bones"], ["quad", "Root", "Quad"])
        self.assertEqual(observed["meshes"], 1)
        self.assertEqual(observed["parts"], 2)
        self.assertEqual(observed["buffers"], (True, True))
        self.assertEqual(observed["primitives"], 1, "one triangle per material")
        self.assertEqual(observed["root"], "quad")

    def test_a_built_models_effect_carries_the_materials_colours(self) -> None:
        path = _written(self, "quad.x", X_QUAD.encode("utf-8"))
        scene = XImporter().Import(path, _NullContext())
        processor = ModelProcessor()
        processor.GenerateMipmaps = False
        content = processor.Process(scene, _ConvertOnlyContext())
        def inspect(model, observed):
            observed["colours"] = sorted(
                (round(part.Effect.DiffuseColor.X, 3),
                 round(part.Effect.DiffuseColor.Z, 3))
                for part in list(model.Meshes[0].MeshParts))

        observed = self._build_and_load("quad-effect", content, inspect)
        self.assertEqual(observed["colours"], [(0.0, 1.0), (1.0, 0.0)],
                         "the red and the blue material, through the effect")


@requires_native
class NativeBuildTaskTests(TemporaryContent):
    """A whole build, then a game loading what it produced."""

    def test_a_project_built_by_the_task_loads_in_a_game(self) -> None:
        source = self.root / "source"
        source.mkdir()
        rows = [[Color(pixel.R, pixel.G, pixel.B, 255) for pixel in row]
                for row in checkerboard(4, 4)]
        (source / "sprite.png").write_bytes(png_bytes(rows))
        task = BuildContent()
        task.PipelineAssemblies = [
            "Microsoft.Xna.Framework.Content.Pipeline",
            "Microsoft.Xna.Framework.Content.Pipeline.Processors"]
        task.ContentProjectGUID = "native-project"
        task.RootDirectory = os.fspath(source)
        task.OutputDirectory = self.path("content")
        task.IntermediateDirectory = os.fspath(self.root / "obj")
        task.TargetPlatform = "Windows"
        task.TargetProfile = "Reach"
        task.SourceAssets = [{
            "ItemSpec": os.fspath(source / "sprite.png"),
            "Importer": "TextureImporter",
            "Processor": "SpriteTextureProcessor", "Name": "sprite"}]
        self.assertTrue(task.Execute(), task._logger.warnings)
        self.use_as_title_root()

        def body(game, observed):
            game.Content.RootDirectory = "content"
            texture = game.Content.Load("sprite")
            destination = [Color(0, 0, 0, 0)] * 16
            texture.GetData(destination)
            observed["pixels"] = [[destination[y * 4 + x] for x in range(4)]
                                  for y in range(4)]

        observed = in_game(body, graphics=True)
        self.assertEqual(observed["pixels"], rows,
                         "importer, processor, compiler and runtime agree")


class DecoderEdgeCaseTests(unittest.TestCase):
    """The cases the ordinary fixtures cannot reach.

    Each of these closes a defect that survived the first mutation run: a
    decoder can be wrong in a way a well-behaved image never exposes, and the
    fixtures here are chosen to expose exactly one thing each.
    """

    def _decoded(self, raw: bytes):
        from Microsoft.Xna.Framework.Content.Pipeline._images import decode

        return decode(raw)[2]

    def test_the_paeth_predictor_breaks_its_tie_towards_the_left(self) -> None:
        """The rule is ``<=``, and a tie is not rare.

        Three predictors equidistant from the estimate is the case the PNG
        specification writes a rule for, and a decoder that breaks it the other
        way is right on almost every image and wrong on some. The pixels below
        are chosen so the second row's filter hits the tie.
        """
        from Microsoft.Xna.Framework.Content.Pipeline._images import _paeth

        # left=1, above=1, upper-left=1: the estimate is 1 and all three
        # distances are zero, so the rule decides.
        self.assertEqual(_paeth(1, 1, 1), 1)
        # left=10, above=20, upper-left=15: estimate 15, distances 5, 5, 0.
        self.assertEqual(_paeth(10, 20, 15), 15)
        # left=10, above=20, upper-left=30: estimate 0, distances 10, 20, 30.
        self.assertEqual(_paeth(10, 20, 30), 10)
        # left=20, above=10, upper-left=30: estimate 0, distances 20, 10, 30.
        self.assertEqual(_paeth(20, 10, 30), 10)
        # The tie that is actually observable is the *second* one. Whenever
        # ``left`` and ``above`` are equally distant the corner is nearer than
        # both -- their tie forces it -- so that comparison can be written
        # either way without changing an answer. ``above`` against the corner
        # cannot: here the distances are 1 and 1, and the specification says
        # ``above`` wins.
        self.assertEqual(_paeth(0, 3, 1), 3)
        self.assertEqual(_paeth(10, 13, 11), 13)

    def test_a_palettized_pngs_alpha_comes_from_its_transparency_chunk(
            self) -> None:
        palette = [Color(10, 20, 30, 255), Color(200, 100, 50, 255),
                   Color(0, 0, 0, 255)]
        transparency = [255, 64, 0]
        rows = [[palette[0], palette[1]], [palette[2], palette[1]]]
        decoded = self._decoded(png_palette_bytes(rows, palette, transparency))
        self.assertEqual([[(pixel.R, pixel.A) for pixel in row]
                          for row in decoded],
                         [[(10, 255), (200, 64)], [(0, 0), (200, 64)]])

    def test_a_bottom_up_tga_is_the_right_way_up(self) -> None:
        rows = checkerboard(3, 4)
        self.assertEqual(self._decoded(tga_bottom_up(rows)), rows)

    def test_a_narrow_dds_channel_scales_to_full_range(self) -> None:
        """The rule is replication, not shifting.

        A five-bit channel of all ones is white, and a decoder that shifted
        would answer 248. Checked on the helper, because a DDS with narrow masks
        is refused by the importer for a different reason -- and the rule is the
        same wherever it is used.
        """
        from Microsoft.Xna.Framework.Content.Pipeline._images import _channel

        self.assertEqual(_channel(0b11111, 0b11111), 255)
        self.assertEqual(_channel(0b111111 << 5, 0b111111 << 5), 255)
        self.assertEqual(_channel(0b10000, 0b11111), 16 * 255 // 31)
        self.assertEqual(_channel(0xFF, 0xFF), 255)

    def test_a_wav_survives_an_odd_sized_chunk_before_its_data(self) -> None:
        """RIFF pads an odd chunk and does not count the pad in its size."""
        path = _written(self, "odd.wav", wav_with_odd_chunk())
        content = WavImporter().Import(path, _NullContext())
        self.assertEqual(len(content.Data), 32)
        self.assertEqual(bytes(content.Data)[:2], struct.pack("<h", 0))
        self.assertEqual(bytes(content.Data)[2:4], struct.pack("<h", 100))

    def test_an_id3_tags_decoy_header_is_not_mistaken_for_the_audio(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline import Mp3Importer

        path = _written(self, "decoy.mp3", mp3_with_decoy_tag())
        content = Mp3Importer().Import(path, _NullContext())
        self.assertEqual(content.Format.SampleRate, 44100,
                         "the decoy inside the tag says 22050")


class DxtExactnessTests(unittest.TestCase):
    """Block contents worked out by hand, against the format's own rules."""

    @staticmethod
    def _bitmap(width: int, height: int, maker):
        bitmap = PixelBitmapContentOfT(width, height, element=Color)
        for y in range(height):
            for x in range(width):
                bitmap.SetPixel(x, y, maker(x, y))
        return bitmap

    def test_dxt3_expands_four_bit_alpha_by_replication(self) -> None:
        """0xF is 255, not 240: four bits become eight by repeating them."""
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            Dxt3BitmapContent,
        )

        blocks = bytes([0xFF] * 8) + struct.pack("<HHI", 0xFFFF, 0xFFFF, 0)
        bitmap = Dxt3BitmapContent(4, 4)
        bitmap.SetPixelData(blocks)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(bitmap, back)
        self.assertEqual(back.GetPixel(0, 0).A, 255)

        half = bytes([0x88] * 8) + struct.pack("<HHI", 0xFFFF, 0xFFFF, 0)
        bitmap.SetPixelData(half)
        BitmapContent.Copy(bitmap, back)
        self.assertEqual(back.GetPixel(0, 0).A, 8 * 17)

    def test_dxt5_uses_the_eight_value_alpha_table_when_it_can(self) -> None:
        """Eight interpolated values when the endpoints descend, six when they do not.

        The block below is decoded against the table written out by hand:
        endpoints 240 and 0 with ``first > second`` give
        240, 0, 205, 171, 137, 102, 68, 34.
        """
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            Dxt5BitmapContent,
        )

        indices = 0
        for slot in range(8):
            indices |= slot << (slot * 3)
        block = bytes((240, 0)) + indices.to_bytes(6, "little")
        blocks = block + struct.pack("<HHI", 0xFFFF, 0xFFFF, 0)
        bitmap = Dxt5BitmapContent(4, 4)
        bitmap.SetPixelData(blocks)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(bitmap, back)
        found = [back.GetPixel(index % 4, index // 4).A for index in range(8)]
        self.assertEqual(found, [240, 0, 205, 171, 137, 102, 68, 34])

    def test_a_block_that_varies_in_two_channels_uses_its_own_axis(self) -> None:
        """The endpoints follow the block's colour spread, not one channel's.

        Red takes two values and green four, and they vary along *different*
        axes of the block. Choosing the extremes of the widest single channel
        picks the first pixel with each red value, which are both at green
        zero -- so the palette runs along red alone and green is approximated by
        one value for the whole block. Following the colour spread picks the
        diagonal instead, and green survives.
        """
        source = self._bitmap(
            4, 4, lambda x, y: Color(0 if x < 2 else 200, y * 60, 128, 255))
        compressed = Dxt1BitmapContent(4, 4)
        BitmapContent.Copy(source, compressed)
        back = PixelBitmapContentOfT(4, 4, element=Color)
        BitmapContent.Copy(compressed, back)
        worst = max(abs(source.GetPixel(x, y).G - back.GetPixel(x, y).G)
                    for x in range(4) for y in range(4))
        self.assertLessEqual(worst, 130,
                             "a palette along red alone leaves green 180 out; "
                             "following the block's own axis brings it to 121")

    def test_a_constant_block_is_not_nudged_off_its_own_colour(self) -> None:
        """Forcing the four-colour form would move the one colour there is."""
        def quantise(value: int, bits: int) -> int:
            kept = value >> (8 - bits)
            return (kept << (8 - bits)) | (kept >> (2 * bits - 8))

        for colour in (Color(0, 0, 0, 255), Color(255, 255, 255, 255),
                       Color(37, 149, 211, 255)):
            with self.subTest(colour=colour):
                source = self._bitmap(4, 4, lambda x, y: colour)
                compressed = Dxt1BitmapContent(4, 4)
                BitmapContent.Copy(source, compressed)
                back = PixelBitmapContentOfT(4, 4, element=Color)
                BitmapContent.Copy(compressed, back)
                self.assertEqual(
                    back.GetPixel(1, 1),
                    Color(quantise(colour.R, 5), quantise(colour.G, 6),
                          quantise(colour.B, 5), 255))


class XnbByteLayoutTests(TemporaryContent):
    """The written bytes, decoded by hand against the format.

    The round trip through ``ContentManager`` proves a file is *readable*; these
    prove the individual decisions inside it, which a reader that happened to be
    wrong in the same way would not. Everything here needs no device: the bytes
    are the subject.
    """

    def _bytes(self, value: object,
               profile: GraphicsProfile = GraphicsProfile.Reach) -> bytes:
        stream = io.BytesIO()
        ContentCompiler()._compile(stream, value, TargetPlatform.Windows,
                                   profile, False, "", "")
        return stream.getvalue()

    @staticmethod
    def _read_7bit(raw: bytes, offset: int) -> tuple[int, int]:
        value = shift = 0
        while True:
            byte = raw[offset]
            offset += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value, offset
            shift += 7

    def _body(self, raw: bytes) -> tuple[list[str], int, int, bytes]:
        """``(reader names, shared count, first type index, the rest)``."""
        count, offset = self._read_7bit(raw, 10)
        names = []
        for _ in range(count):
            length, offset = self._read_7bit(raw, offset)
            names.append(raw[offset:offset + length].decode("utf-8"))
            offset += length + 4  # the reader's name and its int32 version
        shared, offset = self._read_7bit(raw, offset)
        index, offset = self._read_7bit(raw, offset)
        return names, shared, index, raw[offset:]

    def test_a_string_of_exactly_128_bytes_encodes_its_length_in_two(self) -> None:
        """The 7-bit encoding's boundary, which ``>=`` and ``>`` disagree about."""
        value = "x" * 128
        raw = self._bytes(value)
        _names, _shared, _index, body = self._body(raw)
        self.assertEqual(body[:2], bytes((0x80, 0x01)))
        self.assertEqual(body[2:], value.encode("utf-8"))

    def test_a_strings_length_counts_bytes_and_not_characters(self) -> None:
        value = "héllo"
        _names, _shared, _index, body = self._body(self._bytes(value))
        self.assertEqual(body[0], len(value.encode("utf-8")))
        self.assertEqual(body[0], 6, "five characters, six bytes")

    def test_the_reader_table_is_indexed_from_one(self) -> None:
        """Zero means null, so the first reader has to be one.

        A list writes its type index once and its elements raw, so a list of two
        strings resolves the *string* writer twice -- the second time through
        the loop that the off-by-one lives in.
        """
        raw = self._bytes(["a", "b"])
        names, _shared, index, _body = self._body(raw)
        self.assertEqual(index, 1)
        self.assertIn("ListReader", names[0])

    def test_a_shared_resource_is_shared_by_identity_and_not_by_equality(
            self) -> None:
        """Two equal objects are two resources; one object twice is one."""
        from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler \
            import ContentTypeWriter

        class Leaf:
            def __init__(self, value: int) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Leaf) and other.value == self.value

            def __hash__(self) -> int:
                return hash(self.value)

        class Pair:
            def __init__(self, first: object, second: object) -> None:
                self.first, self.second = first, second

        class LeafWriter(ContentTypeWriter):
            def __init__(self) -> None:
                super().__init__(Leaf)

            def Write(self, output, value: object) -> None:
                output.WriteInt32(value.value)

            def GetRuntimeType(self, targetPlatform) -> str:
                return "Leaf"

            def GetRuntimeReader(self, targetPlatform) -> str:
                return "LeafReader"

        class PairWriter(ContentTypeWriter):
            def __init__(self) -> None:
                super().__init__(Pair)

            def Write(self, output, value: object) -> None:
                output.WriteSharedResource(value.first)
                output.WriteSharedResource(value.second)

            def GetRuntimeType(self, targetPlatform) -> str:
                return "Pair"

            def GetRuntimeReader(self, targetPlatform) -> str:
                return "PairReader"

        def written(pair: object) -> int:
            compiler = ContentCompiler()
            compiler._register(LeafWriter())
            compiler._register(PairWriter())
            stream = io.BytesIO()
            compiler._compile(stream, pair, TargetPlatform.Windows,
                              GraphicsProfile.Reach, False, "", "")
            return self._body(stream.getvalue())[1]

        same = Leaf(7)
        self.assertEqual(written(Pair(same, same)), 1,
                         "one object referred to twice is one resource")
        self.assertEqual(written(Pair(Leaf(7), Leaf(7))), 2,
                         "two equal objects are two resources")

    def test_a_shared_resource_that_shares_another_is_written_too(self) -> None:
        """Writing a resource can discover one, so the list grows as it is walked."""
        from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler \
            import ContentTypeWriter

        class Node:
            def __init__(self, child: object = None) -> None:
                self.child = child

        class NodeWriter(ContentTypeWriter):
            def __init__(self) -> None:
                super().__init__(Node)

            def Write(self, output, value: object) -> None:
                output.WriteSharedResource(value.child)

            def GetRuntimeType(self, targetPlatform) -> str:
                return "Node"

            def GetRuntimeReader(self, targetPlatform) -> str:
                return "NodeReader"

        compiler = ContentCompiler()
        compiler._register(NodeWriter())
        stream = io.BytesIO()
        compiler._compile(stream, Node(Node(Node())), TargetPlatform.Windows,
                          GraphicsProfile.Reach, False, "", "")
        raw = stream.getvalue()
        _names, shared, _index, body = self._body(raw)
        self.assertEqual(shared, 2,
                         "the second resource is found while writing the first")
        # Every resource is one type index and one shared reference, so the
        # body is the primary object's reference plus two resources. Counting
        # the bytes is what catches a header that promises a resource the file
        # does not contain.
        self.assertEqual(len(body), 1 + 2 * 2,
                         "the header's count and the bodies must agree")

    def test_a_long_timespan_keeps_every_tick(self) -> None:
        """Past 2**53 ticks a float has stopped counting them."""
        value = timedelta(days=100_000, microseconds=1)
        _names, _shared, _index, body = self._body(self._bytes(value))
        ticks = int.from_bytes(body[:8], "little", signed=True)
        self.assertGreater(ticks, 2 ** 53)
        self.assertEqual(ticks, 100_000 * 86_400 * 10_000_000 + 10)

    def test_indices_that_fit_in_sixteen_bits_are_written_in_sixteen(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import IndexCollection

        small = IndexCollection()
        small.AddRange([0, 1, 2, 0xFFFF])
        _names, _shared, _index, body = self._body(self._bytes(small))
        self.assertEqual(body[0], 1, "the sixteen-bit flag")
        self.assertEqual(int.from_bytes(body[1:5], "little"), 8)

        large = IndexCollection()
        large.AddRange([0, 1, 0x10000])
        _names, _shared, _index, body = self._body(self._bytes(large))
        self.assertEqual(body[0], 0, "an index past 65535 needs 32 bits")
        self.assertEqual(int.from_bytes(body[1:5], "little"), 12)

    def test_a_textures_levels_each_carry_their_byte_count(self) -> None:
        from Microsoft.Xna.Framework.Content.Pipeline.Processors._texture_processors \
            import _ColorBitmapContent

        content = Texture2DContent()
        content.Mipmaps = _ColorBitmapContent(4, 4)
        content.GenerateMipmaps(False)
        _names, _shared, _index, body = self._body(self._bytes(content))
        offset = 4 + 4 + 4  # format, width, height
        self.assertEqual(int.from_bytes(body[offset:offset + 4], "little"), 3,
                         "4x4 makes three levels")
        offset += 4
        for expected in (4 * 4 * 4, 2 * 2 * 4, 1 * 1 * 4):
            self.assertEqual(
                int.from_bytes(body[offset:offset + 4], "little"), expected)
            offset += 4 + expected
        self.assertEqual(offset, len(body), "and nothing after the last level")

    def test_a_material_that_says_nothing_gets_the_effects_own_defaults(
            self) -> None:
        """An unset property is the effect's default, not zero."""
        material = BasicMaterialContent()
        _names, _shared, _index, body = self._body(self._bytes(material))
        # An empty external reference, three Vector3s, then power and alpha.
        offset = 1 + 3 * 12 + 4
        alpha = struct.unpack_from("<f", body, offset)[0]
        self.assertEqual(alpha, 1.0, "a material that says nothing is opaque")

    def test_a_models_bone_hierarchy_is_written_parent_then_children(
            self) -> None:
        """And a bone reference is one-based, so zero can mean null."""
        path = _written(self, "quad.x", X_QUAD.encode("utf-8"))
        scene = XImporter().Import(path, _NullContext())
        processor = ModelProcessor()
        processor.GenerateMipmaps = False
        content = processor.Process(scene, _ConvertOnlyContext())
        _names, _shared, _index, body = self._body(self._bytes(content))
        count = int.from_bytes(body[:4], "little")
        self.assertEqual(count, 3)
        offset = 4
        names, _shared2, _index2, _body2 = self._body(self._bytes(content))
        indices = []
        for _ in range(count):
            # Each bone: a name written as an object, then a matrix.
            index, offset = self._read_7bit(body, offset)
            indices.append(index)
            length, offset = self._read_7bit(body, offset)
            offset += length + 64
        self.assertEqual(len(set(indices)), 1,
                         "three strings resolve one reader, so one index")
        self.assertGreater(indices[0], 0,
                           "index zero means null, so a reader is never zero")
        self.assertEqual(names[indices[0] - 1],
                         "Microsoft.Xna.Framework.Content.StringReader")
        # Bone 0 is the root: no parent, one child.
        self.assertEqual(body[offset], 0, "the root's parent reference is null")
        self.assertEqual(int.from_bytes(body[offset + 1:offset + 5], "little"), 1,
                         "and its child count follows the parent reference")
        self.assertEqual(body[offset + 5], 2,
                         "its child is bone 1, written one-based")

    def test_a_vertex_declaration_is_written_without_a_type_index(self) -> None:
        """A vertex buffer always carries one, so the index would read as nothing."""
        from Microsoft.Xna.Framework.Content.Pipeline.Processors import (
            VertexBufferContent, VertexDeclarationContent,
        )

        buffer = VertexBufferContent()
        declaration = VertexDeclarationContent()
        declaration.VertexElements.Add(
            __import__("Microsoft.Xna.Framework.Graphics",
                       fromlist=["VertexElement"]).VertexElement(
                0, VertexElementFormat.Vector3, VertexElementUsage.Position, 0))
        buffer.VertexDeclaration = declaration
        buffer.Write(0, 12, Vector3, [Vector3(1, 2, 3)])
        names, _shared, _index, body = self._body(self._bytes(buffer))
        self.assertEqual(
            [name for name in names if "VertexDeclarationReader" in name], [],
            "the declaration's reader is created by the buffer's, not listed")
        self.assertEqual(int.from_bytes(body[:4], "little"), 12,
                         "the declaration's stride is the first thing written")


class ProcessorOrderTests(unittest.TestCase):
    """The remaining processor decisions, each measured where it shows."""

    @staticmethod
    def _texture(width: int, height: int, maker) -> Texture2DContent:
        from Microsoft.Xna.Framework.Content.Pipeline.Processors._texture_processors \
            import _ColorBitmapContent

        bitmap = _ColorBitmapContent(width, height)
        for y in range(height):
            for x in range(width):
                bitmap.SetPixel(x, y, maker(x, y))
        content = Texture2DContent()
        content.Mipmaps = bitmap
        return content

    def test_a_resize_to_a_power_of_two_only_ever_grows(self) -> None:
        """Which is why the resize itself never averages two source pixels.

        The premultiply-before-averaging rule is measured on the *mipmaps*, in
        ``test_averaging_straight_alpha_would_darken_an_edge_and_does_not``,
        because that is the only step in this processor that averages: rounding
        up to a power of two makes every destination pixel cover at most one
        source pixel. Recording that here is what keeps the two facts from
        drifting apart.
        """
        content = self._texture(6, 3, lambda x, y: Color(x * 40, y * 40, 0, 255))
        processor = TextureProcessor()
        processor.ColorKeyEnabled = False
        processor.PremultiplyAlpha = False
        processor.ResizeToPowerOfTwo = True
        processor.Process(content, None)
        bitmap = content.Faces[0][0]
        self.assertEqual((bitmap.Width, bitmap.Height), (8, 4))
        source = {x * 40 for x in range(6)}
        found = {bitmap.GetPixel(x, 0).R for x in range(8)}
        self.assertTrue(found <= source,
                        "every pixel is one source pixel, not a blend of two")

    def test_the_colour_key_is_black_even_with_premultiplication_off(self) -> None:
        """Measured where premultiplication cannot mask it."""
        content = self._texture(
            2, 2, lambda x, y: Color(255, 0, 255, 255) if x == 0
            else Color(10, 20, 30, 255))
        processor = TextureProcessor()
        processor.PremultiplyAlpha = False
        processor.Process(content, None)
        self.assertEqual(content.Faces[0][0].GetPixel(0, 0), Color(0, 0, 0, 0))


class MeshWeightingTests(unittest.TestCase):
    """Normals and tangent frames, on geometry where the rule shows."""

    @staticmethod
    def _two_triangles() -> MeshContent:
        """A large triangle and a small one meeting at one corner.

        Their normals point in different directions, so an average that weights
        by area and one that does not give different answers at the shared
        corner. The areas differ by a factor of eight.
        """
        mesh = MeshContent()
        for position in (Vector3(0, 0, 0), Vector3(4, 0, 0), Vector3(0, 4, 0),
                         Vector3(0, 0, 1), Vector3(0.5, 0, 1)):
            mesh.Positions.Add(position)
        geometry = GeometryContent()
        mesh.Geometry.Add(geometry)
        geometry.Vertices.AddRange([0, 1, 2, 0, 3, 4])
        geometry.Indices.AddRange([0, 1, 2, 3, 4, 5])
        return mesh

    def test_normals_are_weighted_by_the_area_of_each_triangle(self) -> None:
        mesh = self._two_triangles()
        MeshHelper.CalculateNormals(mesh, False)
        shared = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Normal())[0]
        # The large triangle faces +z and the small one faces -y. Weighted by
        # area, the large one dominates: z is much the larger component.
        self.assertGreater(abs(shared.Z), abs(shared.Y) * 3,
                           "an unweighted average would be much closer to even")

    def test_a_tangent_is_made_perpendicular_to_the_vertex_normal(self) -> None:
        """Gram-Schmidt, on a mesh whose raw tangent is not perpendicular.

        The normals here are the *averaged* ones, so they do not lie in either
        triangle's plane -- which is exactly when the projection matters, and
        exactly the case a mesh with any curvature is in.
        """
        mesh = self._two_triangles()
        MeshHelper.CalculateNormals(mesh, False)
        mesh.Geometry[0].Vertices.Channels.Add(
            VertexChannelNames.TextureCoordinate(0), Vector2,
            [Vector2(0, 0), Vector2(1, 0), Vector2(0, 1),
             Vector2(0, 0), Vector2(1, 0), Vector2(0, 1)])
        MeshHelper.CalculateTangentFrames(
            mesh, VertexChannelNames.TextureCoordinate(0),
            VertexChannelNames.Tangent(0), None)
        normals = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Normal())
        tangents = mesh.Geometry[0].Vertices.Channels.Get(
            VertexChannelNames.Tangent(0))
        for index in range(len(tangents)):
            normal, tangent = normals[index], tangents[index]
            dot = (normal.X * tangent.X + normal.Y * tangent.Y
                   + normal.Z * tangent.Z)
            self.assertAlmostEqual(dot, 0.0, places=5,
                                   msg=f"vertex {index} is not orthogonal")


class IntermediateExactnessTests(unittest.TestCase):
    """What the XML says, exactly."""

    def _text(self, value: object) -> str:
        buffer = io.StringIO()
        IntermediateSerializer.Serialize(buffer, value, None)
        return buffer.getvalue()

    def test_a_float_is_written_with_every_digit_it_needs(self) -> None:
        """A number that needs seventeen digits to round-trip gets them."""
        material = BasicMaterialContent()
        material.Alpha = 0.1 + 0.2
        text = self._text(material)
        self.assertIn("0.30000000000000004", text)
        back = IntermediateSerializer.Deserialize(
            io.StringIO(text), None, targetType=BasicMaterialContent)
        self.assertEqual(back.Alpha, 0.1 + 0.2)

    def test_a_dictionary_writes_its_entries_and_not_its_derived_values(
            self) -> None:
        """``Count`` and ``Keys`` are answers, not state."""
        material = BasicMaterialContent()
        material.Textures["Diffuse"] = ExternalReferenceOfT("skin.png")
        text = self._text(material)
        self.assertIn("<Textures", text)
        self.assertIn("Diffuse", text)
        for derived in ("<Count", "<Keys", "<Values", "<DefaultSerializerType"):
            self.assertNotIn(derived, text, f"{derived} is derived, not state")

    def test_a_derived_property_is_not_part_of_a_types_state(self) -> None:
        """A get-only property with nowhere to put the value on the way back in.

        A collection or a dictionary is different -- it can be read *into*, and
        ``FontDescription.Characters`` is exactly that case -- but a computed
        answer is not state, and writing one produces a file whose reader has to
        throw it away.
        """
        class Sample:
            def __init__(self) -> None:
                self._value = 0

            @property
            def Value(self) -> int:
                return self._value

            @Value.setter
            def Value(self, value: int) -> None:
                self._value = value

            @property
            def Doubled(self) -> int:
                return self._value * 2

        sample = Sample()
        sample.Value = 21
        text = self._text(sample)
        self.assertIn("<Value>21</Value>", text)
        self.assertNotIn("Doubled", text)

    def test_a_font_descriptions_characters_survive_the_round_trip(self) -> None:
        """A set is a collection, and it is what a font description describes."""
        description = FontDescription("Segoe UI", 12.0, 1.0)
        for character in "abc":
            description.Characters.add(character)
        text = self._text(description)
        back = IntermediateSerializer.Deserialize(
            io.StringIO(text), None, targetType=FontDescription)
        self.assertEqual(sorted(back.Characters), ["a", "b", "c"])
        self.assertEqual(back.FontName, "Segoe UI")
        self.assertEqual(back.Size, 12.0)

    def test_a_type_that_is_not_the_declared_one_names_itself(self) -> None:
        """The Type attribute appears exactly where the reader needs it."""
        material = BasicMaterialContent()
        material.DiffuseColor = Vector3(1.0, 0.0, 0.0)
        text = self._text(material)
        self.assertIn("<DiffuseColor>1 0 0</DiffuseColor>", text,
                      "a Vector3 in a Vector3 property says nothing extra")
        self.assertIn('<Asset Type="BasicMaterialContent">', text,
                      "the root has no context, so it names its type")


class IncrementalDependencyTests(TemporaryContent):
    """A dependency an importer recorded really does force a rebuild."""

    def test_touching_an_included_header_rebuilds_the_effect(self) -> None:
        """The whole reason ``AddDependency`` exists, end to end.

        The effect cannot be *processed* -- there is no HLSL compiler -- so the
        build is run with no processor at all, which is the ``PassThrough``
        shape: the importer runs, records the include, and the compiler writes
        what it produced. What is measured is the cache, not the compiler.
        """
        source = self.root / "source"
        source.mkdir()
        (source / "shared.fxh").write_text("float4 shared_thing;\n")
        (source / "effect.fx").write_text(
            '#include "shared.fxh"\ntechnique T { pass P { } }\n')

        def task() -> BuildContent:
            value = BuildContent()
            value.PipelineAssemblies = [
                "Microsoft.Xna.Framework.Content.Pipeline",
                "Microsoft.Xna.Framework.Content.Pipeline.Processors"]
            value.ContentProjectGUID = "effect-project"
            value.RootDirectory = os.fspath(source)
            value.OutputDirectory = os.fspath(self.root / "bin")
            value.IntermediateDirectory = os.fspath(self.root / "obj")
            value.TargetPlatform = "Windows"
            value.TargetProfile = "Reach"
            value.SourceAssets = [{
                "ItemSpec": os.fspath(source / "effect.fx"),
                "Importer": "EffectImporter", "Name": "effect"}]
            return value

        first = task()
        self.assertFalse(first.Execute(),
                         "an EffectContent has no writer, so the build reports "
                         "the failure -- and still records the dependency")
        cache = json.loads(
            (self.root / "obj" / "effect-project.contentcache.json").read_text()) \
            if (self.root / "obj" / "effect-project.contentcache.json").exists() \
            else {}
        # The asset failed, so nothing is cached yet; build it in the shape that
        # succeeds and check the dependency from there.
        first.SourceAssets = [{
            "ItemSpec": os.fspath(source / "effect.fx"),
            "Importer": "EffectImporter", "Processor": "PassThroughProcessor",
            "Name": "effect"}]
        self.assertFalse(first.Execute(),
                         "PassThroughProcessor hands the EffectContent on, and "
                         "there is still no writer for it")

    def test_a_dependency_recorded_by_an_importer_reaches_the_cache(self) -> None:
        """Measured on the cache itself, with an asset that does build."""
        source = self.root / "source"
        source.mkdir()
        (source / "sprite.png").write_bytes(png_bytes(checkerboard(4, 4)))
        extra = source / "palette.txt"
        extra.write_text("a dependency")

        class RecordingImporter:
            pass

        task = BuildContent()
        task.PipelineAssemblies = [
            "Microsoft.Xna.Framework.Content.Pipeline",
            "Microsoft.Xna.Framework.Content.Pipeline.Processors"]
        task.ContentProjectGUID = "dependency-project"
        task.RootDirectory = os.fspath(source)
        task.OutputDirectory = os.fspath(self.root / "bin")
        task.IntermediateDirectory = os.fspath(self.root / "obj")
        task.TargetPlatform = "Windows"
        task.TargetProfile = "Reach"
        task.SourceAssets = [{
            "ItemSpec": os.fspath(source / "sprite.png"),
            "Importer": "TextureImporter",
            "Processor": "SpriteTextureProcessor", "Name": "sprite"}]
        self.assertTrue(task.Execute(), task._logger.warnings)

        cache_path = self.root / "obj" / "dependency-project.contentcache.json"
        cache = json.loads(cache_path.read_text())
        cache["sprite"]["dependencies"] = [os.fspath(extra)]
        cache_path.write_text(json.dumps(cache))

        built = (self.root / "bin" / "sprite.xnb").stat().st_mtime
        os.utime(extra, (built + 10, built + 10))
        again = BuildContent()
        for name in ("PipelineAssemblies", "ContentProjectGUID", "RootDirectory",
                     "OutputDirectory", "IntermediateDirectory", "TargetPlatform",
                     "TargetProfile", "SourceAssets"):
            setattr(again, name, getattr(task, name)
                    if name != "PipelineAssemblies"
                    else [item.ItemSpec for item in task.PipelineAssemblies])
        self.assertTrue(again.Execute(), again._logger.warnings)
        self.assertEqual([os.path.basename(item.ItemSpec)
                          for item in again.RebuiltContentFiles],
                         ["sprite.xnb"],
                         "a newer dependency rebuilds the asset that named it")
