"""Textures, as content: faces, mipmap chains and the rules they must obey.

Every texture is a ``MipmapChainCollection``: a list of faces, each a list of
mipmap levels. A 2D texture has one face, a cube map has six, and a volume
texture has one face whose levels are the whole volume's slices stacked. That
one shape is why ``TextureContent`` can generate mipmaps and convert bitmap
types for all four without knowing which it is.

``Validate`` is where the target profile's limits are enforced, and it is worth
being exact about: XNA's Reach profile allows textures up to 2048 pixels and
refuses a non-power-of-two texture the moment it is used with anything but
clamped addressing, while HiDef allows 4096 and no such restriction. The
pipeline cannot know how a texture will be addressed, so what it checks is what
it can know -- the size limit, and the power-of-two rule for the compressed
formats, which Reach requires unconditionally.
"""

from __future__ import annotations

from .... import Rectangle
from ....Graphics import GraphicsProfile, SurfaceFormat
from .._collections import NamedValueDictionaryOfT
from .._errors import InvalidContentException
from .._identity import ContentItem, ExternalReferenceOfT
from ._bitmap import (
    BitmapContent, Dxt1BitmapContent, Dxt3BitmapContent, Dxt5BitmapContent,
    MipmapChain, MipmapChainCollection, PixelBitmapContentOfT,
)

#: The largest texture each profile allows, in pixels on a side.
_PROFILE_LIMITS = {GraphicsProfile.Reach: 2048, GraphicsProfile.HiDef: 4096}

#: The block-compressed formats, which Reach requires to be a power of two.
_COMPRESSED = (SurfaceFormat.Dxt1, SurfaceFormat.Dxt3, SurfaceFormat.Dxt5)


