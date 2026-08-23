"""Pure XNA Single-based math values.

Every public component is narrowed to binary32 on assignment and after each
primitive arithmetic operation.  This is intentional: Python's binary64 float
is not the XNA ``System.Single`` contract.
"""

from __future__ import annotations

import math
from typing import Any

from ._language import classproperty
from ._numeric import add32, div32, f32, hash32_sum, mul32, single_hash, sub32


class _dualmethod:
    def __init__(self, instance_function: Any, static_function: Any) -> None:
        self._instance_function = instance_function
        self._static_function = static_function

    def __get__(self, instance: object | None, owner: type | None = None) -> Any:
        if instance is None:
            return self._static_function
        return self._instance_function.__get__(instance, owner)


def _sqrt32(value: float) -> float:
    try:
        return f32(math.sqrt(value))
    except ValueError:
        return math.nan


def _acos32(value: float) -> float:
    try:
        return f32(math.acos(value))
    except ValueError:
        return math.nan


def _sin32(value: float) -> float:
    return f32(math.sin(f32(value)))


def _cos32(value: float) -> float:
    return f32(math.cos(f32(value)))


def _sum3(a: float, b: float, c: float) -> float:
    return add32(add32(a, b), c)


def _sum4(a: float, b: float, c: float, d: float) -> float:
    return add32(add32(add32(a, b), c), d)


def _quaternion_rotation_terms(rotation: "Quaternion") -> tuple[float, ...]:
    x2,y2,z2=add32(rotation.X,rotation.X),add32(rotation.Y,rotation.Y),add32(rotation.Z,rotation.Z)
    wx2,wy2,wz2=mul32(rotation.W,x2),mul32(rotation.W,y2),mul32(rotation.W,z2)
    xx2,xy2,xz2=mul32(rotation.X,x2),mul32(rotation.X,y2),mul32(rotation.X,z2)
    yy2,yz2,zz2=mul32(rotation.Y,y2),mul32(rotation.Y,z2),mul32(rotation.Z,z2)
    return (sub32(sub32(1,yy2),zz2),sub32(xy2,wz2),add32(xz2,wy2),
            add32(xy2,wz2),sub32(sub32(1,xx2),zz2),sub32(yz2,wx2),
            sub32(xz2,wy2),add32(yz2,wx2),sub32(sub32(1,xx2),yy2))


def _validate_transform_range(source: object, source_index: object, destination: object,
                              destination_index: object, length: object) -> tuple[int, int, int]:
    if not hasattr(source, "__len__") or not hasattr(source, "__getitem__"):
        raise TypeError("sourceArray must be a sequence")
    if not hasattr(destination, "__len__") or not hasattr(destination, "__setitem__"):
        raise TypeError("destinationArray must be a mutable sequence")
    from ._numeric import int32
    source_index = int32(source_index, name="sourceIndex")
    destination_index = int32(destination_index, name="destinationIndex")
    length = int32(length, name="length")
    if source_index + length > len(source) or destination_index + length > len(destination):
        raise ValueError("transform range exceeds an array boundary")
    # XNA's range helper does not reject a negative length: the following loop
    # simply performs no work. Negative indices only fail if an element would
    # actually be accessed (CLR arrays never wrap from the end as Python does).
    if length > 0 and (source_index < 0 or destination_index < 0):
        raise IndexError("transform array index is outside the array")
    return source_index, destination_index, length


class MathHelper:
    E = f32(2.71828175)
    Log2E = f32(1.442695)
    Log10E = f32(0.4342945)
    Pi = f32(3.14159274)
    TwoPi = f32(6.28318548)
    PiOver2 = f32(1.57079637)
    PiOver4 = f32(0.7853982)

    def __new__(cls) -> "MathHelper":
        raise TypeError("MathHelper is static")

    @staticmethod
    def ToRadians(degrees: float) -> float:
        return mul32(degrees, f32(0.0174532924))

    @staticmethod
    def ToDegrees(radians: float) -> float:
        return mul32(radians, f32(57.29578))

    @staticmethod
    def Distance(value1: float, value2: float) -> float:
        return abs(sub32(value1, value2))

    @staticmethod
    def Min(value1: float, value2: float) -> float:
        a, b = f32(value1), f32(value2)
        if math.isnan(a):
            return a
        return a if a < b else b

    @staticmethod
    def Max(value1: float, value2: float) -> float:
        a, b = f32(value1), f32(value2)
        if math.isnan(a):
            return a
        return a if a > b else b

    @staticmethod
    def Clamp(value: float, min: float, max: float) -> float:
        result, lower, upper = f32(value), f32(min), f32(max)
        if result > upper:
            result = upper
        if result < lower:
            result = lower
        return result

    @staticmethod
    def Lerp(value1: float, value2: float, amount: float) -> float:
        return add32(value1, mul32(sub32(value2, value1), amount))

    @staticmethod
    def Barycentric(value1: float, value2: float, value3: float, amount1: float, amount2: float) -> float:
        return add32(add32(value1, mul32(sub32(value2, value1), amount1)), mul32(sub32(value3, value1), amount2))

    @staticmethod
    def SmoothStep(value1: float, value2: float, amount: float) -> float:
        t = MathHelper.Clamp(amount, 0.0, 1.0)
        t = mul32(mul32(t, t), sub32(3.0, mul32(2.0, t)))
        return MathHelper.Lerp(value1, value2, t)

    @staticmethod
    def CatmullRom(value1: float, value2: float, value3: float, value4: float, amount: float) -> float:
        t = f32(amount)
        t2 = mul32(t, t)
        t3 = mul32(t, t2)
        quadratic = sub32(
            add32(sub32(mul32(2.0, value1), mul32(5.0, value2)), mul32(4.0, value3)),
            value4,
        )
        cubic = add32(
            sub32(add32(f32(-f32(value1)), mul32(3.0, value2)), mul32(3.0, value3)),
            value4,
        )
        inner = add32(mul32(2.0, value2), mul32(add32(f32(-f32(value1)), value3), t))
        inner = add32(inner, mul32(quadratic, t2))
        inner = add32(inner, mul32(cubic, t3))
        return mul32(0.5, inner)

    @staticmethod
    def Hermite(value1: float, tangent1: float, value2: float, tangent2: float, amount: float) -> float:
        t = f32(amount)
        t2 = mul32(t, t)
        t3 = mul32(t, t2)
        h1 = add32(sub32(mul32(2.0, t3), mul32(3.0, t2)), 1.0)
        h3 = add32(mul32(-2.0, t3), mul32(3.0, t2))
        h2 = add32(sub32(t3, mul32(2.0, t2)), t)
        h4 = sub32(t3, t2)
        result = add32(mul32(value1, h1), mul32(value2, h3))
        result = add32(result, mul32(tangent1, h2))
        return add32(result, mul32(tangent2, h4))

    @staticmethod
    def WrapAngle(angle: float) -> float:
        try:
            value = f32(math.remainder(f32(angle), MathHelper.TwoPi))
        except ValueError:
            return math.nan
        if value <= -MathHelper.Pi:
            value = add32(value, MathHelper.TwoPi)
        elif value > MathHelper.Pi:
            value = sub32(value, MathHelper.TwoPi)
        return value


class _VectorValue:
    __slots__ = ()

    def __copy__(self) -> Any:
        return type(self)(*(getattr(self, name) for name in self._component_names))

    __deepcopy__ = lambda self, memo: self.__copy__()

    def __iter__(self):
        return iter(getattr(self, name) for name in self._component_names)

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and all(getattr(self, name) == getattr(other, name) for name in self._component_names)

    def __hash__(self) -> int:
        return self.GetHashCode()

    def Equals(self, other: object) -> bool:
        return self == other

    def GetHashCode(self) -> int:
        return hash32_sum(*(single_hash(getattr(self, name)) for name in self._component_names))

    def ToString(self) -> str:
        return "{" + " ".join(f"{name}:{getattr(self, name):g}" for name in self._component_names) + "}"

    def __repr__(self) -> str:
        values = ", ".join(repr(getattr(self, name)) for name in self._component_names)
        return f"{type(self).__name__}({values})"

    def __str__(self) -> str:
        return self.ToString()


def _vector_value(cls):
    for name in ("__copy__", "__deepcopy__", "__iter__", "__eq__", "__hash__",
                 "Equals", "GetHashCode", "ToString", "__repr__", "__str__"):
        setattr(cls, name, _VectorValue.__dict__[name])
    return cls


