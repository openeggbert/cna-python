"""XNA-compatible pure value geometry and intersection primitives."""

from __future__ import annotations

from enum import IntEnum
import math
from typing import Any

from ._math import MathHelper, Matrix, Quaternion, Vector3, Vector4, _dualmethod, _sqrt32
from ._numeric import add32, div32, f32, hash32_sum, mul32, single_hash, sub32


class ContainmentType(IntEnum):
    Disjoint = 0
    Contains = 1
    Intersects = 2


class PlaneIntersectionType(IntEnum):
    Front = 0
    Back = 1
    Intersecting = 2


def _copy_vector(value: Vector3, *, name: str = "value") -> Vector3:
    if not isinstance(value, Vector3):
        raise TypeError(f"{name} must be Vector3")
    return Vector3(value.X, value.Y, value.Z)


def _copy_plane(value: "Plane") -> "Plane":
    return Plane(value.Normal, value.D)


class _StructValue:
    __slots__ = ()

    def Equals(self, other: object) -> bool:
        return self == other

    def GetHashCode(self) -> int:
        return hash(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        return self.__copy__()


class Plane(_StructValue):
    __slots__ = ("_normal", "_d")

    def __init__(self, *args: object) -> None:
        if not args:
            normal, d = Vector3.Zero, 0.0
        elif len(args) == 2 and isinstance(args[0], Vector3):
            normal, d = args
        elif len(args) == 1 and isinstance(args[0], Vector4):
            normal, d = Vector3(args[0].X, args[0].Y, args[0].Z), args[0].W
        elif len(args) == 4:
            normal, d = Vector3(args[0], args[1], args[2]), args[3]
        elif len(args) == 3 and all(isinstance(value, Vector3) for value in args):
            normal = Vector3.Normalize(Vector3.Cross(args[1] - args[0], args[2] - args[0]))
            d = f32(-Vector3.Dot(normal, args[0]))
        else:
            raise TypeError("Plane expects (), Vector3 and d, Vector4, a/b/c/d, or three Vector3 points")
        self.Normal = normal
        self.D = d

    @property
    def Normal(self) -> Vector3:
        return _copy_vector(self._normal)

    @Normal.setter
    def Normal(self, value: Vector3) -> None:
        self._normal = _copy_vector(value, name="Normal")

    @property
    def D(self) -> float:
        return self._d

    @D.setter
    def D(self, value: float) -> None:
        self._d = f32(value)

    def __copy__(self) -> "Plane":
        return Plane(self.Normal, self.D)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Plane) and self.Normal == other.Normal and self.D == other.D

    def __hash__(self) -> int:
        return self.GetHashCode()

    def GetHashCode(self) -> int:
        return hash32_sum(self.Normal.GetHashCode(), single_hash(self.D))

    def ToString(self) -> str:
        return f"{{Normal:{self.Normal} D:{self.D:g}}}"

    __str__ = ToString

    def _normalize_instance(self) -> None:
        length_squared = self.Normal.LengthSquared()
        if not abs(sub32(length_squared, 1.0)) < f32(1.1920929e-7):
            factor = div32(1.0, _sqrt32(length_squared))
            self._normal = self._normal * factor
            self._d = mul32(self._d, factor)

    @staticmethod
    def _normalize_static(value: "Plane") -> "Plane":
        if not isinstance(value, Plane):
            raise TypeError("value must be Plane")
        result = value.__copy__()
        result._normalize_instance()
        return result

    Normalize = _dualmethod(_normalize_instance, _normalize_static)

    @staticmethod
    def Transform(plane: "Plane", transform: object) -> "Plane":
        if not isinstance(plane, Plane):
            raise TypeError("plane must be Plane")
        if isinstance(transform, Matrix):
            inverse = Matrix.Invert(transform)
            x, y, z, d = plane.Normal.X, plane.Normal.Y, plane.Normal.Z, plane.D
            return Plane(
                add32(add32(mul32(x, inverse.M11), mul32(y, inverse.M12)), add32(mul32(z, inverse.M13), mul32(d, inverse.M14))),
                add32(add32(mul32(x, inverse.M21), mul32(y, inverse.M22)), add32(mul32(z, inverse.M23), mul32(d, inverse.M24))),
                add32(add32(mul32(x, inverse.M31), mul32(y, inverse.M32)), add32(mul32(z, inverse.M33), mul32(d, inverse.M34))),
                add32(add32(mul32(x, inverse.M41), mul32(y, inverse.M42)), add32(mul32(z, inverse.M43), mul32(d, inverse.M44))),
            )
        if isinstance(transform, Quaternion):
            return Plane(Vector3.Transform(plane.Normal, transform), plane.D)
        raise TypeError("transform must be Matrix or Quaternion")

    def Dot(self, value: Vector4) -> float:
        if not isinstance(value, Vector4):
            raise TypeError("value must be Vector4")
        return add32(add32(mul32(self.Normal.X, value.X), mul32(self.Normal.Y, value.Y)), add32(mul32(self.Normal.Z, value.Z), mul32(self.D, value.W)))

    def DotCoordinate(self, value: Vector3) -> float:
        return add32(Vector3.Dot(self.Normal, _copy_vector(value)), self.D)

    def DotNormal(self, value: Vector3) -> float:
        return Vector3.Dot(self.Normal, _copy_vector(value))

    def Intersects(self, value: object) -> PlaneIntersectionType:
        if isinstance(value, BoundingSphere):
            distance = self.DotCoordinate(value.Center)
            if distance > value.Radius:
                return PlaneIntersectionType.Front
            if distance < -value.Radius:
                return PlaneIntersectionType.Back
            return PlaneIntersectionType.Intersecting
        if isinstance(value, BoundingBox):
            normal = self.Normal
            negative = Vector3(
                value.Min.X if normal.X >= 0 else value.Max.X,
                value.Min.Y if normal.Y >= 0 else value.Max.Y,
                value.Min.Z if normal.Z >= 0 else value.Max.Z,
            )
            positive = Vector3(
                value.Max.X if normal.X >= 0 else value.Min.X,
                value.Max.Y if normal.Y >= 0 else value.Min.Y,
                value.Max.Z if normal.Z >= 0 else value.Min.Z,
            )
            if self.DotCoordinate(negative) > 0:
                return PlaneIntersectionType.Front
            return PlaneIntersectionType.Back if self.DotCoordinate(positive) < 0 else PlaneIntersectionType.Intersecting
        if isinstance(value, BoundingFrustum):
            return value.Intersects(self)
        raise TypeError("Plane.Intersects expects BoundingBox, BoundingSphere, or BoundingFrustum")


