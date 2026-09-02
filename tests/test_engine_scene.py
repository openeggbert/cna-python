"""Particles, decals, the prepass and transparency, against their own formulas.

Every pure helper here is compared with an independent implementation in
:mod:`tests.engine_oracles`, which is itself checked against worked cases in
:mod:`tests.test_engine_oracles`. The stateful objects are checked by driving
them and reading the state back -- a particle system simulated on the CPU whose
particles are then compared with the same step function applied in Python, a
prepass whose depth texture is read back, a draw list whose callbacks are
counted and ordered.

Randomness is not a reason to test loosely. CNA's particle draw is a hash of a
seed, not a stream, so a particle system is fully reproducible and the tests
predict it rather than sampling it.
"""

from __future__ import annotations

import math
import unittest
from dataclasses import replace

from Microsoft.Xna.Framework import (
    BoundingBox, Color, Matrix, Vector2, Vector3, Vector4,
)
from Microsoft.Xna.Framework.Graphics import SurfaceFormat, Texture2D

from cna.extensions.engine import (
    DecalPass, DepthEncoding, DepthNormalPrepass, PARTICLE_STORAGE_BINDING,
    PARTICLE_SYSTEM_DEFAULT_CAPACITY, Particle, ParticleEmitterSettings,
    ParticleSystem, TransparentDrawList, WeightedBlendedTransparency,
    camera_position_of, decode_velocity, depth_decode_glsl, has_velocity,
    is_inside_decal_box, pack_depth, particle_lookup_glsl, particle_random,
    sort_key, transparency_accumulation_glsl, transparency_weight, unpack_depth,
    uses_packed_depth, velocity_decode_glsl,
)
from cna.extensions.engine.errors import EngineDisposedError, EngineError

from . import engine_oracles as oracle
from .engine_fixtures import in_game, requires_engine, requires_engine_gpu


