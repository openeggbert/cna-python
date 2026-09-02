"""What went wrong, in the categories CNA's compiled-content ABI actually uses.

These are **CNA** errors, not XNA ones. A `.cnb` file has no XNA counterpart, so
translating its refusals into ``ContentLoadException`` would claim an equivalence
that does not exist and would lose the reason CNA gave. The strict XNA
``ContentManager`` keeps raising exactly what it raised before; nothing here
reaches it.

There is deliberately not one class per C result code. A caller acts on a
handful of distinctions -- is the file bad, is this build unable to read it, is
something missing, did a bound stop it -- and the exact code and CNA's own
message stay available on every instance for the cases where it matters.
"""

from __future__ import annotations

__all__ = [
    "CnbError",
    "CnbFormatError",
    "CnbUnsupportedError",
    "CnbMissingReferenceError",
    "CnbLimitError",
    "CnbInternalError",
]


class CnbError(Exception):
    """Base of every failure the compiled-content extension reports.

    ``result`` is CNA's own result code and ``category`` its error category,
    both preserved verbatim; ``native_message`` is the diagnostic CNA produced,
    which usually names the offending offset or field.
    """

    def __init__(self, operation: str, result: int, category: int | None,
                 native_message: str) -> None:
        self.operation = operation
        self.result = int(result)
        self.category = None if category is None else int(category)
        self.native_message = native_message
        detail = native_message or f"{operation} failed with CNA result {result}"
        super().__init__(detail)


class CnbFormatError(CnbError):
    """The bytes are not a valid `.cnb` document, or not the one that was expected.

    Covers every structural refusal: a bad magic, a failed checksum, a truncated
    chunk, a duplicate singleton, an unknown mandatory chunk, malformed UTF-8, a
    schema whose declared counts disagree with its payload lengths, and an asset
    type or schema version other than the one a decoder asked for.
    """


class CnbUnsupportedError(CnbError):
    """The file is well-formed but this build cannot act on it.

    A compression codec compiled out, an audio encoding the WAV importer refuses
    by name rather than resampling, or a loader whose product cannot cross the C
    boundary.
    """


class CnbMissingReferenceError(CnbError):
    """A named file or registration the operation needed does not exist.

    A `.cnj` sidecar that is absent, an image path that cannot be opened, or a
    document whose asset type has no registered loader.
    """


class CnbLimitError(CnbError):
    """A read limit or a fixed-width bound refused the value before allocating.

    This is the safety refusal, not a defect: a hostile count is meant to reach
    it. ``CnbReadLimits`` says which bound applied.
    """


class CnbInternalError(CnbError):
    """CNA failed for a reason that is none of the above.

    Out of memory, an internal invariant, a thread rule, or a shutdown in
    progress. It is kept distinct so it is never mistaken for a statement about
    the caller's file.
    """
