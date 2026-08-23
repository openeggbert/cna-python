"""Pure managed XNA 4.0 scalar curves."""

from __future__ import annotations

import math
from enum import IntEnum
from typing import Iterator, MutableSequence

from ._numeric import add32, div32, f32, hash32_sum, int32, mul32, single_hash, sub32


class CurveContinuity(IntEnum):
    Smooth = 0
    Step = 1


class CurveLoopType(IntEnum):
    Constant = 0
    Cycle = 1
    CycleOffset = 2
    Oscillate = 3
    Linear = 4


class CurveTangent(IntEnum):
    Flat = 0
    Linear = 1
    Smooth = 2


def _enum(value: object, enum_type: type[IntEnum], name: str):
    if not isinstance(value, enum_type):
        raise TypeError(f"{name} must be {enum_type.__name__}")
    return value


class CurveKey:
    __slots__ = ("_position", "_value", "_tangent_in", "_tangent_out", "_continuity")

    def __init__(self, *args: object) -> None:
        if len(args) == 2:
            position, value = args
            tangent_in = tangent_out = 0.0
            continuity = CurveContinuity.Smooth
        elif len(args) == 4:
            position, value, tangent_in, tangent_out = args
            continuity = CurveContinuity.Smooth
        elif len(args) == 5:
            position, value, tangent_in, tangent_out, continuity = args
        else:
            raise TypeError("CurveKey expects position, value[, tangentIn, tangentOut[, continuity]]")
        self._position = f32(position)
        self.Value = value
        self.TangentIn = tangent_in
        self.TangentOut = tangent_out
        self.Continuity = continuity

    @property
    def Position(self) -> float:
        return self._position

    @property
    def Value(self) -> float:
        return self._value

    @Value.setter
    def Value(self, value: float) -> None:
        self._value = f32(value)

    @property
    def TangentIn(self) -> float:
        return self._tangent_in

    @TangentIn.setter
    def TangentIn(self, value: float) -> None:
        self._tangent_in = f32(value)

    @property
    def TangentOut(self) -> float:
        return self._tangent_out

    @TangentOut.setter
    def TangentOut(self, value: float) -> None:
        self._tangent_out = f32(value)

    @property
    def Continuity(self) -> CurveContinuity:
        return self._continuity

    @Continuity.setter
    def Continuity(self, value: CurveContinuity) -> None:
        self._continuity = _enum(value, CurveContinuity, "Continuity")

    def Clone(self) -> "CurveKey":
        return CurveKey(self.Position, self.Value, self.TangentIn, self.TangentOut, self.Continuity)

    def CompareTo(self, other: "CurveKey") -> int:
        if not isinstance(other, CurveKey):
            raise TypeError("other must be CurveKey")
        if self.Position == other.Position:
            return 0
        return -1 if self.Position < other.Position else 1

    def Equals(self, other: object) -> bool:
        return (
            isinstance(other, CurveKey)
            and self.Position == other.Position
            and self.Value == other.Value
            and self.TangentIn == other.TangentIn
            and self.TangentOut == other.TangentOut
            and self.Continuity == other.Continuity
        )

    def GetHashCode(self) -> int:
        return hash32_sum(
            single_hash(self.Position), single_hash(self.Value),
            single_hash(self.TangentIn), single_hash(self.TangentOut), int(self.Continuity),
        )

    def __eq__(self, other: object) -> bool:
        return self.Equals(other)

    def __ne__(self, other: object) -> bool:
        return not self.Equals(other)

    def __hash__(self) -> int:
        return self.GetHashCode()

    def __copy__(self) -> "CurveKey":
        return self.Clone()

    def __deepcopy__(self, memo: object) -> "CurveKey":
        return self.Clone()

    def __repr__(self) -> str:
        return f"CurveKey({self.Position!r}, {self.Value!r}, {self.TangentIn!r}, {self.TangentOut!r}, {self.Continuity!r})"


