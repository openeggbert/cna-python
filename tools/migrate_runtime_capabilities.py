#!/usr/bin/env python3
"""One-shot migration of the runtime capability registry to schema 2.

Schema 1 had a single ``qualifiedBackend`` string, so every row's status was
implicitly a claim about one artifact. That is how a whole draw surface came to
be recorded as backend-blocked: the only artifact could not rasterize, and the
registry had nowhere to say so. Schema 2 names the artifacts and lets a row
differ between them, because they genuinely do.

Statuses are also renamed to the vocabulary the census and the remaining-work
table use, so one word means one thing across the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/runtime-capabilities.json"

ARTIFACTS = [
    {
        "id": "control",
        "role": "deterministic non-windowed control",
        "renderer": "HEADLESS",
        "rasterizes": False,
        "audio": "SDL3 mixer on the dummy device",
        "video": "AUTO (FFmpeg present)",
        "platform": "Linux x86-64",
        "sha256": "94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d",
    },
    {
        "id": "gpu",
        "role": "real windowed renderer",
        "renderer": "OPENGLES3",
        "rasterizes": True,
        "audio": "SDL3 mixer on the dummy device",
        "video": "AUTO (FFmpeg present)",
        "platform": "Linux x86-64, isolated Xvfb display, Mesa GL ES 3.2 (llvmpipe)",
        "sha256": "65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9",
    },
]

STATUSES = [
    "VERIFIED_NATIVE",
    "VERIFIED_MANAGED",
    "BLOCKED_UPSTREAM",
    "BLOCKED_RENDERER",
    "BLOCKED_PLATFORM",
    "BLOCKED_HARDWARE",
    "BLOCKED_FIXTURE",
    "LANGUAGE_MAPPING_LIMITATION",
    "DELIBERATE_OUT_OF_SCOPE",
    "ACTIONABLE_LOCAL",
]

RENAME = {
    "UPSTREAM_CNA_BLOCKED": "BLOCKED_UPSTREAM",
    "BACKEND_BLOCKED": "BLOCKED_RENDERER",
    "HARDWARE_PENDING": "BLOCKED_HARDWARE",
    "PLATFORM_PENDING": "BLOCKED_PLATFORM",
    "ASSET_PENDING": "BLOCKED_FIXTURE",
    "UNIMPLEMENTED_CNA_PYTHON": "ACTIONABLE_LOCAL",
}

#: operation -> (status, evidence, notes, byArtifact|None)
CHANGES: dict[str, tuple] = {
    "FrameworkDispatcher Update without a live Game": (
        "BLOCKED_UPSTREAM",
        "runtime.h cna_framework_dispatcher_update(CNA_Handle game); re-read on CNA 0.21.0",
        "Re-measured, unchanged: the route still takes a Game handle, so it has nothing to pump "
        "without one. XNA permits a process-level call; Python reports the limitation and never "
        "silently no-ops.",
        None),
    "Broader GamerServices ecosystem": (
        "DELIBERATE_OUT_OF_SCOPE",
        "the selected 257-type profile ends at GamerServicesComponent",
        "Not a backend limit: CNA has 250 gamer-service routes and the profile deliberately "
        "excludes them. Opening the family is a future-profile decision, and no Gamer, Guide, "
        "Avatar, achievement or leaderboard facade is fabricated meanwhile.",
        None),
    "Game activation/deactivation delivery": (
        "VERIFIED_NATIVE",
        "cna_game_subscribe; the Activated event is delivered on both qualified artifacts",
        "Activation is delivered for real. A deactivation transition needs a focus change no "
        "automated run performs, so it is exercised but not observed here.",
        None),
    "GameWindow resize/orientation events": (
        "VERIFIED_NATIVE",
        "cna_game_window_subscribe; ClientSizeChanged delivered after ApplyChanges resized the "
        "window from 800x480 to 512x384 on the windowed artifact",
        "The event is real on a renderer that has a window. The control artifact has none, so it "
        "delivers nothing and none is synthesized. Orientation never changes on this platform.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "GraphicsDevice.ResourceCreated/ResourceDestroyed": (
        "BLOCKED_UPSTREAM",
        "graphics_device.h CNA_ResourceCreatedEventInfo / CNA_ResourceDestroyedEventInfo",
        "The subscription routes now exist, but CNA states that the event is raised from the "
        "graphics-resource base constructor, so the object is still under construction and no "
        "native object pointer crosses the ABI. XNA's ResourceCreatedEventArgs.Resource therefore "
        "cannot be supplied and would have to be fabricated.",
        None),
    "DynamicVertexBuffer.SetData(offset, streaming options)": (
        "VERIFIED_NATIVE",
        "cna_vertex_buffer_set_data_raw_at_with_options; a window written at vertex three with "
        "NoOverwrite left vertices zero to two intact",
        "Closed upstream: the current generation has the route carrying both the destination "
        "offset and the streaming hint, which the historical one lacked.",
        None),
    "DrawPrimitives/DrawIndexedPrimitives": (
        "VERIFIED_NATIVE",
        "rendered-pixel test: each path writes its own colour and reads it back",
        "Both paths produce the colour they were given on the windowed renderer. The control "
        "artifact has no pixel storage and refuses back-buffer readback outright.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "DrawInstancedPrimitives": (
        "VERIFIED_NATIVE",
        "cna_graphics_device_draw_instanced_primitives; two instances drawn and read back",
        "Executes and rasterizes on the windowed renderer.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "DrawUserPrimitives/DrawUserIndexedPrimitives": (
        "VERIFIED_NATIVE",
        "rendered-pixel test: each user path writes its own colour and reads it back",
        "Both user-array paths rasterize. Only explicit built-in vertex codecs and deterministic "
        "contiguous bytes are accepted.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "RenderTarget visible output": (
        "VERIFIED_NATIVE",
        "a render target cleared to a known colour reads that colour back through GetData, and "
        "the backbuffer keeps its own",
        "Rendering into a target and reading it back is verified; the two surfaces are shown to be "
        "distinct rather than assumed.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "RenderTargetCube ContentLost delivery": (
        "BLOCKED_RENDERER",
        "cna_render_target_subscribe_content_lost / _unsubscribe_content_lost",
        "Subscription and release are now real and verified on both artifacts. CNA raises the "
        "event only where a renderer can lose and recreate its device, which none of the "
        "identities available on this platform can, so a subscription here is valid and silent. "
        "No loss is synthesized.",
        None),
    "Bound render-target disposal": (
        "VERIFIED_NATIVE",
        "cna_render_target_destroy returns CNA_RESULT_INVALID_STATE, 'Disposing target that is "
        "still bound'; the same handle destroys cleanly once unbound",
        "Closed upstream: the historical generation aborted the process here, which is why Python "
        "guards before calling. CNA now refuses cleanly, and the Python guard is kept as "
        "defence in depth. It preserves the handle for a legal retry and never silently restores "
        "the backbuffer.",
        None),
    "GraphicsDevice.Present(rectangles, window)": (
        "BLOCKED_UPSTREAM",
        "graphics_device.h cna_graphics_device_present(CNA_Handle graphics_device)",
        "Re-measured, unchanged: the only Present route takes the device alone, with no source or "
        "destination rectangle and no target window. Raises after strict argument validation.",
        None),
    "GraphicsDevice.DeviceLost": (
        "BLOCKED_RENDERER",
        "cna_graphics_device_subscribe_event; no device-loss transition exists on this renderer",
        "The subscription is real. Only renderer families whose API can lose a device raise it, "
        "and none is available on this platform; none is fabricated.",
        None),
    "Compiled Effect execution": (
        "BLOCKED_FIXTURE",
        "cna_graphics_device_executes_shader_effect_source_ext answers true on the windowed "
        "renderer and false on the control artifact",
        "The running device is asked rather than the renderer name inferred from. The windowed "
        "renderer does execute shader effect source, so what is missing is a legal compiled-effect "
        "fixture, not backend support. No shader is fabricated.",
        {"control": "BLOCKED_RENDERER", "gpu": "BLOCKED_FIXTURE"}),
    "Stock-effect visible GPU output": (
        "VERIFIED_NATIVE",
        "BasicEffect with vertex colours produces the drawn colour through every draw path",
        "Stock-effect output is rendered and read back.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "Texture3D": (
        "VERIFIED_NATIVE",
        "cna_texture3d_create/set_data/get_data; all eight voxels round-trip exactly",
        "Creation and the complete Color codec work on the windowed renderer. The control "
        "artifact refuses creation, which is a renderer boundary rather than a missing feature.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "TextureCube Color transfer": (
        "VERIFIED_NATIVE",
        "cna_texturecube_set_data/get_data; two faces written with different contents read back "
        "distinctly",
        "The face selector is proven by writing two faces differently rather than by writing one.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "Model visible GPU output": (
        "VERIFIED_NATIVE",
        "a Model loaded from XNB and drawn through its BasicEffect covered 47,960 pixels",
        "The managed XNB model graph draws for real. The graph itself stays managed by design; "
        "CNA's native model runtime is a separate extension concept and does not replace it.",
        {"control": "BLOCKED_RENDERER", "gpu": "VERIFIED_NATIVE"}),
    "SoundEffectInstance.Apply3D(multiple listeners)": (
        "VERIFIED_NATIVE",
        "cna_sound_effect_instance_apply_3d_multi_ext accepts any positive listener count",
        "Closed upstream since ABI 0.9: the historical generation refused every count but one. "
        "Where several listeners are given the nearest decides the applied attenuation, pan and "
        "Doppler, which is an approximation CNA documents rather than one this binding invents. "
        "A zero count stays refused and is not guessed at.",
        None),
    "Microphone enumeration": (
        "VERIFIED_NATIVE",
        "cna_microphone_get_count and the indexed name/rate/state routes; the real mixer "
        "enumerates capture devices and reports a default",
        "The historical null backend had no devices at all. Enumeration, naming, sample rate and "
        "default selection are now measured against a real backend.",
        None),
    "Microphone capture": (
        "BLOCKED_HARDWARE",
        "Start/Stop transition the state machine, BufferDuration validation refuses a 10 ms "
        "duration, GetSampleSizeInBytes matches the reported rate, and GetData returns bytes",
        "The capture path is fully exercised: the state machine, the duration contract, the size "
        "arithmetic and a real byte transfer. The bytes are silence because the deterministic "
        "device supplies silence, so a non-zero sample remains physical-capture evidence this "
        "environment cannot produce.",
        None),
    "AudioEngine renderer selection": (
        "BLOCKED_UPSTREAM",
        "xact.h: 'Both extra arguments are accepted and ignored'",
        "Re-measured, unchanged: CNA has exactly one audio backend, so a renderer id has nothing "
        "to select between. Reported rather than approximated.",
        None),
    "AudioEngine look-ahead": (
        "BLOCKED_UPSTREAM",
        "xact.h: 'Both extra arguments are accepted and ignored'",
        "Re-measured, unchanged: the backend has no scheduling look-ahead to set.",
        None),
    "Storage FileShare enforcement": (
        "BLOCKED_UPSTREAM",
        "storage.h: 'The canonical implementation currently ignores file_share'",
        "Re-measured, unchanged. The exact flag value reaches the C ABI and Python reports the "
        "divergence instead of pretending the lock was taken.",
        None),
    "Real visualization spectrum": (
        "VERIFIED_NATIVE",
        "with a generated 440 Hz tone playing, the 256-point spectrum has a non-zero peak and the "
        "waveform swings both positive and negative",
        "The historical null backend had no decoded signal, so zeros were all it could report. A "
        "real mixer decodes the tone and the visualization follows it.",
        None),
    "Video decode": (
        "VERIFIED_NATIVE",
        "a generated clip loaded through ContentManager plays and yields frame textures on both "
        "artifacts",
        "The fixture is generated at test time and never committed; the repository ships no "
        "encoded media. CNA refuses a video whose declared metadata disagrees with the file, so "
        "the clip is produced to match the asset exactly.",
        None),
    "Video decode on a non-rendering backend": (
        "VERIFIED_NATIVE",
        "the same generated clip decodes on the non-windowed control artifact",
        "Decoding does not depend on the renderer; it was the title-relative path, not the "
        "backend, that prevented it before.",
        None),
    "Video frame stable identity/generation": (
        "VERIFIED_NATIVE",
        "cna_video_player_get_frame_ext supplies a monotonic decode generation with the borrowed "
        "frame texture",
        "Closed upstream since ABI 0.9. GetTexture returns a real Texture2D that borrows the "
        "runtime's frame; it is never owned, never destroyed and never registered per frame, and "
        "a use after the borrow ended refuses with the reason it ended. CNA decodes into a single "
        "texture rather than alternating two, which is a divergence from XNA's slot model that "
        "the generation makes observable rather than hidden.",
        None),
    "VideoPlayer.GetTexture route": (
        "VERIFIED_NATIVE",
        "cna_video_player_get_frame_ext; no frame before playback maps to None",
        "Asking before playback has produced a frame is an ordinary answer of None, matching the "
        "canonical implementation rather than faulting.",
        None),
    "OcclusionQuery": (
        "VERIFIED_NATIVE",
        "cna_occlusion_query_*; the query completes asynchronously and PixelCount reads after it",
        "XNA's query is asynchronous. The control artifact answers at once and the windowed "
        "renderer takes a bounded number of polls; both satisfy the contract, so the test waits "
        "rather than encoding one backend's timing.",
        None),
}


def main() -> int:
    value = json.loads(SOURCE.read_text(encoding="utf-8"))
    operations = []
    for item in value["operations"]:
        name = item["operation"]
        status = RENAME.get(item["status"], item["status"])
        evidence, notes, by_artifact = item["evidence"], item["notes"], None
        if name in CHANGES:
            status, evidence, notes, by_artifact = CHANGES[name]
        row = {"operation": name, "status": status, "evidence": evidence, "notes": notes}
        if by_artifact:
            row["byArtifact"] = by_artifact
        operations.append(row)

    unknown = sorted({row["status"] for row in operations} - set(STATUSES))
    if unknown:
        raise ValueError(f"unknown statuses: {unknown}")
    missing = sorted(set(CHANGES) - {item["operation"] for item in value["operations"]})
    if missing:
        raise ValueError(f"change table names operations that do not exist: {missing}")

    result = {
        "schemaVersion": 2,
        "abi": "0.21.0",
        "cnaRevision": "7712534d3d22c7e284714e0e87afebba3f3cb472",
        "sharpRuntimeRevision": "9cc96cd57cde394940cc24d58743edf9bf63d3fb",
        "artifacts": ARTIFACTS,
        "statuses": STATUSES,
        "operations": operations,
    }
    SOURCE.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for row in operations:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"OPERATIONS={len(operations)}")
    for status in STATUSES:
        print(f"{status}={counts.get(status, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
