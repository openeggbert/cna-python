"""Owner-thread game context used by XNA's static input facades."""

from __future__ import annotations

from threading import local

_state = local()


def set_current_game(game: object | None) -> None:
    _state.game = game


def current_game() -> object:
    game = getattr(_state, "game", None)
    if game is None:
        raise RuntimeError("input polling requires an active CNA Game.Run owner thread")
    return game
