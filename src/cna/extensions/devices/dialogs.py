"""Host UI: file dialogs, message boxes and the system tray.

**Nothing in this module opens a real window during qualification.** Every one
of these three families has a CNA test backend, and
:mod:`cna.extensions.devices.testing` installs it; with the test backend
installed the same public calls below answer deterministically and put nothing
on anyone's desktop. Calling them without it shows real host UI, which is what a
shipping game wants and what an automated run must not do.

The file dialog is genuinely asynchronous: the show call returns once the
request is made, and the handler runs whenever the platform answers -- which may
be long afterwards, or never. Cancellation is an empty result rather than a
separate signal, which is the canonical shape and is preserved here.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from typing import Callable, Sequence, TYPE_CHECKING

from _cna_native import devices_abi as _devices
from _cna_native import devices_support as _dev
from _cna_native.family_support import CallbackRoot, checked, string_view

from .values import MessageBoxType

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "pending_dialog_count",
    "FileDialogFilter",
    "MessageBoxTestLog",
    "SystemTray",
    "are_file_dialogs_supported",
    "is_message_box_supported",
    "is_system_tray_supported",
    "show_open_file_dialog",
    "show_open_folder_dialog",
    "show_save_file_dialog",
    "show_message_box",
    "show_simple_message_box",
]

_support = _dev.support
_VERSION = 1

#: Trampolines for pending dialog answers, rooted until the answer arrives.
#:
#: A file dialog's handler may be called long after the call that showed it
#: returned, so the trampoline cannot live on the stack. It is held here and
#: released the moment the handler runs -- exactly once, which is what the
#: canonical contract promises and what the qualification asserts.
_pending = CallbackRoot()


@dataclass(frozen=True, slots=True)
class FileDialogFilter:
    """One file-type filter: a human-readable name and a platform pattern."""

    name: str
    pattern: str


@dataclass(frozen=True, slots=True)
class MessageBoxTestLog:
    """What the installed message-box test backend has been asked to do."""

    simple_calls: int
    choice_calls: int
    last_type: MessageBoxType
    last_button_count: int


def are_file_dialogs_supported(game: "Game") -> bool:
    """Whether this platform can show file dialogs, asked of CNA."""
    return _support.out_bool("cna_file_dialog_get_is_supported_ext",
                             _dev.game_handle(game, "file dialogs"))


def is_message_box_supported(game: "Game") -> bool:
    """Whether this platform can show message boxes, asked of CNA."""
    return _support.out_bool("cna_message_box_get_is_supported_ext",
                             _dev.game_handle(game, "message box"))


def is_system_tray_supported(game: "Game") -> bool:
    """Whether this platform has a system tray, asked of CNA."""
    return _support.out_bool("cna_system_tray_get_is_supported_ext",
                             _dev.game_handle(game, "system tray"))


def _filters(filters: Sequence[FileDialogFilter] | None):
    """Builds the borrowed filter array, keeping every encoded string alive."""
    filters = tuple(filters or ())
    if not filters:
        return None, 0, []
    keep: list[bytes] = []
    array = (_devices.CNA_FileDialogFilter * len(filters))()
    for index, entry in enumerate(filters):
        if not isinstance(entry, FileDialogFilter):
            raise TypeError(
                f"filters[{index}] must be a FileDialogFilter, "
                f"not {type(entry).__name__}")
        item = array[index]
        item.struct_size = c.sizeof(_devices.CNA_FileDialogFilter)
        item.struct_version = _VERSION
        name_view, name_bytes = string_view(entry.name, "filter name")
        pattern_view, pattern_bytes = string_view(entry.pattern, "filter pattern")
        item.name = name_view
        item.pattern = pattern_view
        keep.extend((name_bytes, pattern_bytes))
    return array, len(filters), keep


def _dialog(route: str, game: "Game", on_result: Callable[[list[str]], None],
            *arguments: object) -> None:
    if not callable(on_result):
        raise TypeError("on_result must be callable")
    key = object()

    def adapt(files, count, _context) -> None:
        try:
            chosen = [bytes(files[index].data[: files[index].byte_length]).decode("utf-8")
                      for index in range(int(count))] if count else []
            on_result(chosen)
        finally:
            # Exactly once: the trampoline is dropped as the answer is delivered,
            # so a backend that called twice would fail to find it the second
            # time rather than delivering a second answer.
            _pending.release(key)

    trampoline = _pending.root(key, _devices.CNA_FileDialogResultCallback, adapt)
    try:
        _support.call(route, _dev.game_handle(game, "file dialog"),
                      trampoline, None, *arguments)
    except BaseException:
        _pending.release(key)
        raise


def show_open_file_dialog(game: "Game", on_result: Callable[[list[str]], None], *,
                          filters: Sequence[FileDialogFilter] | None = None,
                          default_location: str = "",
                          allow_multiple: bool = False) -> None:
    """Asks the host for files to open; ``on_result`` receives the chosen paths.

    An empty list means the dialog was cancelled.
    """
    array, count, _keep = _filters(filters)
    location, _location_bytes = string_view(default_location, "default_location")
    _dialog("cna_file_dialog_show_open_file_ext", game, on_result,
            array, c.c_uint64(count), location, c.c_uint8(1 if allow_multiple else 0))


def show_save_file_dialog(game: "Game", on_result: Callable[[list[str]], None], *,
                          filters: Sequence[FileDialogFilter] | None = None,
                          default_location: str = "") -> None:
    """Asks the host where to save a file."""
    array, count, _keep = _filters(filters)
    location, _location_bytes = string_view(default_location, "default_location")
    _dialog("cna_file_dialog_show_save_file_ext", game, on_result,
            array, c.c_uint64(count), location)


def show_open_folder_dialog(game: "Game", on_result: Callable[[list[str]], None], *,
                            default_location: str = "",
                            allow_multiple: bool = False) -> None:
    """Asks the host for folders. Folder dialogs take no filters, in CNA and here."""
    location, _location_bytes = string_view(default_location, "default_location")
    _dialog("cna_file_dialog_show_open_folder_ext", game, on_result,
            location, c.c_uint8(1 if allow_multiple else 0))


def pending_dialog_count() -> int:
    """How many dialog answers are still outstanding.

    Every rooted trampoline is one dialog that has been shown and not yet
    answered. Zero after a run is what proves no answer was left dangling.
    """
    return len(_pending)


def show_message_box(game: "Game", kind: MessageBoxType, title: str, message: str,
                     buttons: Sequence[str]) -> int:
    """Shows a message box with buttons and returns the index of the one chosen."""
    if not buttons:
        raise ValueError("a message box with buttons needs at least one")
    keep: list[bytes] = []
    array = (_devices.abi.CNA_StringView * len(buttons))()
    for index, label in enumerate(buttons):
        view, encoded = string_view(label, f"buttons[{index}]")
        array[index] = view
        keep.append(encoded)
    title_view, _title_bytes = string_view(title, "title")
    message_view, _message_bytes = string_view(message, "message")
    return _support.out_i32(
        "cna_message_box_show_ext", _dev.game_handle(game, "message box"),
        c.c_uint32(MessageBoxType(kind)), title_view, message_view,
        array, c.c_uint64(len(buttons)))


def show_simple_message_box(game: "Game", kind: MessageBoxType, title: str,
                            message: str) -> None:
    """Shows a message box with the platform's own single acknowledgement."""
    title_view, _title_bytes = string_view(title, "title")
    message_view, _message_bytes = string_view(message, "message")
    _support.call("cna_message_box_show_simple_ext",
                  _dev.game_handle(game, "message box"),
                  c.c_uint32(MessageBoxType(kind)), title_view, message_view)


