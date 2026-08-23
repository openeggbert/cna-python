"""Private helpers implementing the normative Python language mapping."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary


class classproperty:
    """Read-only class property used for CLR static properties."""

    def __init__(self, getter: Callable[[type], Any]) -> None:
        self._getter = getter

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        return self._getter(owner if owner is not None else type(instance))

    def __set__(self, instance: object, value: object) -> None:
        raise AttributeError("static XNA value properties are read-only")


class staticproperty:
    """Mutable CLR static property, with assignment mediated by ``staticpropertymeta``."""

    def __init__(self, getter: Callable[[type], Any], setter: Callable[[type, object], None]) -> None:
        self.fget = getter
        self.fset = setter

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        return self.fget(owner if owner is not None else type(instance))

    def __set__(self, instance: object, value: object) -> None:
        self.fset(instance if isinstance(instance, type) else type(instance), value)


class staticpropertymeta(type):
    """Keeps class assignment from replacing a mutable static-property descriptor."""

    def __setattr__(cls, name: str, value: object) -> None:
        descriptor = cls.__dict__.get(name)
        if isinstance(descriptor, staticproperty):
            descriptor.__set__(cls, value)
            return
        super().__setattr__(name, value)


class _BoundEvent:
    def __init__(self, owner: object, descriptor: "Event") -> None:
        self._owner = owner
        self._descriptor = descriptor

    def __iadd__(self, handler: Callable[..., object]) -> "_BoundEvent":
        if not callable(handler):
            raise TypeError("event handler must be callable")
        self._descriptor._handlers_for(self._owner).append(handler)
        return self

    def __isub__(self, handler: Callable[..., object]) -> "_BoundEvent":
        handlers = self._descriptor._handlers_for(self._owner)
        try:
            handlers.remove(handler)
        except ValueError as error:
            raise ValueError("event handler is not subscribed") from error
        return self

    def __call__(self, *args: object, **kwargs: object) -> None:
        # Snapshotting gives stable ordering and permits deterministic self-removal.
        for handler in tuple(self._descriptor._handlers_for(self._owner)):
            handler(*args, **kwargs)


class Event:
    """Descriptor for mapped CLR events.

    Duplicates are retained, removal removes the first matching subscription,
    handlers run in subscription order, and exceptions propagate immediately.
    """

    def __init__(self) -> None:
        self._handlers: WeakKeyDictionary[object, list[Callable[..., object]]] = WeakKeyDictionary()

    def _handlers_for(self, owner: object) -> list[Callable[..., object]]:
        return self._handlers.setdefault(owner, [])

    def __get__(self, instance: object | None, owner: type | None = None) -> object:
        if instance is None:
            return self
        return _BoundEvent(instance, self)

    def __set__(self, instance: object, value: object) -> None:
        # ``obj.Event += fn`` performs descriptor assignment after __iadd__.
        if isinstance(value, _BoundEvent) and value._owner is instance and value._descriptor is self:
            return
        raise AttributeError("events support only += and -=")
