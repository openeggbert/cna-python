"""Culling, level of detail and instancing, against independent geometry.

The frustum planes are extracted a second time in :mod:`tests.engine_oracles`
by combining rows of the view-projection, and every visibility answer is checked
against them. Level selection, the projected pixel radius and the hysteresis
rule are all reimplemented there too, so no CNA getter is its own oracle.

The fixtures are deliberately awkward: thresholds added out of order, a camera
that is not at the origin looking down an axis in the cases where the transform
matters, and bounds that are visible, behind, and off to the side.

A LOD group and a frustum culler are arithmetic and run on any build with an
engine layer. The instanced renderer and the GPU culler need a device, so they
are separated out.
"""

from __future__ import annotations

import math
import unittest

from Microsoft.Xna.Framework import (
    BoundingBox, BoundingFrustum, BoundingSphere, Color, Matrix, Vector3,
)

from cna.extensions.engine import (
    FrustumCuller, GPU_INSTANCE_STORAGE_BINDING, GpuCullableInstance, GpuInstanceCuller,
    IndirectDrawArguments, IndirectDrawIndexedArguments, InstancedRenderer, LodGroup,
    LodSelectionMode, StorageBuffer, draw_indexed_primitives_indirect,
    draw_primitives_indirect, instance_lookup_glsl, instance_vertex_elements,
    instance_vertex_stride, tint_vertex_elements, tint_vertex_stride,
)
from cna.extensions.engine.errors import (
    EngineArgumentError, EngineDisposedError, EngineError, EngineUnavailableError,
)

from . import engine_oracles as oracle
from .engine_fixtures import (
    ENGINE_PRESENT, in_game, requires_engine, requires_engine_gpu, requires_native,
)

FIELD_OF_VIEW = 0.9773843811168246
ASPECT = 1.7777777777777777
NEAR, FAR = 0.35, 47.5
PROJECTION = Matrix.CreatePerspectiveFieldOfView(FIELD_OF_VIEW, ASPECT, NEAR, FAR)
VIEW = Matrix.CreateLookAt(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, -1.0),
                           Vector3(0.0, 1.0, 0.0))
#: A camera that is neither at the origin nor looking down an axis, so a missing
#: view transform is a different answer rather than the same one.
OFF_AXIS_VIEW = Matrix.CreateLookAt(Vector3(3.0, 2.0, 7.0), Vector3(-1.0, 0.5, -4.0),
                                    Vector3(0.0, 1.0, 0.0))

#: Thresholds added out of order, so a group that failed to sort would answer
#: differently from the oracle at every distance.
THRESHOLDS = (25.0, 5.0, 100.0)
SORTED_THRESHOLDS = (5.0, 25.0, 100.0)


def _mesh_part(device=None, *, with_buffers: bool = False):
    """A strict-XNA mesh part, of the shape a loaded model produces.

    Built here rather than loaded, because the geometry does not matter to any
    of these cases and a content fixture would make them depend on the content
    pipeline as well.
    """
    from Microsoft.Xna.Framework.Graphics import (
        BufferUsage, IndexBuffer, IndexElementSize, ModelMeshPart, VertexBuffer,
        VertexPositionColor,
    )

    part = ModelMeshPart()
    part._num, part._primitive, part._start, part._offset = 3, 1, 0, 0
    if with_buffers:
        vertices = VertexBuffer(device, VertexPositionColor, 3, BufferUsage.WriteOnly)
        vertices.SetData([VertexPositionColor(Vector3(0.0, 0.0, 0.0), Color.White),
                          VertexPositionColor(Vector3(1.0, 0.0, 0.0), Color.White),
                          VertexPositionColor(Vector3(0.0, 1.0, 0.0), Color.White)])
        indices = IndexBuffer(device, IndexElementSize.SixteenBits, 3,
                              BufferUsage.WriteOnly)
        indices.SetData([0, 1, 2])
        part._set_resources(vertices, indices)
    return part


