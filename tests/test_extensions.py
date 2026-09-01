"""The CNA extension profile and the gate that keeps it separate."""

from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from cna.extensions import graphics
from _cna_native.errors import NativeUnavailableError
import verify_extensions


def _native_available() -> bool:
    try:
        graphics.current_renderer()
    except NativeUnavailableError:
        return False
    except Exception:  # pragma: no cover - a configured library that fails to load
        return False
    return True


NATIVE = _native_available()


class ExtensionSeparationTests(unittest.TestCase):
    """The extension profile must not reach into, or be reached from, XNA."""

    def test_gate_is_green(self) -> None:
        summary = verify_extensions.audit()["summary"]
        self.assertEqual(summary["EXTENSION_SURFACE_DIAGNOSTICS"], 0)
        self.assertEqual(summary["XNA_NAMESPACE_CONTAMINATION"], 0)
        self.assertGreater(summary["PUBLIC_EXTENSION_NAMES"], 0)

    def test_gate_rejects_a_leaked_ctypes_type(self) -> None:
        graphics.LeakedCtypes = ctypes.c_uint32
        graphics.__all__.append("LeakedCtypes")
        try:
            summary = verify_extensions.audit()["summary"]
            self.assertEqual(summary["PUBLIC_CTYPES_LEAK"], 1)
            self.assertGreater(summary["EXTENSION_SURFACE_DIAGNOSTICS"], 0)
        finally:
            graphics.__all__.remove("LeakedCtypes")
            del graphics.LeakedCtypes

    def test_gate_rejects_a_leaked_private_native_type(self) -> None:
        from _cna_native.ownership import NativeResource

        graphics.LeakedNative = NativeResource
        graphics.__all__.append("LeakedNative")
        try:
            summary = verify_extensions.audit()["summary"]
            self.assertEqual(summary["PRIVATE_NATIVE_LEAK"], 1)
        finally:
            graphics.__all__.remove("LeakedNative")
            del graphics.LeakedNative

    def test_gate_rejects_an_undocumented_public_name(self) -> None:
        def undocumented_helper() -> None:
            pass

        undocumented_helper.__module__ = graphics.__name__
        graphics.undocumented_helper = undocumented_helper
        graphics.__all__.append("undocumented_helper")
        try:
            summary = verify_extensions.audit()["summary"]
            self.assertEqual(summary["UNDOCUMENTED_PUBLIC"], 1)
        finally:
            graphics.__all__.remove("undocumented_helper")
            del graphics.undocumented_helper

    def test_xna_namespace_never_imports_the_extension_profile(self) -> None:
        report = verify_extensions.audit()
        self.assertEqual(report["xnaContamination"], [])

    def test_importing_xna_does_not_import_the_extension_profile(self) -> None:
        import subprocess

        source = Path(__file__).resolve().parents[1] / "src"
        code = (
            "import sys; import Microsoft.Xna.Framework as f; "
            "print(any(name == 'cna' or name.startswith('cna.') for name in sys.modules))"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                cwd=str(source))
        self.assertEqual(result.stdout.strip(), "False", result.stderr)


@unittest.skipUnless(NATIVE, "no CNA native library is configured")
class RendererExtensionTests(unittest.TestCase):
    def test_identity_is_consistent_with_the_loaded_build(self) -> None:
        current = graphics.current_renderer()
        self.assertIn(current, graphics.available_renderers())
        self.assertTrue(graphics.is_renderer_available(current))
        self.assertEqual(graphics.selected_renderer(), current)
        name = graphics.current_renderer_name()
        self.assertTrue(name)
        # The name and the identity are two reports of one fact and must agree.
        self.assertEqual(graphics.parse_renderer_name(name), current)

    def test_unrecognised_name_is_an_answer_not_a_failure(self) -> None:
        self.assertIsNone(graphics.parse_renderer_name("definitely-not-a-renderer"))
        with self.assertRaises(TypeError):
            graphics.parse_renderer_name(None)

    def test_active_renderer_is_absent_until_the_selection_latches(self) -> None:
        if graphics.is_selection_latched():
            self.assertIsNotNone(graphics.active_renderer())
        else:
            self.assertIsNone(graphics.active_renderer())

    def test_fallback_history_is_reported_rather_than_assumed(self) -> None:
        history = graphics.fallback_history()
        self.assertIsInstance(history, tuple)
        for record in history:
            self.assertIsInstance(record.reason_name, str)
            self.assertTrue(record.message)

    def test_automatic_fallback_reports_a_real_setting(self) -> None:
        self.assertIsInstance(graphics.automatic_fallback(), bool)
        with self.assertRaises(TypeError):
            graphics.set_automatic_fallback(1)

    def test_non_rendering_identities_agree_with_the_private_layer(self) -> None:
        """Two places name the non-rendering backends; they must not drift apart."""
        from _cna_native.runtime_identity import NON_RENDERING_IDENTITIES

        self.assertEqual({int(value) for value in graphics.NON_RENDERING},
                         set(NON_RENDERING_IDENTITIES))

    def test_no_public_name_exposes_a_handle_or_a_ctypes_object(self) -> None:
        for name in graphics.__all__:
            value = getattr(graphics, name)
            self.assertFalse(isinstance(value, ctypes._SimpleCData), name)
            self.assertNotIn("_cna_native", getattr(value, "__module__", ""), name)


if __name__ == "__main__":
    unittest.main()
