from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from _cna_native.errors import NativeAbiMismatchError, NativeLibraryError, NativeUnavailableError
from _cna_native.loader import QUALIFIED_ABI, _reset_for_tests, get_library


@contextmanager
def native_environment(**values: str | None):
    names = ("CNA_NATIVE_LIBRARY", "CNA_NATIVE_DIR")
    old = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        for name, value in values.items():
            if value is not None:
                os.environ[name] = value
        _reset_for_tests()
        yield
    finally:
        for name in names:
            os.environ.pop(name, None)
            if old[name] is not None:
                os.environ[name] = old[name]
        _reset_for_tests()


class LoaderTests(unittest.TestCase):
    def test_unconfigured_loader_is_actionable(self) -> None:
        with native_environment():
            with self.assertRaisesRegex(NativeUnavailableError, "CNA_NATIVE_LIBRARY"):
                get_library()

    def test_explicit_path_must_be_absolute_existing_file(self) -> None:
        with native_environment(CNA_NATIVE_LIBRARY="relative.so"):
            with self.assertRaisesRegex(NativeLibraryError, "absolute"):
                get_library()
        with native_environment(CNA_NATIVE_LIBRARY="/definitely/missing/cna.so"):
            with self.assertRaisesRegex(NativeUnavailableError, "existing file"):
                get_library()

    def _build_library(self, version: int, extra: str = "") -> str:
        directory = tempfile.mkdtemp(prefix="cna-python-loader-")
        source, library = Path(directory) / "fake.c", Path(directory) / "libfake.so"
        source.write_text(f"#include <stdint.h>\nuint32_t cna_get_abi_version(void){{return {version}u;}}\n{extra}\n")
        subprocess.run(["cc", "-shared", "-fPIC", str(source), "-o", str(library)], check=True)
        return str(library)

    def test_superseded_abi_generation_is_rejected(self) -> None:
        """The historical 0.7.0 generation is a different contract, not a subset."""
        path = self._build_library(0x00000700)
        with native_environment(CNA_NATIVE_LIBRARY=path):
            with self.assertRaises(NativeAbiMismatchError) as caught:
                get_library()
        self.assertEqual(caught.exception.actual, 0x00000700)

    def test_later_abi_minor_is_rejected(self) -> None:
        """A later minor may change a contract incompatibly, so it is not assumed."""
        later = QUALIFIED_ABI + (1 << 8)
        path = self._build_library(later)
        with native_environment(CNA_NATIVE_LIBRARY=path):
            with self.assertRaises(NativeAbiMismatchError) as caught:
                get_library()
        self.assertEqual(caught.exception.actual, later)

    def test_different_major_is_rejected(self) -> None:
        path = self._build_library(0x00011500)
        with native_environment(CNA_NATIVE_LIBRARY=path):
            with self.assertRaises(NativeAbiMismatchError) as caught:
                get_library()
        self.assertEqual(caught.exception.actual, 0x00011500)

    def test_missing_symbol_names_exact_import(self) -> None:
        """A patch inside the supported minor is accepted, then audited symbol by symbol."""
        path = self._build_library(QUALIFIED_ABI + 3)
        with native_environment(CNA_NATIVE_LIBRARY=path):
            with self.assertRaisesRegex(NativeLibraryError, "cna_error_get_last_info"):
                get_library()


if __name__ == "__main__":
    unittest.main()
