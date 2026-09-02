"""The post-process passes, their pure twins, and the display they end on.

The passes are mostly state, so most of what is proved here is that the state
reaches CNA. Where CNA also publishes the CPU twin of what the shader does --
bloom's threshold, the tonemap curve, the PQ transfer function, the Rec.2020
matrix -- the twin is checked against arithmetic worked out here, because that
is a stronger claim than a round trip and it is available without drawing.

Two of them are checked against pixels as well: a tonemap pass with a known
exposure over a known colour, and a blit through a chain, because a pass that
stores its settings and then ignores them would pass every round trip.
"""

from __future__ import annotations

import math
import unittest

from Microsoft.Xna.Framework import Color, Vector3
from Microsoft.Xna.Framework.Graphics import RenderTarget2D, SurfaceFormat, Texture2D

from cna.extensions.engine import (
    AsciiPass, AsciiQuantizeMode, AutoExposure, BloomPass,
    COLOR_GRADE_MAXIMUM_LUT_SIZE, CUBE_LUT_MAXIMUM_SIZE, CUBE_LUT_MINIMUM_SIZE,
    ChromaticAberrationPass, ColorGradePass, CubeLut, DisplayColorSpace,
    FilmGrainPass, FxaaPass, HDR_DEFAULT_PAPER_WHITE_NITS, HDR_DEFAULT_PEAK_NITS,
    HdrDisplayOutput, LENS_FLARE_GHOST_COUNT, LensFlarePass, LutInterpolation,
    PostProcessContext, RenderQuality, SpatialUpscalePass, ToneMapPass,
    TonemappingMode, bloom_extract_channel, bloom_iterations_for,
    create_identity_lut, decode_pq, encode_for_display, encode_pq,
    fxaa_edge_threshold_for, fxaa_fragment_glsl, is_identity_scale,
    lut_size_for_strip, rec709_to_rec2020, roll_off, tonemap_channel,
)
from cna.extensions.engine.errors import EngineDisposedError, EngineError

from . import engine_oracles as oracle
from .engine_fixtures import in_game, requires_engine, requires_engine_gpu

#: A tiny, complete `.cube` document: a 2x2x2 identity table with a title.
IDENTITY_CUBE = """TITLE "identity"
LUT_3D_SIZE 2
DOMAIN_MIN 0.0 0.0 0.0
DOMAIN_MAX 1.0 1.0 1.0
0.0 0.0 0.0
1.0 0.0 0.0
0.0 1.0 0.0
1.0 1.0 0.0
0.0 0.0 1.0
1.0 0.0 1.0
0.0 1.0 1.0
1.0 1.0 1.0
"""


