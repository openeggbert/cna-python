"""What CNA adds to XNA's avatars: real clips, appearance, and real rendering.

XNA's ``AvatarRenderer`` draws the platform's avatar. CNA can also drive a real
animation clip by name, set an explicit appearance, and render a model the caller
supplies -- none of which XNA has, so none of which belongs in
``Microsoft.Xna.Framework.GamerServices``.
"""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from typing import Callable, TYPE_CHECKING

from Microsoft.Xna.Framework.GamerServices import (
    AvatarAnimation, AvatarAnimationPreset, AvatarBodyType, AvatarDescription,
    AvatarRenderer,
)

from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import CallbackRoot, checked, string_view

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Color
    from Microsoft.Xna.Framework.Graphics import GraphicsDevice, Model

__all__ = [
    "preset_clip_name", "avatar_body_type_content_name", "animation_clip_name",
    "set_animation_clip_name", "set_avatar_appearance",
    "enable_real_avatar_rendering", "draw_real_avatar",
    "on_avatar_description_changed",
]

_support = _on.support
_VERSION = 1
_TICKS_PER_MICROSECOND = 10
_roots = CallbackRoot()


def preset_clip_name(preset: AvatarAnimationPreset) -> str:
    """The content name of the clip a preset plays."""
    value = c.c_uint32(int(AvatarAnimationPreset(preset)))
    return _support.sized_text("cna_avatar_animation_preset_get_clip_name_size_ext",
                               "cna_avatar_animation_preset_copy_clip_name_ext",
                               (value,), "preset clip name")


def avatar_body_type_content_name(body_type: AvatarBodyType) -> str:
    """The content name of a body type's avatar model."""
    value = c.c_uint32(int(AvatarBodyType(body_type)))
    return _support.sized_text("cna_avatar_body_type_get_content_name_size_ext",
                               "cna_avatar_body_type_copy_content_name_ext",
                               (value,), "body type content name")


def animation_clip_name(animation: AvatarAnimation) -> str:
    """The real clip an animation is playing, when one has been set."""
    return _support.sized_text("cna_avatar_animation_get_real_clip_name_size_ext",
                               "cna_avatar_animation_copy_real_clip_name_ext",
                               (animation._value,), "animation clip name")


def set_animation_clip_name(animation: AvatarAnimation, clip_name: str) -> None:
    """Points an animation at a real clip by name."""
    view, _keep = string_view(clip_name, "clip_name")
    _support.call("cna_avatar_animation_set_real_clip_name_ext", animation._value,
                  view)


def set_avatar_appearance(renderer: AvatarRenderer, *, skin: "Color | None" = None,
                          hair: "Color | None" = None, shirt: "Color | None" = None,
                          pants: "Color | None" = None,
                          shoes: "Color | None" = None) -> None:
    """Sets an avatar's five colours, starting from CNA's own default.

    The default is read from CNA rather than written down, so a colour this
    caller does not name keeps whatever CNA chose for it.
    """
    from _cna_native import abi

    appearance = _support.out_struct(_online.CNA_AvatarAppearanceEXT, _VERSION,
                                     "cna_avatar_appearance_init_ext")
    for name, colour in (("skin_color", skin), ("hair_color", hair),
                         ("shirt_color", shirt), ("pants_color", pants),
                         ("shoes_color", shoes)):
        if colour is None:
            continue
        native = abi.CNA_Color()
        native.r, native.g = int(colour.R), int(colour.G)
        native.b, native.a = int(colour.B), int(colour.A)
        setattr(appearance, name, native)
    _support.call("cna_avatar_renderer_set_appearance_ext", renderer._value,
                  c.byref(appearance))


def enable_real_avatar_rendering(renderer: AvatarRenderer, device: "GraphicsDevice",
                                 model: "Model") -> None:
    """Gives a renderer a device and a model so it can draw something real.

    Both are **borrowed** for as long as the renderer draws with them, and CNA
    says so: the renderer holds neither alive, so the caller must.
    """
    for name, value in (("device", device), ("model", model)):
        if not hasattr(value, "_require_handle"):
            raise TypeError(f"{name} must be a strict XNA graphics object")
    _support.call("cna_avatar_renderer_enable_real_rendering_ext", renderer._value,
                  c.c_uint64(device._require_handle()),
                  c.c_uint64(model._require_handle()))


def draw_real_avatar(renderer: AvatarRenderer, clip_name: str,
                     position: timedelta, *, loop: bool = True) -> None:
    """Draws the enabled model at a position in a named clip."""
    view, _keep = string_view(clip_name, "clip_name")
    microseconds = (position.days * 86_400_000_000 + position.seconds * 1_000_000
                    + position.microseconds)
    _support.call("cna_avatar_renderer_draw_real_ext", renderer._value, view,
                  c.c_int64(microseconds * _TICKS_PER_MICROSECOND),
                  c.c_uint8(1 if loop else 0))


def on_avatar_description_changed(handler: Callable[[], None]) -> int:
    """Calls ``handler()`` when the signed-in gamer changes their avatar."""
    if not callable(handler):
        raise TypeError("handler must be callable")

    def adapt(_context) -> None:
        handler()

    key = object()
    trampoline = _roots.root(key, _online.CNA_GamerAsyncCallback, adapt)
    try:
        registration = _support.out_handle(
            "cna_avatar_description_subscribe_changed_ext", trampoline, None)
    except BaseException:
        _roots.release(key)
        raise
    _roots.root(registration, _online.CNA_GamerAsyncCallback, adapt)
    _roots.release(key)
    return registration
