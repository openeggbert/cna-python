"""PBR materials, extensions and effects: every field, and the slot order.

The trap this family sets is that CNA's seven texture slots are numbered in one
order and declared in the structure in another -- occlusion and emissive are
swapped. So the slot tests give all seven distinct values and check each one
back individually; a binding that indexed by field position would put the
emissive coordinate set on the occlusion map and still pass a test that only
looked at one slot.

Nothing here uses a getter as its own oracle for a *default*: the defaults are
CNA's, read once, and what is asserted about them is that they are coherent --
a unit-length colour, a roughness in range, a material that is neutral.
"""

from __future__ import annotations

import math
import unittest
from dataclasses import replace

from Microsoft.Xna.Framework import Color, Vector2, Vector3, Vector4
from Microsoft.Xna.Framework.Graphics import SurfaceFormat, Texture2D

from cna.extensions.engine import (
    AlphaMode, GltfMaterialExtensionSource, GltfMaterialSource,
    PBR_TEXTURE_SLOT_COUNT, PbrEffect, PbrMaterial, PbrMaterialExtensions,
    PbrTextureSlot, SkinnedPbrEffect, TextureTransform, TransparencyMode,
    build_extensions, build_material, thin_film_iridescence,
    thin_film_iridescence_glsl,
)
from cna.extensions.engine.errors import EngineDisposedError

from .engine_fixtures import in_game, requires_engine, requires_engine_gpu


def distinct_slot_values() -> dict[PbrTextureSlot, int]:
    """A coordinate-set pattern where neighbouring slots differ.

    CNA packs the set into one bit per slot and refuses anything but 0 or 1 --
    measured: a 2 is an argument error -- so seven distinct values are not
    available. Alternating is enough for what the pattern is for: every test
    that cares flips exactly one slot and asserts the material changed, which a
    binding that indexed by field position rather than by slot would fail.
    """
    return {slot: index % 2 for index, slot in enumerate(PbrTextureSlot)}


def distinct_transforms() -> dict[PbrTextureSlot, TextureTransform]:
    """A different transform per slot, none of them the default."""
    return {slot: TextureTransform(Vector2(0.1 * (index + 1), 0.2 * (index + 1)),
                                   Vector2(1.0 + index, 2.0 + index),
                                   0.05 * (index + 1))
            for index, slot in enumerate(PbrTextureSlot)}


