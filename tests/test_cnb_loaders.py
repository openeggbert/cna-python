"""Running a Python `.cnb` loader, through CNA, on a live native content manager.

Invoking a loader is the one part of this family that needs a running ``Game``.
CNA's loader signature takes a content manager by reference -- there is no "no
manager" to pass, which is measured here rather than assumed -- and a native
content manager needs a ``GraphicsDevice``, which needs an active ``Game.Run``
owner thread. So everything in this module runs inside one frame of a real game.

That native content manager is a **separate cache domain** from
``Microsoft.Xna.Framework.Content.ContentManager``. The last class here asserts
the separation rather than describing it: the strict manager is used in the same
frame, and neither one sees the other's asset.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import unittest

from Microsoft.Xna.Framework import Game, GraphicsDeviceManager
from _cna_native.errors import NativeUnavailableError
from _cna_native.runtime_identity import runtime_identity

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb


def _native_available() -> bool:
    if not HAS_NATIVE:
        return False
    try:
        runtime_identity()
    except NativeUnavailableError:
        return False
    except Exception:  # pragma: no cover - a configured library that fails to load
        return False
    return True


AVAILABLE = _native_available()


class _InOneFrame(unittest.TestCase):
    """Runs a body inside one frame of a real ``Game``, and reports what it saw."""

    def run_in_game(self, body) -> dict:
        observed: dict[str, object] = {}
        failures: list[BaseException] = []

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
                    body(self.GraphicsDevice, observed)
                except BaseException as error:  # noqa: BLE001 - reported below
                    failures.append(error)
                finally:
                    self.Exit()

            def Update(self, gameTime) -> None:
                if self.done:
                    self.Exit()

        game = Probe()
        try:
            game.Run()
        finally:
            game.Dispose()
        self.assertTrue(game.done, "Draw never ran, so nothing was measured")
        if failures:
            raise failures[0]
        return observed


@unittest.skipUnless(AVAILABLE, "CNA_NATIVE_LIBRARY is not configured")
class NativeContentManagerTests(_InOneFrame):
    def test_a_manager_opens_against_a_live_device_and_closes_cleanly(self) -> None:
        def body(device, observed):
            with cnb.NativeContentManager(device) as manager:
                observed["open"] = not manager.closed
                observed["repr"] = repr(manager)
            observed["closed_after"] = True

        observed = self.run_in_game(body)
        self.assertTrue(observed["open"])
        self.assertEqual(observed["repr"], "<NativeContentManager open>")
        self.assertTrue(observed["closed_after"])

    def test_a_manager_needs_a_live_device(self) -> None:
        with self.assertRaises(ValueError):
            cnb.NativeContentManager(None)
        with self.assertRaises(ValueError):
            cnb.NativeContentManager(object())

    def test_a_root_directory_is_accepted_and_is_not_a_machine_path_leak(self) -> None:
        def body(device, observed):
            with cnb.NativeContentManager(device, root_directory="Content") as manager:
                observed["open"] = not manager.closed

        self.assertTrue(self.run_in_game(body)["open"])


@unittest.skipUnless(AVAILABLE, "CNA_NATIVE_LIBRARY is not configured")
class PythonLoaderInvocationTests(_InOneFrame):
    TYPE_NAME = "CnaPythonTests.Level"

    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(cnb.clear_loader_registry)
        cnb.clear_loader_registry()

    def _document(self, payload: bytes = b"\x2a\x00\x00\x00") -> bytes:
        identifier = cnb.asset_type_id_from_name(self.TYPE_NAME)
        with cnb.CnbWriter(identifier, 1) as writer:
            writer.set_metadata(self.TYPE_NAME, "levels/one")
            writer.add_chunk(cnb.chunk_id("lvlh"), payload)
            return writer.build()

    def test_a_python_loader_runs_and_its_object_comes_back(self) -> None:
        """The whole chain: register, resolve, invoke, receive the real object.

        The object CNA carries is a token, never a Python address; what comes
        back here is the very object the loader returned, identity included.
        """
        image = self._document(struct.pack("<I", 42))
        marker = {"level": 42}
        seen: list[tuple[str, int]] = []

        def loader(document, asset_name):
            index = document.require_single(cnb.chunk_id("lvlh"))
            with document.open_chunk(index) as reader:
                seen.append((asset_name, reader.read_u32()))
            return marker

        def body(device, observed):
            with cnb.register_loader(self.TYPE_NAME, loader) as registration:
                with cnb.NativeContentManager(device) as manager:
                    with cnb.CnbDocument.parse(image, origin="level.cnb") as document:
                        observed["object"] = registration.load(
                            document, manager, asset_name="levels/one")

        observed = self.run_in_game(body)
        self.assertIs(observed["object"], marker,
                      "the very object the loader returned, not a copy")
        self.assertEqual(seen, [("levels/one", 42)],
                         "the loader saw its asset name and its own chunk")

    def test_the_document_the_loader_receives_is_real_and_callback_scoped(self) -> None:
        image = self._document()
        captured: list[object] = []

        def loader(document, asset_name):
            captured.append(document)
            return {
                "asset_type_id": document.asset_type_id,
                "metadata": document.metadata.asset_type_name,
                "chunks": [chunk.type_text for chunk in document.chunks],
            }

        def body(device, observed):
            with cnb.register_loader(self.TYPE_NAME, loader) as registration:
                with cnb.NativeContentManager(device) as manager:
                    with cnb.CnbDocument.parse(image) as document:
                        observed["result"] = registration.load(document, manager)

        result = self.run_in_game(body)["result"]
        self.assertEqual(result["asset_type_id"],
                         cnb.asset_type_id_from_name(self.TYPE_NAME))
        self.assertEqual(result["metadata"], self.TYPE_NAME)
        self.assertEqual(result["chunks"], ["CMET", "lvlh"])
        # CNA invalidates the borrow before the callback returns, so the wrapper
        # gave the handle up rather than keeping something that is now dangling.
        self.assertTrue(captured[0].closed)

    def test_an_exception_inside_the_loader_reaches_the_caller_intact(self) -> None:
        """No Python exception may unwind through a C frame.

        It is captured, turned into a failed load in CNA's own vocabulary, and
        re-raised on this side after CNA has returned through its own frames --
        as the original exception, not as a CNA result code.
        """
        image = self._document()

        def loader(document, asset_name):
            raise KeyError("the game's own loader bug")

        def body(device, observed):
            with cnb.register_loader(self.TYPE_NAME, loader) as registration:
                with cnb.NativeContentManager(device) as manager:
                    with cnb.CnbDocument.parse(image) as document:
                        try:
                            registration.load(document, manager)
                        except BaseException as error:  # noqa: BLE001 - recorded
                            observed["error"] = error
                        # The process is still usable afterwards, which it would
                        # not be after an unwind through native frames.
                        observed["still_alive"] = document.chunk_count

        observed = self.run_in_game(body)
        self.assertIsInstance(observed["error"], KeyError)
        self.assertIn("the game's own loader bug", str(observed["error"]))
        self.assertEqual(observed["still_alive"], 2)

    def test_a_builtin_loader_refuses_to_hand_its_object_across_the_boundary(self) -> None:
        """CNA's own loaders build C++ objects, and this says so.

        Only a loader registered from Python produces something Python can hold.
        Reporting that as unsupported is the honest answer; handing back a
        pointer nothing here could name would not be.
        """
        from Microsoft.Xna.Framework import Curve, CurveKey

        curve = Curve()
        curve.Keys.Add(CurveKey(0.0, 1.0))
        image = cnb.encode_curve(curve, content_name="curves/one")

        def body(device, observed):
            cnb.register_builtin_loaders()
            with cnb.NativeContentManager(device) as manager:
                with cnb.CnbDocument.parse(image) as document:
                    with cnb.resolve_loader(document) as loader:
                        try:
                            loader.invoke(document, manager, asset_name="curves/one")
                            observed["error"] = None
                        except cnb.CnbError as error:
                            observed["error"] = error

        error = self.run_in_game(body)["error"]
        self.assertIsInstance(error, cnb.CnbUnsupportedError)

    def test_a_loader_found_by_number_invokes_the_same_way(self) -> None:
        # find_loader performs no type-name check, so it is the wrong entry point
        # for loading a file -- but the loader it returns is a real one.
        image = self._document()
        marker = object()

        def body(device, observed):
            with cnb.register_loader(self.TYPE_NAME, lambda d, n: marker):
                identifier = cnb.asset_type_id_from_name(self.TYPE_NAME)
                with cnb.NativeContentManager(device) as manager:
                    with cnb.CnbDocument.parse(image) as document:
                        found = cnb.find_loader(identifier)
                        self.assertIsNotNone(found)
                        with found as loader:
                            observed["object"] = loader.invoke(document, manager)

        self.assertIs(self.run_in_game(body)["object"], marker)

    def test_a_loader_survives_a_registration_that_rehashes_the_table(self) -> None:
        # CNA hands the loader back by value on purpose: a pointer into the table
        # would be invalidated by a later registration, and nothing would say so.
        image = self._document()
        marker = object()

        def body(device, observed):
            with cnb.register_loader(self.TYPE_NAME, lambda d, n: marker):
                with cnb.NativeContentManager(device) as manager:
                    with cnb.CnbDocument.parse(image) as document:
                        with cnb.resolve_loader(document) as loader:
                            # Twenty more registrations between resolve and invoke.
                            extra = [cnb.register_loader(f"Filler.Type{index}",
                                                         lambda d, n: None)
                                     for index in range(20)]
                            try:
                                observed["object"] = loader.invoke(document, manager)
                            finally:
                                for registration in extra:
                                    registration.close()

        self.assertIs(self.run_in_game(body)["object"], marker)

    def test_two_loaders_stay_apart(self) -> None:
        first_name, second_name = "CnaPythonTests.Alpha", "CnaPythonTests.Beta"

        def image_for(name: str) -> bytes:
            with cnb.CnbWriter(cnb.asset_type_id_from_name(name), 1) as writer:
                writer.set_metadata(name, name)
                writer.add_chunk(cnb.chunk_id("data"), b"\x01")
                return writer.build()

        def body(device, observed):
            with cnb.register_loader(first_name, lambda d, n: "alpha") as alpha:
                with cnb.register_loader(second_name, lambda d, n: "beta") as beta:
                    with cnb.NativeContentManager(device) as manager:
                        with cnb.CnbDocument.parse(image_for(first_name)) as document:
                            observed["alpha"] = alpha.load(document, manager)
                        with cnb.CnbDocument.parse(image_for(second_name)) as document:
                            observed["beta"] = beta.load(document, manager)

        observed = self.run_in_game(body)
        self.assertEqual(observed["alpha"], "alpha")
        self.assertEqual(observed["beta"], "beta")


@unittest.skipUnless(AVAILABLE, "CNA_NATIVE_LIBRARY is not configured")
class CacheDomainSeparationTests(_InOneFrame):
    """The two content managers do not share anything, asserted rather than said."""

    TYPE_NAME = "CnaPythonTests.Level"

    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(cnb.clear_loader_registry)
        cnb.clear_loader_registry()

    def test_the_strict_manager_never_learns_about_a_cnb_asset(self) -> None:
        import tempfile

        from Microsoft.Xna.Framework.Content import ContentLoadException, ContentManager
        from Microsoft.Xna.Framework._title import _set_title_root_for_tests

        identifier = cnb.asset_type_id_from_name(self.TYPE_NAME)
        with cnb.CnbWriter(identifier, 1) as writer:
            writer.set_metadata(self.TYPE_NAME, "levels/one")
            writer.add_chunk(cnb.chunk_id("lvlh"), struct.pack("<I", 7))
            image = writer.build()

        directory = tempfile.TemporaryDirectory(prefix="cnb-domain-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "Content").mkdir()
        # A .cnb sitting exactly where the strict manager looks for a .xnb.
        (root / "Content" / "levels" ).mkdir()
        (root / "Content" / "levels" / "one.cnb").write_bytes(image)

        def body(device, observed):
            _set_title_root_for_tests(root)
            self.addCleanup(_set_title_root_for_tests, None)
            with cnb.register_loader(self.TYPE_NAME, lambda d, n: {"level": 7}) as reg:
                with cnb.NativeContentManager(device) as manager:
                    with cnb.CnbDocument.parse(image) as document:
                        observed["through_extension"] = reg.load(document, manager)
                # The strict manager reads .xnb and only .xnb: a .cnb next to it
                # is not a fallback, and the failure names a missing .xnb.
                strict = ContentManager(object(), "Content")
                try:
                    strict.Load("levels/one")
                    observed["strict"] = "loaded"
                except (ContentLoadException, Exception) as error:
                    observed["strict"] = type(error).__name__
                finally:
                    strict.Unload()

        observed = self.run_in_game(body)
        self.assertEqual(observed["through_extension"], {"level": 7})
        self.assertNotEqual(observed["strict"], "loaded",
                            "the strict ContentManager must not read a .cnb")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