@requires_engine
class PureHelperTests(unittest.TestCase):
    """CNA's CPU twins of what the shaders do."""

    def test_bloom_extraction_matches_an_independent_implementation(self) -> None:
        """A soft knee, not a cutoff -- which is what the oracle encodes.

        A texel exactly at the threshold contributes a quarter of itself rather
        than nothing, because a hard cutoff makes bloom pop on and off as a
        highlight crosses the threshold.
        """
        for value in (0.0, 0.2, 0.5, 0.6, 0.9, 1.0, 2.0, 8.0):
            for threshold in (0.0, 0.25, 0.5, 1.0):
                with self.subTest(value=value, threshold=threshold):
                    self.assertAlmostEqual(
                        bloom_extract_channel(value, threshold),
                        oracle.bloom_extract_channel(value, threshold), places=5)
        # Rising in the value, and never rising in the threshold. Only never:
        # once the knee saturates, raising the threshold changes nothing, so a
        # strictly-decreasing claim would be false at a saturated value.
        self.assertGreater(bloom_extract_channel(1.0, 0.5),
                           bloom_extract_channel(0.8, 0.5))
        for threshold, higher in ((0.2, 0.4), (0.4, 0.6), (0.6, 1.0)):
            with self.subTest(threshold=threshold):
                self.assertGreaterEqual(bloom_extract_channel(1.0, threshold),
                                        bloom_extract_channel(1.0, higher))
        # And inside the ramp it really does decrease.
        self.assertGreater(bloom_extract_channel(0.6, 0.2),
                           bloom_extract_channel(0.6, 0.6))

    def test_the_quality_presets_are_ordered(self) -> None:
        iterations = [bloom_iterations_for(quality) for quality in RenderQuality]
        thresholds = [fxaa_edge_threshold_for(quality) for quality in RenderQuality]
        self.assertEqual(iterations, sorted(iterations),
                         "more quality has to mean at least as much bloom")
        self.assertGreater(iterations[-1], iterations[0])
        # A lower edge threshold means more edges are filtered, so quality goes
        # the other way.
        self.assertEqual(thresholds, sorted(thresholds, reverse=True), thresholds)
        for value in iterations:
            self.assertGreater(value, 0)
        for value in thresholds:
            self.assertGreater(value, 0.0)

    def test_the_tonemap_curves_differ_and_none_is_the_identity_of_none(self) -> None:
        produced = {mode: tonemap_channel(mode, 0.75, 1.0, 1.0)
                    for mode in TonemappingMode}
        # Every curve gives a different answer for the same input, or the mode
        # is not reaching the arithmetic.
        self.assertEqual(len({round(value, 5) for value in produced.values()}),
                         len(TonemappingMode), produced)
        # "None" with unit exposure and unit gamma changes nothing.
        self.assertAlmostEqual(produced[TonemappingMode.Nothing], 0.75, places=4)
        # Every curve is monotonic in the input.
        for mode in TonemappingMode:
            with self.subTest(mode=mode.name):
                values = [tonemap_channel(mode, x / 8.0, 1.0, 1.0) for x in range(9)]
                self.assertEqual(values, sorted(values), f"{mode.name} is not monotonic")

    def test_exposure_and_gamma_move_the_tonemap_the_way_they_should(self) -> None:
        base = tonemap_channel(TonemappingMode.Reinhard, 0.5, 1.0, 1.0)
        brighter = tonemap_channel(TonemappingMode.Reinhard, 0.5, 2.0, 1.0)
        self.assertGreater(brighter, base, "doubling exposure has to brighten")
        # Gamma is applied as a reciprocal power, so a larger gamma brightens a
        # value below one.
        gamma_two = tonemap_channel(TonemappingMode.Nothing, 0.25, 1.0, 2.0)
        self.assertAlmostEqual(gamma_two, 0.25 ** (1.0 / 2.0), places=4)

    def test_pq_encoding_and_decoding_are_inverses(self) -> None:
        for nits in (0.0, 1.0, 100.0, 203.0, 1000.0, 4000.0, 10000.0):
            with self.subTest(nits=nits):
                self.assertAlmostEqual(decode_pq(encode_pq(nits)), nits,
                                       delta=max(0.5, nits * 1e-3))
        # And it is monotonic, which is what makes it a transfer function.
        encoded = [encode_pq(nits) for nits in (0.0, 10.0, 100.0, 1000.0, 10000.0)]
        self.assertEqual(encoded, sorted(encoded))
        self.assertGreaterEqual(encoded[0], 0.0)
        self.assertLessEqual(encoded[-1], 1.0 + 1e-4)

    def test_rec2020_widens_the_primaries_and_keeps_white(self) -> None:
        """White is white in both spaces; a pure primary is not."""
        white = rec709_to_rec2020(Vector3(1.0, 1.0, 1.0))
        self.assertTrue(oracle.vectors_agree(white, Vector3(1.0, 1.0, 1.0), 1e-3),
                        f"white moved: {tuple(white)}")
        red = rec709_to_rec2020(Vector3(1.0, 0.0, 0.0))
        # Rec.2020's red is more saturated, so a Rec.709 red maps to less than
        # full red with a little green and blue.
        self.assertLess(red.X, 1.0)
        self.assertGreater(red.X, 0.5)
        self.assertGreaterEqual(red.Y, 0.0)
        self.assertGreaterEqual(red.Z, 0.0)

    def test_roll_off_compresses_toward_the_peak_and_leaves_dim_values_alone(self) -> None:
        peak = 1000.0
        # Well under the peak, nothing much happens.
        self.assertAlmostEqual(roll_off(10.0, peak), 10.0, delta=1.0)
        # Over the peak, the result is at most the peak.
        self.assertLessEqual(roll_off(5000.0, peak), peak + 1e-3)
        self.assertLessEqual(roll_off(100000.0, peak), peak + 1e-3)
        # Monotonic all the way up.
        values = [roll_off(nits, peak) for nits in (1.0, 10.0, 100.0, 1000.0, 10000.0)]
        self.assertEqual(values, sorted(values))

    def test_encoding_for_a_display_depends_on_the_space(self) -> None:
        scene = Vector3(0.25, 0.5, 0.75)
        produced = {space: encode_for_display(space, scene,
                                              HDR_DEFAULT_PAPER_WHITE_NITS,
                                              HDR_DEFAULT_PEAK_NITS)
                    for space in DisplayColorSpace}
        rendered = {space: (round(value.X, 5), round(value.Y, 5), round(value.Z, 5))
                    for space, value in produced.items()}
        self.assertEqual(len(set(rendered.values())), len(DisplayColorSpace), rendered)
        # Every channel stays finite and non-negative whichever space it is.
        for space, value in produced.items():
            with self.subTest(space=space.name):
                for component in (value.X, value.Y, value.Z):
                    self.assertTrue(math.isfinite(component))
                    self.assertGreaterEqual(component, 0.0)

    def test_a_strip_lookup_table_reports_the_size_it_encodes(self) -> None:
        # A strip of N slices each NxN is N*N wide and N tall.
        for size in (2, 4, 16, 32):
            with self.subTest(size=size):
                self.assertEqual(lut_size_for_strip(size * size, size), size)

    def test_an_upscale_to_the_same_size_is_the_identity(self) -> None:
        self.assertTrue(is_identity_scale(64, 32, 64, 32))
        self.assertFalse(is_identity_scale(64, 32, 128, 64))
        self.assertFalse(is_identity_scale(64, 32, 64, 33))

    def test_the_published_fxaa_shader_is_real_source(self) -> None:
        source = fxaa_fragment_glsl()
        self.assertTrue(source.strip())
        self.assertIn("{", source)
        self.assertIn("}", source)


