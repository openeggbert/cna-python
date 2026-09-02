"""GPU compute, storage buffers, barriers and timers, against independent oracles.

What counts as evidence here is buffer content, not a result code. Every compute
case dispatches a program whose output Python computes itself from the same
arithmetic the shader states, so a dispatch that ran the wrong program, read the
wrong binding, or never ran at all produces different numbers rather than a
passing test. A round trip through ``write`` and ``read`` is used only where the
claim really is "the upload path preserves bytes"; it is never used to stand in
for "the GPU computed this".

The shaders are project-authored, a few lines each, and tiny enough to be
redistributable with the tests.
"""

from __future__ import annotations

import struct
import unittest

from cna.extensions import engine
from cna.extensions.engine import (
    ComputeShader, GpuTimer, ImageAccess, MemoryBarrier, StorageBuffer,
    barrier_contains,
)
from cna.extensions.engine.errors import (
    ComputeShaderCompileError, EngineDisposedError, EngineInternalError,
    EngineUnavailableError, EngineUnsupportedError,
)

from .engine_fixtures import (
    ENGINE_PRESENT, IDENTITY, NATIVE, in_game, requires_engine,
    requires_engine_gpu,
)

#: ``out[i] = i * scale + offset``.  Chosen because every element differs, the
#: two uniforms have different effects, and Python computes the same value
#: without consulting the GPU.
SCALE_AND_OFFSET = """#version 310 es
layout(local_size_x = 4) in;
layout(std430, binding = 0) buffer Output { float values[]; } outputs;
uniform float scale;
uniform int offset;
void main() {
    uint i = gl_GlobalInvocationID.x;
    outputs.values[i] = float(i) * scale + float(offset);
}
"""

#: Reads one buffer and writes another, so a dispatch that ignored its input
#: binding cannot produce the expected answer by accident.
DOUBLE_INPUT = """#version 310 es
layout(local_size_x = 4) in;
layout(std430, binding = 0) readonly buffer Input { float values[]; } inputs;
layout(std430, binding = 1) buffer Output { float values[]; } outputs;
void main() {
    uint i = gl_GlobalInvocationID.x;
    outputs.values[i] = inputs.values[i] * 2.0 + 1.0;
}
"""

#: Six sources rejected for six different reasons, so a single failure mode
#: cannot stand in for "the compiler refuses bad source".
BROKEN_SOURCES = {
    "empty": "",
    "syntax error": "#version 310 es\nlayout(local_size_x=4) in;\n"
                    "void main(){ this is not GLSL; }\n",
    "no main": "#version 310 es\nlayout(local_size_x=4) in;\nvoid other(){}\n",
    "no #version": "void main(){}\n",
    "undeclared identifier": "#version 310 es\nlayout(local_size_x=4) in;\n"
                             "void main(){ nope = 1.0; }\n",
    "no local_size": "#version 310 es\nvoid main(){}\n",
}