class SystemTray:
    """A tray icon and its entries.

    Constructing this creates a **real** tray icon. Use
    :func:`~cna.extensions.devices.testing.open_test_system_tray` for
    qualification.
    """

    __slots__ = ("_handle", "_callbacks", "_entries")

    def __init__(self, game: "Game", tooltip: str = "") -> None:
        view, _keep = string_view(tooltip, "tooltip")
        handle = _support.out_handle("cna_system_tray_create",
                                     _dev.game_handle(game, "system tray"), view)
        self._adopt(handle)

    def _adopt(self, handle: int) -> None:
        self._handle = _support.handle(handle, "cna_system_tray_destroy",
                                       "system tray")
        self._callbacks = CallbackRoot()
        self._entries = 0

    @classmethod
    def _over(cls, handle: int) -> "SystemTray":
        tray = cls.__new__(cls)
        tray._adopt(handle)
        return tray

    def add_entry(self, label: str, on_click: Callable[[], None], *,
                  checkable: bool = False, initially_checked: bool = False,
                  initially_enabled: bool = True) -> int:
        """Adds one entry and returns its index.

        The click handler is rooted for as long as the tray lives and released
        when it closes, so no click can arrive after the tray is gone.
        """
        if not callable(on_click):
            raise TypeError("on_click must be callable")
        view, _keep = string_view(label, "label")
        index = len(self._callbacks)

        def adapt(_context) -> None:
            on_click()

        trampoline = self._callbacks.root(
            index, _devices.CNA_TrayEntryClickCallback, adapt)
        written = _support.out_u64(
            "cna_system_tray_add_entry", self._handle.argument, view,
            c.c_uint8(1 if checkable else 0),
            c.c_uint8(1 if initially_checked else 0),
            c.c_uint8(1 if initially_enabled else 0), trampoline, None)
        self._entries = max(self._entries, int(written) + 1)
        return int(written)

    def set_tooltip(self, tooltip: str) -> None:
        view, _keep = string_view(tooltip, "tooltip")
        _support.call("cna_system_tray_set_tooltip", self._handle.argument, view)

    def set_entry_label(self, index: int, label: str) -> None:
        view, _keep = string_view(label, "label")
        _support.call("cna_system_tray_set_entry_label", self._handle.argument,
                      c.c_uint64(checked(index, "uint64", "index")), view)

    def entry_checked(self, index: int) -> bool:
        return _support.out_bool("cna_system_tray_get_entry_checked",
                                 self._handle.argument,
                                 c.c_uint64(checked(index, "uint64", "index")))

    def set_entry_checked(self, index: int, checked_state: bool) -> None:
        _support.call("cna_system_tray_set_entry_checked", self._handle.argument,
                      c.c_uint64(checked(index, "uint64", "index")),
                      c.c_uint8(1 if checked_state else 0))

    def entry_enabled(self, index: int) -> bool:
        return _support.out_bool("cna_system_tray_get_entry_enabled",
                                 self._handle.argument,
                                 c.c_uint64(checked(index, "uint64", "index")))

    def set_entry_enabled(self, index: int, enabled: bool) -> None:
        _support.call("cna_system_tray_set_entry_enabled", self._handle.argument,
                      c.c_uint64(checked(index, "uint64", "index")),
                      c.c_uint8(1 if enabled else 0))

    @property
    def callback_failures(self) -> list:
        """``(handler, exception)`` for every click handler that raised."""
        return list(self._callbacks.failures)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        if self._handle.closed:
            return
        self._callbacks.clear()
        self._handle.close()

    def __enter__(self) -> "SystemTray":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()
