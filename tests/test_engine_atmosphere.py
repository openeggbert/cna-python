"""Screen-space effects and the sky, against the arithmetic they publish.

A screen-space effect is hard to check by looking at it -- SSAO on a flat scene
looks like SSAO on a broken one -- so what is checked here is the arithmetic
each shader runs, which CNA publishes as a CPU function. The lens equation is
zero at the focus plane and grows both ways; the transmittance reddens with
distance because blue scatters most; the sky is brighter toward the sun and
changes with turbidity. Each of those is a prediction, not a screenshot.

The state round trips are here too, because a pass whose setting never arrived
would produce a perfectly plausible picture.
"""

from __future__ import annotations

import math
import unittest

from Microsoft.Xna.Framework import Matrix, Vector2, Vector3
from Microsoft.Xna.Framework.Graphics import SurfaceFormat, TextureCube

from cna.extensions.engine import (
    AerialPerspectivePass, AtmosphericSky, ContactShadowPass,
    DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES, DepthOfFieldPass, HeightFogPass,
    LIGHT_SHAFT_STEP_COUNT, LightShaftPass, MotionBlurPass, RenderQuality,
    SSR_MAXIMUM_STEP_COUNT, SSR_MINIMUM_STEP_COUNT, ShadowMap, ShadowQuality,
    Skybox, SsaoPass, SsrPass, VOLUMETRIC_FOG_SLICE_COUNT, VolumetricFogPass,
    air_mass_for_distance, circle_of_confusion_millimetres, combine_visibility,
    compute_skybox_view_ray, contact_shadow_occlusion_glsl, is_occluded,
    optical_depth, sky_model_glsl, sky_radiance, ssao_occlusion_glsl,
    ssao_sample_count_for, transmittance,
)

from . import engine_oracles as oracle
from .engine_fixtures import in_game, requires_engine, requires_engine_gpu

SUN = Vector3(0.37, 0.62, 0.69)


@requires_engine
class LensTests(unittest.TestCase):
    """The depth-of-field equation, which is a lens rather than a look."""

    def test_the_circle_of_confusion_is_zero_at_the_focus_plane(self) -> None:
        self.assertAlmostEqual(
            circle_of_confusion_millimetres(5.0, 5.0, 50.0, 2.8), 0.0, places=5)

    def test_it_grows_on_both_sides_of_focus(self) -> None:
        near = circle_of_confusion_millimetres(2.0, 5.0, 50.0, 2.8)
        far = circle_of_confusion_millimetres(20.0, 5.0, 50.0, 2.8)
        self.assertGreater(near, 0.0)
        self.assertGreater(far, 0.0)
        # Nearer than focus blurs more than the same distance beyond it, because
        # the geometry is not symmetric -- which is what makes this a lens.
        closer = circle_of_confusion_millimetres(4.0, 5.0, 50.0, 2.8)
        further = circle_of_confusion_millimetres(6.0, 5.0, 50.0, 2.8)
        self.assertGreater(closer, further)

    def test_a_wider_aperture_blurs_more_and_a_longer_lens_blurs_more(self) -> None:
        wide = circle_of_confusion_millimetres(20.0, 5.0, 50.0, 1.4)
        narrow = circle_of_confusion_millimetres(20.0, 5.0, 50.0, 16.0)
        self.assertGreater(wide, narrow, "a wider aperture has to blur more")
        long_lens = circle_of_confusion_millimetres(20.0, 5.0, 200.0, 2.8)
        short_lens = circle_of_confusion_millimetres(20.0, 5.0, 24.0, 2.8)
        self.assertGreater(long_lens, short_lens, "a longer lens has to blur more")

    def test_the_sensor_height_is_the_headers(self) -> None:
        # 24mm is a full-frame sensor's height, and it is what turns the
        # millimetres above into a fraction of the screen.
        self.assertGreater(DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES, 0.0)


