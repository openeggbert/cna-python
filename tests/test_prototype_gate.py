"""Falsifiability tests for the compiler-backed prototype gate.

Every planted defect below changes an ABI-observable property of a real imported
route.  Each one must be rejected by the C compiler; a gate that accepts them
would prove nothing about the migrated native boundary.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from _cna_native import abi
from _cna_native.loader import FUNCTION_MANIFEST
from cna_headers import parse_include_directory
from verify_prototypes import verify_manifest


def _cna_include() -> Path | None:
    root = os.environ.get("CNA_SOURCE_ROOT")
    if root is None:
        return None
    include = Path(root) / "modules/c-api/include"
    return include if (include / "CNA/C/abi.h").is_file() else None


INCLUDE = _cna_include()
COMPILER = shutil.which("cc") or shutil.which("gcc")


@unittest.skipIf(INCLUDE is None, "CNA_SOURCE_ROOT is not configured")
@unittest.skipIf(COMPILER is None, "no C compiler is available")
class PrototypeGateFalsifiability(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert INCLUDE is not None
        cls.canonical = parse_include_directory(INCLUDE)
        cls.entries = {entry[0]: entry for entry in FUNCTION_MANIFEST}

    def _verify(self, entries: list[tuple[str, object, list[object], str]]) -> dict[str, object]:
        assert INCLUDE is not None and COMPILER is not None
        return verify_manifest(tuple(entries), self.canonical, INCLUDE, COMPILER)

    def _entry(self, symbol: str) -> tuple[str, object, list[object], str]:
        entry = self.entries[symbol]
        return (entry[0], entry[1], list(entry[2]), entry[3])

    def _assert_rejected(self, entry: tuple[str, object, list[object], str], reason: str) -> None:
        report = self._verify([entry])
        summary = report["summary"]
        rejected = summary["PROTOTYPE_CONFLICTS"] + summary["RENDER_FAILURES"]
        self.assertEqual(rejected, 1, f"planted defect was accepted: {reason}")
        self.assertEqual(summary["PROTOTYPES_COMPILER_VERIFIED"], 0, reason)

    def test_unmutated_route_is_accepted(self) -> None:
        report = self._verify([self._entry("cna_game_create")])
        self.assertEqual(report["summary"]["PROTOTYPES_COMPILER_VERIFIED"], 1)
        self.assertEqual(report["summary"]["PROTOTYPE_CONFLICTS"], 0)

    def test_wrong_integer_width_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_set_target_elapsed_time_ticks")
        self.assertIs(argtypes[1], ctypes.c_int64)
        argtypes[1] = ctypes.c_int32
        self._assert_rejected((symbol, restype, argtypes, ownership), "int64_t narrowed to int32_t")

    def test_wrong_signedness_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_set_target_elapsed_time_ticks")
        argtypes[1] = ctypes.c_uint64
        self._assert_rejected((symbol, restype, argtypes, ownership), "int64_t made unsigned")

    def test_wrong_return_width_is_rejected(self) -> None:
        symbol, _restype, argtypes, ownership = self._entry("cna_game_run")
        self._assert_rejected(
            (symbol, ctypes.c_uint64, argtypes, ownership), "CNA_Result widened to uint64_t"
        )

    def test_pointer_depth_change_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_create")
        self.assertIs(argtypes[1], ctypes.POINTER(ctypes.c_uint64))
        argtypes[1] = ctypes.POINTER(ctypes.POINTER(ctypes.c_uint64))
        self._assert_rejected((symbol, restype, argtypes, ownership), "out handle pointer depth raised")

    def test_struct_by_value_instead_of_pointer_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_create")
        argtypes[0] = abi.CNA_GameCreateInfo
        self._assert_rejected(
            (symbol, restype, argtypes, ownership), "create info passed by value, not by pointer"
        )

    def test_pointer_instead_of_struct_by_value_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_set_window_title")
        self.assertIs(argtypes[1], abi.CNA_StringView)
        argtypes[1] = ctypes.POINTER(abi.CNA_StringView)
        self._assert_rejected(
            (symbol, restype, argtypes, ownership), "string view passed by pointer, not by value"
        )

    def test_swapped_parameters_are_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_storage_container_open_file_share")
        argtypes[1], argtypes[5] = argtypes[5], argtypes[1]
        self._assert_rejected((symbol, restype, argtypes, ownership), "parameters swapped")

    def test_wrong_arity_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_create")
        self._assert_rejected((symbol, restype, argtypes[:1], ownership), "one parameter dropped")

    def test_wrong_callback_signature_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_subscribe")
        self.assertIs(argtypes[2], abi.CNA_GameEventCallback)
        argtypes[2] = ctypes.CFUNCTYPE(None, ctypes.c_uint64, ctypes.c_void_p)
        self._assert_rejected(
            (symbol, restype, argtypes, ownership), "callback gained a leading handle parameter"
        )

    def test_wrong_callback_return_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_game_subscribe")
        argtypes[2] = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
        self._assert_rejected(
            (symbol, restype, argtypes, ownership), "void callback given a result return"
        )

    def test_wrong_pointee_type_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_error_get_last_info")
        argtypes[0] = ctypes.POINTER(abi.CNA_GameTime)
        self._assert_rejected((symbol, restype, argtypes, ownership), "wrong output structure type")

    def test_char_buffer_confused_with_byte_buffer_is_rejected(self) -> None:
        symbol, restype, argtypes, ownership = self._entry("cna_error_copy_last_message")
        self.assertIs(argtypes[0], ctypes.POINTER(ctypes.c_char))
        argtypes[0] = ctypes.POINTER(ctypes.c_uint8)
        self._assert_rejected((symbol, restype, argtypes, ownership), "char* confused with uint8_t*")

    def test_unknown_symbol_is_reported(self) -> None:
        report = self._verify([("cna_not_a_real_route", ctypes.c_uint32, [], "none")])
        self.assertEqual(report["summary"]["ABSENT_FROM_HEADERS"], 1)


if __name__ == "__main__":
    unittest.main()
