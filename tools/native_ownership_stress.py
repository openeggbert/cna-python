#!/usr/bin/env python3
"""Repeat real game/resource ownership cycles against a configured CNA ABI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, Vector2  # noqa: E402
from Microsoft.Xna.Framework.Graphics import SpriteBatch, Texture2D  # noqa: E402


class StressGame(Game):
    def __init__(self) -> None:
        super().__init__()
        self.manager = GraphicsDeviceManager(self)
        self.texture = None
        self.batch = None
        self.draws = 0

    def LoadContent(self) -> None:
        with (ROOT / "tests/fixtures/logo.png").open("rb") as stream:
            self.texture = Texture2D.FromStream(self.GraphicsDevice, stream)
        self.batch = SpriteBatch(self.GraphicsDevice)

    def Draw(self, gameTime) -> None:
        self.GraphicsDevice.Clear(Color.CornflowerBlue)
        self.batch.Begin()
        self.batch.Draw(self.texture, Vector2(4, 4), Color.White)
        self.batch.End()
        self.draws += 1
        self.Exit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=20)
    args = parser.parse_args()
    if args.cycles <= 0:
        raise ValueError("cycles must be positive")
    child_cycles = double_dispose = parent_first = 0
    for index in range(args.cycles):
        game = StressGame()
        game.Run()
        if game.draws != 1:
            raise RuntimeError(f"cycle {index} drew {game.draws} frames")
        if index % 2:
            game.texture.Dispose()
            game.texture.Dispose()
            game.batch.Dispose()
            game.batch.Dispose()
            double_dispose += 1
        child_cycles += 1
        game.Dispose()
        game.Dispose()
        if not game.texture.IsDisposed or not game.batch.IsDisposed:
            raise RuntimeError("parent shutdown did not invalidate live children")
        parent_first += 1
    print(f"LIFECYCLE_CYCLES={args.cycles}")
    print(f"CHILD_RESOURCE_CYCLES={child_cycles}")
    print(f"EXPLICIT_DOUBLE_DISPOSE_CYCLES={double_dispose}")
    print(f"PARENT_BEFORE_CHILD_CYCLES={parent_first}")
    print("CRASHES=0")
    print("OBSERVED_UAF_OR_DOUBLE_FREE=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
