# Core value and geometry evidence

Foundation Milestone 2 completes the selected pure foundation without NumPy
or native ownership. The strict verifier reports local zero for MathHelper,
Vector2, Vector3, Vector4, Quaternion, Matrix, Color, Point, Rectangle,
GameTime, ContainmentType, PlaneIntersectionType, Plane, Ray, BoundingBox,
BoundingSphere, and BoundingFrustum.

All public Single state narrows to IEEE-754 binary32. Arithmetic helpers narrow
behaviorally significant intermediate operations and preserve XNA evaluation
order, signed zero, NaN/infinity, overflow, underflow, and reciprocal-before-
multiply scalar division. Golden observations include XNA spline ULPs,
quaternion products and transforms, singular inversion, infinity projection,
mirrored decomposition, degenerate LookAt/shadow/Plane, hash codes, and static
struct-copy behavior.

Geometry implements every selected containment/intersection combination.
BoundingFrustum extracts and normalizes six planes using XNA's distinct vector
and scalar division order, constructs eight corners, and uses convex support /
GJK interaction for boxes, spheres, and other frusta. Tangencies,
near-parallel rays, inside-origin rays, point boundaries, degenerate and
non-finite cases are covered by unit and exact-bit corpus evidence.

Evidence commands:

```text
python3 -m unittest tests.test_values tests.test_intersections -v
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
```

The corpus is `PURE_XNA_DERIVED`: pinned XNA metadata plus IL/algorithm and
neutral golden-snapshot analysis. It is not labelled as a Windows runtime
capture and does not use CNA output as XNA authority.