class TextureContent(ContentItem):
    """One texture, in whatever bitmap type it currently holds."""

    __slots__ = ("_faces",)

    def __init__(self, faces: MipmapChainCollection) -> None:
        super().__init__()
        if not isinstance(faces, MipmapChainCollection):
            raise TypeError(
                f"faces must be a MipmapChainCollection, not {type(faces).__name__}")
        self._faces = faces

    @property
    def Faces(self) -> MipmapChainCollection:
        return self._faces

    def Validate(self, targetProfile: GraphicsProfile | None) -> None:
        """Refuses a texture the target profile could not hold.

        ``None`` means "no profile in particular", which is what a caller that
        is building intermediate content rather than a final asset passes: the
        structural checks still run, and the size limits do not.
        """
        profile = None if targetProfile is None else GraphicsProfile(targetProfile)
        if not self._faces:
            raise InvalidContentException("a texture has no faces", self.Identity)
        for face_index, chain in enumerate(self._faces):
            if not chain:
                raise InvalidContentException(
                    f"face {face_index} has no mipmap levels", self.Identity)
            self._validate_chain(face_index, chain, profile)

    def _validate_chain(self, face_index: int, chain: MipmapChain,
                        profile: GraphicsProfile | None) -> None:
        top = chain[0]
        limit = _PROFILE_LIMITS.get(profile) if profile is not None else None
        if limit is not None and (top.Width > limit or top.Height > limit):
            raise InvalidContentException(
                f"face {face_index} is {top.Width}x{top.Height}, and "
                f"{profile.name} allows at most {limit}", self.Identity)
        found, surface = top.TryGetFormat()
        if (profile is GraphicsProfile.Reach and found and surface in _COMPRESSED
                and not (_is_power_of_two(top.Width)
                         and _is_power_of_two(top.Height))):
            raise InvalidContentException(
                f"face {face_index} is {top.Width}x{top.Height} in "
                f"{surface.name}, and Reach requires a compressed texture's "
                "dimensions to be powers of two", self.Identity)
        width, height = top.Width, top.Height
        for level, bitmap in enumerate(list(chain)[1:], start=1):
            width = max(1, width // 2)
            height = max(1, height // 2)
            if bitmap.Width != width or bitmap.Height != height:
                raise InvalidContentException(
                    f"face {face_index} level {level} is "
                    f"{bitmap.Width}x{bitmap.Height}, and the level above it "
                    f"makes {width}x{height} the only size that follows",
                    self.Identity)
            if type(bitmap) is not type(top):
                raise InvalidContentException(
                    f"face {face_index} level {level} is a "
                    f"{type(bitmap).__name__} and level 0 is a "
                    f"{type(top).__name__}", self.Identity)

    def GenerateMipmaps(self, overwriteExistingMipmaps: bool) -> None:
        """Builds every level below the top one, by halving until 1x1.

        A face that already has levels is left alone unless the caller says to
        overwrite: an artist who authored their own mipmaps -- which is the
        whole reason a ``.dds`` carries them -- did so on purpose.
        """
        if type(overwriteExistingMipmaps) is not bool:
            raise TypeError("overwriteExistingMipmaps must be a bool")
        for chain in self._faces:
            if len(chain) > 1:
                if not overwriteExistingMipmaps:
                    continue
                while chain.Count > 1:
                    chain.RemoveAt(chain.Count - 1)
            top = chain[0]
            width, height = top.Width, top.Height
            while width > 1 or height > 1:
                width = max(1, width // 2)
                height = max(1, height // 2)
                level = _like(top, width, height)
                BitmapContent.Copy(
                    top, Rectangle(0, 0, top.Width, top.Height),
                    level, Rectangle(0, 0, width, height))
                chain.Add(level)

    def ConvertBitmapType(self, newBitmapType: type) -> None:
        """Rewrites every level as ``newBitmapType``.

        This is how a texture becomes DXT-compressed, and how a compressed one
        is brought back to ``Color`` for a processor that needs to look at
        pixels. The conversion goes through ``BitmapContent.Copy``, so a type
        that cannot be converted says so there rather than silently producing
        an empty bitmap.
        """
        if not isinstance(newBitmapType, type) \
                or not issubclass(newBitmapType, BitmapContent):
            raise TypeError(
                "newBitmapType must be a BitmapContent subclass, not "
                f"{newBitmapType!r}")
        for chain in self._faces:
            for level, bitmap in enumerate(list(chain)):
                if type(bitmap) is newBitmapType:
                    continue
                converted = _make(newBitmapType, bitmap.Width, bitmap.Height)
                BitmapContent.Copy(bitmap, converted)
                converted.Name = bitmap.Name
                converted.Identity = bitmap.Identity
                chain.SetItem(level, converted)


class Texture2DContent(TextureContent):
    """A texture with exactly one face."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(MipmapChainCollection(1))

    @property
    def Mipmaps(self) -> MipmapChain:
        return self._faces[0]

    @Mipmaps.setter
    def Mipmaps(self, value: MipmapChain | BitmapContent) -> None:
        if isinstance(value, BitmapContent):
            # XNA's implicit BitmapContent -> MipmapChain conversion, which is
            # what makes ``content.Mipmaps = bitmap`` the ordinary spelling.
            value = MipmapChain(value)
        if not isinstance(value, MipmapChain):
            raise TypeError(
                f"Mipmaps must be a MipmapChain or a BitmapContent, not "
                f"{type(value).__name__}")
        self._faces.SetItem(0, value)

    def Validate(self, targetProfile: GraphicsProfile | None) -> None:
        if len(self._faces) != 1:
            raise InvalidContentException(
                f"a Texture2DContent has one face, not {len(self._faces)}",
                self.Identity)
        super().Validate(targetProfile)


class Texture3DContent(TextureContent):
    """A volume texture, laid out as one *face per mipmap level*.

    A volume has two things to store where a 2D texture has one: slices, and
    levels. ``MipmapChainCollection`` has exactly two dimensions, so this type
    uses them both -- ``Faces[level]`` is the list of depth slices at that
    level. That reading is fixed here and nowhere else, and it is what makes
    :meth:`GenerateMipmaps` a real operation rather than an ambiguity: level
    *n+1* has half the width, half the height **and** half the depth of level
    *n*, and there is somewhere to put the result.

    (A cube map reads the same collection as six faces of one level, which is
    why the meaning belongs to the type rather than to the collection.)
    """

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(MipmapChainCollection(1))

    @property
    def _slices(self) -> MipmapChain:
        return self._faces[0]

    def Validate(self, targetProfile: GraphicsProfile | None) -> None:
        profile = None if targetProfile is None else GraphicsProfile(targetProfile)
        if profile is GraphicsProfile.Reach:
            raise InvalidContentException(
                "the Reach profile has no volume textures", self.Identity)
        if not self._faces or not self._faces[0]:
            raise InvalidContentException(
                "a Texture3DContent has at least one level with at least one "
                "slice", self.Identity)
        first = self._faces[0][0]
        depth = len(self._faces[0])
        for level, slices in enumerate(self._faces):
            wanted = (max(1, first.Width >> level), max(1, first.Height >> level),
                      max(1, depth >> level))
            if len(slices) != wanted[2]:
                raise InvalidContentException(
                    f"level {level} has {len(slices)} slices, and halving "
                    f"{depth} makes {wanted[2]} the only count that follows",
                    self.Identity)
            for index, slice_bitmap in enumerate(slices):
                if (slice_bitmap.Width, slice_bitmap.Height) != wanted[:2]:
                    raise InvalidContentException(
                        f"level {level} slice {index} is "
                        f"{slice_bitmap.Width}x{slice_bitmap.Height}, and "
                        f"{wanted[0]}x{wanted[1]} is the only size that follows",
                        self.Identity)
        limit = _PROFILE_LIMITS[GraphicsProfile.HiDef]
        if first.Width > limit or first.Height > limit or depth > limit:
            raise InvalidContentException(
                f"a volume texture is at most {limit} in every dimension",
                self.Identity)

    def GenerateMipmaps(self, overwriteExistingMipmaps: bool) -> None:
        """Halves the volume in all three dimensions until it is 1x1x1.

        Each destination voxel is the average of the eight it covers -- the
        2x2 box in each of the two slices above it -- which is the three
        dimensional form of the filter :class:`TextureContent` uses for a
        surface. Averaging within a slice only would give a volume that is sharp
        along z and blurred across it, and would look like exactly that.
        """
        if type(overwriteExistingMipmaps) is not bool:
            raise TypeError("overwriteExistingMipmaps must be a bool")
        if len(self._faces) > 1:
            if not overwriteExistingMipmaps:
                return
            while self._faces.Count > 1:
                self._faces.RemoveAt(self._faces.Count - 1)
        top = self._faces[0]
        width, height, depth = top[0].Width, top[0].Height, len(top)
        source = top
        while width > 1 or height > 1 or depth > 1:
            width = max(1, width // 2)
            height = max(1, height // 2)
            depth = max(1, depth // 2)
            level = MipmapChain()
            for index in range(depth):
                near = _as_pixels(source[min(index * 2, len(source) - 1)])
                far = _as_pixels(source[min(index * 2 + 1, len(source) - 1)])
                level.Add(_averaged(near, far, width, height))
            self._faces.Add(level)
            source = level


class TextureCubeContent(TextureContent):
    """A cube map: six faces, in XNA's face order."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(MipmapChainCollection(6))

    def Validate(self, targetProfile: GraphicsProfile | None) -> None:
        if len(self._faces) != 6:
            raise InvalidContentException(
                f"a TextureCubeContent has six faces, not {len(self._faces)}",
                self.Identity)
        super().Validate(targetProfile)
        first = self._faces[0][0]
        if first.Width != first.Height:
            raise InvalidContentException(
                f"a cube face is square, and this one is "
                f"{first.Width}x{first.Height}", self.Identity)
        for index, chain in enumerate(list(self._faces)[1:], start=1):
            if chain[0].Width != first.Width or chain[0].Height != first.Height:
                raise InvalidContentException(
                    f"face {index} is {chain[0].Width}x{chain[0].Height} and "
                    f"face 0 is {first.Width}x{first.Height}; a cube map's "
                    "faces are all the same size", self.Identity)


class TextureReferenceDictionary(
        NamedValueDictionaryOfT[ExternalReferenceOfT]):
    """A material's textures, by the name the effect knows them under."""

    __slots__ = ()
    _element = ExternalReferenceOfT


def _as_pixels(bitmap: BitmapContent) -> PixelBitmapContentOfT:
    """A slice as readable pixels, decompressing it if it is compressed."""
    if isinstance(bitmap, PixelBitmapContentOfT):
        return bitmap
    from ._bitmap import DxtBitmapContent

    if isinstance(bitmap, DxtBitmapContent):
        return bitmap._decode()
    raise InvalidContentException(
        f"{type(bitmap).__name__} cannot be read as pixels")


def _averaged(near: "PixelBitmapContentOfT", far: "PixelBitmapContentOfT",
              width: int, height: int) -> "PixelBitmapContentOfT":
    """One slice of the next level down: the 2x2x2 box below each voxel."""
    from .... import Vector4
    from ._vectors import from_vector4, to_vector4

    element = near._pixel_type
    result = PixelBitmapContentOfT(width, height, element=element)
    for y in range(height):
        for x in range(width):
            total = [0.0, 0.0, 0.0, 0.0]
            count = 0
            for plane in (near, far):
                for offset_y in (0, 1):
                    for offset_x in (0, 1):
                        sample_x = min(x * 2 + offset_x, plane.Width - 1)
                        sample_y = min(y * 2 + offset_y, plane.Height - 1)
                        value = to_vector4(plane.GetPixel(sample_x, sample_y))
                        total[0] += value.X
                        total[1] += value.Y
                        total[2] += value.Z
                        total[3] += value.W
                        count += 1
            result.SetPixel(x, y, from_vector4(element, Vector4(
                total[0] / count, total[1] / count, total[2] / count,
                total[3] / count)))
    return result


def _is_power_of_two(value: int) -> bool:
    return value > 0 and not (value & (value - 1))


def _like(bitmap: BitmapContent, width: int, height: int) -> BitmapContent:
    return _make(type(bitmap), width, height,
                 element=getattr(bitmap, "_pixel_type", None))


def _make(kind: type, width: int, height: int, element: type | None = None
          ) -> BitmapContent:
    if kind is PixelBitmapContentOfT:
        if element is None:
            raise TypeError(
                "PixelBitmapContentOfT needs a pixel type; use a closed "
                "subclass or pass one")
        return PixelBitmapContentOfT(width, height, element=element)
    if issubclass(kind, PixelBitmapContentOfT):
        return kind(width, height)
    if kind in (Dxt1BitmapContent, Dxt3BitmapContent, Dxt5BitmapContent):
        return kind(width, height)
    return kind(width, height)
