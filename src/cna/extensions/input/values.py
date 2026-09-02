"""Value types the extended-input family reads and writes.

Every enum here takes its members from the generated ABI constants rather than
from numbers written down again, so a value CNA changes changes here too.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag

from _cna_native import input_abi as _input

__all__ = [
    "TextInputType",
    "MouseCursorStock",
    "JoystickType",
    "JoystickHatPosition",
    "SensorType",
    "HapticDirectionType",
    "HapticEffectType",
    "HapticFeature",
    "PowerState",
    "JoystickInfo",
    "JoystickCapabilities",
    "SensorInfo",
    "InputDeviceInfo",
    "HapticCapabilities",
    "HapticDirection",
    "HapticEffect",
    "TextEditing",
    "TextEditingCandidates",
    "HAPTIC_EFFECT_INFINITE_LENGTH",
]

#: The length that means "play until stopped", from the canonical header.
HAPTIC_EFFECT_INFINITE_LENGTH = _input.CNA_HAPTIC_EFFECT_INFINITE_LENGTH


class TextInputType(IntEnum):
    """What kind of text a screen keyboard should be laid out for."""

    Text = _input.CNA_TEXT_INPUT_TYPE_TEXT
    TextName = _input.CNA_TEXT_INPUT_TYPE_TEXT_NAME
    TextEmail = _input.CNA_TEXT_INPUT_TYPE_TEXT_EMAIL
    TextUsername = _input.CNA_TEXT_INPUT_TYPE_TEXT_USERNAME
    TextPasswordHidden = _input.CNA_TEXT_INPUT_TYPE_TEXT_PASSWORD_HIDDEN
    TextPasswordVisible = _input.CNA_TEXT_INPUT_TYPE_TEXT_PASSWORD_VISIBLE
    Number = _input.CNA_TEXT_INPUT_TYPE_NUMBER
    NumberPasswordHidden = _input.CNA_TEXT_INPUT_TYPE_NUMBER_PASSWORD_HIDDEN
    NumberPasswordVisible = _input.CNA_TEXT_INPUT_TYPE_NUMBER_PASSWORD_VISIBLE


class MouseCursorStock(IntEnum):
    """The cursors every platform provides."""

    Arrow = _input.CNA_MOUSE_CURSOR_STOCK_ARROW
    IBeam = _input.CNA_MOUSE_CURSOR_STOCK_IBEAM
    Wait = _input.CNA_MOUSE_CURSOR_STOCK_WAIT
    Crosshair = _input.CNA_MOUSE_CURSOR_STOCK_CROSSHAIR
    WaitArrow = _input.CNA_MOUSE_CURSOR_STOCK_WAIT_ARROW
    SizeNwse = _input.CNA_MOUSE_CURSOR_STOCK_SIZE_NWSE
    SizeNesw = _input.CNA_MOUSE_CURSOR_STOCK_SIZE_NESW
    SizeWe = _input.CNA_MOUSE_CURSOR_STOCK_SIZE_WE
    SizeNs = _input.CNA_MOUSE_CURSOR_STOCK_SIZE_NS
    SizeAll = _input.CNA_MOUSE_CURSOR_STOCK_SIZE_ALL
    No = _input.CNA_MOUSE_CURSOR_STOCK_NO
    Hand = _input.CNA_MOUSE_CURSOR_STOCK_HAND


class JoystickType(IntEnum):
    """What kind of device a joystick reports itself to be."""

    Unknown = _input.CNA_JOYSTICK_TYPE_UNKNOWN
    Gamepad = _input.CNA_JOYSTICK_TYPE_GAMEPAD
    Wheel = _input.CNA_JOYSTICK_TYPE_WHEEL
    ArcadeStick = _input.CNA_JOYSTICK_TYPE_ARCADE_STICK
    FlightStick = _input.CNA_JOYSTICK_TYPE_FLIGHT_STICK
    DancePad = _input.CNA_JOYSTICK_TYPE_DANCE_PAD
    Guitar = _input.CNA_JOYSTICK_TYPE_GUITAR
    DrumKit = _input.CNA_JOYSTICK_TYPE_DRUM_KIT
    ArcadePad = _input.CNA_JOYSTICK_TYPE_ARCADE_PAD
    Throttle = _input.CNA_JOYSTICK_TYPE_THROTTLE


class JoystickHatPosition(IntEnum):
    """Where a hat switch is pointing.

    An enumeration and **not** a flag set. The canonical header says so in as
    many words: ``RIGHT_UP`` is the identity 5, not ``RIGHT | UP``. Projecting
    it as flags would make ``Left | Up`` produce 12 -- a position that does not
    exist -- and would make ``LeftUp`` compare equal to nothing CNA reports.
    """

    Centered = _input.CNA_JOYSTICK_HAT_POSITION_CENTERED
    Up = _input.CNA_JOYSTICK_HAT_POSITION_UP
    Right = _input.CNA_JOYSTICK_HAT_POSITION_RIGHT
    Down = _input.CNA_JOYSTICK_HAT_POSITION_DOWN
    Left = _input.CNA_JOYSTICK_HAT_POSITION_LEFT
    RightUp = _input.CNA_JOYSTICK_HAT_POSITION_RIGHT_UP
    RightDown = _input.CNA_JOYSTICK_HAT_POSITION_RIGHT_DOWN
    LeftUp = _input.CNA_JOYSTICK_HAT_POSITION_LEFT_UP
    LeftDown = _input.CNA_JOYSTICK_HAT_POSITION_LEFT_DOWN


class SensorType(IntEnum):
    """A sensor an input device carries, as distinct from the host's own."""

    Unknown = _input.CNA_SENSOR_TYPE_UNKNOWN
    Accelerometer = _input.CNA_SENSOR_TYPE_ACCELEROMETER
    Gyroscope = _input.CNA_SENSOR_TYPE_GYROSCOPE
    AccelerometerLeft = _input.CNA_SENSOR_TYPE_ACCELEROMETER_LEFT
    GyroscopeLeft = _input.CNA_SENSOR_TYPE_GYROSCOPE_LEFT
    AccelerometerRight = _input.CNA_SENSOR_TYPE_ACCELEROMETER_RIGHT
    GyroscopeRight = _input.CNA_SENSOR_TYPE_GYROSCOPE_RIGHT


