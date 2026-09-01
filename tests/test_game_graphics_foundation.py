from __future__ import annotations

import copy
import io
import math
import unittest

from Microsoft.Xna.Framework import (
    Color, DrawableGameComponent, Game, GameComponent, GameTime, GraphicsDeviceInformation,
    GraphicsDeviceManager, IGraphicsDeviceManager, Matrix, Rectangle, Vector2,
    Vector3,
)
from Microsoft.Xna.Framework.Graphics import (
    Blend, BlendState, BufferUsage, DynamicIndexBuffer, DynamicVertexBuffer,
    GraphicsProfile, IGraphicsDeviceService, IndexBuffer, IndexElementSize,
    PrimitiveType, RenderTarget2D, SamplerState, SetDataOptions, SpriteBatch,
    SpriteFont, SurfaceFormat, Texture2D, ResourceCreatedEventArgs,
    ResourceDestroyedEventArgs, VertexBuffer, VertexBufferBinding,
    VertexDeclaration, VertexElement, VertexElementFormat, VertexElementUsage,
    VertexPositionColor, VertexPositionColorTexture, Viewport,
)
from _cna_native.errors import NativeError


class _OrderedComponent(GameComponent):
    def __init__(self, game, name, log):
        super().__init__(game); self.name, self.log = name, log
    def Update(self, gameTime): self.log.append(self.name)


class GameObjectModelTests(unittest.TestCase):
    def test_services_are_exact_keyed_isolated_and_manager_registered(self):
        first, second = Game(), Game()
        manager = GraphicsDeviceManager(first)
        self.assertIs(first.Services.GetService(IGraphicsDeviceManager), manager)
        self.assertIs(first.Services.GetService(IGraphicsDeviceService), manager)
        self.assertIsNone(second.Services.GetService(IGraphicsDeviceManager))
        with self.assertRaises(ValueError):
            first.Services.AddService(IGraphicsDeviceManager, manager)
        with self.assertRaises(TypeError):
            first.Services.AddService(Game, None)
        first.Dispose(); second.Dispose()

    def test_component_snapshot_order_mutation_and_events(self):
        game, log = Game(), []
        first = _OrderedComponent(game, "first", log)
        second = _OrderedComponent(game, "second", log)
        first.UpdateOrder = second.UpdateOrder = 4
        game.Components.Add(first); game.Components.Add(second)
        removed = []
        game.Components.ComponentRemoved += lambda sender, args: removed.append(args.GameComponent)
        first.Update = lambda time: (log.append("first"), game.Components.Remove(first))
        time = GameTime()
        game.Initialize(); game.Update(time)
        self.assertEqual(log, ["first", "second"])
        self.assertEqual(removed, [first])
        game.Update(time)
        self.assertEqual(log, ["first", "second", "second"])
        game.Dispose()

    def test_component_collection_duplicate_replacement_clear_and_live_enabled(self):
        game, log = Game(), []
        first = _OrderedComponent(game, "first", log)
        second = _OrderedComponent(game, "second", log)
        game.Components.Add(first); game.Components.Add(second)
        with self.assertRaises(ValueError): game.Components.Add(first)
        with self.assertRaises(RuntimeError): game.Components[0] = second

        first.Update = lambda time: setattr(second, "Enabled", False)
        game.Update(GameTime())
        self.assertEqual(log, [])

        observed_counts = []
        game.Components.ComponentRemoved += (
            lambda sender, args: observed_counts.append(sender.Count))
        game.Components.Clear()
        self.assertEqual(observed_counts, [2, 2])
        self.assertEqual(game.Components.Count, 0)

        game.Components.Add(first)
        disposed = []
        first.Disposed += lambda sender, args: disposed.append(sender)
        first.Dispose(False)
        self.assertEqual(game.Components.Count, 1)
        first.Dispose(); first.Dispose()
        self.assertEqual(disposed, [first])
        self.assertEqual(game.Components.Count, 0)
        game.Dispose()

    def test_viewport_projection_round_trip_and_value_edges(self):
        viewport = Viewport(10, 20, 640, 480)
        viewport.MinDepth, viewport.MaxDepth = 0.2, 0.8
        source = Vector3(0.25, -0.5, 0.4)
        projected = viewport.Project(source, Matrix.Identity, Matrix.Identity, Matrix.Identity)
        restored = viewport.Unproject(projected, Matrix.Identity, Matrix.Identity, Matrix.Identity)
        self.assertAlmostEqual(restored.X, source.X, places=5)
        self.assertAlmostEqual(restored.Y, source.Y, places=5)
        self.assertAlmostEqual(restored.Z, source.Z, places=5)
        self.assertEqual(Viewport(0, 0, 0, 480).AspectRatio, 0.0)
        degenerate = Viewport(0, 0, 0, 0).Unproject(
            Vector3.Zero, Matrix.Identity, Matrix.Identity, Matrix.Identity)
        self.assertTrue(any(not math.isfinite(value) for value in degenerate))

    def test_vertex_values_are_explicit_value_copies(self):
        value = VertexPositionColorTexture(Vector3(1, 2, 3), Color.Red, Vector2(4, 5))
        duplicate = copy.copy(value)
        duplicate.Position.X = 9
        self.assertEqual(value.Position.X, 1.0)
        self.assertEqual(VertexPositionColor.VertexDeclaration.VertexStride, 16)
        self.assertEqual(VertexPositionColorTexture.VertexDeclaration.VertexStride, 24)
        element = VertexElement(12, VertexElementFormat.Color,
                                VertexElementUsage.Color, 0)
        self.assertEqual(copy.copy(element), element)

    def test_state_defaults_and_prebind_mutability(self):
        state = BlendState()
        self.assertEqual(state.ColorSourceBlend, Blend.One)
        self.assertEqual(state.ColorDestinationBlend, Blend.Zero)
        state.ColorSourceBlend = Blend.SourceAlpha
        self.assertEqual(state.ColorSourceBlend, Blend.SourceAlpha)
        self.assertEqual(SamplerState.LinearWrap.Name, "SamplerState.LinearWrap")
        with self.assertRaises(RuntimeError):
            SamplerState.LinearWrap.MaxAnisotropy = 8

    def test_resource_event_argument_identity_is_ready_without_fake_events(self):
        resource = object()
        created = ResourceCreatedEventArgs._create(resource)
        destroyed = ResourceDestroyedEventArgs._create("texture", resource)
        self.assertIs(created.Resource, resource)
        self.assertEqual(destroyed.Name, "texture")
        self.assertIs(destroyed.Tag, resource)
        with self.assertRaises(TypeError): ResourceCreatedEventArgs(resource)


