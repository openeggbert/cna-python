from enum import IntEnum, IntFlag
from typing import Any, Final, MutableSequence, Sequence, overload
from .. import PlayerIndex, Vector2

class ButtonState(IntEnum):
    Released: int
    Pressed: int

class Buttons(IntFlag):
    A: int
    B: int
    X: int
    Y: int
    Back: int
    Start: int
    DPadUp: int
    DPadDown: int
    DPadLeft: int
    DPadRight: int
    LeftShoulder: int
    RightShoulder: int
    LeftStick: int
    RightStick: int
    BigButton: int
    LeftThumbstickLeft: int
    LeftThumbstickRight: int
    LeftThumbstickDown: int
    LeftThumbstickUp: int
    RightThumbstickLeft: int
    RightThumbstickRight: int
    RightThumbstickDown: int
    RightThumbstickUp: int
    LeftTrigger: int
    RightTrigger: int

class GamePad:
    @overload
    @staticmethod
    def GetState(playerIndex: PlayerIndex) -> GamePadState: ...
    @overload
    @staticmethod
    def GetState(playerIndex: PlayerIndex, deadZoneMode: GamePadDeadZone) -> GamePadState: ...
    @staticmethod
    def GetCapabilities(playerIndex: PlayerIndex) -> GamePadCapabilities: ...
    @staticmethod
    def SetVibration(playerIndex: PlayerIndex, leftMotor: float, rightMotor: float) -> bool: ...

class GamePadButtons:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, buttons: Buttons) -> None: ...
    def Equals(self, obj: object) -> bool: ...
    def GetHashCode(self) -> int: ...
    def ToString(self) -> str: ...
    def __eq__(self, right: GamePadButtons) -> bool: ...
    def __ne__(self, right: GamePadButtons) -> bool: ...
    @property
    def A(self) -> ButtonState: ...
    @property
    def B(self) -> ButtonState: ...
    @property
    def Back(self) -> ButtonState: ...
    @property
    def X(self) -> ButtonState: ...
    @property
    def Y(self) -> ButtonState: ...
    @property
    def Start(self) -> ButtonState: ...
    @property
    def LeftShoulder(self) -> ButtonState: ...
    @property
    def LeftStick(self) -> ButtonState: ...
    @property
    def RightShoulder(self) -> ButtonState: ...
    @property
    def RightStick(self) -> ButtonState: ...
    @property
    def BigButton(self) -> ButtonState: ...
    def __copy__(self) -> GamePadButtons: ...
    def __deepcopy__(self, memo: object) -> GamePadButtons: ...

class GamePadCapabilities:
    @property
    def GamePadType(self) -> GamePadType: ...
    @property
    def IsConnected(self) -> bool: ...
    @property
    def HasAButton(self) -> bool: ...
    @property
    def HasBackButton(self) -> bool: ...
    @property
    def HasBButton(self) -> bool: ...
    @property
    def HasDPadDownButton(self) -> bool: ...
    @property
    def HasDPadLeftButton(self) -> bool: ...
    @property
    def HasDPadRightButton(self) -> bool: ...
    @property
    def HasDPadUpButton(self) -> bool: ...
    @property
    def HasLeftShoulderButton(self) -> bool: ...
    @property
    def HasLeftStickButton(self) -> bool: ...
    @property
    def HasRightShoulderButton(self) -> bool: ...
    @property
    def HasRightStickButton(self) -> bool: ...
    @property
    def HasStartButton(self) -> bool: ...
    @property
    def HasXButton(self) -> bool: ...
    @property
    def HasYButton(self) -> bool: ...
    @property
    def HasBigButton(self) -> bool: ...
    @property
    def HasLeftXThumbStick(self) -> bool: ...
    @property
    def HasLeftYThumbStick(self) -> bool: ...
    @property
    def HasRightXThumbStick(self) -> bool: ...
    @property
    def HasRightYThumbStick(self) -> bool: ...
    @property
    def HasLeftTrigger(self) -> bool: ...
    @property
    def HasRightTrigger(self) -> bool: ...
    @property
    def HasLeftVibrationMotor(self) -> bool: ...
    @property
    def HasRightVibrationMotor(self) -> bool: ...
    @property
    def HasVoiceSupport(self) -> bool: ...
    def __copy__(self) -> GamePadCapabilities: ...
    def __deepcopy__(self, memo: object) -> GamePadCapabilities: ...