@requires_engine
class LodGroupTests(unittest.TestCase):
    def _group(self, thresholds=THRESHOLDS):
        group = LodGroup()
        parts = [_mesh_part() for _ in thresholds]
        for threshold, part in zip(thresholds, parts):
            group.add_level(threshold, part)
        return group, parts

    def test_an_empty_group_selects_nothing(self) -> None:
        with LodGroup() as group:
            self.assertEqual(group.levels(), ())
            self.assertEqual(group.select_index(1.0), -1)
            self.assertIsNone(group.select(1.0))

    def test_levels_are_sorted_finest_first_whatever_order_they_arrive_in(self) -> None:
        group, parts = self._group()
        with group:
            levels = group.levels()
            self.assertEqual(tuple(round(level.max_distance, 5) for level in levels),
                             SORTED_THRESHOLDS)
            # And each level still carries the caller's own object.
            for level, threshold in zip(levels, SORTED_THRESHOLDS):
                self.assertIs(level.part, parts[THRESHOLDS.index(threshold)])

    def test_every_selection_matches_an_independent_upper_bound(self) -> None:
        group, parts = self._group()
        with group:
            for distance in (0.0, 1.0, 4.999, 5.0, 5.001, 24.9, 25.0, 99.0, 100.0,
                             101.0, -3.0):
                group.reset_hysteresis()
                clamped = max(distance, 0.0)
                self.assertEqual(
                    group.select_index(distance),
                    oracle.lod_select_by_distance(list(SORTED_THRESHOLDS), clamped),
                    f"distance {distance}")

    def test_selecting_answers_with_the_caller_s_own_mesh_part(self) -> None:
        group, parts = self._group()
        with group:
            group.reset_hysteresis()
            chosen = group.select(1.0)
            self.assertIs(chosen, parts[THRESHOLDS.index(5.0)])
            group.reset_hysteresis()
            self.assertIs(group.select(30.0), parts[THRESHOLDS.index(100.0)])

    def test_past_every_level_nothing_is_selected(self) -> None:
        group, _parts = self._group()
        with group:
            group.reset_hysteresis()
            self.assertEqual(group.select_index(1e9), -1)
            self.assertIsNone(group.select(1e9))

    def test_a_threshold_that_is_not_positive_is_refused(self) -> None:
        with LodGroup() as group:
            for threshold in (0.0, -1.0):
                with self.subTest(threshold=threshold), self.assertRaises(EngineError):
                    group.add_level(threshold, _mesh_part())
            self.assertEqual(group.levels(), ())

    def test_clearing_drops_every_level(self) -> None:
        group, _parts = self._group()
        with group:
            group.clear()
            self.assertEqual(group.levels(), ())
            self.assertEqual(group.select_index(1.0), -1)

    def test_hysteresis_holds_a_level_across_its_own_boundary(self) -> None:
        """The behaviour it exists for, and the oracle agrees about both steps."""
        group, _parts = self._group()
        with group:
            group.hysteresis = 2.0
            group.reset_hysteresis()
            first = group.select_index(4.0)
            held = group.select_index(6.0)
            moved = group.select_index(20.0)
            self.assertEqual(first, 0)
            self.assertEqual(held, oracle.lod_apply_hysteresis(
                list(SORTED_THRESHOLDS),
                oracle.lod_select_by_distance(list(SORTED_THRESHOLDS), 6.0), 0, 6.0,
                2.0))
            self.assertEqual(held, 0, "6.0 is within 2.0 of the boundary at 5.0")
            self.assertEqual(moved, 1, "20.0 is a real change, not a wobble")

    def test_hysteresis_never_holds_across_more_than_one_boundary(self) -> None:
        """A jump of two levels is a real change, whatever the margin.

        Holding it back would be worse than the flicker hysteresis prevents:
        the object would be drawn at a level chosen for a distance it left some
        time ago. Checked with a margin far larger than the boundary it would
        otherwise be sticky at.
        """
        group, _parts = self._group()
        with group:
            group.hysteresis = 1000.0
            group.reset_hysteresis()
            self.assertEqual(group.select_index(1.0), 0)
            two_away = group.select_index(30.0)
            self.assertEqual(
                two_away,
                oracle.lod_apply_hysteresis(
                    list(SORTED_THRESHOLDS),
                    oracle.lod_select_by_distance(list(SORTED_THRESHOLDS), 30.0), 0,
                    30.0, 1000.0))
            self.assertEqual(two_away, 2, "two levels at once is never sticky")

    def test_a_non_positive_margin_becomes_zero_rather_than_being_refused(self) -> None:
        with LodGroup() as group:
            self.assertEqual(group.hysteresis, 0.0)
            group.hysteresis = -5.0
            self.assertEqual(group.hysteresis, 0.0)
            group.hysteresis = 3.5
            self.assertAlmostEqual(group.hysteresis, 3.5, places=6)

    def test_the_screen_space_mode_re_sorts_and_forgets(self) -> None:
        group, _parts = self._group()
        with group:
            self.assertEqual(group.selection_mode, LodSelectionMode.Distance)
            group.selection_mode = LodSelectionMode.ScreenSpaceError
            self.assertEqual(group.selection_mode, LodSelectionMode.ScreenSpaceError)
            self.assertEqual(
                tuple(round(level.max_distance, 5) for level in group.levels()),
                tuple(reversed(SORTED_THRESHOLDS)))

    def test_an_unknown_selection_mode_is_refused(self) -> None:
        with LodGroup() as group:
            with self.assertRaises(ValueError):
                group.selection_mode = 99

    def test_every_projected_radius_matches_an_independent_projection(self) -> None:
        with LodGroup() as group:
            group.set_screen_space_parameters(1.5, FIELD_OF_VIEW, 720.0)
            for distance in (1.0, 2.5, 10.0, 100.0):
                self.assertAlmostEqual(
                    group.projected_radius_pixels(distance),
                    oracle.lod_projected_radius_pixels(1.5, FIELD_OF_VIEW, 720.0,
                                                       distance),
                    places=3, msg=f"distance {distance}")

    def test_at_or_behind_the_eye_the_radius_is_as_large_as_it_gets(self) -> None:
        with LodGroup() as group:
            group.set_screen_space_parameters(1.5, FIELD_OF_VIEW, 720.0)
            for distance in (0.0, -4.0):
                self.assertGreater(group.projected_radius_pixels(distance), 1e30)

    def test_screen_space_selection_uses_pixels_and_turns_the_comparison_round(self) -> None:
        pixel_thresholds = (400.0, 100.0, 20.0)
        group, _parts = self._group(pixel_thresholds)
        with group:
            group.set_screen_space_parameters(1.5, FIELD_OF_VIEW, 720.0)
            group.selection_mode = LodSelectionMode.ScreenSpaceError
            sorted_pixels = sorted(pixel_thresholds, reverse=True)
            for distance in (1.0, 3.0, 10.0, 40.0, 200.0):
                group.reset_hysteresis()
                pixels = group.projected_radius_pixels(distance)
                self.assertEqual(
                    group.select_index(distance),
                    oracle.lod_select_by_screen_space(sorted_pixels, pixels),
                    f"distance {distance} covers {pixels} pixels")

    def test_screen_space_parameters_refuse_a_value_outside_their_range(self) -> None:
        with LodGroup() as group:
            for arguments in ((0.0, FIELD_OF_VIEW, 720.0), (1.5, 0.0, 720.0),
                              (1.5, 3.2, 720.0), (1.5, FIELD_OF_VIEW, 0.0)):
                with self.subTest(arguments=arguments), self.assertRaises(EngineError):
                    group.set_screen_space_parameters(*arguments)

    def test_it_refuses_something_that_is_not_a_mesh_part(self) -> None:
        with LodGroup() as group, self.assertRaises(TypeError):
            group.add_level(1.0, object())

    def test_a_closed_group_refuses_rather_than_reaching_freed_memory(self) -> None:
        group, _parts = self._group()
        group.close()
        group.close()
        with self.assertRaises(EngineDisposedError):
            group.select_index(1.0)


