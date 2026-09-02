"""The pipeline's two failures.

``PipelineException`` is a build that could not proceed. ``InvalidContentException``
is content that is wrong, and it carries the identity of the content that is
wrong -- which is the difference that lets a build tool put an error on the right
line of the right file instead of on the processor that noticed.
"""

from __future__ import annotations

from ._identity import ContentIdentity


class PipelineException(Exception):
    """A build failure that is not attributable to one piece of content.

    XNA's ``params object[] messageArgs`` overload formats the message; Python
    has ``str.format``, and the argument list is applied with it so that a
    caller who passes arguments gets a formatted message rather than a tuple
    printed after one.
    """

    def __init__(self, *args: object) -> None:
        if not args:
            super().__init__()
            return
        message = args[0]
        if not isinstance(message, str):
            raise TypeError(
                f"message must be a str, not {type(message).__name__}")
        rest = args[1:]
        if len(rest) == 1 and isinstance(rest[0], BaseException):
            super().__init__(message)
            self.__cause__ = rest[0]
            return
        if rest:
            super().__init__(_format(message, rest))
            return
        super().__init__(message)


class InvalidContentException(Exception):
    """Content the pipeline understood well enough to reject.

    ``ContentIdentity`` is the whole point: the message says what is wrong and
    the identity says where, so a build tool can put the error on the line the
    artist has open.
    """

    def __init__(self, *args: object) -> None:
        self._content_identity: ContentIdentity | None = None
        if not args:
            super().__init__()
            return
        message = args[0]
        if not isinstance(message, str):
            raise TypeError(
                f"message must be a str, not {type(message).__name__}")
        rest = list(args[1:])
        if rest and isinstance(rest[0], (ContentIdentity, type(None))):
            # ``None`` is an identity that says nothing, which is what a caller
            # passes when the content it is rejecting has none. Refusing it
            # would make every raise site test for it first.
            self._content_identity = rest.pop(0)
        if len(rest) == 1 and isinstance(rest[0], BaseException):
            super().__init__(message)
            self.__cause__ = rest[0]
            return
        if rest:
            raise TypeError(
                "InvalidContentException expects (), message, "
                "message and innerException, message and contentIdentity, or "
                "message, contentIdentity and innerException")
        super().__init__(message)

    @property
    def ContentIdentity(self) -> ContentIdentity | None:
        return self._content_identity

    @ContentIdentity.setter
    def ContentIdentity(self, value: "ContentIdentity | None") -> None:
        if value is not None and not isinstance(value, ContentIdentity):
            raise TypeError("ContentIdentity must be a ContentIdentity, not "
                            f"{type(value).__name__}")
        self._content_identity = value

    def GetObjectData(self, info: object, context: object) -> None:
        """XNA's ``ISerializable`` half, projected onto a mapping.

        .NET binary serialization has no Python counterpart, so what is
        projected is the operation's *observable* effect: the exception's own
        state is written into the mapping it is handed, under the names XNA
        writes. A caller that wants to move an exception between processes has
        something real to move; nothing here pretends to be a
        ``SerializationInfo``.
        """
        try:
            info["Message"] = str(self)
            info["ContentIdentity"] = self._content_identity
        except TypeError as error:
            raise TypeError(
                "GetObjectData writes into a mutable mapping, and "
                f"{type(info).__name__} is not one") from error


def _format(message: str, arguments: tuple[object, ...]) -> str:
    try:
        return message.format(*arguments)
    except (IndexError, KeyError, ValueError):
        # A message with no placeholders, or one whose placeholders do not match
        # what was passed, is still a message: XNA's String.Format would throw,
        # and losing the message to a formatting error is worse than keeping it.
        return message


#: XNA's constructor arities, declared because both dispatchers are variadic.
#: ``PipelineException`` has (), (message), (message, innerException),
#: (message, messageArgs) and the serialization pair; ``InvalidContentException``
#: adds (message, contentIdentity) and (message, contentIdentity,
#: innerException). The serialization constructors are not projected: their two
#: parameters both map to ``object``, so the overload would be
#: indistinguishable from (message, innerException) at run time. That is a
#: LANGUAGE_MAPPING_LIMITATION, recorded as one rather than hidden behind an
#: overload nothing could dispatch.
PipelineException.__xna_arities__ = {"__init__": {0, 1, 2}}
InvalidContentException.__xna_arities__ = {"__init__": {0, 1, 2, 3}}
