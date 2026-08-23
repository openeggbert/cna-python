"""XNA input values and real CNA polling facades."""

from __future__ import annotations

import ctypes as c
from enum import IntEnum, IntFlag
import math
import struct

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.runtime_context import current_game

from .._game import PlayerIndex
from .._language import staticproperty, staticpropertymeta
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
        if keys is None:
            keys = ()
        try:
            raw_values = tuple(keys)
        except TypeError as error:
            raise TypeError("KeyboardState expects an iterable of Keys") from error
        values: set[Keys] = set()
        for value in raw_values:
            number = int32(value, name="key") if type(value) is int else int(value) if isinstance(value, Keys) else None
            if number is None:
                raise TypeError("KeyboardState keys must be Keys or Int32 values")
            try:
                values.add(Keys(number))
            except ValueError:
                pass
        self._pressed = frozenset(values)

    @classmethod
    def _from_native(cls, state: abi.CNA_KeyboardState) -> "KeyboardState":
        return cls(key for key in range(256)
                   if state.pressed_key_words[key // 64] & (1 << (key % 64)))

    def IsKeyDown(self, key: Keys) -> bool:
        if isinstance(key, Keys):
            value = int(key)
        elif type(key) is int:
            value = int32(key, name="key")
        else:
            raise TypeError("key must be Keys or an Int32 value")
        try:
            return Keys(value) in self._pressed
        except ValueError:
            return False

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

    def __copy__(self): return KeyboardState(self._pressed)
    __deepcopy__ = lambda self, memo: self.__copy__()

    def Equals(self, other: object) -> bool: return self == other
    def GetHashCode(self) -> int: return self.__hash__()


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
        if not args:
            player = None
        elif len(args) == 1:
            player = PlayerIndex(args[0])
        else:
            raise TypeError("Keyboard.GetState expects zero arguments or PlayerIndex")
        library = get_library()
        if player is None:
            result = library.cna_keyboard_get_state(_native_game_handle(), c.byref(state))
            operation = "cna_keyboard_get_state"
        else:
            result = library.cna_keyboard_get_state_for_player(_native_game_handle(), int(player), c.byref(state))
            operation = "cna_keyboard_get_state_for_player"
        library.check(result, operation)
        return KeyboardState._from_native(state)


class MouseState:
    __slots__ = ("_x", "_y", "_wheel", "_left", "_middle", "_right", "_x1", "_x2")

    def __init__(self, *args: object) -> None:
        if not args:
            x, y, scrollWheel = 0, 0, 0
            leftButton = middleButton = rightButton = xButton1 = xButton2 = ButtonState.Released
        elif len(args) == 8:
            x, y, scrollWheel, leftButton, middleButton, rightButton, xButton1, xButton2 = args
        else:
            raise TypeError("MouseState expects zero arguments or all eight state values")
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
    def __hash__(self): return _signed32(self.X ^ self.Y ^ int(self.LeftButton) ^ int(self.RightButton) ^ int(self.MiddleButton) ^ int(self.XButton1) ^ int(self.XButton2) ^ self.ScrollWheelValue)
    def __copy__(self): return MouseState(*tuple(self))
    __deepcopy__ = lambda self, memo: self.__copy__()
    def Equals(self, other: object) -> bool: return self == other
    def GetHashCode(self) -> int: return self.__hash__()
    def ToString(self) -> str:
        names = [name for name, value in (("Left", self.LeftButton), ("Right", self.RightButton), ("Middle", self.MiddleButton), ("XButton1", self.XButton1), ("XButton2", self.XButton2)) if value is ButtonState.Pressed]
        return f"{{X:{self.X} Y:{self.Y} Buttons:{' '.join(names) if names else 'None'} Wheel:{self.ScrollWheelValue}}}"
    __str__ = ToString

    @classmethod
    def _from_native(cls, state: abi.CNA_MouseState) -> "MouseState":
        button = lambda mask: ButtonState.Pressed if state.pressed_buttons & mask else ButtonState.Released
        return cls(state.x, state.y, state.scroll_wheel, button(1), button(2), button(4), button(8), button(16))


def _get_mouse_window_handle(cls: type) -> int:
    value = c.c_uint64()
    library = get_library()
    library.check(library.cna_mouse_get_window_handle(_native_game_handle(), c.byref(value)),
                  "cna_mouse_get_window_handle")
    return value.value if value.value <= 0x7FFFFFFFFFFFFFFF else value.value - 0x10000000000000000


def _set_mouse_window_handle(cls: type, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("WindowHandle must be an IntPtr integer")
    if value < -0x8000000000000000 or value > 0x7FFFFFFFFFFFFFFF:
        raise OverflowError("WindowHandle is outside the 64-bit IntPtr range")
    library = get_library()
    library.check(library.cna_mouse_set_window_handle(_native_game_handle(), value & 0xFFFFFFFFFFFFFFFF),
                  "cna_mouse_set_window_handle")


class Mouse(metaclass=staticpropertymeta):
    WindowHandle = staticproperty(_get_mouse_window_handle, _set_mouse_window_handle)

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
        x,y=int32(x),int32(y)
        library = get_library()
        library.check(library.cna_mouse_set_position(_native_game_handle(), x, y),
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


class GamePadType(IntEnum):
    Unknown = 0
    GamePad = 1
    Wheel = 2
    ArcadeStick = 3
    FlightStick = 4
    DancePad = 5
    Guitar = 6
    AlternateGuitar = 7
    DrumKit = 8
    BigButtonPad = 0x300


def _signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value if value < 0x80000000 else value - 0x100000000


def _float_bits(value: float) -> int:
    return _signed32(struct.unpack("=I", struct.pack("=f", f32(value)))[0])


def _smart_hash(*values: int) -> int:
    result = 0
    for value in values:
        result ^= value & 0xFFFFFFFF
    result = _signed32(result)
    return 0x7FFFFFFF if result == 0 else result


class GamePadButtons:
    __slots__ = ("_buttons",)
    _named_mask = (Buttons.A | Buttons.B | Buttons.X | Buttons.Y | Buttons.Back | Buttons.Start |
                   Buttons.BigButton | Buttons.LeftShoulder | Buttons.RightShoulder |
                   Buttons.LeftStick | Buttons.RightStick)
    def __init__(self, buttons: Buttons = Buttons(0)) -> None: self._buttons = Buttons(buttons) & self._named_mask
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
    def __hash__(self): return self.GetHashCode()
    def __copy__(self): return GamePadButtons(self._buttons)
    __deepcopy__ = lambda self, memo: self.__copy__()
    def Equals(self, other): return self == other
    def GetHashCode(self): return _smart_hash(*(int(getattr(self,name)) for name in ("A","B","X","Y","LeftShoulder","RightShoulder","LeftStick","RightStick","Start","Back","BigButton")))
    def ToString(self):
        names=[name for name in ("A","B","X","Y","LeftShoulder","RightShoulder","LeftStick","RightStick","Start","Back","BigButton") if getattr(self,name) is ButtonState.Pressed]
        return f"{{Buttons:{' '.join(names) if names else 'None'}}}"
    __str__=ToString


class GamePadDPad:
    __slots__ = ("_buttons",)
    def __init__(self, *args: object):
        if not args:
            up = down = left = right = ButtonState.Released
        elif len(args) == 4:
            up, down, left, right = args
        else:
            raise TypeError("GamePadDPad expects zero arguments or four ButtonState values")
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
    def __hash__(self): return self.GetHashCode()
    def __copy__(self): return GamePadDPad(self.Up, self.Down, self.Left, self.Right)
    __deepcopy__ = lambda self, memo: self.__copy__()
    def Equals(self, other): return self == other
    def GetHashCode(self):
        return _smart_hash(int(self.Up),int(self.Down),int(self.Left),int(self.Right))
    def ToString(self):
        names=[name for name in ("Up","Down","Left","Right") if getattr(self,name) is ButtonState.Pressed]
        return f"{{DPad:{' '.join(names) if names else 'None'}}}"
    __str__=ToString


class GamePadThumbSticks:
    __slots__ = ("_left", "_right")
    def __init__(self, *args: object):
        if not args:
            left, right = Vector2.Zero, Vector2.Zero
        elif len(args) == 2 and all(isinstance(value, Vector2) for value in args):
            left, right = args
        else:
            raise TypeError("GamePadThumbSticks expects zero arguments or two Vector2 values")
        self._left = Vector2.Max(Vector2.Min(left, Vector2.One), -Vector2.One)
        self._right = Vector2.Max(Vector2.Min(right, Vector2.One), -Vector2.One)
    @property
    def Left(self): return Vector2(self._left.X, self._left.Y)
    @property
    def Right(self): return Vector2(self._right.X, self._right.Y)
    def __eq__(self, other): return isinstance(other, GamePadThumbSticks) and self._left == other._left and self._right == other._right
    def __hash__(self): return self.GetHashCode()
    def __copy__(self): return GamePadThumbSticks(self.Left, self.Right)
    __deepcopy__ = lambda self, memo: self.__copy__()
    def Equals(self, other): return self == other
    def GetHashCode(self): return _smart_hash(_float_bits(self.Left.X),_float_bits(self.Left.Y),_float_bits(self.Right.X),_float_bits(self.Right.Y))
    def ToString(self): return f"{{Left:{self.Left} Right:{self.Right}}}"
    __str__=ToString


class GamePadTriggers:
    __slots__ = ("_left", "_right")
    def __init__(self, *args: object):
        if not args:
            left, right = 0.0, 0.0
        elif len(args) == 2:
            left, right = args
        else:
            raise TypeError("GamePadTriggers expects zero arguments or two Single values")
        left,right=f32(left),f32(right)
        self._left, self._right = f32(max(min(left,1.0),0.0)),f32(max(min(right,1.0),0.0))
    @property
    def Left(self): return self._left
    @property
    def Right(self): return self._right
    def __eq__(self, other): return isinstance(other, GamePadTriggers) and self.Left == other.Left and self.Right == other.Right
    def __hash__(self): return self.GetHashCode()
    def __copy__(self): return GamePadTriggers(self.Left, self.Right)
    __deepcopy__ = lambda self, memo: self.__copy__()
    def Equals(self, other): return self == other
    def GetHashCode(self): return _smart_hash(_float_bits(self.Left),_float_bits(self.Right))
    def ToString(self): return f"{{Left:{self.Left:g} Right:{self.Right:g}}}"
    __str__=ToString


class GamePadState:
    __slots__ = ("_connected", "_packet", "_buttons_mask", "_thumbs", "_triggers")
    def __init__(self, *args: object, _connected: bool = False, _packet: int = 0, _mask: Buttons = Buttons(0)) -> None:
        self._connected, self._packet, self._buttons_mask = _connected, int32(_packet), Buttons(_mask)
        self._thumbs, self._triggers = GamePadThumbSticks(), GamePadTriggers()
        if args:
            if (len(args) == 4 and isinstance(args[0], GamePadThumbSticks)
                    and isinstance(args[1], GamePadTriggers)
                    and isinstance(args[2], GamePadButtons) and isinstance(args[3], GamePadDPad)):
                self._thumbs = GamePadThumbSticks(args[0].Left, args[0].Right)
                self._triggers = GamePadTriggers(args[1].Left, args[1].Right)
                self._buttons_mask = args[2]._buttons | args[3]._buttons
                self._connected = True
            elif (len(args) == 5 and isinstance(args[0], Vector2) and isinstance(args[1], Vector2)):
                supplied = () if args[4] is None else args[4]
                try:
                    values = tuple(Buttons(value) for value in supplied)
                except TypeError as error:
                    raise TypeError("buttons must be a sequence of Buttons") from error
                mask = Buttons(0)
                for button in values:
                    mask |= button
                self._thumbs = GamePadThumbSticks(args[0], args[1])
                self._triggers = GamePadTriggers(args[2], args[3])
                self._buttons_mask = GamePadButtons(mask)._buttons | (mask & (Buttons.DPadUp|Buttons.DPadDown|Buttons.DPadLeft|Buttons.DPadRight))
                self._connected = True
            else:
                raise TypeError("no matching XNA GamePadState constructor")
            self._buttons_mask |= self._analog_buttons(self._thumbs,self._triggers)
    @staticmethod
    def _analog_buttons(thumbs:GamePadThumbSticks,triggers:GamePadTriggers)->Buttons:
        result=Buttons(0)
        left_x,left_y=int(f32(thumbs.Left.X*32767.0)),int(f32(thumbs.Left.Y*32767.0))
        right_x,right_y=int(f32(thumbs.Right.X*32767.0)),int(f32(thumbs.Right.Y*32767.0))
        if left_x < -7849: result|=Buttons.LeftThumbstickLeft
        if left_x > 7849: result|=Buttons.LeftThumbstickRight
        if left_y < -7849: result|=Buttons.LeftThumbstickDown
        if left_y > 7849: result|=Buttons.LeftThumbstickUp
        if right_x < -8689: result|=Buttons.RightThumbstickLeft
        if right_x > 8689: result|=Buttons.RightThumbstickRight
        if right_y < -8689: result|=Buttons.RightThumbstickDown
        if right_y > 8689: result|=Buttons.RightThumbstickUp
        left_trigger=0 if math.isnan(triggers.Left) else int(f32(triggers.Left*255.0))
        right_trigger=0 if math.isnan(triggers.Right) else int(f32(triggers.Right*255.0))
        if left_trigger>30:result|=Buttons.LeftTrigger
        if right_trigger>30:result|=Buttons.RightTrigger
        return result
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
    def ThumbSticks(self): return GamePadThumbSticks(self._thumbs.Left, self._thumbs.Right)
    @property
    def Triggers(self): return GamePadTriggers(self._triggers.Left, self._triggers.Right)
    def IsButtonDown(self, button: Buttons):
        button=Buttons(button)
        return (self._buttons_mask & button)==button
    def IsButtonUp(self, button: Buttons): return not self.IsButtonDown(button)
    def __eq__(self, other): return isinstance(other,GamePadState) and (self._connected,self._packet,self._buttons_mask,self._thumbs,self._triggers)==(other._connected,other._packet,other._buttons_mask,other._thumbs,other._triggers)
    def __hash__(self): return self.GetHashCode()
    def Equals(self, other): return self == other
    def GetHashCode(self):return _signed32(self.ThumbSticks.GetHashCode()^self.Triggers.GetHashCode()^self.Buttons.GetHashCode()^int(self.IsConnected)^self.DPad.GetHashCode()^self.PacketNumber)
    def ToString(self):return f"{{IsConnected:{'True' if self.IsConnected else 'False'}}}"
    __str__=ToString
    def __copy__(self):
        result = GamePadState(_connected=self._connected, _packet=self._packet, _mask=self._buttons_mask)
        result._thumbs, result._triggers = self.ThumbSticks, self.Triggers
        return result
    __deepcopy__ = lambda self, memo: self.__copy__()

    @classmethod
    def _from_native(cls, state: abi.CNA_GamePadState) -> "GamePadState":
        result=cls(_connected=state.is_connected!=0,_packet=state.packet_number,_mask=Buttons(state.pressed_buttons))
        result._thumbs=GamePadThumbSticks(Vector2(state.analog.left_thumb_stick.x,state.analog.left_thumb_stick.y),Vector2(state.analog.right_thumb_stick.x,state.analog.right_thumb_stick.y))
        result._triggers=GamePadTriggers(state.analog.left_trigger,state.analog.right_trigger)
        return result


_CAPABILITY_FIELDS = {
    "IsConnected":"is_connected","HasAButton":"has_a_button","HasBButton":"has_b_button",
    "HasXButton":"has_x_button","HasYButton":"has_y_button","HasBackButton":"has_back_button",
    "HasStartButton":"has_start_button","HasBigButton":"has_big_button",
    "HasDPadUpButton":"has_dpad_up_button","HasDPadDownButton":"has_dpad_down_button",
    "HasDPadLeftButton":"has_dpad_left_button","HasDPadRightButton":"has_dpad_right_button",
    "HasLeftShoulderButton":"has_left_shoulder_button","HasRightShoulderButton":"has_right_shoulder_button",
    "HasLeftStickButton":"has_left_stick_button","HasRightStickButton":"has_right_stick_button",
    "HasLeftXThumbStick":"has_left_x_thumb_stick","HasLeftYThumbStick":"has_left_y_thumb_stick",
    "HasRightXThumbStick":"has_right_x_thumb_stick","HasRightYThumbStick":"has_right_y_thumb_stick",
    "HasLeftTrigger":"has_left_trigger","HasRightTrigger":"has_right_trigger",
    "HasLeftVibrationMotor":"has_left_vibration_motor","HasRightVibrationMotor":"has_right_vibration_motor",
    "HasVoiceSupport":"has_voice_support",
}


class GamePadCapabilities:
    __slots__=("_gamepad_type",*("_"+name for name in _CAPABILITY_FIELDS.values()))
    def __init__(self)->None:
        self._gamepad_type=GamePadType.Unknown
        for name in _CAPABILITY_FIELDS.values():setattr(self,"_"+name,False)
    @property
    def GamePadType(self):return self._gamepad_type
    def __copy__(self):
        result=GamePadCapabilities();result._gamepad_type=self._gamepad_type
        for name in _CAPABILITY_FIELDS.values():setattr(result,"_"+name,getattr(self,"_"+name))
        return result
    __deepcopy__=lambda self,memo:self.__copy__()
    @classmethod
    def _from_native(cls,value:abi.CNA_GamePadCapabilities)->"GamePadCapabilities":
        result=cls();result._gamepad_type=GamePadType.BigButtonPad if value.gamepad_type==9 else GamePadType(value.gamepad_type)
        for name in _CAPABILITY_FIELDS.values():setattr(result,"_"+name,bool(getattr(value,name)))
        return result


for _public_name,_native_name in _CAPABILITY_FIELDS.items():
    setattr(GamePadCapabilities,_public_name,property(lambda self,name=_native_name:getattr(self,"_"+name)))


class GamePad:
    def __new__(cls): raise TypeError("GamePad is static")
    @staticmethod
    def GetState(playerIndex: PlayerIndex, deadZoneMode: GamePadDeadZone = GamePadDeadZone.IndependentAxes) -> GamePadState:
        player,dead_zone=PlayerIndex(playerIndex),GamePadDeadZone(deadZoneMode)
        state=abi.CNA_GamePadState();state.struct_size,state.struct_version=c.sizeof(state),1
        library=get_library()
        library.check(library.cna_gamepad_get_state_with_dead_zone(_native_game_handle(),int(player),int(dead_zone),c.byref(state)),"cna_gamepad_get_state_with_dead_zone")
        return GamePadState._from_native(state)
    @staticmethod
    def GetCapabilities(playerIndex:PlayerIndex)->GamePadCapabilities:
        player=PlayerIndex(playerIndex)
        value=abi.CNA_GamePadCapabilities();value.struct_size,value.struct_version=c.sizeof(value),1
        library=get_library();library.check(library.cna_gamepad_get_capabilities(_native_game_handle(),int(player),c.byref(value)),"cna_gamepad_get_capabilities")
        return GamePadCapabilities._from_native(value)
    @staticmethod
    def SetVibration(playerIndex:PlayerIndex,leftMotor:float,rightMotor:float)->bool:
        player=PlayerIndex(playerIndex);left,right=f32(leftMotor),f32(rightMotor);applied=c.c_uint8()
        library=get_library();library.check(library.cna_gamepad_set_vibration(_native_game_handle(),int(player),left,right,c.byref(applied)),"cna_gamepad_set_vibration")
        return bool(applied.value)


Keyboard.__xna_arities__ = {"GetState": {0, 1}}
Mouse.__xna_arities__ = {"GetState": {0}, "SetPosition": {2}}
MouseState.__xna_arities__ = {"__init__": {0, 8}}
GamePadButtons.__xna_arities__ = {"__init__": {0, 1}}
GamePadDPad.__xna_arities__ = {"__init__": {0, 4}}
GamePadThumbSticks.__xna_arities__ = {"__init__": {0, 2}}
GamePadTriggers.__xna_arities__ = {"__init__": {0, 2}}
GamePadState.__xna_arities__ = {"__init__": {0, 4, 5}}
GamePadCapabilities.__xna_arities__ = {"__init__": {0}}
GamePad.__xna_arities__ = {"GetState": {1, 2}, "GetCapabilities": {1}, "SetVibration": {3}}