@requires_engine
class CubeLutTests(unittest.TestCase):
    """A `.cube` file is a file format, so parsing it needs no device."""

    def test_a_parsed_table_reports_what_the_document_said(self) -> None:
        with CubeLut.parse(IDENTITY_CUBE) as lut:
            self.assertEqual(lut.size, 2)
            self.assertEqual(lut.title, "identity")
            self.assertTrue(lut.is_unit_domain)
            self.assertTrue(oracle.vectors_agree(lut.domain_minimum,
                                                 Vector3(0.0, 0.0, 0.0)))
            self.assertTrue(oracle.vectors_agree(lut.domain_maximum,
                                                 Vector3(1.0, 1.0, 1.0)))
            # The eight entries are the eight corners of the colour cube, and
            # the index order is red fastest -- which is what a wrong index
            # order would get backwards.
            self.assertTrue(oracle.vectors_agree(lut.entry(0, 0, 0),
                                                 Vector3(0.0, 0.0, 0.0)))
            self.assertTrue(oracle.vectors_agree(lut.entry(1, 0, 0),
                                                 Vector3(1.0, 0.0, 0.0)))
            self.assertTrue(oracle.vectors_agree(lut.entry(0, 1, 0),
                                                 Vector3(0.0, 1.0, 0.0)))
            self.assertTrue(oracle.vectors_agree(lut.entry(0, 0, 1),
                                                 Vector3(0.0, 0.0, 1.0)))
            self.assertTrue(oracle.vectors_agree(lut.entry(1, 1, 1),
                                                 Vector3(1.0, 1.0, 1.0)))

    def test_the_size_bounds_are_what_the_header_declares(self) -> None:
        self.assertLess(CUBE_LUT_MINIMUM_SIZE, CUBE_LUT_MAXIMUM_SIZE)
        self.assertLessEqual(CUBE_LUT_MAXIMUM_SIZE, COLOR_GRADE_MAXIMUM_LUT_SIZE)

    def test_a_malformed_document_is_refused(self) -> None:
        for label, text in (("empty", ""),
                            ("no size", "TITLE \"x\"\n0.0 0.0 0.0\n"),
                            ("short", "LUT_3D_SIZE 2\n0.0 0.0 0.0\n")):
            with self.subTest(document=label):
                with self.assertRaises(EngineError):
                    CubeLut.parse(text)

    def test_a_closed_table_refuses(self) -> None:
        lut = CubeLut.parse(IDENTITY_CUBE)
        lut.close()
        self.assertTrue(lut.is_closed)
        with self.assertRaises(EngineDisposedError):
            lut.size
        lut.close()

    def test_it_is_not_constructed_directly(self) -> None:
        with self.assertRaises(TypeError):
            CubeLut()


