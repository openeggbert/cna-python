"""Post-processing, against pixels and lifecycle rather than result codes.

A blit's output can be predicted exactly, which is why it is the pass the
plumbing is checked with: source pixels chosen so no two channels agree and no
row matches another, then read back from the destination. A chain is checked
with two passes that do not commute, because a test where order cannot matter
proves nothing about ordering.

Ownership is checked by making CNA refuse: a pool asked to reset while a view is
out, a factory asked to clear while an effect is out. Those refusals are the
contract, so a test that avoids them tests nothing.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import Color, Matrix
from Microsoft.Xna.Framework.Graphics import (
    DepthFormat, RenderTarget2D, SamplerState, SurfaceFormat, Texture2D,
)

from cna.extensions.engine import (
    BlitPass, EffectPass, FullscreenPass, PostProcessChain, PostProcessContext,
    RenderTargetPool, ShaderEffectFactory, bind_render_target,
)
from cna.extensions.engine.errors import (
    EngineDisposedError, EngineError, EngineStateError,
)

from .engine_fixtures import in_game, over_frames, requires_engine_gpu

#: A 4x4 pattern where every pixel differs from every other, no channel equals
#: another within a pixel, and the image is not symmetric in either axis. A blit
#: that transposed, flipped, swizzled or offset it would produce a different
#: image rather than the same one.
def asymmetric_pixels(width: int = 4, height: int = 4) -> list[Color]:
    pixels = []
    for y in range(height):
        for x in range(width):
            pixels.append(Color(11 + 17 * x + 3 * y,
                                40 + 5 * x + 29 * y,
                                90 + 2 * x + 7 * y,
                                255))
    return pixels


#: Multiplies red by a uniform. Two of these with different factors do not
#: commute with the additive pass below, which is what makes chain order
#: observable.
#: CNA draws every full-screen pass through ``SpriteBatch``, so a pass shader
#: speaks the batch's vertex contract: position, texture coordinate and vertex
#: colour in locations 0..2, the batch's own ``projection``, and ``texture1``
#: for the sampler. Copied from the convention CNA's own passes use, not
#: guessed; a shader that got it wrong would link and draw nothing.
PASS_VERTEX = """#version 300 es
precision highp float;
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aTexCoord;
layout(location = 2) in vec4 aColor;
out vec2 TexCoord;
uniform mat4 projection;
void main() { gl_Position = projection * vec4(aPos, 0.0, 1.0); TexCoord = aTexCoord; }
"""

HALVE_RED_FRAGMENT = """#version 300 es
precision highp float;
in vec2 TexCoord;
out vec4 FragColor;
uniform sampler2D texture1;
void main() {
    vec4 c = texture(texture1, TexCoord);
    FragColor = vec4(c.r * 0.5, c.g, c.b, c.a);
}
"""


def read_back(target: RenderTarget2D) -> list[Color]:
    pixels = [Color(0, 0, 0, 0)] * (target.Width * target.Height)
    target.GetData(pixels)
    return pixels


def rgba(pixels) -> list[tuple[int, int, int, int]]:
    return [(int(p.R), int(p.G), int(p.B), int(p.A)) for p in pixels]


@requires_engine_gpu
class RenderTargetPoolTests(unittest.TestCase):
    def test_the_same_shape_and_slot_is_one_target_and_a_new_slot_is_another(self) -> None:
        def body(game, device, observed):
            with RenderTargetPool(device) as pool:
                observed["empty"] = pool.target_count
                first = pool.acquire(8, 8)
                observed["after_first"] = pool.target_count
                observed["bytes"] = pool.estimated_bytes
                second = pool.acquire(8, 8)
                observed["after_same"] = pool.target_count
                third = pool.acquire(8, 8, slot=1)
                observed["after_other_slot"] = pool.target_count
                fourth = pool.acquire(16, 8)
                observed["after_other_shape"] = pool.target_count
                observed["shape"] = (first.Width, first.Height,
                                     int(first.Format), int(fourth.Width))
                for view in (first, second, third, fourth):
                    view.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["empty"], 0)
        self.assertEqual(observed["after_first"], 1)
        # The point of a pool: the same request does not allocate again.
        self.assertEqual(observed["after_same"], 1)
        self.assertEqual(observed["after_other_slot"], 2)
        self.assertEqual(observed["after_other_shape"], 3)
        self.assertEqual(observed["shape"], (8, 8, int(SurfaceFormat.Color), 16))
        # 8*8 colour pixels at four bytes is the floor for one target; three
        # targets must estimate at least that much for the first.
        self.assertGreaterEqual(observed["bytes"], 8 * 8 * 4)

    def test_reset_is_refused_while_a_view_is_out_and_allowed_after(self) -> None:
        def body(game, device, observed):
            with RenderTargetPool(device) as pool:
                view = pool.acquire(8, 8)
                try:
                    pool.reset()
                except EngineError as error:
                    observed["refused"] = type(error).__name__
                else:
                    observed["refused"] = None
                view.Dispose()
                pool.reset()
                observed["after_reset"] = pool.target_count

        observed = in_game(body)
        self.assertEqual(observed["refused"], "EngineStateError")
        self.assertEqual(observed["after_reset"], 0)

    def test_disposing_a_view_does_not_dispose_the_pooled_target(self) -> None:
        """The contract that makes a pool a pool rather than an allocator."""
        def body(game, device, observed):
            with RenderTargetPool(device) as pool:
                first = pool.acquire(8, 8)
                first.Dispose()
                observed["still_pooled"] = pool.target_count
                again = pool.acquire(8, 8)
                observed["no_new_target"] = pool.target_count
                again.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["still_pooled"], 1)
        self.assertEqual(observed["no_new_target"], 1)

    def test_a_pooled_view_is_a_working_render_target(self) -> None:
        """It binds, it clears, and the pixels come back."""
        def body(game, device, observed):
            with RenderTargetPool(device) as pool:
                view = pool.acquire(4, 4)
                try:
                    with bind_render_target(device, view) as scope:
                        observed["recorded"] = scope.has_recorded_previous
                        device.Clear(Color(20, 130, 200, 255))
                    observed["pixels"] = rgba(read_back(view))
                finally:
                    view.Dispose()

        observed = in_game(body)
        self.assertEqual(set(observed["pixels"]), {(20, 130, 200, 255)})
        self.assertIsInstance(observed["recorded"], bool)


@requires_engine_gpu
class RenderTargetScopeTests(unittest.TestCase):
    def test_the_scope_restores_the_previous_binding(self) -> None:
        """What was bound before the scope is what is bound after it."""
        def body(game, device, observed):
            outer = RenderTarget2D(device, 4, 4)
            inner = RenderTarget2D(device, 4, 4)
            try:
                device.SetRenderTarget(outer)
                device.Clear(Color(10, 20, 30, 255))
                with bind_render_target(device, inner):
                    device.Clear(Color(200, 100, 50, 255))
                # Restored: this clear must land on `outer`, not on `inner`.
                device.Clear(Color(90, 80, 70, 255))
                device.SetRenderTarget(None)
                observed["outer"] = rgba(read_back(outer))
                observed["inner"] = rgba(read_back(inner))
            finally:
                outer.Dispose()
                inner.Dispose()

        observed = in_game(body)
        self.assertEqual(set(observed["outer"]), {(90, 80, 70, 255)})
        self.assertEqual(set(observed["inner"]), {(200, 100, 50, 255)})

    def test_nested_scopes_must_close_innermost_first(self) -> None:
        def body(game, device, observed):
            first = RenderTarget2D(device, 4, 4)
            second = RenderTarget2D(device, 4, 4)
            try:
                outer = bind_render_target(device, first)
                inner = bind_render_target(device, second)
                try:
                    outer.end()
                except EngineError as error:
                    observed["out_of_order"] = type(error).__name__
                else:
                    observed["out_of_order"] = None
                inner.end()
                outer.end()
                observed["closed"] = (inner.is_closed, outer.is_closed)
            finally:
                first.Dispose()
                second.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["out_of_order"], "EngineStateError")
        self.assertEqual(observed["closed"], (True, True))


@requires_engine_gpu
class ShaderEffectFactoryTests(unittest.TestCase):
    def test_a_repeat_request_is_served_from_the_cache(self) -> None:
        def body(game, device, observed):
            with ShaderEffectFactory(device) as factory:
                observed["before"] = (factory.compile_count, factory.contains("tint"))
                first = factory.acquire("tint", PASS_VERTEX, HALVE_RED_FRAGMENT)
                observed["after_first"] = (factory.compile_count, factory.contains("tint"))
                second = factory.acquire("tint", PASS_VERTEX, HALVE_RED_FRAGMENT)
                observed["after_second"] = factory.compile_count
                observed["has_parameters"] = first.Parameters is not None
                first.Dispose()
                second.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["before"], (0, False))
        self.assertEqual(observed["after_first"], (1, True))
        # Cached: the second acquire compiles nothing.
        self.assertEqual(observed["after_second"], 1)
        self.assertTrue(observed["has_parameters"])

    def test_clear_is_refused_while_an_effect_view_is_out(self) -> None:
        def body(game, device, observed):
            with ShaderEffectFactory(device) as factory:
                effect = factory.acquire("tint", PASS_VERTEX, HALVE_RED_FRAGMENT)
                try:
                    factory.clear()
                except EngineError as error:
                    observed["refused"] = type(error).__name__
                else:
                    observed["refused"] = None
                effect.Dispose()
                factory.clear()
                observed["after_clear"] = factory.contains("tint")
                # Clearing does not reset the compile count, which is what makes
                # the count usable as evidence.
                observed["compile_count"] = factory.compile_count

        observed = in_game(body)
        self.assertEqual(observed["refused"], "EngineStateError")
        self.assertFalse(observed["after_clear"])
        self.assertEqual(observed["compile_count"], 1)


@requires_engine_gpu
class FullscreenPassTests(unittest.TestCase):
    def test_a_copy_reproduces_every_source_pixel(self) -> None:
        source_pixels = asymmetric_pixels()

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(source_pixels)
            destination = RenderTarget2D(device, 4, 4)
            with FullscreenPass(device) as pass_:
                try:
                    pass_.draw(source, destination, 4, 4,
                               sampler=SamplerState.PointClamp)
                    observed["copied"] = rgba(read_back(destination))
                finally:
                    source.Dispose()
                    destination.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["copied"], rgba(source_pixels))


@requires_engine_gpu
class PostProcessPassTests(unittest.TestCase):
    def test_a_blit_pass_copies_its_source_exactly(self) -> None:
        source_pixels = asymmetric_pixels()

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(source_pixels)
            destination = RenderTarget2D(device, 4, 4)
            pass_ = BlitPass(device)
            try:
                observed["name"] = pass_.name
                observed["supported"] = pass_.is_supported(device)
                pass_.apply(PostProcessContext(source=source, destination=destination,
                                               width=4, height=4))
                observed["pixels"] = rgba(read_back(destination))
            finally:
                pass_.close()
                source.Dispose()
                destination.Dispose()

        observed = in_game(body)
        self.assertTrue(observed["name"].strip(), "a pass must name itself")
        self.assertTrue(observed["supported"])
        self.assertEqual(observed["pixels"], rgba(source_pixels))

    def test_an_effect_pass_draws_through_its_effect(self) -> None:
        """Red halved, green and blue untouched: the shader's own arithmetic."""
        source_pixels = asymmetric_pixels()

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(source_pixels)
            destination = RenderTarget2D(device, 4, 4)
            factory = ShaderEffectFactory(device)
            effect = factory.acquire("halve-red", PASS_VERTEX, HALVE_RED_FRAGMENT)
            pass_ = EffectPass(device, effect, "halve-red")
            try:
                observed["name"] = pass_.name
                observed["effect_is_the_one_given"] = pass_.effect is effect
                pass_.apply(PostProcessContext(source=source, destination=destination,
                                               width=4, height=4))
                observed["pixels"] = rgba(read_back(destination))
            finally:
                pass_.close()
                effect.Dispose()
                factory.close()
                source.Dispose()
                destination.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["name"], "halve-red")
        self.assertTrue(observed["effect_is_the_one_given"])
        for produced, original in zip(observed["pixels"], source_pixels):
            # 8-bit storage rounds, so the red channel is within one of half.
            self.assertLessEqual(abs(produced[0] - int(original.R) // 2), 1,
                                 f"{produced} from {rgba([original])[0]}")
            self.assertEqual(produced[1], int(original.G))
            self.assertEqual(produced[2], int(original.B))

    def test_the_pass_keeps_its_borrowed_effect_alive(self) -> None:
        """CNA borrows the effect; an unreferenced one must not be collected."""
        import gc

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(asymmetric_pixels())
            destination = RenderTarget2D(device, 4, 4)
            factory = ShaderEffectFactory(device)
            pass_ = EffectPass(
                device, factory.acquire("halve-red", PASS_VERTEX, HALVE_RED_FRAGMENT),
                "halve-red")
            try:
                gc.collect()
                pass_.apply(PostProcessContext(source=source, destination=destination,
                                               width=4, height=4))
                observed["applied"] = True
                observed["effect_still_there"] = pass_.effect is not None
            finally:
                effect = pass_.effect
                pass_.close()
                if effect is not None:
                    effect.Dispose()
                factory.close()
                source.Dispose()
                destination.Dispose()

        observed = in_game(body)
        self.assertTrue(observed["applied"])
        self.assertTrue(observed["effect_still_there"])

    def test_a_closed_pass_refuses_before_reaching_cna(self) -> None:
        def body(game, device, observed):
            pass_ = BlitPass(device)
            pass_.close()
            observed["closed"] = pass_.is_closed
            with self.assertRaises(EngineDisposedError):
                pass_.name
            pass_.close()

        self.assertTrue(in_game(body)["closed"])


@requires_engine_gpu
class PostProcessChainTests(unittest.TestCase):
    def _two_non_commuting_passes(self, device, factory):
        """Halve red, then subtract a constant -- and the reverse, which differs.

        ``(r/2) - 0.25`` and ``(r - 0.25)/2`` are not the same function, so the
        chain's order is observable in the output rather than only in a count.
        """
        halve = factory.acquire("halve-red", PASS_VERTEX, HALVE_RED_FRAGMENT)
        subtract = factory.acquire("subtract-red", PASS_VERTEX, SUBTRACT_RED_FRAGMENT)
        return halve, subtract

    def test_chain_order_changes_the_pixels(self) -> None:
        source_pixels = [Color(200, 60, 30, 255)] * 16

        def run(device, first_name, second_name, factory, source, destination):
            first = factory.acquire(first_name, PASS_VERTEX, FRAGMENTS[first_name])
            second = factory.acquire(second_name, PASS_VERTEX, FRAGMENTS[second_name])
            chain = PostProcessChain(device)
            passes = [EffectPass(device, first, first_name),
                      EffectPass(device, second, second_name)]
            try:
                for item in passes:
                    chain.add(item)
                assert chain.pass_count == 2
                chain.apply(PostProcessContext(source=source, destination=destination,
                                               width=4, height=4))
                return rgba(read_back(destination))
            finally:
                chain.close()
                for item in passes:
                    item.close()
                first.Dispose()
                second.Dispose()

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(source_pixels)
            destination = RenderTarget2D(device, 4, 4)
            factory = ShaderEffectFactory(device)
            try:
                observed["halve_then_subtract"] = run(
                    device, "halve-red", "subtract-red", factory, source, destination)
                observed["subtract_then_halve"] = run(
                    device, "subtract-red", "halve-red", factory, source, destination)
            finally:
                factory.close()
                source.Dispose()
                destination.Dispose()

        observed = in_game(body)
        first_order = observed["halve_then_subtract"][0]
        second_order = observed["subtract_then_halve"][0]
        # (200/2) - 64 = 36 against (200 - 64)/2 = 68, both out of 255.
        self.assertLessEqual(abs(first_order[0] - 36), 2, first_order)
        self.assertLessEqual(abs(second_order[0] - 68), 2, second_order)
        self.assertNotEqual(first_order[0], second_order[0])

    def test_add_clear_and_count(self) -> None:
        def body(game, device, observed):
            chain = PostProcessChain(device)
            first, second = BlitPass(device), BlitPass(device)
            try:
                observed["empty"] = chain.pass_count
                chain.add(first)
                chain.add(second)
                observed["two"] = (chain.pass_count, len(chain))
                chain.clear()
                observed["cleared"] = chain.pass_count
                # Clearing a chain that borrowed its passes leaves them usable.
                observed["first_alive"] = not first.is_closed
                observed["first_name"] = first.name
            finally:
                chain.close()
                first.close()
                second.close()

        observed = in_game(body)
        self.assertEqual(observed["empty"], 0)
        self.assertEqual(observed["two"], (2, 2))
        self.assertEqual(observed["cleared"], 0)
        self.assertTrue(observed["first_alive"])
        self.assertTrue(observed["first_name"].strip())

    def test_a_chain_with_no_source_is_refused(self) -> None:
        def body(game, device, observed):
            chain = PostProcessChain(device)
            pass_ = BlitPass(device)
            try:
                chain.add(pass_)
                try:
                    chain.apply(PostProcessContext(width=4, height=4))
                except EngineError as error:
                    observed["no_source"] = type(error).__name__
                else:
                    observed["no_source"] = None
                source = Texture2D(device, 4, 4)
                try:
                    chain.apply(PostProcessContext(source=source, width=0, height=0))
                except EngineError as error:
                    observed["no_size"] = type(error).__name__
                else:
                    observed["no_size"] = None
                finally:
                    source.Dispose()
            finally:
                chain.close()
                pass_.close()

        observed = in_game(body)
        self.assertEqual(observed["no_source"], "EngineArgumentError")
        self.assertEqual(observed["no_size"], "EngineArgumentError")

    def test_the_target_pool_is_a_counted_borrow(self) -> None:
        def body(game, device, observed):
            chain = PostProcessChain(device)
            pool = chain.target_pool
            try:
                observed["borrowed"] = pool.is_borrowed
                observed["count"] = pool.target_count
                try:
                    chain.close()
                except EngineError as error:
                    observed["refused"] = type(error).__name__
                else:
                    observed["refused"] = None
            finally:
                pool.close()
            chain.close()
            observed["closed"] = chain.is_closed

        observed = in_game(body)
        self.assertTrue(observed["borrowed"])
        self.assertEqual(observed["refused"], "EngineStateError")
        self.assertTrue(observed["closed"])

    def test_gpu_timing_is_only_observable_after_the_chain_has_run(self) -> None:
        """ENGINE-004, and the timings that do arrive once it has.

        ``engine_layer.h`` says to enable timing and then ask
        ``is_gpu_timing_enabled`` what the request got, because a renderer
        without timers accepts and stays off. On a renderer that *does* have
        timers the read straight after the write still answers ``False``: the
        flag only becomes observable once the chain has applied. Following the
        documented protocol therefore reports "no timing" on a device that is
        about to time perfectly well.

        A query opened in one frame is also collected in a later one, so this
        runs over frames rather than inside a single ``Draw``.
        """
        source_pixels = asymmetric_pixels()

        def body(game, device, observed, frame):
            if frame == 1:
                source = Texture2D(device, 4, 4)
                source.SetData(source_pixels)
                observed["_keep"] = (source, RenderTarget2D(device, 4, 4),
                                     PostProcessChain(device), BlitPass(device))
                _source, _destination, chain, pass_ = observed["_keep"]
                chain.add(pass_)
                observed["before_write"] = chain.gpu_timing_enabled
                chain.gpu_timing_enabled = True
                observed["after_write_before_apply"] = chain.gpu_timing_enabled
            source, destination, chain, pass_ = observed["_keep"]
            chain.apply(PostProcessContext(source=source, destination=destination,
                                           width=4, height=4))
            observed[f"frame{frame}"] = (
                chain.gpu_timing_enabled,
                [(t.name, t.sample_count, t.milliseconds) for t in chain.pass_timings])
            if frame == 8:
                chain.close()
                pass_.close()
                source.Dispose()
                destination.Dispose()
                observed.pop("_keep")

        observed = over_frames(body, frames=8)
        self.assertFalse(observed["before_write"])
        # The documented read-back protocol, giving the wrong answer.
        self.assertFalse(observed["after_write_before_apply"],
                         "CNA now reports the flag before the first apply; "
                         "ENGINE-004 needs re-measuring")
        enabled_first, timings_first = observed["frame1"]
        self.assertTrue(enabled_first, "the flag is observable once the chain has run")
        self.assertEqual([(name, samples) for name, samples, _ in timings_first],
                         [("Blit", 0)],
                         "the first frame's query has not been collected yet")

        enabled_last, timings_last = observed["frame8"]
        self.assertTrue(enabled_last)
        self.assertEqual(len(timings_last), 1)
        name, samples, milliseconds = timings_last[0]
        self.assertEqual(name, "Blit")
        self.assertEqual(samples, 7, "one sample per frame after the first")
        self.assertGreater(milliseconds, 0.0)
        self.assertLess(milliseconds, 1000.0)

        # ENGINE-003 again, through the chain: the first sample it collects is
        # the same unsigned 32-bit wrap the standalone timer produces.
        _enabled, timings_second = observed["frame2"]
        self.assertAlmostEqual(timings_second[0][2], (2 ** 32 - 1) / 1e6, places=2)

    def test_gpu_timing_can_be_turned_off_again(self) -> None:
        def body(game, device, observed):
            chain = PostProcessChain(device)
            try:
                chain.gpu_timing_enabled = True
                chain.gpu_timing_enabled = False
                observed["off"] = chain.gpu_timing_enabled
            finally:
                chain.close()

        self.assertFalse(in_game(body)["off"])

    def test_reset_targets_releases_the_pooled_intermediates(self) -> None:
        source_pixels = asymmetric_pixels()

        def body(game, device, observed):
            source = Texture2D(device, 4, 4)
            source.SetData(source_pixels)
            destination = RenderTarget2D(device, 4, 4)
            chain = PostProcessChain(device)
            first, second = BlitPass(device), BlitPass(device)
            try:
                chain.add(first)
                chain.add(second)
                chain.apply(PostProcessContext(source=source, destination=destination,
                                               width=4, height=4))
                pool = chain.target_pool
                observed["allocated"] = pool.target_count
                pool.close()
                chain.reset_targets()
                pool = chain.target_pool
                observed["after_reset"] = pool.target_count
                pool.close()
                # Two blits still reproduce the source exactly.
                observed["pixels"] = rgba(read_back(destination))
            finally:
                chain.close()
                first.close()
                second.close()
                source.Dispose()
                destination.Dispose()

        observed = in_game(body)
        self.assertGreater(observed["allocated"], 0,
                           "a chain of two passes has to ping-pong through something")
        self.assertEqual(observed["after_reset"], 0)
        self.assertEqual(observed["pixels"], rgba(source_pixels))


SUBTRACT_RED_FRAGMENT = """#version 300 es
precision highp float;
in vec2 TexCoord;
out vec4 FragColor;
uniform sampler2D texture1;
void main() {
    vec4 c = texture(texture1, TexCoord);
    FragColor = vec4(max(c.r - 0.25, 0.0), c.g, c.b, c.a);
}
"""

FRAGMENTS = {
    "halve-red": HALVE_RED_FRAGMENT,
    "subtract-red": SUBTRACT_RED_FRAGMENT,
}