class PowerState(IntEnum):
    """A device's power state.

    The same six values as the host's, because CNA declares one identity for
    both and this package does not invent a second.
    """

    Error = _input.CNA_POWER_STATE_ERROR
    Unknown = _input.CNA_POWER_STATE_UNKNOWN
    OnBattery = _input.CNA_POWER_STATE_ON_BATTERY
    NoBattery = _input.CNA_POWER_STATE_NO_BATTERY
    Charging = _input.CNA_POWER_STATE_CHARGING
    Charged = _input.CNA_POWER_STATE_CHARGED


class HapticDirectionType(IntEnum):
    """How a haptic direction's three values are interpreted."""

    Polar = _input.CNA_HAPTIC_DIRECTION_TYPE_POLAR
    Cartesian = _input.CNA_HAPTIC_DIRECTION_TYPE_CARTESIAN
    Spherical = _input.CNA_HAPTIC_DIRECTION_TYPE_SPHERICAL
    SteeringAxis = _input.CNA_HAPTIC_DIRECTION_TYPE_STEERING_AXIS


class HapticEffectType(IntEnum):
    """Which of the effect structure's field groups is meaningful."""

    Constant = _input.CNA_HAPTIC_EFFECT_TYPE_CONSTANT
    Sine = _input.CNA_HAPTIC_EFFECT_TYPE_SINE
    Square = _input.CNA_HAPTIC_EFFECT_TYPE_SQUARE
    Triangle = _input.CNA_HAPTIC_EFFECT_TYPE_TRIANGLE
    SawtoothUp = _input.CNA_HAPTIC_EFFECT_TYPE_SAWTOOTH_UP
    SawtoothDown = _input.CNA_HAPTIC_EFFECT_TYPE_SAWTOOTH_DOWN
    Ramp = _input.CNA_HAPTIC_EFFECT_TYPE_RAMP
    Spring = _input.CNA_HAPTIC_EFFECT_TYPE_SPRING
    Damper = _input.CNA_HAPTIC_EFFECT_TYPE_DAMPER
    Inertia = _input.CNA_HAPTIC_EFFECT_TYPE_INERTIA
    Friction = _input.CNA_HAPTIC_EFFECT_TYPE_FRICTION
    Custom = _input.CNA_HAPTIC_EFFECT_TYPE_CUSTOM
    LeftRight = _input.CNA_HAPTIC_EFFECT_TYPE_LEFT_RIGHT


class HapticFeature(IntFlag):
    """What a haptic device can do, as the bit set CNA reports."""

    None_ = _input.CNA_HAPTIC_FEATURE_NONE
    Constant = _input.CNA_HAPTIC_FEATURE_CONSTANT
    Sine = _input.CNA_HAPTIC_FEATURE_SINE
    Square = _input.CNA_HAPTIC_FEATURE_SQUARE
    Triangle = _input.CNA_HAPTIC_FEATURE_TRIANGLE
    SawtoothUp = _input.CNA_HAPTIC_FEATURE_SAWTOOTH_UP
    SawtoothDown = _input.CNA_HAPTIC_FEATURE_SAWTOOTH_DOWN
    Ramp = _input.CNA_HAPTIC_FEATURE_RAMP
    Spring = _input.CNA_HAPTIC_FEATURE_SPRING
    Damper = _input.CNA_HAPTIC_FEATURE_DAMPER
    Inertia = _input.CNA_HAPTIC_FEATURE_INERTIA
    Friction = _input.CNA_HAPTIC_FEATURE_FRICTION
    Custom = _input.CNA_HAPTIC_FEATURE_CUSTOM
    LeftRight = _input.CNA_HAPTIC_FEATURE_LEFT_RIGHT
    Gain = _input.CNA_HAPTIC_FEATURE_GAIN
    Autocenter = _input.CNA_HAPTIC_FEATURE_AUTOCENTER
    Status = _input.CNA_HAPTIC_FEATURE_STATUS
    Pause = _input.CNA_HAPTIC_FEATURE_PAUSE
    All = _input.CNA_HAPTIC_FEATURE_ALL