class Ray(_StructValue):
    __slots__ = ("_position", "_direction")

    def __init__(self, *args: object) -> None:
        if not args:
            position, direction = Vector3.Zero, Vector3.Zero
        elif len(args) == 2:
            position, direction = args
        else:
            raise TypeError("Ray expects position and direction")
        self.Position = position
        self.Direction = direction

    @property
    def Position(self) -> Vector3:
        return _copy_vector(self._position)

    @Position.setter
    def Position(self, value: Vector3) -> None:
        self._position = _copy_vector(value, name="Position")

    @property
    def Direction(self) -> Vector3:
        return _copy_vector(self._direction)

    @Direction.setter
    def Direction(self, value: Vector3) -> None:
        self._direction = _copy_vector(value, name="Direction")

    def __copy__(self) -> "Ray":
        return Ray(self.Position, self.Direction)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ray) and self.Position == other.Position and self.Direction == other.Direction

    def __hash__(self) -> int:
        return self.GetHashCode()

    def GetHashCode(self) -> int:
        return hash32_sum(self.Position.GetHashCode(), self.Direction.GetHashCode())

    def ToString(self) -> str:
        return f"{{Position:{self.Position} Direction:{self.Direction}}}"

    __str__ = ToString

    def Intersects(self, value: object) -> float | None:
        if isinstance(value, BoundingBox):
            return value.Intersects(self)
        if isinstance(value, BoundingFrustum):
            return value.Intersects(self)
        if isinstance(value, Plane):
            denominator = Vector3.Dot(value.Normal, self.Direction)
            if abs(denominator) < f32(1e-5):
                return None
            distance = div32(-add32(Vector3.Dot(value.Normal, self.Position), value.D), denominator)
            if distance < 0:
                return None if distance < f32(-1e-5) else f32(0)
            return distance
        if isinstance(value, BoundingSphere):
            offset = value.Center - self.Position
            distance_squared = offset.LengthSquared()
            radius_squared = mul32(value.Radius, value.Radius)
            if distance_squared <= radius_squared:
                return f32(0)
            projection = Vector3.Dot(offset, self.Direction)
            if projection < 0:
                return None
            closest_squared = sub32(distance_squared, mul32(projection, projection))
            if closest_squared > radius_squared:
                return None
            return sub32(projection, _sqrt32(sub32(radius_squared, closest_squared)))
        raise TypeError("Ray.Intersects expects BoundingBox, BoundingSphere, BoundingFrustum, or Plane")