@requires_engine
class FrustumCullerTests(unittest.TestCase):
    BOXES = (BoundingBox(Vector3(-1.0, -1.0, -5.0), Vector3(1.0, 1.0, -4.0)),
             BoundingBox(Vector3(-1.0, -1.0, 5.0), Vector3(1.0, 1.0, 6.0)),
             BoundingBox(Vector3(100.0, 100.0, -5.0), Vector3(101.0, 101.0, -4.0)),
             BoundingBox(Vector3(-2.0, -2.0, -40.0), Vector3(2.0, 2.0, -39.0)))
    SPHERES = (BoundingSphere(Vector3(0.0, 0.0, -5.0), 1.0),
               BoundingSphere(Vector3(0.0, 0.0, 5.0), 1.0),
               BoundingSphere(Vector3(0.0, 0.0, 5.0), 20.0),
               BoundingSphere(Vector3(0.0, 0.0, -100.0), 1.0))

    def _culler(self, view=VIEW):
        culler = FrustumCuller()
        culler.set_camera(view, PROJECTION)
        return culler

    def _planes(self, view=VIEW):
        return oracle.frustum_planes(Matrix.Multiply(view, PROJECTION))

    def test_every_box_answer_matches_the_independent_plane_test(self) -> None:
        with self._culler() as culler:
            planes = self._planes()
            for index, box in enumerate(self.BOXES):
                self.assertEqual(culler.is_visible(box),
                                 oracle.box_is_visible(planes, box.Min, box.Max),
                                 f"box {index}")

    def test_every_sphere_answer_matches_the_independent_plane_test(self) -> None:
        with self._culler() as culler:
            planes = self._planes()
            for index, sphere in enumerate(self.SPHERES):
                self.assertEqual(
                    culler.is_visible(sphere),
                    oracle.sphere_is_visible(planes, sphere.Center, sphere.Radius),
                    f"sphere {index}")

    def test_it_still_agrees_under_a_camera_that_is_not_on_an_axis(self) -> None:
        """An identity-ish view would hide a missing world-to-view transform."""
        with self._culler(OFF_AXIS_VIEW) as culler:
            planes = self._planes(OFF_AXIS_VIEW)
            for index, box in enumerate(self.BOXES):
                self.assertEqual(culler.is_visible(box),
                                 oracle.box_is_visible(planes, box.Min, box.Max),
                                 f"box {index}")

    def test_setting_the_combined_matrix_is_the_same_as_setting_both(self) -> None:
        with FrustumCuller() as one, FrustumCuller() as two:
            one.set_camera(OFF_AXIS_VIEW, PROJECTION)
            two.set_view_projection(Matrix.Multiply(OFF_AXIS_VIEW, PROJECTION))
            for box in self.BOXES:
                self.assertEqual(one.is_visible(box), two.is_visible(box))

    def test_culling_a_list_gives_the_indices_the_single_test_agrees_with(self) -> None:
        with self._culler() as culler:
            visible = culler.cull_boxes(self.BOXES)
            self.assertEqual(
                visible,
                tuple(index for index, box in enumerate(self.BOXES)
                      if culler.is_visible(box)))
            planes = self._planes()
            self.assertEqual(
                visible,
                tuple(index for index, box in enumerate(self.BOXES)
                      if oracle.box_is_visible(planes, box.Min, box.Max)))

    def test_culling_spheres_likewise(self) -> None:
        with self._culler() as culler:
            visible = culler.cull_spheres(self.SPHERES)
            planes = self._planes()
            self.assertEqual(
                visible,
                tuple(index for index, sphere in enumerate(self.SPHERES)
                      if oracle.sphere_is_visible(planes, sphere.Center,
                                                  sphere.Radius)))

    def test_an_empty_list_culls_to_nothing_rather_than_failing(self) -> None:
        with self._culler() as culler:
            self.assertEqual(culler.cull_boxes(()), ())
            self.assertEqual(culler.cull_spheres(()), ())
            self.assertEqual(culler.cull_transforms((), ()), ())

    def test_culling_transforms_keeps_the_ones_whose_bounds_survive(self) -> None:
        transforms = (Matrix.CreateTranslation(0.0, 0.0, 0.0),
                      Matrix.CreateTranslation(1.0, 2.0, 3.0),
                      Matrix.CreateTranslation(-4.0, 0.0, 5.0))
        with self._culler() as culler:
            kept = culler.cull_transforms(transforms, self.BOXES[:3])
            expected = [transform for transform, box in zip(transforms, self.BOXES)
                        if culler.is_visible(box)]
            self.assertEqual(len(kept), len(expected))
            for got, want in zip(kept, expected):
                self.assertEqual(list(got), list(want))

    def test_a_transform_with_no_matching_bound_is_kept(self) -> None:
        """Measured: fewer bounds than transforms means "always draw these"."""
        transforms = tuple(Matrix.CreateTranslation(float(x), 0.0, 0.0)
                           for x in range(3))
        behind = BoundingBox(Vector3(-1.0, -1.0, 5.0), Vector3(1.0, 1.0, 6.0))
        with self._culler() as culler:
            self.assertFalse(culler.is_visible(behind))
            kept = culler.cull_transforms(transforms, (behind,))
            self.assertEqual(len(kept), 2)
            self.assertEqual(list(kept[0]), list(transforms[1]))
            self.assertEqual(list(kept[1]), list(transforms[2]))

    def test_the_frustum_is_a_strict_bounding_frustum_over_the_same_matrix(self) -> None:
        with self._culler(OFF_AXIS_VIEW) as culler:
            frustum = culler.frustum
            self.assertIsInstance(frustum, BoundingFrustum)
            expected = Matrix.Multiply(OFF_AXIS_VIEW, PROJECTION)
            for got, want in zip(frustum.Matrix, expected):
                self.assertAlmostEqual(got, want, places=4)

    def test_a_culler_with_no_camera_still_answers(self) -> None:
        """The identity matrix is a degenerate frustum, not an error."""
        with FrustumCuller() as culler:
            self.assertIsInstance(culler.is_visible(self.BOXES[0]), bool)

    def test_it_refuses_something_that_is_neither_a_box_nor_a_sphere(self) -> None:
        with self._culler() as culler, self.assertRaises(TypeError):
            culler.is_visible(object())


