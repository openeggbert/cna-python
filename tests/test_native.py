from __future__ import annotations

from pathlib import Path
import os
import unittest

from _cna_native.errors import NativeError
from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, PlayerIndex, Vector2
from Microsoft.Xna.Framework.Graphics import SpriteBatch, SpriteEffects, Texture2D
from Microsoft.Xna.Framework.Input import GamePad, GamePadCapabilities, Keyboard, Mouse, MouseState


NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
LOGO = Path(__file__).parent / "fixtures/logo.png"


@unittest.skipUnless(NATIVE and Path(NATIVE).is_file(), "CNA_NATIVE_LIBRARY is not configured")
class NativeSliceTests(unittest.TestCase):
    def test_all_non_touch_input_routes_execute_against_cna(self) -> None:
        class InputProbe(Game):
            def __init__(self):
                super().__init__(); self.manager = GraphicsDeviceManager(self)
            def Update(self, gameTime):
                self.keyboard = Keyboard.GetState()
                self.player_keyboard = Keyboard.GetState(PlayerIndex.One)
                self.mouse = Mouse.GetState()
                handle = Mouse.WindowHandle
                Mouse.WindowHandle = handle
                Mouse.SetPosition(self.mouse.X, self.mouse.Y)
                self.gamepad = GamePad.GetState(PlayerIndex.One)
                self.capabilities = GamePad.GetCapabilities(PlayerIndex.One)
                self.vibration_applied = GamePad.SetVibration(PlayerIndex.One, 0.0, 0.0)
                self.Exit()
        game = InputProbe()
        game.Run(); game.Dispose()
        self.assertIsInstance(game.mouse, MouseState)
        self.assertIsInstance(game.capabilities, GamePadCapabilities)
        self.assertIsInstance(game.vibration_applied, bool)

    def test_60_frame_lifecycle_graphics_png_sprite_and_input(self) -> None:
        class Probe(Game):
            def __init__(self):
                super().__init__()
                self.manager = GraphicsDeviceManager(self)
                self.events, self.frames = [], 0
                self.Exiting += self._record_exiting
            def _record_exiting(self, sender, args): self.events.append("Exiting")
            def Initialize(self): self.events.append("Initialize")
            def LoadContent(self):
                self.events.append("LoadContent")
                with LOGO.open("rb") as stream:
                    self.logo = Texture2D.FromStream(self.GraphicsDevice, stream)
                self.batch = SpriteBatch(self.GraphicsDevice)
            def BeginRun(self): self.events.append("BeginRun")
            def Update(self, gameTime):
                Keyboard.GetState(); Mouse.GetState(); GamePad.GetState(PlayerIndex.One)
            def Draw(self, gameTime):
                self.GraphicsDevice.Clear(Color.CornflowerBlue)
                if self.frames == 0:
                    viewport = self.GraphicsDevice.Viewport
                    self.title_safe_area = viewport.TitleSafeArea
                    self.GraphicsDevice.Viewport = viewport
                self.batch.Begin()
                self.batch.Draw(self.logo, Vector2(100, 100), None, Color.White,
                                0.1, Vector2(64, 64), 1.1, SpriteEffects.None_, 0.0)
                self.batch.End()
                self.frames += 1
                if self.frames == 60: self.Exit()
            def EndRun(self): self.events.append("EndRun")
            def UnloadContent(self):
                self.events.append("UnloadContent")
                self.batch.Dispose(); self.logo.Dispose()
        game = Probe()
        game.Run()
        self.assertEqual(game.frames, 60)
        self.assertEqual((game.logo.Width, game.logo.Height), (128, 128))
        self.assertGreaterEqual(game.title_safe_area.Width, 0)
        self.assertGreaterEqual(game.title_safe_area.Height, 0)
        game.Dispose()
        game.Dispose()
        self.assertEqual(game.events, ["Initialize", "LoadContent", "BeginRun", "Exiting", "EndRun", "UnloadContent"])

    def test_callback_exception_is_rethrown_at_run_boundary(self) -> None:
        class Throwing(Game):
            def __init__(self): super().__init__(); self.manager = GraphicsDeviceManager(self)
            def Update(self, gameTime): raise LookupError("update sentinel")
        game = Throwing()
        try:
            with self.assertRaisesRegex(LookupError, "update sentinel"):
                game.Run()
        finally:
            game.Dispose()

    def test_callback_exception_phases_remain_python_exceptions(self) -> None:
        for phase in ("Initialize", "LoadContent", "Update", "Draw"):
            with self.subTest(phase=phase):
                class Throwing(Game):
                    def __init__(self):
                        super().__init__(); self.manager = GraphicsDeviceManager(self)
                    def _throw(self): raise LookupError(f"{phase} sentinel")
                    def Initialize(self):
                        if phase == "Initialize": self._throw()
                    def LoadContent(self):
                        if phase == "LoadContent": self._throw()
                    def Update(self, gameTime):
                        if phase == "Update": self._throw()
                    def Draw(self, gameTime):
                        if phase == "Draw": self._throw()
                game = Throwing()
                with self.assertRaisesRegex(LookupError, f"{phase} sentinel"):
                    game.Run()
                game.Dispose()

    def test_unload_exception_is_rethrown_from_dispose(self) -> None:
        class Throwing(Game):
            def __init__(self): super().__init__(); self.manager = GraphicsDeviceManager(self)
            def Draw(self, gameTime): self.Exit()
            def UnloadContent(self): raise LookupError("UnloadContent sentinel")
        game = Throwing()
        game.Run()
        with self.assertRaisesRegex(LookupError, "UnloadContent sentinel"):
            game.Dispose()

    def test_dispose_before_run_and_context_manager(self) -> None:
        game = Game()
        GraphicsDeviceManager(game)
        with game:
            pass
        game.Dispose()
        with self.assertRaisesRegex(RuntimeError, "disposed"):
            game.Run()

    def test_invalid_encoded_image_copies_native_failure(self) -> None:
        class InvalidImage(Game):
            def __init__(self): super().__init__(); self.manager = GraphicsDeviceManager(self)
            def LoadContent(self):
                import io
                Texture2D.FromStream(self.GraphicsDevice, io.BytesIO(b"not an image"))
        game = InvalidImage()
        try:
            with self.assertRaises(NativeError) as caught:
                game.Run()
            self.assertIn("cna_texture2d_create_from_encoded_memory", caught.exception.operation)
            self.assertTrue(str(caught.exception))
        finally:
            game.Dispose()

    def test_live_resources_are_disposed_before_parent(self) -> None:
        class LiveChildren(Game):
            def __init__(self): super().__init__(); self.manager = GraphicsDeviceManager(self)
            def LoadContent(self):
                self.texture = Texture2D(self.GraphicsDevice, 1, 1)
                self.batch = SpriteBatch(self.GraphicsDevice)
            def Draw(self, gameTime): self.Exit()
        game = LiveChildren()
        game.Run()
        game.Dispose()
        self.assertTrue(game.texture.IsDisposed)
        self.assertTrue(game.batch.IsDisposed)

    def test_texture_color_roundtrip_and_context_disposal(self) -> None:
        class Transfer(Game):
            def __init__(self): super().__init__(); self.manager = GraphicsDeviceManager(self); self.done = False
            def LoadContent(self):
                with Texture2D(self.GraphicsDevice, 2, 2) as texture:
                    source = [Color.Red, Color.Green, Color.Blue, Color.White]
                    texture.SetData(source)
                    target = [Color.Black for _ in range(4)]
                    texture.GetData(target)
                    self.assertion = target == source
                self.disposed = texture.IsDisposed
            def Draw(self, gameTime): self.done = True; self.Exit()
        game = Transfer()
        game.Run(); game.Dispose()
        self.assertTrue(game.assertion)
        self.assertTrue(game.disposed)


if __name__ == "__main__":
    unittest.main()
