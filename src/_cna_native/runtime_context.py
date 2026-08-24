"""Owner-thread game context used by XNA's static input facades."""

from __future__ import annotations

from threading import RLock, get_ident, local
import weakref

_state = local()
_lock = RLock()
_live_games: list[weakref.ReferenceType[object]] = []


def set_current_game(game: object | None) -> None:
    _state.game = game


def current_game() -> object:
    game = getattr(_state, "game", None)
    if game is None:
        raise RuntimeError("input polling requires an active CNA Game.Run owner thread")
    return game


def try_current_game() -> object | None:
    """Returns the owner-thread Game when one is active, otherwise ``None``."""
    return getattr(_state, "game", None)


def register_live_game(game: object) -> None:
    """Register one created CNA game without extending its Python lifetime."""
    with _lock:
        _live_games[:] = [reference for reference in _live_games
                          if reference() not in (None, game)]
        _live_games.append(weakref.ref(game))


def unregister_live_game(game: object) -> None:
    with _lock:
        _live_games[:] = [reference for reference in _live_games
                          if reference() not in (None, game)]


def live_game(operation: str) -> object:
    """Return the valid owner-thread runtime generation used by static facades."""
    current = try_current_game()
    if current is not None:
        return current
    with _lock:
        games = [reference() for reference in _live_games]
        games = [game for game in games
                 if game is not None and not getattr(game, "_disposed", True)
                 and getattr(getattr(game, "_host", None), "handle", 0)]
        _live_games[:] = [weakref.ref(game) for game in games]
    owned = [game for game in games
             if getattr(getattr(game, "_host", None), "owner_thread", None) == get_ident()]
    if not owned:
        raise RuntimeError(f"{operation} requires a live CNA Game on its owner thread")
    if len(owned) != 1:
        raise RuntimeError(f"{operation} cannot select between multiple live CNA Game generations")
    return owned[0]