@requires_engine
class IndirectDrawArgumentTests(unittest.TestCase):
    """Two structures whose layout is the contract, because the GPU reads it."""

    def test_the_defaults_are_all_zero_and_draw_nothing(self) -> None:
        arguments = IndirectDrawArguments.default()
        self.assertEqual((arguments.vertex_count, arguments.instance_count,
                          arguments.first_vertex, arguments.base_instance),
                         (0, 0, 0, 0))
        indexed = IndirectDrawIndexedArguments.default()
        self.assertEqual((indexed.index_count, indexed.instance_count,
                          indexed.first_index, indexed.base_vertex,
                          indexed.base_instance), (0, 0, 0, 0, 0))

    def test_the_packed_bytes_are_the_words_in_order(self) -> None:
        """Sixteen and twenty bytes, little-endian, no padding anywhere."""
        import struct

        packed = IndirectDrawArguments(3, 2, 1, 0).pack()
        self.assertEqual(len(packed), 16)
        self.assertEqual(struct.unpack("<4I", packed), (3, 2, 1, 0))
        indexed = IndirectDrawIndexedArguments(6, 4, 3, -2, 0).pack()
        self.assertEqual(len(indexed), 20)
        self.assertEqual(struct.unpack("<3Ii1I", indexed), (6, 4, 3, -2, 0))

    def test_a_negative_base_vertex_is_allowed_and_the_others_are_not(self) -> None:
        """base_vertex is signed, as the graphics API is; the rest are not."""
        IndirectDrawIndexedArguments(1, 1, 0, -5, 0).pack()
        with self.assertRaises(ValueError):
            IndirectDrawArguments(-1, 1, 0, 0).pack()
        with self.assertRaises(ValueError):
            IndirectDrawIndexedArguments(1, 1, -1, 0, 0).pack()