class NativeGraphicsFoundationTests(unittest.TestCase):
    def test_owned_buffers_bindings_targets_encoding_and_sprite_font(self):
        testcase = self

        class FoundationGame(Game):
            def __init__(self):
                super().__init__(); self.manager = GraphicsDeviceManager(self)
                self.completed = False
                self.manager_events = []
                self.manager.PreparingDeviceSettings += (
                    lambda sender, args: self.manager_events.append("preparing"))
                self.manager.DeviceCreated += (
                    lambda sender, args: self.manager_events.append("created"))
                self.Activated += lambda sender, args: self.manager_events.append("activated")
                self.Deactivated += lambda sender, args: self.manager_events.append("deactivated")

            def LoadContent(self):
                device = self.GraphicsDevice
                testcase.assertIn("preparing", self.manager_events)
                testcase.assertIn("created", self.manager_events)
                testcase.assertNotIn("activated", self.manager_events)
                testcase.assertNotIn("deactivated", self.manager_events)
                # XNA exposes the platform window handle. A windowed renderer supplies a
                # real one and a non-windowed backend supplies none; both are contract-
                # conformant, so the stable identity is what is asserted, not the value.
                handle = self.Window.Handle
                testcase.assertIsInstance(handle, int)
                testcase.assertGreaterEqual(handle, 0)
                testcase.assertEqual(handle, self.Window.Handle)

                current_information = self.manager.FindBestDevice(True)
                testcase.assertTrue(self.manager.CanResetDevice(current_information))
                alternate_information = current_information.Clone()
                alternate_information.GraphicsProfile = (
                    GraphicsProfile.HiDef if current_information.GraphicsProfile == GraphicsProfile.Reach
                    else GraphicsProfile.Reach)
                testcase.assertFalse(self.manager.CanResetDevice(alternate_information))
                ranked = [alternate_information, current_information]
                self.manager.RankDevices(ranked)
                testcase.assertIs(ranked[0], current_information)

                reset_events = []
                device.DeviceResetting += lambda sender, args: reset_events.append("resetting")
                device.DeviceReset += lambda sender, args: reset_events.append("reset")
                device.Reset()
                testcase.assertEqual(reset_events, ["resetting", "reset"])
                testcase.assertIs(device.SamplerStates, device.SamplerStates)
                testcase.assertIs(device.Textures, device.Textures)
                testcase.assertEqual(device.SamplerStates.Count, 16)
                testcase.assertEqual(device.VertexSamplerStates.Count,
                                     0 if device.GraphicsProfile == GraphicsProfile.Reach else 4)

                state = BlendState(); state.ColorSourceBlend = Blend.SourceAlpha
                device.BlendState = state
                testcase.assertIs(device.BlendState, state)
                with testcase.assertRaises(RuntimeError): state.ColorSourceBlend = Blend.One

                vertices = [
                    VertexPositionColor(Vector3(0, 0, 0), Color.Red),
                    VertexPositionColor(Vector3(1, 0, 0), Color.Green),
                    VertexPositionColor(Vector3(0, 1, 0), Color.Blue),
                ]
                self.vertex_buffer = VertexBuffer(device, VertexPositionColor, 3,
                                                  BufferUsage.None_)
                self.vertex_buffer.SetData(vertices)
                read_vertices = [None, None, None]
                self.vertex_buffer.GetData(read_vertices)
                testcase.assertEqual(read_vertices, vertices)
                device.SetVertexBuffer(self.vertex_buffer)
                testcase.assertIs(device.GetVertexBuffers()[0].VertexBuffer,
                                  self.vertex_buffer)

                self.dynamic_vertex_buffer = DynamicVertexBuffer(
                    device, VertexPositionColor, 3, BufferUsage.WriteOnly)
                self.dynamic_vertex_buffer.SetData(
                    vertices, 0, 3, SetDataOptions.Discard)
                testcase.assertFalse(self.dynamic_vertex_buffer.IsContentLost)

                self.index_buffer = IndexBuffer(device, IndexElementSize.SixteenBits,
                                                3, BufferUsage.None_)
                self.index_buffer.SetData([0, 1, 2])
                indices = [0, 0, 0]; self.index_buffer.GetData(indices)
                testcase.assertEqual(indices, [0, 1, 2])
                device.Indices = self.index_buffer
                testcase.assertIs(device.Indices, self.index_buffer)
                try:
                    device.DrawIndexedPrimitives(PrimitiveType.TriangleList,
                                                 0, 0, 3, 0, 1)
                except NativeError as error:
                    testcase.assertEqual(error.result, 12)  # HEADLESS has no visible 3D route.

                self.target = RenderTarget2D(device, 8, 8)
                testcase.assertEqual((self.target.Width, self.target.Height,
                                      self.target.Format), (8, 8, SurfaceFormat.Color))
                device.SetRenderTarget(self.target)
                testcase.assertIs(device.GetRenderTargets()[0].RenderTarget, self.target)
                with testcase.assertRaises(NativeError): self.target.Dispose()
                device.SetRenderTarget(None)

                self.texture = Texture2D(device, 1, 1)
                self.texture.SetData([Color.White])
                png, jpeg = io.BytesIO(), io.BytesIO()
                self.texture.SaveAsPng(png, 1, 1); self.texture.SaveAsJpeg(jpeg, 1, 1)
                testcase.assertTrue(png.getvalue().startswith(b"\x89PNG"))
                testcase.assertTrue(jpeg.getvalue().startswith(b"\xff\xd8"))

                disposing = []
                probe = Texture2D(device, 1, 1)
                def on_disposing(sender, args):
                    disposing.append(sender)
                    sender.Disposing -= on_disposing
                probe.Disposing += on_disposing
                probe.Dispose(); probe.Dispose()
                testcase.assertEqual(disposing, [probe])

                failing = Texture2D(device, 1, 1)
                failing.Disposing += lambda sender, args: (_ for _ in ()).throw(
                    RuntimeError("disposing handler"))
                with testcase.assertRaisesRegex(RuntimeError, "disposing handler"):
                    failing.Dispose()
                testcase.assertTrue(failing.IsDisposed)
                failing.Dispose()

                bound_texture = Texture2D(device, 1, 1)
                device.Textures[0] = bound_texture
                bound_texture.Dispose()
                testcase.assertTrue(bound_texture.IsDisposed)
                testcase.assertIsNone(device.Textures[0])

                self.font = SpriteFont._create(
                    self.texture, [Rectangle(0, 0, 1, 1)],
                    [Rectangle(0, 0, 1, 1)], ["A"], 8, 0.0,
                    [Vector3(0, 1, 0)], "A")
                testcase.assertEqual(self.font.Characters, ("A",))
                testcase.assertEqual(self.font.MeasureString("AA\nA"), Vector2(2, 16))
                self.batch = SpriteBatch(device); self.batch.Begin()
                self.batch.DrawString(self.font, "AA", Vector2.Zero, Color.White)
                self.batch.End(); self.completed = True

            def Update(self, gameTime): self.Exit()

        game = FoundationGame()
        try:
            game.Run()
            self.assertTrue(game.completed)
        finally:
            # The shutdown path must release persistent bindings before owned
            # children, and a failed Run must not strand the one C-owned game.
            game.Dispose()


if __name__ == "__main__":
    unittest.main()