@requires_engine
class PbrMaterialValueTests(unittest.TestCase):
    """The material as a value: defaults, round trips and CNA's own equality."""

    def test_the_slot_count_matches_the_enum(self) -> None:
        self.assertEqual(len(PbrTextureSlot), PBR_TEXTURE_SLOT_COUNT)
        self.assertEqual(sorted(int(slot) for slot in PbrTextureSlot),
                         list(range(PBR_TEXTURE_SLOT_COUNT)))

    def test_defaults_are_cnas_and_are_coherent(self) -> None:
        material = PbrMaterial.default()
        self.assertIsInstance(material.albedo_color, Color)
        # A default material has to be renderable: opaque, single-sided, with a
        # roughness and an index of refraction in physical range.
        self.assertEqual(material.alpha_mode, AlphaMode.Opaque)
        self.assertFalse(material.double_sided)
        self.assertGreaterEqual(material.roughness_factor, 0.0)
        self.assertLessEqual(material.roughness_factor, 1.0)
        self.assertGreaterEqual(material.metallic_factor, 0.0)
        self.assertLessEqual(material.metallic_factor, 1.0)
        self.assertGreater(material.ior, 1.0, "an index of refraction under one is not physical")
        self.assertEqual(len(material.coordinate_sets), PBR_TEXTURE_SLOT_COUNT)
        self.assertEqual(len(material.transforms), PBR_TEXTURE_SLOT_COUNT)
        self.assertEqual(material.textures, {})

    def test_every_scalar_field_survives_a_round_trip_through_cna(self) -> None:
        """One distinct value per field, so a field copied over another shows."""
        original = replace(
            PbrMaterial.default(),
            albedo_color=Color(11, 22, 33, 44),
            emissive_factor=Vector3(0.125, 0.25, 0.375),
            specular_color_factor=Vector3(0.5, 0.625, 0.75),
            metallic_factor=0.1875, roughness_factor=0.3125, normal_scale=1.375,
            occlusion_strength=0.8125, ior=1.4375, specular_factor=0.6875,
            alpha_cutoff=0.28125, alpha_mode=AlphaMode.Mask, double_sided=True,
            base_color_texture_srgb=False, emissive_texture_srgb=True,
            specular_color_texture_srgb=False, output_encoded_to_srgb=True)
        # CNA's own equality is the round trip: build the native value, compare.
        self.assertTrue(original.matches(original))
        # And a material differing in exactly one field is not equal.
        for name, value in (("metallic_factor", 0.9), ("alpha_mode", AlphaMode.Blend),
                            ("double_sided", False), ("ior", 1.9),
                            ("albedo_color", Color(11, 22, 33, 45)),
                            ("emissive_factor", Vector3(0.125, 0.25, 0.376)),
                            ("output_encoded_to_srgb", False)):
            with self.subTest(field=name):
                self.assertFalse(original.matches(replace(original, **{name: value})),
                                 f"{name} does not reach CNA")

    def test_each_texture_slot_keeps_its_own_coordinate_set_and_transform(self) -> None:
        """The test the emissive/occlusion field-order swap fails."""
        sets, transforms = distinct_slot_values(), distinct_transforms()
        material = replace(PbrMaterial.default(), coordinate_sets=sets,
                           transforms=transforms)
        for slot in PbrTextureSlot:
            with self.subTest(slot=slot.name):
                # Changing exactly one slot's coordinate set changes the material.
                moved = dict(sets)
                moved[slot] = 1 - sets[slot]
                self.assertFalse(material.matches(
                    replace(material, coordinate_sets=moved)),
                    f"{slot.name}'s coordinate set does not reach CNA")
                # And the same for its transform.
                shifted = dict(transforms)
                shifted[slot] = replace(transforms[slot], rotation=1.25)
                self.assertFalse(material.matches(
                    replace(material, transforms=shifted)),
                    f"{slot.name}'s transform does not reach CNA")

    def test_the_hash_is_consistent_with_cnas_equality(self) -> None:
        first = replace(PbrMaterial.default(), roughness_factor=0.3125)
        same = replace(PbrMaterial.default(), roughness_factor=0.3125)
        other = replace(PbrMaterial.default(), roughness_factor=0.9375)
        self.assertTrue(first.matches(same))
        self.assertEqual(first.cna_hash(), same.cna_hash())
        self.assertFalse(first.matches(other))
        # Not required by the contract, but a hash that collided here would make
        # the hash useless, so it is worth knowing.
        self.assertNotEqual(first.cna_hash(), other.cna_hash())

    def test_python_equality_and_cna_equality_answer_the_same_way_on_values(self) -> None:
        """Two independent implementations, cross-checked where both apply.

        They can differ on textures -- Python compares objects, CNA compares
        handles -- so this compares materials with no textures, where the two
        questions are the same question.
        """
        base = PbrMaterial.default()
        cases = [base, replace(base, roughness_factor=0.25),
                 replace(base, alpha_mode=AlphaMode.Blend),
                 replace(base, coordinate_sets=distinct_slot_values())]
        for left in cases:
            for right in cases:
                with self.subTest(left=id(left), right=id(right)):
                    self.assertEqual(left == right, left.matches(right))

    def test_the_material_describes_itself(self) -> None:
        text = PbrMaterial.default().describe()
        self.assertTrue(text.strip())
        self.assertIsInstance(text, str)

    def test_transparency_modes_are_distinct(self) -> None:
        values = {int(mode) for mode in TransparencyMode}
        self.assertEqual(len(values), len(TransparencyMode))


