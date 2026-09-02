#!/usr/bin/env python3
"""Derives a native family's ctypes function manifest from its headers.

A manifest entry is four things: the symbol, its ctypes return type, its ctypes
argument types, and the ownership contract the Python wrapper has to keep. The
first three are *facts about the header* and are read from it here. The fourth
is a decision, and comes from :data:`OWNERSHIP` -- a shape rule per route family
plus the explicit overrides that shape rule would get wrong.

Writing seven hundred prototypes out by hand is how a wrong pointer depth gets
in. Reading them means a route CNA changes shows up as a diff in a generated
file, and ``tools/verify_prototypes.py`` still proves every entry against the
canonical declaration with the C compiler -- generated or not, nothing here is
trusted without that.

Which routes a family's manifest carries is *not* generated: it comes from the
family's landed groups, so a route is imported when its Python consumer exists
and not before. An imported route with no caller is dead native surface, and
``tools/verify_route_reachability.py`` fails on one.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from cna_headers import Declaration, parse_header, strip_comments  # noqa: E402
import generate_family_abi as families  # noqa: E402

SRC = ROOT / "src/_cna_native"

#: C spellings with a fixed ctypes rendering.
SCALARS = {
    "void": "None",
    "uint8_t": "c.c_uint8",
    "uint16_t": "c.c_uint16",
    "uint32_t": "c.c_uint32",
    "uint64_t": "c.c_uint64",
    "int8_t": "c.c_int8",
    "int16_t": "c.c_int16",
    "int32_t": "c.c_int32",
    "int64_t": "c.c_int64",
    "float": "c.c_float",
    "double": "c.c_double",
    "char": "c.c_char",
    "CNA_Handle": "c.c_uint64",
    "CNA_Bool": "c.c_uint8",
    "CNA_Result": "c.c_uint32",
}

_SCALAR_TYPEDEF = re.compile(
    r"^typedef\s+(uint8_t|uint16_t|uint32_t|uint64_t|int8_t|int16_t|int32_t|int64_t|float|double)"
    r"\s+(CNA_[A-Za-z0-9_]+)\s*;", re.M)
_HANDLE_TYPEDEF = re.compile(r"^typedef\s+CNA_Handle\s+(CNA_[A-Za-z0-9_]+)\s*;", re.M)


class ManifestError(RuntimeError):
    """A declaration this generator will not guess at."""


@dataclass(frozen=True)
class Rendered:
    name: str
    restype: str
    argtypes: list[str]
    ownership: str


def _resolve_aliases(include: Path) -> tuple[dict[str, str], set[str]]:
    """Every scalar typedef and every opaque handle typedef CNA declares."""
    aliases: dict[str, str] = {}
    handles: set[str] = set()
    for header in sorted((include / "CNA/C").glob("*.h")):
        text = strip_comments(header.read_text(encoding="utf-8"))
        for base, name in _SCALAR_TYPEDEF.findall(text):
            aliases[name] = base
        handles.update(_HANDLE_TYPEDEF.findall(text))
    return aliases, handles


def _known_structures(family: families.Family) -> dict[str, str]:
    """Structures and callback types this family's module or its imports declare."""
    import ctypes as _ctypes
    import importlib

    found: dict[str, str] = {}
    modules = [("abi", "abi")] + [(f"{name}_abi", f"{name}_abi")
                                  for name in family.imports]
    modules.append((f"{family.identifier}_abi", f"{family.identifier}_abi"))
    for module_name, alias in modules:
        module = importlib.import_module(f"_cna_native.{module_name}")
        for name in dir(module):
            value = getattr(module, name)
            if not name.startswith("CNA_"):
                continue
            if isinstance(value, type) and issubclass(
                    value, (_ctypes.Structure, _ctypes.Union)):
                found[name] = f"{alias}.{name}"
            elif isinstance(value, type) and issubclass(value, _ctypes._CFuncPtr):
                found[name] = f"{alias}.{name}"
    return found


def _render_type(spelling: str, aliases: dict[str, str], handles: set[str],
                 structures: dict[str, str]) -> str:
    text = " ".join(spelling.replace("const ", " ").replace("struct ", " ").split())
    if text.endswith("*"):
        pointee = text[:-1].strip()
        if pointee in ("void",):
            return "c.c_void_p"
        return f"c.POINTER({_render_type(pointee, aliases, handles, structures)})"
    if text in SCALARS:
        return SCALARS[text]
    if text in handles:
        return "c.c_uint64"
    if text in aliases:
        return SCALARS[aliases[text]]
    if text in structures:
        return structures[text]
    raise ManifestError(f"no ctypes rendering for C type {spelling!r}")


