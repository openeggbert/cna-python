"""Materials: what a surface looks like, before an effect is chosen for it.

Every material property lives in ``OpaqueData`` under a string key, and the
typed properties on the derived materials are windows onto it. That is not an
implementation detail -- it is the design. An importer that read a format with
a property XNA has no name for can put it in the same dictionary, a processor
can read it, and the material still round-trips through the intermediate
serializer with everything else.

Which is why every derived material also exposes its keys as constants: a
processor that wants "whatever the diffuse colour is, on any material that has
one" reads ``BasicMaterialContent.DiffuseColorKey`` out of the dictionary rather
than testing the material's type.

Every typed property is *nullable*, and the difference matters: ``None`` means
the material does not say, and the effect's own default stands. Zero means the
material says zero.
"""

from __future__ import annotations

from .... import Vector3
from ....Graphics import CompareFunction
from .._identity import ContentItem, ExternalReferenceOfT
from ._texture import TextureReferenceDictionary


class MaterialContent(ContentItem):
    """A named bag of material properties and texture references."""

    __slots__ = ("_textures",)

    def __init__(self) -> None:
        super().__init__()
        self._textures = TextureReferenceDictionary()

    @property
    def Textures(self) -> TextureReferenceDictionary:
        return self._textures

    def SetProperty(self, key: str, value: object) -> None:
        """Stores a property, or removes it when ``value`` is ``None``.

        Removing is what makes "the material does not say" expressible: a key
        set to ``None`` and a key that is absent would otherwise be two ways of
        spelling the same thing, and the intermediate serializer would write the
        first one out as an element saying nothing.
        """
        if value is None:
            self.OpaqueData.Remove(key)
            return
        self.OpaqueData[key] = value

    def SetTexture(self, key: str,
                   value: ExternalReferenceOfT | None) -> None:
        if value is None:
            self._textures.Remove(key)
            return
        self._textures[key] = value

    def GetValueTypeProperty(self, key: str, *, expected: type):
        """A value-typed property, or ``None`` when the material has none.

        XNA's generic parameter is the expected type, and it has no argument to
        be inferred from, so it is spelled as a keyword: the positional
        signature stays XNA's one key. A stored value of the wrong type is an
        error rather than a silent ``None`` -- it means an importer wrote
        something a processor is about to misread.
        """
        found, value = self.OpaqueData.TryGetValue(key)
        if not found:
            return None
        if not isinstance(value, expected):
            raise TypeError(
                f"{key!r} holds a {type(value).__name__}, not a "
                f"{expected.__name__}")
        return value

    def GetReferenceTypeProperty(self, key: str, *, expected: type):
        return self.GetValueTypeProperty(key, expected=expected)

    def GetTexture(self, key: str) -> ExternalReferenceOfT | None:
        found, value = self._textures.TryGetValue(key)
        return value if found else None


MaterialContent.__xna_arities__ = {
    "SetProperty": {2}, "SetTexture": {2},
    "GetValueTypeProperty": {1}, "GetReferenceTypeProperty": {1},
}


def _property(key: str, kind: type | tuple[type, ...], what: str) -> property:
    """One nullable material property, stored under ``key`` in the opaque data."""

    def get(self: MaterialContent):
        found, value = self.OpaqueData.TryGetValue(key)
        return value if found else None

    def set(self: MaterialContent, value: object) -> None:
        if value is None:
            self.OpaqueData.Remove(key)
            return
        if kind is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"{what} must be a real number or None, not "
                    f"{type(value).__name__}")
            value = float(value)
        elif kind is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    f"{what} must be an int or None, not {type(value).__name__}")
        elif kind is bool:
            if type(value) is not bool:
                raise TypeError(f"{what} must be a bool or None")
        elif isinstance(kind, type) and issubclass(kind, CompareFunction):
            value = CompareFunction(value)
        elif not isinstance(value, kind):
            raise TypeError(
                f"{what} must be a {getattr(kind, '__name__', kind)} or None, "
                f"not {type(value).__name__}")
        self.OpaqueData[key] = value

    get.__name__ = what
    # The declared type, as an object rather than a string: the intermediate
    # serializer reads it to decide whether an element needs a ``Type``
    # attribute, and a generated property would otherwise declare nothing.
    get.__annotations__ = {"return": kind}
    return property(get, set)