@requires_engine
class PbrMaterialExtensionsTests(unittest.TestCase):
    """The glTF extensions, whose flags CNA derives rather than stores."""

    SCALARS = (
        ("clearcoat_factor", 0.375), ("clearcoat_roughness", 0.1875),
        ("clearcoat_normal_scale", 1.625), ("sheen_roughness", 0.4375),
        ("transmission_factor", 0.5625), ("thickness_factor", 2.125),
        ("attenuation_distance", 3.25), ("iridescence_factor", 0.6875),
        ("iridescence_ior", 1.3125), ("iridescence_thickness_minimum", 110.0),
        ("iridescence_thickness_maximum", 430.0), ("subsurface_wrap", 0.28125),
    )
    VECTORS = (
        ("sheen_color_factor", Vector3(0.1, 0.2, 0.3)),
        ("attenuation_color", Vector3(0.4, 0.5, 0.6)),
        ("subsurface_color", Vector3(0.7, 0.8, 0.9)),
    )

    def test_a_fresh_extensions_object_is_neutral(self) -> None:
        with PbrMaterialExtensions() as extensions:
            self.assertTrue(extensions.is_neutral,
                            "a material with no extensions set must shade as plain PBR")
            self.assertFalse(extensions.is_sheen_enabled)
            self.assertFalse(extensions.is_transmission_enabled)
            self.assertFalse(extensions.is_iridescence_enabled)
            self.assertFalse(extensions.is_subsurface_enabled)

    def test_every_scalar_and_vector_field_round_trips(self) -> None:
        with PbrMaterialExtensions() as extensions:
            for name, value in self.SCALARS:
                setattr(extensions, name, value)
            for name, value in self.VECTORS:
                setattr(extensions, name, value)
            for name, value in self.SCALARS:
                with self.subTest(field=name):
                    self.assertAlmostEqual(getattr(extensions, name), value, places=5)
            for name, value in self.VECTORS:
                with self.subTest(field=name):
                    produced = getattr(extensions, name)
                    self.assertAlmostEqual(produced.X, value.X, places=5)
                    self.assertAlmostEqual(produced.Y, value.Y, places=5)
                    self.assertAlmostEqual(produced.Z, value.Z, places=5)

    def test_the_flags_follow_the_factors_rather_than_being_set(self) -> None:
        with PbrMaterialExtensions() as extensions:
            extensions.transmission_factor = 0.5
            self.assertTrue(extensions.is_transmission_enabled)
            self.assertFalse(extensions.is_neutral)
            extensions.transmission_factor = 0.0
            self.assertFalse(extensions.is_transmission_enabled)
            self.assertTrue(extensions.is_neutral,
                            "turning the only extension off must return to neutral")
            extensions.iridescence_factor = 0.25
            self.assertTrue(extensions.is_iridescence_enabled)
            self.assertFalse(extensions.is_neutral)

    def test_copy_from_and_equality(self) -> None:
        with PbrMaterialExtensions() as first, PbrMaterialExtensions() as second:
            self.assertTrue(first.matches(second), "two fresh objects are equal")
            first.clearcoat_factor = 0.625
            first.sheen_color_factor = Vector3(0.2, 0.4, 0.6)
            self.assertFalse(first.matches(second))
            second.copy_from(first)
            self.assertTrue(first.matches(second))
            self.assertEqual(first.cna_hash(), second.cna_hash())
            self.assertAlmostEqual(second.clearcoat_factor, 0.625, places=5)
            self.assertTrue(second.describe().strip())

    def test_use_after_close_is_refused(self) -> None:
        extensions = PbrMaterialExtensions()
        extensions.close()
        self.assertTrue(extensions.is_closed)
        with self.assertRaises(EngineDisposedError):
            extensions.clearcoat_factor
        extensions.close()