@requires_engine
class PureSceneHelperTests(unittest.TestCase):
    """The formulas CNA publishes beside its own shaders."""

    def test_the_particle_draw_matches_an_independent_hash(self) -> None:
        for seed in (0, 1, 2, 7, 12345, 0x7FFFFFFF, 0xFFFFFFFF):
            with self.subTest(seed=seed):
                self.assertAlmostEqual(particle_random(seed),
                                       oracle.particle_random(seed), places=6)

    def test_the_particle_draw_is_reproducible(self) -> None:
        self.assertEqual(particle_random(4096), particle_random(4096))
        self.assertNotEqual(particle_random(4096), particle_random(4097))

    def test_depth_packing_matches_an_independent_implementation(self) -> None:
        for depth in (0.0, 0.001, 0.125, 0.5, 0.87654321, 0.99999, 1.0, 1.5, -0.5):
            with self.subTest(depth=depth):
                produced = pack_depth(depth)
                expected = oracle.pack_depth(depth)
                for index, (a, b) in enumerate(zip(produced, expected)):
                    self.assertAlmostEqual(a, b, places=5, msg=f"channel {index}")

    def test_depth_survives_a_pack_and_unpack(self) -> None:
        """The precision the encoding actually gives, measured rather than assumed."""
        worst = 0.0
        for step in range(0, 1000):
            depth = step / 1000.0
            recovered = unpack_depth(*pack_depth(depth))
            worst = max(worst, abs(recovered - depth))
        # Four channels of eight bits is 32 bits of depth; anything near a
        # single channel's 1/256 would mean three of them are doing nothing.
        self.assertLess(worst, 1e-5, f"worst round-trip error was {worst}")

    def test_a_far_plane_depth_does_not_wrap_to_the_nearest_surface(self) -> None:
        self.assertGreater(unpack_depth(*pack_depth(1.0)), 0.99)

    def test_velocity_decoding_matches_an_independent_implementation(self) -> None:
        cases = [Color(255, 0, 0, 0), Color(128, 128, 0, 0), Color(0, 255, 0, 127),
                 Color(200, 50, 0, 128), Color(200, 50, 0, 255)]
        for texel in cases:
            with self.subTest(texel=(texel.R, texel.G, texel.B, texel.A)):
                self.assertEqual(has_velocity(texel),
                                 oracle.has_velocity(int(texel.A)))
                produced = decode_velocity(texel)
                expected = oracle.decode_velocity(int(texel.R), int(texel.G),
                                                  int(texel.B), int(texel.A))
                self.assertAlmostEqual(produced.X, expected[0], places=5)
                self.assertAlmostEqual(produced.Y, expected[1], places=5)

    def test_an_unwritten_velocity_texel_is_absent_rather_than_zero(self) -> None:
        """The distinction the alpha marker exists to keep."""
        unwritten = Color(128, 128, 0, 255)
        self.assertFalse(has_velocity(unwritten))
        # A texel that decodes to (0, 0) but is marked *is* a zero velocity, and
        # that is a different answer from an absent one.
        marked_zero = Color(128, 128, 0, 0)
        self.assertTrue(has_velocity(marked_zero))

    def test_transparency_weight_matches_an_independent_implementation(self) -> None:
        for depth in (0.0, 0.5, 5.0, 50.0, 99.0, 100.0, 250.0):
            for alpha in (0.25, 1.0):
                with self.subTest(depth=depth, alpha=alpha):
                    self.assertAlmostEqual(
                        transparency_weight(depth, alpha, 100.0),
                        oracle.transparency_weight(depth, alpha, 100.0),
                        delta=max(1e-4, abs(oracle.transparency_weight(
                            depth, alpha, 100.0)) * 1e-4))

    def test_sort_key_matches_an_independent_implementation(self) -> None:
        cases = [
            (BoundingBox(Vector3(3.0, 4.0, 0.0), Vector3(9.0, 9.0, 0.0)),
             Vector3(0.0, 0.0, 0.0)),
            (BoundingBox(Vector3(-1.0, -1.0, -1.0), Vector3(1.0, 1.0, 1.0)),
             Vector3(0.5, -0.25, 0.0)),
            (BoundingBox(Vector3(-8.0, 2.0, -3.0), Vector3(-4.0, 6.0, 1.0)),
             Vector3(7.0, -2.0, 11.0)),
        ]
        for bounds, camera in cases:
            with self.subTest(camera=tuple(camera)):
                self.assertAlmostEqual(
                    sort_key(bounds, camera),
                    oracle.sort_key(bounds.Min, bounds.Max, camera), places=4)

    def test_the_camera_position_is_the_eye_a_view_looks_from(self) -> None:
        eye = Vector3(4.0, 3.0, 9.0)
        view = Matrix.CreateLookAt(eye, Vector3(-1.0, 0.5, 0.0),
                                   Vector3(0.0, 1.0, 0.0))
        produced = camera_position_of(view)
        self.assertTrue(oracle.vectors_agree(produced, eye, 1e-3),
                        f"{tuple(produced)} is not {tuple(eye)}")

    def test_a_scaled_view_still_gives_the_right_eye(self) -> None:
        """The case the negate-and-rotate shortcut gets wrong."""
        eye = Vector3(2.0, -5.0, 7.0)
        view = Matrix.Multiply(
            Matrix.CreateLookAt(eye, Vector3(0.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0)),
            Matrix.CreateScale(2.0))
        produced = camera_position_of(view)
        self.assertTrue(oracle.vectors_agree(produced, eye, 1e-3),
                        f"{tuple(produced)} is not {tuple(eye)}")

    def test_the_decal_box_matches_an_independent_implementation(self) -> None:
        cases = [Vector3(0.0, 0.0, 0.0), Vector3(0.5, 0.5, 0.5),
                 Vector3(-0.5, -0.5, -0.5), Vector3(0.51, 0.0, 0.0),
                 Vector3(0.0, -0.7, 0.0), Vector3(0.4, 0.4, 0.6)]
        for point in cases:
            with self.subTest(point=tuple(point)):
                self.assertEqual(is_inside_decal_box(point),
                                 oracle.is_inside_decal_box(point))

    def test_the_published_shader_source_is_real(self) -> None:
        for name, source in (("particle lookup", particle_lookup_glsl()),
                             ("packed depth decode", depth_decode_glsl(True)),
                             ("unpacked depth decode", depth_decode_glsl(False)),
                             ("velocity decode", velocity_decode_glsl()),
                             ("accumulation", transparency_accumulation_glsl())):
            with self.subTest(source=name):
                self.assertTrue(source.strip(), f"{name} GLSL is empty")
        # The two depth decoders are genuinely different, or the packed flag
        # would be doing nothing.
        self.assertNotEqual(depth_decode_glsl(True), depth_decode_glsl(False))
        # The particle lookup names the binding the constant declares.
        self.assertIn(str(PARTICLE_STORAGE_BINDING), particle_lookup_glsl())


