"""Extended input: text and IME, cursors, joysticks, haptics and hotplug.

Everything driven through CNA's raise routes is ``SYNTHETIC_BACKEND_VERIFIED``:
no IME composed anything, no joystick was plugged in, no motor moved. What is
measured is the event plumbing, the UTF-16 handling, the index-versus-id
distinction, the callback contract and this binding's own conversions.

Two claims are *not* synthetic and are marked as such: device enumeration reads
the real host device list, and joystick and haptic counts are the real ones.
Both are non-invasive, and an empty list is a measurement rather than a failure.

The fixtures are chosen to catch the mistakes this family invites:

* **Non-BMP text.** "Hé😀" is three characters and four UTF-16 code units, so an
  implementation that counted code units as characters, or that dropped a
  surrogate, produces a different string.
* **A candidate list longer than one.** Three candidates with a selection that
  is neither the first nor the last, so an off-by-one in the stride or the
  selected index is visible.
* **A hat position that is not a bit set.** ``LeftUp`` is the identity 7, so a
  projection that treated hats as flags would produce 12 instead.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Rectangle

import cna.extensions.input as inputs
from cna.extensions.input import (
    HapticDirection, HapticDirectionType, HapticEffect, HapticEffectType,
    HapticFeature, InputDeviceInfo, JoystickHatPosition, JoystickType,
    MouseCursorStock, PowerState, SensorType, TextEditing, TextEditingCandidates,
    TextInputAccumulator, TextInputType,
)
from cna.extensions.input import testing as backend
from cna.extensions.input.errors import InputError, InputStateError

from .device_fixtures import in_game, requires_native, requires_renderer

#: Three characters, four UTF-16 code units: the third is above U+FFFF.
NON_BMP = "Hé\N{GRINNING FACE}"
NON_BMP_UNITS = (0x48, 0xE9, 0xD83D, 0xDE00)

#: A candidate list where the selection is neither end.
CANDIDATES = ("候補一", "候補二", "候補三")


class TextInputAccumulatorTests(unittest.TestCase):
    """The one place a surrogate pair becomes a character. No library needed."""

    def test_a_non_bmp_character_arrives_as_two_units_and_becomes_one(self) -> None:
        accumulator = TextInputAccumulator()
        for unit in NON_BMP_UNITS:
            accumulator(unit)
        self.assertEqual(accumulator.text, NON_BMP)
        self.assertEqual(len(accumulator.text), 3)
        self.assertEqual(len(NON_BMP_UNITS), 4)
        self.assertEqual(accumulator.unpaired, [])

    def test_a_high_surrogate_is_held_until_its_partner_arrives(self) -> None:
        accumulator = TextInputAccumulator()
        accumulator(0xD83D)
        self.assertEqual(accumulator.text, "")
        self.assertEqual(accumulator.pending_high_surrogate, 0xD83D)
        accumulator(0xDE00)
        self.assertEqual(accumulator.text, "\N{GRINNING FACE}")
        self.assertIsNone(accumulator.pending_high_surrogate)

    def test_an_unpaired_high_surrogate_is_reported_rather_than_replaced(self) -> None:
        accumulator = TextInputAccumulator()
        accumulator(0xD83D)
        accumulator(0x41)
        self.assertEqual(accumulator.text, "A")
        self.assertEqual(accumulator.unpaired, [0xD83D])

    def test_an_unpaired_low_surrogate_is_reported_rather_than_replaced(self) -> None:
        accumulator = TextInputAccumulator()
        accumulator(0xDE00)
        accumulator(0x42)
        self.assertEqual(accumulator.text, "B")
        self.assertEqual(accumulator.unpaired, [0xDE00])

    def test_two_high_surrogates_in_a_row_report_the_first(self) -> None:
        accumulator = TextInputAccumulator()
        accumulator(0xD83D)
        accumulator(0xD83C)
        accumulator(0xDF00)
        self.assertEqual(accumulator.unpaired, [0xD83D])
        self.assertEqual(accumulator.text, "\N{CYCLONE}")

    def test_a_code_unit_outside_sixteen_bits_is_refused(self) -> None:
        accumulator = TextInputAccumulator()
        with self.assertRaises(ValueError):
            accumulator(0x10000)

    def test_clear_forgets_the_pending_surrogate_too(self) -> None:
        accumulator = TextInputAccumulator()
        accumulator(0xD83D)
        accumulator.clear()
        self.assertIsNone(accumulator.pending_high_surrogate)
        self.assertEqual(accumulator.text, "")


class ValueTests(unittest.TestCase):
    """Values that need no native library."""

    def test_a_hat_position_is_an_identity_and_not_a_bit_set(self) -> None:
        import enum

        # The canonical header says so in as many words: RIGHT_UP is the
        # identity 5, not RIGHT | UP.
        self.assertEqual(int(JoystickHatPosition.RightUp), 5)
        self.assertEqual(int(JoystickHatPosition.LeftUp), 7)
        self.assertFalse(issubclass(JoystickHatPosition, enum.Flag),
                         "a flag projection would invent positions CNA never reports")
        # Under a flag projection 3 would be Up|Right, a combination; under the
        # identities it is Down, which is what CNA means by 3.
        self.assertIs(JoystickHatPosition(3), JoystickHatPosition.Down)
        # And a value that is only reachable by combining bits must not exist.
        with self.assertRaises(ValueError):
            JoystickHatPosition(9)

    def test_haptic_features_are_a_bit_set(self) -> None:
        combined = HapticFeature.Constant | HapticFeature.Sine
        self.assertIn(HapticFeature.Constant, combined)
        self.assertIn(HapticFeature.Sine, combined)
        self.assertNotIn(HapticFeature.Ramp, combined)

    def test_the_default_effect_is_a_zeroed_constant_with_a_polar_direction(self) -> None:
        # CNA documents the default that way, and both identities are zero, so
        # the zeroed structure *is* the default. If either identity moved off
        # zero this would stop being true, which is what this asserts.
        effect = HapticEffect()
        self.assertEqual(int(effect.type), 0)
        self.assertEqual(int(HapticEffectType.Constant), 0)
        self.assertEqual(int(effect.direction.type), 0)
        self.assertEqual(int(HapticDirectionType.Polar), 0)
        self.assertEqual(effect.direction.values, (0, 0, 0))

    def test_a_per_axis_field_with_the_wrong_length_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            HapticEffect(deadband=(1, 2))
        with self.assertRaises(ValueError):
            HapticDirection(HapticDirectionType.Polar, (1, 2))

    def test_a_per_axis_value_outside_its_native_width_is_refused(self) -> None:
        """The six per-axis fields are three different widths between them.

        ``deadband`` is unsigned 16-bit and ``center`` is signed, so a value that
        fits one does not fit the other; a conversion that used one width for
        both would let a negative deadband or an over-large centre through.
        """
        from cna.extensions.input.haptics import _to_native

        with self.assertRaises(ValueError):
            _to_native(HapticEffect(deadband=(-1, 0, 0)))
        with self.assertRaises(ValueError):
            _to_native(HapticEffect(center=(0x8000, 0, 0)))
        with self.assertRaises(ValueError):
            _to_native(HapticEffect(right_saturation=(0x10000, 0, 0)))
        with self.assertRaises(ValueError):
            _to_native(HapticEffect(left_coefficient=(0, -0x8001, 0)))


@requires_native
class TextInputTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: CNA's raise routes, not a physical keyboard."""

    def _session(self, body):
        def wrapped(game, observed):
            try:
                body(game, observed)
            finally:
                inputs.stop_text_input(game)
                backend.reset_text_input(game)

        return in_game(wrapped)

    def test_starting_and_stopping_answers_without_inventing_a_state(self) -> None:
        """Whether text input *becomes* active needs a window; asking does not.

        A build with no window starts text input successfully and reports it
        inactive, because there is nothing to type into. That is the honest
        answer and it is what a non-windowed artifact must give; the windowed
        artifact's stronger claim is
        :meth:`TextInputWindowedTests.test_starting_makes_text_input_active`.
        """
        def body(game, observed):
            observed["before"] = inputs.is_text_input_active(game)
            inputs.start_text_input(game)
            observed["during"] = inputs.is_text_input_active(game)
            inputs.stop_text_input(game)
            observed["after"] = inputs.is_text_input_active(game)

        observed = self._session(body)
        self.assertFalse(observed["before"])
        self.assertIsInstance(observed["during"], bool)
        self.assertFalse(observed["after"])

    def test_a_typed_string_arrives_as_utf16_code_units(self) -> None:
        def body(game, observed):
            units: list[int] = []
            with inputs.on_text_input(units.append):
                inputs.start_text_input(game, TextInputType.TextEmail)
                backend.raise_text_input_string(game, NON_BMP)
                observed["units"] = list(units)

        units = self._session(body)["units"]
        self.assertEqual(tuple(units), NON_BMP_UNITS)
        self.assertEqual(len(units), 4, "three characters, four code units")

    def test_the_accumulator_turns_those_units_back_into_the_string(self) -> None:
        def body(game, observed):
            accumulator = TextInputAccumulator()
            with inputs.on_text_input(accumulator):
                inputs.start_text_input(game)
                backend.raise_text_input_string(game, NON_BMP)
                observed["text"] = accumulator.text
                observed["unpaired"] = list(accumulator.unpaired)

        observed = self._session(body)
        self.assertEqual(observed["text"], NON_BMP)
        self.assertEqual(observed["unpaired"], [])

    def test_a_composition_update_keeps_its_utf16_offsets(self) -> None:
        def body(game, observed):
            updates: list[TextEditing] = []
            with inputs.on_text_editing(updates.append):
                inputs.start_text_input(game)
                backend.raise_text_editing(game, "こんにちは", 2, 3)
                observed["updates"] = list(updates)

        updates = self._session(body)["updates"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0], TextEditing("こんにちは", 2, 3))
        # The offsets are code-unit offsets and are not converted into anything.
        self.assertEqual(updates[0].start, 2)
        self.assertEqual(updates[0].length, 3)

    def test_a_candidate_list_keeps_its_order_count_and_selection(self) -> None:
        def body(game, observed):
            lists: list[TextEditingCandidates] = []
            with inputs.on_text_editing_candidates(lists.append):
                inputs.start_text_input(game)
                backend.raise_text_editing_candidates(
                    game, CANDIDATES, selected=1, horizontal=False)
                observed["lists"] = list(lists)

        lists = self._session(body)["lists"]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].candidates, CANDIDATES)
        self.assertEqual(lists[0].selected, 1)
        self.assertFalse(lists[0].horizontal)

    def test_no_selection_is_none_rather_than_minus_one(self) -> None:
        def body(game, observed):
            lists: list[TextEditingCandidates] = []
            with inputs.on_text_editing_candidates(lists.append):
                inputs.start_text_input(game)
                backend.raise_text_editing_candidates(game, CANDIDATES, selected=-1)
                observed["lists"] = list(lists)

        self.assertIsNone(self._session(body)["lists"][0].selected)

    def test_an_empty_candidate_list_arrives_empty(self) -> None:
        def body(game, observed):
            lists: list[TextEditingCandidates] = []
            with inputs.on_text_editing_candidates(lists.append):
                inputs.start_text_input(game)
                backend.raise_text_editing_candidates(game, ())
                observed["lists"] = list(lists)

        lists = self._session(body)["lists"]
        self.assertEqual(lists[0].candidates, ())

    def test_no_code_unit_arrives_after_unsubscribing(self) -> None:
        def body(game, observed):
            units: list[int] = []
            subscription = inputs.on_text_input(units.append)
            inputs.start_text_input(game)
            backend.raise_text_input(game, 0x41)
            subscription.close()
            backend.raise_text_input(game, 0x42)
            observed["units"] = list(units)
            observed["closed"] = subscription.closed

        observed = self._session(body)
        self.assertEqual(observed["units"], [0x41])
        self.assertTrue(observed["closed"])

    def test_a_handler_that_raises_does_not_unwind_into_c(self) -> None:
        def body(game, observed):
            def explode(_unit: int) -> None:
                raise ArithmeticError("planted")

            seen: list[int] = []
            with inputs.on_text_input(explode), inputs.on_text_input(seen.append):
                inputs.start_text_input(game)
                backend.raise_text_input(game, 0x41)
                observed["failures"] = [type(error).__name__ for _handler, error
                                        in inputs.text.callback_failures()]
                backend.raise_text_input(game, 0x42)
                # The exception was caught at the boundary, so delivery kept
                # working -- both to the handler that raised and to the other one.
                observed["seen"] = list(seen)

        observed = self._session(body)
        self.assertIn("ArithmeticError", observed["failures"])
        self.assertEqual(observed["seen"], [0x41, 0x42])

    def test_the_input_rectangle_is_accepted(self) -> None:
        def body(game, observed):
            inputs.start_text_input(game)
            inputs.set_input_rectangle(game, Rectangle(10, 20, 30, 40))
            observed["ok"] = True

        self.assertTrue(self._session(body)["ok"])

    def test_a_rectangle_of_the_wrong_type_is_refused(self) -> None:
        def body(game, observed):
            try:
                inputs.set_input_rectangle(game, (1, 2, 3, 4))
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True

        self.assertTrue(self._session(body)["refused"])

    def test_the_screen_keyboard_question_is_answerable(self) -> None:
        def body(game, observed):
            observed["shown"] = inputs.is_screen_keyboard_shown(game)
            observed["window"] = inputs.window_handle(game)
            observed["for_window"] = inputs.is_screen_keyboard_shown(
                game, observed["window"])

        observed = self._session(body)
        self.assertIsInstance(observed["shown"], bool)
        self.assertIsInstance(observed["for_window"], bool)