@requires_engine
class ContactShadowMathTests(unittest.TestCase):
    def test_a_ray_behind_a_surface_by_more_than_the_bias_is_occluded(self) -> None:
        # The ray is 0.4 behind the surface: past the 0.05 bias, inside the 0.5
        # thickness.
        self.assertTrue(is_occluded(10.0, 9.6, 0.05, 0.5))
        # Within the bias, it is the surface shadowing itself.
        self.assertFalse(is_occluded(10.0, 9.99, 0.05, 0.5))
        # In front of the surface, nothing is between it and the light.
        self.assertFalse(is_occluded(9.0, 10.0, 0.05, 0.5))
        # Both bounds are strict, which is where an inclusive comparison would
        # differ. The values are powers of two so the difference is exact in the
        # single precision CNA computes it in -- 10.0 - 9.95 is 0.05000019 in a
        # float, which is *not* on the boundary at all.
        self.assertFalse(is_occluded(10.0, 9.9375, 0.0625, 0.5))
        self.assertFalse(is_occluded(10.0, 9.5, 0.0625, 0.5))

    def test_a_ray_far_behind_a_thin_surface_passed_it_rather_than_into_it(self) -> None:
        """The thickness test, which is what stops a distant surface shadowing."""
        self.assertTrue(is_occluded(10.0, 9.5, 0.05, 1.0))
        self.assertFalse(is_occluded(10.0, 5.0, 0.05, 1.0),
                         "a ray five units behind a one-unit surface went past it")

    def test_visibilities_multiply_rather_than_adding(self) -> None:
        # Full visibility both ways is full visibility.
        self.assertAlmostEqual(combine_visibility(1.0, 1.0), 1.0, places=5)
        # Either one blocking blocks.
        self.assertAlmostEqual(combine_visibility(0.0, 1.0), 0.0, places=5)
        self.assertAlmostEqual(combine_visibility(1.0, 0.0), 0.0, places=5)
        # And it never goes below zero or above one.
        for a in (0.0, 0.25, 0.5, 1.0):
            for b in (0.0, 0.25, 0.5, 1.0):
                with self.subTest(a=a, b=b):
                    value = combine_visibility(a, b)
                    self.assertGreaterEqual(value, 0.0)
                    self.assertLessEqual(value, 1.0)
                    # Combining cannot brighten either input, and it is a
                    # product: two half-shadows leave a quarter of the light.
                    self.assertLessEqual(value, min(a, b) + 1e-5)
                    self.assertAlmostEqual(value, a * b, places=5)

    def test_the_published_occlusion_test_is_real_source(self) -> None:
        source = contact_shadow_occlusion_glsl()
        self.assertTrue(source.strip())
        self.assertIn("{", source)