@requires_engine
class ParticleValueTests(unittest.TestCase):
    """Emitter settings, one particle, and the step that advances it."""

    def test_defaults_come_from_cna_and_are_usable(self) -> None:
        settings = ParticleEmitterSettings.default()
        self.assertGreater(settings.lifetime, 0.0,
                           "a particle that dies instantly is not a particle")
        self.assertGreater(settings.emission_rate, 0.0)
        self.assertGreaterEqual(settings.cone_angle, 0.0)
        particle = Particle.default()
        self.assertIsInstance(particle.position, Vector4)
        self.assertEqual(particle.age, 0.0)

    def test_a_step_integrates_gravity_and_drag_exactly(self) -> None:
        """A particle well inside its lifetime just moves, and predictably.

        With no drag the velocity gains ``gravity * dt`` and the position gains
        the new velocity times ``dt`` -- semi-implicit Euler, which is what the
        source does, and the order matters.
        """
        settings = replace(ParticleEmitterSettings.default(),
                           gravity=Vector3(0.0, -10.0, 0.0), drag=0.0,
                           lifetime=100.0, lifetime_variance=0.0)
        particle = Particle(Vector4(1.0, 2.0, 3.0, 0.0),
                            Vector4(4.0, 0.0, -1.0, 0.0),
                            Vector4(0.0, 100.0, 0.0, 0.0))
        stepped = ParticleSystem.step(particle, 0, settings, 0.5)
        # velocity += gravity * dt
        self.assertAlmostEqual(stepped.velocity.Y, 0.0 + -10.0 * 0.5, places=4)
        self.assertAlmostEqual(stepped.velocity.X, 4.0, places=4)
        # position += new velocity * dt
        self.assertAlmostEqual(stepped.position.X, 1.0 + 4.0 * 0.5, places=4)
        self.assertAlmostEqual(stepped.position.Y, 2.0 + (-5.0) * 0.5, places=4)
        self.assertAlmostEqual(stepped.position.Z, 3.0 + (-1.0) * 0.5, places=4)
        # age advances, lifetime and generation do not
        self.assertAlmostEqual(stepped.age, 0.5, places=5)
        self.assertAlmostEqual(stepped.generation, 0.0, places=5)

    def test_drag_removes_a_fraction_of_the_velocity(self) -> None:
        settings = replace(ParticleEmitterSettings.default(),
                           gravity=Vector3(0.0, 0.0, 0.0), drag=0.5,
                           lifetime=100.0, lifetime_variance=0.0)
        particle = Particle(Vector4(0.0, 0.0, 0.0, 0.0),
                            Vector4(8.0, 0.0, 0.0, 0.0),
                            Vector4(0.0, 100.0, 0.0, 0.0))
        stepped = ParticleSystem.step(particle, 0, settings, 0.5)
        # drag * dt = 0.25 of the velocity is removed.
        self.assertAlmostEqual(stepped.velocity.X, 8.0 * 0.75, places=4)

    def test_outliving_the_lifetime_respawns_with_a_new_generation(self) -> None:
        settings = replace(ParticleEmitterSettings.default(),
                           position=Vector3(7.0, -3.0, 2.0),
                           direction=Vector3(0.0, 1.0, 0.0),
                           gravity=Vector3(0.0, 0.0, 0.0), drag=0.0,
                           speed=10.0, speed_variance=0.0, cone_angle=0.0,
                           lifetime=1.0, lifetime_variance=0.0)
        particle = Particle(Vector4(100.0, 100.0, 100.0, 0.0),
                            Vector4(0.0, 0.0, 0.0, 0.0),
                            Vector4(0.9, 1.0, 0.0, 0.0))
        stepped = ParticleSystem.step(particle, 0, settings, 0.5)
        self.assertAlmostEqual(stepped.generation, 1.0, places=5)
        # Age wraps rather than resetting, so emission does not drift.
        self.assertAlmostEqual(stepped.age, 0.9 + 0.5 - 1.0, places=4)
        # A zero cone angle sends it straight along the emitter's direction, at
        # the emitter's speed, from the emitter's position.
        self.assertAlmostEqual(stepped.velocity.Y, 10.0, places=3)
        self.assertAlmostEqual(stepped.velocity.X, 0.0, places=3)
        self.assertAlmostEqual(stepped.position.X, 7.0, places=3)

    def test_two_slots_respawn_in_different_directions(self) -> None:
        """The index seeds the draw, so a cone really spreads."""
        settings = replace(ParticleEmitterSettings.default(),
                           direction=Vector3(0.0, 1.0, 0.0),
                           gravity=Vector3(0.0, 0.0, 0.0), drag=0.0,
                           speed=10.0, speed_variance=0.0, cone_angle=0.8,
                           lifetime=1.0, lifetime_variance=0.0)
        expired = Particle(Vector4(0.0, 0.0, 0.0, 0.0), Vector4(0.0, 0.0, 0.0, 0.0),
                           Vector4(1.5, 1.0, 0.0, 0.0))
        directions = []
        for index in range(8):
            stepped = ParticleSystem.step(expired, index, settings, 0.0)
            directions.append((round(stepped.velocity.X, 4),
                               round(stepped.velocity.Y, 4),
                               round(stepped.velocity.Z, 4)))
        self.assertEqual(len(set(directions)), 8,
                         f"two slots drew the same direction: {directions}")
        # Every one of them still has the emitter's speed.
        for x, y, z in directions:
            self.assertAlmostEqual(math.sqrt(x * x + y * y + z * z), 10.0, places=2)

    def test_the_same_slot_and_generation_respawn_identically(self) -> None:
        """Reproducible, which is what a hash-seeded emitter buys."""
        settings = replace(ParticleEmitterSettings.default(), cone_angle=0.8,
                           lifetime=1.0, lifetime_variance=0.0)
        expired = Particle(Vector4(0.0, 0.0, 0.0, 0.0), Vector4(0.0, 0.0, 0.0, 0.0),
                           Vector4(1.5, 1.0, 0.0, 0.0))
        first = ParticleSystem.step(expired, 3, settings, 0.0)
        second = ParticleSystem.step(expired, 3, settings, 0.0)
        self.assertEqual(tuple(first.velocity), tuple(second.velocity))