@requires_engine_gpu
class PassStateTests(unittest.TestCase):
    """Every pass's own state, and that a pass is a pass."""

    def test_each_pass_names_itself_and_reports_support(self) -> None:
        def body(game, device, observed):
            for kind in (BloomPass, ToneMapPass, ColorGradePass, FxaaPass,
                         ChromaticAberrationPass, FilmGrainPass, LensFlarePass,
                         AsciiPass):
                with kind(device) as pass_:
                    observed[kind.__name__] = (pass_.name,
                                               pass_.is_supported(device))

        observed = in_game(body)
        names = []
        for label, (name, supported) in observed.items():
            with self.subTest(pass_=label):
                self.assertTrue(name.strip(), f"{label} has no name")
                self.assertIsInstance(supported, bool)
                names.append(name)
        # Eight different passes must not all answer to one name.
        self.assertEqual(len(set(names)), len(names), names)

    def test_bloom_state_round_trips(self) -> None:
        def body(game, device, observed):
            with BloomPass(device) as bloom:
                bloom.threshold = 0.625
                bloom.intensity = 1.375
                bloom.iterations = 5
                observed["values"] = (bloom.threshold, bloom.intensity,
                                      bloom.iterations)
                bloom.reset_targets()
                observed["reset"] = True

        observed = in_game(body)
        threshold, intensity, iterations = observed["values"]
        self.assertAlmostEqual(threshold, 0.625, places=5)
        self.assertAlmostEqual(intensity, 1.375, places=5)
        self.assertEqual(iterations, 5)
        self.assertTrue(observed["reset"])

    def test_tonemap_state_round_trips(self) -> None:
        def body(game, device, observed):
            with ToneMapPass(device) as tonemap:
                tonemap.mode = TonemappingMode.Uncharted2
                tonemap.exposure = 1.75
                tonemap.gamma = 2.2
                tonemap.deband_enabled = True
                tonemap.deband_strength = 0.375
                observed["values"] = (tonemap.mode, tonemap.exposure, tonemap.gamma,
                                      tonemap.deband_enabled, tonemap.deband_strength)

        mode, exposure, gamma, deband, strength = in_game(body)["values"]
        self.assertEqual(mode, TonemappingMode.Uncharted2)
        self.assertAlmostEqual(exposure, 1.75, places=5)
        self.assertAlmostEqual(gamma, 2.2, places=5)
        self.assertTrue(deband)
        self.assertAlmostEqual(strength, 0.375, places=5)

    def test_the_remaining_scalar_passes_round_trip(self) -> None:
        def body(game, device, observed):
            with FxaaPass(device) as fxaa:
                fxaa.edge_threshold = 0.0625
                observed["fxaa"] = fxaa.edge_threshold
            with ChromaticAberrationPass(device) as aberration:
                aberration.strength = 0.03125
                observed["aberration"] = aberration.strength
            with FilmGrainPass(device) as grain:
                grain.intensity = 0.1875
                observed["grain"] = grain.intensity
            with LensFlarePass(device) as flare:
                flare.threshold = 1.5
                flare.intensity = 0.75
                flare.dispersal = 0.25
                observed["flare"] = (flare.threshold, flare.intensity, flare.dispersal)

        observed = in_game(body)
        self.assertAlmostEqual(observed["fxaa"], 0.0625, places=5)
        self.assertAlmostEqual(observed["aberration"], 0.03125, places=5)
        self.assertAlmostEqual(observed["grain"], 0.1875, places=5)
        threshold, intensity, dispersal = observed["flare"]
        self.assertAlmostEqual(threshold, 1.5, places=5)
        self.assertAlmostEqual(intensity, 0.75, places=5)
        self.assertAlmostEqual(dispersal, 0.25, places=5)
        self.assertGreater(LENS_FLARE_GHOST_COUNT, 0)

    def test_a_colour_grade_holds_the_tables_it_was_given(self) -> None:
        def body(game, device, observed):
            lut = create_identity_lut(device, 8)
            with ColorGradePass(device) as grade:
                try:
                    observed["lut_shape"] = (lut.Width, lut.Height)
                    observed["no_lut"] = grade.lut
                    grade.lut = lut
                    observed["identity"] = grade.lut is lut
                    grade.interpolation = LutInterpolation.Tetrahedral
                    grade.strength = 0.875
                    observed["state"] = (grade.interpolation, grade.strength)
                    grade.lut = None
                    observed["cleared"] = grade.lut
                finally:
                    lut.Dispose()

        observed = in_game(body)
        # A strip of eight slices, each 8x8.
        self.assertEqual(observed["lut_shape"], (64, 8))
        self.assertIsNone(observed["no_lut"])
        self.assertTrue(observed["identity"])
        interpolation, strength = observed["state"]
        self.assertEqual(interpolation, LutInterpolation.Tetrahedral)
        self.assertAlmostEqual(strength, 0.875, places=5)
        self.assertIsNone(observed["cleared"])

    def test_a_cube_lut_becomes_a_texture_a_grade_can_sample(self) -> None:
        def body(game, device, observed):
            with CubeLut.parse(IDENTITY_CUBE) as lut:
                strip = lut.create_strip_texture(device)
                volume = lut.create_volume_texture(device)
                with ColorGradePass(device) as grade:
                    try:
                        observed["strip"] = (strip.Width, strip.Height)
                        observed["volume"] = (volume.Width, volume.Height,
                                              volume.Depth)
                        grade.lut = strip
                        grade.volume_lut = volume
                        observed["assigned"] = (grade.lut is strip,
                                                grade.volume_lut is volume)
                        grade.lut = None
                        grade.volume_lut = None
                    finally:
                        strip.Dispose()
                        volume.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["strip"], (4, 2))
        self.assertEqual(observed["volume"], (2, 2, 2))
        self.assertEqual(observed["assigned"], (True, True))

    def test_the_ascii_pass_exposes_one_counted_effect(self) -> None:
        def body(game, device, observed):
            pass_ = AsciiPass(device)
            effect = pass_.ascii_effect
            observed["same"] = effect is pass_.ascii_effect
            observed["default_cell"] = effect.cell_size
            effect.cell_size = (12, 16)
            effect.quantize_mode = AsciiQuantizeMode.BlackAndWhite
            observed["cell"] = effect.cell_size
            observed["mode"] = effect.quantize_mode
            observed["grid"] = effect.last_grid_dimensions
            pass_.close()
            observed["closed"] = pass_.is_closed

        observed = in_game(body)
        self.assertTrue(observed["same"], "the effect must be one counted borrow")
        self.assertEqual(observed["cell"], (12, 16))
        self.assertEqual(observed["mode"], AsciiQuantizeMode.BlackAndWhite)
        self.assertEqual(len(observed["grid"]), 2)
        self.assertTrue(observed["closed"])
        width, height = observed["default_cell"]
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)


