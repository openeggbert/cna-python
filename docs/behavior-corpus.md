# Behavior corpus

`behavior/xna40-pure-values.json` is the first normalized CNA-Python
differential corpus. Its 16 observations and 35 scalar assertions cover
binary32 math, vector operations, static value-copy behavior, matrix
translation/multiplication, quaternion identity, Color conversion, Rectangle
edge inclusion, Point equality, and signed zero.

The expected values are labelled `PURE_XNA_DERIVED`: they come from the pinned
XNA reference metadata plus IL/algorithm analysis. They are not described as a
Windows runtime capture and Linux CNA output was not used as the XNA authority.
`tools/run_behavior_corpus.py` produces
`docs/generated/behavior-corpus-report.json` and currently reports:

```text
OBSERVATIONS=16
ASSERTIONS=35
FAILURES=0
```

Native lifecycle/graphics/input tests are separately labelled
`NATIVE_CNA_RUNTIME`. HEADLESS route execution is not physical-device evidence;
future `PLATFORM/HARDWARE` observations must come from qualified hardware.