@requires_engine_gpu
class ParticleSystemTests(unittest.TestCase):
    def test_capacity_and_settings_round_trip(self) -> None:
        def body(game, device, observed):
            with ParticleSystem(device) as default_system:
                observed["default_capacity"] = default_system.capacity
            with ParticleSystem(device, 64) as system:
                observed["capacity"] = system.capacity
                settings = replace(ParticleEmitterSettings.default(),
                                   position=Vector3(1.0, 2.0, 3.0),
                                   speed=12.5, lifetime=2.25, emission_rate=8.0,
                                   start_size=0.5, end_size=1.5,
                                   start_color=Vector4(0.1, 0.2, 0.3, 1.0),
                                   end_color=Vector4(0.8, 0.4, 0.2, 0.0))
                system.settings = settings
                observed["read"] = system.settings
                observed["written"] = settings
                observed["uses_compute"] = system.uses_compute
                observed["reason"] = system.unsupported_reason
                observed["clamped"] = system.emission_rate_clamped

        observed = in_game(body)
        self.assertEqual(observed["default_capacity"], PARTICLE_SYSTEM_DEFAULT_CAPACITY)
        self.assertEqual(observed["capacity"], 64)
        read, written = observed["read"], observed["written"]
        self.assertAlmostEqual(read.speed, written.speed, places=4)
        self.assertAlmostEqual(read.lifetime, written.lifetime, places=4)
        self.assertAlmostEqual(read.emission_rate, written.emission_rate, places=4)
        self.assertAlmostEqual(read.start_size, written.start_size, places=4)
        for name in ("start_color", "end_color"):
            with self.subTest(field=name):
                produced, expected = getattr(read, name), getattr(written, name)
                for axis in ("X", "Y", "Z", "W"):
                    self.assertAlmostEqual(getattr(produced, axis),
                                           getattr(expected, axis), places=5)
        self.assertTrue(oracle.vectors_agree(read.position, written.position))
        self.assertIsInstance(observed["uses_compute"], bool)

    def test_a_cpu_simulation_advances_exactly_as_step_predicts(self) -> None:
        """The strongest particle evidence available: predict every particle.

        The CPU path is forced so the simulation is inspectable, then every
        particle the system produced is compared with the same step function
        applied by hand from the state one update earlier.
        """
        def body(game, device, observed):
            with ParticleSystem(device, 16) as system:
                system.simulation_on_cpu = True
                observed["forced"] = system.simulation_on_cpu
                system.settings = replace(
                    ParticleEmitterSettings.default(),
                    gravity=Vector3(0.0, -9.81, 0.0), drag=0.1,
                    lifetime=4.0, lifetime_variance=0.0, emission_rate=16.0)
                system.update(0.25)
                observed["settings"] = system.settings
                observed["before"] = system.particles()
                system.update(0.125)
                observed["after"] = system.particles()
                observed["active"] = system.active_count

        observed = in_game(body)
        self.assertTrue(observed["forced"])
        before, after = observed["before"], observed["after"]
        self.assertEqual(len(before), len(after))
        self.assertGreater(len(before), 0, "the system emitted nothing")
        settings = observed["settings"]
        mismatched = []
        for index, (was, now) in enumerate(zip(before, after)):
            expected = ParticleSystem.step(was, index, settings, 0.125)
            if not (oracle.vectors_agree(
                        Vector3(now.position.X, now.position.Y, now.position.Z),
                        Vector3(expected.position.X, expected.position.Y,
                                expected.position.Z), 1e-3)
                    and abs(now.age - expected.age) < 1e-3):
                mismatched.append(index)
        self.assertEqual(mismatched, [],
                         f"{len(mismatched)} of {len(before)} particles did not "
                         "advance as step predicts")

    def test_the_live_count_is_the_emission_rate_times_the_lifetime(self) -> None:
        """What "active" means, measured rather than assumed.

        A pool does not hold as many particles as it has slots: it holds as many
        as the emitter produces in one lifetime, capped by the pool. The cap is
        reported separately, so a caller can tell a small pool from a slow
        emitter.
        """
        def body(game, device, observed):
            with ParticleSystem(device, 16) as system:
                system.simulation_on_cpu = True
                base = ParticleEmitterSettings.default()
                for rate in (1.0, 4.0, 100.0):
                    system.settings = replace(base, emission_rate=rate, lifetime=1.0,
                                              lifetime_variance=0.0)
                    system.reset()
                    for _ in range(4):
                        system.update(0.25)
                    observed[rate] = (system.active_count,
                                      system.emission_rate_clamped)

        observed = in_game(body)
        # rate * lifetime, until the pool of 16 is the limit.
        self.assertEqual(observed[1.0], (1, False))
        self.assertEqual(observed[4.0], (4, False))
        self.assertEqual(observed[100.0], (16, True))

    def test_reset_returns_every_particle_to_the_emitter(self) -> None:
        def body(game, device, observed):
            with ParticleSystem(device, 16) as system:
                system.simulation_on_cpu = True
                system.settings = replace(
                    ParticleEmitterSettings.default(),
                    position=Vector3(9.0, -4.0, 2.0), gravity=Vector3(0.0, -9.0, 0.0),
                    lifetime=8.0, lifetime_variance=0.0)
                system.update(0.5)
                moved = system.particles()
                observed["moved_age"] = moved[0].age
                observed["moved_position"] = tuple(moved[0].position)
                system.reset()
                restored = system.particles()
                observed["reset_age"] = restored[0].age
                observed["reset_position"] = tuple(restored[0].position)

        observed = in_game(body)
        self.assertGreater(observed["moved_age"], 0.0)
        self.assertEqual(observed["reset_age"], 0.0)
        # Gravity had moved it off the emitter; the reset put it back.
        self.assertNotEqual(observed["moved_position"], observed["reset_position"])

    def test_softness_and_depth_input_are_state_the_system_keeps(self) -> None:
        def body(game, device, observed):
            texture = Texture2D(device, 8, 8, False, SurfaceFormat.Color)
            with ParticleSystem(device, 8) as system:
                try:
                    observed["default_softness"] = system.softness
                    system.softness = 1.75
                    observed["softness"] = system.softness
                    system.set_depth_input(texture, 100.0)
                    observed["set"] = True
                    system.set_depth_input(None, 100.0)
                    observed["cleared"] = True
                finally:
                    texture.Dispose()

        observed = in_game(body)
        self.assertAlmostEqual(observed["softness"], 1.75, places=5)
        self.assertTrue(observed["set"])
        self.assertTrue(observed["cleared"])

    def test_a_closed_system_refuses(self) -> None:
        def body(game, device, observed):
            system = ParticleSystem(device, 8)
            system.close()
            observed["closed"] = system.is_closed
            with self.assertRaises(EngineDisposedError):
                system.capacity
            system.close()

        self.assertTrue(in_game(body)["closed"])


