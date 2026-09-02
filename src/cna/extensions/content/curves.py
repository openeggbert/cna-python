"""The `.cnb` ``Curve`` codec, over the strict XNA ``Curve`` value type.

A curve is one place where the strict XNA type *is* exactly the natural public
representation: ``Microsoft.Xna.Framework.Curve`` already carries every field the
`.cnb` schema stores -- both loop types and each key's position, value, tangents
and continuity -- so inventing a ``CnbCurveData`` beside it would be a second
spelling of the same value with nothing to add.

The dependency runs extension -> strict. The XNA ``Curve`` is unchanged, stays
pure managed, and does not know this module exists.

**A dependency worth stating.** ``cna_cnb_encode_curve`` takes a *native* curve
handle and ``cna_cnb_decode_curve`` produces one, so the codec cannot be reached
from a managed-only curve at all. Eleven ``curve.h`` routes are therefore
imported to build a native curve from managed keys and read one back. That is a
dependency of the selected CNB profile, not a decision to bind ``curve.h``: the
native curve exists only inside these two functions and is destroyed before
either returns.
"""

from __future__ import annotations

import ctypes as c
from enum import IntEnum

from Microsoft.Xna.Framework import Curve, CurveContinuity, CurveKey, CurveLoopType

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

__all__ = ["CURVE_SCHEMA_VERSION", "CurveChunk", "decode_curve", "encode_curve"]

#: Highest ``Curve`` schema version this CNA generation understands.
CURVE_SCHEMA_VERSION = _abi.CNA_CNB_CURVE_SCHEMA_VERSION


class CurveChunk(IntEnum):
    """The two chunk identifiers the curve schema writes."""

    Header = _abi.CNA_CNB_CURVE_CHUNK_HEADER
    Keys = _abi.CNA_CNB_CURVE_CHUNK_KEYS


class _NativeCurve:
    """A native ``Curve`` built for the length of one codec call and no longer."""

    def __init__(self) -> None:
        self.handle = _support.NativeHandle(
            _support.out_handle("cna_curve_create"), "cna_curve_destroy", "native curve")

    def close(self) -> None:
        self.handle.close()

    def __enter__(self) -> "_NativeCurve":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def value(self) -> c.c_uint64:
        return c.c_uint64(self.handle.value)

    def _keys(self) -> _support.NativeHandle:
        # The collection view retains the curve, so it is closed first.
        return _support.NativeHandle(
            _support.out_handle("cna_curve_get_keys", self.value),
            "cna_curve_key_collection_destroy", "native curve keys", parent=self.handle)

    def load(self, curve: Curve) -> None:
        """Copies a managed curve's loop types and keys into the native one."""
        _support.call("cna_curve_set_pre_loop", self.value,
                      c.c_uint32(int(curve.PreLoop)))
        _support.call("cna_curve_set_post_loop", self.value,
                      c.c_uint32(int(curve.PostLoop)))
        keys = self._keys()
        try:
            for key in curve.Keys:
                native = _abi.CNA_CurveKey()
                native.position = float(key.Position)
                native.value = float(key.Value)
                native.tangent_in = float(key.TangentIn)
                native.tangent_out = float(key.TangentOut)
                native.continuity = int(key.Continuity)
                _support.call("cna_curve_key_collection_add",
                              c.c_uint64(keys.value), native)
        finally:
            keys.close()

    def store(self) -> Curve:
        """Builds a managed curve from the native one's loop types and keys."""
        curve = Curve()
        curve.PreLoop = CurveLoopType(
            _support.out_u32("cna_curve_get_pre_loop", self.value))
        curve.PostLoop = CurveLoopType(
            _support.out_u32("cna_curve_get_post_loop", self.value))
        keys = self._keys()
        try:
            count = _support.out_u64(
                "cna_curve_key_collection_get_count", c.c_uint64(keys.value))
            for index in range(count):
                native = _abi.CNA_CurveKey()
                _support.call("cna_curve_key_collection_get", c.c_uint64(keys.value),
                              c.c_int32(index), c.byref(native))
                curve.Keys.Add(CurveKey(
                    float(native.position), float(native.value),
                    float(native.tangent_in), float(native.tangent_out),
                    CurveContinuity(int(native.continuity))))
        finally:
            keys.close()
        return curve


def encode_curve(curve: Curve, *, content_name: str = "") -> bytes:
    """Encodes a ``Microsoft.Xna.Framework.Curve`` as a complete `.cnb` byte image.

    The managed curve is not modified and nothing native outlives the call.
    """
    if not isinstance(curve, Curve):
        raise TypeError("curve must be a Microsoft.Xna.Framework.Curve")
    view, keep = _support.string_view(content_name, "content_name")
    with _NativeCurve() as native:
        native.load(curve)
        result = _support.two_call_bytes("cna_cnb_encode_curve", (native.value, view))
    del keep
    return result


def decode_curve(document) -> Curve:
    """Decodes a ``Microsoft.Xna.Framework.Curve`` from a parsed container.

    What comes back is an ordinary managed curve with no native handle behind
    it: the native one CNA produced is read out and destroyed before this
    returns, so the caller has nothing to close.
    """
    handle = _support.out_handle("cna_cnb_decode_curve", document._value)
    native = _NativeCurve.__new__(_NativeCurve)
    native.handle = _support.NativeHandle(handle, "cna_curve_destroy", "native curve")
    try:
        return native.store()
    finally:
        native.close()