@_vector_value
class Vector2:
    __slots__ = ("_x", "_y")
    _component_names = ("X", "Y")

    def __init__(self, *args: object) -> None:
        if not args:
            x = y = 0.0
        elif len(args) == 1:
            x = y = args[0]
        elif len(args) == 2:
            x, y = args
        else:
            raise TypeError("Vector2 expects (), value, or x, y")
        self.X, self.Y = x, y

    @property
    def X(self) -> float:
        return self._x

    @X.setter
    def X(self, value: float) -> None:
        self._x = f32(value)

    @property
    def Y(self) -> float:
        return self._y

    @Y.setter
    def Y(self, value: float) -> None:
        self._y = f32(value)

    @classproperty
    def Zero(cls) -> "Vector2":
        return cls(0.0)

    @classproperty
    def One(cls) -> "Vector2":
        return cls(1.0)

    @classproperty
    def UnitX(cls) -> "Vector2":
        return cls(1.0, 0.0)

    @classproperty
    def UnitY(cls) -> "Vector2":
        return cls(0.0, 1.0)

    def LengthSquared(self) -> float:
        return add32(mul32(self.X, self.X), mul32(self.Y, self.Y))

    def Length(self) -> float:
        return _sqrt32(self.LengthSquared())

    def _normalize_instance(self) -> None:
        factor = div32(1.0, self.Length())
        self.X, self.Y = mul32(self.X, factor), mul32(self.Y, factor)

    @staticmethod
    def _normalize_static(value: "Vector2") -> "Vector2":
        result = Vector2(value.X, value.Y)
        result._normalize_instance()
        return result

    Normalize = _dualmethod(_normalize_instance, _normalize_static)

    @staticmethod
    def Distance(value1: "Vector2", value2: "Vector2") -> float:
        return (value1 - value2).Length()

    @staticmethod
    def DistanceSquared(value1: "Vector2", value2: "Vector2") -> float:
        return (value1 - value2).LengthSquared()

    @staticmethod
    def Dot(value1: "Vector2", value2: "Vector2") -> float:
        return add32(mul32(value1.X, value2.X), mul32(value1.Y, value2.Y))

    @staticmethod
    def Reflect(vector: "Vector2", normal: "Vector2") -> "Vector2":
        scale = mul32(2.0, Vector2.Dot(vector, normal))
        return vector - normal * scale

    @staticmethod
    def Min(value1: "Vector2", value2: "Vector2") -> "Vector2":
        return Vector2(value1.X if value1.X < value2.X else value2.X,
                       value1.Y if value1.Y < value2.Y else value2.Y)

    @staticmethod
    def Max(value1: "Vector2", value2: "Vector2") -> "Vector2":
        return Vector2(value1.X if value1.X > value2.X else value2.X,
                       value1.Y if value1.Y > value2.Y else value2.Y)

    @staticmethod
    def Clamp(value: "Vector2", min: "Vector2", max: "Vector2") -> "Vector2":
        return Vector2(MathHelper.Clamp(value.X, min.X, max.X), MathHelper.Clamp(value.Y, min.Y, max.Y))

    @staticmethod
    def Lerp(value1: "Vector2", value2: "Vector2", amount: float) -> "Vector2":
        return Vector2(MathHelper.Lerp(value1.X, value2.X, amount), MathHelper.Lerp(value1.Y, value2.Y, amount))

    @staticmethod
    def Barycentric(value1: "Vector2", value2: "Vector2", value3: "Vector2", amount1: float, amount2: float) -> "Vector2":
        return Vector2(*(MathHelper.Barycentric(a, b, c, amount1, amount2) for a, b, c in zip(value1, value2, value3)))

    @staticmethod
    def SmoothStep(value1: "Vector2", value2: "Vector2", amount: float) -> "Vector2":
        return Vector2(*(MathHelper.SmoothStep(a, b, amount) for a, b in zip(value1, value2)))

    @staticmethod
    def CatmullRom(value1: "Vector2", value2: "Vector2", value3: "Vector2", value4: "Vector2", amount: float) -> "Vector2":
        return Vector2(*(MathHelper.CatmullRom(a, b, c, d, amount) for a, b, c, d in zip(value1, value2, value3, value4)))

    @staticmethod
    def Hermite(value1: "Vector2", tangent1: "Vector2", value2: "Vector2", tangent2: "Vector2", amount: float) -> "Vector2":
        return Vector2(*(MathHelper.Hermite(a, b, c, d, amount) for a, b, c, d in zip(value1, tangent1, value2, tangent2)))

    @staticmethod
    def Negate(value: "Vector2") -> "Vector2":
        return -value

    @staticmethod
    def Add(value1: "Vector2", value2: "Vector2") -> "Vector2":
        return value1 + value2

    @staticmethod
    def Subtract(value1: "Vector2", value2: "Vector2") -> "Vector2":
        return value1 - value2

    @staticmethod
    def Multiply(value1: "Vector2", value2: "Vector2 | float") -> "Vector2":
        return value1 * value2

    @staticmethod
    def Divide(value1: "Vector2", value2: "Vector2 | float") -> "Vector2":
        return value1 / value2

    @staticmethod
    def _transform_one(value: "Vector2", transform: object, *, normal: bool = False) -> "Vector2":
        if not isinstance(value, Vector2):
            raise TypeError("value must be Vector2")
        if isinstance(transform, Matrix):
            x = add32(mul32(value.X, transform.M11), mul32(value.Y, transform.M21))
            y = add32(mul32(value.X, transform.M12), mul32(value.Y, transform.M22))
            if not normal:
                x, y = add32(x, transform.M41), add32(y, transform.M42)
            return Vector2(x, y)
        if normal:
            raise TypeError("TransformNormal expects a Matrix")
        if isinstance(transform, Quaternion):
            m11,m12,_m13,m21,m22,_m23,_m31,_m32,_m33=_quaternion_rotation_terms(transform)
            return Vector2(add32(mul32(value.X,m11),mul32(value.Y,m12)),
                           add32(mul32(value.X,m21),mul32(value.Y,m22)))
        raise TypeError("transform must be Matrix or Quaternion")

    @staticmethod
    def _transform_dispatch(args: tuple[object, ...], *, normal: bool = False):
        if len(args) == 2 and isinstance(args[0], Vector2):
            return Vector2._transform_one(args[0], args[1], normal=normal)
        if len(args) == 3:
            source, transform, destination = args
            source_index, destination_index, length = _validate_transform_range(
                source, 0, destination, 0, len(source) if hasattr(source, "__len__") else 0
            )
        elif len(args) == 6:
            source, source_index, transform, destination, destination_index, length = args
            source_index, destination_index, length = _validate_transform_range(
                source, source_index, destination, destination_index, length
            )
        else:
            raise TypeError("no matching XNA transform overload")
        for index in range(length):
            value = source[source_index + index]
            destination[destination_index + index] = Vector2._transform_one(value, transform, normal=normal)
        return None

    @staticmethod
    def Transform(*args: object):
        return Vector2._transform_dispatch(args)

    @staticmethod
    def TransformNormal(*args: object):
        return Vector2._transform_dispatch(args, normal=True)

    def __neg__(self) -> "Vector2":
        return Vector2(f32(-self.X), f32(-self.Y))

    def __add__(self, other: "Vector2") -> "Vector2":
        if not isinstance(other, Vector2): return NotImplemented
        return Vector2(add32(self.X, other.X), add32(self.Y, other.Y))

    def __sub__(self, other: "Vector2") -> "Vector2":
        if not isinstance(other, Vector2): return NotImplemented
        return Vector2(sub32(self.X, other.X), sub32(self.Y, other.Y))

    def __mul__(self, other: "Vector2 | float") -> "Vector2":
        if isinstance(other, Vector2): return Vector2(mul32(self.X, other.X), mul32(self.Y, other.Y))
        if isinstance(other, (int, float)): return Vector2(mul32(self.X, other), mul32(self.Y, other))
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other: "Vector2 | float") -> "Vector2":
        if isinstance(other, Vector2): return Vector2(div32(self.X, other.X), div32(self.Y, other.Y))
        if isinstance(other, (int, float)):
            factor=div32(1,other);return Vector2(mul32(self.X,factor),mul32(self.Y,factor))
        return NotImplemented


