# Engine-layer upstream findings

Defects and documentation/implementation disagreements found in CNA's
`engine_layer.h` family while building `cna.extensions.engine`. Every entry was
measured on the artifact it names; none is carried over from another language
binding, and none is a conclusion quoted from prose.

Each finding records the exact revision, a reproducer, the expected contract,
the actual result, the public Python operation it affects, what this binding
does instead, and what would unblock it.

## Measurement environment

```text
cnanext            5347b52eae1311fbea1f89955ae8a48c6843a88a
CNA C ABI          0.21.0
engine layer       revision 2

control artifact   HEADLESS, no engine layer
                   cmake-build-headless/modules/c-api/libcna_c_api.so
                   94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d

gpu artifact       OPENGLES3, Mesa GL ES 3.2 (llvmpipe), isolated Xvfb display
                   cmake-build-opengles3/modules/c-api/libcna_c_api.so
                   65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9
```

The control artifact reports `cna_engine_layer_get_version() == 0` and
`cna_graphics_ext_is_available() == false`: **it has no engine layer at all**,
while still exporting all 857 engine symbols. That is CNA's stated design -- one
export list regardless of build options, so the recorded ABI baseline describes
every build -- and it is why availability is read from the version route rather
than from the symbol table.

---

## ENGINE-001 -- `cna_compute_shader_create` fails on source that does not compile

**Status:** open. Does not block; this binding reports what happens.

**Documented contract.** `engine_layer.h` says, of `cna_compute_shader_create`:

> Creation succeeds even when the source does not compile: ask
> `cna_compute_shader_is_valid` and read `cna_compute_shader_copy_compile_error`.
> That mirrors the canonical class, which records the failure rather than
> throwing, because a renderer without compute is a documented boundary rather
> than a defect.

**Actual result.** Creation fails and hands back no handle. Measured on the GPU
artifact with six sources rejected for six different reasons:

| Source | `create` result | handle |
|---|---:|---:|
| empty | 12 (`CNA_RESULT_INTERNAL`) | 0 |
| syntax error | 12 | 0 |
| no `main` | 12 | 0 |
| no `#version` | 12 | 0 |
| undeclared identifier | 12 | 0 |
| no `local_size` | 12 | 0 |
| a source that compiles | 0 | valid, `is_valid` true, no diagnostic |

CNA's error message carries the compiler log, for example
`CNA::Graphics::ComputeShader: the program did not compile: CS: 0:3(15): error:
illegal use of reserved word 'this'`.

**Reproducer.** In C, against the GPU artifact:

```c
CNA_ComputeShaderHandle shader = 0;
const char* source = "#version 310 es\nlayout(local_size_x=4) in;\nvoid other(){}\n";
CNA_StringView view = { source, strlen(source) };
CNA_Result result = cna_compute_shader_create(device, view, &shader);
/* documented: result == CNA_RESULT_SUCCESS and shader valid-but-not-compiled */
/* actual:     result == 12 and shader == 0                                   */
```

`tests/test_engine_compute.py::ComputeShaderTests::test_source_that_does_not_compile_raises_with_the_compiler_log`
is the same measurement as a test, and it fails if CNA later starts keeping the
documented contract, which is when this finding needs re-measuring.

**Two separate problems.** The failure mode is one; the category is another.
A source the caller wrote badly is reported as `CNA_RESULT_INTERNAL`, the
category reserved for CNA's own invariants running out. A caller cannot tell
"my shader is wrong" from "CNA broke" by result code alone.

**Affected Python operation.** `cna.extensions.engine.ComputeShader(device,
source)`.

**Local behaviour.** The constructor raises
`cna.extensions.engine.errors.ComputeShaderCompileError`, whose `result` stays
12 verbatim and which subclasses `EngineInternalError`, so nothing is
relabelled: `except EngineInternalError` still catches it, and CNA's compiler
log is on `native_message`. The subclass exists so a caller can tell a
diagnostic from an allocation failure without parsing a message. The documented
path is handled too: a shader CNA does return while calling it invalid is closed
and reported, rather than being handed out as something that can be dispatched.

**Unblock condition.** Either the header stops promising a non-throwing
creation, or the implementation starts keeping it. If the implementation
changes, this binding keeps working -- the invalid-shader branch is already
there -- and the test above is what will say so.

---

Findings are added as each engine family is qualified. A family that has not
been measured yet has no entry here, and an absent entry is not a claim that it
is clean.
