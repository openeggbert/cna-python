"""Game-owned GamerServices dispatcher component."""

from __future__ import annotations

from _cna_native.loader import get_library

from .._game import GameTime
from .._game_objects import GameComponent


class GamerServicesComponent(GameComponent):
    def Initialize(self) -> None:
        if self._disposed:
            raise RuntimeError("GamerServicesComponent is disposed")
        host = self.Game._ensure_host()
        library = get_library()
        library.check(
            library.cna_gamer_services_dispatcher_set_window_handle(self.Game.Window.Handle),
            "cna_gamer_services_dispatcher_set_window_handle",
        )
        library.check(
            library.cna_gamer_services_dispatcher_initialize(host.handle),
            "cna_gamer_services_dispatcher_initialize",
        )
        super().Initialize()

    def Update(self, gameTime: GameTime) -> None:
        library = get_library()
        library.check(
            library.cna_gamer_services_dispatcher_update(),
            "cna_gamer_services_dispatcher_update",
        )
        super().Update(gameTime)
