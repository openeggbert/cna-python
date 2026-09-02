"""Animation, as the pipeline carries it.

An ``AnimationContent`` is a named animation on a node; its ``Channels`` are one
per bone, and a channel is a list of keyframes sorted by time. The sort is not
incidental: a runtime reads keyframes in order and interpolates between
neighbours, so a channel that stored them in insertion order would play the
animation wrong rather than fail.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterator

from .... import Matrix
from .._collections import NamedValueDictionaryOfT
from .._identity import ContentItem


class AnimationKeyframe:
    """One bone pose at one time.

    Comparable by time, which is what keeps a channel sorted. Two keyframes at
    the same time compare equal, and a channel keeps both -- an animation with a
    duplicated time is a content error for a processor to report, not something
    a collection should silently drop.
    """

    __slots__ = ("_time", "_transform")

    def __init__(self, time: timedelta, transform: Matrix) -> None:
        if not isinstance(time, timedelta):
            raise TypeError(f"time must be a timedelta, not {type(time).__name__}")
        if not isinstance(transform, Matrix):
            raise TypeError(
                f"transform must be a Matrix, not {type(transform).__name__}")
        self._time = time
        self._transform = transform

    @property
    def Time(self) -> timedelta:
        return self._time

    @property
    def Transform(self) -> Matrix:
        return self._transform

    @Transform.setter
    def Transform(self, value: Matrix) -> None:
        if not isinstance(value, Matrix):
            raise TypeError(f"Transform must be a Matrix, not {type(value).__name__}")
        self._transform = value

    def CompareTo(self, other: "AnimationKeyframe") -> int:
        if not isinstance(other, AnimationKeyframe):
            raise TypeError(
                f"other must be an AnimationKeyframe, not {type(other).__name__}")
        if self._time < other._time:
            return -1
        return 1 if self._time > other._time else 0

    def __repr__(self) -> str:
        return f"AnimationKeyframe({self._time!r})"


class AnimationChannel:
    """One bone's keyframes, kept sorted by time.

    ``Add`` answers the index the keyframe landed at, which is XNA's signature
    and is the only way a caller can find a keyframe again after the collection
    has put it where it belongs.
    """

    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items: list[AnimationKeyframe] = []

    def Add(self, item: AnimationKeyframe) -> int:
        if not isinstance(item, AnimationKeyframe):
            raise TypeError(
                f"item must be an AnimationKeyframe, not {type(item).__name__}")
        # The insertion point is the first keyframe strictly later than this
        # one, so equal times keep the order they were added in.
        index = len(self._items)
        for position, present in enumerate(self._items):
            if present.Time > item.Time:
                index = position
                break
        self._items.insert(index, item)
        return index

    def Clear(self) -> None:
        self._items.clear()

    def Contains(self, item: AnimationKeyframe) -> bool:
        return any(present is item for present in self._items)

    def IndexOf(self, item: AnimationKeyframe) -> int:
        for index, present in enumerate(self._items):
            if present is item:
                return index
        return -1

    def Remove(self, item: AnimationKeyframe) -> bool:
        index = self.IndexOf(item)
        if index < 0:
            return False
        del self._items[index]
        return True

    def RemoveAt(self, index: int) -> None:
        self._check(index)
        del self._items[index]

    def GetEnumerator(self) -> Iterator[AnimationKeyframe]:
        return iter(self._items)

    @property
    def Count(self) -> int:
        return len(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[AnimationKeyframe]:
        return iter(self._items)

    def __getitem__(self, index: int) -> AnimationKeyframe:
        self._check(index)
        return self._items[index]

    def __contains__(self, item: object) -> bool:
        return any(present is item for present in self._items)

    def _check(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError(f"index must be an int, not {type(index).__name__}")
        if not 0 <= index < len(self._items):
            raise IndexError(f"index {index} is outside 0..{len(self._items) - 1}")


class AnimationChannelDictionary(NamedValueDictionaryOfT[AnimationChannel]):
    """A named animation's channels, one per bone."""

    __slots__ = ()
    _element = AnimationChannel


class AnimationContent(ContentItem):
    """One named animation.

    ``Duration`` is a value a caller sets, not one derived from the channels:
    an animation may end after its last keyframe -- a pose held to the end of a
    bar -- and shortening it to the last keyframe would change the timing.
    """

    __slots__ = ("_duration", "_channels")

    def __init__(self) -> None:
        super().__init__()
        self._duration = timedelta(0)
        self._channels = AnimationChannelDictionary()

    @property
    def Duration(self) -> timedelta:
        return self._duration

    @Duration.setter
    def Duration(self, value: timedelta) -> None:
        if not isinstance(value, timedelta):
            raise TypeError(f"Duration must be a timedelta, not {type(value).__name__}")
        self._duration = value

    @property
    def Channels(self) -> AnimationChannelDictionary:
        return self._channels


class AnimationContentDictionary(NamedValueDictionaryOfT[AnimationContent]):
    """Every animation on one node, by name."""

    __slots__ = ()
    _element = AnimationContent