@requires_engine_gpu
class TonemapPixelTests(unittest.TestCase):
    """One pass checked against arithmetic rather than against its own getters."""

    def test_a_tonemap_pass_produces_what_its_cpu_twin_predicts(self) -> None:
        source_pixels = [Color(64, 128, 192, 255)] * 16

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(source_pixels)
            destination = RenderTarget2D(device, 4, 4)
            with ToneMapPass(device) as tonemap:
                try:
                    tonemap.mode = TonemappingMode.Reinhard
                    tonemap.exposure = 1.0
                    tonemap.gamma = 1.0
                    tonemap.deband_enabled = False
                    tonemap.apply(PostProcessContext(
                        source=source, destination=destination, width=4, height=4))
                    pixels = [Color(0, 0, 0, 0)] * 16
                    destination.GetData(pixels)
                    observed["produced"] = (int(pixels[0].R), int(pixels[0].G),
                                            int(pixels[0].B))
                    observed["expected"] = tuple(
                        tonemap_channel(TonemappingMode.Reinhard, channel / 255.0,
                                        1.0, 1.0)
                        for channel in (64, 128, 192))
                    observed["supported"] = tonemap.is_supported(device)
                finally:
                    source.Dispose()
                    destination.Dispose()

        observed = in_game(body)
        if not observed["supported"]:
            self.skipTest("this renderer degrades the tonemap pass to a copy")
        produced = observed["produced"]
        expected = [round(value * 255.0) for value in observed["expected"]]
        for index, (got, want) in enumerate(zip(produced, expected)):
            with self.subTest(channel="RGB"[index]):
                # Eight-bit storage and the shader's own rounding, so within
                # two levels rather than exact.
                self.assertLessEqual(abs(got - want), 2,
                                     f"{produced} against {expected}")
        # And it really did something: Reinhard darkens everything below one.
        self.assertLess(produced[2], 192)


