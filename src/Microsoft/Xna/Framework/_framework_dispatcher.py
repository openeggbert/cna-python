"""Public XNA framework dispatcher over the single CNA game dispatcher."""

from __future__ import annotations

from _cna_native.errors import NativeCapabilityError
from _cna_native.runtime_context import live_game


class FrameworkDispatcher:
    def __new__(cls, *args: object, **kwargs: object):
        raise TypeError("FrameworkDispatcher is static")

    @staticmethod
    def Update() -> None:
        try:
            game = live_game("FrameworkDispatcher.Update")
        except RuntimeError as error:
            raise NativeCapabilityError(
                "FrameworkDispatcher.Update", 6, None,
                "CNA's dispatcher route takes a Game handle, so it has nothing to pump without one, "
                "although XNA permits a process-level update",
            ) from error
        host = game._host
        if host is None or host.handle == 0:
            raise NativeCapabilityError(
                "FrameworkDispatcher.Update", 6, None,
                "the current CNA Game generation is no longer valid",
            )
        result = host.library.cna_framework_dispatcher_update(host.handle)
        try:
            from .Media._player import _update_media_game
            _update_media_game(game)
            host._drain_dispatch_callbacks()
        except BaseException as error:
            if host.pending_exception is None:
                host.pending_exception = error
        host._finish_call(result, "cna_framework_dispatcher_update")
