#!/usr/bin/env python3
"""Compare canonical C headers, ctypes layouts, and an explicit ELF artifact."""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _cna_native import abi
from _cna_native import cnb_abi
from _cna_native import devices_abi
from _cna_native import engine_abi
from _cna_native import input_abi
from _cna_native import online_abi
from _cna_native.loader import FUNCTION_MANIFEST, QUALIFIED_ABI


TYPES = {
    value.__name__: value for value in (
        abi.CNA_StringView, abi.CNA_ErrorInfo, abi.CNA_GameTime, abi.CNA_CallbackError,
        abi.CNA_GameCallbacks, abi.CNA_GameFrameHooks, abi.CNA_GameCreateInfo,
        abi.CNA_Color, abi.CNA_Vector2, abi.CNA_Vector3, abi.CNA_Vector4,
        abi.CNA_AudioCapabilities, abi.CNA_SoundEffectCreateInfo,
        abi.CNA_SoundEffectInstanceInfo, abi.CNA_AudioEmitter,
        abi.CNA_AudioListener, abi.CNA_CueInfo,
        abi.CNA_VisualizationData, abi.CNA_VideoFrameEXT,
        abi.CNA_Quaternion, abi.CNA_Matrix,
        abi.CNA_Rectangle, abi.CNA_Viewport, abi.CNA_DisplayMode,
        abi.CNA_GraphicsAdapterInfo, abi.CNA_GraphicsFormatSelection,
        abi.CNA_PresentationParameters, abi.CNA_GraphicsDeviceInformation,
        abi.CNA_BlendState, abi.CNA_DepthStencilState, abi.CNA_RasterizerState,
        abi.CNA_SamplerState, abi.CNA_TextureSlotInfo,
        abi.CNA_VertexElement, abi.CNA_VertexBufferCreateInfo,
        abi.CNA_VertexBufferInfo, abi.CNA_VertexBufferTransfer,
        abi.CNA_VertexPositionColor, abi.CNA_VertexPositionColorTexture,
        abi.CNA_VertexPositionNormalTexture, abi.CNA_VertexPositionTexture,
        abi.CNA_VertexBufferBinding,
        abi.CNA_IndexBufferCreateInfo, abi.CNA_IndexBufferInfo,
        abi.CNA_IndexBufferTransfer, abi.CNA_RenderTarget2DCreateInfo,
        abi.CNA_RenderTargetCubeCreateInfo, abi.CNA_RenderTargetInfo,
        abi.CNA_RenderTargetBinding,
        abi.CNA_BackBufferReadback, abi.CNA_UserPrimitives, abi.CNA_UserIndices,
        abi.CNA_SpriteFontGlyph, abi.CNA_SpriteFontCreateInfo,
        abi.CNA_SpriteFontInfo,
        abi.CNA_Texture2DInfo, abi.CNA_Texture2DCreateInfo, abi.CNA_Texture2DTransfer,
        abi.CNA_Texture2DDecodeInfo,
        abi.CNA_Texture3DCreateInfo, abi.CNA_Texture3DInfo, abi.CNA_Texture3DTransfer,
        abi.CNA_TextureCubeCreateInfo, abi.CNA_TextureCubeInfo, abi.CNA_TextureCubeTransfer,
        abi.CNA_EffectParameterCreateInfo, abi.CNA_EffectParameterInfo,
        abi.CNA_EffectAnnotationCreateInfo, abi.CNA_EffectAnnotationInfo,
        abi.CNA_SpriteBatchBeginInfo,
        abi.CNA_SpriteCommand, abi.CNA_SpriteScaledCommand, abi.CNA_KeyboardState, abi.CNA_MouseState,
        abi.CNA_GamePadAnalogState, abi.CNA_GamePadState,
        abi.CNA_GamePadCapabilities,
        abi.CNA_TouchLocation, abi.CNA_TouchCapabilities, abi.CNA_TouchState,
        abi.CNA_GestureSample,
        cnb_abi.CNA_CnbReadLimits, cnb_abi.CNA_CnbChunkEntry,
        cnb_abi.CNA_CnbExternalReference, cnb_abi.CNA_CnbMetadata,
        cnb_abi.CNA_CnbTextureInfo, cnb_abi.CNA_CnbTextureTransform,
        cnb_abi.CNA_CnbSamplerState, cnb_abi.CNA_CnbModelLight,
        cnb_abi.CNA_CnbModelInfo, cnb_abi.CNA_CnbModelBone,
        cnb_abi.CNA_CnbModelPartInfo, cnb_abi.CNA_CnbMaterialInfo,
        cnb_abi.CNA_CnbMorphInfo, cnb_abi.CNA_CnbMeshInfo,
        cnb_abi.CNA_CnbSkeletonInfo, cnb_abi.CNA_CnbMorphWeightKeyInfo,
        cnb_abi.CNA_CnbSpriteFontInfo, cnb_abi.CNA_CnbSoundEffectInfo,
        cnb_abi.CNA_CnbVideoInfo, cnb_abi.CNA_CnbImageImportOptions,
        cnb_abi.CNA_KeyframeEXT, cnb_abi.CNA_BoneTrackEXTDescriptor,
        cnb_abi.CNA_AnimationClipEXTDescriptor, cnb_abi.CNA_CurveKey,
        cnb_abi.CNA_ContentManagerCreateInfo,
        *engine_abi.ENGINE_STRUCTURES,
        *devices_abi.DEVICES_STRUCTURES,
        *input_abi.INPUT_STRUCTURES,
        *online_abi.ONLINE_STRUCTURES,
    )
}