class CurveKeyCollection:
    __slots__ = ("_keys", "_time_range", "_inverse_time_range", "_cache_available")

    def __init__(self) -> None:
        self._keys: list[CurveKey] = []
        self._time_range = f32(0.0)
        self._inverse_time_range = f32(0.0)
        self._cache_available = True

    @property
    def Count(self) -> int:
        return len(self._keys)

    @property
    def IsReadOnly(self) -> bool:
        return False

    def __getitem__(self, index: int) -> CurveKey:
        index = self._index(index)
        return self._keys[index]

    def __setitem__(self, index: int, value: CurveKey) -> None:
        index = self._index(index)
        self._require_key(value)
        old_position = self._keys[index].Position
        if old_position == value.Position:
            self._keys[index] = value
            return
        self._keys.pop(index)
        self.Add(value)

    def __len__(self) -> int:
        return len(self._keys)

    def __iter__(self) -> Iterator[CurveKey]:
        return iter(self._keys)

    @staticmethod
    def _require_key(value: object) -> CurveKey:
        if not isinstance(value, CurveKey):
            raise TypeError("item must be CurveKey")
        return value

    def _index(self, value: object) -> int:
        index = int32(value, name="index")
        if index < 0 or index >= len(self._keys):
            raise IndexError("CurveKeyCollection index is out of range")
        return index

    def IndexOf(self, item: CurveKey) -> int:
        self._require_key(item)
        for index, value in enumerate(self._keys):
            if value == item:
                return index
        return -1

    def RemoveAt(self, index: int) -> None:
        self._keys.pop(self._index(index))
        self._cache_available = False

    def Add(self, item: CurveKey) -> None:
        item = self._require_key(item)
        low, high = 0, len(self._keys) - 1
        found = -1
        while low <= high:
            middle = low + ((high - low) >> 1)
            comparison = self._keys[middle].CompareTo(item)
            if comparison == 0:
                found = middle
                break
            if comparison < 0:
                low = middle + 1
            else:
                high = middle - 1
        index = found if found >= 0 else low
        if found >= 0:
            while index < len(self._keys) and item.Position == self._keys[index].Position:
                index += 1
        self._keys.insert(index, item)
        self._cache_available = False

    def Clear(self) -> None:
        self._keys.clear()
        self._time_range = f32(0.0)
        self._inverse_time_range = f32(0.0)
        self._cache_available = False

    def Contains(self, item: CurveKey) -> bool:
        return self.IndexOf(item) >= 0

    def CopyTo(self, array: MutableSequence[CurveKey], arrayIndex: int) -> None:
        if not hasattr(array, "__len__") or not hasattr(array, "__setitem__"):
            raise TypeError("array must be a mutable sequence")
        index = int32(arrayIndex, name="arrayIndex")
        if index < 0:
            raise IndexError("arrayIndex must be nonnegative")
        if index + len(self._keys) > len(array):
            raise ValueError("destination array is too small")
        for offset, item in enumerate(self._keys):
            array[index + offset] = item
        self._cache_available = False

    def Remove(self, item: CurveKey) -> bool:
        self._require_key(item)
        self._cache_available = False
        index = self.IndexOf(item)
        if index < 0:
            return False
        self._keys.pop(index)
        return True

    def GetEnumerator(self) -> Iterator[CurveKey]:
        return iter(self._keys)

    def Clone(self) -> "CurveKeyCollection":
        result = CurveKeyCollection()
        result._keys = list(self._keys)
        result._time_range = self._time_range
        result._inverse_time_range = self._inverse_time_range
        result._cache_available = True
        return result

    def _ensure_cache(self) -> None:
        if self._cache_available:
            return
        self._time_range = f32(0.0)
        self._inverse_time_range = f32(0.0)
        if len(self._keys) > 1:
            self._time_range = sub32(self._keys[-1].Position, self._keys[0].Position)
            if self._time_range > math.ldexp(1.0, -149):
                self._inverse_time_range = div32(1.0, self._time_range)
        self._cache_available = True

    @property
    def _range(self) -> tuple[float, float]:
        self._ensure_cache()
        return self._time_range, self._inverse_time_range