@_vector_value
class Vector3:
    __slots__ = ("_x", "_y", "_z")
    _component_names = ("X", "Y", "Z")

    def __init__(self, *args: object) -> None:
        if not args:
            values = (0.0, 0.0, 0.0)
        elif len(args) == 1:
            values = (args[0], args[0], args[0])
        elif len(args) == 2 and isinstance(args[0], Vector2):
            values = (args[0].X, args[0].Y, args[1])
        elif len(args) == 3:
            values = args
        else:
            raise TypeError("Vector3 expects (), value, Vector2 and z, or x, y, z")
        self.X, self.Y, self.Z = values

    def _component(name: str):
        private = "_" + name.lower()
        def get(self): return getattr(self, private)
        def set(self, value): setattr(self, private, f32(value))
        return property(get, set)

    X = _component("X")
    Y = _component("Y")
    Z = _component("Z")

    @classproperty
    def Zero(cls): return cls(0.0)
    @classproperty
    def One(cls): return cls(1.0)
    @classproperty
    def UnitX(cls): return cls(1.0, 0.0, 0.0)
    @classproperty
    def UnitY(cls): return cls(0.0, 1.0, 0.0)
    @classproperty
    def UnitZ(cls): return cls(0.0, 0.0, 1.0)
    @classproperty
    def Up(cls): return cls(0.0, 1.0, 0.0)
    @classproperty
    def Down(cls): return cls(0.0, -1.0, 0.0)
    @classproperty
    def Right(cls): return cls(1.0, 0.0, 0.0)
    @classproperty
    def Left(cls): return cls(-1.0, 0.0, 0.0)
    @classproperty
    def Forward(cls): return cls(0.0, 0.0, -1.0)
    @classproperty
    def Backward(cls): return cls(0.0, 0.0, 1.0)

    def LengthSquared(self): return add32(add32(mul32(self.X,self.X),mul32(self.Y,self.Y)),mul32(self.Z,self.Z))
    def Length(self): return _sqrt32(self.LengthSquared())
    def _normalize_instance(self):
        factor=div32(1.0,self.Length()); self.X,self.Y,self.Z=mul32(self.X,factor),mul32(self.Y,factor),mul32(self.Z,factor)
    @staticmethod
    def _normalize_static(value):
        result=Vector3(value.X,value.Y,value.Z); result._normalize_instance(); return result
    Normalize=_dualmethod(_normalize_instance,_normalize_static)
    @staticmethod
    def Distance(a,b): return (a-b).Length()
    @staticmethod
    def DistanceSquared(a,b): return (a-b).LengthSquared()
    @staticmethod
    def Dot(a,b): return add32(add32(mul32(a.X,b.X),mul32(a.Y,b.Y)),mul32(a.Z,b.Z))
    @staticmethod
    def Cross(a,b): return Vector3(sub32(mul32(a.Y,b.Z),mul32(a.Z,b.Y)),sub32(mul32(a.Z,b.X),mul32(a.X,b.Z)),sub32(mul32(a.X,b.Y),mul32(a.Y,b.X)))
    @staticmethod
    def Reflect(v,n): return v-n*mul32(2.0,Vector3.Dot(v,n))
    @staticmethod
    def Min(a,b): return Vector3(*(x if x<y else y for x,y in zip(a,b)))
    @staticmethod
    def Max(a,b): return Vector3(*(x if x>y else y for x,y in zip(a,b)))
    @staticmethod
    def Clamp(v,minimum,maximum): return Vector3(*(MathHelper.Clamp(x,y,z) for x,y,z in zip(v,minimum,maximum)))
    @staticmethod
    def Lerp(a,b,t): return Vector3(*(MathHelper.Lerp(x,y,t) for x,y in zip(a,b)))
    @staticmethod
    def Barycentric(a,b,c,t,u): return Vector3(*(MathHelper.Barycentric(x,y,z,t,u) for x,y,z in zip(a,b,c)))
    @staticmethod
    def SmoothStep(a,b,t): return Vector3(*(MathHelper.SmoothStep(x,y,t) for x,y in zip(a,b)))
    @staticmethod
    def CatmullRom(a,b,c,d,t): return Vector3(*(MathHelper.CatmullRom(w,x,y,z,t) for w,x,y,z in zip(a,b,c,d)))
    @staticmethod
    def Hermite(a,b,c,d,t): return Vector3(*(MathHelper.Hermite(w,x,y,z,t) for w,x,y,z in zip(a,b,c,d)))
    Negate=staticmethod(lambda v:-v); Add=staticmethod(lambda a,b:a+b); Subtract=staticmethod(lambda a,b:a-b)
    Multiply=staticmethod(lambda a,b:a*b); Divide=staticmethod(lambda a,b:a/b)
    @staticmethod
    def _transform_one(value, transform, *, normal=False):
        if not isinstance(value,Vector3): raise TypeError("value must be Vector3")
        if isinstance(transform,Matrix):
            x=_sum3(mul32(value.X,transform.M11),mul32(value.Y,transform.M21),mul32(value.Z,transform.M31))
            y=_sum3(mul32(value.X,transform.M12),mul32(value.Y,transform.M22),mul32(value.Z,transform.M32))
            z=_sum3(mul32(value.X,transform.M13),mul32(value.Y,transform.M23),mul32(value.Z,transform.M33))
            if not normal:x,y,z=add32(x,transform.M41),add32(y,transform.M42),add32(z,transform.M43)
            return Vector3(x,y,z)
        if normal: raise TypeError("TransformNormal expects a Matrix")
        if isinstance(transform,Quaternion):
            m11,m12,m13,m21,m22,m23,m31,m32,m33=_quaternion_rotation_terms(transform)
            return Vector3(_sum3(mul32(value.X,m11),mul32(value.Y,m12),mul32(value.Z,m13)),
                           _sum3(mul32(value.X,m21),mul32(value.Y,m22),mul32(value.Z,m23)),
                           _sum3(mul32(value.X,m31),mul32(value.Y,m32),mul32(value.Z,m33)))
        raise TypeError("transform must be Matrix or Quaternion")
    @staticmethod
    def _transform_dispatch(args,normal=False):
        if len(args)==2 and isinstance(args[0],Vector3):return Vector3._transform_one(args[0],args[1],normal=normal)
        if len(args)==3:
            source,transform,destination=args
            si,di,length=_validate_transform_range(source,0,destination,0,len(source) if hasattr(source,"__len__") else 0)
        elif len(args)==6:
            source,si,transform,destination,di,length=args
            si,di,length=_validate_transform_range(source,si,destination,di,length)
        else:raise TypeError("no matching XNA transform overload")
        for index in range(length):destination[di+index]=Vector3._transform_one(source[si+index],transform,normal=normal)
        return None
    @staticmethod
    def Transform(*args):return Vector3._transform_dispatch(args)
    @staticmethod
    def TransformNormal(*args):return Vector3._transform_dispatch(args,normal=True)
    def __neg__(self): return Vector3(f32(-self.X),f32(-self.Y),f32(-self.Z))
    def __add__(self,o): return Vector3(*(add32(a,b) for a,b in zip(self,o))) if isinstance(o,Vector3) else NotImplemented
    def __sub__(self,o): return Vector3(*(sub32(a,b) for a,b in zip(self,o))) if isinstance(o,Vector3) else NotImplemented
    def __mul__(self,o):
        if isinstance(o,Vector3): return Vector3(*(mul32(a,b) for a,b in zip(self,o)))
        if isinstance(o,(int,float)): return Vector3(*(mul32(a,o) for a in self))
        return NotImplemented
    __rmul__=__mul__
    def __truediv__(self,o):
        if isinstance(o,Vector3): return Vector3(*(div32(a,b) for a,b in zip(self,o)))
        if isinstance(o,(int,float)):
            factor=div32(1,o);return Vector3(*(mul32(a,factor) for a in self))
        return NotImplemented


