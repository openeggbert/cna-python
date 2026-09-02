"""Avatars: the description, its animations, and the renderer.

Part of the ``xna40-windows-online`` strict profile, measured against
`Microsoft.Xna.Framework.Avatar.dll`.

Four things are kept apart here, because on a host with no avatar platform only
the first two are real:

* a **structurally valid description** -- a byte array CNA validates, whose body
  type and height are read out of it;
* a **randomly generated** description, which CNA produces deterministically
  enough to be qualified;
* the description **a signed-in gamer owns**, which needs a platform identity;
* **rendering**, which needs a device and the avatar content.

``AvatarDescription.Description`` is the exact bytes CNA holds -- never a zeroed
array standing in for them -- and ``IsValid`` is CNA's answer rather than a
length check invented here.
"""

from __future__ import annotations

import ctypes as c
from datetime import timedelta

from .. import Matrix, Vector3
from .._language import Event
from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import CallbackRoot, checked, string_view

from ._enums import (
    AvatarAnimationPreset, AvatarBodyType, AvatarEye, AvatarEyebrow, AvatarMouth,
    AvatarRendererState,
)
from ._gamer import Gamer, _GamerAsyncResult

__all__ = ["AvatarExpression", "AvatarDescription", "AvatarAnimation",
           "AvatarRenderer", "IAvatarAnimation"]

_support = _on.support
_VERSION = 1
_TICKS_PER_MICROSECOND = 10

#: Registrations for ``AvatarDescription.Changed``, rooted while CNA can call them.
_roots = CallbackRoot()


def _ticks(value: timedelta, what: str) -> int:
    if not isinstance(value, timedelta):
        raise TypeError(f"{what} must be a timedelta, not {type(value).__name__}")
    microseconds = (value.days * 86_400_000_000 + value.seconds * 1_000_000
                    + value.microseconds)
    return microseconds * _TICKS_PER_MICROSECOND


def _timespan(ticks: int) -> timedelta:
    return timedelta(microseconds=int(ticks) // _TICKS_PER_MICROSECOND)


def _matrix(value) -> Matrix:
    return Matrix(*(float(getattr(value, f"m{row}{column}"))
                    for row in range(1, 5) for column in range(1, 5)))


def _to_matrix(value: Matrix):
    from _cna_native import abi

    native = abi.CNA_Matrix()
    for row in range(1, 5):
        for column in range(1, 5):
            setattr(native, f"m{row}{column}",
                    float(getattr(value, f"M{row}{column}")))
    return native


def _to_vector(value: Vector3):
    from _cna_native import abi

    native = abi.CNA_Vector3()
    native.x, native.y, native.z = float(value.X), float(value.Y), float(value.Z)
    return native


class IAvatarAnimation:
    """XNA's animation protocol: what a renderer needs from an animation.

    Python has no interfaces, so this is the protocol as a base class -- the
    same choice this projection already makes for ``IPackedVector`` and the
    effect interfaces. Every member raises here; an implementer overrides them.
    """

    __slots__ = ()

    def Update(self, elapsedAnimationTime: timedelta, loop: bool) -> None:
        raise NotImplementedError

    @property
    def BoneTransforms(self) -> tuple[Matrix, ...]:
        raise NotImplementedError

    @property
    def CurrentPosition(self) -> timedelta:
        raise NotImplementedError

    @CurrentPosition.setter
    def CurrentPosition(self, value: timedelta) -> None:
        raise NotImplementedError

    @property
    def Length(self) -> timedelta:
        raise NotImplementedError

    @property
    def Expression(self) -> "AvatarExpression":
        raise NotImplementedError


class AvatarExpression:
    """The five parts of an avatar's face.

    A value type in XNA and a value here: equality is field-wise and an instance
    is copied rather than shared.
    """

    __slots__ = ("_mouth", "_left_eye", "_right_eye", "_left_eyebrow",
                 "_right_eyebrow")

    def __init__(self) -> None:
        self._mouth = AvatarMouth(0)
        self._left_eye = AvatarEye(0)
        self._right_eye = AvatarEye(0)
        self._left_eyebrow = AvatarEyebrow(0)
        self._right_eyebrow = AvatarEyebrow(0)

    @classmethod
    def _from_native(cls, value) -> "AvatarExpression":
        expression = cls()
        expression._mouth = AvatarMouth(int(value.mouth))
        expression._left_eye = AvatarEye(int(value.left_eye))
        expression._right_eye = AvatarEye(int(value.right_eye))
        expression._left_eyebrow = AvatarEyebrow(int(value.left_eyebrow))
        expression._right_eyebrow = AvatarEyebrow(int(value.right_eyebrow))
        return expression

    def _to_native(self):
        native = _on.in_struct(_online.CNA_AvatarExpression, _VERSION)
        native.mouth = int(self._mouth)
        native.left_eye = int(self._left_eye)
        native.right_eye = int(self._right_eye)
        native.left_eyebrow = int(self._left_eyebrow)
        native.right_eyebrow = int(self._right_eyebrow)
        return native

    @property
    def Mouth(self) -> AvatarMouth:
        return self._mouth

    @Mouth.setter
    def Mouth(self, value: AvatarMouth) -> None:
        self._mouth = AvatarMouth(value)

    @property
    def LeftEye(self) -> AvatarEye:
        return self._left_eye

    @LeftEye.setter
    def LeftEye(self, value: AvatarEye) -> None:
        self._left_eye = AvatarEye(value)

    @property
    def RightEye(self) -> AvatarEye:
        return self._right_eye

    @RightEye.setter
    def RightEye(self, value: AvatarEye) -> None:
        self._right_eye = AvatarEye(value)

    @property
    def LeftEyebrow(self) -> AvatarEyebrow:
        return self._left_eyebrow

    @LeftEyebrow.setter
    def LeftEyebrow(self, value: AvatarEyebrow) -> None:
        self._left_eyebrow = AvatarEyebrow(value)

    @property
    def RightEyebrow(self) -> AvatarEyebrow:
        return self._right_eyebrow

    @RightEyebrow.setter
    def RightEyebrow(self, value: AvatarEyebrow) -> None:
        self._right_eyebrow = AvatarEyebrow(value)

    def _key(self):
        return (self._mouth, self._left_eye, self._right_eye, self._left_eyebrow,
                self._right_eyebrow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AvatarExpression):
            return NotImplemented
        return self._key() == other._key()

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self) -> int:
        return hash(self._key())

    def __copy__(self) -> "AvatarExpression":
        return AvatarExpression._from_native(self._to_native())

    def __deepcopy__(self, memo: object) -> "AvatarExpression":
        return self.__copy__()


