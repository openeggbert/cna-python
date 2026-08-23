"""Core integral and color value types."""

from __future__ import annotations

import math

from ._language import classproperty
from ._math import MathHelper, Vector3, Vector4
from ._numeric import f32, hash32_sum, int32, mul32, uint32


def _byte(value: object) -> int:
    number = float(value)
    if math.isnan(number) or number <= 0:
        return 0
    if number >= 255:
        return 255
    return int(number)


def _normalized_byte(value: object) -> int:
    scaled = f32(f32(value) * 255.0)
    if math.isnan(scaled) or scaled <= 0:
        return 0
    if scaled >= 255:
        return 255
    return round(scaled)


def _pack_unorm(bitmask: float, value: object) -> int:
    scaled = f32(f32(value) * f32(bitmask))
    if math.isnan(scaled) or scaled <= 0:
        return 0
    if scaled >= bitmask:
        return int(bitmask)
    return round(scaled)


def _truncating_divide(value: int, divisor: int) -> int:
    result = abs(value) // divisor
    return -result if value < 0 else result


class _ColorProperty:
    def __init__(self, packed: int) -> None:
        self._packed = packed

    def __get__(self, instance: object, owner: type | None = None) -> "Color":
        return Color._from_packed(self._packed)


class Color:
    __slots__ = ("_packed_value",)

    def __init__(self, *args: object) -> None:
        self._packed_value = 0
        if not args:
            channels = (0, 0, 0, 0)
        elif len(args) == 1 and isinstance(args[0], Vector4):
            channels = tuple(_normalized_byte(value) for value in args[0])
        elif len(args) == 1 and isinstance(args[0], Vector3):
            channels = (*(_normalized_byte(value) for value in args[0]), 255)
        elif len(args) in (3, 4) and all(type(value) is int for value in args):
            values = tuple(int32(value) for value in (args if len(args) == 4 else (*args, 255)))
            channels = tuple(_byte(value) for value in values)
        elif len(args) in (3, 4) and all(type(value) is float for value in args):
            values = args if len(args) == 4 else (*args, 1.0)
            channels = tuple(_normalized_byte(value) for value in values)
        else:
            raise TypeError("Color expects (), Vector3, Vector4, three/four Int32, or three/four Single values")
        self.R, self.G, self.B, self.A = channels

    @classmethod
    def _from_packed(cls, value: int) -> "Color":
        result = cls(0, 0, 0, 0)
        result.PackedValue = value
        return result

    @property
    def R(self) -> int:
        return self._packed_value & 0xFF

    @R.setter
    def R(self, value: int) -> None:
        self._packed_value = (self._packed_value & 0xFFFFFF00) | _byte(value)

    @property
    def G(self) -> int:
        return (self._packed_value >> 8) & 0xFF

    @G.setter
    def G(self, value: int) -> None:
        self._packed_value = (self._packed_value & 0xFFFF00FF) | (_byte(value) << 8)

    @property
    def B(self) -> int:
        return (self._packed_value >> 16) & 0xFF

    @B.setter
    def B(self, value: int) -> None:
        self._packed_value = (self._packed_value & 0xFF00FFFF) | (_byte(value) << 16)

    @property
    def A(self) -> int:
        return (self._packed_value >> 24) & 0xFF

    @A.setter
    def A(self, value: int) -> None:
        self._packed_value = (self._packed_value & 0x00FFFFFF) | (_byte(value) << 24)

    @property
    def PackedValue(self) -> int:
        return self._packed_value

    @PackedValue.setter
    def PackedValue(self, value: int) -> None:
        self._packed_value = uint32(value, name="PackedValue")

    @staticmethod
    def FromNonPremultiplied(*args: object) -> "Color":
        if len(args) == 1 and isinstance(args[0], Vector4):
            value = args[0]
            return Color(mul32(value.X,value.W),mul32(value.Y,value.W),mul32(value.Z,value.W),value.W)
        if len(args) == 4 and all(type(value) is int for value in args):
            r,g,b,a=(int32(value) for value in args)
            return Color(_byte(_truncating_divide(r*a,255)),_byte(_truncating_divide(g*a,255)),
                         _byte(_truncating_divide(b*a,255)),_byte(a))
        raise TypeError("FromNonPremultiplied expects Vector4 or r, g, b, a")

    def ToVector3(self) -> Vector3:
        return Vector3(f32(self.R / 255.0), f32(self.G / 255.0), f32(self.B / 255.0))

    def ToVector4(self) -> Vector4:
        return Vector4(f32(self.R / 255.0), f32(self.G / 255.0), f32(self.B / 255.0), f32(self.A / 255.0))

    @staticmethod
    def Lerp(value1: "Color", value2: "Color", amount: float) -> "Color":
        if not isinstance(value1,Color) or not isinstance(value2,Color):raise TypeError("Lerp expects two Color values")
        fraction=_pack_unorm(65536.0,amount)
        return Color(*(a+(((b-a)*fraction)>>16) for a,b in zip(value1,value2)))

    @staticmethod
    def Multiply(value: "Color", scale: float) -> "Color":
        if not isinstance(value,Color):raise TypeError("value must be Color")
        scaled=mul32(scale,65536.0)
        fixed=0 if math.isnan(scaled) or scaled<=0 else 16777215 if scaled>=16777215 else int(scaled)
        return Color(*(min(255,(channel*fixed)>>16) for channel in value))

    def __mul__(self, scale: float) -> "Color":
        return Color.Multiply(self, scale)

    def __iter__(self):
        return iter((self.R, self.G, self.B, self.A))

    def __copy__(self) -> "Color":
        return Color._from_packed(self.PackedValue)

    __deepcopy__ = lambda self, memo: self.__copy__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Color) and self.PackedValue == other.PackedValue

    def __hash__(self) -> int: return self.GetHashCode()

    def Equals(self, other: object) -> bool:
        return self == other

    def GetHashCode(self) -> int:
        value=self.PackedValue
        return value if value<0x80000000 else value-0x100000000

    def ToString(self) -> str:
        return f"{{R:{self.R} G:{self.G} B:{self.B} A:{self.A}}}"

    __str__ = ToString

    def __repr__(self) -> str:
        return f"Color({self.R}, {self.G}, {self.B}, {self.A})"


