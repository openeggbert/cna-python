"""Independent expectations for the engine's pure math.

Every function here computes what CNA should answer **without calling CNA**,
from the formula CNA's own source states rather than from its output. A getter
is never allowed to be its own oracle, so these are written against the
algorithm and then compared with the route.

An oracle that is wrong in the same way as the implementation proves nothing, so
these are gated too: :mod:`tests.test_engine_oracles` checks each one against a
worked case computed by hand in the test itself, and the mutation harness plants
defects here to prove that a wrong oracle is caught rather than agreed with.

Everything is plain Python and needs no native library.
"""

from __future__ import annotations

import math

from Microsoft.Xna.Framework import Matrix, Vector3


def normalized(value: Vector3) -> Vector3:
    length = math.sqrt(value.X * value.X + value.Y * value.Y + value.Z * value.Z)
    if length == 0.0:
        return Vector3(0.0, 0.0, 0.0)
    return Vector3(value.X / length, value.Y / length, value.Z / length)


def box_centre(minimum: Vector3, maximum: Vector3) -> Vector3:
    return Vector3((minimum.X + maximum.X) * 0.5,
                   (minimum.Y + maximum.Y) * 0.5,
                   (minimum.Z + maximum.Z) * 0.5)


def box_radius(minimum: Vector3, maximum: Vector3) -> float:
    """Half the diagonal of the box, which is what contains it in any rotation."""
    x, y, z = maximum.X - minimum.X, maximum.Y - minimum.Y, maximum.Z - minimum.Z
    return 0.5 * math.sqrt(x * x + y * y + z * z)


def shadow_light_view(direction: Vector3, minimum: Vector3, maximum: Vector3) -> Matrix:
    """The directional light's view transform for a scene.

    The algorithm, stated: stand back from the scene centre along the light's
    direction by twice the enclosing radius (at least two units, so a degenerate
    box still gives a defined view), and look at the centre. The up vector is
    ``+Y`` except for a light within about eight degrees of straight up or down,
    where ``+Z`` is used instead -- a straight-down sun is the common case that
    breaks the obvious choice.
    """
    unit = normalized(direction)
    centre = box_centre(minimum, maximum)
    distance = max(box_radius(minimum, maximum), 1.0) * 2.0
    eye = Vector3(centre.X - unit.X * distance,
                  centre.Y - unit.Y * distance,
                  centre.Z - unit.Z * distance)
    up = Vector3(0.0, 0.0, 1.0) if abs(unit.Y) > 0.99 else Vector3(0.0, 1.0, 0.0)
    return Matrix.CreateLookAt(eye, centre, up)


def cascade_split_distances(near_plane: float, far_plane: float, cascade_count: int,
                            split_lambda: float) -> list[float]:
    """Where the cascades end: a blend of a logarithmic and a uniform division.

    ``logarithmic_i = near * (far/near)**(i/n)`` and
    ``uniform_i = near + (far - near) * (i/n)``, blended by ``lambda``, with the
    last distance replaced by the far plane so no sliver is left unshadowed.
    """
    split_lambda = min(max(split_lambda, 0.0), 1.0)
    ratio = far_plane / near_plane
    span = far_plane - near_plane
    splits = []
    for index in range(1, cascade_count + 1):
        fraction = index / cascade_count
        logarithmic = near_plane * (ratio ** fraction)
        uniform = near_plane + span * fraction
        splits.append(split_lambda * logarithmic + (1.0 - split_lambda) * uniform)
    splits[-1] = far_plane
    return splits


#: The eight normalised-device corners of a frustum, with depth running 0..1.
#: That is the Direct3D convention, which is the one XNA's projection matrices
#: produce; taking the OpenGL -1..1 convention would put the near corners half
#: way to the camera.
NDC_CORNERS = (
    (-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (-1.0, 1.0, 0.0), (1.0, 1.0, 0.0),
    (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (-1.0, 1.0, 1.0), (1.0, 1.0, 1.0),
)


def transform_coordinate(point: tuple[float, float, float], matrix: Matrix) -> Vector3:
    """A point through a matrix, divided by its own w. Row-vector convention."""
    x, y, z = point
    values = tuple(matrix)
    result = [
        x * values[0] + y * values[4] + z * values[8] + values[12],
        x * values[1] + y * values[5] + z * values[9] + values[13],
        x * values[2] + y * values[6] + z * values[10] + values[14],
    ]
    w = x * values[3] + y * values[7] + z * values[11] + values[15]
    if w != 0.0:
        result = [value / w for value in result]
    return Vector3(*result)


def frustum_corners(view: Matrix, projection: Matrix) -> list[Vector3]:
    """The eight world-space corners of a camera frustum."""
    inverse = Matrix.Invert(Matrix.Multiply(view, projection))
    return [transform_coordinate(corner, inverse) for corner in NDC_CORNERS]


def bounding_sphere(corners) -> tuple[Vector3, float]:
    """The mean of eight points and the greatest distance from it.

    Not the smallest enclosing sphere: the mean is what CNA uses, and a cascade
    fitted to the mean is stable as the camera turns, which is what matters more
    than being minimal. A degenerate frustum floors the radius at 1e-3 so the
    projection stays defined.
    """
    centre = Vector3(sum(corner.X for corner in corners) / 8.0,
                     sum(corner.Y for corner in corners) / 8.0,
                     sum(corner.Z for corner in corners) / 8.0)
    radius = 0.0
    for corner in corners:
        dx, dy, dz = corner.X - centre.X, corner.Y - centre.Y, corner.Z - centre.Z
        radius = max(radius, math.sqrt(dx * dx + dy * dy + dz * dz))
    return centre, max(radius, 1e-3)


def snap_to_texel_grid(centre: Vector3, radius: float, cascade_size: int) -> Vector3:
    """Quantizes X and Y to the cascade's own texel size, leaving Z alone."""
    if cascade_size <= 0 or not radius > 0.0:
        return centre
    world_per_texel = 2.0 * radius / cascade_size
    return Vector3(math.floor(centre.X / world_per_texel) * world_per_texel,
                   math.floor(centre.Y / world_per_texel) * world_per_texel,
                   centre.Z)


def matrices_agree(left: Matrix, right: Matrix, tolerance: float = 1e-4) -> bool:
    """Whether two matrices agree within a tolerance, element by element."""
    return all(abs(a - b) <= tolerance for a, b in zip(tuple(left), tuple(right)))


def vectors_agree(left: Vector3, right: Vector3, tolerance: float = 1e-4) -> bool:
    return (abs(left.X - right.X) <= tolerance and abs(left.Y - right.Y) <= tolerance
            and abs(left.Z - right.Z) <= tolerance)