@requires_engine
class InstanceStreamLayoutTests(unittest.TestCase):
    """The vertex layout a caller's own shader has to declare, published by CNA."""

    def test_the_instance_stream_is_four_vector4_rows(self) -> None:
        from Microsoft.Xna.Framework.Graphics import (
            VertexElementFormat, VertexElementUsage,
        )

        elements = instance_vertex_elements()
        self.assertEqual(len(elements), 4)
        for index, element in enumerate(elements):
            self.assertEqual(element.Offset, index * 16)
            self.assertEqual(element.VertexElementFormat, VertexElementFormat.Vector4)
            self.assertEqual(element.VertexElementUsage,
                             VertexElementUsage.TextureCoordinate)
            self.assertEqual(element.UsageIndex, index + 1)

    def test_the_instance_stride_is_a_whole_matrix(self) -> None:
        self.assertEqual(instance_vertex_stride(), 64)
        elements = instance_vertex_elements()
        self.assertEqual(elements[-1].Offset + 16, instance_vertex_stride())

    def test_the_tint_stream_is_one_packed_colour(self) -> None:
        from Microsoft.Xna.Framework.Graphics import (
            VertexElementFormat, VertexElementUsage,
        )

        elements = tint_vertex_elements()
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].Offset, 0)
        self.assertEqual(elements[0].VertexElementFormat, VertexElementFormat.Color)
        self.assertEqual(elements[0].VertexElementUsage, VertexElementUsage.Color)
        self.assertEqual(elements[0].UsageIndex, 1)
        self.assertEqual(tint_vertex_stride(), 4)

    def test_the_published_glsl_names_what_a_shader_calls(self) -> None:
        source = instance_lookup_glsl()
        self.assertGreater(len(source), 50)
        self.assertIn("cnaInstanceWorld", source)
        self.assertEqual(source, instance_lookup_glsl())


# --- what needs a renderer ----------------------------------------------------


