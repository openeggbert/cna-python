"""Building a session's roster, and driving one without a peer.

XNA's ``NetworkSession`` fills its own rosters from the network. CNA can fill
them explicitly -- add a remote gamer, set who the host is, deliver a packet --
which is how a session's behaviour is qualified on one machine with no second
peer. None of it is XNA, so none of it belongs in
``Microsoft.Xna.Framework.Net``.

A result obtained through this module is evidence about the session's own
bookkeeping, the packet protocol and this binding. It is **not** evidence that
two machines talked to each other.
"""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from enum import IntEnum
from typing import Callable, Sequence

from Microsoft.Xna.Framework.GamerServices import SignedInGamer
from Microsoft.Xna.Framework.Net import (
    AvailableNetworkSession, AvailableNetworkSessionCollection, LocalNetworkGamer,
    NetworkGamer, NetworkMachine, NetworkSession, NetworkSessionEndReason,
    NetworkSessionProperties, NetworkSessionType, QualityOfService, SendDataOptions,
)

from _cna_native import online_abi as _online
from _cna_native import online_support as _on
from _cna_native.family_support import CallbackRoot, checked, string_view

__NETWORK_EVENT_DOC = """One of CNA's network-event identities."""

__all__ = [
    "NetworkEventType",
    "create_network_gamer", "create_local_network_gamer", "create_network_machine",
    "add_remote_gamer", "remove_gamer", "set_gamer_id", "set_gamer_is_host",
    "set_gamer_has_left", "set_gamer_machine", "set_gamer_roundtrip",
    "enqueue_packet", "clear_packet_queue", "send_network_event",
    "create_available_session", "create_available_session_collection",
    "release_session_properties", "live_session_count", "owned_gamer_count",
    "active_session_action_count", "on_invite_accepted",
]

_support = _on.support
_VERSION = 1
_TICKS_PER_MICROSECOND = 10
_roots = CallbackRoot()


class NetworkEventType(IntEnum):
    """Which event :func:`send_network_event` raises.

    CNA's identities, read from the generated ABI rather than written down: an
    event a session raises is one of these five, and choosing the wrong number
    would raise a different event without anything noticing.
    """

    PacketSend = _online.CNA_NETWORK_EVENT_TYPE_PACKET_SEND
    GamerJoin = _online.CNA_NETWORK_EVENT_TYPE_GAMER_JOIN
    GamerLeave = _online.CNA_NETWORK_EVENT_TYPE_GAMER_LEAVE
    HostChange = _online.CNA_NETWORK_EVENT_TYPE_HOST_CHANGE
    StateChange = _online.CNA_NETWORK_EVENT_TYPE_STATE_CHANGE


def create_network_gamer(session: NetworkSession, gamertag: str) -> NetworkGamer:
    """Creates a remote gamer for a session. CNA's factory, not XNA's."""
    view, _keep = string_view(gamertag, "gamertag")
    return NetworkGamer(_support.out_handle("cna_network_gamer_create",
                                            session._value, view), owned=True)


def create_local_network_gamer(gamer: SignedInGamer,
                               session: NetworkSession) -> LocalNetworkGamer:
    """Creates the local gamer a signed-in gamer plays a session as."""
    return LocalNetworkGamer(_support.out_handle(
        "cna_local_network_gamer_create_ext", gamer._value, session._value),
        owned=True)


def create_network_machine() -> NetworkMachine:
    """Creates a machine a session's gamers can be attached to."""
    return NetworkMachine(_support.out_handle("cna_network_machine_create"),
                          owned=True)


def add_remote_gamer(session: NetworkSession, gamer: NetworkGamer) -> None:
    """Puts a gamer on a session's remote roster."""
    _support.call("cna_network_session_add_remote_gamer_ext", session._value,
                  gamer._value)


def remove_gamer(session: NetworkSession, gamer: NetworkGamer,
                 reason: NetworkSessionEndReason) -> None:
    """Takes a gamer off a session, with the reason the event will carry."""
    _support.call("cna_network_session_remove_gamer_ext", session._value,
                  gamer._value,
                  c.c_uint32(int(NetworkSessionEndReason(reason))))


