"""Microsoft.Xna.Framework.Content.Pipeline.Audio strict namespace."""

from ._audio import AudioContent, AudioFormat
from ._enums import AudioFileType, ConversionFormat, ConversionQuality

__all__ = [
    "AudioContent", "AudioFileType", "AudioFormat", "ConversionFormat",
    "ConversionQuality",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