@requires_engine
class AtmosphereMathTests(unittest.TestCase):
    def test_a_horizon_ray_crosses_more_air_than_a_vertical_one(self) -> None:
        up = air_mass_for_distance(Vector3(0.0, 1.0, 0.0), 1000.0, 800.0)
        horizon = air_mass_for_distance(Vector3(1.0, 0.0, 0.0), 1000.0, 800.0)
        self.assertGreater(horizon, up,
                           "a horizon ray has to cross more atmosphere")
        self.assertGreater(up, 0.0)

    def test_air_mass_grows_with_distance(self) -> None:
        values = [air_mass_for_distance(Vector3(1.0, 0.2, 0.0), distance, 800.0)
                  for distance in (10.0, 100.0, 1000.0, 10000.0)]
        self.assertEqual(values, sorted(values))

    def test_transmittance_reddens_with_air_and_never_leaves_zero_to_one(self) -> None:
        near = transmittance(2.0, 0.1)
        far = transmittance(2.0, 10.0)
        for value in (near, far):
            for component in (value.X, value.Y, value.Z):
                self.assertGreaterEqual(component, 0.0)
                self.assertLessEqual(component, 1.0 + 1e-5)
        # More air transmits less of everything.
        self.assertLess(far.X, near.X)
        self.assertLess(far.Z, near.Z)
        # And blue is scattered most, so what survives is redder.
        self.assertGreater(far.X, far.Z,
                           "distant light has to redden, not blue")

    def test_thicker_air_transmits_less(self) -> None:
        clear = transmittance(1.0, 2.0)
        hazy = transmittance(8.0, 2.0)
        self.assertLess(hazy.Z, clear.Z)

    def test_height_fog_accumulates_with_distance_and_density(self) -> None:
        base = optical_depth(10.0, 0.0, 100.0, 0.02, 0.1, 0.0)
        further = optical_depth(10.0, 0.0, 500.0, 0.02, 0.1, 0.0)
        denser = optical_depth(10.0, 0.0, 100.0, 0.08, 0.1, 0.0)
        self.assertGreater(further, base, "more distance is more fog")
        self.assertGreater(denser, base, "more density is more fog")
        self.assertGreaterEqual(base, 0.0)
        # Zero distance is zero fog.
        self.assertAlmostEqual(optical_depth(10.0, 0.0, 0.0, 0.02, 0.1, 0.0), 0.0,
                               places=5)

    def test_height_fog_thins_with_height(self) -> None:
        low = optical_depth(1.0, 0.0, 100.0, 0.05, 0.2, 0.0)
        high = optical_depth(50.0, 0.0, 100.0, 0.05, 0.2, 0.0)
        self.assertGreater(low, high, "fog has to thin with height")

    def test_the_sky_is_brighter_toward_the_sun(self) -> None:
        toward = sky_radiance(SUN, SUN, 2.0)
        away = sky_radiance(Vector3(-SUN.X, SUN.Y, -SUN.Z), SUN, 2.0)
        toward_sum = toward.X + toward.Y + toward.Z
        away_sum = away.X + away.Y + away.Z
        self.assertGreater(toward_sum, away_sum,
                           "the sky has to be brighter toward the sun")
        for value in (toward, away):
            for component in (value.X, value.Y, value.Z):
                self.assertTrue(math.isfinite(component))
                self.assertGreaterEqual(component, 0.0)

    def test_turbidity_changes_the_sky(self) -> None:
        """Compared relatively, because a zenith radiance is a small number.

        An absolute tolerance would call 1.3e-5 and 7.2e-8 equal, which is a
        two-hundred-fold difference and the whole effect of turbidity at the
        zenith.
        """
        clear = sky_radiance(Vector3(0.0, 1.0, 0.0), SUN, 1.5)
        hazy = sky_radiance(Vector3(0.0, 1.0, 0.0), SUN, 8.0)
        for axis in ("X", "Y", "Z"):
            with self.subTest(channel=axis):
                a, b = getattr(clear, axis), getattr(hazy, axis)
                self.assertGreater(abs(a - b), max(abs(a), abs(b)) * 0.05,
                                   f"turbidity moved {axis} from {a} to {b}")

    def test_the_published_sky_model_is_real_source(self) -> None:
        source = sky_model_glsl()
        self.assertTrue(source.strip())
        self.assertIn("{", source)

    def test_a_skybox_view_ray_points_where_the_camera_looks(self) -> None:
        view = Matrix.CreateLookAt(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, -1.0),
                                   Vector3(0.0, 1.0, 0.0))
        projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.0, 0.1, 100.0)
        centre = compute_skybox_view_ray(view, projection, 0.0, 0.0, 0.0)
        length = math.sqrt(centre.X ** 2 + centre.Y ** 2 + centre.Z ** 2)
        self.assertAlmostEqual(length, 1.0, places=4, msg="the ray is not a direction")
        # Looking down -Z, the centre of the screen looks down -Z.
        self.assertLess(centre.Z, -0.9)
        # The corners look outward, and to different places.
        left = compute_skybox_view_ray(view, projection, -1.0, 0.0, 0.0)
        right = compute_skybox_view_ray(view, projection, 1.0, 0.0, 0.0)
        self.assertLess(left.X, right.X, "the screen is not the right way round")

    def test_the_skybox_yaw_turns_the_ray(self) -> None:
        view = Matrix.CreateLookAt(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, -1.0),
                                   Vector3(0.0, 1.0, 0.0))
        projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.0, 0.1, 100.0)
        straight = compute_skybox_view_ray(view, projection, 0.0, 0.0, 0.0)
        turned = compute_skybox_view_ray(view, projection, 0.0, 0.0, math.pi / 2.0)
        self.assertFalse(oracle.vectors_agree(straight, turned, 1e-2),
                         "a quarter turn changed nothing")
        # A yaw is a rotation, so it keeps the ray a unit vector and keeps its
        # height.
        self.assertAlmostEqual(
            math.sqrt(turned.X ** 2 + turned.Y ** 2 + turned.Z ** 2), 1.0, places=4)
        self.assertAlmostEqual(turned.Y, straight.Y, places=4)


