"""Shared harness for the sensors and device-services tests.

Two facts decide what a device test can prove, and they are different questions:

``NATIVE``
    a CNA library is configured at all.
``DEVICES_PRESENT``
    the loaded build contains the device-services layer. Every device route is
    exported in every build, so this is read from ``cna_devices_ext_is_available``
    and never from the symbol table.

Everything below runs against **CNA's own deterministic backends**. Nothing here
tilts an accelerometer, opens a camera, spins a motor or puts a window on a
desktop. A result obtained here is ``SYNTHETIC_BACKEND_VERIFIED``; it is evidence
about the state machine, the value protocol and this binding, and it is never
evidence about hardware.

Fixtures are deliberately **non-symmetric**: no axis triple is a permutation of
another, no two axes share a value, and the timestamps are past 2**53 ticks so a
tick count that went through a double would come back wrong.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Game, GraphicsDeviceManager, Matrix, Quaternion, Vector3

from _cna_native.errors import NativeUnavailableError
from _cna_native.runtime_identity import runtime_identity


def _identity():
    try:
        return runtime_identity()
    except NativeUnavailableError:
        return None
    except Exception:  # pragma: no cover - a configured library that fails to load
        return None


IDENTITY = _identity()
NATIVE = IDENTITY is not None
RENDERS = bool(IDENTITY and IDENTITY.renders)


def _devices_present() -> bool:
    if not NATIVE:
        return False
    from cna.extensions.devices import device_services_available

    try:
        return device_services_available()
    except Exception:  # pragma: no cover - defensive
        return False


DEVICES_PRESENT = _devices_present()

requires_native = unittest.skipUnless(NATIVE, "needs a configured CNA library")
requires_devices = unittest.skipUnless(
    DEVICES_PRESENT, "the loaded CNA build has no device-services layer")
requires_renderer = unittest.skipUnless(
    DEVICES_PRESENT and RENDERS,
    "needs a device-services build on a rasterizing renderer")


#: A timestamp well past 2**53 ticks, with a whole-hour offset.
#:
#: 2**53 is 9_007_199_254_740_992; this is about seventy times that, which is
#: what an ordinary present-day timestamp looks like in this ABI. A tick count
#: that went through a Python float on the way in or out would come back with
#: its low digits replaced, and every timestamp assertion below would fail --
#: which is the point of choosing it.
LARGE_TICKS = 638_651_234_567_891_237
UTC_OFFSET_TICKS = 3600 * 10_000_000

#: A second timestamp, one tick later, so "the timestamp survived" cannot pass
#: by comparing two values that were equal anyway.
LARGE_TICKS_NEXT = LARGE_TICKS + 1


def timestamp(ticks: int = LARGE_TICKS, offset: int = UTC_OFFSET_TICKS):
    from cna.extensions.devices import DateTimeOffset

    return DateTimeOffset(ticks, offset)


#: Three axes that are pairwise different, none zero, and not a permutation of
#: each other, so an implementation that swapped two of them fails.
AXES = (0.125, -0.5, 2.25)
AXES_SECOND = (-1.75, 0.375, -3.5)


def attitude_reading():
    """A non-symmetric attitude: no two angles equal, no identity matrix."""
    from cna.extensions.devices import AttitudeReading

    return AttitudeReading(
        timestamp(), pitch=0.25, roll=-0.75, yaw=1.5,
        quaternion=Quaternion(0.125, -0.25, 0.5, 0.8125),
        rotation_matrix=Matrix(*[float(value) / 16.0 for value in range(1, 17)]))


def compass_reading():
    from cna.extensions.devices import CompassReading

    return CompassReading(
        timestamp(), heading_accuracy=1.5, magnetic_heading=123.25,
        true_heading=124.75, magnetometer_reading=Vector3(*AXES))


def motion_reading():
    from cna.extensions.devices import MotionReading

    return MotionReading(
        timestamp(), attitude=attitude_reading(),
        device_acceleration=Vector3(*AXES),
        device_rotation_rate=Vector3(*AXES_SECOND),
        gravity=Vector3(-0.0625, 0.9375, -0.03125))


def in_game(body, *, graphics: bool = False):
    """Runs ``body(game, observed)`` once inside a real frame.

    Device routes take a live game handle, so the measurement happens inside one
    running game rather than around it. An exception inside the frame is
    re-raised here rather than being swallowed into a frame that did nothing.
    """
    observed: dict = {}
    failure: list[BaseException] = []

    class Probe(Game):
        def __init__(self) -> None:
            super().__init__()
            if graphics:
                self.manager = GraphicsDeviceManager(self)
            self.done = False

        def Update(self, gameTime) -> None:
            if self.done:
                self.Exit()
                return
            self.done = True
            try:
                body(self, observed)
            except BaseException as error:  # re-raised outside the frame
                failure.append(error)
            self.Exit()

    game = Probe()
    try:
        game.Run()
    finally:
        game.Dispose()
    if failure:
        raise failure[0]
    if not game.done:
        raise AssertionError("Update never ran")
    return observed