class GamePadDPad:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, upValue: ButtonState, downValue: ButtonState, leftValue: ButtonState, rightValue: ButtonState) -> None: ...
    def Equals(self, obj: object) -> bool: ...
    def GetHashCode(self) -> int: ...
    def ToString(self) -> str: ...
    def __eq__(self, right: GamePadDPad) -> bool: ...
    def __ne__(self, right: GamePadDPad) -> bool: ...
    @property
    def Up(self) -> ButtonState: ...
    @property
    def Down(self) -> ButtonState: ...
    @property
    def Right(self) -> ButtonState: ...
    @property
    def Left(self) -> ButtonState: ...
    def __copy__(self) -> GamePadDPad: ...
    def __deepcopy__(self, memo: object) -> GamePadDPad: ...

class GamePadDeadZone(IntEnum):
    None_: int
    IndependentAxes: int
    Circular: int

class GamePadState:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, thumbSticks: GamePadThumbSticks, triggers: GamePadTriggers, buttons: GamePadButtons, dPad: GamePadDPad) -> None: ...
    @overload
    def __init__(self, leftThumbStick: Vector2, rightThumbStick: Vector2, leftTrigger: float, rightTrigger: float, buttons: Sequence[Buttons]) -> None: ...
    def IsButtonDown(self, button: Buttons) -> bool: ...
    def IsButtonUp(self, button: Buttons) -> bool: ...
    def Equals(self, obj: object) -> bool: ...
    def GetHashCode(self) -> int: ...
    def ToString(self) -> str: ...
    def __eq__(self, right: GamePadState) -> bool: ...
    def __ne__(self, right: GamePadState) -> bool: ...
    @property
    def Buttons(self) -> GamePadButtons: ...
    @property
    def DPad(self) -> GamePadDPad: ...
    @property
    def IsConnected(self) -> bool: ...
    @property
    def PacketNumber(self) -> int: ...
    @property
    def ThumbSticks(self) -> GamePadThumbSticks: ...
    @property
    def Triggers(self) -> GamePadTriggers: ...
    def __copy__(self) -> GamePadState: ...
    def __deepcopy__(self, memo: object) -> GamePadState: ...

class GamePadThumbSticks:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, leftThumbstick: Vector2, rightThumbstick: Vector2) -> None: ...
    def Equals(self, obj: object) -> bool: ...
    def GetHashCode(self) -> int: ...
    def ToString(self) -> str: ...
    def __eq__(self, right: GamePadThumbSticks) -> bool: ...
    def __ne__(self, right: GamePadThumbSticks) -> bool: ...
    @property
    def Left(self) -> Vector2: ...
    @property
    def Right(self) -> Vector2: ...
    def __copy__(self) -> GamePadThumbSticks: ...
    def __deepcopy__(self, memo: object) -> GamePadThumbSticks: ...

class GamePadTriggers:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, leftTrigger: float, rightTrigger: float) -> None: ...
    def Equals(self, obj: object) -> bool: ...
    def GetHashCode(self) -> int: ...
    def ToString(self) -> str: ...
    def __eq__(self, right: GamePadTriggers) -> bool: ...
    def __ne__(self, right: GamePadTriggers) -> bool: ...
    @property
    def Left(self) -> float: ...
    @property
    def Right(self) -> float: ...
    def __copy__(self) -> GamePadTriggers: ...
    def __deepcopy__(self, memo: object) -> GamePadTriggers: ...

class GamePadType(IntEnum):
    Unknown: int
    ArcadeStick: int
    DancePad: int
    FlightStick: int
    GamePad: int
    Wheel: int
    Guitar: int
    DrumKit: int
    AlternateGuitar: int
    BigButtonPad: int

class KeyState(IntEnum):
    Down: int
    Up: int

class Keyboard:
    @overload
    @staticmethod
    def GetState() -> KeyboardState: ...
    @overload
    @staticmethod
    def GetState(playerIndex: PlayerIndex) -> KeyboardState: ...

class KeyboardState:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, keys: Sequence[Keys]) -> None: ...
    def IsKeyDown(self, key: Keys) -> bool: ...
    def IsKeyUp(self, key: Keys) -> bool: ...
    def GetPressedKeys(self) -> list[Keys]: ...
    def GetHashCode(self) -> int: ...
    def Equals(self, obj: object) -> bool: ...
    def __eq__(self, b: KeyboardState) -> bool: ...
    def __ne__(self, b: KeyboardState) -> bool: ...
    def __getitem__(self, key: Keys) -> KeyState: ...
    def __copy__(self) -> KeyboardState: ...
    def __deepcopy__(self, memo: object) -> KeyboardState: ...