@_vector_value
class Vector4:
    __slots__=("_x","_y","_z","_w")
    _component_names=("X","Y","Z","W")
    def __init__(self,*args:object):
        if not args: values=(0.0,0.0,0.0,0.0)
        elif len(args)==1: values=(args[0],)*4
        elif len(args)==2 and isinstance(args[0],Vector3): values=(args[0].X,args[0].Y,args[0].Z,args[1])
        elif len(args)==3 and isinstance(args[0],Vector2): values=(args[0].X,args[0].Y,args[1],args[2])
        elif len(args)==4: values=args
        else: raise TypeError("no matching XNA Vector4 constructor")
        self.X,self.Y,self.Z,self.W=values
    def _component(name):
        p="_"+name.lower(); return property(lambda s:getattr(s,p),lambda s,v:setattr(s,p,f32(v)))
    X=_component("X");Y=_component("Y");Z=_component("Z");W=_component("W")
    @classproperty
    def Zero(cls): return cls(0.0)
    @classproperty
    def One(cls): return cls(1.0)
    @classproperty
    def UnitX(cls): return cls(1,0,0,0)
    @classproperty
    def UnitY(cls): return cls(0,1,0,0)
    @classproperty
    def UnitZ(cls): return cls(0,0,1,0)
    @classproperty
    def UnitW(cls): return cls(0,0,0,1)
    def LengthSquared(self): return _sum4(mul32(self.X,self.X),mul32(self.Y,self.Y),mul32(self.Z,self.Z),mul32(self.W,self.W))
    def Length(self): return _sqrt32(self.LengthSquared())
    def _normalize_instance(self):
        f=div32(1,self.Length()); self.X,self.Y,self.Z,self.W=*(mul32(v,f) for v in self),
    @staticmethod
    def _normalize_static(v): r=Vector4(*v);r._normalize_instance();return r
    Normalize=_dualmethod(_normalize_instance,_normalize_static)
    @staticmethod
    def Distance(a,b): return (a-b).Length()
    @staticmethod
    def DistanceSquared(a,b): return (a-b).LengthSquared()
    @staticmethod
    def Dot(a,b): return _sum4(mul32(a.X,b.X),mul32(a.Y,b.Y),mul32(a.Z,b.Z),mul32(a.W,b.W))
    @staticmethod
    def Min(a,b): return Vector4(*(x if x<y else y for x,y in zip(a,b)))
    @staticmethod
    def Max(a,b): return Vector4(*(x if x>y else y for x,y in zip(a,b)))
    @staticmethod
    def Clamp(v,mn,mx): return Vector4(*(MathHelper.Clamp(x,y,z) for x,y,z in zip(v,mn,mx)))
    @staticmethod
    def Lerp(a,b,t): return Vector4(*(MathHelper.Lerp(x,y,t) for x,y in zip(a,b)))
    @staticmethod
    def SmoothStep(a,b,t): return Vector4(*(MathHelper.SmoothStep(x,y,t) for x,y in zip(a,b)))
    @staticmethod
    def Barycentric(a,b,c,t,u): return Vector4(*(MathHelper.Barycentric(x,y,z,t,u) for x,y,z in zip(a,b,c)))
    @staticmethod
    def CatmullRom(a,b,c,d,t): return Vector4(*(MathHelper.CatmullRom(w,x,y,z,t) for w,x,y,z in zip(a,b,c,d)))
    @staticmethod
    def Hermite(a,b,c,d,t): return Vector4(*(MathHelper.Hermite(w,x,y,z,t) for w,x,y,z in zip(a,b,c,d)))
    @staticmethod
    def _transform_one(value,transform):
        if isinstance(transform,Quaternion):
            if isinstance(value,Vector2):
                result=Vector3._transform_one(Vector3(value.X,value.Y,0),transform);return Vector4(result,1)
            if isinstance(value,Vector3):
                result=Vector3._transform_one(value,transform);return Vector4(result,1)
            if isinstance(value,Vector4):
                result=Vector3._transform_one(Vector3(value.X,value.Y,value.Z),transform)
                return Vector4(result,value.W)
            raise TypeError("value must be Vector2, Vector3, or Vector4")
        if not isinstance(transform,Matrix):raise TypeError("transform must be Matrix or Quaternion")
        if isinstance(value,Vector2): values=(value.X,value.Y,0.0,1.0)
        elif isinstance(value,Vector3): values=(value.X,value.Y,value.Z,1.0)
        elif isinstance(value,Vector4): values=tuple(value)
        else: raise TypeError("value must be Vector2, Vector3, or Vector4")
        return Vector4(*(_sum4(*(mul32(values[row-1],getattr(transform,f"M{row}{column}")) for row in range(1,5))) for column in range(1,5)))
    @staticmethod
    def Transform(*args):
        if len(args)==2 and isinstance(args[0],(Vector2,Vector3,Vector4)):return Vector4._transform_one(args[0],args[1])
        if len(args)==3:
            source,transform,destination=args
            si,di,length=_validate_transform_range(source,0,destination,0,len(source) if hasattr(source,"__len__") else 0)
        elif len(args)==6:
            source,si,transform,destination,di,length=args
            si,di,length=_validate_transform_range(source,si,destination,di,length)
        else:raise TypeError("no matching XNA Vector4.Transform overload")
        for index in range(length):destination[di+index]=Vector4._transform_one(source[si+index],transform)
        return None
    Negate=staticmethod(lambda v:-v);Add=staticmethod(lambda a,b:a+b);Subtract=staticmethod(lambda a,b:a-b);Multiply=staticmethod(lambda a,b:a*b);Divide=staticmethod(lambda a,b:a/b)
    def __neg__(self): return Vector4(*(f32(-v) for v in self))
    def __add__(self,o): return Vector4(*(add32(a,b) for a,b in zip(self,o))) if isinstance(o,Vector4) else NotImplemented
    def __sub__(self,o): return Vector4(*(sub32(a,b) for a,b in zip(self,o))) if isinstance(o,Vector4) else NotImplemented
    def __mul__(self,o):
        if isinstance(o,Vector4): return Vector4(*(mul32(a,b) for a,b in zip(self,o)))
        if isinstance(o,(int,float)): return Vector4(*(mul32(a,o) for a in self))
        return NotImplemented
    __rmul__=__mul__
    def __truediv__(self,o):
        if isinstance(o,Vector4): return Vector4(*(div32(a,b) for a,b in zip(self,o)))
        if isinstance(o,(int,float)):
            factor=div32(1,o);return Vector4(*(mul32(a,factor) for a in self))
        return NotImplemented