class Curve:
    __slots__ = ("_keys", "_pre_loop", "_post_loop")

    def __init__(self) -> None:
        self._keys = CurveKeyCollection()
        self._pre_loop = CurveLoopType.Constant
        self._post_loop = CurveLoopType.Constant

    @property
    def PreLoop(self) -> CurveLoopType:
        return self._pre_loop

    @PreLoop.setter
    def PreLoop(self, value: CurveLoopType) -> None:
        self._pre_loop = _enum(value, CurveLoopType, "PreLoop")

    @property
    def PostLoop(self) -> CurveLoopType:
        return self._post_loop

    @PostLoop.setter
    def PostLoop(self, value: CurveLoopType) -> None:
        self._post_loop = _enum(value, CurveLoopType, "PostLoop")

    @property
    def Keys(self) -> CurveKeyCollection:
        return self._keys

    @property
    def IsConstant(self) -> bool:
        return self.Keys.Count <= 1

    def Clone(self) -> "Curve":
        result = Curve()
        result._keys = self.Keys.Clone()
        result.PreLoop = self.PreLoop
        result.PostLoop = self.PostLoop
        return result

    def ComputeTangent(self, *args: object) -> None:
        if len(args) == 2:
            key_index, tangent_in = args
            tangent_out = tangent_in
        elif len(args) == 3:
            key_index, tangent_in, tangent_out = args
        else:
            raise TypeError("ComputeTangent expects keyIndex and one or two tangent modes")
        index = int32(key_index, name="keyIndex")
        if index < 0 or index >= self.Keys.Count:
            raise IndexError("keyIndex is out of range")
        tangent_in = _enum(tangent_in, CurveTangent, "tangentInType")
        tangent_out = _enum(tangent_out, CurveTangent, "tangentOutType")
        key = self.Keys[index]
        previous = self.Keys[index - 1] if index > 0 else key
        following = self.Keys[index + 1] if index + 1 < self.Keys.Count else key
        key.TangentIn = self._tangent(key, previous, following, tangent_in, True)
        key.TangentOut = self._tangent(key, previous, following, tangent_out, False)

    @staticmethod
    def _tangent(key: CurveKey, previous: CurveKey, following: CurveKey,
                 tangent: CurveTangent, incoming: bool) -> float:
        if tangent is CurveTangent.Linear:
            return sub32(key.Value, previous.Value) if incoming else sub32(following.Value, key.Value)
        if tangent is not CurveTangent.Smooth:
            return f32(0.0)
        position_span = sub32(following.Position, previous.Position)
        value_span = sub32(following.Value, previous.Value)
        if abs(value_span) < f32(1.1920929e-7):
            return f32(0.0)
        side_span = abs(sub32(previous.Position if incoming else following.Position, key.Position))
        return div32(mul32(value_span, side_span), position_span)

    def ComputeTangents(self, *args: object) -> None:
        if len(args) == 1:
            tangent_in = tangent_out = args[0]
        elif len(args) == 2:
            tangent_in, tangent_out = args
        else:
            raise TypeError("ComputeTangents expects one or two tangent modes")
        tangent_in = _enum(tangent_in, CurveTangent, "tangentInType")
        tangent_out = _enum(tangent_out, CurveTangent, "tangentOutType")
        for index in range(self.Keys.Count):
            self.ComputeTangent(index, tangent_in, tangent_out)

    def Evaluate(self, position: float) -> float:
        position = f32(position)
        if self.Keys.Count == 0:
            return f32(0.0)
        if self.Keys.Count == 1:
            return self.Keys[0].Value
        first, last = self.Keys[0], self.Keys[self.Keys.Count - 1]
        virtual_position = position
        value_offset = f32(0.0)
        if virtual_position < first.Position:
            if self.PreLoop is CurveLoopType.Constant:
                return first.Value
            if self.PreLoop is CurveLoopType.Linear:
                return sub32(first.Value, mul32(first.TangentIn, sub32(first.Position, virtual_position)))
            virtual_position, value_offset = self._loop_position(virtual_position, first, last, self.PreLoop)
        elif last.Position < virtual_position:
            if self.PostLoop is CurveLoopType.Constant:
                return last.Value
            if self.PostLoop is CurveLoopType.Linear:
                return sub32(last.Value, mul32(last.TangentOut, sub32(last.Position, virtual_position)))
            virtual_position, value_offset = self._loop_position(virtual_position, first, last, self.PostLoop)
        start, end, amount = self._find_segment(virtual_position)
        return add32(value_offset, self._hermite(start, end, amount))

    def _calculate_cycle(self, position: float) -> float:
        _, inverse_range = self.Keys._range
        cycle = mul32(sub32(position, self.Keys[0].Position), inverse_range)
        if cycle < 0.0:
            cycle = sub32(cycle, 1.0)
        if not math.isfinite(cycle) or cycle < -2_147_483_648 or cycle > 2_147_483_647:
            integer = -2_147_483_648
        else:
            integer = int(cycle)
        return f32(integer)

    def _loop_position(self, position: float, first: CurveKey, last: CurveKey,
                       mode: CurveLoopType) -> tuple[float, float]:
        time_range, _ = self.Keys._range
        cycle = self._calculate_cycle(position)
        cycle_position = sub32(position, add32(first.Position, mul32(cycle, time_range)))
        offset = f32(0.0)
        if mode is CurveLoopType.Cycle:
            position = add32(first.Position, cycle_position)
        elif mode is CurveLoopType.CycleOffset:
            position = add32(first.Position, cycle_position)
            offset = mul32(sub32(last.Value, first.Value), cycle)
        else:
            position = (add32(first.Position, cycle_position) if int(cycle) & 1 == 0
                        else sub32(last.Position, cycle_position))
        return position, offset

    def _find_segment(self, position: float) -> tuple[CurveKey, CurveKey, float]:
        amount = position
        start = self.Keys[0]
        end = self.Keys[1]
        for index in range(1, self.Keys.Count):
            end = self.Keys[index]
            if end.Position >= position:
                span = float(end.Position) - float(start.Position)
                amount = f32(0.0)
                if span > 1e-10:
                    amount = f32((float(position) - float(start.Position)) / span)
                return start, end, amount
            start = end
        return start, end, amount

    @staticmethod
    def _hermite(start: CurveKey, end: CurveKey, amount: float) -> float:
        if start.Continuity is CurveContinuity.Step:
            return start.Value if amount < 1.0 else end.Value
        squared = mul32(amount, amount)
        cubed = mul32(squared, amount)
        first_basis = add32(sub32(mul32(2.0, cubed), mul32(3.0, squared)), 1.0)
        second_basis = add32(mul32(-2.0, cubed), mul32(3.0, squared))
        first_tangent = add32(sub32(cubed, mul32(2.0, squared)), amount)
        second_tangent = sub32(cubed, squared)
        result = add32(mul32(start.Value, first_basis), mul32(end.Value, second_basis))
        result = add32(result, mul32(start.TangentOut, first_tangent))
        return add32(result, mul32(end.TangentIn, second_tangent))


CurveKey.__xna_arities__ = {
    "__init__": {2, 4, 5}, "Clone": {0}, "Equals": {1}, "GetHashCode": {0},
    "__eq__": {1}, "__ne__": {1}, "CompareTo": {1},
}
CurveKeyCollection.__xna_arities__ = {
    "__init__": {0}, "IndexOf": {1}, "RemoveAt": {1}, "Add": {1}, "Clear": {0},
    "Contains": {1}, "CopyTo": {2}, "Remove": {1}, "GetEnumerator": {0}, "Clone": {0},
    "__getitem__": {1},
}
Curve.__xna_arities__ = {
    "__init__": {0}, "Clone": {0}, "ComputeTangent": {2, 3},
    "ComputeTangents": {1, 2}, "Evaluate": {1},
}
