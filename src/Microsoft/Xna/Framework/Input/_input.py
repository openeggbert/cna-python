"""XNA input values and real CNA polling facades."""

from __future__ import annotations

import ctypes as c
from enum import IntEnum, IntFlag

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.runtime_context import current_game

from .._game import PlayerIndex
from .._math import Vector2
from .._numeric import f32, int32


class ButtonState(IntEnum):
    Released = 0
    Pressed = 1


class KeyState(IntEnum):
    Up = 0
    Down = 1


class Keys(IntEnum):
    A = 65
    Add = 107
    Apps = 93
    Attn = 246
    B = 66
    Back = 8
    BrowserBack = 166
    BrowserFavorites = 171
    BrowserForward = 167
    BrowserHome = 172
    BrowserRefresh = 168
    BrowserSearch = 170
    BrowserStop = 169
    C = 67
    CapsLock = 20
    ChatPadGreen = 202
    ChatPadOrange = 203
    Crsel = 247
    D = 68
    D0 = 48
    D1 = 49
    D2 = 50
    D3 = 51
    D4 = 52
    D5 = 53
    D6 = 54
    D7 = 55
    D8 = 56
    D9 = 57
    Decimal = 110
    Delete = 46
    Divide = 111
    Down = 40
    E = 69
    End = 35
    Enter = 13
    EraseEof = 249
    Escape = 27
    Execute = 43
    Exsel = 248
    F = 70
    F1 = 112
    F10 = 121
    F11 = 122
    F12 = 123
    F13 = 124
    F14 = 125
    F15 = 126
    F16 = 127
    F17 = 128
    F18 = 129
    F19 = 130
    F2 = 113
    F20 = 131
    F21 = 132
    F22 = 133
    F23 = 134
    F24 = 135
    F3 = 114
    F4 = 115
    F5 = 116
    F6 = 117
    F7 = 118
    F8 = 119
    F9 = 120
    G = 71
    H = 72
    Help = 47
    Home = 36
    I = 73
    ImeConvert = 28
    ImeNoConvert = 29
    Insert = 45
    J = 74
    K = 75
    Kana = 21
    Kanji = 25
    L = 76
    LaunchApplication1 = 182
    LaunchApplication2 = 183
    LaunchMail = 180
    Left = 37
    LeftAlt = 164
    LeftControl = 162
    LeftShift = 160
    LeftWindows = 91
    M = 77
    MediaNextTrack = 176
    MediaPlayPause = 179
    MediaPreviousTrack = 177
    MediaStop = 178
    Multiply = 106
    N = 78
    None_ = 0
    NumLock = 144
    NumPad0 = 96
    NumPad1 = 97
    NumPad2 = 98
    NumPad3 = 99
    NumPad4 = 100
    NumPad5 = 101
    NumPad6 = 102
    NumPad7 = 103
    NumPad8 = 104
    NumPad9 = 105
    O = 79
    Oem8 = 223
    OemAuto = 243
    OemBackslash = 226
    OemClear = 254
    OemCloseBrackets = 221
    OemComma = 188
    OemCopy = 242
    OemEnlW = 244
    OemMinus = 189
    OemOpenBrackets = 219
    OemPeriod = 190
    OemPipe = 220
    OemPlus = 187
    OemQuestion = 191
    OemQuotes = 222
    OemSemicolon = 186
    OemTilde = 192
    P = 80
    Pa1 = 253
    PageDown = 34
    PageUp = 33
    Pause = 19
    Play = 250
    Print = 42
    PrintScreen = 44
    ProcessKey = 229
    Q = 81
    R = 82
    Right = 39
    RightAlt = 165
    RightControl = 163
    RightShift = 161
    RightWindows = 92
    S = 83
    Scroll = 145
    Select = 41
    SelectMedia = 181
    Separator = 108
    Sleep = 95
    Space = 32
    Subtract = 109
    T = 84
    Tab = 9
    U = 85
    Up = 38
    V = 86
    VolumeDown = 174
    VolumeMute = 173
    VolumeUp = 175
    W = 87
    X = 88
    Y = 89
    Z = 90
    Zoom = 251


