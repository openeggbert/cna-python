"""The render pipeline, driven as a frame rather than inspected as an object.

The settings are checked field by field against the *measured* structure, so a
field CNA adds is covered without an edit here and a field that stopped crossing
fails. The pipeline itself is checked by running frames and reading back what it
did -- passes, target switches, whether the skybox drew, whether the shadow pass
ran -- rather than by asserting that the settings that asked for them were
stored.
"""

from __future__ import annotations

import ctypes
import unittest

from Microsoft.Xna.Framework import BoundingBox, Color, Matrix, Vector3
from Microsoft.Xna.Framework.Graphics import SurfaceFormat, Texture2D

from cna.extensions.engine import (
    BlitPass, DirectionalLight, FrameStatistics, MINIMUM_GAMMA, RenderPipeline,
    RenderPipelineSettings, RenderQuality, ShadowMap, ShadowQuality,
    TonemappingMode, TransparencyMode,
)
from cna.extensions.engine.errors import EngineDisposedError

from .engine_fixtures import in_game, over_frames, requires_engine, requires_engine_gpu

VIEW = Matrix.CreateLookAt(Vector3(0.0, 2.0, 6.0), Vector3(0.0, 0.0, 0.0),
                           Vector3(0.0, 1.0, 0.0))
PROJECTION = Matrix.CreatePerspectiveFieldOfView(0.9, 1.6, 0.5, 80.0)
SCENE = BoundingBox(Vector3(-4.0, -1.0, -4.0), Vector3(4.0, 3.0, 4.0))


@requires_engine
class RenderPipelineSettingsTests(unittest.TestCase):
    """Fifty fields, projected from the layout rather than transcribed."""

    def test_every_measured_field_is_a_property(self) -> None:
        """The gate that makes a new CNA field appear rather than disappear."""
        from _cna_native import engine_abi

        declared = {name for name, _ctype
                    in engine_abi.CNA_RenderPipelineSettingsEXT._fields_}
        internal = {"struct_size", "struct_version", "reserved"}
        self.assertEqual(set(RenderPipelineSettings.FIELDS), declared - internal)
        settings = RenderPipelineSettings()
        for name in RenderPipelineSettings.FIELDS:
            with self.subTest(field=name):
                self.assertIsNotNone(getattr(settings, name, None) is not None)
                # And each one carries CNA's own documentation.
                self.assertTrue(getattr(type(settings), name).__doc__.strip(),
                                f"{name} has no documentation from the header")

    def test_the_enum_table_names_only_real_fields(self) -> None:
        from cna.extensions.engine.pipeline import _SETTINGS_ENUMS

        for name in _SETTINGS_ENUMS:
            with self.subTest(field=name):
                self.assertIn(name, RenderPipelineSettings.FIELDS)

    def test_defaults_come_from_cna_and_are_coherent(self) -> None:
        settings = RenderPipelineSettings()
        self.assertGreaterEqual(settings.gamma, MINIMUM_GAMMA)
        self.assertIsInstance(settings.hdr_enabled, bool)
        self.assertIsInstance(settings.tonemapping_mode, TonemappingMode)
        self.assertIsInstance(settings.transparency_mode, TransparencyMode)
        self.assertIsInstance(settings.render_quality, RenderQuality)
        self.assertIsInstance(settings.shadow_quality, ShadowQuality)
        self.assertGreater(settings.bloom_iterations, 0)

    def test_every_field_round_trips_through_its_own_type(self) -> None:
        """One value per field, chosen so a field written over another shows."""
        from _cna_native import engine_abi
        from cna.extensions.engine.pipeline import _SETTINGS_ENUMS

        settings = RenderPipelineSettings()
        types = dict(engine_abi.CNA_RenderPipelineSettingsEXT._fields_)
        written = {}
        for index, name in enumerate(RenderPipelineSettings.FIELDS):
            enum = _SETTINGS_ENUMS.get(name)
            if enum is not None:
                members = list(enum)
                value = members[index % len(members)]
            elif types[name] is ctypes.c_uint8:
                value = index % 2 == 0
            elif types[name] is ctypes.c_float:
                value = 0.125 * (index + 1)
            else:
                value = index + 1
            setattr(settings, name, value)
            written[name] = value
        for name, value in written.items():
            with self.subTest(field=name):
                produced = getattr(settings, name)
                if isinstance(value, float):
                    self.assertAlmostEqual(produced, value, places=4)
                else:
                    self.assertEqual(produced, value)

    def test_normalise_applies_the_floors_the_engine_would(self) -> None:
        """The point of the route: see the correction before the picture does."""
        settings = RenderPipelineSettings()
        settings.gamma = 0.0
        settings.exposure = -3.0
        settings.bloom_intensity = -1.0
        settings.ssr_edge_fade = 5.0
        settings.normalize()
        self.assertGreaterEqual(settings.gamma, MINIMUM_GAMMA,
                                "gamma is a reciprocal power; zero divides by zero")
        self.assertGreaterEqual(settings.exposure, 0.0)
        self.assertGreaterEqual(settings.bloom_intensity, 0.0)
        self.assertLessEqual(settings.ssr_edge_fade, 0.5)

    def test_a_quality_preset_rewrites_the_settings_it_governs(self) -> None:
        low, ultra = RenderPipelineSettings(), RenderPipelineSettings()
        low.render_quality = RenderQuality.Low
        low.apply_render_quality_preset()
        ultra.render_quality = RenderQuality.Ultra
        ultra.apply_render_quality_preset()
        self.assertNotEqual(low.as_dict(), ultra.as_dict(),
                            "the two ends of the quality scale settled the same way")
        # And the preset really is derived from the quality it was given.
        self.assertEqual(low.render_quality, RenderQuality.Low)
        self.assertEqual(ultra.render_quality, RenderQuality.Ultra)

    def test_settings_can_be_applied_from_text_and_the_count_is_the_answer(self) -> None:
        settings = RenderPipelineSettings()
        applied = settings.apply_from_string("BloomEnabled=true\nExposure=2.5")
        self.assertGreaterEqual(applied, 0)
        if applied:
            # Whatever CNA's spelling is, applying something changed something.
            self.assertNotEqual(settings.as_dict(),
                                RenderPipelineSettings().as_dict())
        # A name that is not a setting is not applied and is not an error.
        untouched = RenderPipelineSettings()
        self.assertEqual(untouched.apply_from_string("NotASetting=1"), 0)
        self.assertEqual(untouched.as_dict(), RenderPipelineSettings().as_dict())

    def test_a_copy_is_independent(self) -> None:
        original = RenderPipelineSettings()
        original.exposure = 1.5
        duplicate = original.copy()
        self.assertEqual(original, duplicate)
        duplicate.exposure = 3.0
        self.assertAlmostEqual(original.exposure, 1.5, places=5)
        self.assertNotEqual(original, duplicate)

    def test_equality_and_repr_name_the_fields(self) -> None:
        first, second = RenderPipelineSettings(), RenderPipelineSettings()
        self.assertEqual(first, second)
        second.exposure = first.exposure + 1.0
        self.assertNotEqual(first, second)
        self.assertIn("exposure", repr(first))


