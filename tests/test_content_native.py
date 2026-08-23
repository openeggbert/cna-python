from __future__ import annotations

import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, Matrix, Vector2, Vector3
from Microsoft.Xna.Framework.Content import ContentLoadException, ResourceContentManager
from Microsoft.Xna.Framework.Content._content import _register_content_type_reader
from Microsoft.Xna.Framework._title import _set_title_root_for_tests
from Microsoft.Xna.Framework.Graphics import (
    BasicEffect, IndexBuffer, Model, SpriteBatch, SpriteFont, Texture2D, VertexBuffer,
)

from .test_content import _compressed_xnb, _ExternalReader, _seven, _text, _xnb


NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
PREFIX = "Microsoft.Xna.Framework.Content."


def _texture_payload(width: int, height: int, levels: list[bytes]) -> bytes:
    result = bytearray(struct.pack("<iIII", 0, width, height, len(levels)))
    for level in levels:
        result.extend(struct.pack("<I", len(level)))
        result.extend(level)
    return bytes(result)


def _texture_xnb() -> bytes:
    level0 = bytes((255, 0, 0, 255, 0, 255, 0, 255,
                    0, 0, 255, 255, 255, 255, 255, 255))
    level1 = bytes((10, 20, 30, 255))
    return _xnb(
        [(PREFIX + "Texture2DReader", 0)],
        _seven(1) + _texture_payload(2, 2, [level0, level1]),
    )


def _spritefont_xnb() -> bytes:
    list_rectangle = PREFIX + "ListReader`1[[Microsoft.Xna.Framework.Rectangle]]"
    list_char = PREFIX + "ListReader`1[[System.Char]]"
    list_vector3 = PREFIX + "ListReader`1[[Microsoft.Xna.Framework.Vector3]]"
    nullable_char = PREFIX + "NullableReader`1[[System.Char]]"
    readers = [
        (PREFIX + "SpriteFontReader", 0),
        (PREFIX + "Texture2DReader", 0),
        (list_rectangle, 0),
        (PREFIX + "RectangleReader", 0),
        (list_char, 0),
        (PREFIX + "CharReader", 0),
        (list_vector3, 0),
        (PREFIX + "Vector3Reader", 0),
        (nullable_char, 0),
    ]
    body = bytearray(_seven(1))
    body.extend(_seven(2))
    body.extend(_texture_payload(1, 1, [bytes((255, 255, 255, 255))]))
    body.extend(_seven(3) + struct.pack("<iiiii", 1, 0, 0, 1, 1))
    body.extend(_seven(3) + struct.pack("<iiiii", 1, 0, 0, 1, 1))
    body.extend(_seven(5) + struct.pack("<i", 1) + b"A")
    body.extend(struct.pack("<if", 8, 0.0))
    body.extend(_seven(7) + struct.pack("<ifff", 1, 0.0, 1.0, 0.0))
    body.extend(_seven(9) + b"\x01A")
    return _xnb(readers, bytes(body))


def _vertex_xnb() -> bytes:
    readers = [
        (PREFIX + "VertexBufferReader", 0),
        (PREFIX + "VertexDeclarationReader", 0),
    ]
    # stride 16; Position/Vector3 at 0 and Color at 12.
    declaration = struct.pack("<ii", 16, 2)
    declaration += struct.pack("<iiii", 0, 2, 0, 0)
    declaration += struct.pack("<iiii", 12, 4, 1, 0)
    vertices = struct.pack("<fffBBBB", 1.0, 2.0, 3.0, 255, 0, 0, 255)
    return _xnb(readers, _seven(1) + declaration + struct.pack("<I", 1) + vertices)


def _index_xnb() -> bytes:
    payload = struct.pack("<HHH", 0, 1, 2)
    return _xnb(
        [(PREFIX + "IndexBufferReader", 0)],
        _seven(1) + b"\x01" + struct.pack("<i", len(payload)) + payload,
    )