#: How each route shape describes its ownership, matched in order by a regular
#: expression over the route name. The first match wins, and a route no rule
#: matches stops the generator rather than acquiring a vague description.
OWNERSHIP: tuple[tuple[str, str], ...] = (
    (r"_create_with_test_backend_ext$|_set_test_backend_ext$",
     "test backend only; installs a deterministic implementation and resets its log"),
    (r"_create(_.*)?$|_open(_.*)?$",
     "owned handle; the caller closes it and nothing else may"),
    (r"_destroy$|_dispose$|_close$",
     "consumes the handle; every borrowed view of it is invalid afterwards"),
    (r"_subscribe(_.*)?$",
     "roots a callback trampoline; the registration is owned and must be released "
     "before the owner is destroyed"),
    (r"_unsubscribe(_.*)?$",
     "consumes a subscription registration; no callback arrives afterwards"),
    (r"_copy_", "caller output; two-call size/copy protocol, no partial write"),
    (r"_get_.*_size(_.*)?$", "caller output; the size half of the size/copy protocol"),
    (r"_get_", "caller output; borrowed handle, nothing is retained"),
    (r"_set_", "borrowed handle; copies the value, retains nothing"),
    (r"_init(_.*)?$", "pure value initialiser over caller-owned storage"),
    (r"_equals$|_get_hash_code$|_not_equals$",
     "pure function over caller-owned input; nothing is retained"),
    (r"", "borrowed handle; retains nothing"),
)

#: Routes whose ownership the shape rules describe wrongly. Each is a decision
#: about lifetime that had to be read out of the header's own documentation.
OWNERSHIP_OVERRIDES: dict[str, str] = {
    "cna_accelerometer_create":
        "owned sensor; borrows the game for the call and holds no reference to it",
    "cna_compass_create":
        "owned sensor; borrows the game for the call and holds no reference to it",
    "cna_gyroscope_create":
        "owned sensor; borrows the game for the call and holds no reference to it",
    "cna_motion_create":
        "owned sensor; borrows the game for the call and holds no reference to it",
    "cna_camera_create":
        "owned camera; borrows the game for the call and holds no reference to it",
    "cna_camera_create_with_test_backend_ext":
        "owned camera over a deterministic backend; test use only",
    "cna_system_tray_create":
        "owned tray; borrows the game for the call and holds no reference to it",
    "cna_system_tray_create_with_test_backend_ext":
        "owned tray over a deterministic backend; test use only",
    "cna_accelerometer_dispose":
        "stops the sensor and releases its subsystem hold; the handle stays valid",
    "cna_compass_dispose":
        "stops the sensor and releases its subsystem hold; the handle stays valid",
    "cna_gyroscope_dispose":
        "stops the sensor and releases its subsystem hold; the handle stays valid",
    "cna_motion_dispose":
        "stops the sensor and releases its subsystem hold; the handle stays valid",
    "cna_camera_try_acquire_frame_ext":
        "caller output; copies the frame bytes into caller storage, retains nothing",
    "cna_mouse_cursor_create_from_texture2d":
        "owned cursor; the Texture2D is read during the call and not retained",
    "cna_mouse_set_cursor_ext":
        "the cursor is BORROWED for as long as it is the active one",
}


def _ownership(name: str) -> str:
    override = OWNERSHIP_OVERRIDES.get(name)
    if override is not None:
        return override
    for pattern, text in OWNERSHIP:
        if re.search(pattern, name):
            return text
    raise ManifestError(f"no ownership rule matched {name}")