@_vector_value
class Quaternion:
    __slots__=("_x","_y","_z","_w")
    _component_names=("X","Y","Z","W")
    def __init__(self,*args:object):
        if not args: values=(0.0,0.0,0.0,0.0)
        elif len(args)==2 and isinstance(args[0],Vector3): values=(args[0].X,args[0].Y,args[0].Z,args[1])
        elif len(args)==4: values=args
        else: raise TypeError("Quaternion expects (), Vector3 and scalarPart, or x, y, z, w")
        self.X,self.Y,self.Z,self.W=values
    def _component(name):
        p="_"+name.lower();return property(lambda s:getattr(s,p),lambda s,v:setattr(s,p,f32(v)))
    X=_component("X");Y=_component("Y");Z=_component("Z");W=_component("W")
    @classproperty
    def Identity(cls): return cls(0,0,0,1)
    def LengthSquared(self): return Vector4(self.X,self.Y,self.Z,self.W).LengthSquared()
    def Length(self): return _sqrt32(self.LengthSquared())
    def _normalize_instance(self):
        f=div32(1,self.Length()); self.X,self.Y,self.Z,self.W=*(mul32(v,f) for v in self),
    @staticmethod
    def _normalize_static(v): r=Quaternion(*v);r._normalize_instance();return r
    Normalize=_dualmethod(_normalize_instance,_normalize_static)
    def _conjugate_instance(self): self.X,self.Y,self.Z=f32(-self.X),f32(-self.Y),f32(-self.Z)
    @staticmethod
    def _conjugate_static(v): return Quaternion(-v.X,-v.Y,-v.Z,v.W)
    Conjugate=_dualmethod(_conjugate_instance,_conjugate_static)
    @staticmethod
    def Dot(a,b): return Vector4.Dot(Vector4(*a),Vector4(*b))
    @staticmethod
    def Inverse(q):
        inv=div32(1,q.LengthSquared()); return Quaternion(mul32(-q.X,inv),mul32(-q.Y,inv),mul32(-q.Z,inv),mul32(q.W,inv))
    @staticmethod
    def CreateFromAxisAngle(axis,angle):
        half=mul32(angle,0.5);s=_sin32(half);return Quaternion(mul32(axis.X,s),mul32(axis.Y,s),mul32(axis.Z,s),_cos32(half))
    @staticmethod
    def CreateFromRotationMatrix(matrix):
        if not isinstance(matrix,Matrix): raise TypeError("matrix must be Matrix")
        trace=add32(add32(matrix.M11,matrix.M22),matrix.M33)
        if trace>0:
            root=_sqrt32(add32(trace,1));factor=div32(0.5,root)
            return Quaternion(mul32(sub32(matrix.M23,matrix.M32),factor),mul32(sub32(matrix.M31,matrix.M13),factor),mul32(sub32(matrix.M12,matrix.M21),factor),mul32(root,0.5))
        if matrix.M11>=matrix.M22 and matrix.M11>=matrix.M33:
            root=_sqrt32(sub32(sub32(add32(1,matrix.M11),matrix.M22),matrix.M33));factor=div32(0.5,root)
            return Quaternion(mul32(0.5,root),mul32(add32(matrix.M12,matrix.M21),factor),mul32(add32(matrix.M13,matrix.M31),factor),mul32(sub32(matrix.M23,matrix.M32),factor))
        if matrix.M22>matrix.M33:
            root=_sqrt32(sub32(sub32(add32(1,matrix.M22),matrix.M11),matrix.M33));factor=div32(0.5,root)
            return Quaternion(mul32(add32(matrix.M21,matrix.M12),factor),mul32(0.5,root),mul32(add32(matrix.M32,matrix.M23),factor),mul32(sub32(matrix.M31,matrix.M13),factor))
        root=_sqrt32(sub32(sub32(add32(1,matrix.M33),matrix.M11),matrix.M22));factor=div32(0.5,root)
        return Quaternion(mul32(add32(matrix.M31,matrix.M13),factor),mul32(add32(matrix.M32,matrix.M23),factor),mul32(0.5,root),mul32(sub32(matrix.M12,matrix.M21),factor))
    @staticmethod
    def CreateFromYawPitchRoll(yaw,pitch,roll):
        half_roll=mul32(roll,0.5);sr,cr=_sin32(half_roll),_cos32(half_roll)
        half_pitch=mul32(pitch,0.5);sp,cp=_sin32(half_pitch),_cos32(half_pitch)
        half_yaw=mul32(yaw,0.5);sy,cy=_sin32(half_yaw),_cos32(half_yaw)
        return Quaternion(add32(mul32(mul32(cy,sp),cr),mul32(mul32(sy,cp),sr)),sub32(mul32(mul32(sy,cp),cr),mul32(mul32(cy,sp),sr)),sub32(mul32(mul32(cy,cp),sr),mul32(mul32(sy,sp),cr)),add32(mul32(mul32(cy,cp),cr),mul32(mul32(sy,sp),sr)))
    @staticmethod
    def Lerp(a,b,t):
        dot=Quaternion.Dot(a,b);inverse=sub32(1,t)
        if dot>=0:r=Quaternion(*(add32(mul32(inverse,x),mul32(t,y)) for x,y in zip(a,b)))
        else:r=Quaternion(*(sub32(mul32(inverse,x),mul32(t,y)) for x,y in zip(a,b)))
        return Quaternion.Normalize(r)
    @staticmethod
    def Slerp(a,b,t):
        dot=Quaternion.Dot(a,b);flip=False
        if dot<0: flip=True;dot=f32(-dot)
        if dot>f32(0.999999):
            left=sub32(1,t);right=f32(-f32(t)) if flip else f32(t)
        else:
            angle=_acos32(dot)
            try: inv_sin=f32(1.0/math.sin(angle))
            except (ValueError,ZeroDivisionError): inv_sin=math.nan
            left=mul32(_sin32(mul32(sub32(1,t),angle)),inv_sin)
            right=mul32(_sin32(mul32(t,angle)),inv_sin)
            if flip:right=f32(-right)
        return Quaternion(*(add32(mul32(x,left),mul32(y,right)) for x,y in zip(a,b)))
    @staticmethod
    def Concatenate(value1,value2):
        if not isinstance(value1,Quaternion) or not isinstance(value2,Quaternion):
            raise TypeError("Concatenate expects two Quaternion values")
        return value2*value1
    Negate=staticmethod(lambda q:-q);Add=staticmethod(lambda a,b:a+b);Subtract=staticmethod(lambda a,b:a-b);Multiply=staticmethod(lambda a,b:a*b);Divide=staticmethod(lambda a,b:a/b)
    def __neg__(self): return Quaternion(*(f32(-v) for v in self))
    def __add__(self,o): return Quaternion(*(add32(a,b) for a,b in zip(self,o))) if isinstance(o,Quaternion) else NotImplemented
    def __sub__(self,o): return Quaternion(*(sub32(a,b) for a,b in zip(self,o))) if isinstance(o,Quaternion) else NotImplemented
    def __mul__(self,o):
        if isinstance(o,(int,float)): return Quaternion(*(mul32(v,o) for v in self))
        if not isinstance(o,Quaternion): return NotImplemented
        x=add32(add32(mul32(self.X,o.W),mul32(o.X,self.W)),sub32(mul32(self.Y,o.Z),mul32(self.Z,o.Y)))
        y=add32(add32(mul32(self.Y,o.W),mul32(o.Y,self.W)),sub32(mul32(self.Z,o.X),mul32(self.X,o.Z)))
        z=add32(add32(mul32(self.Z,o.W),mul32(o.Z,self.W)),sub32(mul32(self.X,o.Y),mul32(self.Y,o.X)))
        w=sub32(mul32(self.W,o.W),add32(add32(mul32(self.X,o.X),mul32(self.Y,o.Y)),mul32(self.Z,o.Z)))
        return Quaternion(x,y,z,w)
    __rmul__=__mul__
    def __truediv__(self,o): return self*Quaternion.Inverse(o) if isinstance(o,Quaternion) else NotImplemented


