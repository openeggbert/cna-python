"""The boundaries this extension promises to keep: layering, copies, lifetimes.

Three separate claims, each asserted rather than described:

* **Import layering.** ``Microsoft.Xna.Framework`` must behave identically
  whether or not this package exists, which means importing it must not load
  ``cna`` at all. Checked in a fresh interpreter, because a module already
  imported by an earlier test would hide exactly the dependency being denied.
* **Copy behaviour.** Everything crossing this boundary is a copy of native
  memory. No zero-copy claim is made anywhere, and the cost is measured rather
  than asserted to be absent.
* **Lifetime.** Closing is deterministic and ordered by the caller, and a closed
  object refuses further use rather than reaching into freed memory.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time
import unittest

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())
ROOT = Path(__file__).resolve().parents[1]

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb


def _fresh(source: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), environment.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(source)],
                          cwd=str(ROOT), env=environment, capture_output=True,
                          text=True, timeout=300)


class ImportLayeringTests(unittest.TestCase):
    """The dependency runs extension -> strict, and only that way."""

    def test_importing_the_xna_namespace_never_loads_the_extension(self) -> None:
        completed = _fresh("""
            import sys
            import Microsoft.Xna.Framework
            import Microsoft.Xna.Framework.Content
            import Microsoft.Xna.Framework.Graphics
            import Microsoft.Xna.Framework.Media
            import Microsoft.Xna.Framework.Audio
            leaked = sorted(name for name in sys.modules
                            if name == "cna" or name.startswith("cna."))
            print("LEAKED", leaked)
        """)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("LEAKED []", completed.stdout, completed.stdout)

    def test_the_extension_may_depend_on_the_strict_value_types(self) -> None:
        # The allowed direction, asserted so a future refactor that inverted it
        # would be caught by the other test rather than by nothing.
        completed = _fresh("""
            import sys
            import cna.extensions.content
            strict = sorted(name for name in sys.modules
                            if name.startswith("Microsoft.Xna.Framework"))
            print("USES", bool(strict))
        """)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("USES True", completed.stdout)

    def test_importing_the_extension_does_not_require_a_native_library(self) -> None:
        # Importing must not load CNA: a program that only inspects the API, or
        # imports it on a machine with no CNA build, has to keep working.
        completed = _fresh("""
            import os
            os.environ.pop("CNA_NATIVE_LIBRARY", None)
            os.environ.pop("CNA_NATIVE_DIR", None)
            import cna.extensions.content as content
            print("NAMES", len(content.__all__))
            print("CONSTANT", content.CONTAINER_MAJOR)
        """)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NAMES", completed.stdout)
        self.assertIn("CONSTANT 1", completed.stdout)

    def test_calling_into_the_extension_without_a_library_says_so(self) -> None:
        completed = _fresh("""
            import os
            os.environ.pop("CNA_NATIVE_LIBRARY", None)
            os.environ.pop("CNA_NATIVE_DIR", None)
            from cna.extensions import content
            try:
                content.format_magic()
                print("RESULT unexpectedly succeeded")
            except Exception as error:
                print("RESULT", type(error).__name__)
        """)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NativeUnavailableError", completed.stdout)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class CopyBehaviourTests(unittest.TestCase):
    """Everything here copies native memory. That is stated, and measured."""

    def test_reading_a_payload_returns_an_independent_copy(self) -> None:
        pixels = bytes(range(64))
        with cnb.CnbTextureData.from_rgba8(4, 4, pixels) as texture:
            first = texture.level(0, 0)
            second = texture.level(0, 0)
            self.assertEqual(first, second)
            self.assertIsNot(first, second, "each read is its own copy")
            # Mutating a copy cannot reach the texture.
            mutated = bytearray(first)
            mutated[0] ^= 0xFF
            self.assertEqual(texture.level(0, 0), pixels)

    def test_a_source_buffer_is_copied_rather_than_borrowed(self) -> None:
        # The caller's buffer may be reused or freed immediately afterwards.
        source = bytearray(range(64))
        with cnb.CnbTextureData.from_rgba8(4, 4, source) as texture:
            source[:] = bytes(64)
            self.assertEqual(texture.level(0, 0), bytes(range(64)))

    @staticmethod
    def _nanoseconds_per_byte(side: int) -> float:
        """Cost of one level read, per byte, after a warm-up read.

        Per byte rather than per call, because that is the quantity a linear
        implementation holds roughly constant and a quadratic one does not.
        """
        payload = bytes(side * side * 4)
        with cnb.CnbTextureData.from_rgba8(side, side, payload) as texture:
            texture.level(0, 0)  # warm: the first read pays for the allocator
            start = time.perf_counter()
            for _ in range(4):
                texture.level(0, 0)
            elapsed = time.perf_counter() - start
        return elapsed / (4 * len(payload)) * 1e9

    def test_reading_a_payload_scales_with_its_size_not_its_square(self) -> None:
        """No accidental quadratic in the two-call read protocol.

        The sizing call is made with no destination, so CNA reports the length
        without copying and only the second call moves bytes. If it copied
        twice, or grew a buffer as it went, cost per byte would climb with size.

        The bound is deliberately loose: this is a shape check on a shared
        machine, not a benchmark. Quadratic behaviour over a fourfold size
        increase would show as a fourfold rise in cost per byte; anything under
        that, with room to spare, is linear.
        """
        one_megabyte = self._nanoseconds_per_byte(512)
        four_megabytes = self._nanoseconds_per_byte(1024)
        self.assertGreater(one_megabyte, 0.0)
        self.assertLess(four_megabytes / one_megabyte, 2.5,
                        f"cost per byte rose from {one_megabyte:.2f} to "
                        f"{four_megabytes:.2f} ns over a fourfold size increase")

    def test_building_a_document_scales_with_its_chunk_count(self) -> None:
        def nanoseconds_per_chunk(chunk_count: int) -> float:
            with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
                writer.set_metadata("Test.Asset", "")
                for _index in range(chunk_count):
                    writer.add_chunk(cnb.chunk_id("aaaa"), bytes(1024))
                writer.build()  # warm
                start = time.perf_counter()
                for _ in range(4):
                    writer.build()
                return (time.perf_counter() - start) / (4 * chunk_count) * 1e9

        few = nanoseconds_per_chunk(32)
        many = nanoseconds_per_chunk(512)
        self.assertGreater(few, 0.0)
        self.assertLess(many / few, 4.0,
                        f"cost per chunk rose from {few:.0f} to {many:.0f} ns over a "
                        "sixteenfold increase in chunk count")

    def test_the_documented_copy_points_are_the_only_ones(self) -> None:
        # A caller deciding where to bind a value needs to know which properties
        # copy. These do, every time they are read, which is why the docstrings
        # say so and why nothing here is described as zero-copy.
        for name, owner in (("samples", "CnbSoundEffectData"),
                            ("cnb_bytes", "CnjCompilation")):
            documentation = (getattr(getattr(cnb, owner), name).__doc__ or "").lower()
            self.assertTrue("copy" in documentation or "copies" in documentation,
                            f"{owner}.{name} does not say that it copies")


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
class LifetimeTests(unittest.TestCase):
    """Every owned object closes explicitly, idempotently, and refuses use after."""

    def _owned(self):
        pixels = bytes(range(64))
        with cnb.CnbTextureData.from_rgba8(4, 4, pixels) as texture:
            image = cnb.encode_texture2d(texture)
        yield "texture", cnb.CnbTextureData.from_rgba8(4, 4, pixels), \
            lambda value: value.info
        yield "document", cnb.CnbDocument.parse(image), lambda value: value.chunk_count
        yield "reader", cnb.CnbReader.over_bytes(b"\x01\x02\x03\x04"), \
            lambda value: value.remaining
        yield "byte writer", cnb.CnbByteWriter(), lambda value: value.size
        yield "writer", cnb.CnbWriter(int(cnb.AssetType.Curve), 1), \
            lambda value: value.schema_chunk_count
        yield "model", cnb.CnbModelData.create(), lambda value: value.info
        yield "font", cnb.CnbSpriteFontData.create(), lambda value: value.info

    def test_every_owned_object_closes_once_twice_and_then_refuses(self) -> None:
        for label, value, use in self._owned():
            with self.subTest(label):
                self.assertFalse(value.closed)
                use(value)
                value.close()
                self.assertTrue(value.closed)
                value.close()  # idempotent, not a double free
                with self.assertRaises(ValueError):
                    use(value)

    def test_every_owned_object_works_as_a_context_manager(self) -> None:
        for label, value, use in self._owned():
            with self.subTest(label):
                with value as entered:
                    self.assertIs(entered, value)
                    use(entered)
                self.assertTrue(value.closed)

    def test_a_closed_object_reprs_without_reaching_into_freed_memory(self) -> None:
        for label, value, _use in self._owned():
            with self.subTest(label):
                value.close()
                self.assertIn("closed", repr(value))

    def test_an_exception_inside_the_block_still_closes(self) -> None:
        texture = cnb.CnbTextureData.from_rgba8(2, 2, bytes(16))
        with self.assertRaises(KeyError):
            with texture:
                raise KeyError("the caller's own failure")
        self.assertTrue(texture.closed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
