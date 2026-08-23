#!/usr/bin/env python3
"""Execute the normalized pure XNA-derived behavior corpus."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from Microsoft.Xna.Framework import (  # noqa: E402
    Color, MathHelper, Matrix, Point, Quaternion, Rectangle, Vector2, Vector3,
)
from Microsoft.Xna.Framework._numeric import f32  # noqa: E402


def vector2(value): return Vector2(*value)
def vector3(value): return Vector3(*value)


def observe(operation: str, args: list[object]) -> object:
    if operation == "MathHelper.Clamp": return MathHelper.Clamp(*args)
    if operation == "MathHelper.Lerp": return MathHelper.Lerp(*args)
    if operation == "Vector2.Add": return list(Vector2.Add(vector2(args[0]), vector2(args[1])))
    if operation == "Vector2.Dot": return Vector2.Dot(vector2(args[0]), vector2(args[1]))
    if operation == "Vector2.Normalize": return list(Vector2.Normalize(vector2(args[0])))
    if operation == "Vector2.ZeroFresh": return Vector2.Zero is not Vector2.Zero
    if operation == "Vector3.Cross": return list(Vector3.Cross(vector3(args[0]), vector3(args[1])))
    if operation == "Quaternion.AxisAngleZero": return list(Quaternion.CreateFromAxisAngle(Vector3.UnitY, 0.0))
    if operation == "Matrix.Translation":
        value = Matrix.CreateTranslation(*args)
        return [value.M41, value.M42, value.M43, value.M44]
    if operation == "Matrix.MultiplyTranslations":
        value = Matrix.CreateTranslation(1, 2, 3) * Matrix.CreateTranslation(4, 5, 6)
        return [value.M41, value.M42, value.M43, value.M44]
    if operation == "Color.Bytes": return list(Color(*args))
    if operation == "Color.Normalized": return list(Color(*args))
    if operation == "Rectangle.Contains": return Rectangle(*args[:4]).Contains(Point(*args[4:]))
    if operation == "Point.Equal": return Point(*args[:2]) == Point(*args[2:])
    if operation == "Float32.NegativeZero": return math.copysign(1.0, f32(-0.0)) < 0.0
    raise ValueError(f"unknown corpus operation {operation}")


def scalar_assertions(value: object) -> int:
    if isinstance(value, list):
        return sum(scalar_assertions(item) for item in value)
    return 1


def equal(actual: object, expected: object) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-7)
    return actual == expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default=str(ROOT / "behavior/xna40-pure-values.json"))
    parser.add_argument("--output")
    args = parser.parse_args()
    corpus = json.loads(Path(args.corpus).read_text())
    results, failures, assertions = [], 0, 0
    for item in corpus["observations"]:
        actual = observe(item["operation"], item["args"])
        passed = equal(actual, item["expected"])
        assertions += scalar_assertions(item["expected"])
        failures += not passed
        results.append({"id": item["id"], "passed": passed,
                        "expected": item["expected"], "actual": actual})
    report = {
        "schemaVersion": 1,
        "profile": corpus["profile"],
        "provenance": corpus["provenance"],
        "category": corpus["category"],
        "summary": {"OBSERVATIONS": len(results), "ASSERTIONS": assertions, "FAILURES": failures},
        "results": results,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    print(f"PROVENANCE={report['provenance']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