class Matrix:
    __slots__=tuple(f"_m{r}{c}" for r in range(1,5) for c in range(1,5))
    _names=tuple(f"M{r}{c}" for r in range(1,5) for c in range(1,5))
    def _component(name):
        private="_"+name.lower()
        return property(lambda self:getattr(self,private),lambda self,value:setattr(self,private,f32(value)))
    M11=_component("M11");M12=_component("M12");M13=_component("M13");M14=_component("M14")
    M21=_component("M21");M22=_component("M22");M23=_component("M23");M24=_component("M24")
    M31=_component("M31");M32=_component("M32");M33=_component("M33");M34=_component("M34")
    M41=_component("M41");M42=_component("M42");M43=_component("M43");M44=_component("M44")
    def __init__(self,*values:float):
        if not values: values=(0.0,)*16
        if len(values)!=16: raise TypeError("Matrix expects zero or sixteen Single values")
        for name,value in zip(self._names,values): setattr(self,name,value)
    def __iter__(self): return iter(getattr(self,n) for n in self._names)
    def __copy__(self): return Matrix(*self)
    __deepcopy__=lambda self,memo:self.__copy__()
    def __eq__(self,o): return isinstance(o,Matrix) and all(a==b for a,b in zip(self,o))
    def __hash__(self): return self.GetHashCode()
    def Equals(self,o): return self==o
    def GetHashCode(self): return hash32_sum(*(single_hash(value) for value in self))
    def ToString(self):
        rows=["{"+" ".join(f"M{row}{column}:{getattr(self,f'M{row}{column}'):g}" for column in range(1,5))+"}" for row in range(1,5)]
        return "{ "+" ".join(rows)+" }"
    __str__=ToString
    def __repr__(self): return f"Matrix({', '.join(repr(v) for v in self)})"
    @classproperty
    def Identity(cls): return cls(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
    @property
    def Right(self): return Vector3(self.M11,self.M12,self.M13)
    @Right.setter
    def Right(self,value): self.M11,self.M12,self.M13=value.X,value.Y,value.Z
    @property
    def Left(self): return Vector3(-self.M11,-self.M12,-self.M13)
    @Left.setter
    def Left(self,value): self.M11,self.M12,self.M13=-value.X,-value.Y,-value.Z
    @property
    def Up(self): return Vector3(self.M21,self.M22,self.M23)
    @Up.setter
    def Up(self,value): self.M21,self.M22,self.M23=value.X,value.Y,value.Z
    @property
    def Down(self): return Vector3(-self.M21,-self.M22,-self.M23)
    @Down.setter
    def Down(self,value): self.M21,self.M22,self.M23=-value.X,-value.Y,-value.Z
    @property
    def Backward(self): return Vector3(self.M31,self.M32,self.M33)
    @Backward.setter
    def Backward(self,value): self.M31,self.M32,self.M33=value.X,value.Y,value.Z
    @property
    def Forward(self): return Vector3(-self.M31,-self.M32,-self.M33)
    @Forward.setter
    def Forward(self,value): self.M31,self.M32,self.M33=-value.X,-value.Y,-value.Z
    @property
    def Translation(self): return Vector3(self.M41,self.M42,self.M43)
    @Translation.setter
    def Translation(self,v): self.M41,self.M42,self.M43=v.X,v.Y,v.Z
    @staticmethod
    def CreateScale(x,y=None,z=None):
        if isinstance(x,Vector3): x,y,z=x.X,x.Y,x.Z
        elif y is None and z is None:y=z=x
        elif y is None or z is None:raise TypeError("CreateScale expects scale, Vector3, or x, y, z")
        m=Matrix.Identity;m.M11=x;m.M22=y;m.M33=z;return m
    @staticmethod
    def CreateTranslation(x,y=None,z=None):
        if isinstance(x,Vector3): x,y,z=x.X,x.Y,x.Z
        elif y is None or z is None: raise TypeError("CreateTranslation expects Vector3 or x, y, z")
        m=Matrix.Identity;m.M41=x;m.M42=y;m.M43=z;return m
    @staticmethod
    def CreateRotationX(radians):
        c,s=_cos32(radians),_sin32(radians);m=Matrix.Identity;m.M22=c;m.M23=s;m.M32=f32(-s);m.M33=c;return m
    @staticmethod
    def CreateRotationY(radians):
        c,s=_cos32(radians),_sin32(radians);m=Matrix.Identity;m.M11=c;m.M13=f32(-s);m.M31=s;m.M33=c;return m
    @staticmethod
    def CreateRotationZ(radians):
        c,s=_cos32(radians),_sin32(radians);m=Matrix.Identity;m.M11=c;m.M12=s;m.M21=f32(-s);m.M22=c;return m
    @staticmethod
    def CreateFromAxisAngle(axis,angle):
        if not isinstance(axis,Vector3): raise TypeError("axis must be Vector3")
        x,y,z=axis.X,axis.Y,axis.Z;s,c=_sin32(angle),_cos32(angle)
        xx,yy,zz=mul32(x,x),mul32(y,y),mul32(z,z)
        xy,xz,yz=mul32(x,y),mul32(x,z),mul32(y,z)
        return Matrix(
            add32(xx,mul32(c,sub32(1,xx))),add32(sub32(xy,mul32(c,xy)),mul32(s,z)),sub32(sub32(xz,mul32(c,xz)),mul32(s,y)),0,
            sub32(sub32(xy,mul32(c,xy)),mul32(s,z)),add32(yy,mul32(c,sub32(1,yy))),add32(sub32(yz,mul32(c,yz)),mul32(s,x)),0,
            add32(sub32(xz,mul32(c,xz)),mul32(s,y)),sub32(sub32(yz,mul32(c,yz)),mul32(s,x)),add32(zz,mul32(c,sub32(1,zz))),0,
            0,0,0,1)
    @staticmethod
    def CreateFromQuaternion(q):
        if not isinstance(q,Quaternion): raise TypeError("quaternion must be Quaternion")
        xx,yy,zz=mul32(q.X,q.X),mul32(q.Y,q.Y),mul32(q.Z,q.Z);xy,xz,yz=mul32(q.X,q.Y),mul32(q.X,q.Z),mul32(q.Y,q.Z);wx,wy,wz=mul32(q.W,q.X),mul32(q.W,q.Y),mul32(q.W,q.Z)
        return Matrix(sub32(1,mul32(2,add32(yy,zz))),mul32(2,add32(xy,wz)),mul32(2,sub32(xz,wy)),0,mul32(2,sub32(xy,wz)),sub32(1,mul32(2,add32(xx,zz))),mul32(2,add32(yz,wx)),0,mul32(2,add32(xz,wy)),mul32(2,sub32(yz,wx)),sub32(1,mul32(2,add32(xx,yy))),0,0,0,0,1)
    @staticmethod
    def CreateFromYawPitchRoll(yaw,pitch,roll):
        return Matrix.CreateFromQuaternion(Quaternion.CreateFromYawPitchRoll(yaw,pitch,roll))
    @staticmethod
    def CreateLookAt(cameraPosition,cameraTarget,cameraUpVector):
        z=Vector3.Normalize(cameraPosition-cameraTarget);x=Vector3.Normalize(Vector3.Cross(cameraUpVector,z));y=Vector3.Cross(z,x)
        return Matrix(x.X,y.X,z.X,0,x.Y,y.Y,z.Y,0,x.Z,y.Z,z.Z,0,f32(-Vector3.Dot(x,cameraPosition)),f32(-Vector3.Dot(y,cameraPosition)),f32(-Vector3.Dot(z,cameraPosition)),1)
    @staticmethod
    def CreateWorld(position,forward,up):
        if not all(isinstance(value,Vector3) for value in (position,forward,up)):
            raise TypeError("CreateWorld expects three Vector3 values")
        backward=Vector3.Normalize(-forward);right=Vector3.Normalize(Vector3.Cross(up,backward));corrected_up=Vector3.Cross(backward,right)
        return Matrix(right.X,right.Y,right.Z,0,corrected_up.X,corrected_up.Y,corrected_up.Z,0,backward.X,backward.Y,backward.Z,0,position.X,position.Y,position.Z,1)
    @staticmethod
    def _validate_perspective(near,far):
        near,far=f32(near),f32(far)
        if near<=0: raise ValueError("nearPlaneDistance must be positive")
        if far<=0: raise ValueError("farPlaneDistance must be positive")
        if near>=far: raise ValueError("nearPlaneDistance must be less than farPlaneDistance")
        return near,far
    @staticmethod
    def CreatePerspectiveFieldOfView(fieldOfView,aspectRatio,nearPlaneDistance,farPlaneDistance):
        fov,aspect=map(f32,(fieldOfView,aspectRatio));near,far=Matrix._validate_perspective(nearPlaneDistance,farPlaneDistance)
        if fov<=0 or fov>=MathHelper.Pi: raise ValueError("fieldOfView must be greater than zero and less than Pi")
        y=div32(1,f32(math.tan(mul32(fov,0.5))));x=div32(y,aspect)
        denominator=sub32(near,far);depth=div32(far,denominator)
        return Matrix(x,0,0,0,0,y,0,0,0,0,depth,-1,0,0,div32(mul32(near,far),denominator),0)
    @staticmethod
    def CreatePerspective(width,height,nearPlaneDistance,farPlaneDistance):
        width,height=f32(width),f32(height);near,far=Matrix._validate_perspective(nearPlaneDistance,farPlaneDistance)
        denominator=sub32(near,far);depth=div32(far,denominator)
        return Matrix(div32(mul32(2,near),width),0,0,0,0,div32(mul32(2,near),height),0,0,0,0,depth,-1,0,0,div32(mul32(near,far),denominator),0)
    @staticmethod
    def CreatePerspectiveOffCenter(left,right,bottom,top,nearPlaneDistance,farPlaneDistance):
        left,right,bottom,top=map(f32,(left,right,bottom,top));near,far=Matrix._validate_perspective(nearPlaneDistance,farPlaneDistance)
        width,height=sub32(right,left),sub32(top,bottom);denominator=sub32(near,far);depth=div32(far,denominator)
        return Matrix(div32(mul32(2,near),width),0,0,0,0,div32(mul32(2,near),height),0,0,div32(add32(left,right),width),div32(add32(top,bottom),height),depth,-1,0,0,div32(mul32(near,far),denominator),0)
    @staticmethod
    def CreateOrthographic(width,height,zNearPlane,zFarPlane):
        width,height,near,far=map(f32,(width,height,zNearPlane,zFarPlane))
        return Matrix(div32(2,width),0,0,0,0,div32(2,height),0,0,0,0,div32(1,sub32(near,far)),0,0,0,div32(near,sub32(near,far)),1)
    @staticmethod
    def CreateOrthographicOffCenter(left,right,bottom,top,zNearPlane,zFarPlane):
        left,right,bottom,top,near,far=map(f32,(left,right,bottom,top,zNearPlane,zFarPlane));width=sub32(right,left);height=sub32(top,bottom);depth=sub32(near,far)
        return Matrix(div32(2,width),0,0,0,0,div32(2,height),0,0,0,0,div32(1,depth),0,div32(add32(left,right),sub32(left,right)),div32(add32(top,bottom),sub32(bottom,top)),div32(near,depth),1)
    @staticmethod
    def CreateBillboard(objectPosition,cameraPosition,cameraUpVector,cameraForwardVector):
        if not all(isinstance(value,Vector3) for value in (objectPosition,cameraPosition,cameraUpVector)) or (cameraForwardVector is not None and not isinstance(cameraForwardVector,Vector3)):
            raise TypeError("CreateBillboard expects Vector3 positions/up and optional Vector3 forward")
        facing=objectPosition-cameraPosition;length_squared=facing.LengthSquared()
        if length_squared<f32(0.0001): facing=-cameraForwardVector if cameraForwardVector is not None else Vector3.Forward
        else: facing*=div32(1,_sqrt32(length_squared))
        right=Vector3.Normalize(Vector3.Cross(cameraUpVector,facing));up=Vector3.Cross(facing,right)
        return Matrix(right.X,right.Y,right.Z,0,up.X,up.Y,up.Z,0,facing.X,facing.Y,facing.Z,0,objectPosition.X,objectPosition.Y,objectPosition.Z,1)
    @staticmethod
    def CreateConstrainedBillboard(objectPosition,cameraPosition,rotateAxis,cameraForwardVector,objectForwardVector):
        if not all(isinstance(value,Vector3) for value in (objectPosition,cameraPosition,rotateAxis)) or any(value is not None and not isinstance(value,Vector3) for value in (cameraForwardVector,objectForwardVector)):
            raise TypeError("CreateConstrainedBillboard expects Vector3 values and nullable forward vectors")
        facing=objectPosition-cameraPosition;length_squared=facing.LengthSquared()
        if length_squared<f32(0.0001): facing=-cameraForwardVector if cameraForwardVector is not None else Vector3.Forward
        else: facing*=div32(1,_sqrt32(length_squared))
        up=Vector3(rotateAxis.X,rotateAxis.Y,rotateAxis.Z);alignment=Vector3.Dot(rotateAxis,facing)
        if abs(alignment)>f32(0.99825466):
            forward=Vector3(objectForwardVector.X,objectForwardVector.Y,objectForwardVector.Z) if objectForwardVector is not None else Vector3.Forward
            alignment=Vector3.Dot(rotateAxis,forward)
            if abs(alignment)>f32(0.99825466): forward=Vector3.Right if abs(Vector3.Dot(rotateAxis,Vector3.Forward))>f32(0.99825466) else Vector3.Forward
            right=Vector3.Normalize(Vector3.Cross(rotateAxis,forward));forward=Vector3.Normalize(Vector3.Cross(right,rotateAxis))
        else:
            right=Vector3.Normalize(Vector3.Cross(rotateAxis,facing));forward=Vector3.Normalize(Vector3.Cross(right,up))
        return Matrix(right.X,right.Y,right.Z,0,up.X,up.Y,up.Z,0,forward.X,forward.Y,forward.Z,0,objectPosition.X,objectPosition.Y,objectPosition.Z,1)
    @staticmethod
    def CreateShadow(lightDirection,plane):
        from ._intersections import Plane
        if not isinstance(lightDirection,Vector3) or not isinstance(plane,Plane): raise TypeError("CreateShadow expects Vector3 and Plane")
        normalized=Plane.Normalize(plane);dot=Vector3.Dot(normalized.Normal,lightDirection);x,y,z,d=-normalized.Normal.X,-normalized.Normal.Y,-normalized.Normal.Z,-normalized.D
        return Matrix(add32(mul32(x,lightDirection.X),dot),mul32(x,lightDirection.Y),mul32(x,lightDirection.Z),0,mul32(y,lightDirection.X),add32(mul32(y,lightDirection.Y),dot),mul32(y,lightDirection.Z),0,mul32(z,lightDirection.X),mul32(z,lightDirection.Y),add32(mul32(z,lightDirection.Z),dot),0,mul32(d,lightDirection.X),mul32(d,lightDirection.Y),mul32(d,lightDirection.Z),dot)
    @staticmethod
    def CreateReflection(value):
        from ._intersections import Plane
        if not isinstance(value,Plane): raise TypeError("value must be Plane")
        plane=Plane.Normalize(value);x,y,z=plane.Normal.X,plane.Normal.Y,plane.Normal.Z;dx,dy,dz=mul32(-2,x),mul32(-2,y),mul32(-2,z)
        return Matrix(add32(mul32(dx,x),1),mul32(dy,x),mul32(dz,x),0,mul32(dx,y),add32(mul32(dy,y),1),mul32(dz,y),0,mul32(dx,z),mul32(dy,z),add32(mul32(dz,z),1),0,mul32(dx,plane.D),mul32(dy,plane.D),mul32(dz,plane.D),1)
    def Decompose(self):
        translation=Vector3(self.M41,self.M42,self.M43);basis=[Vector3(self.M11,self.M12,self.M13),Vector3(self.M21,self.M22,self.M23),Vector3(self.M31,self.M32,self.M33)];scale=Vector3(*(value.Length() for value in basis));scales=[scale.X,scale.Y,scale.Z]
        ordered=sorted(range(3),key=lambda index:scales[index],reverse=True);largest,middle,smallest=ordered
        canonical=(Vector3.UnitX,Vector3.UnitY,Vector3.UnitZ)
        if scales[largest]<f32(0.0001): basis[largest]=canonical[largest]
        basis[largest]=Vector3.Normalize(basis[largest])
        if scales[middle]<f32(0.0001):
            least=min(range(3),key=lambda index:abs(Vector3.Dot(basis[largest],canonical[index])))
            basis[middle]=Vector3.Cross(basis[largest],canonical[least])
        basis[middle]=Vector3.Normalize(basis[middle])
        if scales[smallest]<f32(0.0001): basis[smallest]=Vector3.Cross(basis[largest],basis[middle])
        basis[smallest]=Vector3.Normalize(basis[smallest])
        rotation_matrix=Matrix(basis[0].X,basis[0].Y,basis[0].Z,0,basis[1].X,basis[1].Y,basis[1].Z,0,basis[2].X,basis[2].Y,basis[2].Z,0,0,0,0,1);determinant=rotation_matrix.Determinant()
        if determinant<0:
            scales[largest]=f32(-scales[largest]);basis[largest]=-basis[largest];rotation_matrix=Matrix(basis[0].X,basis[0].Y,basis[0].Z,0,basis[1].X,basis[1].Y,basis[1].Z,0,basis[2].X,basis[2].Y,basis[2].Z,0,0,0,0,1);determinant=f32(-determinant)
        scale=Vector3(*scales);error=mul32(sub32(determinant,1),sub32(determinant,1))
        if math.isnan(error) or error>f32(0.0001): return False,scale,Quaternion.Identity,translation
        return True,scale,Quaternion.CreateFromRotationMatrix(rotation_matrix),translation
    @staticmethod
    def Transpose(value): return Matrix(*(getattr(value,f"M{c}{r}") for r in range(1,5) for c in range(1,5)))
    def Determinant(self):
        n1=sub32(mul32(self.M33,self.M44),mul32(self.M34,self.M43));n2=sub32(mul32(self.M32,self.M44),mul32(self.M34,self.M42));n3=sub32(mul32(self.M32,self.M43),mul32(self.M33,self.M42))
        n4=sub32(mul32(self.M31,self.M44),mul32(self.M34,self.M41));n5=sub32(mul32(self.M31,self.M43),mul32(self.M33,self.M41));n6=sub32(mul32(self.M31,self.M42),mul32(self.M32,self.M41))
        a=add32(sub32(mul32(self.M22,n1),mul32(self.M23,n2)),mul32(self.M24,n3));b=add32(sub32(mul32(self.M21,n1),mul32(self.M23,n4)),mul32(self.M24,n5))
        c=add32(sub32(mul32(self.M21,n2),mul32(self.M22,n4)),mul32(self.M24,n6));d=add32(sub32(mul32(self.M21,n3),mul32(self.M22,n5)),mul32(self.M23,n6))
        return sub32(add32(sub32(mul32(self.M11,a),mul32(self.M12,b)),mul32(self.M13,c)),mul32(self.M14,d))
    @staticmethod
    def Invert(matrix):
        if not isinstance(matrix,Matrix): raise TypeError("matrix must be Matrix")
        n=list(matrix)
        n1,n2,n3,n4,n5,n6,n7,n8,n9,n10,n11,n12,n13,n14,n15,n16=n
        n17=sub32(mul32(n11,n16),mul32(n12,n15));n18=sub32(mul32(n10,n16),mul32(n12,n14));n19=sub32(mul32(n10,n15),mul32(n11,n14));n20=sub32(mul32(n9,n16),mul32(n12,n13));n21=sub32(mul32(n9,n15),mul32(n11,n13));n22=sub32(mul32(n9,n14),mul32(n10,n13))
        n23=add32(sub32(mul32(n6,n17),mul32(n7,n18)),mul32(n8,n19));n24=f32(-add32(sub32(mul32(n5,n17),mul32(n7,n20)),mul32(n8,n21)));n25=add32(sub32(mul32(n5,n18),mul32(n6,n20)),mul32(n8,n22));n26=f32(-add32(sub32(mul32(n5,n19),mul32(n6,n21)),mul32(n7,n22)))
        n27=div32(1,add32(add32(mul32(n1,n23),mul32(n2,n24)),add32(mul32(n3,n25),mul32(n4,n26))))
        result=[0.0]*16
        result[0]=mul32(n23,n27);result[4]=mul32(n24,n27);result[8]=mul32(n25,n27);result[12]=mul32(n26,n27)
        result[1]=mul32(-add32(sub32(mul32(n2,n17),mul32(n3,n18)),mul32(n4,n19)),n27);result[5]=mul32(add32(sub32(mul32(n1,n17),mul32(n3,n20)),mul32(n4,n21)),n27)
        result[9]=mul32(-add32(sub32(mul32(n1,n18),mul32(n2,n20)),mul32(n4,n22)),n27);result[13]=mul32(add32(sub32(mul32(n1,n19),mul32(n2,n21)),mul32(n3,n22)),n27)
        n28=sub32(mul32(n7,n16),mul32(n8,n15));n29=sub32(mul32(n6,n16),mul32(n8,n14));n30=sub32(mul32(n6,n15),mul32(n7,n14));n31=sub32(mul32(n5,n16),mul32(n8,n13));n32=sub32(mul32(n5,n15),mul32(n7,n13));n33=sub32(mul32(n5,n14),mul32(n6,n13))
        result[2]=mul32(add32(sub32(mul32(n2,n28),mul32(n3,n29)),mul32(n4,n30)),n27);result[6]=mul32(-add32(sub32(mul32(n1,n28),mul32(n3,n31)),mul32(n4,n32)),n27)
        result[10]=mul32(add32(sub32(mul32(n1,n29),mul32(n2,n31)),mul32(n4,n33)),n27);result[14]=mul32(-add32(sub32(mul32(n1,n30),mul32(n2,n32)),mul32(n3,n33)),n27)
        n34=sub32(mul32(n7,n12),mul32(n8,n11));n35=sub32(mul32(n6,n12),mul32(n8,n10));n36=sub32(mul32(n6,n11),mul32(n7,n10));n37=sub32(mul32(n5,n12),mul32(n8,n9));n38=sub32(mul32(n5,n11),mul32(n7,n9));n39=sub32(mul32(n5,n10),mul32(n6,n9))
        result[3]=mul32(-add32(sub32(mul32(n2,n34),mul32(n3,n35)),mul32(n4,n36)),n27);result[7]=mul32(add32(sub32(mul32(n1,n34),mul32(n3,n37)),mul32(n4,n38)),n27)
        result[11]=mul32(-add32(sub32(mul32(n1,n35),mul32(n2,n37)),mul32(n4,n39)),n27);result[15]=mul32(add32(sub32(mul32(n1,n36),mul32(n2,n38)),mul32(n3,n39)),n27)
        return Matrix(*result)
    @staticmethod
    def Lerp(matrix1,matrix2,amount):
        if not isinstance(matrix1,Matrix) or not isinstance(matrix2,Matrix): raise TypeError("Lerp expects two Matrix values")
        return Matrix(*(add32(a,mul32(sub32(b,a),amount)) for a,b in zip(matrix1,matrix2)))
    @staticmethod
    def Transform(value,rotation):
        if not isinstance(value,Matrix) or not isinstance(rotation,Quaternion): raise TypeError("Transform expects Matrix and Quaternion")
        m11,m12,m13,m21,m22,m23,m31,m32,m33=_quaternion_rotation_terms(rotation);result=[]
        for row in range(1,5):
            x,y,z=getattr(value,f"M{row}1"),getattr(value,f"M{row}2"),getattr(value,f"M{row}3")
            result.extend((_sum3(mul32(x,m11),mul32(y,m12),mul32(z,m13)),
                           _sum3(mul32(x,m21),mul32(y,m22),mul32(z,m23)),
                           _sum3(mul32(x,m31),mul32(y,m32),mul32(z,m33)),
                           getattr(value,f"M{row}4")))
        return Matrix(*result)
    @staticmethod
    def Add(a,b): return a+b
    @staticmethod
    def Subtract(a,b): return a-b
    @staticmethod
    def Negate(v): return -v
    @staticmethod
    def Multiply(a,b): return a*b
    @staticmethod
    def Divide(a,b): return a/b
    def __neg__(self): return Matrix(*(f32(-v) for v in self))
    def __add__(self,o): return Matrix(*(add32(a,b) for a,b in zip(self,o))) if isinstance(o,Matrix) else NotImplemented
    def __sub__(self,o): return Matrix(*(sub32(a,b) for a,b in zip(self,o))) if isinstance(o,Matrix) else NotImplemented
    def __mul__(self,o):
        if isinstance(o,(int,float)): return Matrix(*(mul32(v,o) for v in self))
        if not isinstance(o,Matrix): return NotImplemented
        values=[]
        for r in range(1,5):
            for c in range(1,5):
                value=mul32(getattr(self,f"M{r}1"),getattr(o,f"M1{c}"))
                value=add32(value,mul32(getattr(self,f"M{r}2"),getattr(o,f"M2{c}")))
                value=add32(value,mul32(getattr(self,f"M{r}3"),getattr(o,f"M3{c}")))
                value=add32(value,mul32(getattr(self,f"M{r}4"),getattr(o,f"M4{c}")))
                values.append(value)
        return Matrix(*values)
    __rmul__=__mul__
    def __truediv__(self,o):
        if isinstance(o,Matrix): return Matrix(*(div32(a,b) for a,b in zip(self,o)))
        if isinstance(o,(int,float)):
            factor=div32(1,o);return Matrix(*(mul32(v,factor) for v in self))
        return NotImplemented


Vector2.__xna_arities__ = {"__init__": {0, 1, 2}, "Normalize": {0, 1}, "Transform": {2, 3, 6}, "TransformNormal": {2, 3, 6}}
Vector3.__xna_arities__ = {"__init__": {0, 1, 2, 3}, "Normalize": {0, 1}, "Transform": {2, 3, 6}, "TransformNormal": {2, 3, 6}}
Vector4.__xna_arities__ = {"__init__": {0, 1, 2, 3, 4}, "Normalize": {0, 1}, "Transform": {2, 3, 6}}
Quaternion.__xna_arities__ = {"Normalize": {0, 1}, "Conjugate": {0, 1},
                              "__init__": {0, 2, 4}, "CreateFromRotationMatrix": {1},
                              "Concatenate": {2}}
Matrix.__xna_arities__ = {"__init__": {0, 16}, "CreateScale": {1, 3}, "CreateTranslation": {1, 3},
                          "CreateBillboard": {4}, "CreateConstrainedBillboard": {5},
                          "CreateFromAxisAngle": {2}, "CreateFromYawPitchRoll": {3},
                          "CreateOrthographic": {4}, "CreateOrthographicOffCenter": {6},
                          "CreatePerspective": {4}, "CreatePerspectiveOffCenter": {6},
                          "CreateReflection": {1}, "CreateShadow": {2}, "CreateWorld": {3},
                          "Decompose": {0}, "Determinant": {0}, "Invert": {1}, "Lerp": {3},
                          "Transform": {2}}
