"""Host device services: camera, host information, dialogs, tray and vibration.

**Nothing here opens a physical camera, records anything, or puts a window on
anyone's desktop.** Every family below has a CNA test backend, and the tests
install it. What is measured is the request, the argument validation, the
exactly-once answer, and the byte-for-byte round trip -- never hardware.

The two claims that are *not* synthetic are marked as such: the host's power,
locales, CPU and memory come from the real machine, and camera enumeration reads
the real device list. Neither opens anything: enumeration is non-invasive, and a
count of zero is a measurement rather than a failure.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Color, Rectangle
from Microsoft.Xna.Framework.Graphics import Texture2D

import cna.extensions.devices as devices
from cna.extensions.devices import (
    Camera, CameraDeviceInfo, CameraPosition, CameraState, DeviceType,
    FileDialogFilter, Locale, MessageBoxType, PowerInformation, PowerState,
    SystemInformation, ticks_for,
)
from cna.extensions.devices import testing as backend
from cna.extensions.devices.errors import (
    DeviceArgumentError, DeviceDisposedError, DeviceError,
)
from cna.extensions.input import clipboard_text_byte_length

from .device_fixtures import in_game, requires_devices, requires_renderer

#: A duration CNA accepts (its vibration limit is five seconds) that is not a
#: whole number of milliseconds, so a conversion through anything coarser than
#: ticks would change it.
ODD_TICKS = 12_345_679

#: Text whose UTF-8 byte count and character count are different numbers.
#: Seven characters, ten bytes.
MIXED_TEXT = "héllo ☃"


def _locales_by_index(game) -> list[tuple[str, str]]:
    """Reads the host's locale list straight from CNA, in index order.

    An oracle for :func:`cna.extensions.devices.preferred_locales` that shares
    none of its code, so a reordering in the public function shows up as a
    difference rather than as two lists that were sorted the same way.
    """
    import ctypes as c

    from _cna_native import devices_support as _dev

    handle = _dev.game_handle(game, "locale oracle")
    support = _dev.support
    count = support.out_u64("cna_locale_get_preferred_count_ext", handle)
    entries = []
    for index in reversed(range(count)):
        position = c.c_uint64(index)
        entries.append((
            support.copied_text("cna_locale_copy_language_at_ext",
                                (handle, position), "language"),
            support.copied_text("cna_locale_copy_country_at_ext",
                                (handle, position), "country")))
    entries.reverse()
    return entries


class ValueTests(unittest.TestCase):
    """Values and conversions that need no native library."""

    def test_ticks_for_a_timedelta_is_exact(self) -> None:
        from datetime import timedelta

        self.assertEqual(ticks_for(timedelta(microseconds=1)), 10)
        self.assertEqual(ticks_for(timedelta(seconds=5)), 50_000_000)
        self.assertEqual(ticks_for(timedelta(days=1)), 864_000_000_000)

    def test_ticks_for_refuses_anything_that_is_not_a_timedelta(self) -> None:
        with self.assertRaises(TypeError):
            ticks_for(1.0)

    def test_the_mixed_text_fixture_really_does_separate_bytes_from_characters(self) -> None:
        self.assertEqual(len(MIXED_TEXT), 7)
        self.assertEqual(len(MIXED_TEXT.encode("utf-8")), 10)


@requires_devices
class HostInformationTests(unittest.TestCase):
    """Real host measurements. Nothing here is synthetic, and nothing is invented."""

    def test_the_device_type_is_one_cna_declares(self) -> None:
        def body(game, observed):
            observed["type"] = devices.device_type()

        self.assertIsInstance(in_game(body)["type"], DeviceType)

    def test_power_reports_unknown_as_none_rather_than_minus_one(self) -> None:
        def body(game, observed):
            observed["power"] = devices.power_information(game)

        power = in_game(body)["power"]
        self.assertIsInstance(power, PowerInformation)
        self.assertIsInstance(power.state, PowerState)
        for value in (power.battery_percent, power.seconds_remaining):
            with self.subTest(value=value):
                self.assertTrue(value is None or value >= 0,
                                "the -1 sentinel must not reach a caller")

    def test_system_information_is_positive(self) -> None:
        def body(game, observed):
            observed["system"] = devices.system_information(game)

        system = in_game(body)["system"]
        self.assertIsInstance(system, SystemInformation)
        self.assertGreater(system.logical_cpu_cores, 0)
        self.assertGreater(system.system_ram_megabytes, 0)

    def test_preferred_locales_keep_the_hosts_order(self) -> None:
        """Against an oracle that reads the same list by index, independently.

        Comparing the public list with itself would let a sort pass, so the
        oracle here walks CNA's per-index routes in the test rather than
        borrowing the implementation's own loop.
        """
        def body(game, observed):
            observed["locales"] = devices.preferred_locales(game)
            observed["oracle"] = _locales_by_index(game)

        observed = in_game(body)
        self.assertEqual([(entry.language, entry.country)
                          for entry in observed["locales"]],
                         observed["oracle"])
        for locale in observed["locales"]:
            with self.subTest(locale=locale):
                self.assertIsInstance(locale, Locale)
                self.assertTrue(locale.language)

    def test_the_safe_area_is_a_strict_rectangle(self) -> None:
        def body(game, observed):
            observed["area"] = devices.safe_area(game)
            observed["scale"] = devices.content_scale(game)

        observed = in_game(body)
        self.assertIsInstance(observed["area"], Rectangle)
        self.assertGreater(observed["scale"], 0.0)

    def test_the_clipboard_round_trips_and_counts_bytes_not_characters(self) -> None:
        def body(game, observed):
            observed["accepted"] = devices.set_clipboard_text(game, MIXED_TEXT)
            observed["text"] = devices.clipboard_text(game)
            observed["bytes"] = clipboard_text_byte_length(game)

        observed = in_game(body)
        if not observed["accepted"]:
            self.skipTest("this host refused the clipboard write")
        self.assertEqual(observed["text"], MIXED_TEXT)
        self.assertEqual(observed["bytes"], len(MIXED_TEXT.encode("utf-8")))
        self.assertNotEqual(observed["bytes"], len(MIXED_TEXT))

    def test_an_empty_clipboard_write_is_accepted_and_read_back(self) -> None:
        def body(game, observed):
            devices.set_clipboard_text(game, "")
            observed["text"] = devices.clipboard_text(game)

        self.assertEqual(in_game(body)["text"], "")


@requires_devices
class CameraEnumerationTests(unittest.TestCase):
    """Enumeration only. Nothing here opens a camera."""

    def test_enumeration_is_consistent_with_the_count(self) -> None:
        def body(game, observed):
            observed["count"] = devices.camera_count(game)
            observed["cameras"] = devices.cameras(game)
            observed["supported"] = devices.is_camera_supported(game)

        observed = in_game(body)
        self.assertEqual(len(observed["cameras"]), observed["count"])
        for entry in observed["cameras"]:
            with self.subTest(camera=entry):
                self.assertIsInstance(entry, CameraDeviceInfo)
                self.assertIsInstance(entry.position, CameraPosition)

    def test_an_empty_camera_list_is_host_evidence_rather_than_a_failure(self) -> None:
        def body(game, observed):
            observed["cameras"] = devices.cameras(game)

        # Zero is a valid, honest answer on a machine with no camera. What is
        # asserted is that asking does not raise and does not invent one.
        self.assertIsInstance(in_game(body)["cameras"], list)


@requires_renderer
class SyntheticCameraTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: CNA's frame backend, not a physical camera."""

    #: Four pixels whose every channel differs, so a frame that arrived
    #: transposed, channel-swapped or offset produces different bytes.
    FRAME = (Color(10, 20, 30, 40), Color(50, 60, 70, 80),
             Color(90, 100, 110, 120), Color(130, 140, 150, 160))

    def test_a_planted_frame_arrives_pixel_for_pixel(self) -> None:
        def body(game, observed):
            with backend.open_test_camera(game) as camera:
                backend.set_camera_test_state(camera, CameraState.Ready)
                backend.set_camera_test_frame(camera, 2, 2, self.FRAME)
                observed["state"] = camera.state
                observed["size"] = (camera.frame_width, camera.frame_height)
                texture = Texture2D(game.GraphicsDevice, 2, 2)
                observed["acquired"] = camera.try_acquire_frame(texture)
                pixels = [Color(0, 0, 0, 0)] * 4
                texture.GetData(pixels)
                observed["pixels"] = [(c.R, c.G, c.B, c.A) for c in pixels]

        observed = in_game(body, graphics=True)
        self.assertEqual(observed["state"], CameraState.Ready)
        self.assertEqual(observed["size"], (2, 2))
        self.assertTrue(observed["acquired"])
        self.assertEqual(observed["pixels"],
                         [(c.R, c.G, c.B, c.A) for c in self.FRAME])

    def test_a_short_pixel_sequence_is_refused_before_cna_reads_past_it(self) -> None:
        """The refusal must be Python's, not CNA's.

        CNA rejects a short frame too, so "a ValueError was raised" would pass
        even with the guard removed. What is asserted is the *kind*: the guard
        raises a plain ``ValueError``, and anything CNA refuses arrives as a
        ``DeviceError``. Only the first proves nothing was handed to C.
        """
        def body(game, observed):
            with backend.open_test_camera(game) as camera:
                try:
                    backend.set_camera_test_frame(camera, 2, 2, self.FRAME[:3])
                    observed["raised"] = None
                except ValueError as error:
                    observed["raised"] = type(error).__name__
                    observed["from_cna"] = isinstance(error, DeviceError)

        observed = in_game(body, graphics=True)
        self.assertEqual(observed["raised"], "ValueError")
        self.assertFalse(observed["from_cna"],
                         "the length must be checked before CNA is called")

    def test_a_camera_that_is_not_ready_reports_it(self) -> None:
        def body(game, observed):
            with backend.open_test_camera(game) as camera:
                backend.set_camera_test_state(camera, CameraState.Denied)
                observed["state"] = camera.state

        self.assertEqual(in_game(body, graphics=True)["state"], CameraState.Denied)

    def test_a_closed_camera_refuses_further_use(self) -> None:
        def body(game, observed):
            camera = backend.open_test_camera(game)
            camera.close()
            observed["closed"] = camera.closed
            try:
                camera.state
                observed["after"] = "succeeded"
            except DeviceDisposedError:
                observed["after"] = "refused"

        observed = in_game(body, graphics=True)
        self.assertTrue(observed["closed"])
        self.assertEqual(observed["after"], "refused")

    def test_a_texture_that_is_not_a_texture2d_is_refused(self) -> None:
        def body(game, observed):
            with backend.open_test_camera(game) as camera:
                try:
                    camera.try_acquire_frame(object())
                    observed["refused"] = False
                except TypeError:
                    observed["refused"] = True

        self.assertTrue(in_game(body, graphics=True)["refused"])