def _model_xnb(*, root_reference: int = 1, parent_reference: int = 0,
               child_reference: int = 2, vertex_reference: int = 1,
               mesh_parent_reference: int = 2, index_reference: int = 2, effect_reference: int = 3,
               truncate_vertex: bool = False, truncate_index: bool = False) -> bytes:
    readers = [
        (PREFIX + "ModelReader", 0),
        (PREFIX + "StringReader", 0),
        (PREFIX + "VertexBufferReader", 0),
        (PREFIX + "IndexBufferReader", 0),
        (PREFIX + "BasicEffectReader", 0),
    ]
    body=bytearray(_seven(1)+struct.pack("<I",2))
    body.extend(_seven(2)+_text("Root")+struct.pack("<16f",*tuple(Matrix.Identity)))
    child=Matrix.CreateTranslation(2,0,0)
    body.extend(_seven(2)+_text("Child")+struct.pack("<16f",*tuple(child)))
    body.extend(bytes((parent_reference,))+struct.pack("<I",1)+bytes((child_reference,)))
    body.extend(b"\x01"+struct.pack("<I",0))
    body.extend(struct.pack("<i",1)+_seven(2)+_text("Triangle")+bytes((mesh_parent_reference,)))
    body.extend(struct.pack("<4f",0,0,0,2)+_seven(2)+_text("mesh-tag")+struct.pack("<i",2))
    for part_index in range(2):
        body.extend(struct.pack("<4i",0,3,0,1)+_seven(2)+_text(f"part-{part_index}"))
        body.extend(_seven(vertex_reference)+_seven(index_reference)+_seven(effect_reference))
    body.extend(bytes((root_reference,))+_seven(2)+_text("model-tag"))
    vertices=struct.pack("<ii",12,1)+struct.pack("<4i",0,2,0,0)+struct.pack("<I9f",3,0,0,0,1,0,0,0,1,0)
    if truncate_vertex:vertices=vertices[:-1]
    body.extend(_seven(3)+vertices)
    indices=b"\x01"+struct.pack("<i",6)+struct.pack("<3H",0,1,2)
    if truncate_index:indices=indices[:-1]
    body.extend(_seven(4)+indices)
    body.extend(_seven(5)+_text("")+struct.pack("<11f",1,1,1,0,0,0,1,1,1,16,1)+b"\x00")
    return _xnb(readers,bytes(body),shared_count=3)


def _compressed_model_xnb() -> bytes:
    # The complete legal graph is only 654 payload bytes, so one frame is the
    # canonical compact representation. Persistent two-frame state is covered
    # separately with a full 0x8000-byte first frame in test_content.
    return _compressed_xnb(_model_xnb())


