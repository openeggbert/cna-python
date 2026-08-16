# CNA-Python implementation plan

**Status:** corrected namespace scaffold in place

**Date:** 2026-08-16

## Phase 0 — namespace scaffold

- [x] Establish `CNA.Framework` and `Microsoft.Xna.Framework` package roots.
- [x] Reserve matching `Graphics`, `Input`, and `Content` packages.
- [x] Reserve `CNA.Interop` for the native ABI mapping.
- [x] Add initial `Game`, `GameTime`, `Vector2`, and `Color` shapes.

## Phase 1 — canonical ABI

- [ ] Choose the extension/FFI mechanism only after canonical CNA headers exist.
- [ ] Add ABI-version checks, UTF-8, structured exceptions, opaque handles,
      callback/GIL rules, ownership, threading, and shutdown.

## Phase 2 — first playable XNA-style loop

- [ ] Add graphics device, texture, sprite batch, content, and keyboard types
      under both public package trees.
- [ ] Run a CNA-backed game that clears, loads/draws a texture, reads Escape,
      and shuts down cleanly.

## Invariants

1. Public package hierarchy follows CNA and `Microsoft.Xna.Framework`.
2. CNA C++ remains the only engine implementation.
3. Only the stable CNA C ABI crosses into Python.
4. Sharp Runtime and C++ ABI details remain native implementation details.