@requires_devices
class SyntheticVibrationTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: the request is measured, not any motor."""

    def _log(self, body):
        def wrapped(game, observed):
            backend.install_vibration_test_backend(
                game, supported=True, device_name="synthetic pad")
            try:
                body(game, observed)
                observed["log"] = backend.vibration_test_log(game)
            finally:
                backend.install_vibration_test_backend(game, installed=False)

        return in_game(wrapped)

    def test_the_installed_backend_answers_support_and_name(self) -> None:
        def body(game, observed):
            observed["supported"] = devices.is_vibration_supported(game)
            observed["name"] = devices.vibration_device_name(game)

        observed = self._log(body)
        self.assertTrue(observed["supported"])
        self.assertEqual(observed["name"], "synthetic pad")

    def test_a_duration_reaches_the_backend_as_exact_ticks(self) -> None:
        def body(game, observed):
            devices.start_vibration(game, ODD_TICKS)

        log = self._log(body)["log"]
        self.assertEqual(log.last_duration_ticks, ODD_TICKS)
        self.assertEqual(log.start_calls, 1)
        self.assertEqual(log.left_right_calls, 0)

    def test_the_two_motors_are_not_interchanged(self) -> None:
        def body(game, observed):
            devices.start_vibration_left_right(game, 0.25, 0.75, ODD_TICKS)

        log = self._log(body)["log"]
        self.assertEqual(log.last_large_motor, 0.25)
        self.assertEqual(log.last_small_motor, 0.75)
        self.assertEqual(log.left_right_calls, 1)

    def test_intensity_and_duration_both_reach_the_backend_exactly(self) -> None:
        def body(game, observed):
            devices.start_vibration_with_intensity(game, ODD_TICKS, 0.375)

        log = self._log(body)["log"]
        self.assertEqual(log.last_intensity, 0.375)
        # ODD_TICKS is not a whole number of milliseconds, so a duration that
        # went through anything coarser than ticks comes back changed.
        self.assertEqual(log.last_duration_ticks, ODD_TICKS)

    def test_the_two_motor_duration_is_exact_too(self) -> None:
        def body(game, observed):
            devices.start_vibration_left_right(game, 0.25, 0.75, ODD_TICKS)

        self.assertEqual(self._log(body)["log"].last_duration_ticks, ODD_TICKS)

    def test_stop_is_counted_separately_from_start(self) -> None:
        def body(game, observed):
            devices.start_vibration(game, ODD_TICKS)
            devices.stop_vibration(game)

        log = self._log(body)["log"]
        self.assertEqual((log.start_calls, log.stop_calls), (1, 1))

    def test_a_duration_beyond_what_cna_accepts_is_refused_rather_than_clamped(self) -> None:
        def body(game, observed):
            try:
                devices.start_vibration(game, 6 * 10_000_000)
                observed["refused"] = False
            except DeviceArgumentError as error:
                observed["refused"] = True
                observed["message"] = error.native_message

        observed = self._log(body)
        self.assertTrue(observed["refused"])
        self.assertIn("duration", observed["message"])

    def test_installing_the_backend_resets_its_log(self) -> None:
        def body(game, observed):
            devices.start_vibration(game, ODD_TICKS)
            backend.install_vibration_test_backend(
                game, supported=True, device_name="synthetic pad")
            observed["after_reinstall"] = backend.vibration_test_log(game).start_calls

        self.assertEqual(self._log(body)["after_reinstall"], 0)

    def test_a_float_duration_is_refused_before_it_reaches_cna(self) -> None:
        def body(game, observed):
            try:
                devices.start_vibration(game, 1.5)
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True

        self.assertTrue(self._log(body)["refused"])


@requires_devices
class SyntheticMessageBoxTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: no modal window is ever shown."""

    def _run(self, body):
        def wrapped(game, observed):
            backend.install_message_box_test_backend(game, chosen_button=2)
            try:
                body(game, observed)
                observed["log"] = backend.message_box_test_log(game)
            finally:
                backend.install_message_box_test_backend(game, installed=False)

        return in_game(wrapped)

    def test_the_chosen_button_index_comes_back(self) -> None:
        def body(game, observed):
            observed["chosen"] = devices.show_message_box(
                game, MessageBoxType.Warning, "title", "message", ["a", "b", "c"])

        observed = self._run(body)
        self.assertEqual(observed["chosen"], 2)
        self.assertEqual(observed["log"].last_button_count, 3)

    def test_the_two_call_kinds_are_counted_separately(self) -> None:
        def body(game, observed):
            devices.show_message_box(game, MessageBoxType.Error, "t", "m", ["ok"])
            devices.show_simple_message_box(game, MessageBoxType.Information, "t", "m")

        log = self._run(body)["log"]
        self.assertEqual((log.choice_calls, log.simple_calls), (1, 1))
        self.assertEqual(log.last_type, MessageBoxType.Information)

    def test_a_message_box_with_no_buttons_is_refused(self) -> None:
        def body(game, observed):
            try:
                devices.show_message_box(game, MessageBoxType.Error, "t", "m", [])
                observed["refused"] = False
            except ValueError:
                observed["refused"] = True

        self.assertTrue(self._run(body)["refused"])


