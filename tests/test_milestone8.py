from __future__ import annotations

import copy
from datetime import timedelta
import os
from pathlib import Path
import unittest

from Microsoft.Xna.Framework import (
    DisplayOrientation, FrameworkDispatcher, Game, GameTime, GraphicsDeviceManager,
    Vector2,
)
from Microsoft.Xna.Framework.GamerServices import GamerServicesComponent
from Microsoft.Xna.Framework.Graphics import (
    CubeMapFace, DepthFormat, OcclusionQuery, RenderTargetBinding,
    RenderTargetCube, RenderTargetUsage, SurfaceFormat, TextureCube,
)
from Microsoft.Xna.Framework.Input.Touch import (
    GestureSample, GestureType, TouchCollection, TouchLocation,
    TouchLocationState, TouchPanel,
)
from Microsoft.Xna.Framework.Storage import (
    StorageDevice, StorageDeviceNotConnectedException,
)
from _cna_native.errors import NativeError
from _cna_native.errors import NativeCapabilityError


NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")


class Milestone8ManagedTests(unittest.TestCase):
    def test_dispatcher_without_a_live_game_is_an_explicit_cna_limitation(self):
        with self.assertRaises(NativeCapabilityError):
            FrameworkDispatcher.Update()

    def test_touch_values_preserve_xna_equality_and_copy_boundaries(self):
        previous = Vector2(2.5, -3.0)
        first = TouchLocation(
            7, TouchLocationState.Moved, Vector2(8, 9),
            TouchLocationState.Pressed, previous,
        )
        different_state = TouchLocation(
            7, TouchLocationState.Released, Vector2(8, 9),
            TouchLocationState.Moved, previous,
        )
        self.assertTrue(first.Equals(different_state))
        self.assertNotEqual(first, different_state)
        found_previous, prior = first.TryGetPreviousLocation()
        self.assertTrue(found_previous)
        self.assertEqual((prior.Id, prior.State, prior.Position),
                         (7, TouchLocationState.Pressed, previous))
        missing, sentinel = TouchLocation(4, TouchLocationState.Pressed,
                                          Vector2.One).TryGetPreviousLocation()
        self.assertFalse(missing)
        self.assertEqual((sentinel.Id, sentinel.State),
                         (-1, TouchLocationState.Invalid))

        collection = TouchCollection([first, different_state])
        self.assertTrue(collection.IsConnected)
        self.assertTrue(collection.IsReadOnly)
        self.assertEqual(collection.FindById(7), (True, first))
        destination = [TouchLocation(), TouchLocation(), TouchLocation()]
        collection.CopyTo(destination, 1)
        self.assertEqual(destination[1:], [first, different_state])
        with self.assertRaises(TypeError):
            collection.Add(first)
        extracted = collection[0]
        self.assertIsNot(extracted, first)

    def test_touch_enumerator_has_clr_current_boundaries_and_python_iteration(self):
        values = [TouchLocation(1, TouchLocationState.Pressed, Vector2(1, 2)),
                  TouchLocation(2, TouchLocationState.Moved, Vector2(3, 4))]
        enumerator = TouchCollection(values).GetEnumerator()
        with self.assertRaises(IndexError):
            _ = enumerator.Current
        self.assertTrue(enumerator.MoveNext())
        self.assertEqual(enumerator.Current, values[0])
        copied = copy.copy(enumerator)
        self.assertTrue(copied.MoveNext())
        self.assertEqual(copied.Current, values[1])
        self.assertTrue(enumerator.MoveNext())
        self.assertFalse(enumerator.MoveNext())
        with self.assertRaises(IndexError):
            _ = enumerator.Current
        enumerator.Dispose()
        self.assertEqual(list(TouchCollection(values)), values)

    def test_gesture_bits_sample_and_storage_exception_mapping(self):
        self.assertEqual(int(GestureType.Tap | GestureType.PinchComplete), 513)
        sample = GestureSample(
            GestureType.FreeDrag, timedelta(microseconds=123), Vector2(1, 2),
            Vector2(3, 4), Vector2(5, 6), Vector2(7, 8),
        )
        self.assertEqual((sample.GestureType, sample.Timestamp, sample.Delta2),
                         (GestureType.FreeDrag, timedelta(microseconds=123), Vector2(7, 8)))
        inner = OSError("inner")
        error = StorageDeviceNotConnectedException("offline", inner)
        self.assertIs(error.__cause__, inner)
        self.assertEqual(str(error), "offline")


@unittest.skipUnless(NATIVE and Path(NATIVE).is_file(),
                     "CNA_NATIVE_LIBRARY is not configured")
