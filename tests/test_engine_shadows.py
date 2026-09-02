"""Shadow maps, against independently computed matrices and rendered depth.

No getter is its own oracle here. Every matrix CNA computes is compared with one
:mod:`tests.engine_oracles` builds from the stated algorithm, and every fixture
is asymmetric on purpose: a light straight down the Y axis, a cube centred on the
origin, or a symmetric split would let a transposed matrix, a swapped axis or an
off-by-one cascade pass.

The maps that need a rasterizer are separated from the pure math, which needs
only a build with an engine layer -- so the control artifact still runs the
matrix cases even though it can draw nothing.
"""

from __future__ import annotations

import math
import struct
import unittest

from Microsoft.Xna.Framework import BoundingBox, Color, Matrix, Vector3
from Microsoft.Xna.Framework.Graphics import CubeMapFace, SurfaceFormat

from cna.extensions.engine import (
    CUBE_SHADOW_FACE_COUNT, CascadedShadowMap, CubeShadowMap, DirectionalLight,
    PointLight, PunctualLight, PunctualLightKind, SHADOW_CASCADE_MAXIMUM,
    ShadowCascadeState, ShadowMap, ShadowQuality, ShadowReceiver, SpotLight,
    SpotShadowMap, compute_light_projection, compute_light_view,
    cube_shadow_map_size_for, shadow_filter_radius_for, shadow_map_size_for,
    supports_shadow_sampling,
)
from cna.extensions.engine.errors import (
    EngineDisposedError, EngineError, EngineUnavailableError,
)

from . import engine_oracles as oracle
from .engine_fixtures import (
    ENGINE_PRESENT, in_game, requires_engine, requires_engine_gpu,
    requires_native,
)

#: A light that is not axis-aligned and not near vertical, so a transposed or
#: axis-swapped view matrix cannot coincide with the right one.
SLANTED = Vector3(0.37, -0.62, 0.69)

#: A box that is not centred on the origin and not a cube, so a centre computed
#: from the wrong corners, or extents read in the wrong order, differ.
SCENE = BoundingBox(Vector3(-3.0, -1.0, 2.0), Vector3(5.0, 7.0, 11.0))


@requires_engine
class ShadowQualityTests(unittest.TestCase):
    """The presets, read from CNA rather than written down.

    Pure value routes, so they answer on any build with an engine layer.
    """

    def test_size_and_filter_rise_with_quality(self) -> None:
        sizes = {quality: shadow_map_size_for(quality) for quality in ShadowQuality}
        radii = {quality: shadow_filter_radius_for(quality) for quality in ShadowQuality}
        # Each is a power of two and none is zero: a shadow map with no texels
        # would be a silently useless object.
        for quality, size in sizes.items():
            with self.subTest(quality=quality.name):
                self.assertGreater(size, 0)
                self.assertEqual(size & (size - 1), 0, f"{size} is not a power of two")
                self.assertGreaterEqual(radii[quality], 0)
        # Monotonic, and strictly bigger at the top than at the bottom.
        order = [ShadowQuality.Disabled, ShadowQuality.Low, ShadowQuality.Medium,
                 ShadowQuality.High, ShadowQuality.Ultra]
        for lower, higher in zip(order, order[1:]):
            with self.subTest(step=f"{lower.name}->{higher.name}"):
                self.assertLessEqual(sizes[lower], sizes[higher])
                self.assertLessEqual(radii[lower], radii[higher])
        self.assertLess(sizes[ShadowQuality.Disabled], sizes[ShadowQuality.Ultra])
        self.assertLess(radii[ShadowQuality.Low], radii[ShadowQuality.Ultra])

    def test_a_cube_face_is_not_forced_to_match_a_flat_map(self) -> None:
        """Six faces cost six times one, so CNA may choose a smaller face."""
        for quality in ShadowQuality:
            with self.subTest(quality=quality.name):
                face = cube_shadow_map_size_for(quality)
                self.assertGreater(face, 0)
                self.assertLessEqual(face, shadow_map_size_for(quality))