@requires_engine_gpu
class InstancedRendererTests(unittest.TestCase):
    TRANSFORMS = (Matrix.CreateTranslation(0.0, 0.0, 0.0),
                  Matrix.CreateTranslation(2.0, 0.0, 0.0),
                  Matrix.CreateTranslation(4.0, 0.0, 0.0))

    def _renderer(self, body):
        def run(game, device, observed):
            part = _mesh_part(device, with_buffers=True)
            try:
                with InstancedRenderer(device, part) as renderer:
                    body(renderer, part, device, observed)
            finally:
                part.VertexBuffer.Dispose()
                part.IndexBuffer.Dispose()

        return in_game(run)

    def test_a_mesh_part_with_no_buffers_is_refused(self) -> None:
        def body(game, device, out):
            try:
                InstancedRenderer(device, _mesh_part()).close()
                out["raised"] = None
            except EngineError as error:
                out["raised"] = type(error).__name__

        self.assertIsNotNone(in_game(body)["raised"])

    def test_the_renderer_keeps_the_caller_s_own_mesh_part(self) -> None:
        def body(renderer, part, device, out):
            out["same"] = renderer.part is part

        self.assertTrue(self._renderer(body)["same"])

    def test_the_instance_list_reads_back_and_the_buffer_grows_once(self) -> None:
        def body(renderer, part, device, out):
            out["empty"] = (renderer.instance_count, renderer.instance_capacity)
            renderer.set_instances(self.TRANSFORMS)
            out["three"] = (renderer.instance_count, renderer.instance_capacity)
            renderer.set_instances(self.TRANSFORMS[:2])
            out["two"] = (renderer.instance_count, renderer.instance_capacity)

        observed = self._renderer(body)
        self.assertEqual(observed["empty"], (0, 0))
        self.assertEqual(observed["three"], (3, 3))
        # Fewer instances reuse the buffer rather than shrinking it.
        self.assertEqual(observed["two"][0], 2)
        self.assertGreaterEqual(observed["two"][1], 3)

    def test_tints_are_off_until_they_are_asked_for(self) -> None:
        def body(renderer, part, device, out):
            out["default"] = renderer.tints_enabled
            renderer.set_instances(self.TRANSFORMS)
            renderer.set_instance_tints((Color.Red, Color.Green, Color.Blue))
            renderer.tints_enabled = True
            out["enabled"] = renderer.tints_enabled
            # Fewer tints than instances is allowed; the rest are white.
            renderer.set_instance_tints((Color.Red,))
            out["still_enabled"] = renderer.tints_enabled
            renderer.tints_enabled = False
            out["disabled"] = renderer.tints_enabled

        observed = self._renderer(body)
        self.assertFalse(observed["default"])
        self.assertTrue(observed["enabled"])
        self.assertTrue(observed["still_enabled"])
        self.assertFalse(observed["disabled"])

    def test_drawing_nothing_issues_no_draw_call(self) -> None:
        def body(renderer, part, device, out):
            from Microsoft.Xna.Framework.Graphics import BasicEffect

            effect = BasicEffect(device)
            try:
                renderer.draw(effect)
                out["calls"] = renderer.last_draw_call_count
                out["instanced"] = renderer.did_last_draw_instance
            finally:
                effect.Dispose()

        observed = self._renderer(body)
        self.assertEqual(observed["calls"], 0)
        self.assertFalse(observed["instanced"])

    def test_the_draw_call_count_says_which_path_ran(self) -> None:
        """One call when instancing ran, one per instance when the fallback did."""
        def body(renderer, part, device, out):
            from Microsoft.Xna.Framework.Graphics import BasicEffect

            renderer.set_instances(self.TRANSFORMS)
            effect = BasicEffect(device)
            try:
                out["supported"] = renderer.is_instancing_supported
                renderer.draw(effect)
                out["calls"] = renderer.last_draw_call_count
                out["instanced"] = renderer.did_last_draw_instance
            finally:
                effect.Dispose()

        observed = self._renderer(body)
        if observed["supported"]:
            self.assertEqual(observed["calls"], 1)
            self.assertTrue(observed["instanced"])
        else:
            self.assertEqual(observed["calls"], len(self.TRANSFORMS))
            self.assertFalse(observed["instanced"])

    def test_the_fallback_is_on_by_default_and_can_be_turned_off(self) -> None:
        def body(renderer, part, device, out):
            out["default"] = renderer.fallback_enabled
            renderer.fallback_enabled = False
            out["off"] = renderer.fallback_enabled
            renderer.fallback_enabled = True
            out["on"] = renderer.fallback_enabled

        observed = self._renderer(body)
        self.assertIs(type(observed["default"]), bool)
        self.assertFalse(observed["off"])
        self.assertTrue(observed["on"])

    def test_it_refuses_the_wrong_kind_of_argument(self) -> None:
        def body(renderer, part, device, out):
            for call in (lambda: renderer.draw(object()),
                         lambda: renderer.set_instance_tints((object(),))):
                try:
                    call()
                    out.setdefault("results", []).append("no error")
                except TypeError:
                    out.setdefault("results", []).append("TypeError")

        self.assertEqual(self._renderer(body)["results"], ["TypeError"] * 2)

    def test_closing_it_releases_the_native_part_it_projected(self) -> None:
        def body(game, device, out):
            part = _mesh_part(device, with_buffers=True)
            try:
                renderer = InstancedRenderer(device, part)
                renderer.close()
                renderer.close()
                out["closed"] = renderer.is_closed
            finally:
                part.VertexBuffer.Dispose()
                part.IndexBuffer.Dispose()

        self.assertTrue(in_game(body)["closed"])


