"""Pure XNA Single-based math values.

Every public component is narrowed to binary32 on assignment and after each
primitive arithmetic operation.  This is intentional: Python's binary64 float
is not the XNA ``System.Single`` contract.
"""

from __future__ import annotations

import math
from typing import Any

from ._language import classproperty
from ._numeric import add32, div32, f32, mul32, sub32


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
        return a if a < b else b

    @staticmethod
    def Max(value1: float, value2: float) -> float:
        a, b = f32(value1), f32(value2)
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
        t2, t3 = mul32(t, t), mul32(mul32(t, t), t)
        inner = add32(
            add32(mul32(2.0, value2), mul32(sub32(value3, value1), t)),
            add32(
                mul32(add32(sub32(mul32(2.0, value1), mul32(5.0, value2)), sub32(mul32(4.0, value3), value4)), t2),
                mul32(add32(sub32(mul32(3.0, value2), value1), sub32(value4, mul32(3.0, value3))), t3),
            ),
        )
        return mul32(0.5, inner)

    @staticmethod
    def Hermite(value1: float, tangent1: float, value2: float, tangent2: float, amount: float) -> float:
        t = f32(amount)
        t2, t3 = mul32(t, t), mul32(mul32(t, t), t)
        h1 = add32(sub32(mul32(2.0, t3), mul32(3.0, t2)), 1.0)
        h2 = add32(sub32(t3, mul32(2.0, t2)), t)
        h3 = add32(mul32(-2.0, t3), mul32(3.0, t2))
        h4 = sub32(t3, t2)
        return add32(add32(mul32(value1, h1), mul32(tangent1, h2)), add32(mul32(value2, h3), mul32(tangent2, h4)))

    @staticmethod
    def WrapAngle(angle: float) -> float:
        value = f32(angle)
        if value > MathHelper.Pi:
            value = sub32(value, mul32(MathHelper.TwoPi, math.ceil(div32(sub32(value, MathHelper.Pi), MathHelper.TwoPi))))
        elif value < -MathHelper.Pi:
            value = add32(value, mul32(MathHelper.TwoPi, math.ceil(div32(sub32(-MathHelper.Pi, value), MathHelper.TwoPi))))
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
        return hash(tuple(getattr(self, name) for name in self._component_names))

    def Equals(self, other: object) -> bool:
        return self == other

    def GetHashCode(self) -> int:
        return hash(self)

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

    def __init__(self, x: float = 0.0, y: float | None = None) -> None:
        self.X = x
        self.Y = x if y is None else y

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
        return Vector2(MathHelper.Min(value1.X, value2.X), MathHelper.Min(value1.Y, value2.Y))

    @staticmethod
    def Max(value1: "Vector2", value2: "Vector2") -> "Vector2":
        return Vector2(MathHelper.Max(value1.X, value2.X), MathHelper.Max(value1.Y, value2.Y))

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
        if isinstance(other, (int, float)): return Vector2(div32(self.X, other), div32(self.Y, other))
        return NotImplemented


@_vector_value
class Vector3:
    __slots__ = ("_x", "_y", "_z")
    _component_names = ("X", "Y", "Z")

    def __init__(self, x: float | Vector2 = 0.0, y: float | None = None, z: float | None = None) -> None:
        if isinstance(x, Vector2):
            if y is None or z is not None: raise TypeError("Vector3(Vector2, z) expects two arguments")
            self.X, self.Y, self.Z = x.X, x.Y, y
        else:
            self.X = x
            self.Y = x if y is None else y
            self.Z = x if z is None else z

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
    def Min(a,b): return Vector3(*(MathHelper.Min(x,y) for x,y in zip(a,b)))
    @staticmethod
    def Max(a,b): return Vector3(*(MathHelper.Max(x,y) for x,y in zip(a,b)))
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
        if isinstance(o,(int,float)): return Vector3(*(div32(a,o) for a in self))
        return NotImplemented