class BoundingBox(_StructValue):
    __slots__ = ("_min", "_max")
    CornerCount = 8

    def __init__(self, *args: object) -> None:
        if not args:
            minimum, maximum = Vector3.Zero, Vector3.Zero
        elif len(args) == 2:
            minimum, maximum = args
        else:
            raise TypeError("BoundingBox expects min and max")
        self.Min = minimum
        self.Max = maximum

    @property
    def Min(self) -> Vector3:
        return _copy_vector(self._min)

    @Min.setter
    def Min(self, value: Vector3) -> None:
        self._min = _copy_vector(value, name="Min")

    @property
    def Max(self) -> Vector3:
        return _copy_vector(self._max)

    @Max.setter
    def Max(self, value: Vector3) -> None:
        self._max = _copy_vector(value, name="Max")

    def __copy__(self) -> "BoundingBox":
        return BoundingBox(self.Min, self.Max)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BoundingBox) and self.Min == other.Min and self.Max == other.Max

    def __hash__(self) -> int:
        return self.GetHashCode()

    def GetHashCode(self) -> int:
        return hash32_sum(self.Min.GetHashCode(), self.Max.GetHashCode())

    def ToString(self) -> str:
        return f"{{Min:{self.Min} Max:{self.Max}}}"

    __str__ = ToString

    def GetCorners(self, corners: object = None) -> list[Vector3] | None:
        minimum, maximum = self.Min, self.Max
        values = [
            Vector3(minimum.X, maximum.Y, maximum.Z), Vector3(maximum.X, maximum.Y, maximum.Z),
            Vector3(maximum.X, minimum.Y, maximum.Z), Vector3(minimum.X, minimum.Y, maximum.Z),
            Vector3(minimum.X, maximum.Y, minimum.Z), Vector3(maximum.X, maximum.Y, minimum.Z),
            Vector3(maximum.X, minimum.Y, minimum.Z), Vector3(minimum.X, minimum.Y, minimum.Z),
        ]
        if corners is None:
            return values
        if not hasattr(corners, "__len__") or not hasattr(corners, "__setitem__"):
            raise TypeError("corners must be a mutable sequence")
        if len(corners) < self.CornerCount:
            raise ValueError("corners must contain at least eight entries")
        for index, value in enumerate(values):
            corners[index] = value
        return None

    @staticmethod
    def CreateMerged(original: "BoundingBox", additional: "BoundingBox") -> "BoundingBox":
        if not isinstance(original, BoundingBox) or not isinstance(additional, BoundingBox):
            raise TypeError("CreateMerged expects two BoundingBox values")
        return BoundingBox(Vector3.Min(original.Min, additional.Min), Vector3.Max(original.Max, additional.Max))

    @staticmethod
    def CreateFromSphere(sphere: "BoundingSphere") -> "BoundingBox":
        if not isinstance(sphere, BoundingSphere):
            raise TypeError("sphere must be BoundingSphere")
        radius = Vector3(sphere.Radius)
        return BoundingBox(sphere.Center - radius, sphere.Center + radius)

    @staticmethod
    def CreateFromPoints(points: object) -> "BoundingBox":
        if points is None:
            raise TypeError("points cannot be None")
        try:
            values = list(points)
        except TypeError as error:
            raise TypeError("points must be iterable") from error
        if not values:
            raise ValueError("points must contain at least one point")
        if not all(isinstance(value, Vector3) for value in values):
            raise TypeError("points must contain only Vector3 values")
        minimum = Vector3(f32(3.402823466e38)); maximum = Vector3(f32(-3.402823466e38))
        for value in values:
            minimum, maximum = Vector3.Min(minimum, value), Vector3.Max(maximum, value)
        return BoundingBox(minimum, maximum)

    def Contains(self, value: object) -> ContainmentType:
        minimum, maximum = self.Min, self.Max
        if isinstance(value, Vector3):
            return ContainmentType.Contains if minimum.X <= value.X <= maximum.X and minimum.Y <= value.Y <= maximum.Y and minimum.Z <= value.Z <= maximum.Z else ContainmentType.Disjoint
        if isinstance(value, BoundingBox):
            if maximum.X < value.Min.X or minimum.X > value.Max.X or maximum.Y < value.Min.Y or minimum.Y > value.Max.Y or maximum.Z < value.Min.Z or minimum.Z > value.Max.Z:
                return ContainmentType.Disjoint
            if minimum.X <= value.Min.X and value.Max.X <= maximum.X and minimum.Y <= value.Min.Y and value.Max.Y <= maximum.Y and minimum.Z <= value.Min.Z and value.Max.Z <= maximum.Z:
                return ContainmentType.Contains
            return ContainmentType.Intersects
        if isinstance(value, BoundingSphere):
            closest = Vector3.Clamp(value.Center, minimum, maximum);distance_squared = Vector3.DistanceSquared(value.Center, closest);radius_squared = mul32(value.Radius, value.Radius)
            if distance_squared > radius_squared:
                return ContainmentType.Disjoint
            radius = value.Radius
            contained = (add32(minimum.X,radius) <= value.Center.X <= sub32(maximum.X,radius) and sub32(maximum.X,minimum.X) > radius and add32(minimum.Y,radius) <= value.Center.Y <= sub32(maximum.Y,radius) and sub32(maximum.Y,minimum.Y) > radius and add32(minimum.Z,radius) <= value.Center.Z <= sub32(maximum.Z,radius) and sub32(maximum.X,minimum.X) > radius)
            return ContainmentType.Contains if contained else ContainmentType.Intersects
        if isinstance(value, BoundingFrustum):
            if all(self.Contains(corner) == ContainmentType.Contains for corner in value.GetCorners()):
                return ContainmentType.Contains
            return ContainmentType.Intersects if self.Intersects(value) else ContainmentType.Disjoint
        raise TypeError("BoundingBox.Contains expects Vector3, BoundingBox, BoundingSphere, or BoundingFrustum")

    def Intersects(self, value: object) -> bool | PlaneIntersectionType | float | None:
        minimum, maximum = self.Min, self.Max
        if isinstance(value, BoundingBox):
            return not (maximum.X < value.Min.X or minimum.X > value.Max.X or maximum.Y < value.Min.Y or minimum.Y > value.Max.Y or maximum.Z < value.Min.Z or minimum.Z > value.Max.Z)
        if isinstance(value, BoundingSphere):
            closest = Vector3.Clamp(value.Center, minimum, maximum)
            return Vector3.DistanceSquared(value.Center, closest) <= mul32(value.Radius, value.Radius)
        if isinstance(value, BoundingFrustum):
            return value.Intersects(self)
        if isinstance(value, Plane):
            return value.Intersects(self)
        if isinstance(value, Ray):
            distance, maximum_distance = f32(0), f32(3.402823466e38)
            for position, direction, low, high in ((value.Position.X,value.Direction.X,minimum.X,maximum.X),(value.Position.Y,value.Direction.Y,minimum.Y,maximum.Y),(value.Position.Z,value.Direction.Z,minimum.Z,maximum.Z)):
                if abs(direction) < f32(1e-6):
                    if position < low or position > high:
                        return None
                    continue
                inverse = div32(1,direction);near=mul32(sub32(low,position),inverse);far=mul32(sub32(high,position),inverse)
                if near > far: near,far=far,near
                distance=MathHelper.Max(near,distance);maximum_distance=MathHelper.Min(far,maximum_distance)
                if distance > maximum_distance: return None
            return distance
        raise TypeError("BoundingBox.Intersects received an unsupported value")


