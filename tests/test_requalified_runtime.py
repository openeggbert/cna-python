"""Runtime behaviour requalified against the current CNA generation.

Every case here was previously blocked, previously untested, or previously
crashed.  Each asserts against an independent expectation rather than reading a
value back through the setter that wrote it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, Vector3
from Microsoft.Xna.Framework.Graphics import (
    AlphaTestEffect, BasicEffect, BufferUsage, DualTextureEffect, DynamicIndexBuffer,
    DynamicVertexBuffer, EnvironmentMapEffect, IndexBuffer, IndexElementSize,
    OcclusionQuery, RenderTarget2D, RenderTargetCube, SetDataOptions, SkinnedEffect,
    SpriteBatch,
    GraphicsDevice, GraphicsProfile, PresentationParameters,
    SurfaceFormat, Texture2D, TextureCube, VertexBuffer, VertexPositionColor,
)
from _cna_native.errors import NativeCapabilityError, NativeUnavailableError
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


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _generate_clip(destination: Path) -> bool:
    """Writes a 320x180, 24 fps, exactly 1.5 s clip, or reports that it could not.

    The clip is generated at test time and never committed: the repository ships
    no encoded media, and CNA refuses to play a video whose declared metadata
    disagrees with the file, so the fixture must match the asset exactly.
    """
    tool = _ffmpeg()
    if tool is None:
        return False
    for codec in ("mpeg4", "libx264", "libvpx"):
        command = [tool, "-y", "-loglevel", "error", "-f", "lavfi",
                   "-i", "color=c=red:s=320x180:r=24", "-frames:v", "36",
                   "-c:v", codec, "-pix_fmt", "yuv420p", str(destination)]
        try:
            if subprocess.run(command, capture_output=True).returncode == 0 and destination.exists():
                return True
        except OSError:
            return False
    return False


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
@unittest.skipUnless(_ffmpeg(), "ffmpeg is not available to generate a legal video fixture")
class VideoDecodeTests(unittest.TestCase):
    """Real decode through the ordinary XNA content path.

    CNA opens the video file itself and resolves a relative path against the
    process working directory rather than the title location, so a title-relative
    reference decoded nowhere except when the two happened to coincide, and the
    player silently stayed stopped.  The reference is now resolved against the
    title before CNA sees it.
    """

    def test_content_video_decodes_and_lends_a_frame_texture(self) -> None:
        from tests.test_media import _video_xnb
        from Microsoft.Xna.Framework._title import _set_title_root_for_tests
        from Microsoft.Xna.Framework.Media import MediaState, VideoPlayer

        case = self
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Content").mkdir()
            if not _generate_clip(root / "Content" / "authored-video.ogv"):
                self.skipTest("no usable video encoder produced the fixture")
            (root / "Content" / "clip.xnb").write_bytes(_video_xnb())
            _set_title_root_for_tests(root)
            observed: dict[str, object] = {}

            class Probe(Game):
                def __init__(self) -> None:
                    super().__init__()
                    self.manager = GraphicsDeviceManager(self)
                    self.Content.RootDirectory = "Content"
                    self.frames = 0
                    self.player = None
                    self.previous = None

                def LoadContent(self) -> None:
                    self.video = self.Content.Load("clip")
                    self.player = VideoPlayer()
                    # Before Play there is no current Video to read a frame from.
                    with case.assertRaises(RuntimeError):
                        self.player.GetTexture()
                    self.player.Play(self.video)

                def Update(self, gameTime) -> None:
                    self.frames += 1
                    observed.setdefault("state", self.player.State)
                    texture = self.player.GetTexture()
                    if texture is not None:
                        observed["size"] = (texture.Width, texture.Height)
                        if self.previous is not None and self.previous is not texture:
                            # The runtime decodes into a single texture and replaces it on
                            # the next call, so the earlier borrow must refuse rather than
                            # read freed memory.
                            with case.assertRaises(RuntimeError):
                                _ = self.previous.Format
                            observed["expired"] = True
                        self.previous = texture
                    if self.frames >= 4:
                        self.player.Dispose()
                        self.Exit()

                def Draw(self, gameTime) -> None:
                    self.GraphicsDevice.Clear(Color.Black)

            game = Probe()
            try:
                game.Run()
            finally:
                game.Dispose()
                _set_title_root_for_tests(None)

        self.assertEqual(observed.get("state"), MediaState.Playing)
        self.assertEqual(observed.get("size"), (320, 180))
        self.assertTrue(observed.get("expired"), "an expired frame borrow was not refused")


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
class RenderTargetContentLostTests(unittest.TestCase):
    """ContentLost is a real native subscription rather than an inert event.

    CNA raises it only when a renderer reports that it lost and recreated its
    device. The renderer families that can do that are not the ones available
    here, so this asserts the subscription contract and asserts that nothing is
    delivered rather than pretending a loss occurred.
    """

    def test_subscription_is_native_and_released_before_the_handle(self) -> None:
        case = self
        raised: list[object] = []

        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)

            def Update(self, gameTime) -> None:
                device = self.GraphicsDevice
                target = RenderTarget2D(device, 8, 8)
                target.ContentLost += lambda sender, args: raised.append(sender)
                case.assertNotEqual(target._content_lost_registration, 0,
                                    "no native ContentLost registration was created")
                case.assertFalse(target.IsContentLost)
                target.Dispose()
                case.assertEqual(target._content_lost_registration, 0,
                                 "the registration outlived the render target")
                # A dropped, never-disposed target must release its registration
                # through the owning generation rather than strand it.
                RenderTarget2D(device, 8, 8).ContentLost += lambda sender, args: raised.append(sender)
                self.Exit()

            def Draw(self, gameTime) -> None:
                self.GraphicsDevice.Clear(Color.Black)

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()
        self.assertEqual(raised, [], "a ContentLost event was delivered without a device loss")


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
class OwnedGraphicsDeviceTests(unittest.TestCase):
    """XNA's public GraphicsDevice constructor and Dispose now reach a real device.

    Every other route hands out the Game's device, borrowed for the duration of a
    callback and released with its Game. The current generation can also create an
    independent device the caller owns, so the constructor is a real device rather
    than a refusal, and Dispose destroys the one kind it may.
    """

    def test_owned_device_is_independent_and_disposable(self) -> None:
        case = self
        observed: dict[str, object] = {}

        class Probe(Game):
            def __init__(self) -> None:
                super().__init__()
                self.manager = GraphicsDeviceManager(self)

            def Update(self, gameTime) -> None:
                borrowed = self.GraphicsDevice
                parameters = PresentationParameters()
                parameters.BackBufferWidth = 64
                parameters.BackBufferHeight = 64
                parameters.IsFullScreen = False
                owned = GraphicsDevice(borrowed.Adapter, GraphicsProfile.Reach, parameters)
                case.assertIsNot(owned, borrowed)

                # A resource belongs to the device that made it, not to the game.
                texture = Texture2D(owned, 4, 4)
                case.assertEqual((texture.Width, texture.Height), (4, 4))
                texture.Dispose()

                owned.Dispose()
                owned.Dispose()  # idempotent
                with case.assertRaises(RuntimeError):
                    _ = owned.Viewport
                observed["owned"] = True

                # The Game's device is borrowed and stays the Game's to release.
                with case.assertRaises(NativeCapabilityError):
                    borrowed.Dispose()
                observed["borrowed_refused"] = True
                self.Exit()

            def Draw(self, gameTime) -> None:
                self.GraphicsDevice.Clear(Color.Black)

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()
        self.assertTrue(observed.get("owned"))
        self.assertTrue(observed.get("borrowed_refused"))

    def test_constructor_still_validates_its_arguments(self) -> None:
        with self.assertRaises(TypeError):
            GraphicsDevice(None, GraphicsProfile.Reach, PresentationParameters())
        with self.assertRaises(TypeError):
            GraphicsDevice(object(), GraphicsProfile.Reach, None)
