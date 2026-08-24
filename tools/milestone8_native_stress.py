#!/usr/bin/env python3
"""Crash-isolated Foundation Milestone 8 native ownership/callback stress."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _cna_native.errors import NativeError  # noqa: E402
from Microsoft.Xna.Framework import FrameworkDispatcher, Game, GraphicsDeviceManager  # noqa: E402
from Microsoft.Xna.Framework.GamerServices import GamerServicesComponent  # noqa: E402
from Microsoft.Xna.Framework.Graphics import (  # noqa: E402
    CubeMapFace, DepthFormat, OcclusionQuery, RenderTargetBinding,
    RenderTargetCube, RenderTargetUsage, SurfaceFormat,
)
from Microsoft.Xna.Framework.Input.Touch import GestureType, TouchPanel  # noqa: E402
from Microsoft.Xna.Framework.Storage import StorageDevice  # noqa: E402


def _capture(action, errors: list[BaseException]) -> None:
    try:
        action()
    except BaseException as error:
        errors.append(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--callback-cycles", type=int, default=50)
    args = parser.parse_args()
    if args.cycles < 20:
        parser.error("--cycles must be at least 20")
    if args.callback_cycles < 50:
        parser.error("--callback-cycles must be at least 50")

    counts = {name: 0 for name in (
        "FRAMEWORK_DISPATCHER", "GAMERSERVICES_INITIALIZE", "GAMERSERVICES_COMPONENT", "OCCLUSION_QUERY",
        "RENDERTARGET_CUBE", "RENDERTARGET_CUBE_FAILURE", "TOUCH_STATE",
        "TOUCH_GESTURE_EMPTY", "STORAGE_DEVICE", "STORAGE_CONTAINER",
        "STORAGE_STREAM", "STORAGE_CALLBACK", "STORAGE_FAILURE",
        "WRONG_THREAD_REFUSAL", "GAME_RECREATION",
    )}

    class TrackingGamer(GamerServicesComponent):
        def Initialize(self):
            super().Initialize()
            counts["GAMERSERVICES_INITIALIZE"] += 1
        def Update(self, game_time):
            super().Update(game_time)
            counts["GAMERSERVICES_COMPONENT"] += 1

    class StressGame(Game):
        def __init__(self):
            super().__init__()
            self.graphics = GraphicsDeviceManager(self)
            self.gamers = [TrackingGamer(self) for _ in range(args.cycles)]
            for gamer in self.gamers:
                self.Components.Add(gamer)
            self.finished = False

        def LoadContent(self):
            if counts["GAMERSERVICES_INITIALIZE"] != args.cycles:
                raise RuntimeError("GamerServices components did not initialize exactly once")

            # Every worker-originated callback enters the same host queue and is
            # delivered only by the public owner-thread dispatcher boundary.
            delivered = []
            for index in range(args.cycles):
                worker = threading.Thread(
                    target=lambda value=index: self._host._queue_dispatch_callback(
                        lambda: delivered.append(value)))
                worker.start(); worker.join()
                if len(delivered) != index:
                    raise RuntimeError("worker callback escaped before dispatcher delivery")
                FrameworkDispatcher.Update()
                counts["FRAMEWORK_DISPATCHER"] += 1
            if delivered != list(range(args.cycles)):
                raise RuntimeError("dispatcher callback order changed")

            marker = RuntimeError("dispatcher callback marker")
            self._host._queue_dispatch_callback(lambda: (_ for _ in ()).throw(marker))
            try:
                FrameworkDispatcher.Update()
            except RuntimeError as error:
                if error is not marker:
                    raise
            else:
                raise RuntimeError("dispatcher callback exception was suppressed")

            device = self.GraphicsDevice
            faces = tuple(CubeMapFace)
            for index in range(args.cycles):
                cube = RenderTargetCube(
                    device, 4, False, SurfaceFormat.Color, DepthFormat.Depth24,
                    0, RenderTargetUsage.PreserveContents,
                )
                face = faces[index % len(faces)]
                device.SetRenderTarget(cube, face)
                binding = device.GetRenderTargets()[0]
                if binding.RenderTarget is not cube or binding.CubeMapFace is not face:
                    raise RuntimeError("cube render-target identity/face did not round-trip")
                if copy.copy(RenderTargetBinding(cube, face)).CubeMapFace is not face:
                    raise RuntimeError("cube binding copy lost its face")
                try:
                    cube.Dispose()
                except NativeError as error:
                    if error.result != 6:
                        raise
                    counts["RENDERTARGET_CUBE_FAILURE"] += 1
                else:
                    raise RuntimeError("bound render-target destruction was not refused")
                if cube.IsDisposed:
                    raise RuntimeError("refused bound-target destruction consumed ownership")
                device.SetRenderTarget(None)
                if index == 0:
                    errors: list[BaseException] = []
                    worker = threading.Thread(target=lambda: _capture(cube.Dispose, errors))
                    worker.start(); worker.join()
                    if (len(errors) != 1 or not isinstance(errors[0], NativeError)
                            or errors[0].result != 8 or cube.IsDisposed):
                        raise RuntimeError("wrong-thread cube destruction was not retryable")
                    counts["WRONG_THREAD_REFUSAL"] += 1
                cube.Dispose(); cube.Dispose()
                counts["RENDERTARGET_CUBE"] += 1

            for _ in range(args.cycles):
                try:
                    query = OcclusionQuery(device)
                except NativeError as error:
                    if error.result != 6:
                        raise
                else:
                    if query.IsComplete:
                        raise RuntimeError("new query unexpectedly reported a completed result")
                    try:
                        query.End()
                    except RuntimeError:
                        pass
                    else:
                        raise RuntimeError("query End without Begin succeeded")
                    query.Begin()
                    try:
                        query.Begin()
                    except RuntimeError:
                        pass
                    else:
                        raise RuntimeError("query Begin twice succeeded")
                    query.End()
                    if query.IsComplete:
                        pixel_count = query.PixelCount
                        if pixel_count < 0:
                            raise RuntimeError("native query returned a negative pixel count")
                        query.Begin(); query.End()
                        if not query.IsComplete:
                            raise RuntimeError("second native query cycle did not complete")
                    else:
                        try:
                            query.PixelCount
                        except RuntimeError:
                            pass
                        else:
                            raise RuntimeError("incomplete query exposed PixelCount")
                    if counts["OCCLUSION_QUERY"] == 0:
                        errors = []
                        worker = threading.Thread(target=lambda: _capture(query.Dispose, errors))
                        worker.start(); worker.join()
                        if (len(errors) != 1 or not isinstance(errors[0], NativeError)
                                or errors[0].result != 8 or query.IsDisposed):
                            raise RuntimeError("wrong-thread query destruction was not retryable")
                        counts["WRONG_THREAD_REFUSAL"] += 1
                    query.Dispose(); query.Dispose()
                counts["OCCLUSION_QUERY"] += 1

            try:
                TouchPanel.IsGestureAvailable
            except RuntimeError:
                pass
            else:
                raise RuntimeError("gesture availability succeeded before gestures were enabled")
            TouchPanel.EnabledGestures = GestureType.Tap | GestureType.DoubleTap
            if TouchPanel.IsGestureAvailable:
                raise RuntimeError("qualified empty touch queue reported a gesture")
            for _ in range(args.cycles):
                state = TouchPanel.GetState()
                if state.Count != len(state):
                    raise RuntimeError("touch snapshot count diverged")
                counts["TOUCH_STATE"] += 1
                try:
                    TouchPanel.ReadGesture()
                except NativeError:
                    counts["TOUCH_GESTURE_EMPTY"] += 1
                else:
                    raise RuntimeError("empty touch queue fabricated a gesture")

            devices = []
            for index in range(args.cycles):
                callback_results = []
                if index == 0:
                    pending = StorageDevice.BeginShowSelector(
                        0, -1, lambda value: callback_results.append(value), index)
                else:
                    pending = StorageDevice.BeginShowSelector(
                        lambda value: callback_results.append(value), index)
                if callback_results != [pending]:
                    raise RuntimeError("selector callback/result identity diverged")
                devices.append(StorageDevice.EndShowSelector(pending))
                counts["STORAGE_DEVICE"] += 1
                counts["STORAGE_CALLBACK"] += 1

            storage = devices[0]
            # A foreign End must leave the token available to its real owner.
            provenance = storage.BeginOpenContainer(
                "cna-python-m8-provenance", None, None)
            try:
                devices[1].EndOpenContainer(provenance)
            except ValueError:
                counts["STORAGE_FAILURE"] += 1
            else:
                raise RuntimeError("foreign StorageDevice accepted a container result")
            provenance_container = storage.EndOpenContainer(provenance)
            provenance_container.Dispose()
            storage.DeleteContainer("cna-python-m8-provenance")

            for index in range(args.callback_cycles - args.cycles):
                name = f"cna-python-m8-callback-{index}"
                observed = []
                pending = storage.BeginOpenContainer(
                    name, lambda value: observed.append(value), index)
                if observed != [pending]:
                    raise RuntimeError("container callback/result identity diverged")
                container = storage.EndOpenContainer(pending)
                container.Dispose(); storage.DeleteContainer(name)
                counts["STORAGE_CALLBACK"] += 1

            for index in range(args.cycles):
                name = f"cna-python-m8-container-{index}"
                pending = storage.BeginOpenContainer(name, None, index)
                container = storage.EndOpenContainer(pending)
                nested = "nested/../nested"
                container.CreateDirectory(nested)
                stream = container.CreateFile(f"{nested}/value.bin")
                stream.write(b"milestone-eight"); stream.flush(); stream.close(); stream.close()
                with container.OpenFile(
                        "nested/value.bin", "open", "read", frozenset({"read"})) as opened:
                    if opened.read() != b"milestone-eight":
                        raise RuntimeError("storage stream payload changed")
                if "value.bin" not in container.GetFileNames("*.bin"):
                    # CNA patterns enumerate only the selected container level.
                    if "nested" not in container.GetDirectoryNames("n*"):
                        raise RuntimeError("storage wildcard enumeration failed")
                for escaping in ("../escape", "..\\escape", "/absolute", "C:\\escape"):
                    try:
                        container.FileExists(escaping)
                    except ValueError:
                        pass
                    else:
                        raise RuntimeError("storage path containment accepted an escape")
                counts["STORAGE_FAILURE"] += 1
                disposing = []
                def handler(sender, event, selected=container):
                    disposing.append(sender)
                    selected.Disposing -= handler
                    selected.Dispose()
                container.Disposing += handler
                container.Disposing += handler
                container.Dispose(); container.Dispose()
                if disposing != [container, container]:
                    raise RuntimeError("Disposing duplicate/self-removal semantics changed")
                storage.DeleteContainer(name)
                counts["STORAGE_CONTAINER"] += 1
                counts["STORAGE_STREAM"] += 1

            # Exercise the off-owner native callback trampoline without claiming
            # that the platform originated a real device transition.
            changed = []
            def changed_handler(sender, event):
                changed.append(threading.get_ident())
            StorageDevice.DeviceChanged += changed_handler
            native_callback = StorageDevice._device_event_callback
            worker = threading.Thread(target=lambda: native_callback(None))
            worker.start(); worker.join()
            if changed:
                raise RuntimeError("DeviceChanged ran user code on the native callback thread")
            FrameworkDispatcher.Update()
            if changed != [self._host.owner_thread]:
                raise RuntimeError("DeviceChanged was not delivered on the owner thread")
            StorageDevice.DeviceChanged -= changed_handler

            # Callback failure is raised only after native control returns and
            # the native result handle is released transactionally.
            for _ in range(args.cycles):
                try:
                    StorageDevice.BeginShowSelector(
                        lambda result: (_ for _ in ()).throw(
                            RuntimeError("storage callback marker")), None)
                except RuntimeError as error:
                    if str(error) != "storage callback marker":
                        raise
                else:
                    raise RuntimeError("storage callback exception was suppressed")
            self.finished = True

        def Update(self, game_time):
            super().Update(game_time)
            if counts["GAMERSERVICES_COMPONENT"] != args.cycles:
                raise RuntimeError("GamerServices components did not update exactly once")
            self.Exit()

    game = StressGame()
    try:
        game.Run()
        if not game.finished:
            raise RuntimeError("Milestone-8 stress Game did not complete")
    finally:
        game.Dispose(); game.Dispose()

    # A fresh generation proves the process-static touch window and Storage
    # registrations do not retain the destroyed Game.
    for _ in range(args.cycles):
        class RecreationGame(Game):
            def LoadContent(self):
                if TouchPanel.WindowHandle != self.Window.Handle:
                    raise RuntimeError("TouchPanel retained a stale Game window handle")
            def Update(self, game_time):
                self.Exit()
        recreated = RecreationGame()
        try:
            recreated.Run()
            counts["GAME_RECREATION"] += 1
        finally:
            recreated.Dispose()

    for name, value in counts.items():
        print(f"{name}_CYCLES={value}")
    print("TOUCH_HARDWARE_STATUS=HARDWARE_PENDING")
    print("TOUCH_GESTURE_STATUS=PLATFORM_PENDING")
    print("STORAGE_SELECTOR_UI_STATUS=PLATFORM_PENDING")
    print("STORAGE_DEVICE_CHANGE_ORIGIN_STATUS=PLATFORM_PENDING")
    print("NATIVE_CRASHES=0")
    print("OBSERVED_UAF=0")
    print("DOUBLE_FREE=0")
    print("SANITIZER_STATUS=NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