def _texture(key: str, what: str) -> property:
    """One texture reference, stored under ``key`` in ``Textures``."""

    def get(self: MaterialContent):
        return self.GetTexture(key)

    def set(self: MaterialContent, value: object) -> None:
        if value is not None and not isinstance(value, ExternalReferenceOfT):
            raise TypeError(
                f"{what} must be an ExternalReferenceOfT or None, not "
                f"{type(value).__name__}")
        self.SetTexture(key, value)

    get.__name__ = what
    get.__annotations__ = {"return": ExternalReferenceOfT}
    return property(get, set)


class BasicMaterialContent(MaterialContent):
    """What ``BasicEffect`` renders: a diffuse colour, a specular highlight."""

    __slots__ = ()

    DiffuseColorKey = "DiffuseColor"
    SpecularColorKey = "SpecularColor"
    EmissiveColorKey = "EmissiveColor"
    SpecularPowerKey = "SpecularPower"
    AlphaKey = "Alpha"
    VertexColorEnabledKey = "VertexColorEnabled"
    TextureKey = "Texture"

    DiffuseColor = _property(DiffuseColorKey, Vector3, "DiffuseColor")
    SpecularColor = _property(SpecularColorKey, Vector3, "SpecularColor")
    EmissiveColor = _property(EmissiveColorKey, Vector3, "EmissiveColor")
    SpecularPower = _property(SpecularPowerKey, float, "SpecularPower")
    Alpha = _property(AlphaKey, float, "Alpha")
    VertexColorEnabled = _property(VertexColorEnabledKey, bool, "VertexColorEnabled")
    Texture = _texture(TextureKey, "Texture")


class AlphaTestMaterialContent(MaterialContent):
    """What ``AlphaTestEffect`` renders: a cutout, by comparison and threshold."""

    __slots__ = ()

    AlphaFunctionKey = "AlphaFunction"
    ReferenceAlphaKey = "ReferenceAlpha"
    DiffuseColorKey = "DiffuseColor"
    AlphaKey = "Alpha"
    VertexColorEnabledKey = "VertexColorEnabled"
    TextureKey = "Texture"

    AlphaFunction = _property(AlphaFunctionKey, CompareFunction, "AlphaFunction")
    ReferenceAlpha = _property(ReferenceAlphaKey, int, "ReferenceAlpha")
    DiffuseColor = _property(DiffuseColorKey, Vector3, "DiffuseColor")
    Alpha = _property(AlphaKey, float, "Alpha")
    VertexColorEnabled = _property(VertexColorEnabledKey, bool, "VertexColorEnabled")
    Texture = _texture(TextureKey, "Texture")


class DualTextureMaterialContent(MaterialContent):
    """What ``DualTextureEffect`` renders: a texture modulated by a lightmap."""

    __slots__ = ()

    DiffuseColorKey = "DiffuseColor"
    AlphaKey = "Alpha"
    VertexColorEnabledKey = "VertexColorEnabled"
    TextureKey = "Texture"
    Texture2Key = "Texture2"

    DiffuseColor = _property(DiffuseColorKey, Vector3, "DiffuseColor")
    Alpha = _property(AlphaKey, float, "Alpha")
    VertexColorEnabled = _property(VertexColorEnabledKey, bool, "VertexColorEnabled")
    Texture = _texture(TextureKey, "Texture")
    Texture2 = _texture(Texture2Key, "Texture2")