@requires_native
class LightValueTests(unittest.TestCase):
    """The light values and their CNA-supplied defaults.

    ``engine_layer.h`` promises these work in **both** builds, because filling a
    light with its defaults needs no engine-layer object. Measured: they do, so
    these run on the control artifact -- the one with no engine layer at all --
    as well as on the GPU one, and the gate is the library rather than the
    layer.
    """

    def test_the_light_values_answer_without_an_engine_layer(self) -> None:
        """The header's "works in both builds" promise, checked where it matters.

        On the control artifact this is the only engine surface that answers at
        all; on the GPU artifact it is unremarkable. Running the same assertion
        on both is what makes it evidence.
        """
        for factory in (DirectionalLight.default, PointLight.default,
                        SpotLight.default, PunctualLight.default,
                        ShadowCascadeState.default):
            with self.subTest(value=factory.__self__.__name__):
                self.assertIsNotNone(factory())
        # And the shadow *math* genuinely does need the layer, which is what the
        # header says and what separates the two claims.
        if not ENGINE_PRESENT:
            with self.assertRaises(EngineUnavailableError):
                shadow_map_size_for(ShadowQuality.High)

    def test_defaults_come_from_cna_and_round_trip(self) -> None:
        from dataclasses import replace

        sun = DirectionalLight.default()
        self.assertIsInstance(sun.direction, Vector3)
        self.assertIsInstance(sun.intensity, float)
        self.assertIsInstance(sun.casts_shadows, bool)
        # The default direction is a unit vector: a light with no direction, or
        # one that is accidentally zero, would silently produce no shadow.
        length = math.sqrt(sun.direction.X ** 2 + sun.direction.Y ** 2
                           + sun.direction.Z ** 2)
        self.assertAlmostEqual(length, 1.0, places=5)
        # Adjusting one field keeps every other CNA default.
        tilted = replace(sun, direction=Vector3(*tuple(SLANTED)))
        self.assertEqual(tilted.color, sun.color)
        self.assertEqual(tilted.intensity, sun.intensity)

    def test_every_light_kind_has_defaults(self) -> None:
        point, spot = PointLight.default(), SpotLight.default()
        punctual = PunctualLight.default()
        cascades = ShadowCascadeState.default()
        self.assertGreater(point.range_, 0.0, "a point light with no range lights nothing")
        self.assertGreater(spot.range_, 0.0)
        # Inner inside outer, or the falloff is inverted.
        self.assertLessEqual(spot.inner_angle, spot.outer_angle)
        self.assertEqual(punctual.kind, PunctualLightKind.Nothing)
        self.assertIsNone(punctual.shadow_map)
        self.assertIsNone(punctual.shadow_cube)
        self.assertEqual(cascades.count, 0, "cascades default to disabled")
        self.assertEqual(len(cascades.world_to_atlas), SHADOW_CASCADE_MAXIMUM)
        self.assertEqual(len(cascades.split_distance), SHADOW_CASCADE_MAXIMUM)