#: Every frozen `.cnb` wire constant, re-read from the header by the C probe and
#: compared against the value this binding uses.  A constant that drifts is a
#: silent misreading of every file already written, so none of them is trusted
#: from prose.
CNB_CONSTANT_PREFIXES = ("CNA_CNB_", "CNA_CLIP_TARGET_SPACE_",
                        "CNA_SURFACE_FORMAT_")

#: Every family ``tools/generate_family_abi.py`` generates, with the prefix its
#: exported tables carry.  Listing the modules rather than the tables means a
#: family that gains a structure, a callback or a constant is measured without
#: an edit here.
FAMILY_ABI_MODULES = (
    (engine_abi, "ENGINE"),
    (devices_abi, "DEVICES"),
    (input_abi, "INPUT"),
    (online_abi, "ONLINE"),
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cna-root", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--output")
    return parser.parse_args()


def c_measurements(cna_root: Path) -> dict[str, int]:
    include = cna_root / "modules/c-api/include"
    if not (include / "CNA/C/abi.h").is_file():
        raise FileNotFoundError(f"canonical CNA C headers are missing under {include}")
    with tempfile.TemporaryDirectory(prefix="cna-python-abi-") as directory:
        executable = Path(directory) / "probe"
        subprocess.run(["cc", "-std=c11", "-I", str(include), str(ROOT / "tools/abi_probe.c"),
                        "-o", str(executable)], check=True)
        output = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    result: dict[str, int] = {}
    for line in output.splitlines():
        kind, owner, *rest = line.split()
        if kind == "VALUE":
            result[f"VALUE:{owner}"] = int(rest[0])
        elif kind == "TYPE":
            result[f"SIZE:{owner}"] = int(rest[0])
            result[f"ALIGN:{owner}"] = int(rest[1])
        elif kind == "FVALUE":
            # A float constant cannot round-trip through an integer, so it gets
            # its own line kind rather than being truncated into VALUE.
            result[f"FVALUE:{owner}"] = float(rest[0])
        elif kind == "FIELD":
            result[f"OFFSET:{owner}:{rest[0]}"] = int(rest[1])
    return result