class BoundingSphere(_StructValue):
    __slots__ = ("_center", "_radius")

    def __init__(self, *args: object) -> None:
        if not args:
            center, radius = Vector3.Zero, 0.0
        elif len(args) == 2:
            center, radius = args
        else:
            raise TypeError("BoundingSphere expects center and radius")
        self.Center = center
        self.Radius = radius

    @property
    def Center(self) -> Vector3:
        return _copy_vector(self._center)

    @Center.setter
    def Center(self, value: Vector3) -> None:
        self._center = _copy_vector(value, name="Center")

    @property
    def Radius(self) -> float:
        return self._radius

    @Radius.setter
    def Radius(self, value: float) -> None:
        value = f32(value)
        if value < 0:
            raise ValueError("radius must be non-negative")
        self._radius = value

    def __copy__(self) -> "BoundingSphere":
        return BoundingSphere(self.Center, self.Radius)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BoundingSphere) and self.Center == other.Center and self.Radius == other.Radius

    def __hash__(self) -> int:
        return self.GetHashCode()

    def GetHashCode(self) -> int:
        return hash32_sum(self.Center.GetHashCode(), single_hash(self.Radius))

    def ToString(self) -> str:
        return f"{{Center:{self.Center} Radius:{self.Radius:g}}}"

    __str__ = ToString

    @staticmethod
    def CreateFromBoundingBox(box: BoundingBox) -> "BoundingSphere":
        if not isinstance(box, BoundingBox): raise TypeError("box must be BoundingBox")
        center=Vector3.Lerp(box.Min,box.Max,0.5);return BoundingSphere(center,mul32(Vector3.Distance(box.Min,box.Max),0.5))

    @staticmethod
    def CreateMerged(original: "BoundingSphere", additional: "BoundingSphere") -> "BoundingSphere":
        if not isinstance(original,BoundingSphere) or not isinstance(additional,BoundingSphere): raise TypeError("CreateMerged expects two BoundingSphere values")
        difference=additional.Center-original.Center;distance=difference.Length();radius,other=original.Radius,additional.Radius
        if add32(radius,other)>=distance:
            if sub32(radius,other)>=distance:return original.__copy__()
            if sub32(other,radius)>=distance:return additional.__copy__()
        direction=difference*div32(1,distance);minimum=MathHelper.Min(-radius,sub32(distance,other));maximum=MathHelper.Max(radius,add32(distance,other));merged=mul32(sub32(maximum,minimum),0.5)
        return BoundingSphere(original.Center+direction*add32(merged,minimum),merged)

    @staticmethod
    def CreateFromPoints(points: object) -> "BoundingSphere":
        if points is None: raise TypeError("points cannot be None")
        try: values=list(points)
        except TypeError as error: raise TypeError("points must be iterable") from error
        if not values: raise ValueError("points must contain at least one point")
        if not all(isinstance(value,Vector3) for value in values): raise TypeError("points must contain only Vector3 values")
        min_x=max_x=min_y=max_y=min_z=max_z=values[0]
        for value in values:
            if value.X<min_x.X:min_x=value
            if value.X>max_x.X:max_x=value
            if value.Y<min_y.Y:min_y=value
            if value.Y>max_y.Y:max_y=value
            if value.Z<min_z.Z:min_z=value
            if value.Z>max_z.Z:max_z=value
        pairs=((min_x,max_x),(min_y,max_y),(min_z,max_z));distances=[Vector3.Distance(a,b) for a,b in pairs];index=max(range(3),key=lambda i:distances[i]);center=Vector3.Lerp(pairs[index][1],pairs[index][0],0.5);radius=mul32(distances[index],0.5)
        for value in values:
            offset=value-center;distance=offset.Length()
            if distance>radius:
                radius=mul32(add32(radius,distance),0.5);center+=offset*sub32(1,div32(radius,distance))
        return BoundingSphere(center,radius)

    @staticmethod
    def CreateFromFrustum(frustum: "BoundingFrustum") -> "BoundingSphere":
        if not isinstance(frustum,BoundingFrustum):raise TypeError("frustum must be BoundingFrustum")
        return BoundingSphere.CreateFromPoints(frustum.GetCorners())

    def Contains(self,value:object)->ContainmentType:
        if isinstance(value,Vector3):return ContainmentType.Contains if Vector3.DistanceSquared(self.Center,value)<mul32(self.Radius,self.Radius) else ContainmentType.Disjoint
        if isinstance(value,BoundingSphere):
            distance=Vector3.Distance(self.Center,value.Center)
            if add32(self.Radius,value.Radius)<distance:return ContainmentType.Disjoint
            return ContainmentType.Contains if sub32(self.Radius,value.Radius)>=distance else ContainmentType.Intersects
        if isinstance(value,BoundingBox):
            if not value.Intersects(self):return ContainmentType.Disjoint
            radius_squared=mul32(self.Radius,self.Radius)
            return ContainmentType.Contains if all(Vector3.DistanceSquared(self.Center,corner)<=radius_squared for corner in value.GetCorners()) else ContainmentType.Intersects
        if isinstance(value,BoundingFrustum):
            if all(self.Contains(corner)==ContainmentType.Contains for corner in value.GetCorners()):return ContainmentType.Contains
            return ContainmentType.Intersects if self.Intersects(value) else ContainmentType.Disjoint
        raise TypeError("BoundingSphere.Contains received an unsupported value")

    def Intersects(self,value:object)->bool|PlaneIntersectionType|float|None:
        if isinstance(value,BoundingBox):return value.Intersects(self)
        if isinstance(value,BoundingSphere):
            total=add32(self.Radius,value.Radius);return mul32(total,total)>Vector3.DistanceSquared(self.Center,value.Center)
        if isinstance(value,BoundingFrustum):return value.Intersects(self)
        if isinstance(value,Plane):return value.Intersects(self)
        if isinstance(value,Ray):return value.Intersects(self)
        raise TypeError("BoundingSphere.Intersects received an unsupported value")

    def Transform(self,matrix:Matrix)->"BoundingSphere":
        if not isinstance(matrix,Matrix):raise TypeError("matrix must be Matrix")
        lengths=(add32(add32(mul32(matrix.M11,matrix.M11),mul32(matrix.M12,matrix.M12)),mul32(matrix.M13,matrix.M13)),add32(add32(mul32(matrix.M21,matrix.M21),mul32(matrix.M22,matrix.M22)),mul32(matrix.M23,matrix.M23)),add32(add32(mul32(matrix.M31,matrix.M31),mul32(matrix.M32,matrix.M32)),mul32(matrix.M33,matrix.M33)))
        return BoundingSphere(Vector3.Transform(self.Center,matrix),mul32(self.Radius,_sqrt32(max(lengths))))


