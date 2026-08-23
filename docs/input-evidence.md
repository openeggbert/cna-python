# Non-touch input evidence

The keyboard, mouse, and gamepad families are structurally local-zero. Touch
was explicitly not started.

KeyboardState filters duplicate and undefined enum values, orders pressed keys
by underlying value, preserves XNA's eight-word hash, and treats invalid Int32
key values as up. Keyboard polling remains real CNA polling for the global and
player overloads.

MouseState covers coordinates, wheel, five buttons, equality, XNA hash, and
string behavior. `Mouse.GetState`, `SetPosition`, and the mutable static
`WindowHandle` property call exact CNA ABI-0.7 routes; there is no managed
shadow-state fallback.

GamePadButtons, GamePadDPad, GamePadThumbSticks, GamePadTriggers, GamePadState,
GamePadCapabilities, GamePadType, and GamePad are complete. The managed value
layer covers clamping, packet/connection state, physical-button filtering,
analog-derived button thresholds, hashes/strings, capability projection,
dead-zone overloads, and vibration. `GetState`, `GetCapabilities`, and
`SetVibration` call canonical CNA functions.

Evidence classification:

- `API_COMPLETE`: all selected non-touch input types are local-zero.
- `NATIVE_ROUTE_VERIFIED`: all selected polling/window/capability/vibration
  calls execute against the qualified HEADLESS ABI-0.7 artifact.
- `PHYSICAL_HARDWARE_NOT_VERIFIED`: no controller or window-system hardware was
  present in the qualification environment; disconnected/default results are
  legitimate and no capability is fabricated.