@requires_devices
class SyntheticFileDialogTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: no file chooser is ever opened."""

    RESULTS = ["/tmp/one.txt", "/tmp/two.txt"]

    def _run(self, body, *, results=None):
        def wrapped(game, observed):
            backend.install_file_dialog_test_backend(game, results=results)
            try:
                body(game, observed)
            finally:
                backend.install_file_dialog_test_backend(game, installed=False)

        return in_game(wrapped)

    def test_an_open_dialog_answers_exactly_once_with_every_path(self) -> None:
        def body(game, observed):
            answers = []
            devices.show_open_file_dialog(
                game, answers.append,
                filters=[FileDialogFilter("Text", "*.txt")], allow_multiple=True)
            observed["answers"] = answers
            observed["pending"] = devices.pending_dialog_count()

        observed = self._run(body, results=self.RESULTS)
        self.assertEqual(observed["answers"], [self.RESULTS])
        self.assertEqual(observed["pending"], 0,
                         "the trampoline must be released as the answer arrives")

    def test_cancellation_is_an_empty_result_rather_than_a_separate_signal(self) -> None:
        def body(game, observed):
            answers = []
            devices.show_open_file_dialog(game, answers.append)
            observed["answers"] = answers

        self.assertEqual(self._run(body, results=[])["answers"], [[]])

    def test_a_save_dialog_answers_with_one_path(self) -> None:
        def body(game, observed):
            answers = []
            devices.show_save_file_dialog(
                game, answers.append, filters=[FileDialogFilter("Text", "*.txt")])
            observed["answers"] = answers

        self.assertEqual(self._run(body, results=["/tmp/one.txt"])["answers"],
                         [["/tmp/one.txt"]])

    def test_a_folder_dialog_takes_no_filters_and_still_answers(self) -> None:
        def body(game, observed):
            answers = []
            devices.show_open_folder_dialog(game, answers.append, allow_multiple=True)
            observed["answers"] = answers

        self.assertEqual(self._run(body, results=["/tmp"])["answers"], [["/tmp"]])

    def test_a_non_callable_handler_is_refused_before_any_dialog_is_shown(self) -> None:
        def body(game, observed):
            try:
                devices.show_open_file_dialog(game, object())
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True
            observed["pending"] = devices.pending_dialog_count()

        observed = self._run(body, results=self.RESULTS)
        self.assertTrue(observed["refused"])
        self.assertEqual(observed["pending"], 0)

    def test_a_failing_show_call_releases_its_trampoline(self) -> None:
        """The rooted trampoline must not outlive a show call that never ran.

        The failure is forced at the seam -- a route name CNA does not export --
        because every argument the public functions validate is rejected before
        anything is rooted, and a dialog that *starts* always answers. What is
        asserted is the contract the ``except`` clause exists for.
        """
        from cna.extensions.devices import dialogs

        def body(game, observed):
            try:
                dialogs._dialog("cna_no_such_route_ext", game, lambda paths: None)
                observed["raised"] = None
            except BaseException as error:
                observed["raised"] = type(error).__name__
            observed["pending"] = dialogs.pending_dialog_count()

        observed = self._run(body, results=self.RESULTS)
        self.assertIsNotNone(observed["raised"])
        self.assertEqual(observed["pending"], 0)

    def test_a_filter_of_the_wrong_type_is_refused(self) -> None:
        def body(game, observed):
            try:
                devices.show_open_file_dialog(game, lambda paths: None,
                                              filters=["*.txt"])
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True

        self.assertTrue(self._run(body, results=self.RESULTS)["refused"])


@requires_devices
class SyntheticSystemTrayTests(unittest.TestCase):
    """SYNTHETIC_BACKEND_VERIFIED: no icon reaches anyone's desktop."""

    def test_an_entry_click_reaches_its_handler(self) -> None:
        def body(game, observed):
            with backend.open_test_system_tray(game, "tooltip") as tray:
                clicks: list[int] = []
                first = tray.add_entry("One", lambda: clicks.append(1))
                second = tray.add_entry("Two", lambda: clicks.append(2))
                backend.click_tray_entry(tray, second)
                backend.click_tray_entry(tray, first)
                observed["clicks"] = list(clicks)
                observed["indices"] = (first, second)

        observed = in_game(body)
        self.assertEqual(observed["indices"], (0, 1))
        self.assertEqual(observed["clicks"], [2, 1],
                         "each entry's own handler must run, in click order")

    def test_entry_state_round_trips(self) -> None:
        def body(game, observed):
            with backend.open_test_system_tray(game) as tray:
                index = tray.add_entry("One", lambda: None, checkable=True,
                                       initially_checked=True)
                observed["checked"] = tray.entry_checked(index)
                tray.set_entry_checked(index, False)
                observed["unchecked"] = tray.entry_checked(index)
                tray.set_entry_enabled(index, False)
                observed["disabled"] = tray.entry_enabled(index)
                tray.set_entry_label(index, "renamed")
                tray.set_tooltip("changed")

        observed = in_game(body)
        self.assertTrue(observed["checked"])
        self.assertFalse(observed["unchecked"])
        self.assertFalse(observed["disabled"])

    def test_a_handler_that_raises_does_not_unwind_into_c(self) -> None:
        def body(game, observed):
            with backend.open_test_system_tray(game) as tray:
                def explode() -> None:
                    raise KeyError("planted")

                index = tray.add_entry("One", explode)
                backend.click_tray_entry(tray, index)
                observed["failures"] = [type(error).__name__
                                        for _handler, error in tray.callback_failures]
                observed["still_usable"] = tray.entry_enabled(index)

        observed = in_game(body)
        self.assertEqual(observed["failures"], ["KeyError"])
        self.assertTrue(observed["still_usable"])

    def test_a_closed_tray_refuses_further_use(self) -> None:
        def body(game, observed):
            tray = backend.open_test_system_tray(game)
            tray.close()
            observed["closed"] = tray.closed
            try:
                tray.set_tooltip("x")
                observed["after"] = "succeeded"
            except DeviceDisposedError:
                observed["after"] = "refused"

        observed = in_game(body)
        self.assertTrue(observed["closed"])
        self.assertEqual(observed["after"], "refused")

    def test_a_non_callable_click_handler_is_refused(self) -> None:
        def body(game, observed):
            with backend.open_test_system_tray(game) as tray:
                try:
                    tray.add_entry("One", object())
                    observed["refused"] = False
                except TypeError:
                    observed["refused"] = True

        self.assertTrue(in_game(body)["refused"])


if __name__ == "__main__":
    unittest.main()