@requires_engine
class ShadowMatrixTests(unittest.TestCase):
    """The pure matrix helpers, against the algorithm rather than their own output."""

    def test_light_view_matches_an_independent_construction(self) -> None:
        from dataclasses import replace

        light = replace(DirectionalLight.default(), direction=SLANTED)
        produced = compute_light_view(light, SCENE)
        expected = oracle.shadow_light_view(SLANTED, SCENE.Min, SCENE.Max)
        self.assertTrue(oracle.matrices_agree(produced, expected),
                        f"\nCNA:      {tuple(produced)}\nexpected: {tuple(expected)}")

    def test_a_light_pointing_straight_down_uses_the_other_up_vector(self) -> None:
        """The case the obvious up vector breaks, and the common one."""
        from dataclasses import replace

        straight_down = Vector3(0.0, -1.0, 0.0)
        light = replace(DirectionalLight.default(), direction=straight_down)
        produced = compute_light_view(light, SCENE)
        expected = oracle.shadow_light_view(straight_down, SCENE.Min, SCENE.Max)
        self.assertTrue(oracle.matrices_agree(produced, expected),
                        f"\nCNA:      {tuple(produced)}\nexpected: {tuple(expected)}")
        # And it is genuinely a different matrix from the slanted case, so the
        # two branches are not accidentally the same answer.
        slanted = compute_light_view(replace(light, direction=SLANTED), SCENE)
        self.assertFalse(oracle.matrices_agree(produced, slanted))

    def test_the_projection_fits_the_scene_in_light_space(self) -> None:
        """Every scene corner lands inside the clip volume, and it is snug."""
        from dataclasses import replace

        light = replace(DirectionalLight.default(), direction=SLANTED)
        view = compute_light_view(light, SCENE)
        projection = compute_light_projection(view, SCENE)
        combined = Matrix.Multiply(view, projection)
        xs, ys = [], []
        for x in (SCENE.Min.X, SCENE.Max.X):
            for y in (SCENE.Min.Y, SCENE.Max.Y):
                for z in (SCENE.Min.Z, SCENE.Max.Z):
                    clip = oracle.transform_coordinate((x, y, z), combined)
                    self.assertLessEqual(abs(clip.X), 1.0 + 1e-4, (x, y, z))
                    self.assertLessEqual(abs(clip.Y), 1.0 + 1e-4, (x, y, z))
                    self.assertGreaterEqual(clip.Z, -1e-4, (x, y, z))
                    self.assertLessEqual(clip.Z, 1.0 + 1e-4, (x, y, z))
                    xs.append(clip.X)
                    ys.append(clip.Y)
        # Snug, not merely containing: a projection ten times too large would
        # pass the bounds above and waste every texel.
        self.assertGreater(max(xs) - min(xs), 1.5)
        self.assertGreater(max(ys) - min(ys), 1.5)

    def test_a_spot_light_view_and_projection_frame_its_cone(self) -> None:
        from dataclasses import replace

        light = replace(SpotLight.default(), position=Vector3(2.0, 6.0, -3.0),
                        direction=SLANTED, range_=40.0,
                        inner_angle=0.25, outer_angle=0.55)
        view = SpotShadowMap.compute_light_view(light)
        projection = SpotShadowMap.compute_light_projection(light)
        # The light's own position is the view's origin.
        origin = oracle.transform_coordinate(tuple(light.position), view)
        self.assertTrue(oracle.vectors_agree(origin, Vector3(0.0, 0.0, 0.0), 1e-3),
                        f"the spot light is not at its own view origin: {tuple(origin)}")
        # A point one unit along the cone axis is straight ahead in view space:
        # x and y vanish and z does not.
        unit = oracle.normalized(SLANTED)
        ahead = Vector3(light.position.X + unit.X, light.position.Y + unit.Y,
                        light.position.Z + unit.Z)
        transformed = oracle.transform_coordinate(tuple(ahead), view)
        self.assertAlmostEqual(transformed.X, 0.0, places=4)
        self.assertAlmostEqual(transformed.Y, 0.0, places=4)
        self.assertAlmostEqual(abs(transformed.Z), 1.0, places=4)
        # The projection is a perspective one: its w row is not the identity's.
        values = tuple(projection)
        self.assertNotEqual(values[11], 0.0,
                            "a spot shadow projection has to be perspective")

    def test_cube_face_views_point_along_six_different_axes(self) -> None:
        """Six faces, six directions -- the test a face-order swap fails."""
        position = Vector3(1.0, -2.0, 3.0)
        forwards = []
        for face in CubeMapFace:
            view = CubeShadowMap.compute_face_view(face, position)
            origin = oracle.transform_coordinate(tuple(position), view)
            self.assertTrue(oracle.vectors_agree(origin, Vector3(0.0, 0.0, 0.0), 1e-3),
                            f"{face.name}: the light is not at its own view origin")
            # The third column of the rotation is the view's forward axis.
            values = tuple(view)
            forwards.append((round(values[2], 4), round(values[6], 4),
                             round(values[10], 4)))
        self.assertEqual(len(set(forwards)), CUBE_SHADOW_FACE_COUNT,
                         f"two faces look the same way: {forwards}")
        # Each is a signed unit axis, and every axis appears twice.
        axes = sorted(abs(component) for forward in forwards for component in forward)
        self.assertEqual(axes, [0.0] * 12 + [1.0] * 6)

    def test_the_cube_face_projection_is_ninety_degrees(self) -> None:
        projection = CubeShadowMap.compute_face_projection(50.0)
        values = tuple(projection)
        # A square 90-degree perspective has m11 == m22 == 1/tan(45) == 1.
        self.assertAlmostEqual(values[0], 1.0, places=4)
        self.assertAlmostEqual(values[5], 1.0, places=4)
        self.assertNotEqual(values[11], 0.0)


