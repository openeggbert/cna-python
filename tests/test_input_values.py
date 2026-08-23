from __future__ import annotations

import copy
import ctypes
import math
import unittest

from _cna_native import abi
from Microsoft.Xna.Framework import Vector2
from Microsoft.Xna.Framework.Input import (
    ButtonState, Buttons, GamePadButtons, GamePadCapabilities, GamePadDPad,
    GamePadState, GamePadThumbSticks, GamePadTriggers, GamePadType, KeyboardState,
    Keys, KeyState, Mouse, MouseState,
)


class KeyboardAndMouseValueTests(unittest.TestCase):
    def test_keyboard_filters_duplicates_and_orders_pressed_keys(self) -> None:
        state = KeyboardState([Keys.Z, 7, Keys.A, Keys.Z, Keys.F1, 300])
        self.assertEqual(state.GetPressedKeys(), [Keys.A, Keys.Z, Keys.F1])
        self.assertTrue(state.IsKeyDown(Keys.A))
        self.assertTrue(state.IsKeyUp(Keys.B))
        self.assertEqual(state[Keys.Z], KeyState.Down)
        self.assertEqual(state[Keys.B], KeyState.Up)
        self.assertEqual(copy.deepcopy(state), state)
        self.assertFalse(state.IsKeyDown(7))
        self.assertFalse(state.IsKeyDown(300))
        self.assertEqual(KeyboardState(None).GetPressedKeys(), [])

    def test_keyboard_native_words_and_value_hash_are_stable(self) -> None:
        native = abi.CNA_KeyboardState()
        native.pressed_key_words[1] = (1 << (int(Keys.A) - 64)) | (1 << (int(Keys.Z) - 64))
        state = KeyboardState._from_native(native)
        self.assertEqual(state.GetPressedKeys(), [Keys.A, Keys.Z])
        self.assertEqual(state.GetHashCode(), KeyboardState([Keys.Z, Keys.A]).GetHashCode())
        self.assertEqual(state.GetHashCode(), 67_108_866)

    def test_mouse_state_all_buttons_equality_hash_and_string(self) -> None:
        state = MouseState(10, -20, 120, ButtonState.Pressed, ButtonState.Released,
                           ButtonState.Pressed, ButtonState.Pressed, ButtonState.Released)
        self.assertEqual((state.X, state.Y, state.ScrollWheelValue), (10, -20, 120))
        self.assertEqual(state.LeftButton, ButtonState.Pressed)
        self.assertEqual(state.MiddleButton, ButtonState.Released)
        self.assertEqual(state.RightButton, ButtonState.Pressed)
        self.assertEqual(state.XButton1, ButtonState.Pressed)
        self.assertEqual(state.XButton2, ButtonState.Released)
        self.assertEqual(copy.copy(state), state)
        self.assertEqual(state.GetHashCode(), hash(state))
        self.assertEqual(str(state), "{X:10 Y:-20 Buttons:Left Right XButton1 Wheel:120}")
        captured = MouseState(12, -3, 120, ButtonState.Pressed, ButtonState.Released,
                              ButtonState.Pressed, ButtonState.Pressed, ButtonState.Released)
        self.assertEqual(captured.GetHashCode(), -120)

    def test_mouse_window_handle_is_a_mutable_static_property(self) -> None:
        descriptor = Mouse.__dict__["WindowHandle"]
        self.assertIsNotNone(descriptor.fget)
        self.assertIsNotNone(descriptor.fset)


class GamePadValueTests(unittest.TestCase):
    def test_component_clamping_copies_strings_and_hashes(self) -> None:
        sticks = GamePadThumbSticks(Vector2(2, -2), Vector2(0.5, -0.5))
        self.assertEqual(sticks.Left, Vector2(1, -1))
        left = sticks.Left
        left.X = 0
        self.assertEqual(sticks.Left, Vector2(1, -1))
        self.assertEqual(str(sticks), "{Left:{X:1 Y:-1} Right:{X:0.5 Y:-0.5}}")
        self.assertEqual(sticks.GetHashCode(), 0x7FFFFFFF)

        triggers = GamePadTriggers(-1, 2)
        self.assertEqual((triggers.Left, triggers.Right), (0, 1))
        self.assertEqual(str(triggers), "{Left:0 Right:1}")
        self.assertTrue(math.isnan(GamePadTriggers(math.nan, 0).Left))

        buttons = GamePadButtons(Buttons.A | Buttons.Y | Buttons.Back | Buttons.LeftTrigger)
        self.assertEqual(buttons.A, ButtonState.Pressed)
        self.assertEqual(buttons.Y, ButtonState.Pressed)
        self.assertEqual(buttons, GamePadButtons(Buttons.A | Buttons.Y | Buttons.Back))
        self.assertEqual(str(buttons), "{Buttons:A Y Back}")
        self.assertEqual(buttons.GetHashCode(), 1)

        dpad = GamePadDPad(ButtonState.Pressed, ButtonState.Released,
                           ButtonState.Released, ButtonState.Pressed)
        self.assertEqual(str(dpad), "{DPad:Up Right}")
        self.assertEqual(dpad.GetHashCode(), 0x7FFFFFFF)
        self.assertEqual(copy.deepcopy(dpad), dpad)

    def test_state_constructor_derives_analog_buttons_and_connection(self) -> None:
        state = GamePadState(Vector2(0.5, -0.5), Vector2(0.5, -0.5),
                             0.2, 0.0, [Buttons.A, Buttons.DPadUp, Buttons.LeftTrigger])
        self.assertTrue(state.IsConnected)
        self.assertEqual(state.PacketNumber, 0)
        self.assertEqual(state.Buttons.A, ButtonState.Pressed)
        self.assertEqual(state.DPad.Up, ButtonState.Pressed)
        self.assertTrue(state.IsButtonDown(Buttons.LeftThumbstickRight))
        self.assertTrue(state.IsButtonDown(Buttons.LeftThumbstickDown))
        self.assertTrue(state.IsButtonDown(Buttons.RightThumbstickRight))
        self.assertTrue(state.IsButtonDown(Buttons.RightThumbstickDown))
        self.assertTrue(state.IsButtonDown(Buttons.LeftTrigger))
        self.assertTrue(state.IsButtonDown(Buttons.A | Buttons.DPadUp))
        self.assertFalse(state.IsButtonDown(Buttons.A | Buttons.B))
        self.assertEqual(str(state), "{IsConnected:True}")
        self.assertEqual(copy.copy(state), state)
        self.assertEqual(GamePadState().ToString(), "{IsConnected:False}")
        self.assertTrue(GamePadState(Vector2.Zero, Vector2.Zero, 0, 0, None).IsConnected)

    def test_capabilities_default_and_native_projection(self) -> None:
        default = GamePadCapabilities()
        self.assertEqual(default.GamePadType, GamePadType.Unknown)
        self.assertFalse(default.IsConnected)
        self.assertFalse(default.HasAButton)
        native = abi.CNA_GamePadCapabilities()
        native.struct_size, native.struct_version = ctypes.sizeof(native), 1
        native.gamepad_type = 9
        native.is_connected = native.has_a_button = native.has_left_vibration_motor = 1
        value = GamePadCapabilities._from_native(native)
        self.assertEqual(value.GamePadType, GamePadType.BigButtonPad)
        self.assertTrue(value.IsConnected)
        self.assertTrue(value.HasAButton)
        self.assertTrue(value.HasLeftVibrationMotor)
        self.assertFalse(value.HasVoiceSupport)
        self.assertEqual(copy.deepcopy(value).GamePadType, GamePadType.BigButtonPad)


if __name__ == "__main__":
    unittest.main()