def set_gamer_id(gamer: NetworkGamer, gamer_id: int) -> None:
    """Sets the byte identity a session uses to find a gamer."""
    _support.call("cna_network_gamer_set_id_ext", gamer._value,
                  c.c_uint8(checked(gamer_id, "uint8", "gamer_id")))


def set_gamer_is_host(gamer: NetworkGamer, is_host: bool) -> None:
    """Makes a gamer the host, or stops it being one."""
    _support.call("cna_network_gamer_set_is_host_ext", gamer._value,
                  c.c_uint8(1 if is_host else 0))


def set_gamer_has_left(gamer: NetworkGamer, has_left: bool) -> None:
    """Marks a gamer as having left the session."""
    _support.call("cna_network_gamer_set_has_left_session_ext", gamer._value,
                  c.c_uint8(1 if has_left else 0))


def set_gamer_machine(gamer: NetworkGamer, machine: NetworkMachine) -> None:
    """Attaches a gamer to a machine.

    The machine is **borrowed**: it must outlive every gamer attached to it.
    """
    _support.call("cna_network_gamer_set_machine", gamer._value, machine._value)


def set_gamer_roundtrip(gamer: NetworkGamer, roundtrip: timedelta) -> None:
    """Sets the round-trip time a gamer reports, in exact ticks."""
    microseconds = (roundtrip.days * 86_400_000_000 + roundtrip.seconds * 1_000_000
                    + roundtrip.microseconds)
    _support.call("cna_network_gamer_set_roundtrip_ticks_ext", gamer._value,
                  c.c_int64(microseconds * _TICKS_PER_MICROSECOND))


def enqueue_packet(gamer: LocalNetworkGamer, data: bytes, *,
                   sender: NetworkGamer | None = None,
                   options: SendDataOptions = SendDataOptions.None_) -> None:
    """Delivers one packet to a local gamer as if it had arrived.

    This is what makes ``ReceiveData`` measurable on one machine: the packet is
    real, its bytes are the caller's, and the receiving side is the same code a
    remote packet would take.
    """
    payload = bytes(bytearray(data))
    buffer = (c.c_uint8 * len(payload))(*payload) if payload else None
    info = _on.in_struct(_online.CNA_NetworkEventInfo, _VERSION)
    # The header is explicit: "the description's gamer field names the sender".
    # ``sender`` is a different field, and setting it instead delivers a packet
    # whose sender a later receive reports as nobody.
    info.gamer = 0 if sender is None else sender._value.value
    info.packet = c.cast(buffer, c.c_void_p) if payload else None
    info.packet_byte_count = len(payload)
    info.reliable = 1 if int(options) & int(SendDataOptions.Reliable) else 0
    _support.call("cna_local_network_gamer_enqueue_packet_ext", gamer._value,
                  c.byref(info))


def clear_packet_queue(gamer: LocalNetworkGamer) -> None:
    """Drops every packet waiting for a local gamer."""
    _support.call("cna_local_network_gamer_clear_packet_queue_ext", gamer._value)


def send_network_event(session: NetworkSession,
                       event_type: "NetworkEventType" = None,
                       *, gamer: NetworkGamer | None = None,
                       state: int = 0, reason: int = 0) -> None:
    """Raises one of a session's events explicitly.

    The event travels the same path a network-delivered one does, which is what
    makes the event contract -- ordering, payload, exactly-once -- measurable
    without a peer.
    """
    if event_type is None:
        raise TypeError("event_type is required")
    info = _on.in_struct(_online.CNA_NetworkEventInfo, _VERSION)
    info.type = int(NetworkEventType(event_type))
    info.gamer = 0 if gamer is None else gamer._value.value
    info.state = checked(state, "uint32", "state")
    info.reason = checked(reason, "uint32", "reason")
    _support.call("cna_network_session_send_network_event_ext", session._value,
                  c.byref(info))


