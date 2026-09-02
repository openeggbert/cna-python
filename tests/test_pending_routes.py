"""A canonical route CNA has declared and no artifact ships yet.

A missing symbol is fatal, and must stay fatal: it is what catches an artifact
that has drifted from the headers this binding was generated against. But CNA's
headers declare 4,055 routes and every artifact measured here exports 4,054 --
``cna_network_session_replace_session_properties`` is declared and not yet
built -- and refusing the library over one route would make the other 4,054
unusable.

So the loader carries a short, declared list. A route on it binds to a stub that
raises when it is *called*; every other missing symbol still refuses the library.
These check both halves, and that the list cannot become a place to hide a typo.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from _cna_native.errors import NativeLibraryError, NativeUnavailableError
from _cna_native.loader import PENDING_ROUTES, FUNCTION_MANIFEST, _PendingRoute

from .device_fixtures import NATIVE

ROOT = Path(__file__).resolve().parents[1]


class DeclarationTests(unittest.TestCase):
    """What the list may hold, checked without loading anything."""

    def test_every_pending_route_is_one_this_binding_imports(self) -> None:
        bound = {entry[0] for entry in FUNCTION_MANIFEST}
        for symbol in PENDING_ROUTES:
            self.assertIn(symbol, bound,
                          "a route nothing imports cannot be pending")

    def test_every_pending_route_carries_a_written_reason(self) -> None:
        for symbol, reason in PENDING_ROUTES.items():
            self.assertGreater(len(reason.strip()), 80, symbol)
            self.assertIn("docs/", reason,
                          "the reason points at where the finding is written up")

    def test_the_list_is_short_enough_to_read(self) -> None:
        """A long list would mean the artifact had drifted, not that CNA had."""
        self.assertLessEqual(len(PENDING_ROUTES), 4)


class StubTests(unittest.TestCase):
    """What a pending route does when it is called."""

    def test_calling_one_names_the_route_the_artifact_and_the_reason(self) -> None:
        stub = _PendingRoute("cna_example_route", Path("/tmp/libcna.so"),
                             "declared and not yet built")
        with self.assertRaises(NativeUnavailableError) as raised:
            stub(1, 2, 3)
        message = str(raised.exception)
        self.assertIn("cna_example_route", message)
        self.assertIn("/tmp/libcna.so", message)
        self.assertIn("declared and not yet built", message)


@unittest.skipUnless(NATIVE, "needs a configured CNA library")
class LoadedLibraryTests(unittest.TestCase):
    """The artifact this run actually loaded."""

    def test_the_library_reports_which_declared_routes_it_lacks(self) -> None:
        from _cna_native.loader import get_library

        library = get_library()
        self.assertEqual(set(library.pending_routes) - set(PENDING_ROUTES), set(),
                         "an artifact may only be missing a declared route")

    def test_a_pending_route_the_artifact_lacks_raises_when_called(self) -> None:
        from _cna_native.loader import get_library

        library = get_library()
        for symbol in library.pending_routes:
            with self.subTest(route=symbol):
                with self.assertRaises(NativeUnavailableError):
                    getattr(library, symbol)()

    def test_a_route_the_artifact_does_export_is_a_real_function(self) -> None:
        from _cna_native.loader import get_library

        library = get_library()
        self.assertNotIsInstance(
            getattr(library, "cna_get_abi_version"), _PendingRoute)


class FatalityTests(unittest.TestCase):
    """A missing symbol that is *not* declared pending still refuses the library.

    Checked by loading a library that is missing one: the C standard library is
    a real shared object with none of CNA's symbols, so it is the smallest
    honest way to ask.
    """

    def test_an_undeclared_missing_symbol_refuses_the_library(self) -> None:
        import ctypes.util

        from _cna_native.loader import NativeLibrary

        path = ctypes.util.find_library("m") or "libm.so.6"
        with self.assertRaises(NativeLibraryError) as raised:
            NativeLibrary(Path(path))
        self.assertIn("cna_get_abi_version", str(raised.exception),
                      "a library with none of CNA's symbols fails at the first")

    def test_the_pending_list_does_not_cover_the_version_route(self) -> None:
        """The one route that is read before anything else is never optional."""
        self.assertNotIn("cna_get_abi_version", PENDING_ROUTES)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