def ctypes_measurements(c_values: dict[str, int]) -> dict[str, int]:
    result = {
        "VALUE:CNA_ABI_VERSION": QUALIFIED_ABI,
        "VALUE:POINTER_WIDTH": ctypes.sizeof(ctypes.c_void_p),
        "VALUE:CNA_Bool": ctypes.sizeof(ctypes.c_uint8),
        "VALUE:CNA_Result": ctypes.sizeof(ctypes.c_uint32),
        "VALUE:CNA_Handle": ctypes.sizeof(ctypes.c_uint64),
        "VALUE:CNA_FALSE": 0,
        "VALUE:CNA_TRUE": 1,
        "VALUE:CNA_GameLifecycleCallback": ctypes.sizeof(abi.CNA_GameLifecycleCallback),
        "VALUE:CNA_GameBeginDrawCallback": ctypes.sizeof(abi.CNA_GameBeginDrawCallback),
        "VALUE:CNA_GameEventCallback": ctypes.sizeof(abi.CNA_GameEventCallback),
        "VALUE:CNA_GraphicsResourceDisposingCallback": ctypes.sizeof(abi.CNA_GraphicsResourceDisposingCallback),
        "VALUE:CNA_GraphicsDeviceEventCallback": ctypes.sizeof(abi.CNA_GraphicsDeviceEventCallback),
        "VALUE:CNA_PreparingDeviceSettingsMutatorEXT": ctypes.sizeof(abi.CNA_PreparingDeviceSettingsMutatorEXT),
        "VALUE:CNA_AudioEventCallback": ctypes.sizeof(abi.CNA_AudioEventCallback),
        "VALUE:CNA_StorageCompletionCallback": ctypes.sizeof(abi.CNA_StorageCompletionCallback),
        "VALUE:CNA_MediaPlayerEventCallback": ctypes.sizeof(abi.CNA_MediaPlayerEventCallback),
        "VALUE:CNA_MediaState": ctypes.sizeof(ctypes.c_uint32),
        "VALUE:CNA_MediaSourceType": ctypes.sizeof(ctypes.c_uint32),
        "VALUE:CNA_VideoSoundtrackType": ctypes.sizeof(ctypes.c_uint32),
        "VALUE:CNA_VISUALIZATION_DATA_SIZE": 256,
        "VALUE:CNA_VIDEO_FRAME_EXT_STRUCT_VERSION": abi.CNA_VIDEO_FRAME_EXT_STRUCT_VERSION,
        "VALUE:CNA_MEDIA_STATE_STOPPED": 0,
        "VALUE:CNA_MEDIA_STATE_PLAYING": 1,
        "VALUE:CNA_MEDIA_STATE_PAUSED": 2,
        "VALUE:CNA_MEDIA_SOURCE_TYPE_LOCAL_DEVICE": 0,
        "VALUE:CNA_MEDIA_SOURCE_TYPE_WINDOWS_MEDIA_CONNECT": 4,
        "VALUE:CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC": 0,
        "VALUE:CNA_VIDEO_SOUNDTRACK_TYPE_DIALOG": 1,
        "VALUE:CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC_AND_DIALOG": 2,
        "VALUE:CNA_CnbTextureFormatSupportedFn":
            ctypes.sizeof(cnb_abi.CNA_CnbTextureFormatSupportedFn),
        "VALUE:CNA_CnbLoaderCallback": ctypes.sizeof(cnb_abi.CNA_CnbLoaderCallback),
    }
    for name in dir(cnb_abi):
        if name.startswith(CNB_CONSTANT_PREFIXES):
            result[f"VALUE:{name}"] = getattr(cnb_abi, name)
    # Every generated-family constant and callback, compared against the value the
    # C compiler computes from the same header.  A float lands on the FVALUE key.
    for module, prefix in FAMILY_ABI_MODULES:
        for name in getattr(module, f"{prefix}_CALLBACKS"):
            result[f"VALUE:{name}"] = ctypes.sizeof(getattr(module, name))
        for name in getattr(module, f"{prefix}_CONSTANTS"):
            value = getattr(module, name)
            result[f"{'FVALUE' if isinstance(value, float) else 'VALUE'}:{name}"] = value
    for name, value in TYPES.items():
        result[f"SIZE:{name}"] = ctypes.sizeof(value)
        result[f"ALIGN:{name}"] = ctypes.alignment(value)
    for key in c_values:
        if not key.startswith("OFFSET:"):
            continue
        _, owner, field = key.split(":")
        result[key] = getattr(TYPES[owner], field).offset
    return result


def exports(library: Path) -> set[str]:
    output = subprocess.run(["nm", "-D", "--defined-only", str(library)], check=True,
                            text=True, capture_output=True).stdout
    return {line.split()[-1].split("@@", 1)[0] for line in output.splitlines() if line.split()}


