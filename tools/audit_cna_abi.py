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
from _cna_native.loader import FUNCTION_MANIFEST, QUALIFIED_ABI


TYPES = {
    value.__name__: value for value in (
        abi.CNA_StringView, abi.CNA_ErrorInfo, abi.CNA_GameTime, abi.CNA_CallbackError,
        abi.CNA_GameCallbacks, abi.CNA_GameFrameHooks, abi.CNA_GameCreateInfo,
        abi.CNA_Color, abi.CNA_Vector2, abi.CNA_Vector3, abi.CNA_Vector4,
        abi.CNA_AudioCapabilities, abi.CNA_SoundEffectCreateInfo,
        abi.CNA_SoundEffectInstanceInfo, abi.CNA_AudioEmitter,
        abi.CNA_AudioListener, abi.CNA_CueInfo,
        abi.CNA_VisualizationData,
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
        abi.CNA_SpriteScaledCommand, abi.CNA_KeyboardState, abi.CNA_MouseState,
        abi.CNA_GamePadAnalogState, abi.CNA_GamePadState,
        abi.CNA_GamePadCapabilities,
        abi.CNA_TouchLocation, abi.CNA_TouchCapabilities, abi.CNA_TouchState,
        abi.CNA_GestureSample,
    )
}


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
        "VALUE:CNA_MEDIA_STATE_STOPPED": 0,
        "VALUE:CNA_MEDIA_STATE_PLAYING": 1,
        "VALUE:CNA_MEDIA_STATE_PAUSED": 2,
        "VALUE:CNA_MEDIA_SOURCE_TYPE_LOCAL_DEVICE": 0,
        "VALUE:CNA_MEDIA_SOURCE_TYPE_WINDOWS_MEDIA_CONNECT": 4,
        "VALUE:CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC": 0,
        "VALUE:CNA_VIDEO_SOUNDTRACK_TYPE_DIALOG": 1,
        "VALUE:CNA_VIDEO_SOUNDTRACK_TYPE_MUSIC_AND_DIALOG": 2,
    }
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


def main() -> int:
    args = arguments()
    cna_root, library = Path(args.cna_root).resolve(), Path(args.library).resolve()
    if not library.is_file():
        raise FileNotFoundError(library)
    c_values = c_measurements(cna_root)
    py_values = ctypes_measurements(c_values)
    mismatches = [{"measurement": key, "c": value, "ctypes": py_values.get(key)}
                  for key, value in sorted(c_values.items()) if py_values.get(key) != value]
    exported = exports(library)
    required = [value[0] for value in FUNCTION_MANIFEST]
    manifest = [
        {"symbol": symbol, "return": ctype_name(return_type),
         "parameters": [ctype_name(parameter) for parameter in parameters],
         "arity": len(parameters), "ownership": ownership}
        for symbol, return_type, parameters, ownership in FUNCTION_MANIFEST
    ]
    missing = sorted(set(required) - exported)
    report = {
        "schemaVersion": 1,
        "summary": {
            "BOUND_FUNCTIONS": len(required),
            "CTYPES_SIGNATURE_MEASUREMENTS": len(manifest),
            "C_LAYOUT_MEASUREMENTS": len(c_values),
            "CTYPES_LAYOUT_MEASUREMENTS": len(py_values),
            "MISSING_SYMBOLS": len(missing),
            "ABI_MISMATCHES": len(mismatches),
        },
        "boundFunctions": required,
        "functionManifest": manifest,
        "missingSymbols": missing,
        "mismatches": mismatches,
        "c": c_values,
        "ctypes": py_values,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    return 1 if missing or mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