class AvatarDescription:
    """The bytes that describe one avatar."""

    __slots__ = ("_handle", "_disposed")

    #: XNA raises this when the signed-in gamer changes their avatar.
    Changed = Event(static=True)

    def __init__(self, data) -> None:
        payload = bytes(data)
        buffer = (c.c_uint8 * len(payload))(*payload) if payload else None
        self._handle = _support.out_handle(
            "cna_avatar_description_create", buffer, c.c_uint64(len(payload)))
        self._disposed = False

    @classmethod
    def _adopt(cls, handle: int) -> "AvatarDescription":
        description = cls.__new__(cls)
        description._handle = int(handle)
        description._disposed = False
        return description

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("AvatarDescription has been disposed")
        return c.c_uint64(self._handle)

    def _read(self):
        return _support.out_struct(_online.CNA_AvatarDescriptionInfo, _VERSION,
                                   "cna_avatar_description_get_info", self._value)

    @staticmethod
    def CreateRandom(bodyType: AvatarBodyType | None = None) -> "AvatarDescription":
        """A randomly generated description, optionally of one body type."""
        if bodyType is None:
            return AvatarDescription._adopt(_support.out_handle(
                "cna_avatar_description_create_random"))
        return AvatarDescription._adopt(_support.out_handle(
            "cna_avatar_description_create_random_for_body_type",
            c.c_uint32(int(AvatarBodyType(bodyType)))))

    @staticmethod
    def BeginGetFromGamer(gamer: Gamer, callback: object, state: object) -> object:
        """Asks the platform for the avatar a gamer owns."""
        if not isinstance(gamer, Gamer):
            raise TypeError("gamer must be a Gamer")
        return _GamerAsyncResult.begin(
            "GetAvatarFromGamer", state, callback,
            lambda: _support.out_handle(
                "cna_avatar_description_get_from_gamer", gamer._value,
                _on.no_callback(_online.CNA_GamerAsyncCallback), None))

    @staticmethod
    def EndGetFromGamer(result: object) -> "AvatarDescription":
        return AvatarDescription._adopt(
            _GamerAsyncResult.end(result, "GetAvatarFromGamer"))

    def _release(self) -> None:
        """Releases the description handle exactly once."""
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call("cna_avatar_description_destroy", c.c_uint64(self._handle))
        self._handle = 0

    @property
    def IsValid(self) -> bool:
        """CNA's own validity answer, not a length check invented here."""
        return bool(self._read().is_valid)

    @property
    def Description(self) -> list[int]:
        """The exact description bytes.

        The size comes from CNA and the copy is sized to it, so a description
        that grew is never truncated into a shorter one that still looks valid.
        """
        size = int(self._read().description_byte_count)
        if not size:
            return []
        buffer = (c.c_uint8 * size)()
        written = c.c_uint64()
        _support.call("cna_avatar_description_copy_description", self._value,
                      buffer, c.c_uint64(size), c.byref(written))
        return [int(buffer[index]) for index in range(int(written.value))]

    @property
    def Height(self) -> float:
        return float(self._read().height)

    @property
    def BodyType(self) -> AvatarBodyType:
        return AvatarBodyType(int(self._read().body_type))