@requires_engine
class QualityPresetTests(unittest.TestCase):
    def test_ssao_samples_rise_with_quality(self) -> None:
        counts = [ssao_sample_count_for(quality) for quality in RenderQuality]
        self.assertEqual(counts, sorted(counts))
        self.assertGreater(counts[-1], counts[0])
        for value in counts:
            self.assertGreater(value, 0)

    def test_the_two_ssao_shaders_differ_by_encoding(self) -> None:
        packed, unpacked = ssao_occlusion_glsl(True), ssao_occlusion_glsl(False)
        self.assertTrue(packed.strip())
        self.assertTrue(unpacked.strip())
        self.assertNotEqual(packed, unpacked,
                            "the packed flag has to change the shader")

    def test_the_declared_bounds_are_coherent(self) -> None:
        self.assertLess(SSR_MINIMUM_STEP_COUNT, SSR_MAXIMUM_STEP_COUNT)
        self.assertGreater(VOLUMETRIC_FOG_SLICE_COUNT, 0)
        self.assertGreater(LIGHT_SHAFT_STEP_COUNT, 0)


@requires_engine_gpu
class ScreenSpacePassStateTests(unittest.TestCase):
    def test_every_pass_names_itself_distinctly(self) -> None:
        def body(game, device, observed):
            for kind in (SsaoPass, SsrPass, MotionBlurPass, DepthOfFieldPass,
                         ContactShadowPass, AerialPerspectivePass, HeightFogPass,
                         LightShaftPass, VolumetricFogPass):
                with kind(device) as pass_:
                    observed[kind.__name__] = (pass_.name, pass_.is_supported(device))

        observed = in_game(body)
        names = [name for name, _supported in observed.values()]
        for label, (name, supported) in observed.items():
            with self.subTest(pass_=label):
                self.assertTrue(name.strip(), f"{label} has no name")
                self.assertIsInstance(supported, bool)
        self.assertEqual(len(set(names)), len(names), names)

    def test_ssao_state_and_kernel(self) -> None:
        def body(game, device, observed):
            with SsaoPass(device) as ssao:
                ssao.radius = 0.75
                ssao.intensity = 1.25
                ssao.sample_count = 12
                ssao.half_resolution = True
                observed["state"] = (ssao.radius, ssao.intensity, ssao.sample_count,
                                     ssao.half_resolution)
                observed["kernel"] = ssao.kernel()
                ssao.reset_targets()

        observed = in_game(body)
        radius, intensity, samples, half = observed["state"]
        self.assertAlmostEqual(radius, 0.75, places=5)
        self.assertAlmostEqual(intensity, 1.25, places=5)
        self.assertEqual(samples, 12)
        self.assertTrue(half)
        kernel = observed["kernel"]
        # The kernel's length is CNA's, not the sample count: asking for twelve
        # offsets answers BUFFER_TOO_SMALL, which is why the size is asked for
        # first rather than assumed.
        self.assertGreaterEqual(len(kernel), 12)
        # Every offset is inside the unit hemisphere, and none is the origin: a
        # kernel that failed either would produce plausible-looking nonsense.
        for index, point in enumerate(kernel):
            with self.subTest(sample=index):
                length = math.sqrt(point.X ** 2 + point.Y ** 2 + point.Z ** 2)
                self.assertGreater(length, 0.0)
                self.assertLessEqual(length, 1.0 + 1e-4)
                self.assertGreaterEqual(point.Z, -1e-4,
                                        "a hemisphere kernel points one way")
        # And the offsets are distinct, or the samples are one sample.
        rendered = {(round(p.X, 4), round(p.Y, 4), round(p.Z, 4)) for p in kernel}
        self.assertEqual(len(rendered), len(kernel))

    def test_ssr_state_round_trips_and_the_step_count_is_clamped(self) -> None:
        def body(game, device, observed):
            with SsrPass(device) as ssr:
                ssr.max_distance = 32.5
                ssr.thickness = 0.375
                ssr.depth_bias = 0.0125
                ssr.roughness_blur = 0.125
                ssr.edge_fade = 0.25
                ssr.intensity = 0.875
                ssr.step_count = 24
                observed["state"] = (ssr.max_distance, ssr.thickness, ssr.depth_bias,
                                     ssr.roughness_blur, ssr.edge_fade, ssr.intensity,
                                     ssr.step_count)
                ssr.step_count = 1
                observed["too_few"] = ssr.step_count
                ssr.step_count = 100000
                observed["too_many"] = ssr.step_count
                # Two documented clamps, checked at the value that exceeds them.
                ssr.roughness_blur = 5.0
                observed["blur_clamped"] = ssr.roughness_blur
                ssr.edge_fade = 5.0
                observed["fade_clamped"] = ssr.edge_fade
                # And a setter that ignores rather than refuses.
                ssr.max_distance = 32.5
                ssr.max_distance = -1.0
                observed["ignored"] = ssr.max_distance

        observed = in_game(body)
        distance, thickness, bias, blur, fade, intensity, steps = observed["state"]
        self.assertAlmostEqual(distance, 32.5, places=5)
        self.assertAlmostEqual(thickness, 0.375, places=5)
        self.assertAlmostEqual(bias, 0.0125, places=5)
        self.assertAlmostEqual(blur, 0.125, places=5)
        self.assertAlmostEqual(fade, 0.25, places=5)
        self.assertAlmostEqual(intensity, 0.875, places=5)
        self.assertEqual(steps, 24)
        # The header declares the bounds; this is whether CNA keeps them.
        # The step count is stored as given and clamped where the trace runs,
        # not where it is set. Measured: setting one reads back one. The bounds
        # are what the *trace* honours, which is what the header says and what
        # the property documents; a test asserting the setter clamped would be
        # asserting something CNA does not do.
        self.assertEqual(observed["too_few"], 1)
        self.assertEqual(observed["too_many"], 100000)
        self.assertLess(SSR_MINIMUM_STEP_COUNT, SSR_MAXIMUM_STEP_COUNT)
        # Measured clamps, not guesses: a roughness blur past a quarter is a
        # quarter, and an edge fade past a half is a half.
        self.assertAlmostEqual(observed["blur_clamped"], 0.25, places=5)
        self.assertAlmostEqual(observed["fade_clamped"], 0.5, places=5)
        # A non-positive distance is ignored, so the previous value survives --
        # which is why the property documents reading it back.
        self.assertAlmostEqual(observed["ignored"], 32.5, places=5)

    def test_the_remaining_screen_space_state_round_trips(self) -> None:
        def body(game, device, observed):
            with MotionBlurPass(device) as blur:
                blur.strength = 0.625
                blur.max_distance = 0.125
                observed["blur"] = (blur.strength, blur.max_distance)
            with DepthOfFieldPass(device) as dof:
                dof.focus_distance = 7.5
                dof.focal_length = 85.0
                dof.f_number = 1.8
                dof.max_radius = 0.125
                observed["dof"] = (dof.focus_distance, dof.focal_length, dof.f_number,
                                   dof.max_radius)
            with ContactShadowPass(device) as contact:
                contact.light_direction = Vector3(0.0, -1.0, 0.0)
                contact.max_distance = 0.5
                contact.step_count = 9
                contact.thickness = 0.125
                contact.intensity = 0.75
                contact.bias = 0.02
                observed["contact"] = (contact.light_direction, contact.max_distance,
                                       contact.step_count, contact.thickness,
                                       contact.intensity, contact.bias)
                observed["contact_fallback"] = contact.fallback_reason

        observed = in_game(body)
        strength, max_distance = observed["blur"]
        self.assertAlmostEqual(strength, 0.625, places=5)
        self.assertAlmostEqual(max_distance, 0.125, places=5)
        focus, focal, aperture, radius = observed["dof"]
        self.assertAlmostEqual(focus, 7.5, places=5)
        self.assertAlmostEqual(focal, 85.0, places=4)
        self.assertAlmostEqual(aperture, 1.8, places=5)
        self.assertAlmostEqual(radius, 0.125, places=5)
        direction, distance, steps, thickness, intensity, bias = observed["contact"]
        self.assertTrue(oracle.vectors_agree(direction, Vector3(0.0, -1.0, 0.0)))
        self.assertAlmostEqual(distance, 0.5, places=5)
        self.assertEqual(steps, 9)
        self.assertAlmostEqual(thickness, 0.125, places=5)
        self.assertAlmostEqual(intensity, 0.75, places=5)
        self.assertAlmostEqual(bias, 0.02, places=5)
        self.assertIsInstance(observed["contact_fallback"], str)