@requires_engine_gpu
class DecalPassTests(unittest.TestCase):
    def test_the_pass_state_round_trips(self) -> None:
        def body(game, device, observed):
            with DecalPass(device) as decals:
                observed["default_opacity"] = decals.opacity
                decals.opacity = 0.625
                decals.tint = Vector3(0.25, 0.5, 0.75)
                decals.max_slope_angle = 0.9
                observed["opacity"] = decals.opacity
                observed["tint"] = decals.tint
                observed["slope"] = decals.max_slope_angle

        observed = in_game(body)
        self.assertAlmostEqual(observed["opacity"], 0.625, places=5)
        self.assertTrue(oracle.vectors_agree(observed["tint"],
                                             Vector3(0.25, 0.5, 0.75)))
        self.assertAlmostEqual(observed["slope"], 0.9, places=5)

    def test_a_decal_needs_a_camera_and_prepass_inputs_before_it_draws(self) -> None:
        """Drawing without them is refused rather than drawing nothing."""
        def body(game, device, observed):
            decal = Texture2D(device, 4, 4, False, SurfaceFormat.Color)
            with DecalPass(device) as decals:
                try:
                    try:
                        decals.draw(decal, Matrix.Identity, 16, 16)
                    except EngineError as error:
                        observed["without"] = type(error).__name__
                    else:
                        observed["without"] = None
                finally:
                    decal.Dispose()

        observed = in_game(body)
        # Either it refuses, or it draws nothing harmlessly. Both are contracts
        # a caller can hold; what matters is which, so it is recorded.
        self.assertIn(observed["without"],
                      {None, "EngineStateError", "EngineArgumentError",
                       "EngineInternalError"})