@_vector_value
class Vector4:
    __slots__=("_x","_y","_z","_w")
    _component_names=("X","Y","Z","W")
    def __init__(self,x:float|Vector2|Vector3=0.0,y:float|None=None,z:float|None=None,w:float|None=None):
        if isinstance(x,Vector3):
            if y is None or z is not None or w is not None: raise TypeError("Vector4(Vector3, w) expects two arguments")
            values=(x.X,x.Y,x.Z,y)
        elif isinstance(x,Vector2):
            if y is None or z is None or w is not None: raise TypeError("Vector4(Vector2, z, w) expects three arguments")
            values=(x.X,x.Y,y,z)
        else: values=(x,x if y is None else y,x if z is None else z,x if w is None else w)
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
    def LengthSquared(self): return add32(add32(mul32(self.X,self.X),mul32(self.Y,self.Y)),add32(mul32(self.Z,self.Z),mul32(self.W,self.W)))
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
    def Dot(a,b): return add32(add32(mul32(a.X,b.X),mul32(a.Y,b.Y)),add32(mul32(a.Z,b.Z),mul32(a.W,b.W)))
    @staticmethod
    def Min(a,b): return Vector4(*(MathHelper.Min(x,y) for x,y in zip(a,b)))
    @staticmethod
    def Max(a,b): return Vector4(*(MathHelper.Max(x,y) for x,y in zip(a,b)))
    @staticmethod
    def Clamp(v,mn,mx): return Vector4(*(MathHelper.Clamp(x,y,z) for x,y,z in zip(v,mn,mx)))
    @staticmethod
    def Lerp(a,b,t): return Vector4(*(MathHelper.Lerp(x,y,t) for x,y in zip(a,b)))
    @staticmethod
    def SmoothStep(a,b,t): return Vector4(*(MathHelper.SmoothStep(x,y,t) for x,y in zip(a,b)))
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
        if isinstance(o,(int,float)): return Vector4(*(div32(a,o) for a in self))
        return NotImplemented