def _triple_cross(a:Vector3,b:Vector3,c:Vector3)->Vector3:
    return Vector3.Cross(Vector3.Cross(a,b),c)


def _gjk_support(first:object,second:object,direction:Vector3)->Vector3:
    return first._gjk_support(direction)-second._gjk_support(-direction)


def _gjk_update(simplex:list[Vector3])->tuple[bool,Vector3]:
    a=simplex[-1];ao=-a
    if len(simplex)==2:
        b=simplex[-2];ab=b-a
        if Vector3.Dot(ab,ao)>0:
            direction=_triple_cross(ab,ao,ab)
            if direction.LengthSquared()==0: return True,Vector3.Zero
            return False,direction
        simplex[:]=[a];return False,ao
    if len(simplex)==3:
        b,c=simplex[-2],simplex[-3];ab,ac=b-a,c-a;abc=Vector3.Cross(ab,ac)
        if Vector3.Dot(Vector3.Cross(abc,ac),ao)>0:
            if Vector3.Dot(ac,ao)>0:simplex[:]=[c,a];return False,_triple_cross(ac,ao,ac)
            simplex[:]=[b,a] if Vector3.Dot(ab,ao)>0 else [a];return False,_triple_cross(ab,ao,ab) if len(simplex)==2 else ao
        if Vector3.Dot(Vector3.Cross(ab,abc),ao)>0:
            simplex[:]=[b,a] if Vector3.Dot(ab,ao)>0 else [a];return False,_triple_cross(ab,ao,ab) if len(simplex)==2 else ao
        if Vector3.Dot(abc,ao)>0:return False,abc
        simplex[:]=[b,c,a];return False,-abc
    b,c,d=simplex[-2],simplex[-3],simplex[-4];ab,ac,ad=b-a,c-a,d-a
    abc=Vector3.Cross(ab,ac);acd=Vector3.Cross(ac,ad);adb=Vector3.Cross(ad,ab)
    if Vector3.Dot(abc,ao)>0:simplex[:]=[c,b,a];return False,abc
    if Vector3.Dot(acd,ao)>0:simplex[:]=[d,c,a];return False,acd
    if Vector3.Dot(adb,ao)>0:simplex[:]=[b,d,a];return False,adb
    return True,Vector3.Zero