AvatarDescription.__xna_arities__ = {"CreateRandom": {0, 1}}


class AvatarAnimation(IAvatarAnimation):
    """One of the avatar animations the platform ships."""

    __slots__ = ("_handle", "_disposed")

    def __init__(self, animationPreset: AvatarAnimationPreset) -> None:
        self._handle = _support.out_handle(
            "cna_avatar_animation_create",
            c.c_uint32(int(AvatarAnimationPreset(animationPreset))))
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("AvatarAnimation has been disposed")
        return c.c_uint64(self._handle)

    def _read(self):
        return _support.out_struct(_online.CNA_AvatarAnimationInfo, _VERSION,
                                   "cna_avatar_animation_get_info", self._value)

    def Update(self, elapsedAnimationTime: timedelta, loop: bool) -> None:
        _support.call("cna_avatar_animation_update", self._value,
                      c.c_int64(_ticks(elapsedAnimationTime, "elapsedAnimationTime")),
                      c.c_uint8(1 if loop else 0))

    @property
    def Length(self) -> timedelta:
        return _timespan(self._read().length_ticks)

    @property
    def CurrentPosition(self) -> timedelta:
        return _timespan(self._read().current_position_ticks)

    @CurrentPosition.setter
    def CurrentPosition(self, value: timedelta) -> None:
        _support.call("cna_avatar_animation_set_current_position", self._value,
                      c.c_int64(_ticks(value, "CurrentPosition")))

    @property
    def BoneTransforms(self) -> tuple[Matrix, ...]:
        from _cna_native import abi

        count = int(self._read().bone_transform_count)
        result = []
        for index in range(count):
            value = abi.CNA_Matrix()
            _support.call("cna_avatar_animation_get_bone_transform_at", self._value,
                          c.c_int32(index), c.byref(value))
            result.append(_matrix(value))
        return tuple(result)

    @property
    def Expression(self) -> AvatarExpression:
        return AvatarExpression._from_native(_support.out_struct(
            _online.CNA_AvatarExpression, _VERSION,
            "cna_avatar_animation_get_expression", self._value))

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self, disposing: bool = True) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call("cna_avatar_animation_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self) -> "AvatarAnimation":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()


AvatarAnimation.__xna_arities__ = {"Dispose": {0, 1}}


class AvatarRenderer:
    """Draws an avatar.

    Constructing one needs a valid description; *drawing* needs the avatar
    content and a device, which a host without the avatar platform does not
    have. :attr:`State` is how a caller finds that out -- it answers
    ``Unavailable`` rather than this package pretending a draw happened.
    """

    __slots__ = ("_handle", "_disposed")

    #: How many bones an avatar skeleton has, from the pinned contract.
    BoneCount = 71

    def __init__(self, avatarDescription: AvatarDescription,
                 useLoadingEffect: bool = True) -> None:
        if not isinstance(avatarDescription, AvatarDescription):
            raise TypeError("avatarDescription must be an AvatarDescription")
        self._handle = _support.out_handle(
            "cna_avatar_renderer_create", avatarDescription._value,
            c.c_uint8(1 if useLoadingEffect else 0))
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError("AvatarRenderer has been disposed")
        return c.c_uint64(self._handle)

    def _read(self):
        return _support.out_struct(_online.CNA_AvatarRendererInfo, _VERSION,
                                   "cna_avatar_renderer_get_info", self._value)

    def _transforms(self):
        from _cna_native import abi

        world, view, projection = abi.CNA_Matrix(), abi.CNA_Matrix(), abi.CNA_Matrix()
        _support.call("cna_avatar_renderer_get_transforms", self._value,
                      c.byref(world), c.byref(view), c.byref(projection))
        return world, view, projection

    def _set_transforms(self, world: Matrix, view: Matrix, projection: Matrix) -> None:
        native_world = _to_matrix(world)
        native_view = _to_matrix(view)
        native_projection = _to_matrix(projection)
        _support.call("cna_avatar_renderer_set_transforms", self._value,
                      c.byref(native_world), c.byref(native_view),
                      c.byref(native_projection))

    @property
    def World(self) -> Matrix:
        return _matrix(self._transforms()[0])

    @World.setter
    def World(self, value: Matrix) -> None:
        world, view, projection = self._transforms()
        self._set_transforms(value, _matrix(view), _matrix(projection))

    @property
    def View(self) -> Matrix:
        return _matrix(self._transforms()[1])

    @View.setter
    def View(self, value: Matrix) -> None:
        world, view, projection = self._transforms()
        self._set_transforms(_matrix(world), value, _matrix(projection))

    @property
    def Projection(self) -> Matrix:
        return _matrix(self._transforms()[2])

    @Projection.setter
    def Projection(self, value: Matrix) -> None:
        world, view, projection = self._transforms()
        self._set_transforms(_matrix(world), _matrix(view), value)

    def _lighting(self):
        from _cna_native import abi

        colour = abi.CNA_Vector3()
        direction = abi.CNA_Vector3()
        ambient = abi.CNA_Vector3()
        _support.call("cna_avatar_renderer_get_lighting", self._value,
                      c.byref(colour), c.byref(direction), c.byref(ambient))
        return colour, direction, ambient

    def _set_lighting(self, colour: Vector3, direction: Vector3,
                      ambient: Vector3) -> None:
        native_colour = _to_vector(colour)
        native_direction = _to_vector(direction)
        native_ambient = _to_vector(ambient)
        _support.call("cna_avatar_renderer_set_lighting", self._value,
                      c.byref(native_colour), c.byref(native_direction),
                      c.byref(native_ambient))

    @staticmethod
    def _vector(value) -> Vector3:
        return Vector3(float(value.x), float(value.y), float(value.z))

    @property
    def LightColor(self) -> Vector3:
        return AvatarRenderer._vector(self._lighting()[0])

    @LightColor.setter
    def LightColor(self, value: Vector3) -> None:
        _colour, direction, ambient = self._lighting()
        self._set_lighting(value, AvatarRenderer._vector(direction),
                           AvatarRenderer._vector(ambient))

    @property
    def LightDirection(self) -> Vector3:
        return AvatarRenderer._vector(self._lighting()[1])

    @LightDirection.setter
    def LightDirection(self, value: Vector3) -> None:
        colour, _direction, ambient = self._lighting()
        self._set_lighting(AvatarRenderer._vector(colour), value,
                           AvatarRenderer._vector(ambient))

    @property
    def AmbientLightColor(self) -> Vector3:
        return AvatarRenderer._vector(self._lighting()[2])

    @AmbientLightColor.setter
    def AmbientLightColor(self, value: Vector3) -> None:
        colour, direction, _ambient = self._lighting()
        self._set_lighting(AvatarRenderer._vector(colour),
                           AvatarRenderer._vector(direction), value)

    @property
    def State(self) -> AvatarRendererState:
        return AvatarRendererState(int(self._read().state))

    @property
    def ParentBones(self) -> tuple[int, ...]:
        return tuple(
            _support.out_i32("cna_avatar_renderer_get_parent_bone_at", self._value,
                             c.c_int32(index))
            for index in range(AvatarRenderer.BoneCount))

    @property
    def BindPose(self) -> tuple[Matrix, ...]:
        from _cna_native import abi

        result = []
        for index in range(AvatarRenderer.BoneCount):
            value = abi.CNA_Matrix()
            _support.call("cna_avatar_renderer_get_bind_pose_at", self._value,
                          c.c_int32(index), c.byref(value))
            result.append(_matrix(value))
        return tuple(result)

    def Draw(self, *args: object) -> None:
        """XNA's two overloads: an animation, or explicit bones and expression."""
        if len(args) == 1:
            animation = args[0]
            if isinstance(animation, AvatarAnimation):
                _support.call("cna_avatar_renderer_draw_animation", self._value,
                              animation._value)
                return
            raise TypeError("Draw takes an AvatarAnimation, or bones and an "
                            "expression")
        if len(args) == 2:
            from _cna_native import abi

            bones, expression = args
            if not isinstance(expression, AvatarExpression):
                raise TypeError("expression must be an AvatarExpression")
            values = tuple(bones)
            array = (abi.CNA_Matrix * len(values))() if values else None
            for index, bone in enumerate(values):
                array[index] = _to_matrix(bone)
            native_expression = expression._to_native()
            _support.call("cna_avatar_renderer_draw_bones", self._value, array,
                          c.c_uint64(len(values)), c.byref(native_expression))
            return
        raise TypeError("no matching Draw overload")

    @property
    def IsDisposed(self) -> bool:
        return self._disposed

    def Dispose(self, disposing: bool = True) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call("cna_avatar_renderer_destroy", c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self) -> "AvatarRenderer":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()


AvatarRenderer.__xna_arities__ = {"Draw": {1, 2}, "Dispose": {0, 1}}
