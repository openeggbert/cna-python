"""The three processor enumerations."""

from __future__ import annotations

from enum import IntEnum


class EffectProcessorDebugMode(IntEnum):
    """How much debug information a compiled effect should carry."""

    Auto = 0
    Debug = 1
    Optimize = 2


class MaterialProcessorDefaultEffect(IntEnum):
    """Which stock effect a material with no effect of its own should use."""

    BasicEffect = 0
    SkinnedEffect = 1
    EnvironmentMapEffect = 2
    DualTextureEffect = 3
    AlphaTestEffect = 4


class TextureProcessorOutputFormat(IntEnum):
    """What pixel format a processed texture should end up in."""

    NoChange = 0
    Color = 1
    DxtCompressed = 2
