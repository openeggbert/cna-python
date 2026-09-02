#!/usr/bin/env python3
"""Plants one defect at a time in the device and input families.

A test suite that has never been shown to fail is a suite nobody has measured.
Each mutation below is a plausible mistake in this family specifically -- an axis
swapped, a tick count rounded through a float, a callback still rooted after
unsubscription, a sentinel treated as a value, a byte count used as a character
count -- and each one must make a *focused* test fail, not merely something
somewhere.

The fixtures are mutated too, and on purpose. A fixture whose axes were all the
same number would let an axis swap pass, and a timestamp below 2**53 would let a
float conversion pass; planting exactly those and requiring the suite to *stop
failing* is not what is measured here -- what is measured is that a wrong
implementation is caught by a test that names the thing that is wrong.

Needs ``CNA_NATIVE_LIBRARY`` pointing at a build with the device-services layer.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

#: (label, file, old, new, the test module the kill is expected in)
MUTATIONS = [
    # --- timestamps ----------------------------------------------------------
    ("timestamp: subtract the offset in floating point",
     "src/cna/extensions/devices/values.py",
     "        return self.ticks - self.offset_ticks",
     "        return int(float(self.ticks) - float(self.offset_ticks))",
     "tests.test_devices_sensors"),
    ("timestamp: add the offset instead of subtracting it",
     "src/cna/extensions/devices/values.py",
     "        return self.ticks - self.offset_ticks",
     "        return self.ticks + self.offset_ticks",
     "tests.test_devices_sensors"),
    ("timestamp: round the sub-microsecond remainder away",
     "src/cna/extensions/devices/values.py",
     "        return self.ticks % TICKS_PER_MICROSECOND",
     "        return 0",
     "tests.test_devices_sensors"),
    ("timestamp: read the tick count through a double on the way out",
     "src/cna/extensions/devices/values.py",
     "        return cls(int(value.ticks), int(value.offset_ticks))",
     "        return cls(int(float(value.ticks)), int(value.offset_ticks))",
     "tests.test_devices_sensors"),
    ("timestamp: accept a sub-microsecond offset by rounding it",
     "src/cna/extensions/devices/values.py",
     "        if self.offset_ticks % TICKS_PER_MICROSECOND:\n"
     "            raise ValueError(\n"
     "                \"the UTC offset is not a whole number of microseconds and cannot \"\n"
     "                f\"be a timedelta: {self.offset_ticks} ticks\")",
     "        pass",
     "tests.test_devices_sensors"),
    ("timestamp: let a float tick count through",
     "src/cna/extensions/devices/values.py",
     "            if isinstance(value, bool) or not isinstance(value, int):\n"
     "                raise TypeError(f\"{name} must be an int, not {type(value).__name__}\")",
     "            pass",
     "tests.test_devices_sensors"),

    # --- readings ------------------------------------------------------------
    ("accelerometer reading: swap the X and Y axes on the way in",
     "src/cna/extensions/devices/sensors.py",
     "    native.x, native.y, native.z = float(value.X), float(value.Y), float(value.Z)",
     "    native.x, native.y, native.z = float(value.Y), float(value.X), float(value.Z)",
     "tests.test_devices_sensors"),
    ("reading: read Z where Y is stored on the way out",
     "src/cna/extensions/devices/sensors.py",
     "    return Vector3(float(value.x), float(value.y), float(value.z))",
     "    return Vector3(float(value.x), float(value.z), float(value.y))",
     "tests.test_devices_sensors"),
    ("attitude: transpose the rotation matrix",
     "src/cna/extensions/devices/sensors.py",
     "        matrix = Matrix(*(float(getattr(value.rotation_matrix, f\"m{row}{column}\"))\n"
     "                          for row in range(1, 5) for column in range(1, 5)))",
     "        matrix = Matrix(*(float(getattr(value.rotation_matrix, f\"m{column}{row}\"))\n"
     "                          for row in range(1, 5) for column in range(1, 5)))",
     "tests.test_devices_sensors"),
    ("attitude: interchange pitch and roll",
     "src/cna/extensions/devices/sensors.py",
     "                   float(value.pitch), float(value.roll), float(value.yaw),",
     "                   float(value.roll), float(value.pitch), float(value.yaw),",
     "tests.test_devices_sensors"),
    ("compass: interchange the magnetic and true headings",
     "src/cna/extensions/devices/sensors.py",
     "                   float(value.heading_accuracy), float(value.magnetic_heading),\n"
     "                   float(value.true_heading), _vector(value.magnetometer_reading))",
     "                   float(value.heading_accuracy), float(value.true_heading),\n"
     "                   float(value.magnetic_heading), _vector(value.magnetometer_reading))",
     "tests.test_devices_sensors"),
    ("motion: interchange gravity and device acceleration",
     "src/cna/extensions/devices/sensors.py",
     "                   _vector(value.device_acceleration),\n"
     "                   _vector(value.device_rotation_rate),\n"
     "                   _vector(value.gravity))",
     "                   _vector(value.gravity),\n"
     "                   _vector(value.device_rotation_rate),\n"
     "                   _vector(value.device_acceleration))",
     "tests.test_devices_sensors"),
    ("event info: narrow the double axes to single precision",
     "src/cna/extensions/devices/sensors.py",
     "        return cls(DateTimeOffset._from_native(value.timestamp),\n"
     "                   float(value.x), float(value.y), float(value.z))",
     "        import ctypes as _c\n"
     "        return cls(DateTimeOffset._from_native(value.timestamp),\n"
     "                   float(_c.c_float(value.x).value), float(_c.c_float(value.y).value),\n"
     "                   float(_c.c_float(value.z).value))",
     "tests.test_devices_sensors"),

    # --- sensor lifetime and callbacks --------------------------------------
    ("subscription: keep the callback rooted after unsubscribing",
     "src/cna/extensions/devices/sensors.py",
     "        self._callbacks.release(subscription._key)\n"
     "        if not self._handle.closed:\n"
     "            _support.call(\"cna_sensor_unsubscribe_ext\",\n"
     "                          c.c_uint64(subscription._handle))",
     "        pass",
     "tests.test_devices_sensors"),
    ("close: destroy the sensor without releasing its subscriptions",
     "src/cna/extensions/devices/sensors.py",
     "        for subscription in list(self._subscriptions):\n"
     "            subscription.close()\n"
     "        self._callbacks.clear()\n"
     "        self._handle.close()",
     "        self._handle.close()",
     "tests.test_devices_sensors"),
    ("callback boundary: let a handler exception unwind into C",
     "src/_cna_native/family_support.py",
     "            except BaseException as error:  # noqa: BLE001 - must not unwind into C\n"
     "                self.failures.append((handler, error))",
     "            except ZeroDivisionError:\n"
     "                pass",
     "tests.test_devices_sensors"),
    ("interval: accept a float tick count",
     "src/_cna_native/family_support.py",
     "    if isinstance(value, bool) or not isinstance(value, int):\n"
     "        raise TypeError(f\"{what} must be an int, not {type(value).__name__}\")",
     "    value = int(value)\n"
     "    if False:\n"
     "        raise TypeError(what)",
     "tests.test_devices_sensors"),

    # --- host services -------------------------------------------------------
    ("power: let the unknown sentinel through as a value",
     "src/cna/extensions/devices/host.py",
     "    return PowerInformation(state,\n"
     "                            None if percent < 0 else int(percent),\n"
     "                            None if seconds < 0 else int(seconds))",
     "    return PowerInformation(state, int(percent), int(seconds))",
     "tests.test_devices_services"),
    ("locales: sort the host's preference order",
     "src/cna/extensions/devices/host.py",
     "    return result",
     "    return sorted(result, key=lambda entry: (entry.country, entry.language))",
     "tests.test_devices_services"),
    ("clipboard: report the character count as the byte count",
     "src/cna/extensions/input/clipboard.py",
     "    return _support.out_u64(\"cna_clipboard_get_text_size\",\n"
     "                            _in.game_handle(game, \"clipboard\"))",
     "    return len(clipboard_text(game))",
     "tests.test_devices_services"),

    # --- vibration -----------------------------------------------------------
    ("vibration: interchange the two motors",
     "src/cna/extensions/devices/vibration.py",
     "                  c.c_float(real(large_motor, \"large_motor\")),\n"
     "                  c.c_float(real(small_motor, \"small_motor\")),",
     "                  c.c_float(real(small_motor, \"small_motor\")),\n"
     "                  c.c_float(real(large_motor, \"large_motor\")),",
     "tests.test_devices_services"),
    ("vibration: round the duration through milliseconds",
     "src/cna/extensions/devices/vibration.py",
     "                  c.c_int64(checked(duration_ticks, \"int64\", \"duration_ticks\")),\n"
     "                  c.c_float(real(intensity, \"intensity\")))",
     "                  c.c_int64(checked(duration_ticks, \"int64\", \"duration_ticks\")\n"
     "                            // 10_000 * 10_000),\n"
     "                  c.c_float(real(intensity, \"intensity\")))",
     "tests.test_devices_services"),
    ("vibration: clamp an over-long duration instead of letting CNA refuse it",
     "src/cna/extensions/devices/vibration.py",
     "    _support.call(\"cna_vibrate_controller_start\",\n"
     "                  _dev.game_handle(game, \"vibration\"),\n"
     "                  c.c_int64(checked(duration_ticks, \"int64\", \"duration_ticks\")))",
     "    _support.call(\"cna_vibrate_controller_start\",\n"
     "                  _dev.game_handle(game, \"vibration\"),\n"
     "                  c.c_int64(min(checked(duration_ticks, \"int64\", \"duration_ticks\"),\n"
     "                                50_000_000)))",
     "tests.test_devices_services"),

    # --- dialogs and the tray -----------------------------------------------
    ("file dialog: keep the trampoline rooted after the answer arrives",
     "src/cna/extensions/devices/dialogs.py",
     "        finally:\n"
     "            # Exactly once: the trampoline is dropped as the answer is delivered,\n"
     "            # so a backend that called twice would fail to find it the second\n"
     "            # time rather than delivering a second answer.\n"
     "            _pending.release(key)",
     "        finally:\n"
     "            pass",
     "tests.test_devices_services"),
    ("file dialog: drop every chosen path after the first",
     "src/cna/extensions/devices/dialogs.py",
     "            on_result(chosen)",
     "            on_result(chosen[:1])",
     "tests.test_devices_services"),
    ("file dialog: leave the trampoline rooted when the show call fails",
     "src/cna/extensions/devices/dialogs.py",
     "    except BaseException:\n"
     "        _pending.release(key)\n"
     "        raise",
     "    except BaseException:\n"
     "        raise",
     "tests.test_devices_services"),
    ("message box: report the button count as the chosen index",
     "src/cna/extensions/devices/dialogs.py",
     "        array, c.c_uint64(len(buttons)))",
     "        array, c.c_uint64(len(buttons))) and len(buttons)",
     "tests.test_devices_services"),
    ("tray: give every entry the first entry's handler",
     "src/cna/extensions/devices/dialogs.py",
     "        trampoline = self._callbacks.root(\n"
     "            index, _devices.CNA_TrayEntryClickCallback, adapt)",
     "        trampoline = self._callbacks.root(\n"
     "            0, _devices.CNA_TrayEntryClickCallback, adapt)",
     "tests.test_devices_services"),
    ("tray: clear the rooted handlers before the tray is destroyed",
     "src/cna/extensions/devices/dialogs.py",
     "        if not isinstance(entry, FileDialogFilter):",
     "        if False:",
     "tests.test_devices_services"),

    # --- camera --------------------------------------------------------------
    ("camera: accept a pixel sequence shorter than the frame",
     "src/cna/extensions/devices/testing.py",
     "    if len(pixels) != width * height:",
     "    if False:",
     "tests.test_devices_services"),
    ("camera: write the blue channel where red belongs",
     "src/cna/extensions/devices/testing.py",
     "        array[index].r = int(colour.R)",
     "        array[index].r = int(colour.B)",
     "tests.test_devices_services"),

    # --- extended input: UTF-16 ---------------------------------------------
    ("accumulator: treat every code unit as a whole character",
     "src/cna/extensions/input/text.py",
     "        if 0xD800 <= unit <= 0xDBFF:",
     "        if False:",
     "tests.test_input_extensions"),
    ("accumulator: combine the surrogate pair with the wrong shift",
     "src/cna/extensions/input/text.py",
     "            self._parts.append(chr(0x10000 + ((high - 0xD800) << 10) + (unit - 0xDC00)))",
     "            self._parts.append(chr(0x10000 + ((high - 0xD800) << 11) + (unit - 0xDC00)))",
     "tests.test_input_extensions"),
    ("accumulator: replace an unpaired surrogate instead of reporting it",
     "src/cna/extensions/input/text.py",
     "            if self._pending is None:\n"
     "                self.unpaired.append(unit)\n"
     "                return",
     "            if self._pending is None:\n"
     "                self._parts.append(chr(0xFFFD))\n"
     "                return",
     "tests.test_input_extensions"),
    ("accumulator: forget the pending surrogate when a plain unit follows",
     "src/cna/extensions/input/text.py",
     "        if self._pending is not None:\n"
     "            self.unpaired.append(self._pending)\n"
     "            self._pending = None\n"
     "        self._parts.append(chr(unit))",
     "        self._pending = None\n"
     "        self._parts.append(chr(unit))",
     "tests.test_input_extensions"),
    ("text input: encode the raised string as UTF-8 rather than UTF-16",
     "src/cna/extensions/input/testing.py",
     "    encoded = text.encode(\"utf-16-le\")",
     "    encoded = text.encode(\"utf-8\") + b\"\\x00\"",
     "tests.test_input_extensions"),

    # --- extended input: IME -------------------------------------------------
    ("candidates: read one candidate fewer than the event carries",
     "src/cna/extensions/input/text.py",
     "        count = int(info.candidate_count)",
     "        count = max(int(info.candidate_count) - 1, 0)",
     "tests.test_input_extensions"),
    ("candidates: let the no-selection sentinel through as an index",
     "src/cna/extensions/input/text.py",
     "            candidates, None if selected < 0 else selected,",
     "            candidates, selected,",
     "tests.test_input_extensions"),
    ("composition: interchange the selection start and length",
     "src/cna/extensions/input/text.py",
     "        handler(TextEditing(_text_of(info.text), int(info.start), int(info.length)))",
     "        handler(TextEditing(_text_of(info.text), int(info.length), int(info.start)))",
     "tests.test_input_extensions"),
    ("text subscription: keep the trampoline rooted after unsubscribing",
     "src/cna/extensions/input/text.py",
     "        _roots.release(self._key)\n"
     "        _support.call(\"cna_text_input_unsubscribe_ext\", c.c_uint64(self._handle))",
     "        pass",
     "tests.test_input_extensions"),

    # --- extended input: hotplug and devices ---------------------------------
    ("hotplug: send every input-device event to the keyboard-connected route",
     "src/cna/extensions/input/devices.py",
     "def on_mouse_connected(handler: Callable[[int], None]) -> InputDeviceSubscription:\n"
     "    \"\"\"Calls ``handler(device_id)`` when a mouse is plugged in.\"\"\"\n"
     "    return _subscribe(\"cna_input_devices_subscribe_mouse_connected_ext\", handler)",
     "def on_mouse_connected(handler: Callable[[int], None]) -> InputDeviceSubscription:\n"
     "    \"\"\"Calls ``handler(device_id)`` when a mouse is plugged in.\"\"\"\n"
     "    return _subscribe(\"cna_input_devices_subscribe_keyboard_connected_ext\", handler)",
     "tests.test_input_extensions"),
    ("device sensors: report an absent reading as a zero vector",
     "src/cna/extensions/input/devices.py",
     "    if not available.value:\n        return None",
     "    if False:\n        return None",
     "tests.test_input_extensions"),
    ("device power: let the unknown sentinels through as values",
     "src/cna/extensions/input/devices.py",
     "        None if seconds.value < 0 else int(seconds.value),\n"
     "        None if percent.value < 0 else int(percent.value))",
     "        int(seconds.value), int(percent.value))",
     "tests.test_input_extensions"),
    ("enumeration: read the mouse list where the keyboard list belongs",
     "src/cna/extensions/input/devices.py",
     "    return _devices(game, \"keyboard\")",
     "    return _devices(game, \"mouse\")",
     "tests.test_input_extensions"),

    # --- extended input: joysticks and haptics -------------------------------
    ("hat position: project the identities as a bit set",
     "src/cna/extensions/input/values.py",
     "class JoystickHatPosition(IntEnum):",
     "class JoystickHatPosition(IntFlag):",
     "tests.test_input_extensions"),
    ("joystick capabilities: let the unknown battery sentinel through",
     "src/cna/extensions/input/joystick.py",
     "        None if percent < 0 else percent, bool(native.is_connected),",
     "        percent, bool(native.is_connected),",
     "tests.test_input_extensions"),
    ("haptic capabilities: let the -1 limits through as counts",
     "src/cna/extensions/input/haptics.py",
     "            None if limit < 0 else limit, None if playing < 0 else playing,",
     "            limit, playing,",
     "tests.test_input_extensions"),
    ("haptic effect: skip the per-axis range check",
     "src/cna/extensions/input/haptics.py",
     "            target[index] = checked(value, width, f\"{name}[{index}]\")",
     "            target[index] = value & 0xFFFF",
     "tests.test_input_extensions"),
    ("haptic effect: drop the custom sample data",
     "src/cna/extensions/input/haptics.py",
     "    samples = tuple(effect.custom_data)",
     "    samples = ()",
     "tests.test_input_extensions"),
    ("haptic effect: interchange the deadband and the centre",
     "src/cna/extensions/input/haptics.py",
     "    \"deadband\": \"uint16\", \"center\": \"int16\",",
     "    \"deadband\": \"int16\", \"center\": \"uint16\",",
     "tests.test_input_extensions"),

    # --- extended input: cursors ---------------------------------------------
    ("cursor: let the active cursor be closed underneath the platform",
     "src/cna/extensions/input/cursor.py",
     "        if _active is self and not force:",
     "        if False:",
     "tests.test_input_extensions"),
]


def run(module: str) -> tuple[bool, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=str(ROOT), env=environment, capture_output=True, text=True, timeout=1800)
    return completed.returncode == 0, completed.stderr


def main() -> int:
    killed, survived, inapplicable = [], [], []
    for label, relative, old, new, module in MUTATIONS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        if original.count(old) != 1:
            inapplicable.append((label, f"anchor appears {original.count(old)} times"))
            continue
        path.write_text(original.replace(old, new), encoding="utf-8")
        try:
            for cache in ROOT.rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
            passed, stderr = run(module)
        finally:
            path.write_text(original, encoding="utf-8")
            for cache in ROOT.rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
        if passed:
            survived.append((label, module))
        else:
            names = [line.split(" ")[1] for line in stderr.splitlines()
                     if line.startswith(("FAIL: ", "ERROR: "))]
            killed.append((label, module, names[:3]))

    print(f"PLANTED={len(MUTATIONS)}")
    print(f"KILLED={len(killed)}")
    print(f"SURVIVED={len(survived)}")
    print(f"INAPPLICABLE={len(inapplicable)}")
    for label, module, names in killed:
        print(f"  KILLED  {label}\n            by {module}: {', '.join(names) or '(import)'}")
    for label, module in survived:
        print(f"  SURVIVED {label} (ran {module})")
    for label, reason in inapplicable:
        print(f"  SKIPPED  {label}: {reason}")
    return 1 if survived or inapplicable else 0


if __name__ == "__main__":
    raise SystemExit(main())