def render(family: families.Family, include: Path,
           groups: dict[str, tuple[str, str]],
           landed: tuple[str, ...]) -> str:
    refused = refused_routes()
    family_exclusions = FAMILY_EXCLUSIONS.get(family.identifier, {})
    aliases, handles = _resolve_aliases(include)
    structures = _known_structures(family)
    declarations: dict[str, Declaration] = {}
    for header in family.headers:
        for declaration in parse_header(include / "CNA/C" / header):
            declarations[declaration.name] = declaration

    claimed: dict[str, str] = {}
    for name in declarations:
        if _is_refused(name, refused) is not None:
            claimed[name] = "<excluded>"
        elif any(re.fullmatch(pattern, name) for pattern in family_exclusions):
            claimed[name] = "<excluded>"
    for group, (prefixes, _title) in groups.items():
        for pattern in prefixes.split():
            for name in declarations:
                if re.fullmatch(pattern, name):
                    if claimed.get(name) == "<excluded>":
                        continue
                    if name in claimed and claimed[name] != group:
                        raise ManifestError(
                            f"{name} is claimed by both {claimed[name]} and {group}")
                    claimed[name] = group

    unclaimed = sorted(set(declarations) - set(claimed))
    if unclaimed:
        raise ManifestError(
            f"{len(unclaimed)} route(s) in {family.identifier} are in no group: "
            + ", ".join(unclaimed[:8]))

    prefix = family.prefix
    import_lines = ["from . import abi"]
    for name in family.imports:
        import_lines.append(f"from . import {name}_abi")
    import_lines.append(f"from . import {family.identifier}_abi")

    lines = [
        f'"""ctypes manifest for CNA\'s {", ".join(f"``{h}``" for h in family.headers)} family.',
        "",
        "Do not edit. ``tools/generate_family_manifest.py`` derives every prototype",
        "from the canonical headers, and ``--check`` fails when the checked-in copy is",
        "not what the current headers produce. Every entry is proven against the",
        "canonical C declaration by ``tools/verify_prototypes.py`` -- being generated is",
        "not a reason to trust it.",
        "",
        "The fourth column is the ownership contract the Python wrapper has to keep.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import ctypes as c",
        "",
        *import_lines,
        "",
        "Entry = tuple[str, object, list[object], str]",
        "",
    ]

    exported: list[str] = []
    for group in groups:
        if group not in landed:
            continue
        _prefixes, title = groups[group]
        names = sorted(name for name, owner in claimed.items() if owner == group)
        constant = f"{prefix}_{group.upper()}_MANIFEST"
        exported.append(constant)
        lines.append(f"#: {title}")
        lines.append(f"{constant}: tuple[Entry, ...] = (")
        for name in names:
            declaration = declarations[name]
            restype = _render_type(declaration.return_type, aliases, handles, structures)
            if declaration.is_void_parameter_list:
                argtypes: list[str] = []
            else:
                argtypes = [
                    _render_type(parameter.type_text, aliases, handles, structures)
                    for parameter in declaration.parameters
                ]
            rendered = ", ".join(argtypes)
            lines.append(f'    ("{name}", {restype}, [{rendered}],')
            lines.append(f'     "{_ownership(name)}"),')
        lines.append(")")
        lines.append("")

    lines.append(f"#: Every group above, in one tuple for :mod:`_cna_native.loader`.")
    lines.append(f"{prefix}_FUNCTION_MANIFEST: tuple[Entry, ...] = (")
    for constant in exported:
        lines.append(f"    {constant}")
        lines.append("    +")
    lines.pop()
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


#: Sensors and device services.  The groups are the census sub-families, so a
#: route's manifest group and its census decision are the same partition.
DEVICES_GROUPS: dict[str, tuple[str, str]] = {
    "accelerometer": (
        r"cna_accelerometer_\w+",
        "The accelerometer: its reading value, its state machine, and the synthetic\n"
        "#: backend the qualification uses instead of physical hardware."),
    "compass": (
        r"cna_compass_\w+",
        "The compass: magnetic and true heading, accuracy, and calibration requests."),
    "gyroscope": (
        r"cna_gyroscope_\w+",
        "The gyroscope: angular rotation rate and its state machine."),
    "motion": (
        r"cna_motion_\w+",
        "The fused motion sensor: attitude, gravity, device acceleration and rate."),
    "sensor_shared": (
        r"cna_attitude_reading_\w+ cna_calibration_event_info_\w+ "
        r"cna_sensors_get_last_error_id_ext cna_sensor_unsubscribe_ext",
        "What every sensor shares: the attitude reading, calibration event identity,\n"
        "#: the last error, and the one unsubscribe every sensor registration uses."),
    "camera": (
        r"cna_camera_\w+",
        "The camera: enumeration, the deterministic frame backend, and acquisition."),
    "host": (
        r"cna_devices_clipboard_\w+ cna_devices_ext_is_available cna_display_info_\w+ "
        r"cna_environment_get_\w+ cna_locale_\w+ cna_power_get_\w+ "
        r"cna_system_info_\w+ cna_url_launcher_\w+",
        "The host itself: clipboard, display metrics, device class, locales, power\n"
        "#: and system information."),
    "dialogs": (
        r"cna_file_dialog_\w+ cna_message_box_\w+ cna_system_tray_\w+",
        "Host UI: file dialogs, message boxes and the system tray, each with the test\n"
        "#: backend that answers without putting anything on a physical desktop."),
    "vibration": (
        r"cna_vibrate_controller_\w+",
        "Controller vibration, and the test log that records what was asked for."),
}

