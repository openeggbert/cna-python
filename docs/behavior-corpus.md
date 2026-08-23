# Behavior corpus

`behavior/xna40-pure-values.json` is the normalized CNA-Python differential
corpus for the completed pure foundation. It grew from 16 observations / 35
scalar assertions to 92 observations / 360 assertions. Groups cover
MathHelper, Vector2/3/4, Quaternion, Matrix, Color, Point, Rectangle, Plane,
Ray, BoundingBox, BoundingSphere, and BoundingFrustum.

The corpus includes ordinary and negative values, exact binary32 golden bits,
zero and signed zero, NaN and infinities, scalar-division evaluation order,
singular inversion, mirrored decomposition, degenerate LookAt/Plane/shadow,
XNA hashes and strings, transforms, tangent and near-parallel intersections,
frustum plane/corner extraction, and convex/GJK relations.

The expected values are labelled `PURE_XNA_DERIVED`: they come from the pinned
XNA reference metadata plus IL/algorithm analysis. They are not described as a
Windows runtime capture and Linux CNA output was not used as the XNA authority.
`tools/run_behavior_corpus.py` produces
`docs/generated/behavior-corpus-report.json` and currently reports:

```text
OBSERVATIONS=92
ASSERTIONS=360
FAILURES=0
```

Native lifecycle/graphics/input tests are separately labelled
`NATIVE_CNA_RUNTIME`. HEADLESS route execution is not physical-device evidence;
future `PLATFORM/HARDWARE` observations must come from qualified hardware.
