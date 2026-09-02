"""The compiled model graph: bones, meshes, parts, materials, skin, morphs, clips.

One deliberately asymmetric fixture carries the whole test. Nothing in it is
symmetric or repeated: the two parts have different vertex and index byte
lengths, the mesh names its parts in an order that is not their index order, the
three bones form a chain rather than a star, every material factor is distinct,
and every morph delta is non-zero. A trivial triangle would round-trip through a
codec that swapped two indices, permuted a mesh's parts, truncated a morph
stream, or reversed a bone's parent; this one cannot.

The round trip is not the only oracle. The encoded document is also inspected
directly -- its chunk set, its external references, and the ``XREF`` order the
schema's own indices depend on -- so a matched pair of encode/decode bugs is
still visible.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import unittest

from Microsoft.Xna.Framework import Matrix, Vector3

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb


def _matrix(seed: float) -> Matrix:
    """A matrix whose sixteen entries are all different, so a transpose shows."""
    return Matrix(*[seed + index for index in range(16)])


def _build_model():
    """The asymmetric fixture every test in this module works from."""
    model = cnb.CnbModelData.create()
    model.set_flags(applies_gltf_lighting_policy=True, has_bone_hierarchy=True)

    root = model.add_bone("root", -1, _matrix(1.0))
    spine = model.add_bone("spine", root, _matrix(100.0))
    head = model.add_bone("head", spine, _matrix(200.0))

    body = model.add_part(
        name="body", vertex_stride=8, vertex_count=4, index_count=6,
        index_element_size=2, primitive_count=2, effect_kind=cnb.EffectKind.Pbr,
        vertex_color_enabled=True)
    model.set_part_vertex_bytes(body, bytes(range(32)))
    model.set_part_index_bytes(body, struct.pack("<6H", 0, 1, 2, 0, 2, 3))

    hat = model.add_part(
        name="hat", external_effect="effects/custom", vertex_stride=4, vertex_count=3,
        index_count=6, index_element_size=4, primitive_count=2,
        effect_kind=cnb.EffectKind.External, unlit=True)
    model.set_part_vertex_bytes(hat, bytes(range(100, 112)))
    model.set_part_index_bytes(hat, struct.pack("<6I", 2, 0, 1, 1, 0, 2))

    model.set_material(body, cnb.CnbMaterial(
        base_color_factor=(0.125, 0.25, 0.375, 0.5), emissive_factor=(0.625, 0.75, 0.875),
        specular_color_factor=(1.0, 1.5, 2.5), metallic_factor=0.03125,
        roughness_factor=0.75, ior=1.25, specular_factor=0.5, normal_scale=2.0,
        occlusion_strength=0.125, alpha_cutoff=0.375, alpha_mode=1, double_sided=True,
        textures={cnb.MaterialTextureSlot.BaseColor: "tex/base",
                  cnb.MaterialTextureSlot.Normal: "tex/normal",
                  cnb.MaterialTextureSlot.SpecularColor: "tex/spec"},
        # The format allows only UV set 0 or 1; alternating them still detects a
        # per-slot shift, which a constant would not.
        coordinate_sets=(0, 1, 0, 1, 1, 0, 1),
        transforms=tuple(
            cnb.CnbTextureTransform(index, index + 0.5, 2.0 + index, 3.0 + index,
                                    0.25 * index)
            for index in range(cnb.TEXTURE_SLOT_COUNT)),
        samplers=tuple(
            cnb.CnbSamplerState(index % 3, (index + 1) % 3, (index + 2) % 3,
                                index % 2 == 0)
            for index in range(cnb.TEXTURE_SLOT_COUNT))))

    # Draw order that is not index order: a mesh that lost its own ordering
    # would still pass if the two agreed.
    model.add_mesh("mesh-upper", spine, [hat, body])
    model.add_mesh("mesh-lower", head, [body])

    model.set_skeleton(
        [-1, 0, 1],
        [_matrix(10.0 * (joint + 1)) for joint in range(3)],
        [_matrix(-10.0 * (joint + 1)) for joint in range(3)],
        root_prefix=[_matrix(1000.0 * (joint + 1)) for joint in range(3)])

    model.set_morph(body, vertex_count=4, recompute_flat_normals=True,
                    weight_track_cubic_spline=True)
    first = model.add_morph_target(body)
    second = model.add_morph_target(body)
    model.set_morph_target_deltas(body, first, cnb.MorphDeltaStream.Position,
                                  [0.5, -1.5, 2.5] * 4)
    model.set_morph_target_deltas(body, first, cnb.MorphDeltaStream.Normal,
                                  [0.25, 0.5, 0.75] * 4)
    model.set_morph_target_deltas(body, second, cnb.MorphDeltaStream.Tangent,
                                  [-3.0, 4.0, -5.0] * 4)
    model.set_morph_weights(body, [0.25, 0.75])
    model.add_morph_weight_key(body, 0.5, [0.125, 0.875],
                               in_tangents=[0.0, -1.0], out_tangents=[1.0, 2.0])

    model.add_animation("walk", 2.0, [
        cnb.CnbAnimationTrack(1, (
            cnb.CnbKeyframe(0.0, (1.0, 2.0, 3.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
            cnb.CnbKeyframe(1.0, (4.0, 5.0, 6.0), (0.0, 1.0, 0.0, 0.0), (2.0, 3.0, 4.0)))),
        cnb.CnbAnimationTrack(2, (
            cnb.CnbKeyframe(0.5, (7.0, 8.0, 9.0), (1.0, 0.0, 0.0, 0.0), (5.0, 6.0, 7.0)),)),
    ], target_space=cnb.ClipTargetSpace.SceneNode)

    model.add_light(cnb.CnbModelLight(Vector3(0.0, -1.0, 0.0),
                                      Vector3(1.0, 0.5, 0.25)))
    return model


def _snapshot(model) -> dict:
    """Every value the graph holds, as plain Python, for an exact comparison."""
    skeleton = model.skeleton()
    return {
        "info": model.info,
        "bones": model.bones,
        "parts": model.parts,
        "meshes": model.meshes,
        "skeleton": skeleton,
        "morph": model.morph(0),
        "morph_weights": model.morph_weights(0),
        "morph_deltas": tuple(
            (target, stream, model.morph_target_deltas(0, target, stream))
            for target in range(2) for stream in cnb.MorphDeltaStream),
        "morph_key": model.morph_weight_key(0, 0),
        "animations": model.animations,
        "lights": tuple((light.direction.X, light.direction.Y, light.direction.Z,
                         light.diffuse_color.X, light.diffuse_color.Y,
                         light.diffuse_color.Z) for light in model.lights),
    }


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ModelGraphTests(unittest.TestCase):
    def test_the_graph_reports_the_counts_and_flags_it_was_given(self) -> None:
        with _build_model() as model:
            info = model.info
            self.assertEqual(info.bone_count, 3)
            self.assertEqual(info.part_count, 2)
            self.assertEqual(info.mesh_count, 2)
            self.assertEqual(info.animation_count, 1)
            self.assertEqual(info.light_count, 1)
            self.assertTrue(info.has_skeleton)
            self.assertTrue(info.applies_gltf_lighting_policy)
            self.assertTrue(info.has_bone_hierarchy)

    def test_the_bone_chain_keeps_each_parent_and_each_transform(self) -> None:
        with _build_model() as model:
            names = [bone.name for bone in model.bones]
            parents = [bone.parent for bone in model.bones]
            self.assertEqual(names, ["root", "spine", "head"])
            self.assertEqual(parents, [-1, 0, 1], "a parent swap is a different chain")
            transform = model.bone(2).transform
            self.assertEqual(transform.M11, 200.0)
            self.assertEqual(transform.M44, 215.0)
            # Off-diagonal, so a transposed transform is a different number:
            # M12 and M21 are 201 and 204, and the diagonal cannot tell them
            # apart.
            self.assertEqual(transform.M12, 201.0)
            self.assertEqual(transform.M21, 204.0)

    def test_each_part_keeps_its_own_bytes_and_its_own_shape(self) -> None:
        with _build_model() as model:
            body, hat = model.parts
            self.assertEqual(body.name, "body")
            self.assertEqual(body.vertex_bytes, bytes(range(32)))
            self.assertEqual(body.index_bytes, struct.pack("<6H", 0, 1, 2, 0, 2, 3))
            self.assertEqual((body.vertex_stride, body.vertex_count), (8, 4))
            self.assertEqual((body.index_count, body.index_element_size), (6, 2))
            self.assertEqual(body.effect_kind, cnb.EffectKind.Pbr)
            self.assertTrue(body.vertex_color_enabled)
            self.assertFalse(body.unlit)
            self.assertEqual(body.external_effect, "")

            self.assertEqual(hat.name, "hat")
            self.assertEqual(hat.vertex_bytes, bytes(range(100, 112)))
            self.assertEqual(hat.index_bytes, struct.pack("<6I", 2, 0, 1, 1, 0, 2))
            # Different lengths on purpose: a codec that shared one buffer
            # between parts would show up here rather than in a symmetric pair.
            self.assertNotEqual(len(body.vertex_bytes), len(hat.vertex_bytes))
            self.assertNotEqual(len(body.index_bytes), len(hat.index_bytes))
            self.assertEqual(hat.index_element_size, 4)
            self.assertEqual(hat.external_effect, "effects/custom")
            self.assertTrue(hat.unlit)

    def test_a_partial_part_update_leaves_every_other_field_alone(self) -> None:
        with _build_model() as model:
            before = model.part(0)
            model.set_part(0, primitive_count=99)
            after = model.part(0)
            self.assertEqual(after.primitive_count, 99)
            self.assertEqual(after.vertex_stride, before.vertex_stride)
            self.assertEqual(after.effect_kind, before.effect_kind)
            self.assertEqual(after.vertex_color_enabled, before.vertex_color_enabled)

    def test_the_mesh_keeps_its_own_draw_order(self) -> None:
        with _build_model() as model:
            upper, lower = model.meshes
            self.assertEqual(upper.name, "mesh-upper")
            self.assertEqual(upper.parent_bone, 1)
            # Declared as [hat, body] -- index order would be [body, hat].
            self.assertEqual(upper.part_indices, (1, 0))
            self.assertEqual(lower.part_indices, (0,))
            self.assertEqual(lower.parent_bone, 2)

    def test_the_material_keeps_every_factor_and_every_slot_apart(self) -> None:
        with _build_model() as model:
            material = model.part(0).material
            # Every value is exactly representable in binary32, which is what
            # the format stores; an exact assertion is then a real one.
            self.assertEqual(material.base_color_factor, (0.125, 0.25, 0.375, 0.5))
            self.assertEqual(material.emissive_factor, (0.625, 0.75, 0.875))
            self.assertEqual(material.specular_color_factor, (1.0, 1.5, 2.5))
            self.assertEqual(material.metallic_factor, 0.03125)
            self.assertEqual(material.roughness_factor, 0.75)
            self.assertEqual(material.ior, 1.25)
            self.assertEqual(material.specular_factor, 0.5)
            self.assertEqual(material.normal_scale, 2.0)
            self.assertEqual(material.occlusion_strength, 0.125)
            self.assertEqual(material.alpha_cutoff, 0.375)
            self.assertEqual(material.alpha_mode, 1)
            self.assertTrue(material.double_sided)
            self.assertEqual(material.textures, {
                cnb.MaterialTextureSlot.BaseColor: "tex/base",
                cnb.MaterialTextureSlot.Normal: "tex/normal",
                cnb.MaterialTextureSlot.SpecularColor: "tex/spec"})
            self.assertEqual(material.coordinate_sets, (0, 1, 0, 1, 1, 0, 1))
            self.assertEqual(len(material.transforms), cnb.TEXTURE_SLOT_COUNT)
            self.assertEqual(material.transforms[3].offset_x, 3.0)
            self.assertEqual(material.transforms[3].rotation, 0.75)
            self.assertEqual(material.samplers[3].filter, 0)
            self.assertFalse(material.samplers[3].declared)
            self.assertTrue(material.samplers[4].declared)

    def test_the_two_texture_index_spaces_stay_apart(self) -> None:
        """The eight material texture *names* are not the seven per-slot arrays.

        The names include ``DualTextureEffect``'s second layer, which glTF has no
        counterpart for; the coordinate sets, transforms and samplers are in the
        importer's own seven-slot order. Conflating them is the trap this test
        exists to catch.
        """
        self.assertEqual(len(cnb.MaterialTextureSlot), 8)
        self.assertEqual(cnb.TEXTURE_SLOT_COUNT, 7)
        with _build_model() as model:
            # Slot 7 is a name and has no per-slot array entry at all.
            model.set_material_texture(0, cnb.MaterialTextureSlot.SpecularColor,
                                       "tex/only-a-name")
            self.assertEqual(
                model.material_texture(0, cnb.MaterialTextureSlot.SpecularColor),
                "tex/only-a-name")
            with self.assertRaises(cnb.CnbError):
                model.material_texture_coordinate_set(0, cnb.TEXTURE_SLOT_COUNT)

    def test_the_skeleton_keeps_its_hierarchy_and_all_three_matrix_arrays(self) -> None:
        with _build_model() as model:
            skeleton = model.skeleton()
            self.assertIsNotNone(skeleton)
            self.assertEqual(skeleton.joint_count, 3)
            self.assertEqual(skeleton.hierarchy, (-1, 0, 1))
            self.assertEqual([matrix.M11 for matrix in skeleton.bind_pose],
                             [10.0, 20.0, 30.0])
            self.assertEqual([matrix.M11 for matrix in skeleton.inverse_bind_pose],
                             [-10.0, -20.0, -30.0])
            self.assertEqual([matrix.M11 for matrix in skeleton.root_prefix],
                             [1000.0, 2000.0, 3000.0])

    def test_an_absent_root_prefix_is_stated_rather_than_inferred(self) -> None:
        # The sidecar format signalled it by leftover bytes, which made
        # "deliberately absent" and "truncated" the same observation.
        with cnb.CnbModelData.create() as model:
            model.set_skeleton([-1], [_matrix(1.0)], [_matrix(2.0)])
            skeleton = model.skeleton()
            self.assertEqual(skeleton.root_prefix, ())
            self.assertEqual(skeleton.joint_count, 1)

    def test_clearing_the_skeleton_removes_it(self) -> None:
        with _build_model() as model:
            model.clear_skeleton()
            self.assertFalse(model.info.has_skeleton)
            self.assertIsNone(model.skeleton())
            model.clear_skeleton()  # a model with none is still a success

    def test_a_skeleton_whose_arrays_disagree_is_refused(self) -> None:
        with cnb.CnbModelData.create() as model:
            with self.assertRaises(ValueError):
                model.set_skeleton([-1, 0], [_matrix(1.0)], [_matrix(2.0)])
            with self.assertRaises(ValueError):
                model.set_skeleton([-1], [_matrix(1.0)], [_matrix(2.0)],
                                   root_prefix=[_matrix(3.0), _matrix(4.0)])

    def test_every_morph_stream_stays_in_its_own_stream(self) -> None:
        with _build_model() as model:
            self.assertTrue(model.has_morph(0))
            self.assertFalse(model.has_morph(1))
            morph = model.morph(0)
            self.assertEqual(morph.vertex_count, 4)
            self.assertEqual(morph.target_count, 2)
            self.assertEqual(morph.weight_count, 2)
            self.assertEqual(morph.weight_track_key_count, 1)
            self.assertTrue(morph.recompute_flat_normals)
            self.assertTrue(morph.weight_track_cubic_spline)
            self.assertFalse(morph.weight_track_step_interpolation)

            self.assertEqual(model.morph_target_deltas(0, 0, cnb.MorphDeltaStream.Position),
                             (0.5, -1.5, 2.5) * 4)
            self.assertEqual(model.morph_target_deltas(0, 0, cnb.MorphDeltaStream.Normal),
                             (0.25, 0.5, 0.75) * 4)
            # Target 0 has no tangents and target 1 has only tangents: a stream
            # or target mix-up is an empty tuple where values belong.
            self.assertEqual(model.morph_target_deltas(0, 0, cnb.MorphDeltaStream.Tangent),
                             ())
            self.assertEqual(model.morph_target_deltas(0, 1, cnb.MorphDeltaStream.Tangent),
                             (-3.0, 4.0, -5.0) * 4)
            self.assertEqual(model.morph_target_deltas(0, 1, cnb.MorphDeltaStream.Position),
                             ())
            self.assertEqual(model.morph_weights(0), (0.25, 0.75))

            key = model.morph_weight_key(0, 0)
            self.assertEqual(key.time_seconds, 0.5)
            self.assertEqual(key.weights, (0.125, 0.875))
            self.assertEqual(key.in_tangents, (0.0, -1.0))
            self.assertEqual(key.out_tangents, (1.0, 2.0))

    def test_clearing_morph_data_removes_it(self) -> None:
        with _build_model() as model:
            model.clear_morph(0)
            self.assertFalse(model.has_morph(0))
            model.clear_morph(0)  # a part with none is still a success
            model.clear_morph(1)

    def test_a_part_with_no_morph_data_refuses_a_morph_read(self) -> None:
        with _build_model() as model:
            with self.assertRaises(cnb.CnbError):
                model.morph(1)
            with self.assertRaises(cnb.CnbError):
                model.add_morph_target(1)

    def test_the_animation_keeps_its_tracks_its_bones_and_its_space(self) -> None:
        with _build_model() as model:
            animation, = model.animations
            self.assertEqual(animation.name, "walk")
            self.assertEqual(animation.duration_seconds, 2.0)
            self.assertEqual(animation.target_space, cnb.ClipTargetSpace.SceneNode)
            self.assertEqual([track.bone_index for track in animation.tracks], [1, 2])
            self.assertEqual([len(track.keyframes) for track in animation.tracks], [2, 1])
            first = animation.tracks[0].keyframes[1]
            self.assertEqual(first.time_seconds, 1.0)
            self.assertEqual(first.translation, (4.0, 5.0, 6.0))
            self.assertEqual(first.rotation, (0.0, 1.0, 0.0, 0.0))
            self.assertEqual(first.scale, (2.0, 3.0, 4.0))

    def test_the_light_keeps_its_direction_and_its_colour_apart(self) -> None:
        with _build_model() as model:
            light, = model.lights
            self.assertEqual((light.direction.X, light.direction.Y, light.direction.Z),
                             (0.0, -1.0, 0.0))
            self.assertEqual((light.diffuse_color.X, light.diffuse_color.Y,
                              light.diffuse_color.Z), (1.0, 0.5, 0.25))


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class ModelCodecTests(unittest.TestCase):
    def test_the_encoded_document_carries_the_schema_chunks_and_its_references(self) -> None:
        with _build_model() as model:
            image = cnb.encode_model(model, content_name="models/hero")
        with cnb.CnbDocument.parse(image, origin="hero.cnb") as document:
            self.assertEqual(document.asset_type, cnb.AssetType.Model)
            self.assertEqual(document.asset_schema_version, cnb.MODEL_SCHEMA_VERSION)
            self.assertEqual(document.metadata.content_name, "models/hero")
            for identity in (cnb.ModelChunk.Header, cnb.ModelChunk.Strings,
                             cnb.ModelChunk.Bones, cnb.ModelChunk.Meshes,
                             cnb.ModelChunk.Materials, cnb.ModelChunk.Skeleton,
                             cnb.ModelChunk.Animations, cnb.ModelChunk.Lights):
                self.assertIsNotNone(document.find_single(int(identity)), identity.name)
            # One vertex and one index chunk per part, plus one morph chunk.
            self.assertEqual(len(document.find_all(int(cnb.ModelChunk.VertexData))), 2)
            self.assertEqual(len(document.find_all(int(cnb.ModelChunk.IndexData))), 2)
            self.assertEqual(len(document.find_all(int(cnb.ModelChunk.MorphData))), 1)
            # Bones at the schema's own stride: three of them, 72 bytes each.
            bones = document.chunk(document.require_single(int(cnb.ModelChunk.Bones)))
            self.assertEqual(bones.uncompressed_size, 3 * 72)
            # Textures and the external effect are logical names in XREF, in the
            # order the schema's own indices expect -- not embedded bytes.
            self.assertEqual([r.name for r in document.external_references],
                             ["tex/base", "tex/normal", "tex/spec", "effects/custom"])

    def test_the_whole_graph_survives_encoding_and_decoding(self) -> None:
        with _build_model() as model:
            before = _snapshot(model)
            image = cnb.encode_model(model, content_name="models/hero")
        with cnb.CnbDocument.parse(image) as document:
            with cnb.decode_model(document) as decoded:
                after = _snapshot(decoded)
        for key in before:
            self.assertEqual(before[key], after[key], key)

    def test_encoding_twice_gives_byte_identical_output(self) -> None:
        with _build_model() as model:
            self.assertEqual(cnb.encode_model(model, content_name="m"),
                             cnb.encode_model(model, content_name="m"))

    def test_an_index_that_addresses_a_vertex_the_part_does_not_have_is_refused(self) -> None:
        # The decoder validates the geometry rather than trusting it, which is
        # what stops a compiled file becoming an out-of-range draw.
        with cnb.CnbModelData.create() as model:
            part = model.add_part(vertex_stride=4, vertex_count=3, index_count=3,
                                  index_element_size=2, primitive_count=1)
            model.set_part_vertex_bytes(part, bytes(12))
            model.set_part_index_bytes(part, struct.pack("<3H", 0, 1, 99))
            model.add_mesh("m", -1, [part])
            image = cnb.encode_model(model)
        with cnb.CnbDocument.parse(image) as document:
            with self.assertRaises(cnb.CnbFormatError) as caught:
                cnb.decode_model(document)
            self.assertIn("99", str(caught.exception))

    def test_geometry_bytes_that_disagree_with_the_declared_shape_are_refused(self) -> None:
        # CNA refuses at encode time, naming the file; the wrapper refuses at the
        # call that supplied the wrong buffer, naming both numbers.
        with cnb.CnbModelData.create() as model:
            part = model.add_part(vertex_stride=4, vertex_count=3, index_count=3,
                                  index_element_size=2, primitive_count=1)
            with self.assertRaises(ValueError) as caught:
                model.set_part_vertex_bytes(part, bytes(11))
            self.assertIn("12", str(caught.exception))
            with self.assertRaises(ValueError):
                model.set_part_index_bytes(part, bytes(5))

    def test_a_texture_coordinate_set_outside_the_format_is_refused(self) -> None:
        # CNA's vertex layouts carry at most two UV sets; a compiled material
        # naming a third could not be drawn.
        with _build_model() as model:
            model.set_material_texture_coordinate_set(0, 0, 2)
            with self.assertRaises(cnb.CnbFormatError):
                image = cnb.encode_model(model)
                with cnb.CnbDocument.parse(image) as document:
                    cnb.decode_model(document)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
