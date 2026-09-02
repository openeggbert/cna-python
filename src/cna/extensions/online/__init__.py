"""What CNA adds around XNA's online runtime, and the backends that qualify it.

The strict ``Microsoft.Xna.Framework.Net`` and
``Microsoft.Xna.Framework.GamerServices`` packages carry exactly XNA's surface.
CNA has more: it can publish a signed-in gamer, build a session roster, hand a
title the Guide's pending request so the title can draw it itself, and give an
avatar a real animation clip. None of that is XNA, so none of it belongs in
those namespaces -- it belongs here.

**Nothing in this package is used by the strict profile.** The dependency runs
one way: this package reaches into the strict types' handles, and the strict
types never import this one. The extension gate asserts that importing the XNA
namespace loads no ``cna`` module.

Publishing a signed-in gamer is platform identity
-------------------------------------------------

:func:`publish_signed_in_gamers` is the route a platform layer would call. It is
here, in an extension package, and never in shipping game code, because a game
that called it would be inventing a user. What the qualification proves through
it is labelled ``SYNTHETIC_SIGNED_IN_GAMER_VERIFIED`` and never
``REAL_PLATFORM_SIGN_IN_VERIFIED``: no Xbox Live account was signed in, and this
package cannot sign one in.
"""

from __future__ import annotations

from . import avatars, errors, gamers, guide, sessions
from .avatars import (
    animation_clip_name, avatar_body_type_content_name, enable_real_avatar_rendering,
    draw_real_avatar, on_avatar_description_changed, preset_clip_name,
    set_animation_clip_name, set_avatar_appearance,
)
from .errors import OnlineExtensionError, OnlineExtensionStateError
from .gamers import (
    create_achievement, create_achievement_collection, create_friend_collection,
    create_friend_gamer, create_signed_in_gamer, freed_gamer_count,
    gamer_collection_add, gamer_collection_clear, gamer_collection_remove,
    on_installing_title_update, on_signed_in, on_signed_out,
    publish_signed_in_gamers, set_presence_mode_string, unsubscribe_gamer_event,
    update_dispatcher_async,
)
from .guide import (
    PendingKeyboardInput, PendingMessageBox, cancel_pending_keyboard_input,
    click_pending_message_box, pending_keyboard_input, pending_message_box,
    render_pending_keyboard_input, render_pending_message_box,
    reset_pending_keyboard_input, reset_pending_message_box, set_guide_visible,
    set_trial_mode, show_achievements,
)
from .sessions import (
    NetworkEventType, active_session_action_count, add_remote_gamer, clear_packet_queue,
    create_available_session, create_available_session_collection,
    create_local_network_gamer, create_network_gamer, create_network_machine,
    enqueue_packet, live_session_count, on_invite_accepted, owned_gamer_count,
    release_session_properties, remove_gamer, send_network_event,
    set_gamer_has_left, set_gamer_id, set_gamer_is_host, set_gamer_machine,
    set_gamer_roundtrip,
)

__all__ = [
    "avatars", "errors", "gamers", "guide", "sessions",
    # avatars
    "animation_clip_name", "avatar_body_type_content_name", "draw_real_avatar",
    "enable_real_avatar_rendering", "on_avatar_description_changed",
    "preset_clip_name", "set_animation_clip_name", "set_avatar_appearance",
    # errors
    "OnlineExtensionError", "OnlineExtensionStateError",
    # gamers
    "create_achievement", "create_achievement_collection",
    "create_friend_collection", "create_friend_gamer", "create_signed_in_gamer",
    "freed_gamer_count", "gamer_collection_add", "gamer_collection_clear",
    "gamer_collection_remove", "on_installing_title_update", "on_signed_in",
    "on_signed_out", "publish_signed_in_gamers", "set_presence_mode_string",
    "unsubscribe_gamer_event", "update_dispatcher_async",
    # guide
    "PendingKeyboardInput", "PendingMessageBox", "cancel_pending_keyboard_input",
    "click_pending_message_box", "pending_keyboard_input", "pending_message_box",
    "render_pending_keyboard_input", "render_pending_message_box",
    "reset_pending_keyboard_input", "reset_pending_message_box",
    "set_guide_visible", "set_trial_mode", "show_achievements",
    # sessions
    "NetworkEventType", "active_session_action_count", "add_remote_gamer", "clear_packet_queue",
    "create_available_session", "create_available_session_collection",
    "create_local_network_gamer", "create_network_gamer", "create_network_machine",
    "enqueue_packet", "live_session_count", "on_invite_accepted",
    "owned_gamer_count", "release_session_properties", "remove_gamer",
    "send_network_event", "set_gamer_has_left", "set_gamer_id", "set_gamer_is_host",
    "set_gamer_machine", "set_gamer_roundtrip",
]