def _gjk_intersects(first:object,second:object)->bool:
    direction=first._gjk_center()-second._gjk_center()
    if direction.LengthSquared()==0:direction=Vector3.UnitX
    simplex=[_gjk_support(first,second,direction)];direction=-simplex[0]
    for _ in range(64):
        if direction.LengthSquared()==0:return True
        point=_gjk_support(first,second,direction)
        if Vector3.Dot(point,direction)<0:return False
        simplex.append(point);contains,direction=_gjk_update(simplex)
        if contains:return True
    return False


class BoundingFrustum:
    __slots__=("_matrix","_planes","_corners")
    CornerCount=8

    def __init__(self,value:Matrix)->None:
        self.Matrix=value

    @property
    def Matrix(self)->Matrix:return self._matrix.__copy__()
    @Matrix.setter
    def Matrix(self,value:Matrix)->None:
        if not isinstance(value,Matrix):raise TypeError("Matrix must be Matrix")
        self._matrix=value.__copy__();m=value
        planes=[Plane(-m.M13,-m.M23,-m.M33,-m.M43),Plane(add32(-m.M14,m.M13),add32(-m.M24,m.M23),add32(-m.M34,m.M33),add32(-m.M44,m.M43)),Plane(sub32(-m.M14,m.M11),sub32(-m.M24,m.M21),sub32(-m.M34,m.M31),sub32(-m.M44,m.M41)),Plane(add32(-m.M14,m.M11),add32(-m.M24,m.M21),add32(-m.M34,m.M31),add32(-m.M44,m.M41)),Plane(add32(-m.M14,m.M12),add32(-m.M24,m.M22),add32(-m.M34,m.M32),add32(-m.M44,m.M42)),Plane(sub32(-m.M14,m.M12),sub32(-m.M24,m.M22),sub32(-m.M34,m.M32),sub32(-m.M44,m.M42))]
        self._planes=[]
        for plane in planes:
            # BoundingFrustum.SetMatrix does not call Plane.Normalize: XNA
            # divides the vector by a shared reciprocal, but divides D by the
            # length directly. The distinction is observable by a few ULPs.
            length=plane.Normal.Length()
            plane.Normal=plane.Normal/length
            plane.D=div32(plane.D,length)
            self._planes.append(plane)
        lines=(self._line(0,2),self._line(3,0),self._line(2,1),self._line(1,3));self._corners=[Vector3.Zero for _ in range(8)]
        self._corners[0]=self._intersection(4,lines[0]);self._corners[3]=self._intersection(5,lines[0]);self._corners[1]=self._intersection(4,lines[1]);self._corners[2]=self._intersection(5,lines[1]);self._corners[4]=self._intersection(4,lines[2]);self._corners[7]=self._intersection(5,lines[2]);self._corners[5]=self._intersection(4,lines[3]);self._corners[6]=self._intersection(5,lines[3])

    def _line(self,first:int,second:int)->Ray:
        p1,p2=self._planes[first],self._planes[second];direction=Vector3.Cross(p1.Normal,p2.Normal);position=Vector3.Cross(p2.Normal*(-p1.D)+p1.Normal*p2.D,direction)/direction.LengthSquared();return Ray(position,direction)
    def _intersection(self,plane_index:int,ray:Ray)->Vector3:
        plane=self._planes[plane_index];distance=div32(sub32(f32(-plane.D),Vector3.Dot(plane.Normal,ray.Position)),Vector3.Dot(plane.Normal,ray.Direction));return ray.Position+ray.Direction*distance
    @property
    def Near(self)->Plane:return _copy_plane(self._planes[0])
    @property
    def Far(self)->Plane:return _copy_plane(self._planes[1])
    @property
    def Left(self)->Plane:return _copy_plane(self._planes[2])
    @property
    def Right(self)->Plane:return _copy_plane(self._planes[3])
    @property
    def Top(self)->Plane:return _copy_plane(self._planes[4])
    @property
    def Bottom(self)->Plane:return _copy_plane(self._planes[5])
    def GetCorners(self,corners:object=None)->list[Vector3]|None:
        values=[_copy_vector(value) for value in self._corners]
        if corners is None:return values
        if not hasattr(corners,"__len__") or not hasattr(corners,"__setitem__"):raise TypeError("corners must be a mutable sequence")
        if len(corners)<8:raise ValueError("corners must contain at least eight entries")
        for index,value in enumerate(values):corners[index]=value
        return None
    def _gjk_center(self)->Vector3:
        result=Vector3.Zero
        for corner in self._corners:result+=corner
        return result/8
    def _gjk_support(self,direction:Vector3)->Vector3:return max(self._corners,key=lambda value:Vector3.Dot(value,direction))
    def Contains(self,value:object)->ContainmentType:
        if isinstance(value,Vector3):return ContainmentType.Disjoint if any(plane.DotCoordinate(value)>f32(1e-5) for plane in self._planes) else ContainmentType.Contains
        if isinstance(value,BoundingBox):
            intersects=False
            for plane in self._planes:
                relation=plane.Intersects(value)
                if relation==PlaneIntersectionType.Front:return ContainmentType.Disjoint
                if relation==PlaneIntersectionType.Intersecting:intersects=True
            return ContainmentType.Intersects if intersects else ContainmentType.Contains
        if isinstance(value,BoundingSphere):
            inside=0
            for plane in self._planes:
                distance=plane.DotCoordinate(value.Center)
                if distance>value.Radius:return ContainmentType.Disjoint
                if distance<-value.Radius:inside+=1
            return ContainmentType.Contains if inside==6 else ContainmentType.Intersects
        if isinstance(value,BoundingFrustum):
            if not self.Intersects(value):return ContainmentType.Disjoint
            return ContainmentType.Contains if all(self.Contains(corner)==ContainmentType.Contains for corner in value._corners) else ContainmentType.Intersects
        raise TypeError("BoundingFrustum.Contains received an unsupported value")
    def Intersects(self,value:object)->bool|PlaneIntersectionType|float|None:
        if isinstance(value,(BoundingBox,BoundingSphere,BoundingFrustum)):return _gjk_intersects(self,value)
        if isinstance(value,Plane):
            mask=0
            for corner in self._corners:
                mask|=1 if value.DotCoordinate(corner)>0 else 2
                if mask==3:return PlaneIntersectionType.Intersecting
            return PlaneIntersectionType.Front if mask==1 else PlaneIntersectionType.Back
        if isinstance(value,Ray):
            if self.Contains(value.Position)==ContainmentType.Contains:return f32(0)
            entry,exit=f32(-3.402823466e38),f32(3.402823466e38)
            for plane in self._planes:
                direction_dot=Vector3.Dot(value.Direction,plane.Normal);position_dot=plane.DotCoordinate(value.Position)
                if abs(direction_dot)<f32(1e-5):
                    if position_dot>0:return None
                    continue
                distance=div32(-position_dot,direction_dot)
                if direction_dot<0:
                    if distance>exit:return None
                    entry=max(entry,distance)
                else:
                    if distance<entry:return None
                    exit=min(exit,distance)
            result=entry if entry>=0 else exit;return result if result>=0 else None
        raise TypeError("BoundingFrustum.Intersects received an unsupported value")
    def Equals(self,other:object)->bool:return self==other
    def GetHashCode(self)->int:return self._matrix.GetHashCode()
    def __eq__(self,other:object)->bool:return isinstance(other,BoundingFrustum) and self._matrix==other._matrix
    def __hash__(self)->int:return self.GetHashCode()
    def ToString(self)->str:return f"{{Near:{self.Near} Far:{self.Far} Left:{self.Left} Right:{self.Right} Top:{self.Top} Bottom:{self.Bottom}}}"
    __str__=ToString