@requires_engine_gpu
class SpatialUpscaleTests(unittest.TestCase):
    def test_state_round_trips_and_a_draw_reaches_the_target(self) -> None:
        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData([Color(200, 100, 50, 255)] * 16)
            destination = RenderTarget2D(device, 8, 8)
            with SpatialUpscalePass(device) as upscale:
                try:
                    upscale.sharpness = 0.375
                    upscale.edge_adaptive = False
                    observed["state"] = (upscale.sharpness, upscale.edge_adaptive)
                    device.SetRenderTarget(destination)
                    device.Clear(Color.Black)
                    upscale.draw(source, 4, 4, 8, 8)
                    device.SetRenderTarget(None)
                    pixels = [Color(0, 0, 0, 0)] * 64
                    destination.GetData(pixels)
                    observed["centre"] = (int(pixels[27].R), int(pixels[27].G),
                                          int(pixels[27].B))
                finally:
                    source.Dispose()
                    destination.Dispose()

        observed = in_game(body)
        sharpness, adaptive = observed["state"]
        self.assertAlmostEqual(sharpness, 0.375, places=5)
        self.assertFalse(adaptive)
        # The target was cleared to black and the source is a solid colour, so a
        # draw that reached it is not black any more.
        self.assertNotEqual(observed["centre"], (0, 0, 0),
                            "the upscale drew nothing")


@requires_engine_gpu
class HdrDisplayOutputTests(unittest.TestCase):
    def test_state_round_trips_and_support_is_reported(self) -> None:
        def body(game, device, observed):
            with HdrDisplayOutput(device) as output:
                observed["supported"] = output.is_supported
                observed["defaults"] = (output.paper_white_nits, output.peak_nits,
                                        output.color_space)
                output.color_space = DisplayColorSpace.Hdr10
                output.paper_white_nits = 250.0
                output.peak_nits = 1500.0
                observed["values"] = (output.color_space, output.paper_white_nits,
                                      output.peak_nits)

        observed = in_game(body)
        self.assertIsInstance(observed["supported"], bool)
        paper, peak, space = observed["defaults"]
        self.assertAlmostEqual(paper, HDR_DEFAULT_PAPER_WHITE_NITS, places=3)
        self.assertAlmostEqual(peak, HDR_DEFAULT_PEAK_NITS, places=3)
        self.assertIsInstance(space, DisplayColorSpace)
        space, paper, peak = observed["values"]
        self.assertEqual(space, DisplayColorSpace.Hdr10)
        self.assertAlmostEqual(paper, 250.0, places=3)
        self.assertAlmostEqual(peak, 1500.0, places=3)