@requires_native
class DeviceEnumerationTests(unittest.TestCase):
    """Real host enumeration. Non-invasive: nothing is opened."""

    def test_enumeration_agrees_with_the_counts(self) -> None:
        def body(game, observed):
            observed["keyboards"] = inputs.keyboards(game)
            observed["keyboard_count"] = inputs.keyboard_count(game)
            observed["mice"] = inputs.mice(game)
            observed["mouse_count"] = inputs.mouse_count(game)
            observed["touch"] = inputs.touch_devices(game)
            observed["touch_count"] = inputs.touch_device_count(game)

        observed = in_game(body)
        for kind in ("keyboard", "mouse", "touch"):
            with self.subTest(kind=kind):
                key = {"keyboard": "keyboards", "mouse": "mice",
                       "touch": "touch"}[kind]
                self.assertEqual(len(observed[key]), observed[f"{kind}_count"])
                for entry in observed[key]:
                    self.assertIsInstance(entry, InputDeviceInfo)
                    self.assertTrue(entry.name)
        if observed["keyboards"] and observed["mice"]:
            # Three lists read through one helper is three chances to pass the
            # wrong kind, and on a host with both the ids differ, so a keyboard
            # list that is really the mouse list is visible here.
            self.assertNotEqual(
                {entry.id for entry in observed["keyboards"]},
                {entry.id for entry in observed["mice"]},
                "the keyboard list must not be the mouse list")

    def test_device_power_reports_unknown_as_none(self) -> None:
        def body(game, observed):
            observed["power"] = inputs.device_power(game)

        power = in_game(body)["power"]
        self.assertIsInstance(power.state, PowerState)
        for value in (power.seconds_remaining, power.battery_percent):
            with self.subTest(value=value):
                self.assertTrue(value is None or value >= 0)

    def test_a_gamepad_with_no_sensor_answers_none_and_not_a_zero_vector(self) -> None:
        def body(game, observed):
            observed["accel"] = inputs.gamepad_acceleration(game)
            observed["gyro"] = inputs.gamepad_angular_velocity(game)
            observed["sensors"] = inputs.device_sensors(game)

        observed = in_game(body)
        for sensor in observed["sensors"]:
            with self.subTest(sensor=sensor):
                self.assertIsInstance(sensor.type, SensorType)
        if observed["sensors"]:
            self.skipTest("this host has a device with sensors")
        # With no sensor at all, both must be None. A zero vector here would be
        # indistinguishable from a controller lying flat.
        self.assertIsNone(observed["accel"])
        self.assertIsNone(observed["gyro"])

    def test_a_hotplug_event_reaches_its_handler_exactly_once(self) -> None:
        def body(game, observed):
            seen: list[int] = []
            subscription = inputs.on_keyboard_connected(seen.append)
            backend.raise_keyboard_connected(game, 41)
            observed["during"] = list(seen)
            subscription.close()
            backend.raise_keyboard_connected(game, 42)
            observed["after"] = list(seen)
            backend.reset_input_devices(game)

        observed = in_game(body)
        self.assertEqual(observed["during"], [41])
        self.assertEqual(observed["after"], [41])

    def test_the_four_hotplug_events_are_not_interchanged(self) -> None:
        def body(game, observed):
            keyboard_in, keyboard_out, mouse_in, mouse_out = [], [], [], []
            subscriptions = [
                inputs.on_keyboard_connected(keyboard_in.append),
                inputs.on_keyboard_disconnected(keyboard_out.append),
                inputs.on_mouse_connected(mouse_in.append),
                inputs.on_mouse_disconnected(mouse_out.append),
            ]
            try:
                backend.raise_keyboard_connected(game, 1)
                backend.raise_keyboard_disconnected(game, 2)
                backend.raise_mouse_connected(game, 3)
                backend.raise_mouse_disconnected(game, 4)
                observed["seen"] = (list(keyboard_in), list(keyboard_out),
                                    list(mouse_in), list(mouse_out))
            finally:
                for subscription in subscriptions:
                    subscription.close()
                backend.reset_input_devices(game)

        self.assertEqual(in_game(body)["seen"], ([1], [2], [3], [4]))

    def test_a_non_callable_hotplug_handler_is_refused(self) -> None:
        def body(game, observed):
            try:
                inputs.on_keyboard_connected(object())
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True

        self.assertTrue(in_game(body)["refused"])