#: Extended input.  The groups are the census sub-families.
INPUT_GROUPS: dict[str, tuple[str, str]] = {
    "clipboard": (
        r"cna_clipboard_\w+",
        "The host clipboard's read side. ``devices.h`` writes it and\n"
        "#: ``input_devices.h`` reads it; the two are one clipboard."),
    "text_input": (
        r"cna_text_input_\w+",
        "Text input and IME composition: committed text, editing updates,\n"
        "#: candidate lists, the input rectangle and the screen keyboard."),
    "cursor": (
        r"cna_mouse_cursor_\w+ cna_mouse_set_cursor_ext",
        "Mouse cursors: stock cursors, cursors built from a Texture2D, and the\n"
        "#: one that is currently active."),
    "joystick": (
        r"cna_joystick_\w+ cna_joysticks_\w+",
        "Raw joysticks: enumeration, capabilities, axis/ball/button/hat state,\n"
        "#: and connect/disconnect events."),
    "haptics": (
        r"cna_haptic_\w+ cna_haptics_\w+",
        "Haptic devices: capabilities, rumble, and the full effect model."),
    "device_enumeration": (
        r"cna_input_device_\w+ cna_input_devices_\w+",
        "Keyboard, mouse and touch device enumeration, and their hotplug events."),
    "gamepad_sensors": (
        r"cna_sensor_info_\w+ cna_sensors_\w+ cna_gamepad_get_\w+ cna_power_get_info",
        "Sensors carried by an input device rather than by the host: a gamepad's\n"
        "#: accelerometer, gyro and power."),
}

#: Net, GamerServices and Avatar.  Unlike the two families above these back a
#: selected *strict* profile rather than a CNA-only extension: the public names
#: are ``Microsoft.Xna.Framework.Net`` and ``Microsoft.Xna.Framework.GamerServices``.
ONLINE_GROUPS: dict[str, tuple[str, str]] = {
    "packets": (
        r"cna_packet_reader_\w+ cna_packet_writer_\w+",
        "PacketReader and PacketWriter: the typed two sides of a network packet."),
    "session_properties": (
        r"cna_network_session_properties_\w+ cna_network_session_property_enumerator_\w+",
        "NetworkSessionProperties: the searchable property list a session\n"
        "#: advertises, and its enumerator."),
    "quality_of_service": (
        r"cna_quality_of_service_\w+ cna_net_get_\w+",
        "QualityOfService, and the last join failure the network layer recorded."),
    "session": (
        r"cna_network_session_(?!properties_|property_|ended_event_)\w+ "
        r"cna_available_network_session_\w+",
        "NetworkSession and AvailableNetworkSession: creation, discovery, join,\n"
        "#: rosters, state and events."),
    "gamers": (
        r"cna_network_gamer_\w+ cna_local_network_gamer_\w+ cna_network_machine_\w+",
        "NetworkGamer, LocalNetworkGamer and NetworkMachine."),
    "events": (
        r"cna_game_ended_event_\w+ cna_game_started_event_\w+ cna_gamer_joined_event_\w+ "
        r"cna_gamer_left_event_\w+ cna_host_changed_event_\w+ "
        r"cna_network_session_ended_event_\w+ cna_write_leaderboards_event_\w+ "
        r"cna_invite_accepted_event_\w+",
        "The event payloads a session raises."),
    "gamer": (
        r"cna_gamer_begin_\w+ cna_gamer_collection_\w+ cna_gamer_copy_\w+ cna_gamer_destroy "
        r"cna_gamer_enumerator_\w+ cna_gamer_get_\w+ cna_gamer_presence_\w+ "
        r"cna_gamer_set_\w+ cna_gamer_signed_in_\w+ cna_gamer_unsubscribe_\w+ "
        r"cna_gamer_profile_\w+ cna_signed_in_gamer_\w+ cna_friend_gamer_\w+ "
        r"cna_friend_collection_\w+ cna_game_defaults_\w+",
        "Gamer, SignedInGamer, GamerProfile, friends and the game defaults."),
    "guide": (
        r"cna_guide_\w+ cna_gamer_services_\w+",
        "Guide, and the GamerServices component and dispatcher."),
    "achievements": (
        r"cna_achievement_\w+ cna_leaderboard_\w+ cna_property_dictionary_\w+ "
        r"cna_write_leaderboards_\w+",
        "Achievements, leaderboards and the typed property dictionary they use."),
    "avatar": (
        r"cna_avatar_\w+",
        "AvatarDescription, AvatarAnimation, AvatarRenderer and their values."),
}

