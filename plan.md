# CNA-Python implementation plan

**Status:** foundation scaffold in place

**Date:** 2026-08-16

**Sources:** `../cnabinding/analysis_binding.md`,
`../cnabinding/analysis_binding_sharp_runtime.md`, and
`../cna/analysis_binding_languages.md`

## Goal

Expose CNA's canonical C++ engine through normal Python objects suitable for
education, prototypes, tooling, tests, and games. Preserve XNA concepts while
using Python naming, exceptions, context managers, and standard-library values.

## Phase 0 — repository scaffold (this commit)

- [x] README, plan, architecture, license, notices, editor settings, ignores.
- [x] Dependency-free `src`-layout Python package.
- [x] Local `Vector2`, `Color`, and `GameTime` types with unit tests.
- [x] Pythonic `Game` lifecycle, context manager, and explicit missing-ABI error.
- [x] Reserved private native module with no guessed declarations.

## Phase 1 — canonical native ABI

- [ ] Wait for headers and implementation in `openeggbert/cna`.
- [ ] Select and isolate the extension/FFI mechanism using packaging and callback
      requirements, not public-API convenience.
- [ ] Validate ABI versions and translate `CNA_Result` plus native detail into a
      useful Python exception hierarchy.
- [ ] Test UTF-8, missing library diagnostics, stale handles, double close,
      callbacks/GIL, threading, and shutdown order.

## Phase 2 — first playable loop

- [ ] Bridge Python game callbacks with strong references and correct GIL rules.
- [ ] Add `GraphicsDevice`, `Texture2D`, `SpriteBatch`, `ContentManager`, and
      keyboard snapshots.
- [ ] Distinguish owned/borrowed handles; support `close()` and `with` for owners.
- [ ] Run HelloGame: clear, load/draw a texture, read Escape, cleanly exit.

## Phase 3 — packaging and performance

- [ ] Batch SpriteBatch commands and bulk data buffers.
- [ ] Build wheels containing supported native CNA binaries.
- [ ] Test supported CPython versions on at least Linux and Windows.
- [ ] Publish a pre-1.0 package only after the end-to-end sample works.

## Phase 4 — broader CNA/XNA concepts

- [ ] Complete math, geometry, color, and input values in Python.
- [ ] Add audio, fonts, render targets, effects, models, and 3D incrementally.
- [ ] Validate real games/tools and publish an honest compatibility matrix.

## Invariants

1. CNA C++ stays canonical; Python crosses only the stable CNA C ABI.
2. C++ exceptions and Sharp Runtime types never cross the boundary.
3. Strings are UTF-8, ABI primitives fixed-width, and ownership explicit.
4. Math stays local; input uses snapshots; high-frequency traffic batches.
5. Raw pointers, handles, result codes, and FFI objects remain private.
