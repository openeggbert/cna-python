"""Shared harness for the engine-layer tests.

Two facts decide what an engine test can prove, and they are different
questions, so both are measured rather than one standing in for the other:

``ENGINE_PRESENT``
    the loaded CNA build contains an engine layer at all. A build configured
    without one still exports every engine symbol, so this is read from
    ``cna_engine_layer_get_version`` and never from the symbol table.
``RENDERS``
    the active renderer executes a real graphics pipeline, so a draw can be
    asked what colour it produced.

The control artifact answers ``False`` to the first. That is not a gap in the
tests: it is the case the public API has to report accurately, and
:class:`EngineAbsenceTests` asserts it does.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Game, GraphicsDeviceManager
from _cna_native.errors import NativeUnavailableError
from _cna_native.runtime_identity import runtime_identity


def _identity():
    try:
        return runtime_identity()
    except NativeUnavailableError:
        return None
    except Exception:  # pragma: no cover - a configured library that fails to load
        return None


IDENTITY = _identity()
NATIVE = IDENTITY is not None
RENDERS = bool(IDENTITY and IDENTITY.renders)


def _engine_present() -> bool:
    if not NATIVE:
        return False
    from cna.extensions import engine

    try:
        return engine.is_available()
    except Exception:  # pragma: no cover - defensive
        return False


ENGINE_PRESENT = _engine_present()

#: An engine test that needs a live GPU object needs both facts to hold.
ENGINE_GPU = ENGINE_PRESENT and RENDERS

requires_native = unittest.skipUnless(NATIVE, "needs a configured CNA library")
requires_engine = unittest.skipUnless(
    ENGINE_PRESENT, "the loaded CNA build has no engine layer")
requires_engine_gpu = unittest.skipUnless(
    ENGINE_GPU, "needs a CNA build with an engine layer on a rasterizing renderer")


def in_game(body):
    """Runs ``body(game, device, observed)`` once inside a real ``Draw``.

    Engine objects are graphics-thread affine and most need a live device, so
    the whole measurement happens inside one frame rather than around it. The
    dictionary ``body`` fills is returned; an exception inside ``Draw`` is
    re-raised here rather than being swallowed into a frame that merely did
    nothing.
    """
    observed: dict = {}
    failure: list[BaseException] = []

    class Probe(Game):
        def __init__(self) -> None:
            super().__init__()
            self.manager = GraphicsDeviceManager(self)
            self.done = False

        def Draw(self, gameTime) -> None:
            if self.done:
                return
            self.done = True
            try:
                body(self, self.GraphicsDevice, observed)
            except BaseException as error:  # re-raised outside the frame
                failure.append(error)
            self.Exit()

        def Update(self, gameTime) -> None:
            if self.done:
                self.Exit()

    game = Probe()
    try:
        game.Run()
    finally:
        game.Dispose()
    if failure:
        raise failure[0]
    if not game.done:
        raise AssertionError("Draw never ran")
    return observed


def over_frames(body, frames: int = 8):
    """Runs ``body(game, device, observed, frame)`` once per frame, ``frames`` times.

    Some engine state only advances across frames rather than inside one: a GPU
    timer query the chain opened in one frame is collected in a later one, so a
    measurement taken entirely inside a single ``Draw`` would see it as absent
    and conclude the feature does not work. ``frame`` counts from one.
    """
    observed: dict = {}
    failure: list[BaseException] = []

    class Probe(Game):
        def __init__(self) -> None:
            super().__init__()
            self.manager = GraphicsDeviceManager(self)
            self.frame = 0

        def Draw(self, gameTime) -> None:
            if failure or self.frame >= frames:
                self.Exit()
                return
            self.frame += 1
            try:
                body(self, self.GraphicsDevice, observed, self.frame)
            except BaseException as error:
                failure.append(error)
            if self.frame >= frames:
                self.Exit()

        def Update(self, gameTime) -> None:
            if failure:
                self.Exit()

    game = Probe()
    try:
        game.Run()
    finally:
        game.Dispose()
    if failure:
        raise failure[0]
    if game.frame < frames:
        raise AssertionError(f"only {game.frame} of {frames} frames ran")
    return observed