@requires_engine
class CascadeMathTests(unittest.TestCase):
    """Cascade splits, corners, spheres and snapping, against the algorithm."""

    def test_split_distances_match_the_blend_of_log_and_uniform(self) -> None:
        # Deliberately not round: 0.37 and 213.7 make a formula that happens to
        # be off by a factor of two visible in every digit.
        for count in (2, 3, 4):
            for lambda_ in (0.0, 0.35, 0.75, 1.0):
                with self.subTest(count=count, lambda_=lambda_):
                    produced = CascadedShadowMap.split_distances(0.37, 213.7, count, lambda_)
                    expected = oracle.cascade_split_distances(0.37, 213.7, count, lambda_)
                    self.assertEqual(len(produced), count)
                    for index, (a, b) in enumerate(zip(produced, expected)):
                        self.assertAlmostEqual(a, b, places=3, msg=f"split {index}")
                    # The last split is the far plane by definition.
                    self.assertAlmostEqual(produced[-1], 213.7, places=3)
                    # Strictly increasing, or a cascade covers nothing.
                    self.assertEqual(list(produced), sorted(produced))

    def test_lambda_is_clamped_rather_than_extrapolated(self) -> None:
        low = CascadedShadowMap.split_distances(1.0, 100.0, 3, 0.0)
        high = CascadedShadowMap.split_distances(1.0, 100.0, 3, 1.0)
        self.assertEqual(CascadedShadowMap.split_distances(1.0, 100.0, 3, -5.0), low)
        self.assertEqual(CascadedShadowMap.split_distances(1.0, 100.0, 3, 5.0), high)
        # And the two ends are genuinely different divisions.
        self.assertNotAlmostEqual(low[0], high[0], places=3)

    def test_a_degenerate_range_is_refused(self) -> None:
        for near, far, count in ((0.0, 100.0, 3), (10.0, 10.0, 3), (1.0, 100.0, 1),
                                 (1.0, 100.0, 5)):
            with self.subTest(near=near, far=far, count=count):
                with self.assertRaises(EngineError):
                    CascadedShadowMap.split_distances(near, far, count, 0.5)

    def test_frustum_corners_match_an_independent_unprojection(self) -> None:
        view = Matrix.CreateLookAt(Vector3(4.0, 3.0, 9.0), Vector3(-1.0, 0.5, 0.0),
                                   Vector3(0.0, 1.0, 0.0))
        projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.6, 0.4, 90.0)
        produced = CascadedShadowMap.frustum_corners(view, projection)
        expected = oracle.frustum_corners(view, projection)
        self.assertEqual(len(produced), 8)
        for index, (a, b) in enumerate(zip(produced, expected)):
            self.assertTrue(oracle.vectors_agree(a, b, 1e-2),
                            f"corner {index}: CNA {tuple(a)} vs {tuple(b)}")
        # Eight distinct corners: a frustum whose corners collapse is not one.
        self.assertEqual(len({(round(v.X, 3), round(v.Y, 3), round(v.Z, 3))
                              for v in produced}), 8)

    def test_bounding_sphere_is_the_mean_and_the_furthest_corner(self) -> None:
        view = Matrix.CreateLookAt(Vector3(4.0, 3.0, 9.0), Vector3(-1.0, 0.5, 0.0),
                                   Vector3(0.0, 1.0, 0.0))
        projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.6, 0.4, 90.0)
        corners = CascadedShadowMap.frustum_corners(view, projection)
        centre, radius = CascadedShadowMap.bounding_sphere(corners)
        expected_centre, expected_radius = oracle.bounding_sphere(corners)
        self.assertTrue(oracle.vectors_agree(centre, expected_centre, 1e-2),
                        f"{tuple(centre)} vs {tuple(expected_centre)}")
        self.assertAlmostEqual(radius, expected_radius, delta=max(1e-2, radius * 1e-3))
        # It really does contain every corner.
        for corner in corners:
            distance = math.dist(tuple(corner), tuple(centre))
            self.assertLessEqual(distance, radius + 1e-2)

    def test_snapping_quantises_x_and_y_and_leaves_depth_alone(self) -> None:
        centre = Vector3(3.14159, -2.71828, 1.41421)
        radius, size = 7.5, 1024
        produced = CascadedShadowMap.snap_to_texel_grid(centre, radius, size)
        expected = oracle.snap_to_texel_grid(centre, radius, size)
        self.assertTrue(oracle.vectors_agree(produced, expected, 1e-5),
                        f"{tuple(produced)} vs {tuple(expected)}")
        # Depth is untouched, which is the half a naive implementation gets wrong.
        self.assertAlmostEqual(produced.Z, centre.Z, places=6)
        # And the result really is on the grid.
        world_per_texel = 2.0 * radius / size
        self.assertAlmostEqual(produced.X % world_per_texel, 0.0, places=5)
        self.assertAlmostEqual(produced.Y % world_per_texel, 0.0, places=5)