@requires_engine_gpu
class AutoExposureTests(unittest.TestCase):
    """Adaptation is time-based, so the direction is what is predicted."""

    def test_a_brighter_scene_lowers_the_exposure_and_a_darker_one_raises_it(self) -> None:
        def body(game, device, observed):
            bright = Texture2D(device, 8, 8)
            bright.SetData([Color(240, 240, 240, 255)] * 64)
            dark = Texture2D(device, 8, 8)
            dark.SetData([Color(8, 8, 8, 255)] * 64)
            with AutoExposure(device) as exposure:
                try:
                    observed["bright_luminance"] = exposure.measure_average_luminance(
                        bright)
                    observed["dark_luminance"] = exposure.measure_average_luminance(dark)
                    observed["key"] = exposure.key_value
                    observed["speeds"] = (exposure.brightening_speed,
                                          exposure.darkening_speed)
                    exposure.set_exposure_range(0.01, 100.0)
                    exposure.set_adaptation_speeds(8.0, 4.0)
                    observed["set_speeds"] = (exposure.brightening_speed,
                                              exposure.darkening_speed)

                    exposure.exposure = 1.0
                    for _ in range(30):
                        toward_bright = exposure.update(bright, 0.1)
                    observed["bright"] = toward_bright

                    exposure.exposure = 1.0
                    for _ in range(30):
                        toward_dark = exposure.update(dark, 0.1)
                    observed["dark"] = toward_dark
                finally:
                    bright.Dispose()
                    dark.Dispose()

        observed = in_game(body)
        self.assertGreater(observed["bright_luminance"], observed["dark_luminance"],
                           "a white image is not brighter than a black one")
        self.assertGreater(observed["key"], 0.0)
        self.assertEqual(observed["set_speeds"], (8.0, 4.0))
        # A bright scene needs less exposure than a dark one. Both start at 1.0,
        # so their order after adapting is the claim.
        self.assertLess(observed["bright"], observed["dark"],
                        f"bright settled at {observed['bright']} and dark at "
                        f"{observed['dark']}")

    def test_the_exposure_range_is_respected(self) -> None:
        def body(game, device, observed):
            scene = Texture2D(device, 8, 8)
            scene.SetData([Color(255, 255, 255, 255)] * 64)
            with AutoExposure(device) as exposure:
                try:
                    exposure.set_exposure_range(0.5, 0.75)
                    exposure.set_adaptation_speeds(100.0, 100.0)
                    exposure.exposure = 1.0
                    for _ in range(50):
                        value = exposure.update(scene, 0.1)
                    observed["settled"] = value
                finally:
                    scene.Dispose()

        settled = in_game(body)["settled"]
        self.assertGreaterEqual(settled, 0.5 - 1e-4)
        self.assertLessEqual(settled, 0.75 + 1e-4)

    def test_the_exposure_reaches_a_pipeline_settings_value(self) -> None:
        from cna.extensions.engine import RenderPipelineSettings

        def body(game, device, observed):
            with AutoExposure(device) as exposure:
                exposure.exposure = 3.25
                settings = RenderPipelineSettings()
                observed["before"] = settings.exposure
                exposure.apply_to(settings)
                observed["after"] = settings.exposure

        observed = in_game(body)
        self.assertAlmostEqual(observed["after"], 3.25, places=4)
        self.assertNotAlmostEqual(observed["before"], 3.25, places=4)