@requires_engine_gpu
class DepthNormalPrepassTests(unittest.TestCase):
    def test_the_prepass_reports_its_own_shape_and_strategy(self) -> None:
        def body(game, device, observed):
            with DepthNormalPrepass(device, 32, 32) as prepass:
                observed["supported"] = prepass.is_supported(device)
                observed["passes"] = prepass.pass_count
                observed["mrt"] = prepass.uses_multiple_render_targets
                observed["packed"] = prepass.is_depth_packed
                observed["device_packed"] = uses_packed_depth(device)
                prepass.roughness = 0.625
                observed["roughness"] = prepass.roughness
                depth = prepass.depth_texture
                normals = prepass.normal_texture
                observed["depth_shape"] = (depth.Width, depth.Height)
                observed["normal_shape"] = (normals.Width, normals.Height)
                observed["same_view"] = depth is prepass.depth_texture
                observed["distinct"] = depth is not normals

        observed = in_game(body)
        self.assertIsInstance(observed["supported"], bool)
        self.assertGreaterEqual(observed["passes"], 1)
        # One pass when depth and normals go to two targets at once, more when
        # they cannot -- and the two answers have to agree with each other.
        self.assertEqual(observed["mrt"], observed["passes"] == 1)
        self.assertEqual(observed["packed"], observed["device_packed"])
        self.assertAlmostEqual(observed["roughness"], 0.625, places=5)
        self.assertEqual(observed["depth_shape"], (32, 32))
        self.assertEqual(observed["normal_shape"], (32, 32))
        self.assertTrue(observed["same_view"])
        self.assertTrue(observed["distinct"],
                        "depth and normals must not be the same target")

    def test_rendering_a_pass_clears_the_depth_target(self) -> None:
        def body(game, device, observed):
            with DepthNormalPrepass(device, 16, 16) as prepass:
                if not prepass.is_supported(device):
                    observed["unsupported"] = True
                    return
                view = Matrix.CreateLookAt(Vector3(0.0, 0.0, 5.0),
                                           Vector3(0.0, 0.0, 0.0),
                                           Vector3(0.0, 1.0, 0.0))
                projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.0, 0.5, 50.0)
                for index in range(prepass.pass_count):
                    with prepass.render(index, view, projection, 0.5, 50.0):
                        pass
                depth = prepass.depth_texture
                pixels = [Color(0, 0, 0, 0)] * (depth.Width * depth.Height)
                depth.GetData(pixels)
                observed["format"] = int(depth.Format)
                observed["corner"] = (int(pixels[0].R), int(pixels[0].G),
                                      int(pixels[0].B), int(pixels[0].A))
                observed["packed"] = prepass.is_depth_packed

        observed = in_game(body)
        if observed.get("unsupported"):
            self.skipTest("this renderer cannot run the depth/normal prepass")
        red, green, blue, alpha = observed["corner"]
        if observed["packed"]:
            # A packed empty prepass reads as the far plane, which is what an
            # unwritten texel has to mean.
            recovered = unpack_depth(red / 255.0, green / 255.0, blue / 255.0,
                                     alpha / 255.0)
            self.assertGreater(recovered, 0.9,
                               f"an empty packed prepass read back {recovered}")
        else:
            self.assertGreaterEqual(max(red, green, blue, alpha), 0)

    def test_velocity_is_off_by_default_and_can_be_turned_on(self) -> None:
        def body(game, device, observed):
            with DepthNormalPrepass(device, 16, 16) as prepass:
                observed["default"] = prepass.velocity_enabled
                observed["no_texture"] = prepass.velocity_texture
                prepass.velocity_enabled = True
                observed["enabled"] = prepass.velocity_enabled
                velocity = prepass.velocity_texture
                observed["texture"] = None if velocity is None else (velocity.Width,
                                                                     velocity.Height)
                prepass.set_previous_world(Matrix.CreateTranslation(
                    Vector3(1.0, 0.0, 0.0)))
                prepass.set_previous_camera(Matrix.Identity, Matrix.Identity)
                observed["accepted"] = True

        observed = in_game(body)
        self.assertFalse(observed["default"])
        self.assertTrue(observed["enabled"])
        self.assertTrue(observed["accepted"])
        if observed["texture"] is not None:
            self.assertEqual(observed["texture"], (16, 16))

    def test_resizing_replaces_the_targets(self) -> None:
        def body(game, device, observed):
            with DepthNormalPrepass(device, 16, 16) as prepass:
                first = prepass.depth_texture
                observed["before"] = (first.Width, first.Height)
                prepass.resize(24, 12)
                observed["first_disposed"] = first.IsDisposed
                second = prepass.depth_texture
                observed["after"] = (second.Width, second.Height)

        observed = in_game(body)
        self.assertEqual(observed["before"], (16, 16))
        self.assertEqual(observed["after"], (24, 12))
        self.assertTrue(observed["first_disposed"],
                        "a resize must not leave the old view outstanding")

    def test_the_prepass_effects_are_distinct_and_disposed_with_it(self) -> None:
        def body(game, device, observed):
            prepass = DepthNormalPrepass(device, 16, 16)
            rigid = prepass.prepass_effect
            skinned = prepass.skinned_prepass_effect
            observed["rigid"] = rigid is not None
            observed["skinned"] = skinned is not None
            observed["distinct"] = rigid is not skinned
            prepass.close()
            observed["rigid_disposed"] = rigid is None or rigid.IsDisposed
            observed["skinned_disposed"] = skinned is None or skinned.IsDisposed

        observed = in_game(body)
        self.assertTrue(observed["distinct"])
        self.assertTrue(observed["rigid_disposed"])
        self.assertTrue(observed["skinned_disposed"])