@requires_engine_gpu
class ShadowMapTests(unittest.TestCase):
    def test_a_map_reports_its_shape_and_both_support_questions(self) -> None:
        def body(game, device, observed):
            with ShadowMap(device, ShadowQuality.Low) as shadow:
                observed["size"] = shadow.size
                observed["quality"] = shadow.quality
                observed["filter"] = shadow.filter_radius
                observed["casting"] = shadow.is_supported
                observed["sampling"] = supports_shadow_sampling(device)
                shadow.depth_bias = 0.0035
                observed["bias"] = shadow.depth_bias

        observed = in_game(body)
        self.assertEqual(observed["quality"], ShadowQuality.Low)
        self.assertEqual(observed["size"], shadow_map_size_for(ShadowQuality.Low))
        self.assertEqual(observed["filter"], shadow_filter_radius_for(ShadowQuality.Low))
        self.assertIsInstance(observed["casting"], bool)
        self.assertIsInstance(observed["sampling"], bool)
        self.assertAlmostEqual(observed["bias"], 0.0035, places=6)

    def test_the_shadow_texture_is_the_same_view_every_time_and_reads_back(self) -> None:
        """One counted borrow, kept, and a real depth target behind it."""
        def body(game, device, observed):
            with ShadowMap(device, ShadowQuality.Low) as shadow:
                first, second = shadow.shadow_texture, shadow.shadow_texture
                observed["identical"] = first is second
                observed["shape"] = (first.Width, first.Height, int(first.Format))
                observed["size"] = shadow.size

        observed = in_game(body)
        self.assertTrue(observed["identical"],
                        "reading the texture twice must not take two borrows")
        width, height, surface = observed["shape"]
        self.assertEqual((width, height), (observed["size"], observed["size"]))
        # A depth map wants more than 256 distinguishable depths where the
        # renderer has them; either choice is CNA's, and both are real formats.
        self.assertIn(surface, {int(SurfaceFormat.Single), int(SurfaceFormat.Color)})

    def test_casting_clears_the_map_to_the_far_plane(self) -> None:
        """White, not black: an unwritten texel must not read as a near occluder.

        Clearing to black would put every texel at the nearest possible depth,
        and the whole scene would be in shadow wherever no caster was drawn.
        """
        def body(game, device, observed):
            from dataclasses import replace

            with ShadowMap(device, ShadowQuality.Low) as shadow:
                if not shadow.is_supported:
                    observed["unsupported"] = True
                    return
                light = replace(DirectionalLight.default(), direction=SLANTED)
                with shadow.cast(light, SCENE):
                    pass
                texture = shadow.shadow_texture
                pixels = [Color(0, 0, 0, 0)] * (texture.Width * texture.Height)
                texture.GetData(pixels)
                first = pixels[0]
                observed["format"] = int(texture.Format)
                observed["bytes"] = bytes((int(first.R), int(first.G),
                                           int(first.B), int(first.A)))
                observed["light_view_projection"] = shadow.light_view_projection

        observed = in_game(body)
        if observed.get("unsupported"):
            self.skipTest("this renderer cannot compile the shadow caster")
        # GetData always hands back four bytes per texel as a Colour, so a float
        # depth map has to be decoded rather than read as a colour. Both formats
        # a shadow map can have mean the same thing here: the far plane.
        raw = observed["bytes"]
        if observed["format"] == int(SurfaceFormat.Single):
            depth = struct.unpack("<f", raw)[0]
            self.assertAlmostEqual(depth, 1.0, places=5,
                                   msg="an empty shadow map must read as infinitely far")
        else:
            self.assertEqual(tuple(raw), (255, 255, 255, 255),
                             "an empty shadow map must read as infinitely far away")
        # And casting computed a transform, not the identity.
        self.assertFalse(oracle.matrices_agree(observed["light_view_projection"],
                                               Matrix.Identity))

    def test_the_cast_transform_is_the_pure_helpers_composed(self) -> None:
        """The map's matrix is exactly view * projection from the pure routes."""
        def body(game, device, observed):
            from dataclasses import replace

            with ShadowMap(device, ShadowQuality.Low) as shadow:
                if not shadow.is_supported:
                    observed["unsupported"] = True
                    return
                light = replace(DirectionalLight.default(), direction=SLANTED)
                with shadow.cast(light, SCENE):
                    pass
                observed["produced"] = shadow.light_view_projection
                view = compute_light_view(light, SCENE)
                observed["expected"] = Matrix.Multiply(
                    view, compute_light_projection(view, SCENE))

        observed = in_game(body)
        if observed.get("unsupported"):
            self.skipTest("this renderer cannot compile the shadow caster")
        self.assertTrue(oracle.matrices_agree(observed["produced"], observed["expected"]),
                        f"\n{tuple(observed['produced'])}\n{tuple(observed['expected'])}")

    def test_close_releases_the_views_it_handed_out(self) -> None:
        """CNA refuses to destroy a map whose borrows are alive; close handles it."""
        def body(game, device, observed):
            shadow = ShadowMap(device, ShadowQuality.Low)
            texture = shadow.shadow_texture
            effect = shadow.caster_effect
            shadow.close()
            observed["closed"] = shadow.is_closed
            observed["texture_disposed"] = texture.IsDisposed
            observed["effect_disposed"] = effect is None or effect.IsDisposed
            with self.assertRaises(EngineDisposedError):
                shadow.size

        observed = in_game(body)
        self.assertTrue(observed["closed"])
        self.assertTrue(observed["texture_disposed"])
        self.assertTrue(observed["effect_disposed"])