@requires_engine_gpu
class GpuInstanceCullerTests(unittest.TestCase):
    def _culler(self, body):
        def run(game, device, observed):
            with GpuInstanceCuller(device) as culler:
                body(culler, device, observed)

        return in_game(run)

    def test_it_reports_which_capability_is_missing(self) -> None:
        def body(culler, device, out):
            out.update(supported=culler.is_supported,
                       reason=culler.unsupported_reason)

        observed = self._culler(body)
        if observed["supported"]:
            self.assertEqual(observed["reason"], "")
        else:
            self.assertTrue(observed["reason"],
                            "an unsupported culler must say which capability is missing")

    def test_the_default_instance_has_a_zero_world_and_not_an_identity(self) -> None:
        """ENGINE-008, pinned so it fails the day CNA fixes it.

        ``engine_layer.h`` says the defaults are "an identity world and an empty
        box". The world comes back all zero, which collapses every vertex of
        every instance onto the origin. Handed back as CNA gives it, because
        ``default()`` reports CNA's defaults rather than substituting sensible
        ones.
        """
        instance = GpuCullableInstance.default()
        self.assertEqual(list(instance.world), [0.0] * 16)
        self.assertNotEqual(list(instance.world), list(Matrix.Identity))
        self.assertIsInstance(instance.bounds, BoundingBox)
        self.assertEqual(tuple(instance.bounds.Min), tuple(instance.bounds.Max))

    def test_instances_upload_and_count(self) -> None:
        from dataclasses import replace

        def body(culler, device, out):
            if not culler.is_supported:
                out["skipped"] = True
                return
            instances = tuple(
                replace(GpuCullableInstance.default(),
                        world=Matrix.CreateTranslation(float(x) * 3.0, 0.0, -6.0),
                        bounds=BoundingBox(Vector3(x * 3.0 - 1.0, -1.0, -7.0),
                                           Vector3(x * 3.0 + 1.0, 1.0, -5.0)))
                for x in range(4))
            out["before"] = culler.instance_count
            culler.set_instances(instances)
            out["after"] = culler.instance_count

        observed = self._culler(body)
        if not observed.get("skipped"):
            self.assertEqual(observed["before"], 0)
            self.assertEqual(observed["after"], 4)

    def test_culling_keeps_the_instances_a_cpu_frustum_test_keeps(self) -> None:
        """The two paths answer the same question, so they are compared."""
        from dataclasses import replace

        boxes = tuple(BoundingBox(Vector3(x * 6.0 - 1.0, -1.0, -7.0),
                                  Vector3(x * 6.0 + 1.0, 1.0, -5.0))
                      for x in range(-2, 3))

        def body(culler, device, out):
            if not culler.is_supported:
                out["skipped"] = True
                return
            culler.set_instances(tuple(
                replace(GpuCullableInstance.default(),
                        world=Matrix.CreateTranslation(box.Min.X + 1.0, 0.0, -6.0),
                        bounds=box)
                for box in boxes))
            culler.cull(VIEW, PROJECTION, 3, 0, 0)
            out["visible"] = culler.read_visible_count()

        observed = self._culler(body)
        if not observed.get("skipped"):
            planes = oracle.frustum_planes(Matrix.Multiply(VIEW, PROJECTION))
            expected = sum(1 for box in boxes
                           if oracle.box_is_visible(planes, box.Min, box.Max))
            self.assertEqual(observed["visible"], expected)
            self.assertGreater(expected, 0, "the fixture must not cull everything")
            self.assertLess(expected, len(boxes),
                            "the fixture must not keep everything either")

    def test_culling_nothing_leaves_nothing_visible(self) -> None:
        def body(culler, device, out):
            if not culler.is_supported:
                out["skipped"] = True
                return
            culler.set_instances(())
            culler.cull(VIEW, PROJECTION, 3, 0, 0)
            out["visible"] = culler.read_visible_count()

        observed = self._culler(body)
        if not observed.get("skipped"):
            self.assertEqual(observed["visible"], 0)

    def test_an_index_count_that_is_not_positive_is_refused(self) -> None:
        def body(culler, device, out):
            if not culler.is_supported:
                out["skipped"] = True
                return
            for arguments in ((0, 0, 0), (3, -1, 0), (3, 0, -1)):
                try:
                    culler.cull(VIEW, PROJECTION, *arguments)
                    out[arguments] = None
                except EngineError as error:
                    out[arguments] = type(error).__name__

        observed = self._culler(body)
        if not observed.get("skipped"):
            for key, value in observed.items():
                if isinstance(key, tuple):
                    self.assertIsNotNone(value, key)

    def test_it_refuses_something_that_is_not_a_cullable_instance(self) -> None:
        def body(culler, device, out):
            try:
                culler.set_instances((object(),))
                out["raised"] = None
            except TypeError:
                out["raised"] = "TypeError"

        self.assertEqual(self._culler(body)["raised"], "TypeError")

    def test_the_storage_binding_is_a_measured_constant(self) -> None:
        self.assertIsInstance(GPU_INSTANCE_STORAGE_BINDING, int)
        self.assertGreaterEqual(GPU_INSTANCE_STORAGE_BINDING, 0)