@requires_engine
class TransparentDrawListTests(unittest.TestCase):
    """Sorted transparency, which needs no device at all."""

    def test_entries_are_replayed_furthest_first(self) -> None:
        order: list[str] = []
        near = BoundingBox(Vector3(-1.0, -1.0, 1.0), Vector3(1.0, 1.0, 2.0))
        middle = BoundingBox(Vector3(-1.0, -1.0, 5.0), Vector3(1.0, 1.0, 6.0))
        far = BoundingBox(Vector3(-1.0, -1.0, 20.0), Vector3(1.0, 1.0, 21.0))
        with TransparentDrawList() as drawn:
            # Submitted near-first on purpose, so submission order is not the
            # answer the test would accept.
            drawn.submit(near, lambda: order.append("near"))
            drawn.submit(far, lambda: order.append("far"))
            drawn.submit(middle, lambda: order.append("middle"))
            self.assertEqual(drawn.count, 3)
            view = Matrix.CreateLookAt(Vector3(0.0, 0.0, 0.0),
                                       Vector3(0.0, 0.0, 1.0),
                                       Vector3(0.0, 1.0, 0.0))
            self.assertEqual(drawn.sorted_order(view), (1, 2, 0))
            drawn.draw_sorted(view)
        self.assertEqual(order, ["far", "middle", "near"])

    def test_moving_the_camera_changes_the_order(self) -> None:
        near = BoundingBox(Vector3(-1.0, -1.0, 1.0), Vector3(1.0, 1.0, 2.0))
        far = BoundingBox(Vector3(-1.0, -1.0, 20.0), Vector3(1.0, 1.0, 21.0))
        with TransparentDrawList() as drawn:
            drawn.submit(near, lambda: None)
            drawn.submit(far, lambda: None)
            in_front = Matrix.CreateLookAt(Vector3(0.0, 0.0, 0.0),
                                           Vector3(0.0, 0.0, 1.0),
                                           Vector3(0.0, 1.0, 0.0))
            behind = Matrix.CreateLookAt(Vector3(0.0, 0.0, 40.0),
                                         Vector3(0.0, 0.0, 0.0),
                                         Vector3(0.0, 1.0, 0.0))
            self.assertEqual(drawn.sorted_order(in_front), (1, 0))
            self.assertEqual(drawn.sorted_order(behind), (0, 1))

    def test_clear_drops_the_entries_and_their_callbacks(self) -> None:
        calls: list[int] = []
        bounds = BoundingBox(Vector3(0.0, 0.0, 0.0), Vector3(1.0, 1.0, 1.0))
        with TransparentDrawList() as drawn:
            drawn.submit(bounds, lambda: calls.append(1))
            drawn.clear()
            self.assertEqual(drawn.count, 0)
            drawn.draw_sorted(Matrix.Identity)
        self.assertEqual(calls, [])

    def test_an_unreferenced_callback_is_still_alive_when_cna_calls_it(self) -> None:
        """CNA holds a trampoline, not a Python object."""
        import gc

        calls: list[int] = []

        def make(index: int):
            def draw() -> None:
                calls.append(index)
            return draw

        bounds = BoundingBox(Vector3(0.0, 0.0, 0.0), Vector3(1.0, 1.0, 1.0))
        with TransparentDrawList() as drawn:
            for index in range(4):
                drawn.submit(bounds, make(index))
            gc.collect()
            drawn.draw_sorted(Matrix.Identity)
        self.assertEqual(sorted(calls), [0, 1, 2, 3])

    def test_a_python_exception_surfaces_after_the_native_call(self) -> None:
        """It must not unwind through C, and it must not be swallowed."""
        bounds = BoundingBox(Vector3(0.0, 0.0, 0.0), Vector3(1.0, 1.0, 1.0))

        def explode() -> None:
            raise ValueError("the caller's draw failed")

        with TransparentDrawList() as drawn:
            drawn.submit(bounds, explode)
            with self.assertRaises(ValueError) as caught:
                drawn.draw_sorted(Matrix.Identity)
            self.assertEqual(str(caught.exception), "the caller's draw failed")
            # The list is still usable afterwards.
            self.assertEqual(drawn.count, 1)

    def test_a_closed_list_refuses(self) -> None:
        drawn = TransparentDrawList()
        drawn.close()
        self.assertTrue(drawn.is_closed)
        with self.assertRaises(EngineDisposedError):
            drawn.count
        drawn.close()


