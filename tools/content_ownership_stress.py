#!/usr/bin/env python3
"""Dedicated Content/XNB ownership and cache stress against the qualified CNA library."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from Microsoft.Xna.Framework import Game, GraphicsDeviceManager  # noqa: E402
from Microsoft.Xna.Framework.Content import ResourceContentManager  # noqa: E402
from Microsoft.Xna.Framework.Content._content import _register_content_type_reader  # noqa: E402
from tests.test_content import (  # noqa: E402
    _ExternalReader, _PayloadReader, _seven, _text, _xnb,
)
from tests.test_content_native import (  # noqa: E402
    PREFIX, _compressed_xnb, _spritefont_xnb,
    _index_xnb, _texture_xnb, _vertex_xnb,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=20)
    args = parser.parse_args()
    if args.cycles < 20:
        parser.error("--cycles must be at least 20")

    custom_identity = "CnaPython.Stress.PayloadReader"
    external_identity = "CnaPython.Stress.ExternalReader"
    unregister_custom = _register_content_type_reader(custom_identity, _PayloadReader)
    unregister_external = _register_content_type_reader(external_identity, _ExternalReader)
    string_reader = PREFIX + "StringReader"
    shared = _xnb(
        [(custom_identity, 0), (string_reader, 0)],
        _seven(1) + _text("root") + _seven(1) + _seven(2) + _text("shared"),
        1,
    )
    external_parent = _xnb([(external_identity, 0)], _seven(1) + _text("target"))
    external_target = _xnb([(string_reader, 0)], _seven(1) + _text("external"))
    texture = _texture_xnb()
    font = _spritefont_xnb()
    assets = {
        "texture": texture,
        "font": font,
        "vertices": _vertex_xnb(),
        "indices": _index_xnb(),
        "custom": shared,
        "external/u_to_c/root": external_parent,
        "external/u_to_c/target": _compressed_xnb(external_target),
        "external/c_to_u/root": _compressed_xnb(external_parent),
        "external/c_to_u/target": external_target,
        "external/c_to_c/root": _compressed_xnb(external_parent),
        "external/c_to_c/target": _compressed_xnb(external_target),
        "compressed/texture": _compressed_xnb(texture),
        "compressed/font": _compressed_xnb(font),
    }

    class StressGame(Game):
        def __init__(self):
            super().__init__()
            self.graphics = GraphicsDeviceManager(self)
            previous = self.Content
            self.Content = ResourceContentManager(self.Services, assets)
            previous.Dispose()
            self.last_live = ()

        def LoadContent(self):
            for cycle in range(args.cycles):
                loaded_texture = self.Content.Load("texture")
                loaded_font = self.Content.Load("font")
                vertices = self.Content.Load("vertices")
                indices = self.Content.Load("indices")
                custom = self.Content.Load("custom")
                external_uc = self.Content.Load("external/u_to_c/root")
                external_cu = self.Content.Load("external/c_to_u/root")
                external_cc = self.Content.Load("external/c_to_c/root")
                compressed_texture = self.Content.Load("compressed/texture")
                compressed_font = self.Content.Load("compressed/font")
                assert self.Content.Load("TEXTURE") is loaded_texture
                assert custom.shared == "shared"
                assert external_uc.shared == external_cu.shared == external_cc.shared == "external"
                assert loaded_texture.Width == compressed_texture.Width == 2
                assert loaded_font.Characters == compressed_font.Characters == ("A",)
                assert vertices.VertexCount == 1 and indices.IndexCount == 3
                live = (
                    loaded_texture, loaded_font, vertices, indices,
                    compressed_texture, compressed_font,
                )
                if cycle + 1 < args.cycles:
                    self.Content.Unload()
                    assert all(
                        resource._native.IsDisposed if hasattr(resource, "_native")
                        else resource.IsDisposed
                        for resource in live
                    )
                else:
                    self.last_live = live

        def Draw(self, gameTime):
            self.Exit()

    try:
        game = StressGame()
        game.Run()
        final_live = game.last_live
        game.Dispose()
        assert all(
            resource._native.IsDisposed if hasattr(resource, "_native")
            else resource.IsDisposed
            for resource in final_live
        )
    finally:
        unregister_external()
        unregister_custom()

    print(f"CONTENT_MANAGER_CYCLES={args.cycles}")
    print(f"TEXTURE_XNB_CYCLES={args.cycles}")
    print(f"SPRITEFONT_XNB_CYCLES={args.cycles}")
    print(f"CUSTOM_READER_CYCLES={args.cycles}")
    print(f"SHARED_RESOURCE_CYCLES={args.cycles}")
    print(f"EXTERNAL_REFERENCE_CYCLES={args.cycles}")
    print(f"COMPRESSED_XNB_CYCLES={args.cycles}")
    print("CRASHES=0")
    print("OBSERVED_UAF_OR_DOUBLE_FREE=0")
    print("SANITIZER_STATUS=NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
