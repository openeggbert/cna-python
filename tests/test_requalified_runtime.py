"""Runtime behaviour requalified against the current CNA generation.

Every case here was previously blocked, previously untested, or previously
crashed.  Each asserts against an independent expectation rather than reading a
value back through the setter that wrote it.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, Vector3
from Microsoft.Xna.Framework.Graphics import (
    AlphaTestEffect, BasicEffect, BufferUsage, DualTextureEffect, DynamicIndexBuffer,
    DynamicVertexBuffer, EnvironmentMapEffect, IndexBuffer, IndexElementSize,
    OcclusionQuery, RenderTarget2D, SetDataOptions, SkinnedEffect, SpriteBatch,
    SurfaceFormat, Texture2D, TextureCube, VertexBuffer, VertexPositionColor,
)
from _cna_native.errors import NativeUnavailableError
from _cna_native.runtime_identity import runtime_identity


def _native_available() -> bool:
    try:
        runtime_identity()
    except NativeUnavailableError:
        return False
    except Exception:  # pragma: no cover - a configured library that fails to load
        return False
    return True


NATIVE = _native_available()


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
class DroppedWrapperOwnershipTests(unittest.TestCase):
    """A dropped Python wrapper must not strand or double-free its CNA handle.

    The owning generation retains the handle, but CNA keeps the disposing
    callback's trampoline pointer until the resource is destroyed and a facade
    may own further native views.  Rooting either of those only on the facade
    let the collector reclaim them first, which crashed the process during
    shutdown rather than leaking.
    """

    def _run_dropping(self, make) -> None:
        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)

            def Update(self, gameTime) -> None:
                make(self.GraphicsDevice)  # deliberately not retained and not disposed
                self.Exit()

            def Draw(self, gameTime) -> None:
                self.GraphicsDevice.Clear(Color.Black)

        game = Probe()
        game.Run()
        # Disposal must complete without a native refusal and without crashing the
        # process; reaching the assertion below is the observation.
        game.Dispose()
        self.assertTrue(True)

    #: Every owned graphics resource kind reachable without a fixture.  A dropped
    #: wrapper of any of them must be released by the owning generation.
    DROPPABLE = {
        "Texture2D": lambda device: Texture2D(device, 2, 2),
        "TextureCube": lambda device: TextureCube(device, 4, False, SurfaceFormat.Color),
        "SpriteBatch": lambda device: SpriteBatch(device),
        "BasicEffect": lambda device: BasicEffect(device),
        "AlphaTestEffect": lambda device: AlphaTestEffect(device),
        "DualTextureEffect": lambda device: DualTextureEffect(device),
        "EnvironmentMapEffect": lambda device: EnvironmentMapEffect(device),
        "SkinnedEffect": lambda device: SkinnedEffect(device),
        "VertexBuffer": lambda device: VertexBuffer(
            device, VertexPositionColor, 3, BufferUsage.None_),
        "DynamicVertexBuffer": lambda device: DynamicVertexBuffer(
            device, VertexPositionColor, 3, BufferUsage.None_),
        "IndexBuffer": lambda device: IndexBuffer(
            device, IndexElementSize.SixteenBits, 3, BufferUsage.None_),
        "DynamicIndexBuffer": lambda device: DynamicIndexBuffer(
            device, IndexElementSize.SixteenBits, 3, BufferUsage.None_),
        "RenderTarget2D": lambda device: RenderTarget2D(device, 4, 4),
        "OcclusionQuery": lambda device: OcclusionQuery(device),
    }

    def test_every_dropped_graphics_resource_is_released(self) -> None:
        for name, make in self.DROPPABLE.items():
            with self.subTest(resource=name):
                self._run_dropping(make)

    def test_retained_resources_still_dispose_cleanly(self) -> None:
        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)

            def Update(self, gameTime) -> None:
                self.texture = Texture2D(self.GraphicsDevice, 2, 2)
                self.effect = BasicEffect(self.GraphicsDevice)
                self.Exit()

            def Draw(self, gameTime) -> None:
                self.GraphicsDevice.Clear(Color.Black)

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()
        self.assertTrue(game.texture.IsDisposed)
        self.assertTrue(game.effect.IsDisposed)


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
class DynamicVertexStreamingTests(unittest.TestCase):
    """A destination offset and a streaming hint now reach CNA together.

    The historical generation had one route carrying the raw destination offset
    and another carrying the streaming option, and none carrying both, so the
    overload was refused.  The current generation has the combined route.
    """

    def test_offset_and_streaming_option_write_exactly_one_window(self) -> None:
        case = self

        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)

            def Update(self, gameTime) -> None:
                device = self.GraphicsDevice
                stride = VertexPositionColor.VertexDeclaration.VertexStride
                buffer = DynamicVertexBuffer(device, VertexPositionColor, 6, BufferUsage.None_)
                try:
                    def vertex(tag: int) -> VertexPositionColor:
                        return VertexPositionColor(Vector3(float(tag), 0.0, 0.0),
                                                   Color(tag, 0, 0, 255))

                    buffer.SetData([vertex(index) for index in range(6)], 0, 6,
                                   SetDataOptions.Discard)
                    read = [VertexPositionColor() for _ in range(6)]
                    buffer.GetData(read, 0, 6)
                    case.assertEqual([int(value.Color.R) for value in read], [0, 1, 2, 3, 4, 5])

                    # Three vertices written at buffer offset three, with a hint.
                    buffer.SetData(3 * stride, [vertex(90), vertex(91), vertex(92)], 0, 3,
                                   stride, SetDataOptions.NoOverwrite)
                    buffer.GetData(read, 0, 6)
                    case.assertEqual([int(value.Color.R) for value in read],
                                     [0, 1, 2, 90, 91, 92])
                finally:
                    buffer.Dispose()
                self.Exit()

            def Draw(self, gameTime) -> None:
                self.GraphicsDevice.Clear(Color.Black)

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
class RuntimeIdentityTests(unittest.TestCase):
    def test_identity_names_the_runtime_that_would_execute(self) -> None:
        identity = runtime_identity()
        self.assertTrue(identity.renderer_name)
        self.assertGreater(identity.abi_version, 0)
        self.assertIsInstance(identity.renders, bool)
        self.assertIn("CNA ABI", identity.describe())


if __name__ == "__main__":
    unittest.main()