@requires_engine_gpu
class CascadedShadowMapTests(unittest.TestCase):
    def test_the_atlas_is_one_row_of_cascades(self) -> None:
        def body(game, device, observed):
            with CascadedShadowMap(device, ShadowQuality.Low, 3) as shadow:
                observed["count"] = shadow.cascade_count
                observed["cascade_size"] = shadow.cascade_size
                texture = shadow.shadow_texture
                observed["atlas"] = (texture.Width, texture.Height)

        observed = in_game(body)
        self.assertEqual(observed["count"], 3)
        size = observed["cascade_size"]
        self.assertEqual(observed["atlas"], (size * 3, size),
                         "three cascades side by side in one atlas")

    def test_update_produces_increasing_splits_and_distinct_transforms(self) -> None:
        def body(game, device, observed):
            from dataclasses import replace

            with CascadedShadowMap(device, ShadowQuality.Low, 4) as shadow:
                shadow.split_lambda = 0.6
                shadow.blend_band = 1.75
                light = replace(DirectionalLight.default(), direction=SLANTED)
                view = Matrix.CreateLookAt(Vector3(4.0, 3.0, 9.0),
                                           Vector3(-1.0, 0.5, 0.0),
                                           Vector3(0.0, 1.0, 0.0))
                projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.6, 0.4, 90.0)
                shadow.update(light, view, projection)
                observed["splits"] = [shadow.split_distance(i) for i in range(4)]
                observed["matrices"] = [tuple(shadow.cascade_matrix(i)) for i in range(4)]
                observed["lambda"] = shadow.split_lambda
                observed["band"] = shadow.blend_band
                observed["selected"] = [shadow.select_cascade(depth)
                                        for depth in (0.5, 5.0, 30.0, 89.0)]

        observed = in_game(body)
        self.assertAlmostEqual(observed["lambda"], 0.6, places=5)
        self.assertAlmostEqual(observed["band"], 1.75, places=5)
        splits = observed["splits"]
        self.assertEqual(splits, sorted(splits), f"splits must increase: {splits}")
        self.assertAlmostEqual(splits[-1], 90.0, delta=0.5)
        # The splits are the pure helper's, for the same camera range.
        expected = oracle.cascade_split_distances(0.4, 90.0, 4, 0.6)
        for index, (produced, wanted) in enumerate(zip(splits, expected)):
            self.assertAlmostEqual(produced, wanted, delta=max(0.05, wanted * 0.02),
                                   msg=f"split {index}")
        # Four cascades, four different transforms.
        self.assertEqual(len({tuple(round(v, 3) for v in m)
                              for m in observed["matrices"]}), 4)
        # Deeper points select later cascades, and never go backwards.
        self.assertEqual(observed["selected"], sorted(observed["selected"]))
        self.assertLess(observed["selected"][0], observed["selected"][-1])

    def test_debug_tint_is_off_by_default_and_settable(self) -> None:
        def body(game, device, observed):
            with CascadedShadowMap(device, ShadowQuality.Low, 2) as shadow:
                observed["default"] = shadow.debug_tint_enabled
                shadow.debug_tint_enabled = True
                observed["on"] = shadow.debug_tint_enabled
                shadow.debug_tint_enabled = False
                observed["off"] = shadow.debug_tint_enabled

        observed = in_game(body)
        self.assertFalse(observed["default"])
        self.assertTrue(observed["on"])
        self.assertFalse(observed["off"])