def ctype_name(value: object) -> str:
    if hasattr(value, "_type_") and isinstance(getattr(value, "_type_"), type):
        return f"pointer<{ctype_name(value._type_)}>"
    return getattr(value, "__name__", repr(value))


def _agrees(key: str, c_value: object, py_value: object) -> bool:
    """Compares one measurement, at the width C actually stores it in.

    Every measurement but one is an integer and compares exactly. A ``float``
    constant does not: C computes it in single precision and this binding holds
    it as a Python double, so ``0.001F`` is genuinely 0.00100000005 on one side
    and 0.001 on the other. Rounding the Python value through a ``c_float``
    compares the two at the width the constant has, which is the property that
    matters; nothing is tolerated, and a constant that really changed still
    fails.
    """
    if py_value is None:
        return False
    if key.startswith("FVALUE:"):
        # Both sides are rounded to the width C stores the constant in. The C
        # probe prints a shortest round-tripping decimal, which is not the exact
        # double of that float, so rounding only the Python side would still
        # disagree with a value that is in fact identical.
        return (float(ctypes.c_float(float(py_value)).value)
                == float(ctypes.c_float(float(c_value)).value))
    return py_value == c_value


def main() -> int:
    args = arguments()
    cna_root, library = Path(args.cna_root).resolve(), Path(args.library).resolve()
    if not library.is_file():
        raise FileNotFoundError(library)
    c_values = c_measurements(cna_root)
    py_values = ctypes_measurements(c_values)
    mismatches = [{"measurement": key, "c": value, "ctypes": py_values.get(key)}
                  for key, value in sorted(c_values.items())
                  if not _agrees(key, value, py_values.get(key))]
    exported = exports(library)
    required = [value[0] for value in FUNCTION_MANIFEST]
    manifest = [
        {"symbol": symbol, "return": ctype_name(return_type),
         "parameters": [ctype_name(parameter) for parameter in parameters],
         "arity": len(parameters), "ownership": ownership}
        for symbol, return_type, parameters, ownership in FUNCTION_MANIFEST
    ]
    from _cna_native.loader import PENDING_ROUTES

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cna_headers import parse_include_directory  # noqa: E402

    declarations = set(parse_include_directory(
        cna_root / "modules" / "c-api" / "include"))
    absent = sorted(set(required) - exported)
    # A route CNA has *declared* and no artifact ships yet is separated from a
    # symbol that is simply not there. The separation is only honest while both
    # halves are checked: a pending route must be declared in the canonical
    # headers, and a declaration for a route the artifact does export is stale.
    pending = [symbol for symbol in absent if symbol in PENDING_ROUTES]
    missing = [symbol for symbol in absent if symbol not in PENDING_ROUTES]
    undeclared = sorted(symbol for symbol in PENDING_ROUTES
                        if symbol not in declarations)
    stale = sorted(symbol for symbol in PENDING_ROUTES if symbol in exported)
    report = {
        "schemaVersion": 1,
        "summary": {
            "BOUND_FUNCTIONS": len(required),
            "CTYPES_SIGNATURE_MEASUREMENTS": len(manifest),
            "C_LAYOUT_MEASUREMENTS": len(c_values),
            "CTYPES_LAYOUT_MEASUREMENTS": len(py_values),
            "MISSING_SYMBOLS": len(missing),
            "PENDING_ROUTES": len(pending),
            "PENDING_ROUTES_NOT_IN_HEADERS": len(undeclared),
            "STALE_PENDING_ROUTES": len(stale),
            "ABI_MISMATCHES": len(mismatches),
        },
        "boundFunctions": required,
        "functionManifest": manifest,
        "missingSymbols": missing,
        "pendingRoutes": [{"symbol": symbol, "reason": PENDING_ROUTES[symbol]}
                          for symbol in pending],
        "pendingRoutesNotInHeaders": undeclared,
        "stalePendingRoutes": stale,
        "mismatches": mismatches,
        "c": c_values,
        "ctypes": py_values,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    return 1 if missing or mismatches or undeclared or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
