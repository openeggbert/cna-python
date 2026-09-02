"""The pipeline's collection vocabulary.

Three shapes, and the difference between them is the whole point:

``_Collection``
    XNA's ``Collection<T>``, which is a *mutable list with overridable hooks*.
    Every mutation funnels through ``InsertItem``/``SetItem``/``RemoveItem``/
    ``ClearItems``, which is how :class:`ChildCollectionOfT` keeps a parent
    pointer in step without the caller doing anything.
``_ReadOnlyCollection``
    a view a caller may read and not write. XNA hands these out where the
    pipeline owns the list.
``NamedValueDictionaryOfT``
    a string-keyed dictionary with the same overridable hooks, and a declared
    element type that the intermediate serializer reads to decide what to write.

They are composition bases: ``Collection<T>`` and ``ReadOnlyCollection<T>`` are
BCL types with no Python identity of their own, so they never appear in a stub.
"""

from __future__ import annotations

from typing import Generic, Iterator, MutableSequence, TypeVar

T = TypeVar("T")
TParent = TypeVar("TParent")
TChild = TypeVar("TChild")


class _Collection(Generic[T]):
    """``System.Collections.ObjectModel.Collection<T>``.

    The four protected hooks are ``InsertItem``, ``SetItem``, ``RemoveItem`` and
    ``ClearItems``; XNA names them exactly that and derived pipeline types
    override them, so they keep their CLR names here rather than becoming
    ``_insert_item``. Everything public routes through one of them.
    """

    __slots__ = ("_items",)

    #: The element type a derived collection accepts, when it declares one.
    #: Checked here rather than in an override, because XNA's own derived
    #: collections declare ``InsertItem``/``SetItem`` only where they have
    #: something else to do in them -- and a type check that added those members
    #: would be adding members XNA does not have.
    _element_type: type | None = None

    def __init__(self, items: MutableSequence[T] | None = None) -> None:
        self._items: list[T] = list(items) if items is not None else []

    # -- the overridable hooks ----------------------------------------------

    def InsertItem(self, index: int, item: T) -> None:
        self._items.insert(index, self._checked_element(item))

    def SetItem(self, index: int, item: T) -> None:
        self._items[index] = self._checked_element(item)

    def _checked_element(self, item: T) -> T:
        if self._element_type is not None and not isinstance(item, self._element_type):
            raise TypeError(
                f"{type(self).__name__} holds {self._element_type.__name__}, "
                f"not {type(item).__name__}")
        return item

    def RemoveItem(self, index: int) -> None:
        del self._items[index]

    def ClearItems(self) -> None:
        self._items.clear()

    # -- the public surface, all of it routed through the hooks --------------

    def Add(self, item: T) -> None:
        self.InsertItem(len(self._items), item)

    def Insert(self, index: int, item: T) -> None:
        if not 0 <= index <= len(self._items):
            raise IndexError(f"index {index} is outside 0..{len(self._items)}")
        self.InsertItem(index, item)

    def Remove(self, item: T) -> bool:
        index = self._index_of(item)
        if index < 0:
            return False
        self.RemoveItem(index)
        return True

    def RemoveAt(self, index: int) -> None:
        self._check(index)
        self.RemoveItem(index)

    def Clear(self) -> None:
        self.ClearItems()

    def Contains(self, item: T) -> bool:
        return self._index_of(item) >= 0

    def IndexOf(self, item: T) -> int:
        return self._index_of(item)

    def CopyTo(self, array: MutableSequence[T], arrayIndex: int) -> None:
        for offset, item in enumerate(self._items):
            array[arrayIndex + offset] = item

    @property
    def Count(self) -> int:
        return len(self._items)

    @property
    def IsReadOnly(self) -> bool:
        return False

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __getitem__(self, index: int) -> T:
        self._check(index)
        return self._items[index]

    def __setitem__(self, index: int, item: T) -> None:
        self._check(index)
        self.SetItem(index, item)

    def __contains__(self, item: object) -> bool:
        return self._index_of(item) >= 0

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._items!r})"

    # -- internals -----------------------------------------------------------

    def _check(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError(f"index must be an int, not {type(index).__name__}")
        if not 0 <= index < len(self._items):
            raise IndexError(f"index {index} is outside 0..{len(self._items) - 1}")

    def _index_of(self, item: object) -> int:
        # Identity first, then equality: two distinct ContentItems can compare
        # equal by default only if one *is* the other, but a value element such
        # as an index or a Vector3 must still be found by value.
        for index, present in enumerate(self._items):
            if present is item or present == item:
                return index
        return -1


class _ReadOnlyCollection(Generic[T]):
    """``System.Collections.ObjectModel.ReadOnlyCollection<T>``.

    A *view*, not a copy: the pipeline builds the backing list and hands this
    out, and a later append by the owner is visible through it. That is what
    XNA does, and a copy would quietly disagree the moment a processor added a
    mesh after the collection was read.
    """

    __slots__ = ("_items",)

    def __init__(self, items: MutableSequence[T]) -> None:
        self._items = items

    def Contains(self, item: T) -> bool:
        return any(present is item or present == item for present in self._items)

    def IndexOf(self, item: T) -> int:
        for index, present in enumerate(self._items):
            if present is item or present == item:
                return index
        return -1

    def CopyTo(self, array: MutableSequence[T], index: int) -> None:
        for offset, item in enumerate(self._items):
            array[index + offset] = item

    @property
    def Count(self) -> int:
        return len(self._items)

    @property
    def IsReadOnly(self) -> bool:
        return True

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __getitem__(self, index: int) -> T:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError(f"index must be an int, not {type(index).__name__}")
        if not 0 <= index < len(self._items):
            raise IndexError(f"index {index} is outside 0..{len(self._items) - 1}")
        return self._items[index]

    def __contains__(self, item: object) -> bool:
        return self.IndexOf(item) >= 0  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({list(self._items)!r})"


class ChildCollectionOfT(_Collection[TChild], Generic[TParent, TChild]):
    """A collection that owns its members' parent pointer.

    Adding a child sets its parent; removing one clears it. XNA leaves *where*
    the pointer lives to the derived class -- a mesh's geometry keeps it in one
    field, a node's children in another -- so :meth:`GetParent` and
    :meth:`SetParent` are the two abstract halves and everything else is here.
    """

    __slots__ = ("_parent",)

    def __init__(self, parent: TParent) -> None:
        super().__init__()
        self._parent = parent

    @property
    def _owner(self) -> TParent:
        return self._parent

    def GetParent(self, child: TChild) -> TParent:
        raise NotImplementedError(
            f"{type(self).__name__}.GetParent must be overridden")

    def SetParent(self, child: TChild, parent: TParent) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.SetParent must be overridden")

    def InsertItem(self, index: int, item: TChild) -> None:
        self._adopt(item)
        super().InsertItem(index, item)

    def SetItem(self, index: int, item: TChild) -> None:
        self._adopt(item)
        self.SetParent(self._items[index], None)  # type: ignore[arg-type]
        super().SetItem(index, item)

    def RemoveItem(self, index: int) -> None:
        self.SetParent(self._items[index], None)  # type: ignore[arg-type]
        super().RemoveItem(index)

    def ClearItems(self) -> None:
        for item in list(self._items):
            self.SetParent(item, None)  # type: ignore[arg-type]
        super().ClearItems()

    def _adopt(self, item: TChild) -> None:
        if item is None:
            raise ValueError("a child collection may not hold None")
        existing = self.GetParent(item)
        if existing is not None and existing is not self._parent:
            raise ValueError(
                f"{type(item).__name__} already belongs to another "
                f"{type(existing).__name__}")
        self.SetParent(item, self._parent)


class NamedValueDictionaryOfT(Generic[T]):
    """A string-keyed dictionary with XNA's four overridable hooks.

    ``DefaultSerializerType`` is what the intermediate serializer asks when a
    value's own type is not written down: it is the declared element type, and
    it is a property rather than a constructor argument because XNA's derived
    dictionaries fix it.
    """

    __slots__ = ("_values",)

    #: The declared element type, overridden by every derived dictionary.
    _element: type = object

    def __init__(self) -> None:
        self._values: dict[str, T] = {}

    # -- the overridable hooks ----------------------------------------------

    def AddItem(self, key: str, value: T) -> None:
        self._values[self._key(key)] = value

    def ClearItems(self) -> None:
        self._values.clear()

    def RemoveItem(self, key: str) -> bool:
        return self._values.pop(self._key(key), _MISSING) is not _MISSING

    def SetItem(self, key: str, value: T) -> None:
        self._values[self._key(key)] = value

    # -- the public surface --------------------------------------------------

    def Add(self, key: str, value: T) -> None:
        name = self._key(key)
        if name in self._values:
            raise ValueError(f"an entry named {name!r} is already present")
        self.AddItem(name, self._checked(value))

    def Clear(self) -> None:
        self.ClearItems()

    def ContainsKey(self, key: str) -> bool:
        return self._key(key) in self._values

    def Remove(self, key: str) -> bool:
        return self.RemoveItem(key)

    def TryGetValue(self, key: str) -> tuple[bool, T | None]:
        """XNA's ``out`` parameter becomes the second half of the answer."""
        name = self._key(key)
        if name in self._values:
            return True, self._values[name]
        return False, None

    def GetEnumerator(self):
        return iter(self._values.items())

    @property
    def DefaultSerializerType(self) -> type:
        return self._element

    @property
    def Count(self) -> int:
        return len(self._values)

    @property
    def Keys(self):
        return tuple(self._values)

    @property
    def Values(self):
        return tuple(self._values.values())

    def __getitem__(self, key: str) -> T:
        name = self._key(key)
        if name not in self._values:
            raise KeyError(name)
        return self._values[name]

    def __setitem__(self, key: str, value: T) -> None:
        self.SetItem(self._key(key), self._checked(value))

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self):
        return iter(self._values.items())

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._values

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._values!r})"

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _key(key: str) -> str:
        if not isinstance(key, str):
            raise TypeError(f"key must be a str, not {type(key).__name__}")
        if not key:
            raise ValueError("key must not be empty")
        return key

    def _checked(self, value: T) -> T:
        if self._element is not object and value is not None \
                and not isinstance(value, self._element):
            raise TypeError(
                f"{type(self).__name__} holds {self._element.__name__}, "
                f"not {type(value).__name__}")
        return value


class OpaqueDataDictionary(NamedValueDictionaryOfT[object]):
    """A processor's parameters, by name, with no declared element type.

    ``GetValue`` is the reason this type exists rather than a plain dictionary:
    a processor asks for a parameter it understands and says what it wants when
    the parameter is absent, which is what makes a processor runnable with no
    parameters at all.
    """

    __slots__ = ()
    _element = object

    def GetValue(self, key: str, defaultValue: object) -> object:
        """The value stored under ``key``, or ``defaultValue`` if there is none.

        A stored ``None`` is a value, and is returned as one -- an absent key
        and a key set to nothing are different states, and a processor that
        cleared a parameter deliberately must not silently get the default back.
        """
        name = self._key(key)
        if name not in self._values:
            return defaultValue
        return self._values[name]

    def GetContentAsXml(self) -> str:
        """Every parameter, as the intermediate XML the build cache stores.

        The build cache compares this text to decide whether a processor's
        parameters changed since the last build, so it has to be stable: the
        keys are written in sorted order rather than insertion order, and the
        values go through the same serializer that writes an intermediate file.
        """
        from .Serialization.Intermediate import IntermediateSerializer

        return IntermediateSerializer._opaque_data_xml(self)


class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<missing>"


_MISSING = _Missing()