@requires_engine
class GltfBridgeTests(unittest.TestCase):
    """The bridge from an imported glTF material to a PBR one."""

    def test_the_glTF_defaults_produce_a_neutral_material(self) -> None:
        source = GltfMaterialSource.default()
        # glTF's own published defaults: white base colour, fully metallic and
        # fully rough, which is what the specification says.
        self.assertEqual(source.alpha_mode, AlphaMode.Opaque)
        self.assertFalse(source.double_sided)
        material = build_material(source)
        self.assertIsInstance(material, PbrMaterial)
        self.assertEqual(material.alpha_mode, AlphaMode.Opaque)
        self.assertEqual(material.textures, {})

    def test_every_source_factor_reaches_the_material(self) -> None:
        base = GltfMaterialSource.default()
        source = replace(
            base, base_color_factor=Vector4(0.75, 0.5, 0.25, 0.9375),
            metallic_factor=0.1875, roughness_factor=0.3125,
            emissive_factor=Vector3(0.125, 0.25, 0.375), normal_scale=1.375,
            occlusion_strength=0.8125, ior=1.4375, specular_factor=0.6875,
            specular_color_factor=Vector3(0.5, 0.625, 0.75),
            alpha_mode=AlphaMode.Mask, alpha_cutoff=0.28125, double_sided=True,
            coordinate_sets=distinct_slot_values(),
            transforms=distinct_transforms())
        material = build_material(source)
        # The bridge quantises glTF's linear float base colour into the
        # material's byte colour, so this is the quantisation and not an
        # identity: 0.75 of 255 is 191, and 0.9375 is 239.
        self.assertEqual(
            (material.albedo_color.R, material.albedo_color.G,
             material.albedo_color.B, material.albedo_color.A),
            (round(0.75 * 255), round(0.5 * 255), round(0.25 * 255),
             round(0.9375 * 255)))
        self.assertAlmostEqual(material.metallic_factor, 0.1875, places=5)
        self.assertAlmostEqual(material.roughness_factor, 0.3125, places=5)
        self.assertAlmostEqual(material.normal_scale, 1.375, places=5)
        self.assertAlmostEqual(material.occlusion_strength, 0.8125, places=5)
        self.assertAlmostEqual(material.ior, 1.4375, places=5)
        self.assertAlmostEqual(material.specular_factor, 0.6875, places=5)
        self.assertAlmostEqual(material.alpha_cutoff, 0.28125, places=5)
        self.assertEqual(material.alpha_mode, AlphaMode.Mask)
        self.assertTrue(material.double_sided)
        # Every slot's coordinate set survives with its own value.
        for slot, expected in distinct_slot_values().items():
            with self.subTest(slot=slot.name):
                self.assertEqual(material.coordinate_sets[slot], expected)
        for slot, expected in distinct_transforms().items():
            with self.subTest(slot=slot.name, part="transform"):
                produced = material.transforms[slot]
                self.assertAlmostEqual(produced.rotation, expected.rotation, places=5)
                self.assertAlmostEqual(produced.scale.X, expected.scale.X, places=5)
                self.assertAlmostEqual(produced.offset.Y, expected.offset.Y, places=5)

    def test_the_extension_bridge_fills_a_destination(self) -> None:
        source = replace(GltfMaterialExtensionSource.default(),
                         clearcoat_factor=0.5, sheen_color_factor=Vector3(0.9, 0.1, 0.2),
                         transmission_factor=0.75, iridescence_ior=1.4)
        with PbrMaterialExtensions() as extensions:
            build_extensions(source, extensions)
            self.assertAlmostEqual(extensions.clearcoat_factor, 0.5, places=5)
            self.assertAlmostEqual(extensions.transmission_factor, 0.75, places=5)
            self.assertAlmostEqual(extensions.iridescence_ior, 1.4, places=5)
            self.assertAlmostEqual(extensions.sheen_color_factor.X, 0.9, places=5)
            self.assertTrue(extensions.is_transmission_enabled)
            self.assertFalse(extensions.is_neutral)

    def test_an_unknown_extension_slot_is_refused_rather_than_ignored(self) -> None:
        source = GltfMaterialExtensionSource.default()
        with PbrMaterialExtensions() as extensions:
            with self.assertRaises(ValueError) as caught:
                build_extensions(source, extensions, {"clearcoat_normal_map": None})
            self.assertIn("clearcoat_normal_map", str(caught.exception))


@requires_engine
class ThinFilmTests(unittest.TestCase):
    """Iridescence: the CPU term and the GLSL that has to agree with it."""

    def test_the_term_varies_with_thickness_and_stays_in_range(self) -> None:
        base = Vector3(0.04, 0.04, 0.04)
        values = [thin_film_iridescence(1.0, 1.3, 0.85, thickness, base)
                  for thickness in (100.0, 250.0, 400.0, 550.0)]
        for produced in values:
            for component in (produced.X, produced.Y, produced.Z):
                self.assertTrue(math.isfinite(component))
                self.assertGreaterEqual(component, 0.0)
                self.assertLessEqual(component, 1.0)
        # A film that changes thickness changes colour: that is what iridescence
        # is, and a term that ignored thickness would return the same triple.
        distinct = {(round(v.X, 4), round(v.Y, 4), round(v.Z, 4)) for v in values}
        self.assertGreater(len(distinct), 1,
                           "the term does not depend on film thickness")
        # And the channels separate, which is why it looks coloured at all.
        self.assertTrue(any(abs(v.X - v.Z) > 1e-4 for v in values),
                        "the term is grey at every thickness")

    def test_a_film_matching_the_outside_is_close_to_the_base(self) -> None:
        """No index step, no interference: the term collapses toward its base."""
        base = Vector3(0.04, 0.04, 0.04)
        produced = thin_film_iridescence(1.0, 1.0, 1.0, 0.0, base)
        for component in (produced.X, produced.Y, produced.Z):
            self.assertAlmostEqual(component, 0.04, delta=0.05)

    def test_the_published_glsl_is_real_source(self) -> None:
        source = thin_film_iridescence_glsl()
        self.assertTrue(source.strip())
        # It has to be a function a caller can paste, not a description of one.
        self.assertIn("(", source)
        self.assertIn("{", source)
        self.assertIn("}", source)


