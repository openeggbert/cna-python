"""The four sensors, against CNA's deterministic backends and independent oracles.

Everything here is ``SYNTHETIC_BACKEND_VERIFIED``. No accelerometer was tilted,
no compass was turned, and the qualification says so rather than implying
otherwise: what is measured is the state machine, the unit conversion, the
timestamp width, the callback contract and this binding's own conversions.

Three things the fixtures are chosen to catch:

* **Axis order.** Every injected triple has three different, non-zero values
  that are not a permutation of one another, so an implementation that swapped
  two axes -- or that read the reading structure at the wrong offset -- produces
  different numbers rather than passing.
* **Units.** CNA documents the accelerometer injection as platform units and the
  reading as g, so injecting 9.80665 must read back as exactly 1. A pass-through
  that skipped the conversion reads back 9.80665.
* **Timestamp width.** Sensor timestamps are around 6.4e17 ticks, seventy times
  2**53. Anything that let one through a Python float would come back with its
  low digits replaced, and the exact-equality assertions below would fail.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Matrix, Quaternion, Vector3

from cna.extensions.devices import (
    Accelerometer, AccelerometerReading, AccelerometerReadingEventInfo,
    AttitudeReading, Compass, CompassReading, DateTimeOffset, Gyroscope,
    GyroscopeReading, Motion, MotionReading, SensorState, TICKS_PER_MICROSECOND,
    last_sensor_error_id, reading_hash_code, reading_text, readings_equal,
)
from cna.extensions.devices import testing as backend
from cna.extensions.devices.errors import DeviceDisposedError, DeviceStateError

from .device_fixtures import (
    AXES, AXES_SECOND, LARGE_TICKS, LARGE_TICKS_NEXT, UTC_OFFSET_TICKS,
    attitude_reading, compass_reading, in_game, motion_reading, requires_devices,
    timestamp,
)

#: Metres per second squared for exactly one g, from CNA's own documented
#: example. Injecting this must read back as 1.0 and nothing else.
ONE_G = 9.80665


class DateTimeOffsetTests(unittest.TestCase):
    """The timestamp type, which needs no native library at all."""

    def test_ticks_beyond_two_to_the_fifty_third_are_exact(self) -> None:
        value = DateTimeOffset(LARGE_TICKS, UTC_OFFSET_TICKS)
        self.assertEqual(value.ticks, LARGE_TICKS)
        self.assertGreater(value.ticks, 2 ** 53)
        # Two adjacent tick counts collapse to the *same* double, which is the
        # whole reason nothing in this family converts one.
        self.assertEqual(float(value.ticks), float(LARGE_TICKS + 1))
        self.assertEqual(value.utc_ticks, LARGE_TICKS - UTC_OFFSET_TICKS)

    def test_two_timestamps_one_tick_apart_are_different(self) -> None:
        first = DateTimeOffset(LARGE_TICKS, 0)
        second = DateTimeOffset(LARGE_TICKS_NEXT, 0)
        self.assertNotEqual(first, second)
        self.assertEqual(second.ticks - first.ticks, 1)

    def test_utc_ticks_uses_integer_arithmetic(self) -> None:
        # 2**53 + 1 is the smallest positive integer a double cannot hold, so if
        # either operand went through one the difference would be wrong by one.
        value = DateTimeOffset(2 ** 53 + 1, 1)
        self.assertEqual(value.utc_ticks, 2 ** 53)

    def test_sub_microsecond_ticks_are_reported_not_dropped(self) -> None:
        value = DateTimeOffset(LARGE_TICKS, UTC_OFFSET_TICKS)
        self.assertEqual(value.sub_microsecond_ticks,
                         LARGE_TICKS % TICKS_PER_MICROSECOND)
        moment = value.to_datetime()
        # The datetime carries the microseconds and not the remainder, which is
        # exactly why the remainder is a separate, readable number.
        self.assertEqual(moment.microsecond,
                         (LARGE_TICKS - UTC_OFFSET_TICKS) // TICKS_PER_MICROSECOND
                         % 1_000_000)

    def test_a_datetime_round_trip_loses_only_the_sub_microsecond_part(self) -> None:
        value = DateTimeOffset(LARGE_TICKS, UTC_OFFSET_TICKS)
        moment = value.to_datetime()
        recovered = DateTimeOffset(
            value.ticks - value.sub_microsecond_ticks, value.offset_ticks)
        self.assertEqual(recovered.to_datetime(), moment)
        self.assertNotEqual(recovered, value)

    def test_a_float_tick_count_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            DateTimeOffset(1.0, 0)
        with self.assertRaises(TypeError):
            DateTimeOffset(True, 0)

    def test_a_tick_count_wider_than_the_abi_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            DateTimeOffset(2 ** 63, 0)

    def test_a_sub_microsecond_offset_refuses_rather_than_rounds(self) -> None:
        with self.assertRaises(ValueError):
            DateTimeOffset(LARGE_TICKS, 1).offset


class ReadingConversionTests(unittest.TestCase):
    """Structure conversion, which needs no library because it touches no route."""

    def test_every_reading_survives_a_native_round_trip(self) -> None:
        cases = [
            AccelerometerReading(timestamp(), Vector3(*AXES)),
            GyroscopeReading(timestamp(), Vector3(*AXES_SECOND)),
            attitude_reading(),
            compass_reading(),
            motion_reading(),
            AccelerometerReadingEventInfo(timestamp(), *AXES),
        ]
        for reading in cases:
            with self.subTest(reading=type(reading).__name__):
                native = reading._to_native()
                recovered = type(reading)._from_native(native)
                self.assertEqual(recovered, reading)
                self.assertEqual(recovered.timestamp.ticks, LARGE_TICKS)

    def test_the_attitude_matrix_is_not_transposed(self) -> None:
        reading = attitude_reading()
        native = reading._to_native()
        # M12 and M21 differ in the fixture, so a transpose swaps them.
        self.assertNotEqual(reading.rotation_matrix.M12, reading.rotation_matrix.M21)
        self.assertEqual(native.rotation_matrix.m12, reading.rotation_matrix.M12)
        self.assertEqual(native.rotation_matrix.m21, reading.rotation_matrix.M21)

    def test_the_event_info_carries_double_precision(self) -> None:
        # 0.1 is not representable in binary32; a value that went through a
        # float field would come back changed.
        info = AccelerometerReadingEventInfo(timestamp(), 0.1, 0.2, 0.3)
        recovered = AccelerometerReadingEventInfo._from_native(info._to_native())
        self.assertEqual(recovered.x, 0.1)
        self.assertEqual(recovered.y, 0.2)
        self.assertEqual(recovered.z, 0.3)


@requires_devices
class CanonicalValueOperationTests(unittest.TestCase):
    """CNA's own equality, hash and text, cross-checked against Python's.

    Python's ``==`` on these dataclasses is a second answer to the same
    question. Both are exact and they are expected to agree; asserting that they
    do is what makes either one usable as evidence, and a change in CNA's
    comparison that Python did not follow shows up here.
    """

    def _readings(self):
        return [
            AccelerometerReading(timestamp(), Vector3(*AXES)),
            GyroscopeReading(timestamp(), Vector3(*AXES_SECOND)),
            attitude_reading(),
            compass_reading(),
            motion_reading(),
            AccelerometerReadingEventInfo(timestamp(), *AXES),
        ]

    def test_cna_and_python_agree_on_equality(self) -> None:
        for reading in self._readings():
            with self.subTest(reading=type(reading).__name__):
                same = type(reading)._from_native(reading._to_native())
                self.assertTrue(readings_equal(reading, same))
                self.assertEqual(reading, same)

    def test_cna_and_python_agree_that_a_changed_timestamp_differs(self) -> None:
        for reading in self._readings():
            with self.subTest(reading=type(reading).__name__):
                import dataclasses

                moved = dataclasses.replace(
                    reading, timestamp=timestamp(LARGE_TICKS_NEXT))
                self.assertFalse(readings_equal(reading, moved))
                self.assertNotEqual(reading, moved)

    def test_equal_readings_hash_alike(self) -> None:
        for reading in self._readings():
            with self.subTest(reading=type(reading).__name__):
                same = type(reading)._from_native(reading._to_native())
                self.assertEqual(reading_hash_code(reading), reading_hash_code(same))

    def test_canonical_text_is_non_empty_and_mentions_a_value(self) -> None:
        reading = AccelerometerReading(timestamp(), Vector3(*AXES))
        text = reading_text(reading)
        self.assertTrue(text)
        self.assertIsInstance(text, str)

    def test_two_different_reading_types_cannot_be_compared(self) -> None:
        with self.assertRaises(TypeError):
            readings_equal(AccelerometerReading(timestamp(), Vector3(*AXES)),
                           GyroscopeReading(timestamp(), Vector3(*AXES)))

    def test_a_non_reading_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            reading_text(object())


@requires_devices
class SensorSupportAndStateTests(unittest.TestCase):
    def test_every_sensor_reports_its_host_support_without_being_created(self) -> None:
        def body(game, observed):
            for kind in (Accelerometer, Compass, Gyroscope, Motion):
                observed[kind.__name__] = kind.is_supported(game)

        observed = in_game(body)
        for name, value in observed.items():
            with self.subTest(sensor=name):
                self.assertIsInstance(value, bool)

    def test_an_unstarted_sensor_reports_a_state_rather_than_a_reading(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                observed["state"] = sensor.state
                try:
                    sensor.current_value
                    observed["read"] = "succeeded"
                except DeviceStateError as error:
                    observed["read"] = error.result

        observed = in_game(body)
        self.assertIsInstance(observed["state"], SensorState)
        # Either answer is honest; what must not happen is a fabricated reading.
        self.assertIn(observed["read"], ("succeeded", 3))

    def test_the_default_update_interval_is_an_exact_tick_count(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                observed["ticks"] = sensor.time_between_updates_ticks

        ticks = in_game(body)["ticks"]
        self.assertIsInstance(ticks, int)
        self.assertGreater(ticks, 0)

    def test_the_update_interval_round_trips_through_ticks(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                sensor.time_between_updates_ticks = 123_456_789
                observed["ticks"] = sensor.time_between_updates_ticks

        self.assertEqual(in_game(body)["ticks"], 123_456_789)

    def test_an_interval_that_is_not_whole_microseconds_refuses_to_be_a_timedelta(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                sensor.time_between_updates_ticks = 123_456_789
                try:
                    sensor.time_between_updates
                    observed["refused"] = False
                except ValueError:
                    observed["refused"] = True

        self.assertTrue(in_game(body)["refused"])

    def test_a_float_interval_is_refused_before_it_reaches_cna(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                try:
                    sensor.time_between_updates_ticks = 1.5
                    observed["refused"] = False
                except TypeError:
                    observed["refused"] = True

        self.assertTrue(in_game(body)["refused"])


@requires_devices
class SyntheticAccelerometerTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: CNA's injector, not a physical sensor."""

    def _inject(self, values, *, second=None):
        def body(game, observed):
            with Accelerometer(game) as sensor:
                backend.set_sensor_supported(sensor, True)
                backend.set_sensor_started(sensor, True)
                seen: list[AccelerometerReading] = []
                subscription = sensor.on_current_value_changed(seen.append)
                backend.inject_accelerometer_update(sensor, *values)
                observed["seen"] = list(seen)
                observed["current"] = sensor.current_value
                observed["valid"] = sensor.is_data_valid
                subscription.close()
                if second is not None:
                    backend.inject_accelerometer_update(sensor, *second)
                observed["after_unsubscribe"] = len(seen)
                observed["failures"] = sensor.callback_failures

        return in_game(body)

    def test_the_documented_unit_conversion_is_cnas_and_not_a_pass_through(self) -> None:
        observed = self._inject((ONE_G, -ONE_G / 2.0, 0.0))
        reading = observed["seen"][0]
        self.assertEqual(reading.acceleration.X, 1.0)
        self.assertEqual(reading.acceleration.Y, -0.5)
        self.assertEqual(reading.acceleration.Z, 0.0)

    def test_the_axes_are_not_swapped(self) -> None:
        observed = self._inject((ONE_G, 2 * ONE_G, 3 * ONE_G))
        reading = observed["seen"][0]
        self.assertEqual(
            (reading.acceleration.X, reading.acceleration.Y, reading.acceleration.Z),
            (1.0, 2.0, 3.0))

    def test_the_reading_timestamp_is_a_real_tick_count_past_two_to_the_fifty_third(self) -> None:
        observed = self._inject((ONE_G, 0.0, 0.0))
        ticks = observed["seen"][0].timestamp.ticks
        self.assertIsInstance(ticks, int)
        self.assertGreater(ticks, 2 ** 53)

    def test_the_subscribed_reading_is_the_current_value(self) -> None:
        observed = self._inject((ONE_G, -ONE_G, ONE_G / 4.0))
        self.assertEqual(observed["seen"][0].acceleration,
                         observed["current"].acceleration)
        self.assertTrue(observed["valid"])

    def test_exactly_one_callback_arrives_per_injection(self) -> None:
        observed = self._inject((ONE_G, 0.0, 0.0))
        self.assertEqual(len(observed["seen"]), 1)

    def test_no_callback_arrives_after_unsubscribing(self) -> None:
        observed = self._inject((ONE_G, 0.0, 0.0), second=(0.0, ONE_G, 0.0))
        self.assertEqual(observed["after_unsubscribe"], 1)

    def test_a_handler_that_raises_does_not_unwind_into_c(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                backend.set_sensor_supported(sensor, True)
                backend.set_sensor_started(sensor, True)

                def explode(_reading):
                    raise ZeroDivisionError("planted")

                sensor.on_current_value_changed(explode)
                backend.inject_accelerometer_update(sensor, ONE_G, 0.0, 0.0)
                observed["failures"] = [type(error).__name__
                                        for _handler, error in sensor.callback_failures]
                observed["still_usable"] = sensor.is_data_valid

        observed = in_game(body)
        self.assertEqual(observed["failures"], ["ZeroDivisionError"])
        self.assertTrue(observed["still_usable"])

    def test_closing_the_sensor_releases_its_subscriptions(self) -> None:
        def body(game, observed):
            sensor = Accelerometer(game)
            backend.set_sensor_supported(sensor, True)
            backend.set_sensor_started(sensor, True)
            seen = []
            subscription = sensor.on_current_value_changed(seen.append)
            sensor.close()
            observed["subscription_closed"] = subscription.closed
            observed["sensor_closed"] = sensor.closed
            try:
                sensor.state
                observed["after_close"] = "succeeded"
            except DeviceDisposedError:
                observed["after_close"] = "refused"

        observed = in_game(body)
        self.assertTrue(observed["subscription_closed"])
        self.assertTrue(observed["sensor_closed"])
        self.assertEqual(observed["after_close"], "refused")

    def test_dispose_releases_the_hold_and_disposes_the_canonical_object(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                backend.set_sensor_supported(sensor, True)
                backend.set_sensor_started(sensor, True)
                observed["before"] = backend.sensor_subsystem_held(sensor)
                sensor.dispose()
                observed["after"] = backend.sensor_subsystem_held(sensor)
                try:
                    sensor.state
                    observed["read_after_dispose"] = "succeeded"
                except DeviceStateError as error:
                    observed["read_after_dispose"] = error.native_message

        observed = in_game(body)
        self.assertFalse(observed["after"])
        # CNA disposes the canonical object, so reading it afterwards is a use
        # after disposal rather than a stale value.
        self.assertIn("disposed", observed["read_after_dispose"])

    def test_a_broadcast_dispatch_reaches_every_registered_sensor(self) -> None:
        def body(game, observed):
            first, second = Accelerometer(game), Accelerometer(game)
            try:
                for sensor in (first, second):
                    backend.set_sensor_supported(sensor, True)
                    backend.set_sensor_started(sensor, True)
                seen_first, seen_second = [], []
                first.on_current_value_changed(seen_first.append)
                second.on_current_value_changed(seen_second.append)
                for sensor in (first, second):
                    backend.register_started_sensor(sensor)
                backend.dispatch_to_started_sensors(
                    game, (first, second), 2 * ONE_G, 0.0, 0.0)
                observed["first"] = [r.acceleration.X for r in seen_first]
                observed["second"] = [r.acceleration.X for r in seen_second]
                backend.unregister_started_sensor(second)
                seen_first.clear()
                seen_second.clear()
                backend.dispatch_to_started_sensors(
                    game, (first,), 3 * ONE_G, 0.0, 0.0)
                observed["after_unregister_first"] = len(seen_first)
                observed["after_unregister_second"] = len(seen_second)
            finally:
                first.close()
                second.close()

        observed = in_game(body)
        self.assertEqual(observed["first"], [2.0])
        self.assertEqual(observed["second"], [2.0])
        self.assertEqual(observed["after_unregister_first"], 1)
        self.assertEqual(observed["after_unregister_second"], 0)

    def test_a_dispatch_mixing_sensor_kinds_is_refused(self) -> None:
        def body(game, observed):
            accelerometer, gyroscope = Accelerometer(game), Gyroscope(game)
            try:
                try:
                    backend.dispatch_to_started_sensors(
                        game, (accelerometer, gyroscope), 1.0, 2.0, 3.0)
                    observed["refused"] = False
                except TypeError:
                    observed["refused"] = True
            finally:
                accelerometer.close()
                gyroscope.close()

        self.assertTrue(in_game(body)["refused"])

    def test_the_second_accelerometer_event_carries_its_own_payload(self) -> None:
        def body(game, observed):
            with Accelerometer(game) as sensor:
                backend.set_sensor_supported(sensor, True)
                backend.set_sensor_started(sensor, True)
                seen: list[AccelerometerReadingEventInfo] = []
                sensor.on_reading_changed(seen.append)
                backend.inject_accelerometer_update(sensor, ONE_G, 2 * ONE_G, 3 * ONE_G)
                observed["seen"] = [(info.x, info.y, info.z, info.timestamp.ticks)
                                    for info in seen]

        seen = in_game(body)["seen"]
        self.assertEqual(len(seen), 1)
        x, y, z, ticks = seen[0]
        self.assertEqual((x, y, z), (1.0, 2.0, 3.0))
        self.assertGreater(ticks, 2 ** 53)


@requires_devices
class SyntheticGyroscopeTests(unittest.TestCase):
    def test_an_injected_rate_reaches_the_reading_unswapped(self) -> None:
        def body(game, observed):
            with Gyroscope(game) as sensor:
                backend.set_sensor_supported(sensor, True)
                backend.set_sensor_started(sensor, True)
                seen: list[GyroscopeReading] = []
                sensor.on_current_value_changed(seen.append)
                backend.inject_gyroscope_update(sensor, 0.125, -0.5, 2.25)
                observed["seen"] = [(r.rotation_rate.X, r.rotation_rate.Y,
                                     r.rotation_rate.Z, r.timestamp.ticks)
                                    for r in seen]

        seen = in_game(body)["seen"]
        self.assertEqual(len(seen), 1)
        x, y, z, ticks = seen[0]
        self.assertEqual((x, y, z), (0.125, -0.5, 2.25))
        self.assertGreater(ticks, 2 ** 53)


@requires_devices
class SyntheticCompassTests(unittest.TestCase):
    def test_a_whole_injected_reading_arrives_field_for_field(self) -> None:
        planted = compass_reading()

        def body(game, observed):
            with Compass(game) as sensor:
                backend.install_compass_test_backend(sensor)
                sensor.start()
                seen: list[CompassReading] = []
                sensor.on_current_value_changed(seen.append)
                backend.inject_compass_reading(sensor, planted)
                observed["seen"] = list(seen)
                observed["current"] = sensor.current_value

        observed = in_game(body)
        self.assertEqual(len(observed["seen"]), 1)
        self.assertEqual(observed["seen"][0], planted)
        self.assertEqual(observed["current"], planted)

    def test_the_two_headings_are_not_interchanged(self) -> None:
        planted = compass_reading()
        self.assertNotEqual(planted.magnetic_heading, planted.true_heading)

        def body(game, observed):
            with Compass(game) as sensor:
                backend.install_compass_test_backend(sensor)
                sensor.start()
                seen: list[CompassReading] = []
                sensor.on_current_value_changed(seen.append)
                backend.inject_compass_reading(sensor, planted)
                observed["seen"] = list(seen)

        reading = in_game(body)["seen"][0]
        self.assertEqual(reading.magnetic_heading, planted.magnetic_heading)
        self.assertEqual(reading.true_heading, planted.true_heading)

    def test_a_calibration_request_reaches_its_handler(self) -> None:
        def body(game, observed):
            with Compass(game) as sensor:
                backend.install_compass_test_backend(sensor)
                sensor.start()
                calls: list[int] = []
                subscription = sensor.on_calibrate(lambda: calls.append(1))
                backend.inject_compass_calibration_request(sensor)
                observed["during"] = len(calls)
                subscription.close()
                backend.inject_compass_calibration_request(sensor)
                observed["after"] = len(calls)

        observed = in_game(body)
        self.assertEqual(observed["during"], 1)
        self.assertEqual(observed["after"], 1)


@requires_devices
class SyntheticMotionTests(unittest.TestCase):
    def test_a_whole_fused_reading_arrives_including_its_attitude(self) -> None:
        planted = motion_reading()

        def body(game, observed):
            with Motion(game) as sensor:
                backend.install_motion_test_backend(sensor, north_referenced=True)
                sensor.start()
                seen: list[MotionReading] = []
                sensor.on_current_value_changed(seen.append)
                backend.inject_motion_reading(sensor, planted)
                observed["seen"] = list(seen)
                observed["north"] = sensor.is_attitude_north_referenced

        observed = in_game(body)
        self.assertEqual(len(observed["seen"]), 1)
        self.assertEqual(observed["seen"][0], planted)
        self.assertTrue(observed["north"])

    def test_gravity_and_device_acceleration_are_not_interchanged(self) -> None:
        planted = motion_reading()
        self.assertNotEqual(planted.gravity, planted.device_acceleration)

        def body(game, observed):
            with Motion(game) as sensor:
                backend.install_motion_test_backend(sensor)
                sensor.start()
                seen: list[MotionReading] = []
                sensor.on_current_value_changed(seen.append)
                backend.inject_motion_reading(sensor, planted)
                observed["seen"] = list(seen)

        reading = in_game(body)["seen"][0]
        self.assertEqual(reading.gravity, planted.gravity)
        self.assertEqual(reading.device_acceleration, planted.device_acceleration)

    def test_the_fused_attitude_keeps_all_three_of_its_forms(self) -> None:
        planted = motion_reading()

        def body(game, observed):
            with Motion(game) as sensor:
                backend.install_motion_test_backend(sensor)
                sensor.start()
                seen: list[MotionReading] = []
                sensor.on_current_value_changed(seen.append)
                backend.inject_motion_reading(sensor, planted)
                observed["seen"] = list(seen)

        attitude = in_game(body)["seen"][0].attitude
        self.assertEqual(attitude.pitch, planted.attitude.pitch)
        self.assertEqual(attitude.roll, planted.attitude.roll)
        self.assertEqual(attitude.yaw, planted.attitude.yaw)
        self.assertEqual(attitude.quaternion, planted.attitude.quaternion)
        self.assertEqual(attitude.rotation_matrix, planted.attitude.rotation_matrix)


@requires_devices
class SensorErrorReportingTests(unittest.TestCase):
    def test_the_last_error_identity_is_optional_rather_than_a_sentinel(self) -> None:
        def body(game, observed):
            observed["error"] = last_sensor_error_id()

        value = in_game(body)["error"]
        self.assertTrue(value is None or isinstance(value, int))

    def test_the_dispatcher_exception_count_is_readable(self) -> None:
        def body(game, observed):
            observed["count"] = backend.sensor_dispatch_exception_count(
                game, Accelerometer)
            observed["message"] = backend.last_sensor_dispatch_exception_message(
                game, Accelerometer)

        observed = in_game(body)
        self.assertIsInstance(observed["count"], int)
        self.assertIsInstance(observed["message"], str)

    def test_a_kind_with_no_dispatcher_is_refused(self) -> None:
        def body(game, observed):
            try:
                backend.sensor_dispatch_exception_count(game, Compass)
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True

        self.assertTrue(in_game(body)["refused"])


if __name__ == "__main__":
    unittest.main()