@requires_engine_gpu
class SpotAndCubeShadowMapTests(unittest.TestCase):
    def test_a_spot_map_records_the_light_it_cast_from(self) -> None:
        def body(game, device, observed):
            from dataclasses import replace

            with SpotShadowMap(device, ShadowQuality.Low) as shadow:
                if not shadow.is_supported:
                    observed["unsupported"] = True
                    return
                light = replace(SpotLight.default(), position=Vector3(2.0, 6.0, -3.0),
                                direction=SLANTED, range_=42.5,
                                inner_angle=0.25, outer_angle=0.55)
                with shadow.cast(light):
                    pass
                observed["position"] = shadow.light_position
                observed["range"] = shadow.light_range
                observed["matrix"] = shadow.light_view_projection
                observed["expected"] = Matrix.Multiply(
                    SpotShadowMap.compute_light_view(light),
                    SpotShadowMap.compute_light_projection(light))
                observed["size"] = shadow.size

        observed = in_game(body)
        if observed.get("unsupported"):
            self.skipTest("this renderer cannot compile the spot shadow caster")
        self.assertTrue(oracle.vectors_agree(observed["position"],
                                             Vector3(2.0, 6.0, -3.0), 1e-4))
        self.assertAlmostEqual(observed["range"], 42.5, places=4)
        self.assertTrue(oracle.matrices_agree(observed["matrix"], observed["expected"]),
                        f"\n{tuple(observed['matrix'])}\n{tuple(observed['expected'])}")

    def test_a_cube_map_is_a_cube_and_covers_six_faces(self) -> None:
        def body(game, device, observed):
            from dataclasses import replace

            with CubeShadowMap(device, ShadowQuality.Low) as shadow:
                observed["size"] = shadow.size
                texture = shadow.shadow_texture
                observed["cube_size"] = texture.Size
                observed["same_view"] = texture is shadow.shadow_texture
                if not shadow.is_supported:
                    observed["unsupported"] = True
                    return
                light = replace(PointLight.default(), position=Vector3(1.0, -2.0, 3.0),
                                range_=25.0)
                shadow.update(light)
                observed["position"] = shadow.light_position
                observed["range"] = shadow.light_range
                for face in CubeMapFace:
                    with shadow.cast(face):
                        pass
                observed["faces"] = len(list(CubeMapFace))

        observed = in_game(body)
        self.assertEqual(observed["cube_size"], observed["size"])
        self.assertEqual(observed["size"], cube_shadow_map_size_for(ShadowQuality.Low))
        self.assertTrue(observed["same_view"])
        if observed.get("unsupported"):
            self.skipTest("this renderer cannot compile the cube shadow caster")
        self.assertTrue(oracle.vectors_agree(observed["position"],
                                             Vector3(1.0, -2.0, 3.0), 1e-4))
        self.assertAlmostEqual(observed["range"], 25.0, places=4)
        self.assertEqual(observed["faces"], CUBE_SHADOW_FACE_COUNT)