@requires_native
class JoystickTests(unittest.TestCase):
    """Real enumeration plus synthetic hotplug. No joystick is fabricated."""

    def test_an_empty_joystick_list_is_host_evidence(self) -> None:
        def body(game, observed):
            observed["count"] = inputs.joystick_count(game)
            observed["joysticks"] = inputs.joysticks(game)

        observed = in_game(body)
        self.assertEqual(len(observed["joysticks"]), observed["count"])
        for entry in observed["joysticks"]:
            with self.subTest(joystick=entry):
                self.assertIsInstance(entry.type, JoystickType)

    def test_a_joystick_that_is_not_there_reads_as_empty_rather_than_invented(self) -> None:
        """CNA answers absence through the values, and that is passed through.

        Capturing the state of an id nothing is plugged into succeeds and hands
        back an *empty* snapshot -- zero axes, zero buttons, zero hats -- and the
        capabilities say ``is_connected=False`` with an empty name. That is the
        canonical behaviour, and what must not happen is a snapshot that looks
        like a device.
        """
        def body(game, observed):
            if inputs.joystick_count(game):
                observed["skip"] = True
                return
            observed["skip"] = False
            with inputs.capture_joystick_state(game, 999) as state:
                observed["counts"] = (state.axis_count, state.ball_count,
                                      state.button_count, state.hat_count)
                observed["ranges"] = (state.axes, state.buttons, state.hats,
                                      state.balls)
            capabilities = inputs.joystick_capabilities(game, 999)
            observed["connected"] = capabilities.is_connected
            observed["name"] = capabilities.name
            observed["type"] = capabilities.type
            observed["power_percent"] = capabilities.power_percent
            observed["power_state"] = capabilities.power_state

        observed = in_game(body)
        if observed["skip"]:
            self.skipTest("this host has a joystick")
        self.assertEqual(observed["counts"], (0, 0, 0, 0))
        self.assertEqual(observed["ranges"], ((), (), (), ()))
        self.assertFalse(observed["connected"])
        self.assertEqual(observed["name"], "")
        self.assertEqual(observed["type"], JoystickType.Unknown)
        self.assertIsNone(observed["power_percent"],
                          "CNA's -1 must not reach a caller as a percentage")
        self.assertIsInstance(observed["power_state"], PowerState)

    def test_a_synthetic_connect_event_reaches_its_handler(self) -> None:
        def body(game, observed):
            connected, disconnected = [], []
            first = inputs.on_joystick_connected(connected.append)
            second = inputs.on_joystick_disconnected(disconnected.append)
            try:
                backend.raise_joystick_connected(game, 7)
                backend.raise_joystick_disconnected(game, 9)
                observed["seen"] = (list(connected), list(disconnected))
            finally:
                first.close()
                second.close()
                backend.reset_joysticks(game)

        self.assertEqual(in_game(body)["seen"], ([7], [9]))

    def test_no_joystick_event_arrives_after_unsubscribing(self) -> None:
        def body(game, observed):
            seen: list[int] = []
            subscription = inputs.on_joystick_connected(seen.append)
            backend.raise_joystick_connected(game, 7)
            subscription.close()
            backend.raise_joystick_connected(game, 8)
            observed["seen"] = list(seen)
            backend.reset_joysticks(game)

        self.assertEqual(in_game(body)["seen"], [7])