@_vector_value
class Quaternion:
    __slots__=("_x","_y","_z","_w")
    _component_names=("X","Y","Z","W")
    def __init__(self,x:float|Vector3=0.0,y:float=0.0,z:float=0.0,w:float=0.0):
        if isinstance(x,Vector3): x,y,z=x.X,x.Y,x.Z
        self.X,self.Y,self.Z,self.W=x,y,z,w
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
    def CreateFromYawPitchRoll(yaw,pitch,roll):
        half_roll=mul32(roll,0.5);sr,cr=_sin32(half_roll),_cos32(half_roll)
        half_pitch=mul32(pitch,0.5);sp,cp=_sin32(half_pitch),_cos32(half_pitch)
        half_yaw=mul32(yaw,0.5);sy,cy=_sin32(half_yaw),_cos32(half_yaw)
        return Quaternion(add32(mul32(mul32(cy,sp),cr),mul32(mul32(sy,cp),sr)),sub32(mul32(mul32(sy,cp),cr),mul32(mul32(cy,sp),sr)),sub32(mul32(mul32(cy,cp),sr),mul32(mul32(sy,sp),cr)),add32(mul32(mul32(cy,cp),cr),mul32(mul32(sy,sp),sr)))
    @staticmethod
    def Lerp(a,b,t):
        dot=Quaternion.Dot(a,b);sign=-1.0 if dot<0 else 1.0
        r=Quaternion(*(add32(mul32(x,sub32(1,t)),mul32(mul32(y,t),sign)) for x,y in zip(a,b)))
        return Quaternion.Normalize(r)
    @staticmethod
    def Slerp(a,b,t):
        dot=Quaternion.Dot(a,b);sign=1.0
        if dot<0: sign=-1.0;dot=f32(-dot)
        if dot>f32(0.999999): return Quaternion.Lerp(a,b,t)
        angle=_acos32(dot);inv_sin=div32(1,_sin32(angle))
        left=mul32(_sin32(mul32(sub32(1,t),angle)),inv_sin);right=mul32(_sin32(mul32(t,angle)),inv_sin);right=mul32(right,sign)
        return Quaternion(*(add32(mul32(x,left),mul32(y,right)) for x,y in zip(a,b)))
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
    def __init__(self,*values:float):
        if not values: values=(0.0,)*16
        if len(values)!=16: raise TypeError("Matrix expects zero or sixteen Single values")
        for name,value in zip(self._names,values): setattr(self,name,value)
    def __getattr__(self,name):
        if name in self._names:return getattr(self,"_"+name.lower())
        raise AttributeError(name)
    def __setattr__(self,name,value):
        if name in self._names: object.__setattr__(self,"_"+name.lower(),f32(value))
        else: object.__setattr__(self,name,value)
    def __iter__(self): return iter(getattr(self,n) for n in self._names)
    def __copy__(self): return Matrix(*self)
    __deepcopy__=lambda self,memo:self.__copy__()
    def __eq__(self,o): return isinstance(o,Matrix) and all(a==b for a,b in zip(self,o))
    def __hash__(self): return hash(tuple(self))
    def Equals(self,o): return self==o
    def GetHashCode(self): return hash(self)
    def ToString(self): return "{"+" ".join(f"{n}:{getattr(self,n):g}" for n in self._names)+"}"
    __str__=ToString
    def __repr__(self): return f"Matrix({', '.join(repr(v) for v in self)})"
    @classproperty
    def Identity(cls): return cls(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
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
    def CreateFromQuaternion(q):
        xx,yy,zz=mul32(q.X,q.X),mul32(q.Y,q.Y),mul32(q.Z,q.Z);xy,xz,yz=mul32(q.X,q.Y),mul32(q.X,q.Z),mul32(q.Y,q.Z);wx,wy,wz=mul32(q.W,q.X),mul32(q.W,q.Y),mul32(q.W,q.Z)
        return Matrix(sub32(1,mul32(2,add32(yy,zz))),mul32(2,add32(xy,wz)),mul32(2,sub32(xz,wy)),0,mul32(2,sub32(xy,wz)),sub32(1,mul32(2,add32(xx,zz))),mul32(2,add32(yz,wx)),0,mul32(2,add32(xz,wy)),mul32(2,sub32(yz,wx)),sub32(1,mul32(2,add32(xx,yy))),0,0,0,0,1)
    @staticmethod
    def CreateLookAt(cameraPosition,cameraTarget,cameraUpVector):
        z=Vector3.Normalize(cameraPosition-cameraTarget);x=Vector3.Normalize(Vector3.Cross(cameraUpVector,z));y=Vector3.Cross(z,x)
        return Matrix(x.X,y.X,z.X,0,x.Y,y.Y,z.Y,0,x.Z,y.Z,z.Z,0,f32(-Vector3.Dot(x,cameraPosition)),f32(-Vector3.Dot(y,cameraPosition)),f32(-Vector3.Dot(z,cameraPosition)),1)
    @staticmethod
    def CreatePerspectiveFieldOfView(fieldOfView,aspectRatio,nearPlaneDistance,farPlaneDistance):
        fov,aspect,near,far=map(f32,(fieldOfView,aspectRatio,nearPlaneDistance,farPlaneDistance))
        if fov<=0 or fov>=MathHelper.Pi: raise ValueError("fieldOfView must be greater than zero and less than Pi")
        if near<=0: raise ValueError("nearPlaneDistance must be positive")
        if far<=0: raise ValueError("farPlaneDistance must be positive")
        if near>=far: raise ValueError("nearPlaneDistance must be less than farPlaneDistance")
        y=div32(1,math.tan(div32(fov,2)));x=div32(y,aspect);depth=div32(far,sub32(near,far))
        return Matrix(x,0,0,0,0,y,0,0,0,0,depth,-1,0,0,mul32(near,depth),0)
    @staticmethod
    def Transpose(value): return Matrix(*(getattr(value,f"M{c}{r}") for r in range(1,5) for c in range(1,5)))
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
        if isinstance(o,(int,float)): return Matrix(*(div32(v,o) for v in self))
        return NotImplemented


Vector2.__xna_arities__ = {"Normalize": {0, 1}}
Vector3.__xna_arities__ = {"Normalize": {0, 1}}
Vector4.__xna_arities__ = {"Normalize": {0, 1}}
Quaternion.__xna_arities__ = {"Normalize": {0, 1}, "Conjugate": {0, 1},
                              "__init__": {0, 2, 4}}
Matrix.__xna_arities__ = {"CreateScale": {1, 3}, "CreateTranslation": {1, 3}}