class EnvironmentMapMaterialContent(MaterialContent):
    """What ``EnvironmentMapEffect`` renders: a cube-mapped reflection."""

    __slots__ = ()

    EnvironmentMapAmountKey = "EnvironmentMapAmount"
    EnvironmentMapSpecularKey = "EnvironmentMapSpecular"
    FresnelFactorKey = "FresnelFactor"
    DiffuseColorKey = "DiffuseColor"
    EmissiveColorKey = "EmissiveColor"
    AlphaKey = "Alpha"
    TextureKey = "Texture"
    EnvironmentMapKey = "EnvironmentMap"

    EnvironmentMapAmount = _property(
        EnvironmentMapAmountKey, float, "EnvironmentMapAmount")
    EnvironmentMapSpecular = _property(
        EnvironmentMapSpecularKey, Vector3, "EnvironmentMapSpecular")
    FresnelFactor = _property(FresnelFactorKey, float, "FresnelFactor")
    DiffuseColor = _property(DiffuseColorKey, Vector3, "DiffuseColor")
    EmissiveColor = _property(EmissiveColorKey, Vector3, "EmissiveColor")
    Alpha = _property(AlphaKey, float, "Alpha")
    Texture = _texture(TextureKey, "Texture")
    EnvironmentMap = _texture(EnvironmentMapKey, "EnvironmentMap")


class SkinnedMaterialContent(MaterialContent):
    """What ``SkinnedEffect`` renders: a mesh deformed by a bone hierarchy."""

    __slots__ = ()

    WeightsPerVertexKey = "WeightsPerVertex"
    DiffuseColorKey = "DiffuseColor"
    SpecularColorKey = "SpecularColor"
    EmissiveColorKey = "EmissiveColor"
    SpecularPowerKey = "SpecularPower"
    AlphaKey = "Alpha"
    TextureKey = "Texture"

    WeightsPerVertex = _property(WeightsPerVertexKey, int, "WeightsPerVertex")
    DiffuseColor = _property(DiffuseColorKey, Vector3, "DiffuseColor")
    SpecularColor = _property(SpecularColorKey, Vector3, "SpecularColor")
    EmissiveColor = _property(EmissiveColorKey, Vector3, "EmissiveColor")
    SpecularPower = _property(SpecularPowerKey, float, "SpecularPower")
    Alpha = _property(AlphaKey, float, "Alpha")
    Texture = _texture(TextureKey, "Texture")


class EffectContent(ContentItem):
    """The *source* of an effect, as text.

    The source, not the bytecode: what compiles it is ``EffectProcessor``, and
    what that produces is ``CompiledEffectContent``.
    """

    __slots__ = ("_effect_code",)

    def __init__(self) -> None:
        super().__init__()
        self._effect_code = ""

    @property
    def EffectCode(self) -> str:
        return self._effect_code

    @EffectCode.setter
    def EffectCode(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"EffectCode must be a str, not {type(value).__name__}")
        self._effect_code = value


class EffectMaterialContent(MaterialContent):
    """A material rendered by an effect of the artist's own.

    It carries both the effect's source reference and its compiled one: the
    first is what a content project names, and the second is what the build
    fills in once ``EffectProcessor`` has run.
    """

    __slots__ = ()

    EffectKey = "Effect"
    CompiledEffectKey = "CompiledEffect"

    @property
    def Effect(self) -> ExternalReferenceOfT | None:
        found, value = self.OpaqueData.TryGetValue(self.EffectKey)
        return value if found else None

    @Effect.setter
    def Effect(self, value: ExternalReferenceOfT | None) -> None:
        self.SetProperty(self.EffectKey, value)

    @property
    def CompiledEffect(self) -> ExternalReferenceOfT | None:
        found, value = self.OpaqueData.TryGetValue(self.CompiledEffectKey)
        return value if found else None

    @CompiledEffect.setter
    def CompiledEffect(self, value: ExternalReferenceOfT | None) -> None:
        self.SetProperty(self.CompiledEffectKey, value)