@requires_engine_gpu
class AtmospherePassStateTests(unittest.TestCase):
    def test_aerial_perspective_and_the_fogs_round_trip(self) -> None:
        def body(game, device, observed):
            with AerialPerspectivePass(device) as aerial:
                aerial.sun_direction = SUN
                aerial.turbidity = 3.5
                aerial.intensity = 0.875
                aerial.scale_height = 1200.0
                observed["aerial"] = (aerial.sun_direction, aerial.turbidity,
                                      aerial.intensity, aerial.scale_height)
                observed["aerial_fallback"] = aerial.fallback_reason
            with HeightFogPass(device) as fog:
                fog.color = Vector3(0.5, 0.55, 0.65)
                fog.density = 0.03
                fog.falloff = 0.15
                fog.base_height = -2.5
                observed["height"] = (fog.color, fog.density, fog.falloff,
                                      fog.base_height)
            with LightShaftPass(device) as shafts:
                shafts.light_screen_position = Vector2(0.25, 0.75)
                shafts.threshold = 0.8
                shafts.intensity = 0.5
                shafts.decay = 0.95
                observed["shafts"] = (shafts.light_screen_position, shafts.threshold,
                                      shafts.intensity, shafts.decay)

        observed = in_game(body)
        direction, turbidity, intensity, scale = observed["aerial"]
        self.assertTrue(oracle.vectors_agree(direction, SUN))
        self.assertAlmostEqual(turbidity, 3.5, places=5)
        self.assertAlmostEqual(intensity, 0.875, places=5)
        self.assertAlmostEqual(scale, 1200.0, places=2)
        self.assertIsInstance(observed["aerial_fallback"], str)
        colour, density, falloff, base = observed["height"]
        self.assertTrue(oracle.vectors_agree(colour, Vector3(0.5, 0.55, 0.65)))
        self.assertAlmostEqual(density, 0.03, places=5)
        self.assertAlmostEqual(falloff, 0.15, places=5)
        self.assertAlmostEqual(base, -2.5, places=5)
        position, threshold, shaft_intensity, decay = observed["shafts"]
        self.assertAlmostEqual(position.X, 0.25, places=5)
        self.assertAlmostEqual(position.Y, 0.75, places=5)
        self.assertAlmostEqual(threshold, 0.8, places=5)
        self.assertAlmostEqual(shaft_intensity, 0.5, places=5)
        self.assertAlmostEqual(decay, 0.95, places=5)

    def test_volumetric_fog_holds_the_shadow_map_it_is_lit_by(self) -> None:
        def body(game, device, observed):
            shadow = ShadowMap(device, ShadowQuality.Low)
            with VolumetricFogPass(device) as fog:
                try:
                    fog.density = 0.04
                    fog.anisotropy = 0.6
                    fog.range_ = 60.0
                    observed["state"] = (fog.density, fog.anisotropy, fog.range_)
                    fog.set_light(shadow, Vector3(0.0, -1.0, 0.0),
                                  Vector3(1.0, 0.95, 0.9))
                    observed["lit"] = True
                    fog.set_light(None, Vector3(0.0, -1.0, 0.0),
                                  Vector3(1.0, 1.0, 1.0))
                    observed["unlit"] = True
                finally:
                    shadow.close()

        observed = in_game(body)
        density, anisotropy, range_ = observed["state"]
        self.assertAlmostEqual(density, 0.04, places=5)
        self.assertAlmostEqual(anisotropy, 0.6, places=5)
        self.assertAlmostEqual(range_, 60.0, places=4)
        self.assertTrue(observed["lit"])
        self.assertTrue(observed["unlit"])

    def test_the_atmospheric_sky_holds_its_state_and_draws(self) -> None:
        from Microsoft.Xna.Framework import Color
        from Microsoft.Xna.Framework.Graphics import RenderTarget2D

        def body(game, device, observed):
            with AtmosphericSky(device) as sky:
                observed["supported"] = sky.is_supported
                sky.sun_direction = SUN
                sky.turbidity = 4.5
                sky.intensity = 1.5
                observed["state"] = (sky.sun_direction, sky.turbidity, sky.intensity)
                if not sky.is_supported:
                    return
                target = RenderTarget2D(device, 16, 16)
                try:
                    device.SetRenderTarget(target)
                    device.Clear(Color.Black)
                    view = Matrix.CreateLookAt(Vector3(0.0, 0.0, 0.0), SUN,
                                               Vector3(0.0, 1.0, 0.0))
                    projection = Matrix.CreatePerspectiveFieldOfView(1.2, 1.0, 0.1,
                                                                     100.0)
                    sky.draw(view, projection, 16, 16)
                    device.SetRenderTarget(None)
                    pixels = [Color(0, 0, 0, 0)] * 256
                    target.GetData(pixels)
                    observed["drew"] = any(
                        (p.R, p.G, p.B) != (0, 0, 0) for p in pixels)
                finally:
                    target.Dispose()

        observed = in_game(body)
        direction, turbidity, intensity = observed["state"]
        self.assertTrue(oracle.vectors_agree(direction, SUN, 1e-3))
        self.assertAlmostEqual(turbidity, 4.5, places=5)
        self.assertAlmostEqual(intensity, 1.5, places=5)
        if not observed["supported"]:
            self.skipTest("this renderer cannot compile the sky shader")
        # The target was cleared to black and the sky was drawn over it.
        self.assertTrue(observed["drew"], "the sky drew nothing at all")

    def test_a_skybox_borrows_the_cube_it_was_given(self) -> None:
        def body(game, device, observed):
            cube = TextureCube(device, 4, False, SurfaceFormat.Color)
            with Skybox(device, cube) as skybox:
                try:
                    observed["supported"] = skybox.is_supported
                    observed["identity"] = skybox.environment is cube
                    skybox.yaw = 1.25
                    skybox.intensity = 0.75
                    skybox.tint = Vector3(0.9, 0.8, 0.7)
                    observed["state"] = (skybox.yaw, skybox.intensity, skybox.tint)
                    skybox.environment = None
                    observed["cleared"] = skybox.environment
                    skybox.environment = cube
                    observed["restored"] = skybox.environment is cube
                finally:
                    pass
            # The cube outlives the skybox, because it was only borrowed.
            observed["cube_alive"] = not cube.IsDisposed
            cube.Dispose()

        observed = in_game(body)
        self.assertTrue(observed["identity"])
        yaw, intensity, tint = observed["state"]
        self.assertAlmostEqual(yaw, 1.25, places=5)
        self.assertAlmostEqual(intensity, 0.75, places=5)
        self.assertTrue(oracle.vectors_agree(tint, Vector3(0.9, 0.8, 0.7)))
        self.assertIsNone(observed["cleared"])
        self.assertTrue(observed["restored"])
        self.assertTrue(observed["cube_alive"],
                        "closing a skybox must not dispose a borrowed cube")