#: Which routes each family's manifest carries, and what the group is.  A group
#: lands when its Python consumer does.
GROUPS: dict[str, dict[str, tuple[str, str]]] = {
    "devices": DEVICES_GROUPS,
    "input": INPUT_GROUPS,
    "online": ONLINE_GROUPS,
}

#: Which of a family's groups are imported today. A group is claimed by a rule
#: as soon as the family is opened -- that is what makes its routes a task
#: rather than a decision -- but it is *imported* only when its Python consumer
#: exists. An imported route with no caller is dead native surface, and
#: ``tools/verify_route_reachability.py`` fails on one.
LANDED: dict[str, tuple[str, ...]] = {}

def refused_routes() -> dict[str, str]:
    """Every route the census already decided may not be imported.

    A rule carrying ``boundIsError`` says binding that route is a defect, not a
    task: a value-structure initialiser Python does not need, a CLR type name
    Python does not have. Reading them from the census means the manifest and
    the census cannot disagree about which routes are refused, and a decision
    changed in one place changes in both.
    """
    import json

    rules = json.loads((ROOT / "tools/route-census-rules.json").read_text())["rules"]
    refused: dict[str, str] = {}
    for rule in rules:
        if not rule.get("boundIsError"):
            continue
        for key in ("names", "prefixes", "suffixes", "contains"):
            for value in rule["match"].get(key, ()):
                refused[f"{key}:{value}"] = rule["reason"]
    return refused


#: Routes a family's manifest does not carry for a reason of its own, rather
#: than because the census refuses them outright. Each is a decision with a
#: written reason, and the census still classifies the route -- as
#: DELIBERATE_NON_BINDING for the disposed flags, and as already BOUND for the
#: three dispatcher routes the strict runtime profile imports.
FAMILY_EXCLUSIONS: dict[str, dict[str, str]] = {
    "online": {
        r"cna_\w+_get_is_disposed":
            "disposal is tracked deterministically by the Python ownership model, "
            "which is authoritative earlier than CNA's flag and stays correct "
            "after the handle is released",
        r"cna_gamer_services_dispatcher_(initialize|set_window_handle|update)":
            "already imported by the strict Windows runtime profile for "
            "GamerServicesComponent; one route is bound once",
        r"cna_gamer_services_component_create":
            "CNA's canonical component pumps the dispatcher from the runtime "
            "side. This projection's GamerServicesComponent is a strict XNA "
            "GameComponent whose Initialize and Update are Python's, already "
            "green in the Windows runtime profile; creating a second native "
            "component beside it would pump the dispatcher twice",
    },
}


def _is_refused(name: str, refused: dict[str, str]) -> str | None:
    for key, reason in refused.items():
        kind, _, value = key.partition(":")
        if ((kind == "names" and name == value)
                or (kind == "prefixes" and name.startswith(value))
                or (kind == "suffixes" and name.endswith(value))
                or (kind == "contains" and value in name)):
            return reason
    return None


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cna-root", required=True)
    parser.add_argument("--family", action="append", choices=sorted(GROUPS))
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    include = Path(args.cna_root).resolve() / "modules/c-api/include"
    selected = args.family or sorted(GROUPS)
    stale = written = 0
    for identifier in selected:
        family = families.FAMILIES_BY_ID[identifier]
        content = render(family, include, GROUPS[identifier],
                         LANDED.get(identifier, tuple(GROUPS[identifier])))
        path = SRC / f"{identifier}_manifest.py"
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == content:
            continue
        if args.check:
            print(f"STALE {path.relative_to(ROOT)}")
            stale += 1
            continue
        path.write_text(content, encoding="utf-8")
        written += 1
    print(f"MANIFEST_FAMILIES={len(selected)}")
    print(f"MANIFEST_GENERATED={written}")
    print(f"MANIFEST_STALE={stale}")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