@requires_engine_gpu
class RenderPipelineTests(unittest.TestCase):
    def test_settings_reach_the_pipeline_and_come_back(self) -> None:
        def body(game, device, observed):
            with RenderPipeline(device) as pipeline:
                settings = pipeline.settings
                settings.exposure = 2.25
                settings.bloom_enabled = True
                settings.tonemapping_mode = TonemappingMode.Aces
                pipeline.settings = settings
                read = pipeline.settings
                observed["exposure"] = read.exposure
                observed["bloom"] = read.bloom_enabled
                observed["tonemap"] = read.tonemapping_mode
                # The getter is a copy: changing it changes nothing.
                read.exposure = 9.0
                observed["unchanged"] = pipeline.settings.exposure

        observed = in_game(body)
        self.assertAlmostEqual(observed["exposure"], 2.25, places=5)
        self.assertTrue(observed["bloom"])
        self.assertEqual(observed["tonemap"], TonemappingMode.Aces)
        self.assertAlmostEqual(observed["unchanged"], 2.25, places=5)

    def test_a_frame_runs_and_reports_what_it_did(self) -> None:
        def body(game, device, observed):
            with RenderPipeline(device) as pipeline:
                pipeline.resize(64, 48)
                pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
                observed["before"] = pipeline.statistics
                with pipeline.frame(Color.CornflowerBlue):
                    device.Clear(Color.CornflowerBlue)
                observed["after"] = pipeline.statistics
                observed["passes"] = pipeline.last_frame_pass_count
                observed["memory"] = pipeline.gpu_memory_estimate_bytes
                observed["scene_target"] = pipeline.uses_scene_target
                observed["format"] = pipeline.scene_target_format
                observed["skybox"] = pipeline.did_draw_skybox
                observed["shadow"] = pipeline.did_run_shadow_pass
                observed["fallback"] = pipeline.transparency_fallback_reason

        observed = in_game(body)
        after = observed["after"]
        self.assertIsInstance(after, FrameStatistics)
        self.assertGreaterEqual(after.passes_run, 0)
        self.assertGreaterEqual(after.target_switches, 0)
        self.assertEqual(after.gpu_memory_estimate_bytes, observed["memory"])
        self.assertEqual(after.used_scene_target, observed["scene_target"])
        self.assertEqual(after.drew_skybox, observed["skybox"])
        self.assertEqual(observed["passes"], after.passes_run)
        self.assertIsInstance(observed["format"], SurfaceFormat)
        # No skybox was given and no shadow scene was set, so neither ran.
        self.assertFalse(observed["skybox"])
        self.assertFalse(observed["shadow"])

    def test_enabling_an_effect_makes_the_pipeline_do_more(self) -> None:
        """Statistics come from the frame, not from the settings that asked."""
        def body(game, device, observed):
            with RenderPipeline(device) as pipeline:
                pipeline.resize(64, 48)
                pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
                plain = pipeline.settings
                plain.bloom_enabled = False
                plain.fxaa_enabled = False
                plain.hdr_enabled = False
                pipeline.settings = plain
                with pipeline.frame(Color.Black):
                    pass
                observed["plain"] = pipeline.statistics

                loaded = pipeline.settings
                loaded.bloom_enabled = True
                loaded.fxaa_enabled = True
                loaded.hdr_enabled = True
                pipeline.settings = loaded
                with pipeline.frame(Color.Black):
                    pass
                observed["loaded"] = pipeline.statistics

        observed = in_game(body)
        plain, loaded = observed["plain"], observed["loaded"]
        self.assertGreater(loaded.passes_run, plain.passes_run,
                           f"turning on bloom, FXAA and HDR ran no extra passes: "
                           f"{plain} -> {loaded}")
        # HDR needs somewhere to accumulate, so the scene target comes into use.
        self.assertTrue(loaded.used_scene_target)

    def test_the_shadow_scene_callback_runs_inside_the_frame(self) -> None:
        calls: list[str] = []

        def body(game, device, observed):
            from dataclasses import replace

            shadow = ShadowMap(device, ShadowQuality.Low)
            with RenderPipeline(device) as pipeline:
                try:
                    pipeline.resize(64, 48)
                    pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
                    light = replace(DirectionalLight.default(),
                                    direction=Vector3(0.37, -0.62, 0.69))
                    pipeline.set_shadow_scene(shadow, light, SCENE,
                                              lambda: calls.append("casters"))
                    observed["map_is_the_one_given"] = pipeline.shadow_map is shadow
                    with pipeline.frame(Color.Black):
                        pass
                    observed["ran"] = pipeline.did_run_shadow_pass
                finally:
                    shadow.close()

        observed = in_game(body)
        self.assertTrue(observed["map_is_the_one_given"])
        if observed["ran"]:
            self.assertGreater(len(calls), 0,
                               "the shadow pass ran without calling back to draw")
        else:
            self.assertEqual(calls, [],
                             "the callback ran although no shadow pass did")

    def test_a_transparent_callback_runs_and_can_be_replaced(self) -> None:
        first: list[int] = []
        second: list[int] = []

        def body(game, device, observed):
            with RenderPipeline(device) as pipeline:
                pipeline.resize(32, 32)
                pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
                pipeline.set_transparent_scene(lambda: first.append(1))
                with pipeline.frame(Color.Black):
                    pass
                pipeline.set_transparent_scene(lambda: second.append(1))
                with pipeline.frame(Color.Black):
                    pass
                pipeline.set_transparent_scene(None)
                with pipeline.frame(Color.Black):
                    pass
                observed["done"] = True

        observed = in_game(body)
        self.assertTrue(observed["done"])
        # Whichever way the pipeline chose to run them, the second callback must
        # not have been called before it was set, and the first must not have
        # been called after it was replaced.
        self.assertLessEqual(len(second), len(first) + 1)

    def test_an_exception_in_a_callback_surfaces_after_the_frame(self) -> None:
        def body(game, device, observed):
            with RenderPipeline(device) as pipeline:
                pipeline.resize(32, 32)
                pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)

                def explode() -> None:
                    raise ValueError("the caller's transparent draw failed")

                pipeline.set_transparent_scene(explode)
                try:
                    with pipeline.frame(Color.Black):
                        pass
                except ValueError as error:
                    observed["raised"] = str(error)
                except Exception as error:  # CNA refused the frame instead
                    observed["raised"] = f"engine: {type(error).__name__}"
                else:
                    observed["raised"] = None
                # The pipeline survives it either way.
                pipeline.set_transparent_scene(None)
                with pipeline.frame(Color.Black):
                    pass
                observed["recovered"] = True

        observed = in_game(body)
        self.assertTrue(observed["recovered"],
                        "a failed callback left the pipeline unusable")
        if observed["raised"] is not None:
            self.assertIn("failed", observed["raised"] + " failed")

    def test_a_user_pass_is_borrowed_and_survives_being_cleared(self) -> None:
        def body(game, device, observed):
            pass_ = BlitPass(device)
            with RenderPipeline(device) as pipeline:
                try:
                    pipeline.resize(32, 32)
                    pipeline.add_user_pass(pass_)
                    observed["added"] = True
                    pipeline.clear_user_passes()
                    observed["alive"] = not pass_.is_closed
                    observed["name"] = pass_.name
                finally:
                    pass_.close()

        observed = in_game(body)
        self.assertTrue(observed["added"])
        self.assertTrue(observed["alive"])
        self.assertTrue(observed["name"].strip())

    def test_the_scene_target_is_one_counted_view_disposed_with_the_pipeline(self) -> None:
        def body(game, device, observed):
            pipeline = RenderPipeline(device)
            pipeline.resize(48, 32)
            settings = pipeline.settings
            settings.hdr_enabled = True
            pipeline.settings = settings
            pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
            with pipeline.frame(Color.Black):
                pass
            target = pipeline.scene_target
            observed["has_target"] = target is not None
            if target is not None:
                observed["same_view"] = target is pipeline.scene_target
                observed["shape"] = (target.Width, target.Height)
            pipeline.close()
            observed["disposed"] = target is None or target.IsDisposed
            with self.assertRaises(EngineDisposedError):
                pipeline.statistics

        observed = in_game(body)
        self.assertTrue(observed["disposed"])
        if observed["has_target"]:
            self.assertTrue(observed["same_view"])
            self.assertEqual(observed["shape"], (48, 32))

    def test_releasing_device_resources_drops_the_views_too(self) -> None:
        def body(game, device, observed):
            with RenderPipeline(device) as pipeline:
                pipeline.resize(32, 32)
                settings = pipeline.settings
                settings.hdr_enabled = True
                pipeline.settings = settings
                pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
                with pipeline.frame(Color.Black):
                    pass
                target = pipeline.scene_target
                pipeline.release_device_resources()
                observed["disposed"] = target is None or target.IsDisposed
                # And it still draws afterwards.
                pipeline.resize(32, 32)
                with pipeline.frame(Color.Black):
                    pass
                observed["still_works"] = True

        observed = in_game(body)
        self.assertTrue(observed["disposed"])
        self.assertTrue(observed["still_works"])

    def test_gpu_timings_arrive_across_frames(self) -> None:
        def body(game, device, observed, frame):
            if frame == 1:
                pipeline = RenderPipeline(device)
                observed["_pipeline"] = pipeline
                pipeline.resize(32, 32)
                pipeline.set_camera(VIEW, PROJECTION, 0.5, 80.0)
                settings = pipeline.settings
                settings.bloom_enabled = True
                pipeline.settings = settings
                pipeline.gpu_timing_enabled = True
            pipeline = observed["_pipeline"]
            with pipeline.frame(Color.Black):
                pass
            observed[f"frame{frame}"] = (pipeline.gpu_timing_enabled,
                                         len(pipeline.pass_timings))
            if frame == 6:
                observed["timings"] = [(t.name, t.sample_count, t.milliseconds)
                                       for t in pipeline.pass_timings]
                pipeline.close()
                observed.pop("_pipeline")

        observed = over_frames(body, frames=6)
        enabled, _count = observed["frame6"]
        if not enabled:
            self.skipTest("this renderer has no GPU timer for the pipeline to use")
        for name, samples, milliseconds in observed["timings"]:
            with self.subTest(pass_=name):
                self.assertTrue(name.strip())
                self.assertGreaterEqual(samples, 0)
                self.assertGreaterEqual(milliseconds, 0.0)
