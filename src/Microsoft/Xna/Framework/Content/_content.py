"""Managed XNA Content/XNB architecture over the existing CNA resource facades."""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from pathlib import PurePosixPath
import re
from threading import RLock
from typing import BinaryIO, Callable, Generic, TypeVar, get_args, get_origin

from .._geometry import Color
from .._math import Matrix, Quaternion, Vector2, Vector3, Vector4
from .._numeric import int32
from ._binary import _BinaryReader


T = TypeVar("T")


class ContentLoadException(Exception):
    """Mapped XNA content-loading failure with Python exception chaining."""

    def __init__(self, *args: object) -> None:
        if not args:
            super().__init__()
        elif len(args) == 1 and isinstance(args[0], str):
            super().__init__(args[0])
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], Exception):
            super().__init__(args[0])
            self.__cause__ = args[1]
        elif len(args) == 2:
            raise TypeError("serialization-info construction is not available in the Python projection")
        else:
            raise TypeError("ContentLoadException expects (), message, or message and innerException")


class ContentSerializerAttribute:
    def __init__(self) -> None:
        self._element_name = ""
        self._flatten_content = False
        self._optional = False
        self._allow_null = True
        self._shared_resource = False
        self._collection_item_name: str | None = None

    def Clone(self) -> "ContentSerializerAttribute":
        result = ContentSerializerAttribute()
        result._element_name = self._element_name
        result._flatten_content = self._flatten_content
        result._optional = self._optional
        result._allow_null = self._allow_null
        result._shared_resource = self._shared_resource
        result._collection_item_name = self._collection_item_name
        return result

    @staticmethod
    def _bool(value: object, name: str) -> bool:
        if type(value) is not bool:
            raise TypeError(f"{name} must be bool")
        return value

    @property
    def ElementName(self) -> str:
        return self._element_name

    @ElementName.setter
    def ElementName(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("ElementName must be str")
        self._element_name = value

    @property
    def FlattenContent(self) -> bool:
        return self._flatten_content

    @FlattenContent.setter
    def FlattenContent(self, value: bool) -> None:
        self._flatten_content = self._bool(value, "FlattenContent")

    @property
    def Optional(self) -> bool:
        return self._optional

    @Optional.setter
    def Optional(self, value: bool) -> None:
        self._optional = self._bool(value, "Optional")

    @property
    def AllowNull(self) -> bool:
        return self._allow_null

    @AllowNull.setter
    def AllowNull(self, value: bool) -> None:
        self._allow_null = self._bool(value, "AllowNull")

    @property
    def SharedResource(self) -> bool:
        return self._shared_resource

    @SharedResource.setter
    def SharedResource(self, value: bool) -> None:
        self._shared_resource = self._bool(value, "SharedResource")

    @property
    def CollectionItemName(self) -> str:
        return "Item" if self._collection_item_name is None else self._collection_item_name

    @CollectionItemName.setter
    def CollectionItemName(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("CollectionItemName must be str")
        if not value:
            raise ValueError("CollectionItemName must not be empty")
        self._collection_item_name = value

    @property
    def HasCollectionItemName(self) -> bool:
        return self._collection_item_name is not None


class ContentSerializerCollectionItemNameAttribute:
    def __init__(self, collectionItemName: str) -> None:
        if collectionItemName is None:
            raise TypeError("collectionItemName cannot be None")
        if not isinstance(collectionItemName, str):
            raise TypeError("collectionItemName must be str")
        self._collection_item_name = collectionItemName

    @property
    def CollectionItemName(self) -> str:
        return self._collection_item_name


class ContentSerializerIgnoreAttribute:
    def __init__(self) -> None:
        pass


class ContentSerializerRuntimeTypeAttribute:
    def __init__(self, runtimeType: str) -> None:
        if runtimeType is None:
            raise TypeError("runtimeType cannot be None")
        if not isinstance(runtimeType, str):
            raise TypeError("runtimeType must be str")
        self._runtime_type = runtimeType

    @property
    def RuntimeType(self) -> str:
        return self._runtime_type


class ContentSerializerTypeVersionAttribute:
    def __init__(self, typeVersion: int) -> None:
        self._type_version = int32(typeVersion, name="typeVersion")

    @property
    def TypeVersion(self) -> int:
        return self._type_version


class ContentTypeReader:
    def __init__(self, targetType: type) -> None:
        if not isinstance(targetType, type):
            raise TypeError("targetType must be a Python runtime type")
        self._target_type = targetType
        self._serialized_identity: str | None = None

    @property
    def TargetType(self) -> type:
        return self._target_type

    @property
    def TypeVersion(self) -> int:
        return 0

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return False

    def Initialize(self, manager: "ContentTypeReaderManager") -> None:
        if not isinstance(manager, ContentTypeReaderManager):
            raise TypeError("manager must be ContentTypeReaderManager")

    def Read(self, input: "ContentReader", existingInstance: object) -> object:
        raise NotImplementedError(f"{type(self).__name__}.Read is not implemented")


class ContentTypeReaderOfT(ContentTypeReader, Generic[T]):
    def __init__(self) -> None:
        super().__init__(_infer_generic_reader_target(type(self)))

    def Read(self, input: "ContentReader", existingInstance: T) -> T:
        raise NotImplementedError(f"{type(self).__name__}.Read is not implemented")


def _infer_generic_reader_target(reader_type: type) -> type:
    explicit = getattr(reader_type, "_content_target_type", None)
    if isinstance(explicit, type):
        return explicit
    for current in reader_type.__mro__:
        for base in getattr(current, "__orig_bases__", ()):
            if get_origin(base) is ContentTypeReaderOfT:
                arguments = get_args(base)
                if len(arguments) != 1:
                    break
                target = arguments[0]
                if isinstance(target, type):
                    return target
                origin = get_origin(target)
                if isinstance(origin, type) and all(isinstance(value, type) for value in get_args(target)):
                    return origin
                raise RuntimeError(
                    "ContentTypeReaderOfT target must resolve to a concrete Python runtime type"
                )
    raise RuntimeError(
        "ContentTypeReaderOfT subclass must declare a concrete ContentTypeReaderOfT[Target] base"
    )


class ContentTypeReaderManager:
    @classmethod
    def _create(cls) -> "ContentTypeReaderManager":
        result = object.__new__(cls)
        result._readers_by_target = {}
        result._readers_by_identity = {}
        result._readers = ()
        result._versions = ()
        return result

    def GetTypeReader(self, targetType: type) -> ContentTypeReader | None:
        if not isinstance(targetType, type):
            raise TypeError("targetType must be a Python runtime type")
        return getattr(self, "_readers_by_target", {}).get(targetType)

    def _get_identity_reader(self, identity: str) -> ContentTypeReader | None:
        return getattr(self, "_readers_by_identity", {}).get(identity)

    def _load_asset_readers(self, input: "ContentReader") -> tuple[ContentTypeReader, ...]:
        count = input._read_7bit()
        if count < 0 or count > 4096:
            raise input._failure(f"invalid type reader count {count}")
        readers: list[ContentTypeReader] = []
        versions: list[int] = []
        for _ in range(count):
            serialized = input.ReadString()
            identity = _normalize_reader_identity(serialized)
            reader = _create_reader(identity, input.AssetName)
            version = input.ReadInt32()
            expected_version = int32(reader.TypeVersion, name="ContentTypeReader.TypeVersion")
            if version != expected_version:
                raise input._failure(
                    f"reader version mismatch for '{serialized}': asset {version}, runtime {expected_version}"
                )
            reader._serialized_identity = identity
            readers.append(reader)
            versions.append(version)
            self._readers_by_target.setdefault(reader.TargetType, reader)
            self._readers_by_identity.setdefault(identity, reader)
        self._readers = tuple(readers)
        self._versions = tuple(versions)
        for reader in readers:
            try:
                reader.Initialize(self)
            except ContentLoadException:
                raise
            except Exception as error:
                raise ContentLoadException(
                    f"Failed to initialize content type reader '{type(reader).__name__}'", error
                ) from error
        return self._readers

    def _version_for(self, reader: ContentTypeReader) -> int:
        for index, candidate in enumerate(getattr(self, "_readers", ())):
            if candidate is reader:
                return self._versions[index]
        raise ValueError("reader is not in this asset's type reader table")


_custom_reader_lock = RLock()
_custom_reader_types: dict[str, type[ContentTypeReader]] = {}


def _register_content_type_reader(
    serialized_reader_name: str, reader_type: type[ContentTypeReader]
) -> Callable[[], None]:
    """Private Python language bridge for custom serialized reader identities."""
    identity = _normalize_reader_identity(serialized_reader_name)
    if not isinstance(reader_type, type) or not issubclass(reader_type, ContentTypeReader):
        raise TypeError("reader_type must derive from ContentTypeReader")
    with _custom_reader_lock:
        if identity in _custom_reader_types:
            raise ValueError(f"a content type reader is already registered as '{identity}'")
        _custom_reader_types[identity] = reader_type

    def unregister() -> None:
        with _custom_reader_lock:
            if _custom_reader_types.get(identity) is reader_type:
                del _custom_reader_types[identity]

    return unregister


def _normalize_reader_identity(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("serialized reader identity must be str")
    value = value.strip()
    if not value:
        raise ContentLoadException("XNB type reader identity must not be empty")
    result: list[str] = []
    depth = 0
    skipping = False
    for character in value:
        if character == "[":
            depth += 1
            skipping = False
            result.append(character)
        elif character == "]":
            if depth == 0:
                raise ContentLoadException(f"malformed XNB type reader identity '{value}'")
            depth -= 1
            skipping = False
            result.append(character)
        elif character == ",":
            if depth == 0:
                break
            skipping = True
        elif not skipping:
            result.append(character)
    if depth != 0:
        raise ContentLoadException(f"malformed XNB type reader identity '{value}'")
    normalized = "".join(result).strip()
    if not normalized or any(character.isspace() for character in normalized):
        raise ContentLoadException(f"malformed XNB type reader identity '{value}'")
    return normalized


def _create_reader(identity: str, asset_name: str) -> ContentTypeReader:
    from ._builtins import _create_builtin_reader

    reader = _create_builtin_reader(identity)
    if reader is not None:
        return reader
    with _custom_reader_lock:
        reader_type = _custom_reader_types.get(identity)
    if reader_type is None:
        raise ContentLoadException(
            f"Could not find ContentTypeReader '{identity}' while loading '{asset_name}'"
        )
    try:
        reader = reader_type()
    except Exception as error:
        raise ContentLoadException(
            f"Failed to construct content type reader '{identity}'", error
        ) from error
    if not isinstance(reader, ContentTypeReader):
        raise ContentLoadException(f"Custom content reader '{identity}' returned the wrong object")
    return reader


class ContentReader(_BinaryReader):
    @classmethod
    def _create(
        cls, content_manager: "ContentManager", payload: bytes, asset_name: str,
        record_disposable: Callable[[object], None] | None,
    ) -> "ContentReader":
        result = object.__new__(cls)
        _BinaryReader.__init__(result, BytesIO(payload))
        result._content_manager = content_manager
        result._asset_name = asset_name
        result._record_disposable = record_disposable
        result._type_readers = ()
        result._reader_manager = ContentTypeReaderManager._create()
        result._shared_fixups = []
        result._shared_count = 0
        return result

    @classmethod
    def _from_xnb(
        cls, manager: "ContentManager", data: bytes, asset_name: str,
        record_disposable: Callable[[object], None] | None,
    ) -> "ContentReader":
        if len(data) < 10:
            raise ContentLoadException(f"Error loading '{asset_name}'. Truncated XNB header")
        if data[:3] != b"XNB":
            raise ContentLoadException(f"Error loading '{asset_name}'. Invalid XNB magic bytes")
        if data[3] != ord("w"):
            raise ContentLoadException(f"Error loading '{asset_name}'. Unsupported XNB platform {data[3]}")
        if data[4] != 5:
            raise ContentLoadException(f"Error loading '{asset_name}'. Unsupported XNB version {data[4]}")
        flags = data[5]
        if flags & 0x40:
            raise ContentLoadException(f"Error loading '{asset_name}'. LZ4 XNB is not an XNA 4.0 format")
        if flags & ~0x80:
            raise ContentLoadException(f"Error loading '{asset_name}'. Invalid XNB flags 0x{flags:02x}")
        declared_size = int.from_bytes(data[6:10], "little", signed=False)
        if declared_size != len(data):
            raise ContentLoadException(
                f"Error loading '{asset_name}'. XNB declares {declared_size} bytes, stream has {len(data)}"
            )
        if flags & 0x80:
            if len(data) < 14:
                raise ContentLoadException(f"Error loading '{asset_name}'. Truncated LZX payload header")
            decompressed_size = int.from_bytes(data[10:14], "little", signed=True)
            if decompressed_size < 0:
                raise ContentLoadException(f"Error loading '{asset_name}'. Negative decompressed size")
            from ._lzx import _decompress_xnb_lzx
            payload = _decompress_xnb_lzx(data[14:], decompressed_size, asset_name)
        else:
            payload = data[10:]
        return cls._create(manager, payload, asset_name, record_disposable)

    @property
    def ContentManager(self) -> "ContentManager":
        return self._content_manager

    @property
    def AssetName(self) -> str:
        return self._asset_name

    def ReadObject(self, *args: object):
        if len(args) == 0:
            return self._read_indexed(None, False)
        if len(args) == 1:
            if isinstance(args[0], ContentTypeReader):
                return self._read_and_record(args[0], None, False)
            return self._read_indexed(args[0], args[0] is not None)
        if len(args) == 2 and isinstance(args[0], ContentTypeReader):
            return self._read_and_record(args[0], args[1], args[1] is not None)
        raise TypeError("ReadObject expects (), existingInstance, typeReader, or typeReader and existingInstance")

    def ReadRawObject(self, *args: object):
        if len(args) == 1 and isinstance(args[0], ContentTypeReader):
            return self._read_and_record(args[0], None, False)
        if len(args) == 2 and isinstance(args[0], ContentTypeReader):
            return self._read_and_record(args[0], args[1], args[1] is not None)
        if len(args) in (0, 1):
            raise NotImplementedError(
                "ReadRawObject[T] without an explicit ContentTypeReader cannot recover Python's erased T"
            )
        raise TypeError("ReadRawObject expects (), existingInstance, typeReader, or typeReader and existingInstance")

    def ReadSharedResource(self, fixup: Callable[[T], None]) -> None:
        if not callable(fixup):
            raise TypeError("fixup must be callable")
        index = self._read_7bit()
        if index == 0:
            return
        if index < 1 or index > self._shared_count:
            raise self._failure(
                f"invalid shared resource index {index}; only {self._shared_count} resources exist"
            )
        self._shared_fixups[index - 1].append(fixup)

    def ReadExternalReference(self):
        reference = self.ReadString()
        if not reference:
            return None
        separator = max(self.AssetName.rfind("/"), self.AssetName.rfind("\\"))
        parent = "" if separator < 0 else self.AssetName[:separator]
        combined = reference if not parent else f"{parent}/{reference}"
        return self.ContentManager.Load(_normalize_asset_name(combined))

    def ReadVector2(self) -> Vector2:
        return Vector2(self.ReadSingle(), self.ReadSingle())

    def ReadVector3(self) -> Vector3:
        return Vector3(self.ReadSingle(), self.ReadSingle(), self.ReadSingle())

    def ReadVector4(self) -> Vector4:
        return Vector4(self.ReadSingle(), self.ReadSingle(), self.ReadSingle(), self.ReadSingle())

    def ReadMatrix(self) -> Matrix:
        return Matrix(*(self.ReadSingle() for _ in range(16)))

    def ReadQuaternion(self) -> Quaternion:
        return Quaternion(self.ReadSingle(), self.ReadSingle(), self.ReadSingle(), self.ReadSingle())

    def ReadColor(self) -> Color:
        return Color(self.ReadByte(), self.ReadByte(), self.ReadByte(), self.ReadByte())

    def ReadSingle(self) -> float:
        return super().ReadSingle()

    def ReadDouble(self) -> float:
        return super().ReadDouble()

    def _read_7bit(self) -> int:
        try:
            return self.Read7BitEncodedInt()
        except Exception as error:
            raise ContentLoadException(
                f"Content asset '{self.AssetName}' has an invalid 7-bit integer", error
            ) from error

    def _failure(self, detail: str) -> ContentLoadException:
        return ContentLoadException(f"Content asset '{self.AssetName}' is not a valid XNB: {detail}")

    def _read_indexed(self, existing: object, has_existing: bool):
        index = self._read_7bit()
        if index == 0:
            return None
        if index < 1 or index > len(self._type_readers):
            raise self._failure(f"invalid type reader index {index}")
        return self._read_and_record(self._type_readers[index - 1], existing, has_existing)

    def _read_and_record(self, reader: ContentTypeReader, existing: object, has_existing: bool):
        if has_existing and not isinstance(existing, reader.TargetType):
            raise TypeError(
                f"existingInstance must be compatible with {reader.TargetType.__name__}"
            )
        try:
            value = reader.Read(self, existing)
        except ContentLoadException:
            raise
        except Exception as error:
            raise ContentLoadException(
                f"Content type reader '{type(reader).__name__}' failed while loading '{self.AssetName}'",
                error,
            ) from error
        if value is not None and not isinstance(value, reader.TargetType):
            if _is_disposable(value):
                try:
                    _dispose_asset(value)
                except Exception:
                    pass
            raise ContentLoadException(
                f"Content type reader '{type(reader).__name__}' declared target "
                f"'{reader.TargetType.__name__}' but returned '{type(value).__name__}'"
            )
        if has_existing and value is not existing:
            if _is_disposable(value):
                try:
                    _dispose_asset(value)
                except Exception:
                    pass
            raise RuntimeError(
                "ContentTypeReader returned a replacement instead of populating the existing instance"
            )
        if not has_existing and _is_disposable(value) and self._record_disposable is not None:
            self._record_disposable(value)
        return value

    def _read_asset(self):
        self._type_readers = self._reader_manager._load_asset_readers(self)
        self._shared_count = self._read_7bit()
        if self._shared_count < 0 or self._shared_count > 1_000_000:
            raise self._failure(f"invalid shared resource count {self._shared_count}")
        self._shared_fixups = [[] for _ in range(self._shared_count)]
        root = self._read_indexed(None, False)
        resources = [self._read_indexed(None, False) for _ in range(self._shared_count)]
        for index, resource in enumerate(resources):
            for fixup in tuple(self._shared_fixups[index]):
                fixup(resource)
        complete = getattr(root, "_content_fixups_complete", None)
        if callable(complete):
            complete()
        return root


def _normalize_asset_name(value: str) -> str:
    if value is None:
        raise TypeError("assetName cannot be None")
    if not isinstance(value, str):
        raise TypeError("assetName must be str")
    if not value:
        raise ValueError("assetName must not be empty")
    if "\0" in value:
        raise ValueError("assetName cannot contain NUL")
    portable = value.replace("\\", "/")
    if portable.startswith("/") or re.match(r"^[A-Za-z]:", portable):
        raise ValueError("assetName must be relative to the Content root")
    parts: list[str] = []
    for part in PurePosixPath(portable).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("assetName escapes the Content root")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("assetName must identify an asset")
    return "/".join(parts)


def _is_disposable(value: object) -> bool:
    return value is not None and (
        callable(getattr(value, "Dispose", None)) or callable(getattr(value, "_dispose", None))
    )


def _dispose_asset(value: object) -> None:
    dispose = getattr(value, "Dispose", None)
    if callable(dispose):
        dispose()
        return
    private = getattr(value, "_dispose", None)
    if callable(private):
        private()


class ContentManager:
    def __init__(self, serviceProvider: object, rootDirectory: str = "") -> None:
        if serviceProvider is None:
            raise TypeError("serviceProvider cannot be None")
        if rootDirectory is None:
            raise TypeError("rootDirectory cannot be None")
        if not isinstance(rootDirectory, str):
            raise TypeError("rootDirectory must be str")
        self._disposed = False
        self._service_provider = serviceProvider
        self._root_directory = rootDirectory
        self._loaded_assets: dict[str, object] = {}
        self._disposable_assets: list[object] = []
        self._disposable_identities: set[int] = set()
        self._loading_assets: list[str] = []

    @property
    def ServiceProvider(self) -> object:
        return self._service_provider

    @property
    def RootDirectory(self) -> str:
        return self._root_directory

    @RootDirectory.setter
    def RootDirectory(self, value: str) -> None:
        self._ensure_open()
        if value is None:
            raise TypeError("RootDirectory cannot be None")
        if not isinstance(value, str):
            raise TypeError("RootDirectory must be str")
        if self._loaded_assets:
            raise RuntimeError("RootDirectory cannot change while assets are loaded")
        self._root_directory = value

    def Load(self, assetName: str):
        self._ensure_open()
        normalized = _normalize_asset_name(assetName)
        key = normalized.casefold()
        if key in self._loaded_assets:
            return self._loaded_assets[key]
        if key in self._loading_assets:
            start = self._loading_assets.index(key)
            cycle = " -> ".join((*self._loading_assets[start:], key))
            raise ContentLoadException(f"Circular external content reference: {cycle}")

        acquired: list[object] = []
        acquired_ids: set[int] = set()

        def record(value: object) -> None:
            if not _is_disposable(value):
                raise TypeError("recordDisposableObject requires a disposable object")
            identity = id(value)
            if identity not in acquired_ids and identity not in self._disposable_identities:
                acquired_ids.add(identity)
                acquired.append(value)

        self._loading_assets.append(key)
        try:
            value = self.ReadAsset(normalized, record)
            self._loaded_assets[key] = value
            self._disposable_assets.extend(acquired)
            self._disposable_identities.update(acquired_ids)
            return value
        except Exception:
            for disposable in reversed(acquired):
                try:
                    _dispose_asset(disposable)
                except Exception:
                    pass
            raise
        finally:
            self._loading_assets.pop()

    def OpenStream(self, assetName: str) -> BinaryIO:
        self._ensure_open()
        normalized = _normalize_asset_name(assetName)
        root = self._root_directory.replace("\\", "/")
        combined = _normalize_asset_name(f"{root}/{normalized}" if root else normalized)
        from .._title import TitleContainer
        return TitleContainer.OpenStream(f"{combined}.xnb")

    def ReadAsset(self, assetName: str, recordDisposableObject: Callable[[object], None]):
        self._ensure_open()
        normalized = _normalize_asset_name(assetName)
        if not callable(recordDisposableObject):
            raise TypeError("recordDisposableObject must be callable")
        stream = None
        primary: Exception | None = None
        try:
            stream = self.OpenStream(normalized)
            if not hasattr(stream, "read"):
                raise TypeError("OpenStream must return a readable binary stream")
            payload = stream.read()
            if not isinstance(payload, (bytes, bytearray, memoryview)):
                raise TypeError("content stream read() must return bytes")
            reader = ContentReader._from_xnb(
                self, bytes(payload), normalized, recordDisposableObject
            )
            try:
                return reader._read_asset()
            finally:
                reader.close()
        except ContentLoadException as error:
            primary = error
            raise
        except Exception as error:
            primary = error
            raise ContentLoadException(
                f"Could not deserialize content asset '{normalized}'", error
            ) from error
        finally:
            if stream is not None:
                close = getattr(stream, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception as close_error:
                        if primary is not None:
                            primary.add_note(f"stream close also failed: {close_error}")
                        else:
                            raise

    def Unload(self) -> None:
        self._ensure_open()
        for disposable in tuple(self._disposable_assets):
            prepare=getattr(disposable,"_content_before_unload",None)
            if callable(prepare):prepare()
        disposables = tuple(reversed(self._disposable_assets))
        self._loaded_assets.clear()
        self._disposable_assets.clear()
        self._disposable_identities.clear()
        self._loading_assets.clear()
        first_error: Exception | None = None
        for disposable in disposables:
            try:
                _dispose_asset(disposable)
            except Exception as error:
                if first_error is None:
                    first_error = error
                else:
                    first_error.add_note(f"another content disposal failed: {error}")
        if first_error is not None:
            raise first_error

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if args and not args[0]:
            return
        if self._disposed:
            return
        first_error: Exception | None = None
        try:
            self.Unload()
        except Exception as error:
            first_error = error
        finally:
            self._disposed = True
        if first_error is not None:
            raise first_error

    def _ensure_open(self) -> None:
        if self._disposed:
            raise RuntimeError("ContentManager is disposed")

    def _graphics_device(self):
        from ..Graphics import GraphicsDevice, IGraphicsDeviceService

        provider = self.ServiceProvider
        service = None
        get_service = getattr(provider, "GetService", None)
        if callable(get_service):
            service = get_service(IGraphicsDeviceService)
            if service is None:
                service = get_service(GraphicsDevice)
        elif isinstance(provider, Mapping):
            service = provider.get(IGraphicsDeviceService, provider.get(GraphicsDevice))
        if isinstance(service, GraphicsDevice):
            return service
        device = getattr(service, "GraphicsDevice", None)
        if isinstance(device, GraphicsDevice):
            return device
        raise ContentLoadException("Graphics content requires an IGraphicsDeviceService")

    def __enter__(self) -> "ContentManager":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.Dispose()


class ResourceContentManager(ContentManager):
    def __init__(self, serviceProvider: object, resourceManager: object) -> None:
        super().__init__(serviceProvider)
        if resourceManager is None:
            raise TypeError("resourceManager cannot be None")
        self._resource_manager = resourceManager

    def OpenStream(self, assetName: str) -> BinaryIO:
        self._ensure_open()
        normalized = _normalize_asset_name(assetName)
        manager = self._resource_manager
        try:
            if isinstance(manager, Mapping):
                value = manager.get(normalized)
            else:
                getter = getattr(manager, "GetObject", None)
                if not callable(getter):
                    getter = getattr(manager, "get_object", None)
                if not callable(getter):
                    raise TypeError("resourceManager must be a Mapping or provide GetObject(assetName)")
                value = getter(normalized)
        except KeyError:
            value = None
        if value is None:
            raise ContentLoadException(f"Resource '{normalized}' was not found")
        if isinstance(value, (bytes, bytearray, memoryview)):
            return BytesIO(bytes(value))
        read = getattr(value, "read", None)
        if callable(read):
            payload = read()
            if not isinstance(payload, (bytes, bytearray, memoryview)):
                raise ContentLoadException(f"Resource '{normalized}' stream did not return bytes")
            return BytesIO(bytes(payload))
        raise ContentLoadException(f"Resource '{normalized}' is not stored as bytes or a binary stream")


ContentLoadException.__xna_arities__ = {"__init__": {0, 1, 2}}
ContentSerializerAttribute.__xna_arities__ = {"__init__": {0}, "Clone": {0}}
ContentSerializerCollectionItemNameAttribute.__xna_arities__ = {"__init__": {1}}
ContentSerializerIgnoreAttribute.__xna_arities__ = {"__init__": {0}}
ContentSerializerRuntimeTypeAttribute.__xna_arities__ = {"__init__": {1}}
ContentSerializerTypeVersionAttribute.__xna_arities__ = {"__init__": {1}}
ContentTypeReader.__xna_arities__ = {"__init__": {1}, "Initialize": {1}, "Read": {2}}
ContentTypeReaderOfT.__xna_arities__ = {"__init__": {0}, "Read": {2}}
ContentTypeReaderManager.__xna_arities__ = {"GetTypeReader": {1}}
ContentReader.__xna_arities__ = {
    "ReadObject": {0, 1, 2}, "ReadRawObject": {0, 1, 2},
    "ReadSharedResource": {1}, "ReadExternalReference": {0},
    "ReadVector2": {0}, "ReadVector3": {0}, "ReadVector4": {0},
    "ReadMatrix": {0}, "ReadQuaternion": {0}, "ReadColor": {0},
    "ReadSingle": {0}, "ReadDouble": {0},
}
ContentManager.__xna_arities__ = {
    "__init__": {1, 2}, "Dispose": {0, 1}, "Unload": {0}, "Load": {1},
    "OpenStream": {1}, "ReadAsset": {2},
}
ResourceContentManager.__xna_arities__ = {
    "__init__": {2}, "OpenStream": {1}, "Dispose": {0, 1},
}