# Named values are pinned from the XNA 4.0 Color property inventory.  The
# descriptor returns a new mutable struct value on every access.
_NAMED_COLOR_PACKED = {
    "AliceBlue": 4294965488,
    "AntiqueWhite": 4292340730,
    "Aqua": 4294967040,
    "Aquamarine": 4292149119,
    "Azure": 4294967280,
    "Beige": 4292670965,
    "Bisque": 4291093759,
    "BlanchedAlmond": 4291685375,
    "Blue": 4294901760,
    "BlueViolet": 4293012362,
    "Brown": 4280953509,
    "BurlyWood": 4287084766,
    "CadetBlue": 4288716383,
    "Chartreuse": 4278255487,
    "Chocolate": 4280183250,
    "Coral": 4283465727,
    "Cornsilk": 4292671743,
    "Crimson": 4282127580,
    "Cyan": 4294967040,
    "DarkBlue": 4287299584,
    "DarkCyan": 4287335168,
    "DarkGoldenrod": 4278945464,
    "DarkGray": 4289309097,
    "DarkGreen": 4278215680,
    "DarkKhaki": 4285249469,
    "DarkMagenta": 4287299723,
    "DarkOliveGreen": 4281297749,
    "DarkOrange": 4278226175,
    "DarkOrchid": 4291572377,
    "DarkRed": 4278190219,
    "DarkSalmon": 4286224105,
    "DarkSeaGreen": 4287347855,
    "DarkSlateBlue": 4287315272,
    "DarkSlateGray": 4283387695,
    "DarkTurquoise": 4291939840,
    "DarkViolet": 4292018324,
    "DeepPink": 4287829247,
    "DeepSkyBlue": 4294950656,
    "DimGray": 4285098345,
    "DodgerBlue": 4294938654,
    "Firebrick": 4280427186,
    "FloralWhite": 4293982975,
    "ForestGreen": 4280453922,
    "Fuchsia": 4294902015,
    "Gainsboro": 4292664540,
    "GhostWhite": 4294965496,
    "Gold": 4278245375,
    "Goldenrod": 4280329690,
    "Gray": 4286611584,
    "Green": 4278222848,
    "GreenYellow": 4281335725,
    "Honeydew": 4293984240,
    "HotPink": 4290013695,
    "IndianRed": 4284243149,
    "Indigo": 4286709835,
    "Ivory": 4293984255,
    "Khaki": 4287424240,
    "Lavender": 4294633190,
    "LavenderBlush": 4294308095,
    "LawnGreen": 4278254716,
    "LemonChiffon": 4291689215,
    "LightBlue": 4293318829,
    "LightCoral": 4286611696,
    "LightCyan": 4294967264,
    "LightGoldenrodYellow": 4292016890,
    "LightGreen": 4287688336,
    "LightGray": 4292072403,
    "LightPink": 4290885375,
    "LightSalmon": 4286226687,
    "LightSeaGreen": 4289376800,
    "LightSkyBlue": 4294626951,
    "LightSlateGray": 4288252023,
    "LightSteelBlue": 4292789424,
    "LightYellow": 4292935679,
    "Lime": 4278255360,
    "LimeGreen": 4281519410,
    "Linen": 4293325050,
    "Magenta": 4294902015,
    "Maroon": 4278190208,
    "MediumAquamarine": 4289383782,
    "MediumBlue": 4291624960,
    "MediumOrchid": 4292040122,
    "MediumPurple": 4292571283,
    "MediumSeaGreen": 4285641532,
    "MediumSlateBlue": 4293814395,
    "MediumSpringGreen": 4288346624,
    "MediumTurquoise": 4291613000,
    "MediumVioletRed": 4286911943,
    "MidnightBlue": 4285536537,
    "MintCream": 4294639605,
    "MistyRose": 4292994303,
    "Moccasin": 4290110719,
    "NavajoWhite": 4289584895,
    "Navy": 4286578688,
    "OldLace": 4293326333,
    "Olive": 4278222976,
    "OliveDrab": 4280520299,
    "Orange": 4278232575,
    "OrangeRed": 4278207999,
    "Orchid": 4292243674,
    "PaleGoldenrod": 4289390830,
    "PaleGreen": 4288215960,
    "PaleTurquoise": 4293848751,
    "PaleVioletRed": 4287852763,
    "PapayaWhip": 4292210687,
    "PeachPuff": 4290370303,
    "Peru": 4282353101,
    "Pink": 4291543295,
    "Plum": 4292714717,
    "PowderBlue": 4293320880,
    "Purple": 4286578816,
    "Red": 4278190335,
    "RosyBrown": 4287598524,
    "RoyalBlue": 4292962625,
    "SaddleBrown": 4279453067,
    "Salmon": 4285694202,
    "SandyBrown": 4284523764,
    "SeaGreen": 4283927342,
    "SeaShell": 4293850623,
    "Sienna": 4281160352,
    "Silver": 4290822336,
    "SkyBlue": 4293643911,
    "SlateBlue": 4291648106,
    "SlateGray": 4287660144,
    "Snow": 4294638335,
    "SpringGreen": 4286578432,
    "SteelBlue": 4290019910,
    "Tan": 4287411410,
    "Teal": 4286611456,
    "Thistle": 4292394968,
    "Tomato": 4282868735,
    "Turquoise": 4291878976,
    "Violet": 4293821166,
    "Wheat": 4289978101,
    "WhiteSmoke": 4294309365,
    "Yellow": 4278255615,
    "YellowGreen": 4281519514,
}
for _name, _packed in _NAMED_COLOR_PACKED.items():
    setattr(Color, _name, _ColorProperty(_packed))