@requires_native
class HapticTests(unittest.TestCase):
    """Real enumeration. Nothing here claims a physical vibration."""

    def test_an_empty_haptic_list_is_host_evidence(self) -> None:
        def body(game, observed):
            observed["count"] = inputs.haptic_count(game)
            observed["devices"] = inputs.haptic_devices(game)
            observed["mouse"] = inputs.is_mouse_haptic(game)

        observed = in_game(body)
        self.assertEqual(len(observed["devices"]), observed["count"])
        self.assertIsInstance(observed["mouse"], bool)

    def test_a_haptic_device_that_is_not_there_opens_closed(self) -> None:
        """Failing to open is not an error, and this does not make it one.

        CNA documents it: the route succeeds and hands back a real object whose
        ``is_open`` is False. Every operation on it must then report "not
        applied" rather than raising or claiming success, and the two unknown
        limits must arrive as ``None`` rather than as -1.
        """
        def body(game, observed):
            if inputs.haptic_count(game):
                observed["skip"] = True
                return
            observed["skip"] = False
            with inputs.open_haptic(game, 0) as device:
                observed["is_open"] = device.is_open
                capabilities = device.capabilities
                observed["features"] = capabilities.features
                observed["limits"] = (capabilities.max_effects,
                                      capabilities.max_effects_playing)
                observed["rumble_supported"] = capabilities.rumble_supported
                observed["applied"] = (device.init_rumble(),
                                       device.play_rumble(0.5, 100),
                                       device.stop_rumble(),
                                       device.pause(), device.resume(),
                                       device.stop_all_effects(),
                                       device.set_gain(50),
                                       device.set_autocenter(50))

        observed = in_game(body)
        if observed["skip"]:
            self.skipTest("this host has a haptic device")
        self.assertFalse(observed["is_open"])
        self.assertEqual(observed["features"], HapticFeature.None_)
        self.assertEqual(observed["limits"], (None, None),
                         "CNA's -1 must not reach a caller as a count")
        self.assertFalse(observed["rumble_supported"])
        self.assertEqual(set(observed["applied"]), {False},
                         "a closed device must report every request unapplied")

    def test_an_effect_with_an_out_of_range_field_is_refused_before_cna(self) -> None:
        from cna.extensions.input.haptics import _to_native

        with self.assertRaises(ValueError):
            _to_native(HapticEffect(level=0x8000))
        with self.assertRaises(ValueError):
            _to_native(HapticEffect(custom_channels=256))

    def test_an_effect_converts_every_field_it_carries(self) -> None:
        from cna.extensions.input.haptics import _to_native

        effect = HapticEffect(
            type=HapticEffectType.Ramp,
            direction=HapticDirection(HapticDirectionType.Cartesian, (1, -2, 3)),
            length=1234, delay=56, button=7, interval=89, level=-100, period=250,
            magnitude=-300, offset=17, phase=9000, ramp_start=-1, ramp_end=2,
            right_saturation=(1, 2, 3), left_saturation=(4, 5, 6),
            right_coefficient=(-1, -2, -3), left_coefficient=(-4, -5, -6),
            deadband=(7, 8, 9), center=(-7, -8, -9),
            large_magnitude=111, small_magnitude=222, custom_period=13,
            custom_channels=2, attack_length=5, attack_level=6,
            fade_length=7, fade_level=8, custom_data=(10, 20, 30, 40))
        native, samples, count = _to_native(effect)
        self.assertEqual(int(native.type), int(HapticEffectType.Ramp))
        self.assertEqual(int(native.direction.type),
                         int(HapticDirectionType.Cartesian))
        self.assertEqual([int(native.direction.values[i]) for i in range(3)],
                         [1, -2, 3])
        self.assertEqual(int(native.length), 1234)
        self.assertEqual(int(native.level), -100)
        self.assertEqual([int(native.deadband[i]) for i in range(3)], [7, 8, 9])
        self.assertEqual([int(native.center[i]) for i in range(3)], [-7, -8, -9])
        self.assertEqual(count, 4)
        self.assertEqual([int(samples[i]) for i in range(count)], [10, 20, 30, 40])

    def test_an_effect_with_no_custom_data_passes_a_null_array(self) -> None:
        from cna.extensions.input.haptics import _to_native

        _native, samples, count = _to_native(HapticEffect())
        self.assertIsNone(samples)
        self.assertEqual(count, 0)