@requires_engine_gpu
class IndirectDrawTests(unittest.TestCase):
    @staticmethod
    def _prepared(device):
        """A bound vertex buffer, a bound index buffer and an applied effect."""
        from Microsoft.Xna.Framework.Graphics import (
            BasicEffect, BufferUsage, IndexBuffer, IndexElementSize, VertexBuffer,
            VertexPositionColor,
        )

        vertices = VertexBuffer(device, VertexPositionColor, 3, BufferUsage.WriteOnly)
        vertices.SetData([VertexPositionColor(Vector3(0.0, 0.0, 0.0), Color.White),
                          VertexPositionColor(Vector3(1.0, 0.0, 0.0), Color.White),
                          VertexPositionColor(Vector3(0.0, 1.0, 0.0), Color.White)])
        indices = IndexBuffer(device, IndexElementSize.SixteenBits, 3,
                              BufferUsage.WriteOnly)
        indices.SetData([0, 1, 2])
        effect = BasicEffect(device)
        device.SetVertexBuffer(vertices)
        device.Indices = indices
        effect.CurrentTechnique.Passes[0].Apply()
        return vertices, indices, effect

    def test_both_indirect_draws_read_their_counts_from_a_storage_buffer(self) -> None:
        def body(game, device, out):
            from Microsoft.Xna.Framework.Graphics import PrimitiveType

            vertices, indices, effect = self._prepared(device)
            try:
                arguments = IndirectDrawArguments(3, 1, 0, 0)
                with StorageBuffer(device, len(arguments.pack())) as buffer:
                    buffer.write(arguments.pack())
                    draw_primitives_indirect(device, PrimitiveType.TriangleList, buffer)
                    out["plain"] = True
                indexed = IndirectDrawIndexedArguments(3, 1, 0, 0, 0)
                with StorageBuffer(device, len(indexed.pack())) as buffer:
                    buffer.write(indexed.pack())
                    draw_indexed_primitives_indirect(device, PrimitiveType.TriangleList,
                                                     buffer)
                    out["indexed"] = True
            finally:
                device.Indices = None
                device.SetVertexBuffer(None)
                effect.Dispose()
                indices.Dispose()
                vertices.Dispose()

        observed = in_game(body)
        self.assertTrue(observed["plain"])
        self.assertTrue(observed["indexed"])

    def test_it_refuses_a_draw_with_no_vertex_buffer_or_no_effect(self) -> None:
        """Measured: CNA names which piece of state is missing rather than
        drawing nothing."""
        def body(game, device, out):
            from Microsoft.Xna.Framework.Graphics import (
                BufferUsage, VertexBuffer, VertexPositionColor, PrimitiveType,
            )

            arguments = IndirectDrawArguments(3, 1, 0, 0)
            with StorageBuffer(device, len(arguments.pack())) as buffer:
                buffer.write(arguments.pack())
                try:
                    draw_primitives_indirect(device, PrimitiveType.TriangleList, buffer)
                    out["no_state"] = None
                except EngineError as error:
                    out["no_state"] = str(error)
                vertices = VertexBuffer(device, VertexPositionColor, 3,
                                        BufferUsage.WriteOnly)
                try:
                    device.SetVertexBuffer(vertices)
                    try:
                        draw_primitives_indirect(device, PrimitiveType.TriangleList,
                                                 buffer)
                        out["no_effect"] = None
                    except EngineError as error:
                        out["no_effect"] = str(error)
                finally:
                    device.SetVertexBuffer(None)
                    vertices.Dispose()

        observed = in_game(body)
        self.assertIn("no vertex buffer", observed["no_state"])
        self.assertIn("no effect", observed["no_effect"])

    def test_a_negative_offset_is_refused(self) -> None:
        from Microsoft.Xna.Framework.Graphics import PrimitiveType

        def body(game, device, out):
            with StorageBuffer(device, 32) as buffer:
                try:
                    draw_primitives_indirect(device, PrimitiveType.TriangleList,
                                             buffer, -4)
                    out["raised"] = None
                except EngineError as error:
                    out["raised"] = type(error).__name__

        self.assertIsNotNone(in_game(body)["raised"])

    def test_it_refuses_something_that_is_not_a_storage_buffer(self) -> None:
        from Microsoft.Xna.Framework.Graphics import PrimitiveType

        def body(game, device, out):
            for call in (lambda: draw_primitives_indirect(
                             device, PrimitiveType.TriangleList, object()),
                         lambda: draw_indexed_primitives_indirect(
                             device, PrimitiveType.TriangleList, object())):
                try:
                    call()
                    out.setdefault("results", []).append("no error")
                except TypeError:
                    out.setdefault("results", []).append("TypeError")

        self.assertEqual(in_game(body)["results"], ["TypeError"] * 2)


class CullingAbsenceTests(unittest.TestCase):
    """What the family answers on a build with no engine layer at all."""

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_every_route_that_needs_the_layer_says_so(self) -> None:
        for name, call in (("LodGroup", LodGroup),
                           ("FrustumCuller", FrustumCuller),
                           ("instance_vertex_stride", instance_vertex_stride),
                           ("tint_vertex_stride", tint_vertex_stride),
                           ("instance_lookup_glsl", instance_lookup_glsl),
                           ("instance_vertex_elements", instance_vertex_elements)):
            with self.subTest(name), self.assertRaises(EngineUnavailableError):
                call()

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_the_indirect_draw_arguments_still_fill_their_defaults(self) -> None:
        """Documented as answering in every build, and measured to."""
        self.assertEqual(IndirectDrawArguments.default().instance_count, 0)
        self.assertEqual(IndirectDrawIndexedArguments.default().index_count, 0)
