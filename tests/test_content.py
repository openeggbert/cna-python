from __future__ import annotations

from io import BytesIO
from pathlib import Path
import struct
import tempfile
import unittest

from Microsoft.Xna.Framework import TitleContainer
from Microsoft.Xna.Framework.Content import (
    ContentLoadException,
    ContentManager,
    ContentReader,
    ContentSerializerAttribute,
    ContentSerializerCollectionItemNameAttribute,
    ContentSerializerRuntimeTypeAttribute,
    ContentSerializerTypeVersionAttribute,
    ContentTypeReader,
    ContentTypeReaderOfT,
    ResourceContentManager,
)
from Microsoft.Xna.Framework.Content._content import _register_content_type_reader
from Microsoft.Xna.Framework.Content._lzx import _decompress_xnb_lzx
from Microsoft.Xna.Framework._title import _set_title_root_for_tests


def _seven(value: int) -> bytes:
    value &= 0xFFFFFFFF
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _seven(len(encoded)) + encoded


def _xnb(readers: list[tuple[str, int]], body: bytes, shared_count: int = 0) -> bytes:
    payload = bytearray(_seven(len(readers)))
    for name, version in readers:
        payload.extend(_text(name))
        payload.extend(struct.pack("<i", version))
    payload.extend(_seven(shared_count))
    payload.extend(body)
    size = 10 + len(payload)
    return b"XNBw\x05\x00" + struct.pack("<I", size) + payload


def _lzx_uncompressed_block(payload: bytes, first: bool) -> bytes:
    if not payload or len(payload) > 0x8000:
        raise ValueError("fixture frame size")
    header_bits = (
        (3 << 28) | (len(payload) << 4)
        if first else (3 << 29) | (len(payload) << 5)
    )
    block = bytearray(16 + len(payload))
    block[0] = (header_bits >> 16) & 0xFF
    block[1] = (header_bits >> 24) & 0xFF
    block[2] = header_bits & 0xFF
    block[3] = (header_bits >> 8) & 0xFF
    block[4] = block[8] = block[12] = 1
    block[16:] = payload
    return bytes(block)


def _lzx_frame(payload: bytes, first: bool) -> bytes:
    block = _lzx_uncompressed_block(payload, first)
    return b"\xff" + struct.pack(">HH", len(payload), len(block)) + block


def _compressed_xnb(uncompressed: bytes) -> bytes:
    payload = uncompressed[10:]
    framed = _lzx_frame(payload, True)
    size = 14 + len(framed)
    return b"XNBw\x05\x80" + struct.pack("<II", size, len(payload)) + framed


STRING_READER = "Microsoft.Xna.Framework.Content.StringReader, Microsoft.Xna.Framework"


class _Payload:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.shared = None


class _PayloadReader(ContentTypeReaderOfT[_Payload]):
    initialized = 0

    def Initialize(self, manager) -> None:
        type(self).initialized += 1

    def Read(self, input, existingInstance):
        value = _Payload(input.ReadString()) if existingInstance is None else existingInstance
        if existingInstance is not None:
            value.name = input.ReadString()
        input.ReadSharedResource(lambda shared: setattr(value, "shared", shared))
        return value

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return True


class _ExternalReader(ContentTypeReaderOfT[_Payload]):
    def Read(self, input, existingInstance):
        result = _Payload()
        result.shared = input.ReadExternalReference()
        return result


class _Disposable:
    disposed = 0

    def Dispose(self) -> None:
        type(self).disposed += 1


class _DisposableReader(ContentTypeReaderOfT[_Disposable]):
    def Read(self, input, existingInstance):
        return _Disposable()


class _FailingReader(ContentTypeReaderOfT[_Payload]):
    def Read(self, input, existingInstance):
        input.ReadObject()
        raise RuntimeError("fixture reader failed")


class _WrongShapeReader(ContentTypeReaderOfT[_Payload]):
    def Read(self, input, existingInstance):
        return "not a payload"


class _ReplacementReader(ContentTypeReaderOfT[_Payload]):
    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return True

    def Read(self, input, existingInstance):
        return _Payload("replacement")


class _IdentityReader(ContentTypeReaderOfT[_Disposable]):
    def Read(self, input, existingInstance):
        return input.ReadObject()


class _FixupFailureReader(ContentTypeReaderOfT[_Payload]):
    def Read(self, input, existingInstance):
        value = _Payload()
        input.ReadSharedResource(lambda resource: (_ for _ in ()).throw(LookupError("fixup")))
        return value


class _ThrowingDisposable:
    disposed = 0

    def Dispose(self) -> None:
        type(self).disposed += 1
        raise LookupError("dispose failure")