# XNA's Transparent is deliberately white with zero alpha, not packed zero.
Color.Transparent = _ColorProperty(0x00FFFFFF)
Color.Black = _ColorProperty(0xFF000000)
Color.CornflowerBlue = _ColorProperty(0xFFED9564)
Color.White = _ColorProperty(0xFFFFFFFF)


class Point:
    __slots__ = ("_x", "_y")

    def __init__(self, *args: object) -> None:
        if not args:
            x, y = 0, 0
        elif len(args) == 2:
            x, y = args
        else:
            raise TypeError("Point expects zero arguments or x, y")
        self.X, self.Y = x, y

    @property
    def X(self) -> int: return self._x
    @X.setter
    def X(self, value: int) -> None: self._x = int32(value, name="X")
    @property
    def Y(self) -> int: return self._y
    @Y.setter
    def Y(self, value: int) -> None: self._y = int32(value, name="Y")
    @classproperty
    def Zero(cls) -> "Point": return cls(0, 0)
    def __copy__(self) -> "Point": return Point(self.X, self.Y)
    __deepcopy__ = lambda self, memo: self.__copy__()
    def __eq__(self, other: object) -> bool: return isinstance(other, Point) and self.X == other.X and self.Y == other.Y
    def __hash__(self) -> int: return self.GetHashCode()
    def Equals(self, other: object) -> bool: return self == other
    def GetHashCode(self) -> int: return hash32_sum(self.X,self.Y)
    def ToString(self) -> str: return f"{{X:{self.X} Y:{self.Y}}}"
    __str__ = ToString
    def __repr__(self) -> str: return f"Point({self.X}, {self.Y})"