class Milestone8NativeTests(unittest.TestCase):
    def test_dispatcher_touch_gamer_graphics_and_storage_routes(self):
        testcase = self
        storage_name = "cna-python-milestone8"

        class MilestoneGame(Game):
            def __init__(self):
                super().__init__()
                self.manager = GraphicsDeviceManager(self)
                self.gamer = GamerServicesComponent(self)
                self.Components.Add(self.gamer)
                self.completed = False

            def LoadContent(self):
                FrameworkDispatcher.Update()

                capabilities = TouchPanel.GetCapabilities()
                testcase.assertGreaterEqual(capabilities.MaximumTouchCount, 0)
                state = TouchPanel.GetState()
                testcase.assertEqual(state.Count, len(state))
                TouchPanel.EnabledGestures = GestureType.Tap | GestureType.Hold
                testcase.assertEqual(TouchPanel.EnabledGestures,
                                     GestureType.Tap | GestureType.Hold)
                testcase.assertFalse(TouchPanel.IsGestureAvailable)
                with testcase.assertRaises(NativeError):
                    TouchPanel.ReadGesture()
                TouchPanel.WindowHandle = self.Window.Handle
                TouchPanel.DisplayOrientation = DisplayOrientation.LandscapeLeft
                TouchPanel.DisplayWidth = 640
                TouchPanel.DisplayHeight = 360
                testcase.assertEqual(
                    (TouchPanel.WindowHandle, TouchPanel.DisplayOrientation,
                     TouchPanel.DisplayWidth, TouchPanel.DisplayHeight),
                    (self.Window.Handle, DisplayOrientation.LandscapeLeft, 640, 360),
                )

                device = self.GraphicsDevice
                cube = RenderTargetCube(
                    device, 8, False, SurfaceFormat.Color, DepthFormat.Depth24,
                    0, RenderTargetUsage.PreserveContents,
                )
                testcase.assertIsInstance(cube, TextureCube)
                testcase.assertEqual(
                    (cube.Size, cube.Format, cube.DepthStencilFormat,
                     cube.MultiSampleCount, cube.RenderTargetUsage),
                    (8, SurfaceFormat.Color, DepthFormat.Depth24,
                     0, RenderTargetUsage.PreserveContents),
                )
                for face in CubeMapFace:
                    device.SetRenderTarget(cube, face)
                    binding = device.GetRenderTargets()[0]
                    testcase.assertIs(binding.RenderTarget, cube)
                    testcase.assertEqual(binding.CubeMapFace, face)
                    testcase.assertEqual(copy.copy(RenderTargetBinding(cube, face)).CubeMapFace,
                                         face)
                with testcase.assertRaises(NativeError):
                    cube.Dispose()
                testcase.assertFalse(cube.IsDisposed)
                device.SetRenderTarget(None)
                cube.Dispose(); cube.Dispose()
                testcase.assertTrue(cube.IsDisposed)

                query = OcclusionQuery(device)
                testcase.assertFalse(query.IsComplete)
                with testcase.assertRaises(RuntimeError):
                    _ = query.PixelCount
                with testcase.assertRaises(RuntimeError):
                    query.End()
                query.Begin()
                with testcase.assertRaises(RuntimeError):
                    query.Begin()
                testcase.assertFalse(query.IsComplete)
                query.End()
                testcase.assertTrue(query.IsComplete)
                testcase.assertGreaterEqual(query.PixelCount, 0)
                query.Begin(); query.End()
                testcase.assertTrue(query.IsComplete)
                query.Dispose(); query.Dispose()
                with testcase.assertRaises(RuntimeError):
                    _ = query.IsComplete

                callbacks = []
                selector = StorageDevice.BeginShowSelector(
                    lambda result: callbacks.append(result), {"state": 8})
                testcase.assertEqual(callbacks, [selector])
                testcase.assertEqual(selector.AsyncState["state"], 8)
                storage = StorageDevice.EndShowSelector(selector)
                with testcase.assertRaises(ValueError):
                    StorageDevice.EndShowSelector(selector)
                testcase.assertTrue(storage.IsConnected)
                testcase.assertGreaterEqual(storage.TotalSpace, storage.FreeSpace)

                opened = []
                pending = storage.BeginOpenContainer(
                    storage_name, lambda result: opened.append(result), "container-state")
                testcase.assertEqual(opened, [pending])
                testcase.assertEqual(pending.AsyncState, "container-state")
                container = storage.EndOpenContainer(pending)
                testcase.assertEqual(container.DisplayName, storage_name)
                testcase.assertIs(container.StorageDevice, storage)
                for escaping in ("../escape", "..\\escape", "/absolute", "C:\\escape", "\0"):
                    with testcase.assertRaises(ValueError):
                        container.FileExists(escaping)
                container.CreateDirectory("nested")
                with container.CreateFile("value.bin") as stream:
                    testcase.assertEqual(stream.write(b"milestone-eight"), 15)
                    stream.flush()
                with container.OpenFile(
                        "value.bin", "open", "read", frozenset({"read"})) as stream:
                    testcase.assertTrue(stream.readable())
                    testcase.assertEqual(stream.read(), b"milestone-eight")
                testcase.assertIn("value.bin", container.GetFileNames("*.bin"))
                disposing = []
                container.Disposing += lambda sender, args: disposing.append(sender)
                container.Dispose(); container.Dispose()
                testcase.assertEqual(disposing, [container])
                testcase.assertTrue(container.IsDisposed)
                storage.DeleteContainer(storage_name)
                self.completed = True

            def Update(self, gameTime: GameTime):
                self.Exit()

        game = MilestoneGame()
        game.Run()
        self.assertTrue(game.completed)
        self.assertTrue(game.gamer._initialized)
        game.Dispose()


if __name__ == "__main__":
    unittest.main()
