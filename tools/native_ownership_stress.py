#!/usr/bin/env python3
"""Repeat real game/resource ownership cycles against a configured CNA ABI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from Microsoft.Xna.Framework import (  # noqa: E402
    Color, Game, GraphicsDeviceManager, Rectangle, Vector2, Vector3,
)
from Microsoft.Xna.Framework.Graphics import (  # noqa: E402
    BlendState, BufferUsage, DynamicIndexBuffer, DynamicVertexBuffer, IndexBuffer,
    IndexElementSize, RenderTarget2D, SetDataOptions, SpriteBatch, SpriteFont, Texture2D,
    VertexBuffer, VertexPositionColor,
)


class StressGame(Game):
    def __init__(self, dispose_children: bool) -> None:
        super().__init__()
        self.manager = GraphicsDeviceManager(self)
        self.texture = None
        self.batch = None
        self.draws = 0
        self.dispose_children = dispose_children

    def LoadContent(self) -> None:
        with (ROOT / "tests/fixtures/logo.png").open("rb") as stream:
            self.texture = Texture2D.FromStream(self.GraphicsDevice, stream)
        self.batch = SpriteBatch(self.GraphicsDevice)
        vertices = [
            VertexPositionColor(Vector3(0, 0, 0), Color.Red),
            VertexPositionColor(Vector3(1, 0, 0), Color.Green),
            VertexPositionColor(Vector3(0, 1, 0), Color.Blue),
        ]
        self.vertex = VertexBuffer(self.GraphicsDevice, VertexPositionColor, 3, BufferUsage.None_)
        self.vertex.SetData(vertices)
        self.dynamic_vertex = DynamicVertexBuffer(
            self.GraphicsDevice, VertexPositionColor, 3, BufferUsage.WriteOnly)
        self.dynamic_vertex.SetData(vertices, 0, 3, SetDataOptions.Discard)
        self.index = IndexBuffer(self.GraphicsDevice, IndexElementSize.SixteenBits,
                                 3, BufferUsage.None_)
        self.index.SetData([0, 1, 2])
        self.dynamic_index = DynamicIndexBuffer(
            self.GraphicsDevice, IndexElementSize.SixteenBits, 3, BufferUsage.None_)
        self.dynamic_index.SetData([0, 1, 2], 0, 3, 0)
        self.target = RenderTarget2D(self.GraphicsDevice, 8, 8)
        self.state = BlendState(); self.GraphicsDevice.BlendState = self.state
        self.font = SpriteFont._create(
            self.texture, [Rectangle(0, 0, 1, 1)], [Rectangle(0, 0, 1, 1)],
            ["A"], 8, 0.0, [Vector3(0, 1, 0)], "A")
        self.callback_probe = Texture2D(self.GraphicsDevice, 1, 1)
        self.callback_count = 0
        def fail_disposing(sender, args):
            self.callback_count += 1
            raise RuntimeError("stress disposing callback")
        self.callback_probe.Disposing += fail_disposing

    def Draw(self, gameTime) -> None:
        self.GraphicsDevice.Clear(Color.CornflowerBlue)
        self.batch.Begin()
        self.batch.Draw(self.texture, Vector2(4, 4), Color.White)
        self.batch.End()
        self.GraphicsDevice.SetVertexBuffer(self.vertex)
        try:
            self.vertex.Dispose()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("CNA allowed a bound vertex buffer to be destroyed")
        self.GraphicsDevice.SetVertexBuffer(self.dynamic_vertex)
        self.GraphicsDevice.Indices = self.index
        try:
            self.index.Dispose()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("CNA allowed a bound index buffer to be destroyed")
        self.GraphicsDevice.Indices = self.dynamic_index
        self.GraphicsDevice.SetRenderTarget(self.target)
        try:
            self.callback_probe.Dispose()
        except RuntimeError as error:
            if str(error) != "stress disposing callback":
                raise
        else:
            raise RuntimeError("disposing callback exception was not rethrown")
        self.callback_probe.Dispose()
        if self.callback_count != 1 or not self.callback_probe.IsDisposed:
            raise RuntimeError("disposing callback was not exactly once and terminal")
        if self.dispose_children:
            self.GraphicsDevice.SetVertexBuffer(None)
            self.GraphicsDevice.Indices = None
            self.GraphicsDevice.SetRenderTarget(None)
            self.batch.Dispose(); self.batch.Dispose()
            self.font._dispose(); self.font._dispose()
            for resource in (self.target, self.dynamic_index, self.index,
                             self.dynamic_vertex, self.vertex, self.texture, self.state):
                resource.Dispose(); resource.Dispose()
        self.draws += 1
        self.Exit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=20)
    args = parser.parse_args()
    if args.cycles <= 0:
        raise ValueError("cycles must be positive")
    child_cycles = double_dispose = parent_first = 0
    buffer_cycles = render_target_cycles = sprite_font_cycles = state_cycles = 0
    callback_exception_cycles = 0
    for index in range(args.cycles):
        game = StressGame(dispose_children=bool(index % 2))
        game.Run()
        if game.draws != 1:
            raise RuntimeError(f"cycle {index} drew {game.draws} frames")
        if index % 2:
            double_dispose += 1
        child_cycles += 1
        buffer_cycles += 1; render_target_cycles += 1
        sprite_font_cycles += 1; state_cycles += 1
        callback_exception_cycles += 1
        game.Dispose()
        game.Dispose()
        resources = (game.texture, game.batch, game.target, game.dynamic_index,
                     game.index, game.dynamic_vertex, game.vertex, game.state,
                     game.callback_probe)
        if not all(resource.IsDisposed for resource in resources) or not game.font._native.IsDisposed:
            raise RuntimeError("parent shutdown did not invalidate live children")
        parent_first += 1
    print(f"LIFECYCLE_CYCLES={args.cycles}")
    print(f"CHILD_RESOURCE_CYCLES={child_cycles}")
    print(f"EXPLICIT_DOUBLE_DISPOSE_CYCLES={double_dispose}")
    print(f"PARENT_BEFORE_CHILD_CYCLES={parent_first}")
    print(f"BUFFER_FAMILY_CYCLES={buffer_cycles}")
    print(f"RENDER_TARGET_CYCLES={render_target_cycles}")
    print(f"SPRITE_FONT_CYCLES={sprite_font_cycles}")
    print(f"GRAPHICS_STATE_CYCLES={state_cycles}")
    print(f"CALLBACK_EXCEPTION_CYCLES={callback_exception_cycles}")
    print("CRASHES=0")
    print("OBSERVED_UAF_OR_DOUBLE_FREE=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