class KeyboardState:
    __slots__ = ("_pressed",)

    def __init__(self, keys: object = ()) -> None:
        try:
            values = tuple(Keys(value) for value in keys)
        except TypeError as error:
            raise TypeError("KeyboardState expects an iterable of Keys") from error
        self._pressed = frozenset(values)

    @classmethod
    def _from_native(cls, state: abi.CNA_KeyboardState) -> "KeyboardState":
        return cls(Keys(key) for key in range(256)
                   if state.pressed_key_words[key // 64] & (1 << (key % 64)))

    def IsKeyDown(self, key: Keys) -> bool:
        return Keys(key) in self._pressed

    def IsKeyUp(self, key: Keys) -> bool:
        return not self.IsKeyDown(key)

    def GetPressedKeys(self) -> list[Keys]:
        return sorted(self._pressed, key=int)

    def __getitem__(self, key: Keys) -> KeyState:
        return KeyState.Down if self.IsKeyDown(key) else KeyState.Up

    def __eq__(self, other: object) -> bool:
        return isinstance(other, KeyboardState) and self._pressed == other._pressed

    def __hash__(self) -> int:
        words = [0] * 8
        for key in self._pressed:
            value = int(key)
            words[value // 32] |= 1 << (value % 32)
        result = 0
        for word in words:
            result ^= word
        return result if result < 0x80000000 else result - 0x100000000

    def Equals(self, other: object) -> bool: return self == other
    def GetHashCode(self) -> int: return hash(self)


def _native_game_handle() -> int:
    game = current_game()
    if getattr(game, "_disposed", False) or game._host is None:
        raise RuntimeError("input polling requires an initialized CNA game")
    return game._host.handle


class Keyboard:
    def __new__(cls):
        raise TypeError("Keyboard is static")

    @staticmethod
    def GetState(*args: object) -> KeyboardState:
        state = abi.CNA_KeyboardState()
        state.struct_size, state.struct_version = c.sizeof(state), 1
        library = get_library()
        if not args:
            result = library.cna_keyboard_get_state(_native_game_handle(), c.byref(state))
            operation = "cna_keyboard_get_state"
        elif len(args) == 1:
            player = PlayerIndex(args[0])
            result = library.cna_keyboard_get_state_for_player(_native_game_handle(), int(player), c.byref(state))
            operation = "cna_keyboard_get_state_for_player"
        else:
            raise TypeError("Keyboard.GetState expects zero arguments or PlayerIndex")
        library.check(result, operation)
        return KeyboardState._from_native(state)


class MouseState:
    __slots__ = ("_x", "_y", "_wheel", "_left", "_middle", "_right", "_x1", "_x2")

    def __init__(self, x: int = 0, y: int = 0, scrollWheel: int = 0,
                 leftButton: ButtonState = ButtonState.Released,
                 middleButton: ButtonState = ButtonState.Released,
                 rightButton: ButtonState = ButtonState.Released,
                 xButton1: ButtonState = ButtonState.Released,
                 xButton2: ButtonState = ButtonState.Released) -> None:
        self._x, self._y, self._wheel = int32(x), int32(y), int32(scrollWheel)
        self._left, self._middle, self._right = ButtonState(leftButton), ButtonState(middleButton), ButtonState(rightButton)
        self._x1, self._x2 = ButtonState(xButton1), ButtonState(xButton2)

    @property
    def X(self): return self._x
    @property
    def Y(self): return self._y
    @property
    def ScrollWheelValue(self): return self._wheel
    @property
    def LeftButton(self): return self._left
    @property
    def MiddleButton(self): return self._middle
    @property
    def RightButton(self): return self._right
    @property
    def XButton1(self): return self._x1
    @property
    def XButton2(self): return self._x2
    def __eq__(self, other: object) -> bool:
        return isinstance(other, MouseState) and tuple(self) == tuple(other)
    def __iter__(self): return iter((self.X, self.Y, self.ScrollWheelValue, self.LeftButton, self.MiddleButton, self.RightButton, self.XButton1, self.XButton2))
    def __hash__(self): return self.X ^ self.Y ^ int(self.LeftButton) ^ int(self.RightButton) ^ int(self.MiddleButton) ^ int(self.XButton1) ^ int(self.XButton2) ^ self.ScrollWheelValue
    def Equals(self, other: object) -> bool: return self == other
    def GetHashCode(self) -> int: return hash(self)
    def ToString(self) -> str:
        names = [name for name, value in (("Left", self.LeftButton), ("Right", self.RightButton), ("Middle", self.MiddleButton), ("XButton1", self.XButton1), ("XButton2", self.XButton2)) if value is ButtonState.Pressed]
        return f"{{X:{self.X} Y:{self.Y} Buttons:{' '.join(names) if names else 'None'} Wheel:{self.ScrollWheelValue}}}"
    __str__ = ToString

    @classmethod
    def _from_native(cls, state: abi.CNA_MouseState) -> "MouseState":
        button = lambda mask: ButtonState.Pressed if state.pressed_buttons & mask else ButtonState.Released
        return cls(state.x, state.y, state.scroll_wheel, button(1), button(2), button(4), button(8), button(16))


class Mouse:
    def __new__(cls):
        raise TypeError("Mouse is static")

    @staticmethod
    def GetState() -> MouseState:
        state = abi.CNA_MouseState()
        state.struct_size, state.struct_version = c.sizeof(state), 1
        library = get_library()
        library.check(library.cna_mouse_get_state(_native_game_handle(), c.byref(state)), "cna_mouse_get_state")
        return MouseState._from_native(state)

    @staticmethod
    def SetPosition(x: int, y: int) -> None:
        library = get_library()
        library.check(library.cna_mouse_set_position(_native_game_handle(), int32(x), int32(y)),
                      "cna_mouse_set_position")


class Buttons(IntFlag):
    DPadUp = 0x00000001
    DPadDown = 0x00000002
    DPadLeft = 0x00000004
    DPadRight = 0x00000008
    Start = 0x00000010
    Back = 0x00000020
    LeftStick = 0x00000040
    RightStick = 0x00000080
    LeftShoulder = 0x00000100
    RightShoulder = 0x00000200
    BigButton = 0x00000800
    A = 0x00001000
    B = 0x00002000
    X = 0x00004000
    Y = 0x00008000
    LeftThumbstickLeft = 0x00200000
    RightTrigger = 0x00400000
    LeftTrigger = 0x00800000
    RightThumbstickUp = 0x01000000
    RightThumbstickDown = 0x02000000
    RightThumbstickRight = 0x04000000
    RightThumbstickLeft = 0x08000000
    LeftThumbstickUp = 0x10000000
    LeftThumbstickDown = 0x20000000
    LeftThumbstickRight = 0x40000000


class GamePadDeadZone(IntEnum):
    None_ = 0
    IndependentAxes = 1
    Circular = 2


class GamePadButtons:
    __slots__ = ("_buttons",)
    def __init__(self, buttons: Buttons = Buttons(0)) -> None: self._buttons = Buttons(buttons)
    def _pressed(self, value: Buttons) -> ButtonState: return ButtonState.Pressed if self._buttons & value else ButtonState.Released
    @property
    def A(self): return self._pressed(Buttons.A)
    @property
    def B(self): return self._pressed(Buttons.B)
    @property
    def X(self): return self._pressed(Buttons.X)
    @property
    def Y(self): return self._pressed(Buttons.Y)
    @property
    def Back(self): return self._pressed(Buttons.Back)
    @property
    def Start(self): return self._pressed(Buttons.Start)
    @property
    def BigButton(self): return self._pressed(Buttons.BigButton)
    @property
    def LeftShoulder(self): return self._pressed(Buttons.LeftShoulder)
    @property
    def RightShoulder(self): return self._pressed(Buttons.RightShoulder)
    @property
    def LeftStick(self): return self._pressed(Buttons.LeftStick)
    @property
    def RightStick(self): return self._pressed(Buttons.RightStick)
    def __eq__(self, other): return isinstance(other, GamePadButtons) and self._buttons == other._buttons
    def __hash__(self): return int(self._buttons)


class GamePadDPad:
    __slots__ = ("_buttons",)
    def __init__(self, up=ButtonState.Released, down=ButtonState.Released, left=ButtonState.Released, right=ButtonState.Released):
        self._buttons = Buttons(0)
        for state, value in ((up,Buttons.DPadUp),(down,Buttons.DPadDown),(left,Buttons.DPadLeft),(right,Buttons.DPadRight)):
            if ButtonState(state) is ButtonState.Pressed: self._buttons |= value
    def _pressed(self, value): return ButtonState.Pressed if self._buttons & value else ButtonState.Released
    @property
    def Up(self): return self._pressed(Buttons.DPadUp)
    @property
    def Down(self): return self._pressed(Buttons.DPadDown)
    @property
    def Left(self): return self._pressed(Buttons.DPadLeft)
    @property
    def Right(self): return self._pressed(Buttons.DPadRight)
    def __eq__(self, other): return isinstance(other, GamePadDPad) and self._buttons == other._buttons
    def __hash__(self): return int(self._buttons)


class GamePadThumbSticks:
    __slots__ = ("_left", "_right")
    def __init__(self, left: Vector2 = Vector2.Zero, right: Vector2 = Vector2.Zero):
        self._left, self._right = Vector2(left.X, left.Y), Vector2(right.X, right.Y)
    @property
    def Left(self): return Vector2(self._left.X, self._left.Y)
    @property
    def Right(self): return Vector2(self._right.X, self._right.Y)
    def __eq__(self, other): return isinstance(other, GamePadThumbSticks) and self._left == other._left and self._right == other._right
    def __hash__(self): return hash((self._left,self._right))


class GamePadTriggers:
    __slots__ = ("_left", "_right")
    def __init__(self, left: float = 0.0, right: float = 0.0):
        self._left, self._right = f32(max(0.0,min(1.0,left))), f32(max(0.0,min(1.0,right)))
    @property
    def Left(self): return self._left
    @property
    def Right(self): return self._right
    def __eq__(self, other): return isinstance(other, GamePadTriggers) and self.Left == other.Left and self.Right == other.Right
    def __hash__(self): return hash((self.Left,self.Right))


class GamePadState:
    __slots__ = ("_connected", "_packet", "_buttons_mask", "_thumbs", "_triggers")
    def __init__(self, *args: object, _connected: bool = False, _packet: int = 0, _mask: Buttons = Buttons(0)) -> None:
        self._connected, self._packet, self._buttons_mask = _connected, int32(_packet), Buttons(_mask)
        self._thumbs, self._triggers = GamePadThumbSticks(), GamePadTriggers()
        if args:
            if len(args) < 2 or not isinstance(args[0], Vector2) or not isinstance(args[1], Vector2):
                raise TypeError("GamePadState expects left/right Vector2 followed by trigger/buttons")
            left_trigger = args[2] if len(args) > 2 else 0.0
            right_trigger = args[3] if len(args) > 3 else 0.0
            mask = Buttons(0)
            for button in args[4:]: mask |= Buttons(button)
            self._thumbs, self._triggers, self._buttons_mask = GamePadThumbSticks(args[0],args[1]), GamePadTriggers(left_trigger,right_trigger), mask
    @property
    def IsConnected(self): return self._connected
    @property
    def PacketNumber(self): return self._packet
    @property
    def Buttons(self): return GamePadButtons(self._buttons_mask)
    @property
    def DPad(self):
        return GamePadDPad(*(ButtonState.Pressed if self._buttons_mask & value else ButtonState.Released for value in (Buttons.DPadUp,Buttons.DPadDown,Buttons.DPadLeft,Buttons.DPadRight)))
    @property
    def ThumbSticks(self): return self._thumbs
    @property
    def Triggers(self): return self._triggers
    def IsButtonDown(self, button: Buttons): return bool(self._buttons_mask & Buttons(button))
    def IsButtonUp(self, button: Buttons): return not self.IsButtonDown(button)
    def __eq__(self, other): return isinstance(other,GamePadState) and (self._connected,self._packet,self._buttons_mask,self._thumbs,self._triggers)==(other._connected,other._packet,other._buttons_mask,other._thumbs,other._triggers)
    def __hash__(self): return hash((self._connected,self._packet,self._buttons_mask,self._thumbs,self._triggers))
    def Equals(self, other): return self == other

    @classmethod
    def _from_native(cls, state: abi.CNA_GamePadState) -> "GamePadState":
        result=cls(_connected=state.is_connected!=0,_packet=state.packet_number,_mask=Buttons(state.pressed_buttons))
        result._thumbs=GamePadThumbSticks(Vector2(state.analog.left_thumb_stick.x,state.analog.left_thumb_stick.y),Vector2(state.analog.right_thumb_stick.x,state.analog.right_thumb_stick.y))
        result._triggers=GamePadTriggers(state.analog.left_trigger,state.analog.right_trigger)
        return result


class GamePad:
    def __new__(cls): raise TypeError("GamePad is static")
    @staticmethod
    def GetState(playerIndex: PlayerIndex, deadZoneMode: GamePadDeadZone = GamePadDeadZone.IndependentAxes) -> GamePadState:
        state=abi.CNA_GamePadState();state.struct_size,state.struct_version=c.sizeof(state),1
        library=get_library()
        library.check(library.cna_gamepad_get_state_with_dead_zone(_native_game_handle(),int(PlayerIndex(playerIndex)),int(GamePadDeadZone(deadZoneMode)),c.byref(state)),"cna_gamepad_get_state_with_dead_zone")
        return GamePadState._from_native(state)