def create_available_session(host_gamertag: str, *, current_gamer_count: int = 0,
                             open_public_gamer_slots: int = 4,
                             open_private_gamer_slots: int = 0,
                             session_type: NetworkSessionType = NetworkSessionType.SystemLink,
                             host_address: str = "", host_port: int = 0,
                             session_properties: NetworkSessionProperties | None = None,
                             roundtrip: timedelta | None = None
                             ) -> AvailableNetworkSession:
    """Builds one discovered session, as discovery would have.

    ``roundtrip`` gives it a measured quality of service; without one the
    session reports CNA's unmeasured default, which is what an undiscovered
    quality really is.
    """
    info = _on.in_struct(_online.CNA_AvailableNetworkSessionCreateInfo, _VERSION)
    info.current_gamer_count = checked(current_gamer_count, "int32",
                                       "current_gamer_count")
    info.open_public_gamer_slots = checked(open_public_gamer_slots, "int32",
                                           "open_public_gamer_slots")
    info.open_private_gamer_slots = checked(open_private_gamer_slots, "int32",
                                            "open_private_gamer_slots")
    info.session_type = int(NetworkSessionType(session_type))
    info.host_port = checked(host_port, "uint16", "host_port")
    tag_view, _keep_tag = string_view(host_gamertag, "host_gamertag")
    address_view, _keep_address = string_view(host_address, "host_address")
    info.host_gamertag = tag_view
    info.host_address = address_view
    info.session_properties = (0 if session_properties is None
                               else session_properties._value.value)
    if roundtrip is None:
        quality = _support.out_struct(_online.CNA_QualityOfService, _VERSION,
                                      "cna_quality_of_service_init")
    else:
        quality = QualityOfService._measured(roundtrip)._native
    return AvailableNetworkSession(_support.out_handle(
        "cna_available_network_session_create_ext", c.byref(info),
        c.byref(quality)), owned=True)


def create_available_session_collection(
        sessions: Sequence[AvailableNetworkSession]
) -> AvailableNetworkSessionCollection:
    """Builds the collection ``NetworkSession.Find`` would have returned."""
    values = []
    for index, session in enumerate(sessions):
        if not isinstance(session, AvailableNetworkSession):
            raise TypeError(f"sessions[{index}] must be an AvailableNetworkSession")
        values.append(session._value.value)
    array = (c.c_uint64 * len(values))(*values) if values else None
    return AvailableNetworkSessionCollection(_support.out_handle(
        "cna_available_network_session_collection_create_ext", array,
        c.c_uint64(len(values))))


def release_session_properties(properties: NetworkSessionProperties) -> None:
    """Releases a property list this caller owns.

    XNA has no ``Dispose`` here -- the list is garbage-collected -- so the C
    handle's release has no public name and lives in this package instead.
    """
    _support.call("cna_network_session_properties_destroy",
                  c.c_uint64(properties._value.value))


def live_session_count() -> int:
    """How many session objects CNA currently holds. A leak check."""
    return _support.out_i32("cna_network_session_get_instance_count_ext")


def owned_gamer_count(session: NetworkSession) -> int:
    """How many gamer objects one session owns. The other half of the leak check."""
    return _support.out_u64("cna_network_session_get_owned_gamer_count_ext",
                            session._value)


def active_session_action_count() -> int:
    """How many asynchronous session actions have not finished.

    Zero after a run is what proves no ``Begin`` was left outstanding.
    """
    return _support.out_i32("cna_network_session_get_active_action_count_ext")


def on_invite_accepted(handler: Callable[[SignedInGamer, bool], None]) -> int:
    """Calls ``handler(gamer, is_current_session)`` when an invite is accepted.

    Process-wide rather than per session, because the invite arrives before any
    session exists -- which is why CNA's subscribe route takes no session either.
    """
    if not callable(handler):
        raise TypeError("handler must be callable")

    def adapt(pointer, _context) -> None:
        info = pointer.contents
        handler(SignedInGamer(int(info.gamer), owned=False),
                bool(info.is_current_session))

    key = object()
    trampoline = _roots.root(key, _online.CNA_InviteAcceptedCallback, adapt)
    try:
        registration = _support.out_handle(
            "cna_network_session_subscribe_invite_accepted", trampoline, None)
    except BaseException:
        _roots.release(key)
        raise
    _roots.root(registration, _online.CNA_InviteAcceptedCallback, adapt)
    _roots.release(key)
    return registration