@dataclass(frozen=True, slots=True)
class JoystickInfo:
    """One enumerated joystick: its instance id, its kind and its name."""

    id: int
    type: JoystickType
    name: str


@dataclass(frozen=True, slots=True)
class JoystickCapabilities:
    """What one joystick has, and what its battery is doing."""

    axis_count: int
    button_count: int
    hat_count: int
    ball_count: int
    type: JoystickType
    power_state: PowerState
    #: The battery percentage, or ``None`` when the device does not report one.
    power_percent: int | None
    is_connected: bool
    name: str
    guid: str


@dataclass(frozen=True, slots=True)
class SensorInfo:
    """One sensor an input device carries."""

    id: int
    type: SensorType
    name: str


@dataclass(frozen=True, slots=True)
class InputDeviceInfo:
    """One enumerated keyboard, mouse or touch device."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class HapticCapabilities:
    """What a haptic device can do.

    ``max_effects`` and ``max_effects_playing`` are ``None`` when the device is
    closed or does not report a limit. CNA's sentinel for both is ``-1``, and it
    is turned into ``None`` here exactly once so no caller has to remember it and
    no arithmetic can treat it as a count.
    """

    features: HapticFeature
    axis_count: int
    max_effects: int | None
    max_effects_playing: int | None
    is_open: bool
    rumble_supported: bool
    name: str


@dataclass(frozen=True, slots=True)
class HapticDirection:
    """The direction an effect pushes in.

    ``values`` is exactly three entries, because the C structure is exactly
    three; which of them mean anything depends on :attr:`type`.
    """

    type: HapticDirectionType
    values: tuple[int, int, int]

    def __post_init__(self) -> None:
        if len(self.values) != 3:
            raise ValueError(
                f"a haptic direction has exactly three values, got {len(self.values)}")


@dataclass(frozen=True, slots=True)
class HapticEffect:
    """One haptic effect, with every field the canonical structure carries.

    Which fields matter depends on :attr:`type`; the rest are ignored by the
    device rather than rejected, which is the canonical behaviour.

    **The defaults are CNA's, not this file's opinion.** ``haptic_effect_init``
    is documented as producing "a zeroed constant effect with a polar
    direction", and both ``Constant`` and ``Polar`` are zero, so the zeroed
    structure *is* that default. A test asserts that ``HapticEffect()`` and a
    zeroed native structure agree field for field, so a CNA that changed either
    identity would be caught rather than silently disagreed with.

    The six per-axis fields hold exactly three entries each, because the C
    arrays do.
    """

    type: HapticEffectType = HapticEffectType.Constant
    direction: HapticDirection = None  # type: ignore[assignment]
    length: int = 0
    delay: int = 0
    button: int = 0
    interval: int = 0
    level: int = 0
    period: int = 0
    magnitude: int = 0
    offset: int = 0
    phase: int = 0
    ramp_start: int = 0
    ramp_end: int = 0
    right_saturation: tuple[int, int, int] = (0, 0, 0)
    left_saturation: tuple[int, int, int] = (0, 0, 0)
    right_coefficient: tuple[int, int, int] = (0, 0, 0)
    left_coefficient: tuple[int, int, int] = (0, 0, 0)
    deadband: tuple[int, int, int] = (0, 0, 0)
    center: tuple[int, int, int] = (0, 0, 0)
    large_magnitude: int = 0
    small_magnitude: int = 0
    custom_period: int = 0
    custom_channels: int = 0
    attack_length: int = 0
    attack_level: int = 0
    fade_length: int = 0
    fade_level: int = 0
    #: A custom waveform's samples, empty for every other effect type.
    custom_data: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.direction is None:
            object.__setattr__(
                self, "direction",
                HapticDirection(HapticDirectionType.Polar, (0, 0, 0)))
        for name in ("right_saturation", "left_saturation", "right_coefficient",
                     "left_coefficient", "deadband", "center"):
            value = getattr(self, name)
            if len(value) != 3:
                raise ValueError(
                    f"{name} has exactly three entries, got {len(value)}")


@dataclass(frozen=True, slots=True)
class TextEditing:
    """One IME composition update: the text so far and the selection in it.

    ``start`` and ``length`` index **UTF-16 code units** in ``text``, which is
    what the platform reports and what an editor has to apply them to. They are
    not character offsets, and this type does not convert them into any.
    """

    text: str
    start: int
    length: int


@dataclass(frozen=True, slots=True)
class TextEditingCandidates:
    """The IME's current candidate list.

    ``selected`` is an index into :attr:`candidates`, or ``None`` when the IME
    has not highlighted one. ``horizontal`` is how the platform wants the list
    laid out.
    """

    candidates: tuple[str, ...]
    selected: int | None
    horizontal: bool