class _ThrowingDisposableReader(ContentTypeReaderOfT[_ThrowingDisposable]):
    def Read(self, input, existingInstance):
        return _ThrowingDisposable()


class ContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._unregister = []

    def tearDown(self) -> None:
        for unregister in reversed(self._unregister):
            unregister()
        _set_title_root_for_tests(None)

    def register(self, name: str, reader: type[ContentTypeReader]) -> None:
        self._unregister.append(_register_content_type_reader(name, reader))

    def test_serializer_attributes_have_xna_defaults_and_independent_clone(self) -> None:
        value = ContentSerializerAttribute()
        self.assertEqual(value.ElementName, "")
        self.assertFalse(value.FlattenContent)
        self.assertFalse(value.Optional)
        self.assertTrue(value.AllowNull)
        self.assertFalse(value.SharedResource)
        self.assertEqual(value.CollectionItemName, "Item")
        self.assertFalse(value.HasCollectionItemName)
        value.ElementName = "Value"
        value.CollectionItemName = "Entry"
        clone = value.Clone()
        clone.ElementName = "Clone"
        clone.CollectionItemName = "Child"
        self.assertEqual(value.ElementName, "Value")
        self.assertEqual(value.CollectionItemName, "Entry")
        self.assertTrue(value.HasCollectionItemName)
        with self.assertRaises(ValueError):
            value.CollectionItemName = ""
        self.assertEqual(ContentSerializerCollectionItemNameAttribute("Glyph").CollectionItemName, "Glyph")
        self.assertEqual(ContentSerializerRuntimeTypeAttribute("Example.Type").RuntimeType, "Example.Type")
        self.assertEqual(ContentSerializerTypeVersionAttribute(7).TypeVersion, 7)

    def test_title_container_is_title_relative_normalized_and_cwd_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as other:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "nested" / "value.bin").write_bytes(b"title")
            _set_title_root_for_tests(root)
            previous = Path.cwd()
            try:
                import os
                os.chdir(other)
                with TitleContainer.OpenStream("nested\\folder\\..\\value.bin") as stream:
                    self.assertEqual(stream.read(), b"title")
                with TitleContainer.OpenStream("nested/value.bin") as first:
                    with TitleContainer.OpenStream("nested/value.bin") as second:
                        self.assertIsNot(first, second)
                self.assertTrue(first.closed)
            finally:
                os.chdir(previous)
            for invalid in ("", "/absolute", "../escape", "C:/drive", "a/../../escape"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    TitleContainer.OpenStream(invalid)
            with self.assertRaises(FileNotFoundError):
                TitleContainer.OpenStream("missing.bin")

        if hasattr(Path, "symlink_to"):
            with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
                root = Path(temporary)
                secret = Path(outside) / "secret.bin"
                secret.write_bytes(b"outside")
                try:
                    (root / "link").symlink_to(Path(outside), target_is_directory=True)
                except OSError:
                    pass
                else:
                    _set_title_root_for_tests(root)
                    with self.assertRaises(ValueError):
                        TitleContainer.OpenStream("link/secret.bin")

    def test_uncompressed_string_reader_cache_root_and_unload(self) -> None:
        asset = _xnb([(STRING_READER, 0)], _seven(1) + _text("hello"))
        manager = ResourceContentManager(object(), {"folder/hello": asset})
        manager.RootDirectory = "ignored-by-resource-manager"
        # ResourceContentManager follows ResourceManager lookup semantics and intentionally
        # does not apply the file-system RootDirectory.
        first = manager.Load("folder/hello")
        second = manager.Load("FOLDER\\HELLO")
        self.assertEqual(first, "hello")
        self.assertIs(first, second)
        manager.Unload()
        self.assertEqual(manager.Load("folder/hello"), "hello")
        manager.Dispose()
        manager.Dispose()
        with self.assertRaises(RuntimeError):
            manager.Load("folder/hello")

    def test_content_manager_root_directory_uses_title_path_and_appends_xnb(self) -> None:
        asset = _xnb([(STRING_READER, 0)], _seven(1) + _text("rooted"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Content").mkdir()
            (root / "Content" / "item.xnb").write_bytes(asset)
            _set_title_root_for_tests(root)
            manager = ContentManager(object(), "Content")
            self.assertEqual(manager.Load("item"), "rooted")
            with self.assertRaises(ContentLoadException):
                manager.Load("item.xnb")
            manager.Unload()
            manager.RootDirectory = "/absolute"
            with self.assertRaises(ContentLoadException):
                manager.Load("item")

    def test_custom_reader_initialization_shared_fixup_and_existing_instance(self) -> None:
        identity = "Example.Content.PayloadReader"
        self.register(identity, _PayloadReader)
        _PayloadReader.initialized = 0
        body = _seven(1) + _text("root") + _seven(1) + _seven(2) + _text("shared")
        asset = _xnb([(identity, 0), (STRING_READER, 0)], body, shared_count=1)
        manager = ResourceContentManager(object(), {"custom": asset})
        value = manager.Load("custom")
        self.assertIsInstance(value, _Payload)
        self.assertEqual((value.name, value.shared), ("root", "shared"))
        self.assertEqual(_PayloadReader.initialized, 1)

        reader = ContentReader._create(manager, _text("updated") + _seven(0), "raw", None)
        existing = _Payload("old")
        self.assertIs(reader.ReadRawObject(_PayloadReader(), existing), existing)
        self.assertEqual(existing.name, "updated")
        none_reader = ContentReader._create(manager, _text("fresh") + _seven(0), "raw", None)
        self.assertEqual(none_reader.ReadRawObject(_PayloadReader(), None).name, "fresh")
        with self.assertRaises(NotImplementedError):
            reader.ReadRawObject()

        replacement_reader = ContentReader._create(manager, b"", "replacement", None)
        with self.assertRaisesRegex(RuntimeError, "replacement"):
            replacement_reader.ReadRawObject(_ReplacementReader(), _Payload())
        with self.assertRaises(TypeError):
            replacement_reader.ReadRawObject(_ReplacementReader(), "wrong")

    def test_external_references_are_relative_cached_and_circularity_is_rejected(self) -> None:
        identity = "Example.Content.ExternalReader"
        self.register(identity, _ExternalReader)
        parent = _xnb([(identity, 0)], _seven(1) + _text("child"))
        child = _xnb([(STRING_READER, 0)], _seven(1) + _text("dependency"))
        manager = ResourceContentManager(
            object(), {"folder/parent": parent, "folder/child": child}
        )
        loaded = manager.Load("folder/parent")
        self.assertEqual(loaded.shared, "dependency")
        self.assertIs(loaded.shared, manager.Load("folder/child"))

        first = _xnb([(identity, 0)], _seven(1) + _text("second"))
        second = _xnb([(identity, 0)], _seven(1) + _text("first"))
        circular = ResourceContentManager(
            object(), {"loop/first": first, "loop/second": second}
        )
        with self.assertRaisesRegex(ContentLoadException, "Circular"):
            circular.Load("loop/first")

    def test_failure_rolls_back_recorded_disposable(self) -> None:
        failing = "Example.Content.FailingReader"
        disposable = "Example.Content.DisposableReader"
        self.register(failing, _FailingReader)
        self.register(disposable, _DisposableReader)
        _Disposable.disposed = 0
        asset = _xnb([(failing, 0), (disposable, 0)], _seven(1) + _seven(2))
        manager = ResourceContentManager(object(), {"failure": asset})
        with self.assertRaises(ContentLoadException) as caught:
            manager.Load("failure")
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(_Disposable.disposed, 1)
        manager.Unload()
        self.assertEqual(_Disposable.disposed, 1)

    def test_wrong_reader_shape_duplicate_identity_and_fixup_failure_cleanup(self) -> None:
        wrong = "Example.Content.WrongShapeReader"
        identity = "Example.Content.IdentityReader"
        disposable = "Example.Content.DisposableReader2"
        fixup = "Example.Content.FixupFailureReader"
        self.register(wrong, _WrongShapeReader)
        self.register(identity, _IdentityReader)
        self.register(disposable, _DisposableReader)
        self.register(fixup, _FixupFailureReader)

        wrong_asset = _xnb([(wrong, 0)], _seven(1))
        with self.assertRaisesRegex(ContentLoadException, "declared target"):
            ResourceContentManager(object(), {"wrong": wrong_asset}).Load("wrong")

        _Disposable.disposed = 0
        duplicate_asset = _xnb([(identity, 0), (disposable, 0)], _seven(1) + _seven(2))
        duplicate_manager = ResourceContentManager(object(), {"duplicate": duplicate_asset})
        duplicate_manager.Load("duplicate")
        duplicate_manager.Unload()
        self.assertEqual(_Disposable.disposed, 1)

        _Disposable.disposed = 0
        fixup_asset = _xnb(
            [(fixup, 0), (disposable, 0)],
            _seven(1) + _seven(1) + _seven(2),
            shared_count=1,
        )
        fixup_manager = ResourceContentManager(object(), {"fixup": fixup_asset})
        with self.assertRaises(ContentLoadException) as caught:
            fixup_manager.Load("fixup")
        self.assertIsInstance(caught.exception.__cause__, LookupError)
        self.assertEqual(_Disposable.disposed, 1)

    def test_resource_manager_snapshots_stream_without_closing_it(self) -> None:
        stream = BytesIO(_xnb([(STRING_READER, 0)], _seven(1) + _text("stream")))
        manager = ResourceContentManager(object(), {"stream": stream})
        self.assertEqual(manager.Load("stream"), "stream")
        self.assertFalse(stream.closed)
        self.assertEqual(stream.tell(), len(stream.getvalue()))
        with self.assertRaises(ContentLoadException):
            ResourceContentManager(object(), {}).Load("missing")

    def test_unload_exception_clears_ownership_and_dispose_can_finish(self) -> None:
        identity = "Example.Content.ThrowingDisposableReader"
        self.register(identity, _ThrowingDisposableReader)
        _ThrowingDisposable.disposed = 0
        asset = _xnb([(identity, 0)], _seven(1))
        manager = ResourceContentManager(object(), {"throwing": asset})
        manager.Load("throwing")
        with self.assertRaisesRegex(LookupError, "dispose failure"):
            manager.Unload()
        self.assertEqual(_ThrowingDisposable.disposed, 1)
        self.assertEqual(manager._loaded_assets, {})
        manager.Dispose()
        with self.assertRaises(RuntimeError):
            manager.Load("throwing")

    def test_header_reader_table_and_shape_failures_are_explicit(self) -> None:
        valid = _xnb([(STRING_READER, 0)], _seven(1) + _text("ok"))
        cases = {
            "magic": b"BAD" + valid[3:],
            "platform": valid[:3] + b"x" + valid[4:],
            "version": valid[:4] + b"\x04" + valid[5:],
            "size": valid[:6] + struct.pack("<I", len(valid) + 1) + valid[10:],
            "reader-index": _xnb([(STRING_READER, 0)], _seven(2)),
            "reader-version": _xnb([(STRING_READER, 1)], _seven(1) + _text("bad")),
            "unknown-reader": _xnb([("Example.UnknownReader", 0)], _seven(1)),
            "invalid-flags": valid[:5] + b"\x01" + valid[6:],
            "lz4-flag": valid[:5] + b"\x40" + valid[6:],
            "truncated-table": b"XNBw\x05\x00\x0b\x00\x00\x00\x01",
            "negative-reader-count": _xnb([], b"")[:10] + _seven(-1),
        }
        for name, payload in cases.items():
            with self.subTest(name=name):
                manager = ResourceContentManager(object(), {name: payload})
                with self.assertRaises(ContentLoadException):
                    manager.Load(name)

    def test_lzx_single_multi_frame_xnb_and_negative_boundaries(self) -> None:
        asset = _xnb([(STRING_READER, 0)], _seven(1) + _text("compressed"))
        compressed = _compressed_xnb(asset)
        manager = ResourceContentManager(object(), {"compressed": compressed})
        self.assertEqual(manager.Load("compressed"), "compressed")

        first = bytes((index * 37 + 11) & 0xFF for index in range(0x8000))
        second = b"persistent decoder frame" * 100
        framed = _lzx_frame(first, True) + _lzx_frame(second, False)
        self.assertEqual(_decompress_xnb_lzx(framed, len(first) + len(second), "multi"), first + second)

        valid = _lzx_frame(b"abcd", True)
        malformed = [
            (b"\xff", 4),
            (b"\xff\x00\x04\x00", 4),
            (valid[:-1], 4),
            (valid, 3),
            (valid, 5),
            (valid + b"\x01", 4),
            (valid + b"\x00\x00\x01", 4),
        ]
        for payload, length in malformed:
            with self.subTest(payload=payload[-5:], length=length), self.assertRaises(ContentLoadException):
                _decompress_xnb_lzx(payload, length, "bad")

    def test_optional_independent_compressed_fixture_bytes(self) -> None:
        import os
        root_value = os.environ.get("CNA_PYTHON_LZX_FIXTURE_DIR")
        if not root_value:
            self.skipTest("CNA_PYTHON_LZX_FIXTURE_DIR is not configured")
        root = Path(root_value)
        for name in ("Explosion", "FontCalibri14"):
            data = (root / f"{name}.xnb").read_bytes()
            expected = (root / "reference-decompressed" / f"{name}.decompressed.bin").read_bytes()
            self.assertEqual(data[:6], b"XNBw\x05\x80")
            self.assertEqual(
                _decompress_xnb_lzx(data[14:], int.from_bytes(data[10:14], "little"), name),
                expected,
            )


if __name__ == "__main__":
    unittest.main()