class Rectangle:
    __slots__ = ("_x", "_y", "_width", "_height")

    def __init__(self, *args: object) -> None:
        if not args:
            x, y, width, height = 0, 0, 0, 0
        elif len(args) == 4:
            x, y, width, height = args
        else:
            raise TypeError("Rectangle expects zero arguments or x, y, width, height")
        self.X, self.Y, self.Width, self.Height = x, y, width, height

    def _component(name: str):
        private = "_" + name.lower()
        return property(lambda self: getattr(self, private), lambda self, value: setattr(self, private, int32(value, name=name)))
    X = _component("X"); Y = _component("Y"); Width = _component("Width"); Height = _component("Height")
    @property
    def Left(self) -> int: return self.X
    @property
    def Right(self) -> int: return self.X + self.Width
    @property
    def Top(self) -> int: return self.Y
    @property
    def Bottom(self) -> int: return self.Y + self.Height
    @property
    def Location(self) -> Point: return Point(self.X, self.Y)
    @Location.setter
    def Location(self, value: Point) -> None: self.X, self.Y = value.X, value.Y
    @property
    def Center(self) -> Point: return Point(self.X + self.Width // 2, self.Y + self.Height // 2)
    @classproperty
    def Empty(cls) -> "Rectangle": return cls()
    @property
    def IsEmpty(self) -> bool: return self.X == 0 and self.Y == 0 and self.Width == 0 and self.Height == 0
    def Offset(self, *args: object) -> None:
        if len(args) == 1 and isinstance(args[0], Point): dx, dy = args[0].X, args[0].Y
        elif len(args) == 2: dx, dy = args
        else: raise TypeError("Offset expects Point or offsetX, offsetY")
        self.X, self.Y = int32(self.X + int32(dx)), int32(self.Y + int32(dy))
    def Inflate(self, horizontalAmount: int, verticalAmount: int) -> None:
        h, v = int32(horizontalAmount), int32(verticalAmount)
        self.X, self.Y = int32(self.X - h), int32(self.Y - v)
        self.Width, self.Height = int32(self.Width + h * 2), int32(self.Height + v * 2)
    def Contains(self, *args: object) -> bool:
        if len(args) == 2: x, y = int32(args[0]), int32(args[1])
        elif len(args) == 1 and isinstance(args[0], Point): x, y = args[0].X, args[0].Y
        elif len(args) == 1 and isinstance(args[0], Rectangle):
            value = args[0]
            return self.X <= value.X and value.Right <= self.Right and self.Y <= value.Y and value.Bottom <= self.Bottom
        else: raise TypeError("Contains expects x, y, Point, or Rectangle")
        return self.X <= x < self.Right and self.Y <= y < self.Bottom
    def Intersects(self, value: "Rectangle") -> bool:
        return value.Left < self.Right and self.Left < value.Right and value.Top < self.Bottom and self.Top < value.Bottom
    @staticmethod
    def Intersect(value1: "Rectangle", value2: "Rectangle") -> "Rectangle":
        left, top = max(value1.Left, value2.Left), max(value1.Top, value2.Top)
        right, bottom = min(value1.Right, value2.Right), min(value1.Bottom, value2.Bottom)
        return Rectangle(left, top, right - left, bottom - top) if right > left and bottom > top else Rectangle.Empty
    @staticmethod
    def Union(value1: "Rectangle", value2: "Rectangle") -> "Rectangle":
        left, top = min(value1.Left, value2.Left), min(value1.Top, value2.Top)
        right, bottom = max(value1.Right, value2.Right), max(value1.Bottom, value2.Bottom)
        return Rectangle(left, top, right - left, bottom - top)
    def __copy__(self): return Rectangle(self.X, self.Y, self.Width, self.Height)
    __deepcopy__ = lambda self, memo: self.__copy__()
    def __eq__(self, other: object) -> bool: return isinstance(other, Rectangle) and tuple(self) == tuple(other)
    def __hash__(self) -> int: return self.GetHashCode()
    def __iter__(self): return iter((self.X, self.Y, self.Width, self.Height))
    def Equals(self, other: object) -> bool: return self == other
    def GetHashCode(self) -> int: return hash32_sum(self.X,self.Y,self.Width,self.Height)
    def ToString(self) -> str: return f"{{X:{self.X} Y:{self.Y} Width:{self.Width} Height:{self.Height}}}"
    __str__ = ToString
    def __repr__(self) -> str: return f"Rectangle({self.X}, {self.Y}, {self.Width}, {self.Height})"


Color.__xna_arities__ = {"__init__": {0, 1, 3, 4}, "FromNonPremultiplied": {1, 4}}
Point.__xna_arities__ = {"__init__": {0, 2}}
Rectangle.__xna_arities__ = {"__init__": {0, 4}, "Offset": {1, 2}, "Contains": {1, 2}}
