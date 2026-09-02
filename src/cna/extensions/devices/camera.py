"""The device camera: enumeration, state, and frames.

Two things are deliberately kept apart here, because conflating them is how a
qualification claims hardware it never touched.

**Enumeration** -- how many cameras there are, what they are called, which way
they face -- is non-invasive: it opens nothing and captures nothing.

**Capture** opens a physical camera. This package never does that implicitly:
:class:`Camera` is constructed explicitly, and
:func:`~cna.extensions.devices.testing.open_test_camera` opens one over CNA's
deterministic backend instead, which is what the qualification uses. A frame
that came from the test backend is evidence about the frame protocol, not about
any camera.

A frame is acquired *into a caller-owned* ``Texture2D``: CNA writes the pixels
into the texture and reports whether a new frame was there at all. The texture
is borrowed for the call and not retained.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from typing import TYPE_CHECKING

from _cna_native import devices_abi as _devices
from _cna_native import devices_support as _dev
from _cna_native.family_support import checked

from .values import CameraPosition, CameraState

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game
    from Microsoft.Xna.Framework.Graphics import Texture2D

__all__ = ["CameraDeviceInfo", "Camera", "camera_count", "camera_info",
           "camera_name", "cameras", "is_camera_supported"]

_support = _dev.support
_VERSION = 1


@dataclass(frozen=True, slots=True)
class CameraDeviceInfo:
    """One enumerated camera: its index, its name, and which way it faces."""

    index: int
    name: str
    position: CameraPosition


def is_camera_supported(game: "Game") -> bool:
    """Whether this host has any camera at all, asked of CNA."""
    return _support.out_bool("cna_camera_get_is_supported_ext",
                             _dev.game_handle(game, "camera support"))


def camera_count(game: "Game") -> int:
    """How many cameras the host reports. Zero is a real answer, not a failure."""
    return _support.out_u64("cna_camera_get_count_ext",
                            _dev.game_handle(game, "camera count"))


def camera_name(game: "Game", index: int) -> str:
    """The name of one enumerated camera."""
    handle = _dev.game_handle(game, "camera name")
    return _support.copied_text(
        "cna_camera_copy_name_at_ext",
        (handle, c.c_uint64(checked(index, "uint64", "index"))), "camera name")


def camera_info(game: "Game", index: int) -> CameraDeviceInfo:
    """Everything CNA reports about one enumerated camera."""
    handle = _dev.game_handle(game, "camera info")
    native = _support.out_struct(
        _devices.CNA_CameraDeviceInfo, _VERSION, "cna_camera_get_info_at_ext",
        handle, c.c_uint64(checked(index, "uint64", "index")))
    return CameraDeviceInfo(int(index), camera_name(game, index),
                            CameraPosition(int(native.position)))


def cameras(game: "Game") -> list[CameraDeviceInfo]:
    """Every camera the host reports, in CNA's order.

    An empty list is host evidence: it means this machine has no camera, which
    is a measurement rather than a failure.
    """
    return [camera_info(game, index) for index in range(camera_count(game))]


class Camera:
    """One opened camera.

    Constructing this opens a **physical** camera. Use
    :func:`~cna.extensions.devices.testing.open_test_camera` for qualification:
    it opens the same object over CNA's deterministic backend and touches no
    hardware.
    """

    __slots__ = ("_handle",)

    def __init__(self, game: "Game") -> None:
        handle = _support.out_handle("cna_camera_create",
                                     _dev.game_handle(game, "camera"))
        self._handle = _support.handle(handle, "cna_camera_destroy", "camera")

    @classmethod
    def _adopt(cls, handle: int) -> "Camera":
        camera = cls.__new__(cls)
        camera._handle = _support.handle(handle, "cna_camera_destroy", "camera")
        return camera

    @property
    def state(self) -> CameraState:
        return CameraState(_support.out_u32("cna_camera_get_state_ext",
                                            self._handle.argument))

    @property
    def frame_width(self) -> int:
        return _support.out_i32("cna_camera_get_frame_width_ext",
                                self._handle.argument)

    @property
    def frame_height(self) -> int:
        return _support.out_i32("cna_camera_get_frame_height_ext",
                                self._handle.argument)

    def try_acquire_frame(self, texture: "Texture2D") -> bool:
        """Copies the newest frame into ``texture``; ``False`` when there is none.

        The texture is borrowed for the call. CNA writes into it and retains
        nothing, so the caller keeps owning it and may reuse it every frame.
        """
        if not hasattr(texture, "_require_handle"):
            raise TypeError(
                "texture must be a Microsoft.Xna.Framework.Graphics.Texture2D, "
                f"not {type(texture).__name__}")
        return _support.out_bool("cna_camera_try_acquire_frame_ext",
                                 self._handle.argument,
                                 c.c_uint64(texture._require_handle()))

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()