def floats(data: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def as_bytes(values) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


class EngineIdentityTests(unittest.TestCase):
    """The two questions the whole family depends on, asked of CNA itself."""

    @unittest.skipUnless(NATIVE, "needs a configured CNA library")
    def test_availability_is_measured_not_inferred(self) -> None:
        version = engine.layer_version()
        self.assertEqual(engine.is_available(), version != 0)
        # The renderer's name is not the answer.  A build with a rasterizing
        # renderer can still have no engine layer, and this asserts the binding
        # reads the version rather than deciding from the backend.
        self.assertIsInstance(version, int)
        self.assertGreaterEqual(version, 0)

    @requires_engine
    def test_version_agrees_with_the_header_this_binding_was_generated_against(self) -> None:
        self.assertEqual(engine.layer_version(), engine.HEADER_LAYER_VERSION)

    @requires_engine
    def test_version_string_names_the_same_revision(self) -> None:
        """CNA answers a sentence, not a bare number, and it must agree.

        The exact wording is CNA's and is not asserted; what is asserted is that
        the text names the revision :func:`layer_version` reports, so the two
        cannot drift apart.
        """
        text = engine.layer_version_string()
        self.assertTrue(text.strip())
        self.assertIn(str(engine.layer_version()), text)


@unittest.skipUnless(NATIVE and not ENGINE_PRESENT,
                     "only meaningful on a build with no engine layer")
class EngineAbsenceTests(unittest.TestCase):
    """A build without an engine layer must say so, by name.

    This is the control artifact's contribution and it is not a lesser one: the
    distinction between "this build has no engine layer" and "this renderer
    cannot" only exists because one artifact can prove each side of it.
    """

    def test_is_available_is_false(self) -> None:
        self.assertFalse(engine.is_available())
        self.assertEqual(engine.layer_version(), 0)

    def test_constructing_an_engine_object_names_the_build_not_the_renderer(self) -> None:
        def body(game, device, observed):
            try:
                StorageBuffer(device, 64)
            except EngineUnavailableError as error:
                observed["error"] = error
            else:  # pragma: no cover - would be a real change in the artifact
                observed["error"] = None

        observed = in_game(body)
        self.assertIsInstance(observed["error"], EngineUnavailableError)
        self.assertEqual(observed["error"].result, 6)


class MemoryBarrierTests(unittest.TestCase):
    """The barrier mask, checked against Python's own bit arithmetic."""

    def test_all_is_every_named_bit(self) -> None:
        folded = MemoryBarrier.Nothing
        for member in MemoryBarrier:
            if member not in (MemoryBarrier.Nothing, MemoryBarrier.All):
                folded |= member
        self.assertEqual(folded, MemoryBarrier.All)

    def test_bits_are_distinct_powers_of_two(self) -> None:
        seen = set()
        for member in MemoryBarrier:
            if member in (MemoryBarrier.Nothing, MemoryBarrier.All):
                continue
            value = int(member)
            self.assertEqual(value & (value - 1), 0, f"{member.name} is not one bit")
            self.assertNotIn(value, seen)
            seen.add(value)

    @requires_engine
    def test_cna_containment_agrees_with_python(self) -> None:
        cases = [
            (MemoryBarrier.All, MemoryBarrier.ShaderStorage, True),
            (MemoryBarrier.ShaderStorage, MemoryBarrier.All, False),
            (MemoryBarrier.ShaderStorage | MemoryBarrier.Uniform,
             MemoryBarrier.Uniform, True),
            (MemoryBarrier.ShaderStorage | MemoryBarrier.Uniform,
             MemoryBarrier.TextureFetch, False),
            (MemoryBarrier.ShaderStorage | MemoryBarrier.Uniform,
             MemoryBarrier.ShaderStorage | MemoryBarrier.TextureFetch, False),
            (MemoryBarrier.Nothing, MemoryBarrier.Nothing, True),
            (MemoryBarrier.Nothing, MemoryBarrier.Uniform, False),
        ]
        for mask, bits, expected in cases:
            with self.subTest(mask=mask, bits=bits):
                self.assertEqual(barrier_contains(mask, bits), expected)
                self.assertEqual((int(mask) & int(bits)) == int(bits), expected)


@requires_engine_gpu
class StorageBufferTests(unittest.TestCase):
    def test_byte_buffer_reports_its_size_and_preserves_bytes(self) -> None:
        payload = bytes(range(64))

        def body(game, device, observed):
            with StorageBuffer(device, 64) as buffer:
                observed["byte_size"] = buffer.byte_size
                observed["element_count"] = buffer.element_count
                observed["element_byte_size"] = buffer.element_byte_size
                buffer.write(payload)
                observed["read"] = buffer.read()
                observed["partial"] = buffer.read(8)

        observed = in_game(body)
        self.assertEqual(observed["byte_size"], 64)
        # A buffer sized in bytes has no element shape, and says so rather than
        # inventing one.
        self.assertEqual(observed["element_count"], 0)
        self.assertEqual(observed["element_byte_size"], 0)
        self.assertEqual(observed["read"], payload)
        self.assertEqual(observed["partial"], payload[:8])

    def test_typed_buffer_remembers_both_numbers(self) -> None:
        values = [1.5, -2.25, 3.0, 4.75]

        def body(game, device, observed):
            with StorageBuffer.of_elements(device, 4, 4) as buffer:
                observed["shape"] = (buffer.element_count, buffer.element_byte_size,
                                     buffer.byte_size)
                buffer.write_elements(as_bytes(values), 4)
                observed["read"] = floats(buffer.read_elements())

        observed = in_game(body)
        self.assertEqual(observed["shape"], (4, 4, 16))
        self.assertEqual(observed["read"], values)

    def test_an_element_upload_of_the_wrong_shape_is_refused_before_cna(self) -> None:
        def body(game, device, observed):
            with StorageBuffer.of_elements(device, 4, 4) as buffer:
                with self.assertRaises(ValueError):
                    buffer.write_elements(b"\x00" * 6, 4)
                with self.assertRaises(ValueError):
                    buffer.write_elements(b"", 0)
                observed["ok"] = True

        self.assertTrue(in_game(body)["ok"])

    def test_use_after_close_is_refused_by_this_binding(self) -> None:
        def body(game, device, observed):
            buffer = StorageBuffer(device, 16)
            buffer.close()
            observed["closed"] = buffer.is_closed
            with self.assertRaises(EngineDisposedError):
                buffer.byte_size
            # Closing twice is not an error, so an owner does not have to track
            # whether it already did.
            buffer.close()

        self.assertTrue(in_game(body)["closed"])


@requires_engine_gpu
class ComputeShaderTests(unittest.TestCase):
    def test_dispatch_produces_the_values_python_predicts(self) -> None:
        scale, offset, count = 2.5, 7, 8

        def body(game, device, observed):
            with ComputeShader(device, SCALE_AND_OFFSET) as shader, \
                    StorageBuffer(device, count * 4) as output:
                shader.set_uniform("scale", scale)
                shader.set_uniform("offset", offset)
                shader.bind_storage_buffer(0, output)
                shader.dispatch(count // 4)
                shader.barrier(MemoryBarrier.ShaderStorage | MemoryBarrier.BufferUpdate)
                observed["values"] = floats(output.read())

        observed = in_game(body)
        expected = [index * scale + offset for index in range(count)]
        self.assertEqual(observed["values"], expected)

    def test_changing_one_uniform_changes_the_output_it_governs(self) -> None:
        """A second dispatch with a different scale must move every element.

        Two runs of the same program with one input changed is what separates
        "the GPU computed this" from "something wrote plausible numbers once".
        """
        count = 8

        def body(game, device, observed):
            with ComputeShader(device, SCALE_AND_OFFSET) as shader, \
                    StorageBuffer(device, count * 4) as output:
                shader.bind_storage_buffer(0, output)
                for name, scale in (("first", 1.0), ("second", -3.0)):
                    shader.set_uniform("scale", scale)
                    shader.set_uniform("offset", 0)
                    shader.dispatch(count // 4)
                    shader.barrier(MemoryBarrier.All)
                    observed[name] = floats(output.read())

        observed = in_game(body)
        self.assertEqual(observed["first"], [float(i) for i in range(count)])
        self.assertEqual(observed["second"], [i * -3.0 for i in range(count)])

    def test_a_dispatch_reads_the_buffer_bound_to_its_input(self) -> None:
        source = [10.0, -4.0, 0.5, 100.0, 0.0, 1.0, 2.0, 3.0]

        def body(game, device, observed):
            with ComputeShader(device, DOUBLE_INPUT) as shader, \
                    StorageBuffer(device, 32) as inputs, \
                    StorageBuffer(device, 32) as outputs:
                inputs.write(as_bytes(source))
                shader.bind_storage_buffer(0, inputs)
                shader.bind_storage_buffer(1, outputs)
                shader.dispatch(2)
                shader.barrier(MemoryBarrier.All)
                observed["values"] = floats(outputs.read())

        observed = in_game(body)
        self.assertEqual(observed["values"], [value * 2.0 + 1.0 for value in source])

    def test_source_that_does_not_compile_raises_with_the_compiler_log(self) -> None:
        """CNA fails creation; the header says it succeeds. Measured, not assumed.

        ``engine_layer.h`` documents creation as succeeding for source that does
        not compile, with the failure read back through ``is_valid``. On CNA
        0.21.0 every one of these six sources fails creation instead, with
        ``CNA_RESULT_INTERNAL`` and no handle. This asserts what actually
        happens, and it is the test that will notice if CNA later keeps the
        documented contract. See ``docs/engine-upstream-findings.md``.
        """
        def body(game, device, observed):
            for label, source in BROKEN_SOURCES.items():
                try:
                    shader = ComputeShader(device, source)
                except ComputeShaderCompileError as error:
                    observed[label] = ("raised", error.result, error.native_message)
                else:
                    observed[label] = ("created", shader.is_valid, shader.compile_error)
                    shader.close()

        observed = in_game(body)
        for label in BROKEN_SOURCES:
            with self.subTest(source=label):
                outcome = observed[label]
                self.assertEqual(outcome[0], "raised",
                                 f"{label}: CNA now keeps the documented contract; "
                                 "the upstream finding needs re-measuring")
                # The result code is preserved verbatim rather than relabelled.
                self.assertEqual(outcome[1], 12)
                self.assertTrue(outcome[2].strip(),
                                f"{label}: CNA gave no diagnostic")
        # A compiler diagnostic stays catchable as what CNA called it.
        self.assertTrue(issubclass(ComputeShaderCompileError, EngineInternalError))

    def test_a_valid_shader_reports_itself_valid_with_no_diagnostic(self) -> None:
        def body(game, device, observed):
            with ComputeShader(device, SCALE_AND_OFFSET) as shader:
                observed["valid"] = shader.is_valid
                observed["error"] = shader.compile_error

        observed = in_game(body)
        self.assertTrue(observed["valid"])
        self.assertEqual(observed["error"], "")

    def test_dispatch_after_a_bound_buffer_is_closed_is_refused(self) -> None:
        """CNA borrows a bound buffer; this binding will not hand it a dead one."""
        def body(game, device, observed):
            with ComputeShader(device, SCALE_AND_OFFSET) as shader:
                buffer = StorageBuffer(device, 32)
                shader.bind_storage_buffer(0, buffer)
                buffer.close()
                with self.assertRaises(EngineDisposedError) as caught:
                    shader.dispatch(1)
                observed["refusal"] = str(caught.exception)

        observed = in_game(body)
        self.assertIn("storage buffer", observed["refusal"])

    def test_a_bool_uniform_is_refused_rather_than_becoming_a_number(self) -> None:
        def body(game, device, observed):
            with ComputeShader(device, SCALE_AND_OFFSET) as shader:
                with self.assertRaises(TypeError):
                    shader.set_uniform("scale", True)
                observed["ok"] = True

        self.assertTrue(in_game(body).get("ok"))

    def test_image_binding_reports_its_own_capability(self) -> None:
        """A renderer with compute may still have no image binding.

        Whichever way this artifact answers, the answer has to be consistent:
        a ``False`` must make :meth:`bind_image` refuse by name, and a ``True``
        must not.
        """
        from Microsoft.Xna.Framework.Graphics import SurfaceFormat, Texture2D

        def body(game, device, observed):
            with ComputeShader(device, SCALE_AND_OFFSET) as shader:
                observed["supported"] = shader.supports_image_binding
                texture = Texture2D(device, 4, 4, False, SurfaceFormat.Color)
                try:
                    if observed["supported"]:
                        shader.bind_image(0, texture, ImageAccess.ReadWrite)
                        observed["bound"] = True
                    else:
                        with self.assertRaises(EngineUnsupportedError) as caught:
                            shader.bind_image(0, texture, ImageAccess.ReadWrite)
                        observed["refusal"] = str(caught.exception)
                finally:
                    texture.Dispose()

        observed = in_game(body)
        self.assertIn("supported", observed)
        if observed["supported"]:
            self.assertTrue(observed["bound"])
        else:
            self.assertIn("image binding", observed["refusal"])


@requires_engine_gpu
class GpuTimerTests(unittest.TestCase):
    """Timing is not deterministic, so nothing here asserts a duration.

    What is deterministic is the query's state machine, and that is what is
    measured: open/closed, a result arriving, the sample count advancing, and a
    duration that is a real non-negative number rather than a placeholder.
    """

    def test_lifecycle_and_a_collected_result(self) -> None:
        from Microsoft.Xna.Framework import Color

        def body(game, device, observed):
            with GpuTimer(device) as timer:
                observed["supported"] = timer.is_supported
                observed["reason"] = timer.unsupported_reason
                if not timer.is_supported:
                    return
                observed["open_before"] = timer.is_open
                observed["samples_before"] = timer.sample_count
                with timer.measure():
                    observed["open_during"] = timer.is_open
                    device.Clear(Color.CornflowerBlue)
                observed["open_after"] = timer.is_open
                collected = False
                for _ in range(2048):
                    if timer.poll():
                        collected = True
                        break
                observed["collected"] = collected
                observed["samples_after"] = timer.sample_count
                observed["milliseconds"] = timer.last_milliseconds

        observed = in_game(body)
        if not observed["supported"]:
            self.skipTest(f"this renderer has no GPU timer: {observed['reason']}")
        self.assertEqual(observed["reason"], "")
        self.assertFalse(observed["open_before"])
        self.assertTrue(observed["open_during"])
        self.assertFalse(observed["open_after"])
        self.assertTrue(observed["collected"], "no timer result arrived after 2048 polls")
        self.assertEqual(observed["samples_after"], observed["samples_before"] + 1)
        milliseconds = observed["milliseconds"]
        self.assertIsInstance(milliseconds, float)
        self.assertGreaterEqual(milliseconds, 0.0)
        self.assertLess(milliseconds, 60_000.0)


@requires_engine
class EngineSurfaceTests(unittest.TestCase):
    """The extension keeps its own promises about what it hands out."""

    def test_no_public_object_exposes_a_handle(self) -> None:
        for value in (StorageBuffer, ComputeShader, GpuTimer):
            for member in dir(value):
                if member.startswith("_"):
                    continue
                self.assertNotIn(member.lower(),
                                 {"handle", "native_handle", "raw_handle"},
                                 f"{value.__name__}.{member}")

    def test_the_renderer_is_named_in_the_evidence(self) -> None:
        self.assertIsNotNone(IDENTITY)
        self.assertTrue(IDENTITY.renderer_name)
