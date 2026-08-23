# Runtime capability inventory

Qualified boundary: CNA C ABI 0.7.0; Linux x86-64 HEADLESS, NULL audio.

| Operation | Status | Evidence | Notes |
|---|---|---|---|
| Game.Components/services/traversal | VERIFIED_MANAGED | tests.test_game_graphics_foundation.GameObjectModelTests | Per-Game services and snapshot traversal with stable ordering. |
| Game.ResetElapsedTime/SuppressDraw | VERIFIED_NATIVE | cna_game_reset_elapsed_time; cna_game_suppress_draw | Calls the active native Game lifecycle. |
| Game activation/deactivation delivery | BACKEND_BLOCKED | cna_game_subscribe | Infrastructure is native; HEADLESS produces no fabricated transition. |
| GameWindow properties and screen-device change | VERIFIED_NATIVE | runtime_window.h routes | HEADLESS reports its real null-window state. |
| GameWindow resize/orientation events | BACKEND_BLOCKED | cna_game_window_subscribe | No HEADLESS window transition is fabricated. |
| SurfaceFormat and graphics value enums | VERIFIED_MANAGED | behavior graphics.surface_format.values | Values follow XNA metadata, independently of CNA enum ordering. |
| Viewport.Project/Unproject | VERIFIED_MANAGED | behavior graphics.viewport.* | Binary32 XNA operation ordering. |
| GraphicsResource disposal event | VERIFIED_NATIVE | cna_graphics_resource_subscribe_disposing | Exactly-once event before native release; double Dispose is idempotent. |
| GraphicsDevice.ResourceCreated/ResourceDestroyed | UPSTREAM_CNA_BLOCKED | graphics_device.h identityless event payloads | ABI 0.7 cannot reconstruct stable Python resource identity and Tag payload. |
| Graphics adapter/display/presentation queries | VERIFIED_NATIVE | display.h routes and native integration | Durable adapter and display facades; one actual HEADLESS adapter. |
| Blend/depth/rasterizer/sampler state binding | VERIFIED_NATIVE | graphics_state.h and native foundation test | XNA defaults and post-bind freeze are managed; descriptors are copied by CNA. |
| SamplerStateCollection/TextureCollection | VERIFIED_NATIVE | graphics_device.h state/texture slot routes | Durable per-device stage facades; Reach exposes zero vertex-stage slots. |
| Texture metadata and Color transfer | VERIFIED_NATIVE | texture.h and native tests | Format and level count are read from native resource information. |
| Texture2D PNG/JPEG encoding | VERIFIED_NATIVE | cna_texture2d_*encoded* and native foundation test | Uses CNA encoders with writable-stream validation and rollback. |
| Vertex declarations and built-in codecs | VERIFIED_MANAGED | graphics.vertex.strides; explicit struct.pack codecs | No reflection, pickle, JSON, or __dict__ layout inference. |
| Vertex/Index buffer create, transfer, binding | VERIFIED_NATIVE | vertex_resources.h; index_resources.h; native foundation/stress | Owned handles; native binding borrows and bound disposal is rejected. |
| DynamicVertexBuffer.SetData(offset, streaming options) | UPSTREAM_CNA_BLOCKED | vertex_resources.h transfer route separation | ABI 0.7 has typed streaming options and raw destination offsets, but no route combining both. |
| DrawPrimitives/DrawIndexedPrimitives | BACKEND_BLOCKED | ABI dispatch observed CNA_RESULT_NOT_SUPPORTED on HEADLESS | Arguments and bindings reach the real CNA route; no visible 3D backend exists. |
| DrawInstancedPrimitives | HARDWARE_PENDING | cna_graphics_device_draw_instanced_primitives | Real instancing route is bound; it is never emulated with repeated draws. |
| DrawUserPrimitives/DrawUserIndexedPrimitives | BACKEND_BLOCKED | graphics_device.h user-array routes | Only explicit built-in vertex codecs and deterministic contiguous bytes are accepted. |
| RenderTarget2D create/bind/query | VERIFIED_NATIVE | render_target.h and native foundation/stress | Command-path and lifetime verified under HEADLESS. |
| RenderTarget visible output | HARDWARE_PENDING | HEADLESS renderer_available=false | No visual correctness claim is made from command-path evidence. |
| RenderTargetCube | UNIMPLEMENTED_CNA_PYTHON | deliberately outside the Effect/Model dependency closure | TextureCube is implemented, but the unrelated RenderTargetCube public type remains deferred. |
| GraphicsDevice.Present() | VERIFIED_NATIVE | cna_graphics_device_present and 60/600-frame consumers | HEADLESS command completion is not visible presentation evidence. |
| GraphicsDevice.Present(rectangles, window) | UPSTREAM_CNA_BLOCKED | No ABI 0.7 route | Raises NativeCapabilityError after strict argument validation. |
| GraphicsDevice.Reset events | VERIFIED_NATIVE | cna_graphics_device_reset* and event subscriptions | Resetting and Reset are delivered by actual native transitions. |
| GraphicsDevice.DeviceLost | BACKEND_BLOCKED | event subscription exists | HEADLESS has no deterministic device-loss transition and none is fabricated. |
| GraphicsDeviceManager lifecycle/preparing settings | VERIFIED_NATIVE | runtime_graphics_manager.h routes | Mutable preparation callback writes validated settings back to CNA. |
| SpriteFont metrics and DrawString | VERIFIED_NATIVE | sprite_font.h plus SpriteBatch glyph submissions | Private glyph factory is used until Content/XNB can construct public assets. |
| SpriteFont public Content loading | VERIFIED_NATIVE | SpriteFontReader graph; tests.test_content_native.NativeContentTests | Real reader-table graph constructs the existing native SpriteFont, verifies metrics/DrawString, cache identity, and reverse atlas ownership. |
| ContentManager.OpenStream / TitleContainer.OpenStream | VERIFIED_NATIVE | cna_title_location_set_path_ext; cna_title_container_read_ext; managed path suite | Deterministic application title root with lexical and symlink escape rejection; no process-CWD fallback. |
| ContentManager.ReadAsset/XNB | VERIFIED_NATIVE | managed ContentReader suite plus native Texture2D/SpriteFont/buffer graphs | Header, exact reader resolver, versions, custom readers, shared fixups, external references, cache, rollback, and reverse disposal are exercised. |
| XNB LZX framing and decoder | VERIFIED_MANAGED | single/multi-frame synthetic suite and independent MonoGame fixture comparison | Persistent 64 KiB state, short/extended framing, exact declared output, malformed boundaries, and compressed resource graphs. |
| ResourceContentManager | VERIFIED_MANAGED | Mapping/GetObject adapter and stream ownership tests | No public System.Resources support package is introduced. |
| Content Load[T] caller type enforcement | LANGUAGE_MAPPING_LIMITATION | docs/xna-python-mapping.md generic-erasure rule | The root reader determines runtime shape; Python cannot recover erased caller T, while reader-declared target shape remains validated. |
| ContentReader.ReadRawObject[T] without reader token | LANGUAGE_MAPPING_LIMITATION | tests.test_content.ContentTests | No assignment-context, caller-bytecode, asset-name, or locals inference; explicit-reader overloads are functional. |
| Effect reflection ownership graph | VERIFIED_NATIVE | native identity integration and effect-model ownership stress | Effect is the sole owner; parameter, annotation, technique, pass, light, and collection handles are stable owned views retained by and invalidated with the Effect. |
| Effect typed parameters | VERIFIED_NATIVE | cna_effect_parameter_get/set_value*, native codec integration | Boolean, Int32, Single, String, Vector2/3/4, Quaternion, Matrix/transpose, all selected arrays, and Texture2D/Cube identities use copied typed storage. |
| Effect annotations | VERIFIED_NATIVE | cna_effect_annotation_get_value_* integration | Read-only scalar, string, vector, and matrix codecs use real annotation views and metadata validation. |
| EffectPass.Apply | VERIFIED_NATIVE | cna_effect_pass_apply; stock and Model-XNB draw tests | A real native pass identity is applied repeatedly; applying after parent disposal is rejected. |
| Compiled Effect creation route | VERIFIED_NATIVE | cna_effect_create_compiled with project-authored legal conformance FXB SHA-256 2e1fe1dd74d67f4395ae6db4451c1a19ee4478dfe7906f9d665a499e28d2a074 | The byte buffer reaches CNA with exact ownership rollback; route verification is distinct from backend acceptance. |
| Compiled Effect execution on HEADLESS | BACKEND_BLOCKED | qualified ABI-0.7 artifact returns structured result 6 for legal FXB | HEADLESS does not advertise compiled effects; no shader or visible output is fabricated. |
| BasicEffect | VERIFIED_NATIVE | cna_basic_effect_* property/create routes and cna_effect_pass_apply | Native state, directional lights, clone isolation, texture retention, and Apply are verified; visible pixels are not. |
| AlphaTestEffect | VERIFIED_NATIVE | cna_alpha_test_effect_* and cna_effect_pass_apply | Native properties, texture retention, clone/disposal route, and Apply are verified. |
| DualTextureEffect | VERIFIED_NATIVE | cna_dual_texture_effect_* and cna_effect_pass_apply | Both native texture slots, managed identity retention, state, and Apply are verified. |
| EnvironmentMapEffect | VERIFIED_NATIVE | cna_environment_map_effect_* and cna_effect_pass_apply | Texture2D/TextureCube identities, lights/fog/matrices, state, and Apply are verified. |
| SkinnedEffect | VERIFIED_NATIVE | cna_skinned_effect_* and cna_effect_pass_apply | Exact 1..72 bone-transform transfer, weights, lights/fog/matrices, state, and Apply are verified. |
| EffectMaterial | VERIFIED_NATIVE | cna_effect_material_create | The material owns a distinct native Effect cloned from its source. |
| Stock-effect visible GPU output | BACKEND_BLOCKED | qualified renderer is HEADLESS | Creation, state mutation, pass application, and command dispatch pass; visible shader output is not qualified. |
| Texture3D | BACKEND_BLOCKED | cna_texture3d_create/get_info/set_data/get_data ABI audit and 20 safe failure cycles | The complete Color codec and validation reach the exact ABI; HEADLESS returns structured result 6 at creation. |
| TextureCube creation and metadata | VERIFIED_NATIVE | cna_texturecube_create/get_info and repeated lifecycle tests | All six faces and mip/rectangle contracts are implemented over the canonical ABI. |
| TextureCube Color transfer on HEADLESS | BACKEND_BLOCKED | cna_texturecube_set_data returns structured result 6 in 20 rollback cycles | No storage is emulated or relabeled; create/info/dispose remain verified native. |
| Model graph | VERIFIED_MANAGED | Model collection/identity behavior and direct graph stress | Bones, hierarchy, meshes, parts, effects, tags, transform copies, and deterministic invalidation are verified. |
| Model.Draw command path | VERIFIED_NATIVE | XNB Model -> buffers -> BasicEffect -> native pass -> cna_graphics_device_draw_indexed_primitives | The ordinary indexed route accepts the command under HEADLESS; no special Model renderer or visible-output claim exists. |
| Model visible GPU output | BACKEND_BLOCKED | qualified renderer is HEADLESS | MODEL_DRAW_NATIVE_DISPATCH passes, but rendered pixels cannot be qualified. |
| Model XNB | VERIFIED_NATIVE | legal synthetic Windows XNB v5 graph integration | Two bones, one mesh, two parts, shared native buffers/BasicEffect, tags, cache, Unload/reload, external reference, and rollback are verified. |
| Compressed Model XNB | VERIFIED_NATIVE | same legal Model payload through existing managed LZX framing | The same reader table, reader, public graph, shared native resources, draw, cache, Unload/reload, and rollback paths are used. |
