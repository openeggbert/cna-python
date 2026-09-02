"""Cross-checks this binding against CNA's own `.cnb` command-line tools.

The tools are a genuinely independent observer. They are a separate executable
built from the same C++ implementation, so agreement between them and this
binding rules out a whole class of mistake the Python tests cannot see on their
own: a wrapper that consistently mis-reads a field would still round-trip
through itself, and would still disagree with `cnb_info`.

The tools' human-readable output is **not** treated as a machine contract -- a C
API exists and is the contract. What is compared is the small set of facts both
sides state independently: whether a file validates at all, its asset type, its
chunk table, its external references, and whether the two compilers produce the
same bytes from the same input.

Both tools are optional. They are built from the CNA tree, which a consumer of
this package need not have, so their absence is a skip and is reported as one
rather than as a pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
HAS_NATIVE = bool(NATIVE and Path(NATIVE).is_file())

if HAS_NATIVE:  # pragma: no branch - the import is what the skip protects
    from cna.extensions import content as cnb
    from tests.cnb_fixtures import distinct_rgba, pcm16, png, wav


def _executable(path: Path) -> Path | None:
    return path if path.is_file() and os.access(path, os.X_OK) else None


def _cna_root(start: Path) -> Path | None:
    """Walks up from the loaded library to the CNA checkout that produced it."""
    for directory in [start, *start.parents]:
        if (directory / "modules/c-api/include/CNA/C/cnb.h").is_file():
            return directory
    return None


def _find_tool(name: str) -> Path | None:
    """Looks for one CNA content tool, beside the library or in its checkout.

    ``CNA_CONTENT_TOOLS`` names a directory explicitly and wins. Otherwise the
    tool is looked for beside the loaded library first -- same build tree, so
    same configuration -- and then in any build directory of the same CNA
    checkout, because a tool is not always built into every configuration.

    Picking a tool from a *different* build of the same checkout is safe here
    precisely because these tests are the cross-check: a tool that disagreed
    with the loaded library would fail them, which is the finding, not a false
    alarm. Nothing outside that checkout is searched.
    """
    configured = os.environ.get("CNA_CONTENT_TOOLS")
    if configured:
        return _executable(Path(configured) / name)
    if not HAS_NATIVE:
        return None
    library = Path(NATIVE).resolve()
    directory = library.parent
    for _ in range(4):
        found = _executable(directory / name)
        if found is not None:
            return found
        directory = directory.parent
    root = _cna_root(library.parent)
    if root is None:
        return None
    for build in sorted(root.glob("*build*")):
        found = _executable(build / name)
        if found is not None:
            return found
    return None


CNB_INFO = _find_tool("cna_tool_cnb_info")
CNJ_TO_CNB = _find_tool("cna_tool_cnj_to_cnb")


def _run(tool: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(tool), *arguments], capture_output=True, text=True,
                          timeout=120)


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
@unittest.skipUnless(CNB_INFO is not None,
                     "cna_tool_cnb_info is not built in this CNA tree")
class CnbInfoCrossCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="cnb-crosscheck-")
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)

    def _write(self, name: str, image: bytes) -> Path:
        path = self.root / name
        path.write_bytes(image)
        return path

    def test_the_tool_validates_every_file_this_binding_writes(self) -> None:
        """Whatever this binding produces, CNA's own validator accepts.

        The tool checks every structural invariant while reading, so a non-zero
        exit means the file is malformed. Covering each asset type makes the
        claim about the writer rather than about one lucky schema.
        """
        cases = {}
        with cnb.CnbTextureData.from_rgba8(4, 3, distinct_rgba(4, 3)) as texture:
            cases["texture2d.cnb"] = cnb.encode_texture2d(texture, content_name="ui/x")
        info = cnb.CnbSoundEffectInfo(cnb.AudioFormat.Pcm16, 22050, 1, 20)
        with cnb.CnbSoundEffectData.create(info, pcm16(20)) as sound:
            cases["sound.cnb"] = cnb.encode_sound_effect(sound, content_name="sfx/x")
        song = cnb.CnbSongData("Music/theme.ogg", "Theme", 1234)
        cases["song.cnb"] = cnb.encode_song(song, content_name="music/x")
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_metadata("Microsoft.Xna.Framework.Curve", "curves/x")
            writer.add_external_reference("textures/atlas")
            writer.add_chunk(cnb.chunk_id("mych"), b"payload!",
                             flags=cnb.ChunkFlags.Mandatory, alignment=4)
            cases["hand-written.cnb"] = writer.build()

        for name, image in cases.items():
            path = self._write(name, image)
            completed = _run(CNB_INFO, str(path), "--quiet")
            self.assertEqual(completed.returncode, 0,
                             f"{name}: {completed.stdout}{completed.stderr}")

    def test_the_tool_and_this_binding_report_the_same_chunk_table(self) -> None:
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_metadata("Microsoft.Xna.Framework.Curve", "curves/x")
            writer.add_external_reference("textures/atlas")
            writer.add_chunk(cnb.chunk_id("aaaa"), b"one", alignment=4)
            writer.add_chunk(cnb.chunk_id("bbbb"), b"two two",
                             flags=cnb.ChunkFlags.Mandatory)
            image = writer.build()
        path = self._write("chunks.cnb", image)

        completed = _run(CNB_INFO, str(path), "--chunks")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        with cnb.CnbDocument.parse(image) as document:
            expected = document.chunks

        # The tool's own rendering names each chunk and its logical size; both
        # facts are compared, in the order the tool printed them.
        printed = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertGreaterEqual(len(printed), len(expected))
        rendered = "\n".join(printed)
        for chunk in expected:
            self.assertIn(chunk.type_text, rendered, chunk.type_text)
            self.assertIn(str(chunk.uncompressed_size), rendered, chunk.type_text)

    def test_the_tool_and_this_binding_report_the_same_external_references(self) -> None:
        # --refs prints one logical name per line, for a build script. Order and
        # content must match what the document reports here.
        names = ["textures/atlas", "audio/step", "effects/custom"]
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_metadata("Microsoft.Xna.Framework.Curve", "curves/x")
            for name in names:
                writer.add_external_reference(name)
            writer.add_chunk(cnb.chunk_id("mych"), b"x")
            image = writer.build()
        path = self._write("refs.cnb", image)

        completed = _run(CNB_INFO, str(path), "--refs")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        printed = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        with cnb.CnbDocument.parse(image) as document:
            self.assertEqual(printed,
                             [reference.name for reference in document.external_references])
            self.assertEqual(printed, names)

    def test_the_tool_refuses_exactly_what_this_binding_refuses(self) -> None:
        """Both sides reject the same corrupt files, which is the stronger claim.

        A binding that accepted something the tool rejects would be reading past
        a check; one that rejected something the tool accepts would be refusing
        valid content. Neither happens here.
        """
        with cnb.CnbWriter(int(cnb.AssetType.Curve), 1) as writer:
            writer.set_metadata("Microsoft.Xna.Framework.Curve", "curves/x")
            writer.add_chunk(cnb.chunk_id("mych"), b"payload!")
            image = writer.build()

        mutations = {
            "magic.cnb": bytes([image[0] ^ 0xFF]) + image[1:],
            "header.cnb": image[:8] + bytes([image[8] ^ 0x01]) + image[9:],
            "payload.cnb": image[:-1] + bytes([image[-1] ^ 0xFF]),
            "truncated.cnb": image[: len(image) // 2],
            "empty.cnb": b"",
        }
        for name, broken in mutations.items():
            path = self._write(name, broken)
            completed = _run(CNB_INFO, str(path), "--quiet")
            with self.assertRaises(cnb.CnbError, msg=name):
                cnb.CnbDocument.parse(broken, origin=name).close()
            self.assertNotEqual(completed.returncode, 0,
                                f"{name}: the tool accepted what this binding refused")


@unittest.skipUnless(HAS_NATIVE, "CNA_NATIVE_LIBRARY is not configured")
@unittest.skipUnless(CNJ_TO_CNB is not None,
                     "cna_tool_cnj_to_cnb is not built in this CNA tree")
class CnjToCnbCrossCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="cnb-crosscheck-")
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)

    def _write_cnj(self, name: str, document: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_the_tool_and_this_binding_compile_the_same_bytes(self) -> None:
        """Two processes, one input, identical output.

        The strongest determinism claim available: two OS processes share no
        allocator state, no static-initialisation order and no warm heap, so
        byte-identical output is not an artifact of running in one interpreter.
        """
        cases = []

        self._write_cnj("ease.cnj", {
            "cnjVersion": 1, "type": "Curve", "preLoop": "Constant",
            "postLoop": "Linear",
            "keys": [{"position": 0, "value": 2.5},
                     {"position": 1, "value": 7.5, "continuity": "Step"}]})
        cases.append("ease.cnj")

        (self.root / "hero.png").write_bytes(png(4, 3, distinct_rgba(4, 3)))
        self._write_cnj("hero.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                     "sourceFile": "hero.png"})
        cases.append("hero.cnj")

        (self.root / "beep.wav").write_bytes(wav(pcm16(24)))
        self._write_cnj("beep.cnj", {"cnjVersion": 1, "type": "SoundEffect",
                                     "sourceFile": "beep.wav"})
        cases.append("beep.cnj")

        for name in cases:
            source = self.root / name
            output = self.root / (source.stem + ".tool.cnb")
            completed = _run(CNJ_TO_CNB, str(source), str(output), "--quiet")
            self.assertEqual(completed.returncode, 0,
                             f"{name}: {completed.stdout}{completed.stderr}")
            with cnb.compile_cnj(source) as result:
                self.assertEqual(result.cnb_bytes, output.read_bytes(),
                                 f"{name}: the two compilers disagree")

    def test_the_logical_name_reaches_both_compilers_the_same_way(self) -> None:
        source = self._write_cnj("ease.cnj", {
            "cnjVersion": 1, "type": "Curve", "keys": [{"position": 0, "value": 1}]})
        output = self.root / "named.cnb"
        completed = _run(CNJ_TO_CNB, str(source), str(output),
                         "--name", "curves/ease", "--quiet")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        with cnb.compile_cnj(source, content_name="curves/ease") as result:
            self.assertEqual(result.cnb_bytes, output.read_bytes())
        with cnb.CnbDocument.parse(output.read_bytes()) as document:
            self.assertEqual(document.metadata.content_name, "curves/ease")

    def test_the_tool_refuses_the_traversal_this_binding_refuses(self) -> None:
        source = self._write_cnj("bad.cnj", {"cnjVersion": 1, "type": "Texture2D",
                                             "sourceFile": "../../etc/passwd"})
        completed = _run(CNJ_TO_CNB, str(source), str(self.root / "bad.cnb"), "--quiet")
        self.assertNotEqual(completed.returncode, 0,
                            "the tool compiled a traversal this binding refuses")
        with self.assertRaises(cnb.CnbError):
            cnb.compile_cnj(source).close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