@unittest.skipUnless(NATIVE and Path(NATIVE).is_file(), "CNA_NATIVE_LIBRARY is not configured")
class NativeContentTests(unittest.TestCase):
    def tearDown(self) -> None:
        _set_title_root_for_tests(None)

    def test_game_configures_and_reads_the_cna_title_location(self) -> None:
        asset = _xnb(
            [(PREFIX + "StringReader", 0)],
            _seven(1) + _text("native title route"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Content").mkdir()
            (root / "Content" / "message.xnb").write_bytes(asset)
            _set_title_root_for_tests(root)

            class Probe(Game):
                def __init__(self):
                    super().__init__()
                    self.manager = GraphicsDeviceManager(self)
                    self.Content.RootDirectory = "Content"

                def LoadContent(self):
                    self.message = self.Content.Load("message")

                def Draw(self, gameTime):
                    self.Exit()

            game = Probe()
            game.Run()
            self.assertEqual(game.message, "native title route")
            game.Dispose()

    def test_texture_spritefont_and_buffers_load_through_content_for_both_framings(self) -> None:
        testcase = self
        uncompressed = {
            "texture": _texture_xnb(),
            "font": _spritefont_xnb(),
            "vertices": _vertex_xnb(),
            "indices": _index_xnb(),
        }
        assets = dict(uncompressed)
        assets.update({f"compressed/{name}": _compressed_xnb(value) for name, value in uncompressed.items()})

        class Probe(Game):
            def __init__(self):
                super().__init__()
                self.manager = GraphicsDeviceManager(self)
                self.Content = ResourceContentManager(self.Services, assets)

            def LoadContent(self):
                self.loaded = {}
                for prefix in ("", "compressed/"):
                    texture = self.Content.Load(prefix + "texture")
                    font = self.Content.Load(prefix + "font")
                    vertices = self.Content.Load(prefix + "vertices")
                    indices = self.Content.Load(prefix + "indices")
                    testcase.assertIsInstance(texture, Texture2D)
                    testcase.assertIsInstance(font, SpriteFont)
                    testcase.assertIsInstance(vertices, VertexBuffer)
                    testcase.assertIsInstance(indices, IndexBuffer)
                    testcase.assertIs(texture, self.Content.Load(prefix + "texture"))
                    testcase.assertEqual((texture.Width, texture.Height, texture.LevelCount), (2, 2, 2))
                    level0 = [Color.Transparent for _ in range(4)]
                    level1 = [Color.Transparent]
                    texture.GetData(0, None, level0, 0, 4)
                    texture.GetData(1, None, level1, 0, 1)
                    testcase.assertEqual(
                        level0,
                        [Color.Red, Color(0, 255, 0, 255), Color.Blue, Color.White],
                    )
                    testcase.assertEqual(level1, [Color(10, 20, 30, 255)])
                    testcase.assertEqual(font.Characters, ("A",))
                    testcase.assertEqual(font.DefaultCharacter, "A")
                    testcase.assertEqual(font.MeasureString("AA"), Vector2(2, 8))
                    testcase.assertEqual((vertices.VertexCount, vertices.VertexDeclaration.VertexStride), (1, 16))
                    read_indices = [9, 9, 9]
                    indices.GetData(read_indices)
                    testcase.assertEqual(read_indices, [0, 1, 2])
                    self.loaded[prefix] = (texture, font, vertices, indices)
                self.batch = SpriteBatch(self.GraphicsDevice)

            def Draw(self, gameTime):
                self.batch.Begin()
                self.batch.DrawString(self.loaded[""][1], "A", Vector2.Zero, Color.White)
                self.batch.End()
                self.Exit()

        game = Probe()
        game.Run()
        game.Dispose()
        for resources in game.loaded.values():
            texture, font, vertices, indices = resources
            self.assertTrue(texture.IsDisposed)
            self.assertTrue(font._native.IsDisposed)
            self.assertTrue(vertices.IsDisposed)
            self.assertTrue(indices.IsDisposed)

    def test_model_xnb_uncompressed_compressed_shared_identity_draw_and_reload(self) -> None:
        testcase=self;external_identity="CnaPython.ModelExternalReader"
        assets={"model":_model_xnb(),"compressed/model":_compressed_model_xnb(),
                "external/root":_xnb([(external_identity,0)],_seven(1)+_text("../compressed/model"))}
        class Probe(Game):
            def __init__(self):
                super().__init__();self.manager=GraphicsDeviceManager(self);self.Content=ResourceContentManager(self.Services,assets);self.done=False
            def _verify(self,name):
                model=self.Content.Load(name);testcase.assertIsInstance(model,Model);testcase.assertIs(model,self.Content.Load(name))
                testcase.assertEqual((model.Bones.Count,model.Meshes.Count),(2,1));testcase.assertEqual(model.Root.Name,"Root")
                testcase.assertIs(model.Bones[1].Parent,model.Bones[0]);testcase.assertIs(model.Bones[0].Children[0],model.Bones[1])
                mesh=model.Meshes["Triangle"];testcase.assertIs(mesh.ParentBone,model.Bones[1]);testcase.assertEqual(mesh.Tag,"mesh-tag")
                testcase.assertEqual((mesh.BoundingSphere.Center,mesh.BoundingSphere.Radius),(Vector3.Zero,2.0));testcase.assertEqual(mesh.MeshParts.Count,2)
                first,second=mesh.MeshParts[0],mesh.MeshParts[1];testcase.assertEqual((first.Tag,second.Tag),("part-0","part-1"))
                testcase.assertIs(first.VertexBuffer,second.VertexBuffer);testcase.assertIs(first.IndexBuffer,second.IndexBuffer);testcase.assertIs(first.Effect,second.Effect)
                testcase.assertIsInstance(first.Effect,BasicEffect);testcase.assertEqual(mesh.Effects.Count,1);testcase.assertIs(mesh.Effects[0],first.Effect)
                model.Draw(Matrix.Identity,Matrix.Identity,Matrix.Identity)
                return model,model.Root,mesh,first,first.Effect.CurrentTechnique.Passes[0]
            def LoadContent(self):
                old=[]
                for name in ("model","compressed/model"):old.append(self._verify(name))
                external=self.Content.Load("external/root");testcase.assertIs(external.shared,self.Content.Load("compressed/model"))
                self.Content.Unload()
                for model,bone,mesh,part,effect_pass in old:
                    with testcase.assertRaises(RuntimeError):_ = model.Root
                    with testcase.assertRaises(RuntimeError):_ = bone.Name
                    with testcase.assertRaises(RuntimeError):_ = mesh.Name
                    with testcase.assertRaises(RuntimeError):_ = part.Effect
                    with testcase.assertRaises(RuntimeError):effect_pass.Apply()
                reloaded=self._verify("model")[0];testcase.assertIsNot(reloaded,old[0][0]);self.done=True;self.Exit()
        unregister=_register_content_type_reader(external_identity,_ExternalReader)
        try:
            game=Probe();game.Run();game.Dispose();self.assertTrue(game.done)
        finally:unregister()

    def test_model_xnb_malformed_graphs_roll_back_and_allow_later_success(self) -> None:
        testcase=self
        malformed={
            "bad-root":_model_xnb(root_reference=3),
            "bad-parent":_model_xnb(parent_reference=2),
            "bad-child":_model_xnb(child_reference=3),
            "bad-mesh-parent":_model_xnb(mesh_parent_reference=3),
            "bad-buffer-ref":_model_xnb(vertex_reference=4),
            "missing-effect":_model_xnb(effect_reference=0),
            "wrong-effect":_model_xnb(effect_reference=1),
            "truncated-vertex":_model_xnb(truncate_vertex=True),
            "truncated-index":_model_xnb(truncate_index=True),
        }
        assets={**malformed,"valid":_model_xnb()}
        class Probe(Game):
            def __init__(self):
                super().__init__();self.manager=GraphicsDeviceManager(self);self.Content=ResourceContentManager(self.Services,assets);self.done=False
            def LoadContent(self):
                for name in malformed:
                    with testcase.assertRaises(ContentLoadException):self.Content.Load(name)
                model=self.Content.Load("valid");testcase.assertEqual(model.Meshes.Count,1);model.Draw(Matrix.Identity,Matrix.Identity,Matrix.Identity)
                self.done=True;self.Exit()
        game=Probe();game.Run();game.Dispose();self.assertTrue(game.done)

    def test_model_xnb_native_construction_failures_release_partial_graph(self) -> None:
        testcase=self;assets={"buffer-failure":_model_xnb(),"effect-failure":_model_xnb(),"valid":_model_xnb()}
        class Probe(Game):
            def __init__(self):
                super().__init__();self.manager=GraphicsDeviceManager(self);self.Content=ResourceContentManager(self.Services,assets);self.done=False
            def LoadContent(self):
                with mock.patch.object(VertexBuffer,"_set_raw_bytes",autospec=True,side_effect=RuntimeError("injected buffer failure")):
                    with testcase.assertRaises(ContentLoadException):self.Content.Load("buffer-failure")
                testcase.assertNotIn("buffer-failure",self.Content._loaded_assets)
                with mock.patch.object(BasicEffect,"__init__",autospec=True,side_effect=RuntimeError("injected Effect failure")):
                    with testcase.assertRaises(ContentLoadException):self.Content.Load("effect-failure")
                testcase.assertNotIn("effect-failure",self.Content._loaded_assets)
                model=self.Content.Load("valid");model.Draw(Matrix.Identity,Matrix.Identity,Matrix.Identity)
                self.done=True;self.Exit()
        game=Probe();game.Run();game.Dispose();self.assertTrue(game.done)


if __name__ == "__main__":
    unittest.main()
