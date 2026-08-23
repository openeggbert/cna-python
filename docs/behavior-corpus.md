# Behavior corpus

`behavior/xna40-pure-values.json` is the normalized CNA-Python differential
corpus for the completed pure foundation and managed Content/Audio projections.
It grew from 16 observations / 35 scalar assertions to 167 observations / 925
assertions. Groups cover
MathHelper, Vector2/3/4, Quaternion, Matrix, Color, Point, Rectangle, Plane,
Ray, BoundingBox, BoundingSphere, BoundingFrustum, SurfaceFormat,
Viewport.Project/Unproject, PresentationParameters defaults, graphics-state
defaults, the selected built-in vertex strides, Content serializer defaults and
clone behavior, RootDirectory/disposal, primitive/value reads, reader versions,
cache identity, shared-resource fixup order, external-reference normalization,
Audio values, all seventeen packed formats, Curve, and all thirteen Design
converter shapes.

The corpus includes ordinary and negative values, exact binary32 golden bits,
zero and signed zero, NaN and infinities, scalar-division evaluation order,
singular inversion, mirrored decomposition, degenerate LookAt/Plane/shadow,
XNA hashes and strings, transforms, tangent and near-parallel intersections,
frustum plane/corner extraction, convex/GJK relations, packed integer identities,
historical XNA half edges, normalized saturation, curve loops/tangents/duplicate
keys, culture-specific Design text, immutable property decomposition,
CreateInstance, and executable reconstruction descriptors.

The expected values are labelled `PURE_XNA_DERIVED`: they come from the pinned
XNA reference metadata plus IL/algorithm analysis. They are not described as a
Windows runtime capture and Linux CNA output was not used as the XNA authority.
`tools/run_behavior_corpus.py` produces
`docs/generated/behavior-corpus-report.json` and currently reports:

```text
OBSERVATIONS=167
ASSERTIONS=925
FAILURES=0
```

Milestone 7 contributes 10 Curve, 17 PackedVector, and 21 Design observations.
Each packed observation includes default zero, ordinary, boundary, clamp,
round-trip, PackedValue identity, and equality assertions; HalfSingle adds
subnormal, non-finite, and exponent-31 bit evidence.

Native lifecycle/graphics/input tests are separately labelled
`NATIVE_CNA_RUNTIME`. HEADLESS route execution is not physical-device evidence;
future `PLATFORM/HARDWARE` observations must come from qualified hardware.