def _box_center(self:BoundingBox)->Vector3:return Vector3.Lerp(self.Min,self.Max,0.5)
def _box_support(self:BoundingBox,direction:Vector3)->Vector3:return Vector3(self.Max.X if direction.X>=0 else self.Min.X,self.Max.Y if direction.Y>=0 else self.Min.Y,self.Max.Z if direction.Z>=0 else self.Min.Z)
def _sphere_center(self:BoundingSphere)->Vector3:return self.Center
def _sphere_support(self:BoundingSphere,direction:Vector3)->Vector3:
    length=direction.Length();return self.Center+direction*div32(self.Radius,length) if length!=0 else self.Center
BoundingBox._gjk_center=_box_center;BoundingBox._gjk_support=_box_support
BoundingSphere._gjk_center=_sphere_center;BoundingSphere._gjk_support=_sphere_support

Plane.__xna_arities__={"__init__":{0,1,2,3,4},"Normalize":{0,1},"Transform":{2},"Intersects":{1}}
Ray.__xna_arities__={"__init__":{0,2},"Intersects":{1}}
BoundingBox.__xna_arities__={"__init__":{0,2},"GetCorners":{0,1},"Contains":{1},"Intersects":{1}}
BoundingSphere.__xna_arities__={"__init__":{0,2},"Contains":{1},"Intersects":{1}}
BoundingFrustum.__xna_arities__={"__init__":{1},"GetCorners":{0,1},"Contains":{1},"Intersects":{1}}
