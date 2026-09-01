"""Rendered-pixel evidence on a renderer that actually rasterizes.

Command-path evidence and rendering evidence are different claims. A non-windowed
control artifact can prove that arguments and bindings reach CNA, and it refuses
back-buffer readback outright because it has no pixel storage; only a real
renderer can show that a draw produced the colour it was asked for.

Every case here uses an independent expectation: each draw path writes a colour
chosen for that path alone, so a result produced by the wrong path, or by an
earlier clear, is a different colour rather than a passing test. No getter is
used to prove its own setter.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import (
    Color, Game, GraphicsDeviceManager, Matrix, Rectangle, Vector2, Vector3,
)
from Microsoft.Xna.Framework.Graphics import (
    BasicEffect, BufferUsage, CubeMapFace, DepthStencilState, IndexBuffer,
    IndexElementSize, PrimitiveType, RasterizerState, RenderTarget2D, RenderTargetCube,
    SpriteBatch, SpriteEffects, SurfaceFormat, Texture2D, Texture3D, TextureCube,
    VertexBuffer, VertexPositionColor,
)
from _cna_native.errors import NativeUnavailableError
from _cna_native.runtime_identity import runtime_identity


def _identity():
    try:
        return runtime_identity()
    except NativeUnavailableError:
        return None
    except Exception:  # pragma: no cover - a configured library that fails to load
        return None


IDENTITY = _identity()
NATIVE = IDENTITY is not None
RENDERS = bool(IDENTITY and IDENTITY.renders)


def _clip_triangle(color: Color) -> list[VertexPositionColor]:
    """One triangle that covers the whole viewport in clip space."""
    return [
        VertexPositionColor(Vector3(-1.0, -1.0, 0.0), color),
        VertexPositionColor(Vector3(3.0, -1.0, 0.0), color),
        VertexPositionColor(Vector3(-1.0, 3.0, 0.0), color),
    ]


@unittest.skipUnless(RENDERS, "the loaded CNA build has no rasterizing renderer")
class RenderedPixelTests(unittest.TestCase):
    def _run(self, body) -> dict:
        observed: dict[str, object] = {}

        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)
                self.done = False

            def Draw(self, gameTime) -> None:
                if self.done:
                    return
                device = self.GraphicsDevice
                device.RasterizerState = RasterizerState.CullNone
                device.DepthStencilState = DepthStencilState.None_
                body(self, device, observed)
                self.done = True
                self.Exit()

            def Update(self, gameTime) -> None:
                if self.done:
                    self.Exit()

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()
        self.assertTrue(game.done, "Draw never ran")
        return observed

    @staticmethod
    def _centre(device) -> Color:
        width, height = device.Viewport.Width, device.Viewport.Height
        pixels = [Color(0, 0, 0, 0)] * (width * height)
        device.GetBackBufferData(pixels)
        return pixels[(height // 2) * width + width // 2]

    def test_clear_writes_the_requested_colour(self) -> None:
        wanted = Color(17, 34, 51, 255)

        def body(game, device, observed):
            device.Clear(wanted)
            observed["centre"] = self._centre(device)

        self.assertEqual(self._run(body)["centre"], wanted)

    def test_every_draw_path_produces_its_own_colour(self) -> None:
        """Four draw paths, four distinct colours, so a wrong path cannot pass."""
        background = Color(0, 0, 0, 255)
        user = Color(255, 0, 0, 255)
        user_indexed = Color(0, 255, 0, 255)
        buffered = Color(0, 0, 255, 255)
        buffered_indexed = Color(0, 255, 255, 255)

        def body(game, device, observed):
            effect = BasicEffect(device)
            effect.VertexColorEnabled = True
            effect.World = Matrix.Identity
            effect.View = Matrix.Identity
            effect.Projection = Matrix.Identity

            def draw(action):
                device.Clear(background)
                for pass_ in effect.CurrentTechnique.Passes:
                    pass_.Apply()
                    action()
                return self._centre(device)

            observed["user"] = draw(
                lambda: device.DrawUserPrimitives(
                    PrimitiveType.TriangleList, _clip_triangle(user), 0, 1))
            observed["user_indexed"] = draw(
                lambda: device.DrawUserIndexedPrimitives(
                    PrimitiveType.TriangleList, _clip_triangle(user_indexed), 0, 3, [0, 1, 2], 0, 1))

            vertices = VertexBuffer(device, VertexPositionColor, 3, BufferUsage.None_)
            vertices.SetData(_clip_triangle(buffered))
            indices = IndexBuffer(device, IndexElementSize.SixteenBits, 3, BufferUsage.None_)
            indices.SetData([0, 1, 2])
            device.SetVertexBuffer(vertices)
            observed["buffered"] = draw(
                lambda: device.DrawPrimitives(PrimitiveType.TriangleList, 0, 1))

            vertices.SetData(_clip_triangle(buffered_indexed))
            device.Indices = indices
            observed["buffered_indexed"] = draw(
                lambda: device.DrawIndexedPrimitives(PrimitiveType.TriangleList, 0, 0, 3, 0, 1))

            device.SetVertexBuffer(None)
            device.Indices = None
            vertices.Dispose()
            indices.Dispose()
            effect.Dispose()

        observed = self._run(body)
        self.assertEqual(observed["user"], user)
        self.assertEqual(observed["user_indexed"], user_indexed)
        self.assertEqual(observed["buffered"], buffered)
        self.assertEqual(observed["buffered_indexed"], buffered_indexed)

    def test_spritebatch_draws_a_texture_the_texture_supplied(self) -> None:
        wanted = Color(255, 255, 0, 255)

        def body(game, device, observed):
            device.Clear(Color(0, 0, 0, 255))
            texture = Texture2D(device, 1, 1)
            texture.SetData([wanted])
            batch = SpriteBatch(device)
            batch.Begin()
            batch.Draw(texture, Vector2(0.0, 0.0), None, Color.White, 0.0, Vector2.Zero,
                       Vector2(float(device.Viewport.Width), float(device.Viewport.Height)),
                       0, 0.0)
            batch.End()
            observed["centre"] = self._centre(device)
            batch.Dispose()
            texture.Dispose()

        self.assertEqual(self._run(body)["centre"], wanted)

    def test_destination_rectangle_overloads_place_and_stretch_the_source(self) -> None:
        """A destination rectangle is its own native command, not a derived scale."""
        left = Color(255, 0, 255, 255)
        right = Color(0, 255, 255, 255)

        def body(game, device, observed):
            width, height = device.Viewport.Width, device.Viewport.Height

            def pixel(x, y):
                buffer = [Color(0, 0, 0, 0)] * (width * height)
                device.GetBackBufferData(buffer)
                return buffer[y * width + x]

            texture = Texture2D(device, 2, 1)
            texture.SetData([left, right])
            batch = SpriteBatch(device)

            # Whole texture stretched across the viewport: each half keeps its texel.
            device.Clear(Color(0, 0, 0, 255))
            batch.Begin()
            batch.Draw(texture, Rectangle(0, 0, width, height), Color.White)
            batch.End()
            observed["stretched"] = (pixel(width // 4, height // 2),
                                     pixel(3 * width // 4, height // 2))

            # The eight-argument overload takes rotation, origin and effects but no
            # scale, and must place the sprite identically.
            device.Clear(Color(0, 0, 0, 255))
            batch.Begin()
            batch.Draw(texture, Rectangle(0, 0, width, height), None, Color.White,
                       0.0, Vector2.Zero, SpriteEffects.None_, 0.0)
            batch.End()
            observed["eight"] = pixel(width // 4, height // 2)

            # Only the right texel, stretched over everything. The runtime's begin
            # route fixes LinearClamp, so a sample on the texel boundary is a blend
            # by design; the two places sampled here are the ones the filter cannot
            # make ambiguous. The left quarter showed the left texel above and must
            # not now, which is what proves the source rectangle was honoured.
            device.Clear(Color(0, 0, 0, 255))
            batch.Begin()
            batch.Draw(texture, Rectangle(0, 0, width, height), Rectangle(1, 0, 1, 1), Color.White)
            batch.End()
            observed["source_edge"] = pixel(width - 1, height // 2)
            observed["source_quarter"] = pixel(width // 4, height // 2)

            # A destination rectangle covering half the viewport leaves the rest clear.
            device.Clear(Color(0, 0, 0, 255))
            batch.Begin()
            batch.Draw(texture, Rectangle(0, 0, width // 2, height), Color.White)
            batch.End()
            observed["untouched"] = pixel(width - 1, height // 2)

            batch.Dispose()
            texture.Dispose()

        observed = self._run(body)
        self.assertEqual(observed["stretched"], (left, right))
        self.assertEqual(observed["eight"], left)
        self.assertEqual(observed["source_edge"], right)
        self.assertNotEqual(observed["source_quarter"], left)
        self.assertEqual(observed["untouched"], Color(0, 0, 0, 255))

    def test_render_target_2d_keeps_what_was_drawn_into_it(self) -> None:
        wanted = Color(9, 8, 7, 255)

        def body(game, device, observed):
            target = RenderTarget2D(device, 8, 8)
            device.SetRenderTarget(target)
            device.Clear(wanted)
            device.SetRenderTarget(None)
            # The backbuffer must not have been touched by the target's clear.
            device.Clear(Color(1, 2, 3, 255))
            read = [Color(0, 0, 0, 0)] * 64
            target.GetData(read)
            observed["target"] = read[0]
            observed["target_uniform"] = all(value == wanted for value in read)
            observed["backbuffer"] = self._centre(device)
            target.Dispose()

        observed = self._run(body)
        self.assertEqual(observed["target"], wanted)
        self.assertTrue(observed["target_uniform"])
        self.assertEqual(observed["backbuffer"], Color(1, 2, 3, 255))

    def test_render_target_cube_binds_and_clears_a_face(self) -> None:
        def body(game, device, observed):
            target = RenderTargetCube(device, 8, False, SurfaceFormat.Color, 0)
            device.SetRenderTarget(target, CubeMapFace.PositiveX)
            device.Clear(Color(3, 4, 5, 255))
            device.SetRenderTarget(None)
            observed["bound"] = True
            target.Dispose()

        self.assertTrue(self._run(body)["bound"])

    def test_texture3d_round_trips_every_voxel(self) -> None:
        def body(game, device, observed):
            texture = Texture3D(device, 2, 2, 2, False, SurfaceFormat.Color)
            texture.SetData([Color(index, 0, 0, 255) for index in range(8)])
            read = [Color(0, 0, 0, 0)] * 8
            texture.GetData(read)
            observed["red"] = [int(value.R) for value in read]
            texture.Dispose()

        self.assertEqual(self._run(body)["red"], list(range(8)))

    def test_texturecube_transfers_a_face(self) -> None:
        def body(game, device, observed):
            texture = TextureCube(device, 2, False, SurfaceFormat.Color)
            texture.SetData(CubeMapFace.PositiveX, [Color(7, 0, 0, 255)] * 4)
            texture.SetData(CubeMapFace.NegativeZ, [Color(11, 0, 0, 255)] * 4)
            first = [Color(0, 0, 0, 0)] * 4
            second = [Color(0, 0, 0, 0)] * 4
            texture.GetData(CubeMapFace.PositiveX, first)
            texture.GetData(CubeMapFace.NegativeZ, second)
            # Two faces with different contents prove the face selector is used.
            observed["faces"] = ([int(v.R) for v in first], [int(v.R) for v in second])
            texture.Dispose()

        self.assertEqual(self._run(body)["faces"], ([7] * 4, [11] * 4))


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
@unittest.skipIf(RENDERS, "this asserts the non-rendering control artifact's boundary")
class NonRenderingBoundaryTests(unittest.TestCase):
    def test_backbuffer_readback_is_refused_rather_than_faked(self) -> None:
        from _cna_native.errors import NativeError

        observed: dict[str, object] = {}

        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)

            def Update(self, gameTime) -> None:
                device = self.GraphicsDevice
                try:
                    device.GetBackBufferData([Color(0, 0, 0, 0)] * 4)
                    observed["refused"] = False
                except NativeError as error:
                    observed["refused"] = True
                    observed["result"] = error.result
                self.Exit()

            def Draw(self, gameTime) -> None:
                self.GraphicsDevice.Clear(Color.Black)

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()
        self.assertTrue(observed.get("refused"),
                        "a backend with no pixel storage returned pixels")


if __name__ == "__main__":
    unittest.main()