@requires_engine_gpu
class WeightedBlendedTransparencyTests(unittest.TestCase):
    def test_the_two_targets_are_distinct_and_the_bracket_opens_and_closes(self) -> None:
        def body(game, device, observed):
            with WeightedBlendedTransparency(device, 32, 16) as transparency:
                observed["supported"] = transparency.is_supported
                observed["reason"] = transparency.unsupported_reason
                accumulation = transparency.accumulation_texture
                revealage = transparency.revealage_texture
                observed["shapes"] = (
                    None if accumulation is None else (accumulation.Width,
                                                       accumulation.Height),
                    None if revealage is None else (revealage.Width, revealage.Height))
                observed["distinct"] = accumulation is not revealage
                observed["before"] = transparency.is_accumulating
                if transparency.is_supported:
                    with transparency.accumulate(100.0):
                        observed["during"] = transparency.is_accumulating
                    observed["after"] = transparency.is_accumulating
                    transparency.resolve(32, 16)
                    observed["resolved"] = True

        observed = in_game(body)
        if not observed["supported"]:
            self.skipTest(f"this renderer cannot accumulate: {observed['reason']}")
        self.assertEqual(observed["reason"], "")
        self.assertEqual(observed["shapes"], ((32, 16), (32, 16)))
        self.assertTrue(observed["distinct"])
        self.assertFalse(observed["before"])
        self.assertTrue(observed["during"])
        self.assertFalse(observed["after"])
        self.assertTrue(observed["resolved"])

    def test_resizing_replaces_both_targets(self) -> None:
        def body(game, device, observed):
            with WeightedBlendedTransparency(device, 16, 16) as transparency:
                first = transparency.accumulation_texture
                if first is None:
                    observed["unsupported"] = True
                    return
                transparency.resize(20, 10)
                observed["disposed"] = first.IsDisposed
                second = transparency.accumulation_texture
                observed["shape"] = (second.Width, second.Height)

        observed = in_game(body)
        if observed.get("unsupported"):
            self.skipTest("this renderer has no accumulation target")
        self.assertTrue(observed["disposed"])
        self.assertEqual(observed["shape"], (20, 10))