class Keys(IntEnum):
    A: int
    Add: int
    Apps: int
    Attn: int
    B: int
    Back: int
    BrowserBack: int
    BrowserFavorites: int
    BrowserForward: int
    BrowserHome: int
    BrowserRefresh: int
    BrowserSearch: int
    BrowserStop: int
    C: int
    CapsLock: int
    Crsel: int
    D: int
    D0: int
    D1: int
    D2: int
    D3: int
    D4: int
    D5: int
    D6: int
    D7: int
    D8: int
    D9: int
    Decimal: int
    Delete: int
    Divide: int
    Down: int
    E: int
    End: int
    Enter: int
    EraseEof: int
    Escape: int
    Execute: int
    Exsel: int
    F: int
    F1: int
    F10: int
    F11: int
    F12: int
    F13: int
    F14: int
    F15: int
    F16: int
    F17: int
    F18: int
    F19: int
    F2: int
    F20: int
    F21: int
    F22: int
    F23: int
    F24: int
    F3: int
    F4: int
    F5: int
    F6: int
    F7: int
    F8: int
    F9: int
    G: int
    H: int
    Help: int
    Home: int
    I: int
    ImeConvert: int
    ImeNoConvert: int
    Insert: int
    J: int
    K: int
    Kana: int
    Kanji: int
    L: int
    LaunchApplication1: int
    LaunchApplication2: int
    LaunchMail: int
    LeftControl: int
    Left: int
    LeftAlt: int
    LeftShift: int
    LeftWindows: int
    M: int
    MediaNextTrack: int
    MediaPlayPause: int
    MediaPreviousTrack: int
    MediaStop: int
    Multiply: int
    N: int
    None_: int
    NumLock: int
    NumPad0: int
    NumPad1: int
    NumPad2: int
    NumPad3: int
    NumPad4: int
    NumPad5: int
    NumPad6: int
    NumPad7: int
    NumPad8: int
    NumPad9: int
    O: int
    OemAuto: int
    OemCopy: int
    OemEnlW: int
    OemSemicolon: int
    OemBackslash: int
    OemQuestion: int
    OemTilde: int
    OemOpenBrackets: int
    OemPipe: int
    OemCloseBrackets: int
    OemQuotes: int
    Oem8: int
    OemClear: int
    OemComma: int
    OemMinus: int
    OemPeriod: int
    OemPlus: int
    P: int
    Pa1: int
    PageDown: int
    PageUp: int
    Pause: int
    Play: int
    Print: int
    PrintScreen: int
    ProcessKey: int
    Q: int
    R: int
    RightControl: int
    Right: int
    RightAlt: int
    RightShift: int
    RightWindows: int
    S: int
    Scroll: int
    Select: int
    SelectMedia: int
    Separator: int
    Sleep: int
    Space: int
    Subtract: int
    T: int
    Tab: int
    U: int
    Up: int
    V: int
    VolumeDown: int
    VolumeMute: int
    VolumeUp: int
    W: int
    X: int
    Y: int
    Z: int
    Zoom: int
    ChatPadGreen: int
    ChatPadOrange: int

class Mouse:
    @staticmethod
    def GetState() -> MouseState: ...
    @staticmethod
    def SetPosition(x: int, y: int) -> None: ...
    WindowHandle: ClassVar[IntPtr]

class MouseState:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, x: int, y: int, scrollWheel: int, leftButton: ButtonState, middleButton: ButtonState, rightButton: ButtonState, xButton1: ButtonState, xButton2: ButtonState) -> None: ...
    def GetHashCode(self) -> int: ...
    def ToString(self) -> str: ...
    def Equals(self, obj: object) -> bool: ...
    def __eq__(self, right: MouseState) -> bool: ...
    def __ne__(self, right: MouseState) -> bool: ...
    @property
    def X(self) -> int: ...
    @property
    def Y(self) -> int: ...
    @property
    def LeftButton(self) -> ButtonState: ...
    @property
    def RightButton(self) -> ButtonState: ...
    @property
    def MiddleButton(self) -> ButtonState: ...
    @property
    def XButton1(self) -> ButtonState: ...
    @property
    def XButton2(self) -> ButtonState: ...
    @property
    def ScrollWheelValue(self) -> int: ...
    def __copy__(self) -> MouseState: ...
    def __deepcopy__(self, memo: object) -> MouseState: ...