@requires_engine_gpu
class ShadowReceiverTests(unittest.TestCase):
    """The engine state an effect carries, written through and read back.

    A round trip is weak evidence on its own, so each value here is one no
    default would produce, and the shadow map assignment is checked against the
    texture identity rather than against a flag.
    """

    def test_state_reaches_the_effect_and_comes_back(self) -> None:
        from Microsoft.Xna.Framework.Graphics import BasicEffect

        def body(game, device, observed):
            effect = BasicEffect(device)
            shadow = ShadowMap(device, ShadowQuality.Low)
            try:
                receiver = ShadowReceiver(effect)
                observed["effect_is_the_one_given"] = receiver.effect is effect
                observed["default_enabled"] = receiver.enabled
                receiver.enabled = True
                receiver.depth_bias = 0.00375
                receiver.filter_radius = 3
                transform = Matrix.CreateTranslation(Vector3(7.0, -2.0, 5.0))
                receiver.light_view_projection = transform
                texture = shadow.shadow_texture
                receiver.shadow_map = texture
                observed["enabled"] = receiver.enabled
                observed["bias"] = receiver.depth_bias
                observed["radius"] = receiver.filter_radius
                observed["transform"] = receiver.light_view_projection
                observed["expected_transform"] = transform
                observed["texture_identity"] = receiver.shadow_map is texture
                receiver.shadow_map = None
                observed["cleared"] = receiver.shadow_map
            finally:
                shadow.close()
                effect.Dispose()

        observed = in_game(body)
        self.assertTrue(observed["effect_is_the_one_given"])
        self.assertFalse(observed["default_enabled"])
        self.assertTrue(observed["enabled"])
        self.assertAlmostEqual(observed["bias"], 0.00375, places=6)
        self.assertEqual(observed["radius"], 3)
        self.assertTrue(oracle.matrices_agree(observed["transform"],
                                              observed["expected_transform"]))
        self.assertTrue(observed["texture_identity"])
        self.assertIsNone(observed["cleared"])

    def test_cascade_state_crosses_whole(self) -> None:
        from Microsoft.Xna.Framework.Graphics import BasicEffect

        def body(game, device, observed):
            from dataclasses import replace

            effect = BasicEffect(device)
            try:
                receiver = ShadowReceiver(effect)
                base = ShadowCascadeState.default()
                # Four distinct transforms and four distinct splits, so a state
                # that copied one entry over all of them would be visible.
                state = replace(
                    base, count=3, blend_band=2.25,
                    world_to_atlas=tuple(
                        Matrix.CreateTranslation(Vector3(index + 1.0, index + 2.0,
                                                         index + 3.0))
                        for index in range(SHADOW_CASCADE_MAXIMUM)),
                    split_distance=(1.5, 9.25, 40.0, 137.75),
                    camera_view=Matrix.CreateTranslation(Vector3(-4.0, 5.0, -6.0)),
                    debug_tint=True)
                receiver.cascades = state
                observed["read"] = receiver.cascades
                observed["written"] = state
            finally:
                effect.Dispose()

        observed = in_game(body)
        read, written = observed["read"], observed["written"]
        self.assertEqual(read.count, written.count)
        self.assertAlmostEqual(read.blend_band, written.blend_band, places=5)
        self.assertEqual(read.debug_tint, written.debug_tint)
        for index in range(SHADOW_CASCADE_MAXIMUM):
            with self.subTest(cascade=index):
                self.assertAlmostEqual(read.split_distance[index],
                                       written.split_distance[index], places=4)
                self.assertTrue(oracle.matrices_agree(read.world_to_atlas[index],
                                                      written.world_to_atlas[index]))
        self.assertTrue(oracle.matrices_agree(read.camera_view, written.camera_view))

    def test_a_punctual_light_crosses_whole(self) -> None:
        from Microsoft.Xna.Framework.Graphics import BasicEffect

        def body(game, device, observed):
            from dataclasses import replace

            effect = BasicEffect(device)
            try:
                receiver = ShadowReceiver(effect)
                light = replace(
                    PunctualLight.default(), kind=PunctualLightKind.Spot,
                    position=Vector3(3.0, -4.0, 5.0), direction=SLANTED,
                    diffuse_color=Vector3(0.25, 0.5, 0.75), range_=17.5,
                    inner_angle=0.3, outer_angle=0.7, shadow_depth_bias=0.0025,
                    shadow_view_projection=Matrix.CreateTranslation(
                        Vector3(-1.0, 2.0, -3.0)))
                receiver.punctual_light = light
                observed["read"] = receiver.punctual_light
                observed["written"] = light
            finally:
                effect.Dispose()

        observed = in_game(body)
        read, written = observed["read"], observed["written"]
        self.assertEqual(read.kind, PunctualLightKind.Spot)
        self.assertTrue(oracle.vectors_agree(read.position, written.position))
        self.assertTrue(oracle.vectors_agree(read.diffuse_color, written.diffuse_color))
        self.assertAlmostEqual(read.range_, written.range_, places=4)
        self.assertAlmostEqual(read.inner_angle, written.inner_angle, places=5)
        self.assertAlmostEqual(read.outer_angle, written.outer_angle, places=5)
        self.assertAlmostEqual(read.shadow_depth_bias, written.shadow_depth_bias,
                               places=6)
        self.assertTrue(oracle.matrices_agree(read.shadow_view_projection,
                                              written.shadow_view_projection))

    def test_a_cascaded_map_applies_its_whole_state_at_once(self) -> None:
        from Microsoft.Xna.Framework.Graphics import BasicEffect

        def body(game, device, observed):
            from dataclasses import replace

            effect = BasicEffect(device)
            shadow = CascadedShadowMap(device, ShadowQuality.Low, 3)
            try:
                receiver = ShadowReceiver(effect)
                observed["before"] = receiver.cascades.count
                light = replace(DirectionalLight.default(), direction=SLANTED)
                view = Matrix.CreateLookAt(Vector3(4.0, 3.0, 9.0),
                                           Vector3(-1.0, 0.5, 0.0),
                                           Vector3(0.0, 1.0, 0.0))
                projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.6, 0.4, 90.0)
                shadow.update(light, view, projection)
                shadow.blend_band = 3.5
                try:
                    shadow.apply_to(receiver)
                except EngineError as error:
                    observed["refused"] = type(error).__name__
                    return
                state = receiver.cascades
                observed["count"] = state.count
                observed["band"] = state.blend_band
                observed["splits"] = list(state.split_distance[:3])
                observed["map_splits"] = [shadow.split_distance(i) for i in range(3)]
            finally:
                shadow.close()
                effect.Dispose()

        observed = in_game(body)
        if "refused" in observed:
            # BasicEffect may not implement the receiver contract; that is a
            # measured boundary, reported rather than asserted away.
            self.assertEqual(observed["refused"], "EngineArgumentError")
            self.skipTest("BasicEffect does not implement the shadow-receiver contract")
        self.assertEqual(observed["before"], 0)
        self.assertEqual(observed["count"], 3)
        self.assertAlmostEqual(observed["band"], 3.5, places=5)
        for index, (applied, own) in enumerate(zip(observed["splits"],
                                                   observed["map_splits"])):
            self.assertAlmostEqual(applied, own, places=4, msg=f"split {index}")