@requires_engine_gpu
class PbrEffectTests(unittest.TestCase):
    """The effects, and the material crossing to them and back.

    ``engine_layer.h`` has no route that creates a ``PbrEffect``; the two
    constructors come from ``effects.h`` as a dependency slice, which is what
    makes ``apply_material`` reachable at all.
    """

    def test_a_material_crosses_to_the_effect_and_back(self) -> None:
        def body(game, device, observed):
            with PbrEffect(device) as effect:
                original = replace(
                    PbrMaterial.default(),
                    albedo_color=Color(11, 22, 33, 44),
                    emissive_factor=Vector3(0.125, 0.25, 0.375),
                    metallic_factor=0.1875, roughness_factor=0.3125,
                    normal_scale=1.375, occlusion_strength=0.8125,
                    alpha_cutoff=0.28125, alpha_mode=AlphaMode.Mask,
                    double_sided=True,
                    coordinate_sets=distinct_slot_values())
                observed["before"] = effect.material
                effect.material = original
                observed["after"] = effect.material
                observed["written"] = original
                observed["has_effect"] = effect.effect is not None

        observed = in_game(body)
        self.assertTrue(observed["has_effect"])
        after, written = observed["after"], observed["written"]
        self.assertEqual(after.albedo_color, written.albedo_color)
        self.assertAlmostEqual(after.metallic_factor, written.metallic_factor, places=5)
        self.assertAlmostEqual(after.roughness_factor, written.roughness_factor, places=5)
        self.assertAlmostEqual(after.normal_scale, written.normal_scale, places=5)
        self.assertAlmostEqual(after.occlusion_strength, written.occlusion_strength,
                               places=5)
        self.assertAlmostEqual(after.alpha_cutoff, written.alpha_cutoff, places=5)
        self.assertEqual(after.alpha_mode, written.alpha_mode)
        self.assertEqual(after.double_sided, written.double_sided)
        for slot, expected in distinct_slot_values().items():
            with self.subTest(slot=slot.name):
                self.assertEqual(after.coordinate_sets[slot], expected)
        # The effect started with something other than what was written, so the
        # comparison above is not comparing a default with itself.
        self.assertFalse(observed["before"].matches(written))

    def test_a_texture_slot_reaches_the_effect_and_comes_back_as_the_same_object(
            self) -> None:
        def body(game, device, observed):
            texture = Texture2D(device, 4, 4, False, SurfaceFormat.Color)
            with PbrEffect(device) as effect:
                try:
                    material = replace(PbrMaterial.default(),
                                       textures={PbrTextureSlot.BaseColor: texture})
                    effect.material = material
                    read = effect.material
                    observed["identity"] = (read.textures.get(PbrTextureSlot.BaseColor)
                                            is texture)
                    observed["only_one_slot"] = list(read.textures)
                    observed["per_slot"] = [
                        effect.texture(slot) is not None for slot in PbrTextureSlot]
                    # Clearing it clears it, so the assignment is not one-way.
                    effect.material = PbrMaterial.default()
                    observed["cleared"] = effect.texture(PbrTextureSlot.BaseColor)
                finally:
                    texture.Dispose()

        observed = in_game(body)
        self.assertTrue(observed["identity"],
                        "a texture must come back as the object that was set")
        self.assertEqual(observed["only_one_slot"], [PbrTextureSlot.BaseColor])
        self.assertEqual(observed["per_slot"],
                         [True] + [False] * (PBR_TEXTURE_SLOT_COUNT - 1))
        self.assertIsNone(observed["cleared"])

    def test_apply_material_alone_carries_no_texture_at_all(self) -> None:
        """ENGINE-005, pinned at the raw route rather than through the wrapper.

        ``cna_pbr_effect_apply_material`` is documented to carry every field of
        the material. Every scalar does cross; not one of the seven texture
        slots does. This drives the raw route so the defect stays visible even
        though the public setter works around it, and it fails the day CNA
        carries them -- which is when the finding needs re-measuring.
        """
        import ctypes

        from _cna_native import engine_abi, engine_support

        def body(game, device, observed):
            texture = Texture2D(device, 4, 4, False, SurfaceFormat.Color)
            with PbrEffect(device) as effect:
                try:
                    handle = ctypes.c_uint64(effect.effect._require_handle())
                    native = replace(
                        PbrMaterial.default(),
                        metallic_factor=0.1875,
                        textures={PbrTextureSlot.BaseColor: texture})._native()
                    engine_support.call("cna_pbr_effect_apply_material", handle,
                                        ctypes.byref(native))
                    extracted = engine_support.out_struct(
                        engine_abi.CNA_PbrMaterialEXT, 1,
                        "cna_pbr_effect_extract_material", handle)
                    observed["metallic"] = float(extracted.metallic_factor)
                    observed["albedo_texture"] = int(extracted.albedo_texture)
                    slots = []
                    for slot in PbrTextureSlot:
                        present = ctypes.c_uint8()
                        produced = ctypes.c_uint64()
                        engine_support.call(
                            "cna_pbr_effect_get_texture", handle,
                            ctypes.c_uint32(int(slot)), ctypes.byref(present),
                            ctypes.byref(produced))
                        slots.append(bool(present.value))
                    observed["slots"] = slots
                finally:
                    texture.Dispose()

        observed = in_game(body)
        # The scalar crossed.
        self.assertAlmostEqual(observed["metallic"], 0.1875, places=5)
        # The texture did not, by the route's own extract and by an independent
        # route from effects.h.
        self.assertEqual(observed["albedo_texture"], 0,
                         "CNA now carries textures through apply_material; "
                         "ENGINE-005 needs re-measuring")
        self.assertEqual(observed["slots"], [False] * PBR_TEXTURE_SLOT_COUNT,
                         "CNA now carries textures through apply_material; "
                         "ENGINE-005 needs re-measuring")

    def test_a_coordinate_set_other_than_zero_or_one_is_refused(self) -> None:
        """A measured bound: CNA packs one bit per slot."""
        from cna.extensions.engine.errors import EngineArgumentError

        def body(game, device, observed):
            with PbrEffect(device) as effect:
                material = replace(
                    PbrMaterial.default(),
                    coordinate_sets={slot: 2 for slot in PbrTextureSlot})
                try:
                    effect.material = material
                except EngineArgumentError as error:
                    observed["refused"] = error.native_message
                else:
                    observed["refused"] = None

        observed = in_game(body)
        self.assertIsNotNone(observed["refused"],
                             "a coordinate set of 2 must be refused")
        self.assertIn("0 or 1", observed["refused"])

    def test_the_skinned_effect_is_a_different_effect_with_the_same_material(self) -> None:
        def body(game, device, observed):
            with SkinnedPbrEffect(device) as skinned:
                material = replace(PbrMaterial.default(), roughness_factor=0.4375)
                skinned.material = material
                observed["roughness"] = skinned.material.roughness_factor
                observed["parameters"] = skinned.effect.Parameters is not None

        observed = in_game(body)
        self.assertAlmostEqual(observed["roughness"], 0.4375, places=5)
        self.assertTrue(observed["parameters"])

    def test_applying_material_state_reaches_the_device(self) -> None:
        """Alpha mode and double-sidedness become blend and cull state."""
        from Microsoft.Xna.Framework.Graphics import BlendState, RasterizerState

        def body(game, device, observed):
            opaque = replace(PbrMaterial.default(), alpha_mode=AlphaMode.Opaque,
                             double_sided=False)
            blended = replace(PbrMaterial.default(), alpha_mode=AlphaMode.Blend,
                              double_sided=True)
            opaque.apply_state(device)
            observed["opaque"] = (device.BlendState.Name, device.RasterizerState.CullMode)
            blended.apply_state(device)
            observed["blended"] = (device.BlendState.Name,
                                   device.RasterizerState.CullMode)

        observed = in_game(body)
        # The two materials must not leave the device in the same state, which
        # is the whole point of the route.
        self.assertNotEqual(observed["opaque"], observed["blended"],
                            f"{observed['opaque']} == {observed['blended']}")

    def test_a_closed_effect_refuses(self) -> None:
        def body(game, device, observed):
            effect = PbrEffect(device)
            effect.close()
            observed["disposed"] = effect.is_disposed
            with self.assertRaises(Exception):
                effect.material
            effect.close()

        self.assertTrue(in_game(body)["disposed"])
