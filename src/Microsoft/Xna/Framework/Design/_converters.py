"""Python-native projection of XNA 4.0 mathematical type converters."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
import re
from types import MappingProxyType
from typing import Callable

from .. import (
    BoundingBox, BoundingSphere, Color, Matrix, Plane, Point, Quaternion, Ray,
    Rectangle, Vector2, Vector3, Vector4,
)
from .._numeric import f32, int32, uint8


_Descriptor = tuple[Callable[..., object], tuple[object, ...]]
_FLOAT_TYPES = (Vector2, Vector3, Vector4, Quaternion)
_COMPONENTS = {
    Point: (("X", int), ("Y", int)),
    Rectangle: (("X", int), ("Y", int), ("Width", int), ("Height", int)),
    Vector2: (("X", float), ("Y", float)),
    Vector3: (("X", float), ("Y", float), ("Z", float)),
    Vector4: (("X", float), ("Y", float), ("Z", float), ("W", float)),
    Quaternion: (("X", float), ("Y", float), ("Z", float), ("W", float)),
    Color: (("R", int), ("G", int), ("B", int), ("A", int)),
    Matrix: (("Translation", Vector3), *((name, float) for name in Matrix._names)),
    BoundingBox: (("Min", Vector3), ("Max", Vector3)),
    BoundingSphere: (("Center", Vector3), ("Radius", float)),
    Plane: (("Normal", Vector3), ("D", float)),
    Ray: (("Position", Vector3), ("Direction", Vector3)),
}
_STRING_TYPES = {Point, Vector2, Vector3, Vector4, Quaternion, Color}
_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")


class _Culture:
    __slots__ = ("decimal", "separator", "nan", "positive_infinity", "negative_infinity")

    def __init__(self, decimal: str, separator: str, nan: str,
                 positive_infinity: str, negative_infinity: str) -> None:
        self.decimal = decimal
        self.separator = separator
        self.nan = nan
        self.positive_infinity = positive_infinity
        self.negative_infinity = negative_infinity


_INVARIANT = _Culture(".", ",", "NaN", "Infinity", "-Infinity")
_GERMAN = _Culture(",", ";", "NaN", "+unendlich", "-unendlich")


def _culture(value: str | None) -> _Culture:
    if value is None:
        return _INVARIANT
    if not isinstance(value, str):
        raise TypeError("culture must be a culture-name string or None")
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"", "invariant", "root", "en", "en-us"}:
        return _INVARIANT
    if normalized in {"de", "de-de"}:
        return _GERMAN
    raise ValueError(f"unsupported deterministic Design culture {value!r}")


def _snapshot(value: object) -> object:
    if isinstance(value, (Vector2, Vector3, Vector4, Quaternion, Matrix, Color,
                          Point, Rectangle, BoundingBox, BoundingSphere, Plane, Ray)):
        return copy.copy(value)
    return value


def _parse_integer(value: str) -> int:
    value = value.strip()
    if not _INTEGER_RE.fullmatch(value):
        raise ValueError("invalid Int32 component")
    return int32(int(value))


def _parse_byte(value: str) -> int:
    try:
        return uint8(_parse_integer(value))
    except OverflowError as error:
        raise ValueError("Byte component is outside 0..255") from error


def _valid_decimal(value: str, decimal: str) -> bool:
    escaped = re.escape(decimal)
    return re.fullmatch(rf"[+-]?(?:[0-9]+(?:{escaped}[0-9]*)?|{escaped}[0-9]+)(?:[eE][+-]?[0-9]+)?", value) is not None


def _parse_single(value: str, culture: _Culture) -> float:
    value = value.strip()
    if value in {culture.nan, "NaN"}:
        return f32(math.nan)
    if value in {culture.positive_infinity, "Infinity", "+Infinity"}:
        return f32(math.inf)
    if value in {culture.negative_infinity, "-Infinity"}:
        return f32(-math.inf)
    if not _valid_decimal(value, culture.decimal):
        raise ValueError("invalid Single component")
    invariant = value if culture.decimal == "." else value.replace(culture.decimal, ".")
    try:
        parsed = f32(float(invariant))
    except (ValueError, OverflowError) as error:
        raise ValueError("invalid Single component") from error
    if math.isinf(parsed):
        raise ValueError("Single component is outside its finite range")
    return parsed


def _format_single(value: float, culture: _Culture) -> str:
    value = f32(value)
    if math.isnan(value):
        return culture.nan
    if value == math.inf:
        return culture.positive_infinity
    if value == -math.inf:
        return culture.negative_infinity
    if value == 0.0:
        return "0"
    negative = math.copysign(1.0, value) < 0.0
    with localcontext() as context:
        context.prec = 7
        context.rounding = ROUND_HALF_UP
        rounded = +Decimal.from_float(abs(value))
    exponent = rounded.adjusted()
    if exponent < -4 or exponent >= 7:
        mantissa = rounded.scaleb(-exponent)
        text = format(mantissa, "f").rstrip("0").rstrip(".")
        text = f"{text}E{'+' if exponent >= 0 else '-'}{abs(exponent):02d}"
    else:
        text = format(rounded, "f").rstrip("0").rstrip(".")
    if negative:
        text = "-" + text
    if culture.decimal != ".":
        text = text.replace(".", culture.decimal)
    return text


def _split_components(value: object, culture: _Culture, count: int) -> list[str]:
    if not isinstance(value, str):
        raise TypeError("value must be str")
    parts = value.strip().split(culture.separator)
    if len(parts) != count or any(not part.strip() for part in parts):
        raise ValueError(f"expected {count} components")
    return parts


def _parse_value(target: type, culture: _Culture, value: object) -> object:
    count = len(_COMPONENTS[target])
    parts = _split_components(value, culture, count)
    if target is Point:
        return Point(*(_parse_integer(part) for part in parts))
    if target is Color:
        return Color(*(_parse_byte(part) for part in parts))
    values = tuple(_parse_single(part, culture) for part in parts)
    return target(*values)


def _format_value(value: object, culture: _Culture) -> str:
    if isinstance(value, Point):
        components = (str(value.X), str(value.Y))
    elif isinstance(value, Color):
        components = tuple(str(component) for component in value)
    elif isinstance(value, _FLOAT_TYPES):
        components = tuple(_format_single(component, culture) for component in value)
    else:
        return value.ToString()  # type: ignore[attr-defined]
    return (culture.separator + " ").join(components)


def _properties_for(value: object) -> Mapping[str, object]:
    target = type(value)
    definitions = _COMPONENTS.get(target)
    if definitions is None:
        raise TypeError("value has the wrong type for this Design converter")
    return MappingProxyType({name: _snapshot(getattr(value, name)) for name, _ in definitions})


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("propertyValues must be a Mapping[str, object]")
    return value


def _required(values: Mapping[str, object], name: str, wanted: type) -> object:
    if name not in values or values[name] is None:
        raise ValueError(f"required property {name!r} is missing or None")
    value = values[name]
    if wanted is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"property {name!r} must be int")
        return int32(value, name=name)
    if wanted is float:
        if type(value) is not float:
            raise TypeError(f"property {name!r} must be a binary32 float value")
        return f32(value)
    if type(value) is not wanted:
        raise TypeError(f"property {name!r} must be {wanted.__name__}")
    return _snapshot(value)


def _create(target: type, property_values: object) -> object:
    values = _mapping(property_values)
    if target is Matrix:
        return Matrix(*(_required(values, name, float) for name in Matrix._names))
    definitions = _COMPONENTS[target]
    arguments = [_required(values, name, wanted) for name, wanted in definitions]
    if target is Color:
        arguments = [uint8(value, name=name) for (name, _), value in zip(definitions, arguments)]
    return target(*arguments)


def _descriptor(value: object) -> _Descriptor:
    target = type(value)
    if target is Matrix:
        arguments = tuple(getattr(value, name) for name in Matrix._names)
    else:
        arguments = tuple(_snapshot(getattr(value, name)) for name, _ in _COMPONENTS[target])
    return target, arguments


class _MathTypeConverterBase:
    propertyDescriptions: Mapping[str, object]
    supportStringConvert: bool

    def __init__(self) -> None:
        self.propertyDescriptions = MappingProxyType({})
        self.supportStringConvert = True
        self._target_type: type | None = None

    def _configure(self, target: type) -> None:
        self._target_type = target
        self.supportStringConvert = target in _STRING_TYPES
        self.propertyDescriptions = MappingProxyType(dict(_COMPONENTS[target]))

    def CanConvertFrom(self, sourceType: type) -> bool:
        if not isinstance(sourceType, type):
            raise TypeError("sourceType must be type")
        return self.supportStringConvert and sourceType is str

    def CanConvertTo(self, destinationType: type) -> bool:
        if not isinstance(destinationType, type):
            raise TypeError("destinationType must be type")
        return destinationType in {str, tuple}

    def GetCreateInstanceSupported(self) -> bool:
        return True

    def GetPropertiesSupported(self) -> bool:
        return True

    def GetProperties(self, value: object) -> Mapping[str, object]:
        if self._target_type is None:
            return MappingProxyType({})
        if type(value) is not self._target_type:
            raise TypeError(f"value must be {self._target_type.__name__}")
        return _properties_for(value)

    def ConvertFrom(self, culture: str | None, value: object) -> object:
        selected = _culture(culture)
        if self._target_type is None or not self.supportStringConvert:
            raise TypeError("conversion from string is not supported by this converter")
        return _parse_value(self._target_type, selected, value)

    def ConvertTo(self, culture: str | None, value: object, destinationType: type) -> object:
        selected = _culture(culture)
        if not isinstance(destinationType, type):
            raise TypeError("destinationType must be type")
        if destinationType is str:
            if self._target_type is not None and type(value) is self._target_type:
                return _format_value(value, selected)
            if value is None:
                raise TypeError("value cannot be None")
            return str(value)
        if destinationType is tuple:
            if self._target_type is None or type(value) is not self._target_type:
                raise TypeError("value has the wrong type for an instance descriptor")
            return _descriptor(value)
        raise TypeError("destinationType is not supported")

    def CreateInstance(self, propertyValues: Mapping[str, object]) -> object:
        if self._target_type is None:
            raise TypeError("MathTypeConverter does not describe a concrete value")
        return _create(self._target_type, propertyValues)


class MathTypeConverter(_MathTypeConverterBase):
    propertyDescriptions: Mapping[str, object] = MappingProxyType({})
    supportStringConvert: bool = True

    def __init__(self) -> None:
        super().__init__()

    def CanConvertFrom(self, sourceType: type) -> bool:
        return super().CanConvertFrom(sourceType)

    def CanConvertTo(self, destinationType: type) -> bool:
        return super().CanConvertTo(destinationType)

    def GetCreateInstanceSupported(self) -> bool:
        return super().GetCreateInstanceSupported()

    def GetPropertiesSupported(self) -> bool:
        return super().GetPropertiesSupported()

    def GetProperties(self, value: object) -> Mapping[str, object]:
        return super().GetProperties(value)


def _converter(name: str, target: type, declared_from: bool) -> type:
    namespace: dict[str, object] = {}

    def __init__(self) -> None:
        MathTypeConverter.__init__(self)
        self._configure(target)

    def ConvertFrom(self, culture: str | None, value: object) -> object:
        return _MathTypeConverterBase.ConvertFrom(self, culture, value)

    def ConvertTo(self, culture: str | None, value: object, destinationType: type) -> object:
        return _MathTypeConverterBase.ConvertTo(self, culture, value, destinationType)

    def CreateInstance(self, propertyValues: Mapping[str, object]) -> object:
        return _MathTypeConverterBase.CreateInstance(self, propertyValues)

    namespace["__init__"] = __init__
    if declared_from:
        namespace["ConvertFrom"] = ConvertFrom
    namespace["ConvertTo"] = ConvertTo
    namespace["CreateInstance"] = CreateInstance
    result = type(name, (MathTypeConverter,), namespace)
    arities = {"__init__": {0}, "ConvertTo": {3}, "CreateInstance": {1}}
    if declared_from:
        arities["ConvertFrom"] = {2}
    result.__xna_arities__ = arities
    return result


BoundingBoxConverter = _converter("BoundingBoxConverter", BoundingBox, True)
BoundingSphereConverter = _converter("BoundingSphereConverter", BoundingSphere, True)
ColorConverter = _converter("ColorConverter", Color, True)
MatrixConverter = _converter("MatrixConverter", Matrix, False)
PlaneConverter = _converter("PlaneConverter", Plane, False)
PointConverter = _converter("PointConverter", Point, True)
QuaternionConverter = _converter("QuaternionConverter", Quaternion, True)
RayConverter = _converter("RayConverter", Ray, True)
RectangleConverter = _converter("RectangleConverter", Rectangle, False)
Vector2Converter = _converter("Vector2Converter", Vector2, True)
Vector3Converter = _converter("Vector3Converter", Vector3, True)
Vector4Converter = _converter("Vector4Converter", Vector4, True)


MathTypeConverter.__xna_arities__ = {
    "__init__": {0}, "CanConvertFrom": {1}, "CanConvertTo": {1},
    "GetCreateInstanceSupported": {0}, "GetPropertiesSupported": {0},
    "GetProperties": {1},
}