@requires_renderer
class TextInputWindowedTests(unittest.TestCase):
    """The claims that need a real window, so a windowed artifact must make them."""

    def test_starting_makes_text_input_active(self) -> None:
        def body(game, observed):
            try:
                observed["before"] = inputs.is_text_input_active(game)
                inputs.start_text_input(game, TextInputType.Text)
                observed["during"] = inputs.is_text_input_active(game)
                inputs.stop_text_input(game)
                observed["after"] = inputs.is_text_input_active(game)
            finally:
                backend.reset_text_input(game)

        observed = in_game(body, graphics=True)
        self.assertFalse(observed["before"])
        self.assertTrue(observed["during"])
        self.assertFalse(observed["after"])

    def test_the_game_window_is_the_one_text_input_uses(self) -> None:
        def body(game, observed):
            try:
                observed["window"] = inputs.window_handle(game)
            finally:
                backend.reset_text_input(game)

        self.assertNotEqual(in_game(body, graphics=True)["window"], 0)


@requires_renderer
class CursorTests(unittest.TestCase):
    """Cursors need a real window, so these run only on the rasterizing artifact."""

    def test_every_stock_cursor_can_be_made(self) -> None:
        def body(game, observed):
            made = {}
            for which in MouseCursorStock:
                cursor = inputs.MouseCursor.stock(game, which)
                made[which.name] = not cursor.closed
                cursor.close(force=True)
            observed["made"] = made

        observed = in_game(body, graphics=True)["made"]
        self.assertEqual(len(observed), len(MouseCursorStock))
        self.assertTrue(all(observed.values()))

    def test_the_active_cursor_refuses_to_be_closed_underneath_the_platform(self) -> None:
        def body(game, observed):
            arrow = inputs.MouseCursor.stock(game, MouseCursorStock.Arrow)
            hand = inputs.MouseCursor.stock(game, MouseCursorStock.Hand)
            inputs.set_cursor(game, arrow)
            observed["active_is_arrow"] = inputs.active_cursor() is arrow
            try:
                arrow.close()
                observed["refused"] = False
            except InputStateError:
                observed["refused"] = True
            inputs.set_cursor(game, hand)
            arrow.close()
            observed["closed_after_swap"] = arrow.closed
            try:
                hand.close()
                observed["hand_refused"] = False
            except InputStateError:
                observed["hand_refused"] = True
            hand.close(force=True)
            observed["hand_closed"] = hand.closed

        observed = in_game(body, graphics=True)
        self.assertTrue(observed["active_is_arrow"])
        self.assertTrue(observed["refused"])
        self.assertTrue(observed["closed_after_swap"])
        self.assertTrue(observed["hand_refused"])
        self.assertTrue(observed["hand_closed"],
                        "force is the way out for the last cursor")

    def test_a_cursor_can_be_built_from_a_texture(self) -> None:
        from Microsoft.Xna.Framework import Color
        from Microsoft.Xna.Framework.Graphics import Texture2D

        def body(game, observed):
            texture = Texture2D(game.GraphicsDevice, 2, 2)
            texture.SetData([Color(255, 0, 0, 255)] * 4)
            with inputs.MouseCursor.from_texture(game, texture, 1, 1) as cursor:
                observed["made"] = not cursor.closed
            texture.Dispose()

        self.assertTrue(in_game(body, graphics=True)["made"])

    def test_a_texture_of_the_wrong_type_is_refused(self) -> None:
        def body(game, observed):
            try:
                inputs.MouseCursor.from_texture(game, object(), 0, 0)
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True

        self.assertTrue(in_game(body, graphics=True)["refused"])


if __name__ == "__main__":
    unittest.main()
