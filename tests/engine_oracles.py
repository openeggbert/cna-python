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

import ctypes
import math

from Microsoft.Xna.Framework import Matrix, Vector3


def f32(value: float) -> float:
    """One value rounded to the width C computes it in.

    Most of the formulas here are precision-independent, and two of them are
    not: depth packing multiplies by 2**24, where a ``float`` has run out of
    fractional bits and a ``double`` has not. Modelling the arithmetic in
    doubles there would produce an oracle that disagrees with a correct
    implementation, which is worse than no oracle.
    """
    return float(ctypes.c_float(value).value)


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


# --- the scene helpers -------------------------------------------------------


def particle_hash(value: int) -> int:
    """CNA's integer hash, the one every particle draw is seeded from.

    Three xor-shift and multiply rounds over 32 bits. Written out because a
    random draw whose oracle came from the same routine it checks would agree
    with any hash at all.
    """
    mask = 0xFFFFFFFF
    value &= mask
    value ^= value >> 16
    value = (value * 0x7FEB352D) & mask
    value ^= value >> 15
    value = (value * 0x846CA68B) & mask
    value ^= value >> 16
    return value & mask


def particle_random(seed: int) -> float:
    """The draw in ``[0, 1)``: the low 24 bits of the hash over 2**24."""
    return (particle_hash(seed) & 0x00FFFFFF) / 16777216.0


def pack_depth(value: float) -> tuple[float, float, float, float]:
    """Splits a normalised depth across four channels.

    The clamp stops one texel short of one, because ``fract(1.0)`` is zero and
    an unclamped far-plane depth would read back as the nearest surface. Each
    channel then drops the part the previous one already holds.

    Computed in single precision throughout, because that is where the answer
    comes from: ``depth * 2**24`` exceeds a ``float``'s 24 bits of mantissa for
    most depths, so its fractional part -- the first channel -- is genuinely
    zero. In doubles it would not be, and the oracle would disagree with a
    correct implementation.
    """
    clamped = f32(min(max(f32(value), 0.0), 0.99999994))
    shifts = (16777216.0, 65536.0, 256.0, 1.0)
    channels = []
    for shift in shifts:
        scaled = f32(clamped * shift)
        channels.append(f32(scaled - math.floor(scaled)))
    return (f32(channels[0]),
            f32(channels[1] - f32(channels[0] / 256.0)),
            f32(channels[2] - f32(channels[1] / 256.0)),
            f32(channels[3] - f32(channels[2] / 256.0)))


def unpack_depth(red: float, green: float, blue: float, alpha: float) -> float:
    """Reassembles the depth from four channels."""
    return red / 16777216.0 + green / 65536.0 + blue / 256.0 + alpha


def has_velocity(alpha: int) -> bool:
    """A velocity texel is marked by an alpha below the midpoint."""
    return alpha < 128


def decode_velocity(red: int, green: int, blue: int, alpha: int) -> tuple[float, float]:
    """Two channels remapped from ``0..255`` onto ``-1..1``; zero when unmarked."""
    if not has_velocity(alpha):
        return 0.0, 0.0
    return (red / 255.0 - 0.5) * 2.0, (green / 255.0 - 0.5) * 2.0


def transparency_weight(view_depth: float, alpha: float, far_plane: float) -> float:
    """The weight an order-independent blend gives one fragment.

    Depth normalised and clamped, then a fourth-power falloff clamped into
    ``0.01 .. 3000``. The order of operations matters: the CPU twin exists to be
    compared against the GPU's, so a reassociated version would disagree in the
    last bits for a reason nobody could then locate.
    """
    z = min(max(view_depth / max(far_plane, 1e-4), 0.0), 1.0)
    return alpha * min(max(0.03 / (1e-5 + z ** 4.0), 1e-2), 3e3)


def sort_key(minimum: Vector3, maximum: Vector3, camera: Vector3) -> float:
    """The distance to the nearest point of a box, zero inside it."""
    def component(value: float, low: float, high: float) -> float:
        return min(max(value, low), high) - value

    x = component(camera.X, minimum.X, maximum.X)
    y = component(camera.Y, minimum.Y, maximum.Y)
    z = component(camera.Z, minimum.Z, maximum.Z)
    return math.sqrt(x * x + y * y + z * z)


def is_inside_decal_box(point: Vector3) -> bool:
    """A decal's box is the unit cube centred on the origin."""
    return (abs(point.X) <= 0.5 and abs(point.Y) <= 0.5 and abs(point.Z) <= 0.5)


def bloom_extract_channel(value: float, threshold: float) -> float:
    """What one channel contributes to bloom, with a soft knee.

    Not ``max(value - threshold, 0)``. The knee is half the threshold, the
    contribution ramps across twice the knee, it is squared to soften the ramp
    further, and the *original* value is scaled by it -- so a texel exactly at
    the threshold contributes a quarter of itself rather than nothing. A hard
    cutoff would make bloom pop on and off as a highlight crosses the threshold,
    which is the artefact the knee exists to remove.
    """
    knee = max(threshold * 0.5, 1e-4)
    contribution = min(max((value - threshold + knee) / (2.0 * knee), 0.0), 1.0)
    return value * contribution * contribution


# --- clustered lighting -------------------------------------------------------


def cluster_index(tiles_x: int, tiles_y: int, x: int, y: int, slice_: int) -> int:
    """The flat index of one cluster.

    x varies fastest, then y, then depth: the layout the GPU path recovers with
    ``cluster % tilesX``, ``(cluster / tilesX) % tilesY``, ``cluster / (tilesX *
    tilesY)``, which is the same statement read the other way round.
    """
    return (slice_ * tiles_y + y) * tiles_x + x


def slice_distance(near_plane: float, far_plane: float, slice_count: int,
                   slice_: int) -> float:
    """The view distance where a depth slice begins.

    Logarithmic spacing: ``near * (far / near) ** (slice / slice_count)``. The
    two ends are named rather than computed, because the exponential is 1 and
    the ratio exactly only in real arithmetic and the boundary has to be the
    plane itself.

    Computed at single precision throughout: the exponential of a float ratio is
    not the exponential of the same ratio in double, and the difference lands in
    the last bits of a number that decides which cluster a light is in.
    """
    if slice_ == 0:
        return f32(near_plane)
    if slice_ == slice_count:
        return f32(far_plane)
    ratio = f32(f32(far_plane) / f32(near_plane))
    exponent = f32(f32(slice_) / f32(slice_count))
    return f32(f32(near_plane) * f32(math.pow(ratio, exponent)))


def slice_for_view_distance(near_plane: float, far_plane: float, slice_count: int,
                            view_distance: float) -> int:
    """Which slice a point at that distance falls in.

    The inverse of :func:`slice_distance`, clamped at both ends so a light that
    pokes out of the frustum still lands in a slice rather than nowhere.
    """
    if view_distance <= near_plane:
        return 0
    if view_distance >= far_plane:
        return slice_count - 1
    ratio = f32(f32(math.log(f32(f32(view_distance) / f32(near_plane))))
                / f32(math.log(f32(f32(far_plane) / f32(near_plane)))))
    return max(0, min(slice_count - 1, int(math.floor(f32(ratio * f32(slice_count))))))


def invert_matrix4(matrix: Matrix) -> list[float]:
    """A 4x4 inverse by cofactor expansion, in row-major order.

    Written out rather than taken from :meth:`Matrix.Invert`, because the point
    of the cluster-bounds oracle is to unproject without using the same code
    CNA does. Kept in double precision: this is the one step where matching
    CNA's exact float rounding is neither possible nor wanted, so the bounds are
    compared with a tolerance instead.
    """
    m = list(matrix)
    inverse = [0.0] * 16
    inverse[0] = (m[5] * m[10] * m[15] - m[5] * m[11] * m[14] - m[9] * m[6] * m[15]
                  + m[9] * m[7] * m[14] + m[13] * m[6] * m[11] - m[13] * m[7] * m[10])
    inverse[4] = (-m[4] * m[10] * m[15] + m[4] * m[11] * m[14] + m[8] * m[6] * m[15]
                  - m[8] * m[7] * m[14] - m[12] * m[6] * m[11] + m[12] * m[7] * m[10])
    inverse[8] = (m[4] * m[9] * m[15] - m[4] * m[11] * m[13] - m[8] * m[5] * m[15]
                  + m[8] * m[7] * m[13] + m[12] * m[5] * m[11] - m[12] * m[7] * m[9])
    inverse[12] = (-m[4] * m[9] * m[14] + m[4] * m[10] * m[13] + m[8] * m[5] * m[14]
                   - m[8] * m[6] * m[13] - m[12] * m[5] * m[10] + m[12] * m[6] * m[9])
    inverse[1] = (-m[1] * m[10] * m[15] + m[1] * m[11] * m[14] + m[9] * m[2] * m[15]
                  - m[9] * m[3] * m[14] - m[13] * m[2] * m[11] + m[13] * m[3] * m[10])
    inverse[5] = (m[0] * m[10] * m[15] - m[0] * m[11] * m[14] - m[8] * m[2] * m[15]
                  + m[8] * m[3] * m[14] + m[12] * m[2] * m[11] - m[12] * m[3] * m[10])
    inverse[9] = (-m[0] * m[9] * m[15] + m[0] * m[11] * m[13] + m[8] * m[1] * m[15]
                  - m[8] * m[3] * m[13] - m[12] * m[1] * m[11] + m[12] * m[3] * m[9])
    inverse[13] = (m[0] * m[9] * m[14] - m[0] * m[10] * m[13] - m[8] * m[1] * m[14]
                   + m[8] * m[2] * m[13] + m[12] * m[1] * m[10] - m[12] * m[2] * m[9])
    inverse[2] = (m[1] * m[6] * m[15] - m[1] * m[7] * m[14] - m[5] * m[2] * m[15]
                  + m[5] * m[3] * m[14] + m[13] * m[2] * m[7] - m[13] * m[3] * m[6])
    inverse[6] = (-m[0] * m[6] * m[15] + m[0] * m[7] * m[14] + m[4] * m[2] * m[15]
                  - m[4] * m[3] * m[14] - m[12] * m[2] * m[7] + m[12] * m[3] * m[6])
    inverse[10] = (m[0] * m[5] * m[15] - m[0] * m[7] * m[13] - m[4] * m[1] * m[15]
                   + m[4] * m[3] * m[13] + m[12] * m[1] * m[7] - m[12] * m[3] * m[5])
    inverse[14] = (-m[0] * m[5] * m[14] + m[0] * m[6] * m[13] + m[4] * m[1] * m[14]
                   - m[4] * m[2] * m[13] - m[12] * m[1] * m[6] + m[12] * m[2] * m[5])
    inverse[3] = (-m[1] * m[6] * m[11] + m[1] * m[7] * m[10] + m[5] * m[2] * m[11]
                  - m[5] * m[3] * m[10] - m[9] * m[2] * m[7] + m[9] * m[3] * m[6])
    inverse[7] = (m[0] * m[6] * m[11] - m[0] * m[7] * m[10] - m[4] * m[2] * m[11]
                  + m[4] * m[3] * m[10] + m[8] * m[2] * m[7] - m[8] * m[3] * m[6])
    inverse[11] = (-m[0] * m[5] * m[11] + m[0] * m[7] * m[9] + m[4] * m[1] * m[11]
                   - m[4] * m[3] * m[9] - m[8] * m[1] * m[7] + m[8] * m[3] * m[5])
    inverse[15] = (m[0] * m[5] * m[10] - m[0] * m[6] * m[9] - m[4] * m[1] * m[10]
                   + m[4] * m[2] * m[9] + m[8] * m[1] * m[6] - m[8] * m[2] * m[5])
    determinant = (m[0] * inverse[0] + m[1] * inverse[4] + m[2] * inverse[8]
                   + m[3] * inverse[12])
    if determinant == 0.0:
        raise ValueError("the matrix is singular")
    return [value / determinant for value in inverse]


def _unproject(inverse: list[float], x: float, y: float, z: float) -> Vector3:
    values = [
        x * inverse[0] + y * inverse[4] + z * inverse[8] + inverse[12],
        x * inverse[1] + y * inverse[5] + z * inverse[9] + inverse[13],
        x * inverse[2] + y * inverse[6] + z * inverse[10] + inverse[14],
    ]
    w = x * inverse[3] + y * inverse[7] + z * inverse[11] + inverse[15]
    if abs(w) <= 1e-9:
        return Vector3(*values)
    return Vector3(*(value / w for value in values))


def _at_distance(at_near: Vector3, at_far: Vector3, distance: float) -> Vector3:
    """The point on a corner ray at one view distance.

    Written as an interpolation between the near and far unprojections rather
    than as a ray scaled by 1/z, because view-space z is linear along that
    segment for an orthographic projection as well as a perspective one, and the
    scaling form is right only for the second.
    """
    span = at_near.Z - at_far.Z
    if abs(span) <= 1e-9:
        return at_near
    t = (at_near.Z + distance) / span
    return Vector3(at_near.X + (at_far.X - at_near.X) * t,
                   at_near.Y + (at_far.Y - at_near.Y) * t, -distance)


def cluster_bounds(projection: Matrix, tiles_x: int, tiles_y: int, slice_count: int,
                   near_plane: float, far_plane: float, x: int, y: int,
                   slice_: int) -> tuple[Vector3, Vector3]:
    """The view-space box one cluster occupies, as ``(minimum, maximum)``.

    Four tile corners unprojected at both NDC depths, each brought to the
    slice's two distances, and the eight results bounded.
    """
    inverse = invert_matrix4(projection)
    us = (2.0 * x / tiles_x - 1.0, 2.0 * (x + 1) / tiles_x - 1.0)
    vs = (2.0 * y / tiles_y - 1.0, 2.0 * (y + 1) / tiles_y - 1.0)
    distances = (slice_distance(near_plane, far_plane, slice_count, slice_),
                 slice_distance(near_plane, far_plane, slice_count, slice_ + 1))
    points = []
    for u in us:
        for v in vs:
            at_near = _unproject(inverse, u, v, 0.0)
            at_far = _unproject(inverse, u, v, 1.0)
            points.extend(_at_distance(at_near, at_far, distance)
                          for distance in distances)
    return (Vector3(min(p.X for p in points), min(p.Y for p in points),
                    min(p.Z for p in points)),
            Vector3(max(p.X for p in points), max(p.Y for p in points),
                    max(p.Z for p in points)))


def point_light_bounds(position: Vector3, range_: float) -> tuple[Vector3, float]:
    """A point light reaches a sphere centred on itself."""
    return position, range_


def spot_light_bounds(position: Vector3, direction: Vector3, range_: float,
                      outer_angle: float) -> tuple[Vector3, float]:
    """The bounding sphere of a cone, in its two cases.

    A cone wider than 45 degrees is bounded by the sphere through its base rim,
    centred at the base. A narrower one is bounded by the sphere through the
    apex *and* the rim, whose centre sits further along the axis than the base
    does. Using the wide case everywhere would be correct but loose, and a torch
    would claim every cluster behind the person holding it.
    """
    axis = normalized(direction)
    if axis.X == 0.0 and axis.Y == 0.0 and axis.Z == 0.0:
        axis = Vector3(0.0, -1.0, 0.0)
    cosine = f32(math.cos(outer_angle))
    if outer_angle > 0.78539816339:
        radius = f32(range_ * f32(math.sin(outer_angle)))
        centre = Vector3(position.X + axis.X * range_ * cosine,
                         position.Y + axis.Y * range_ * cosine,
                         position.Z + axis.Z * range_ * cosine)
        return centre, radius
    radius = f32(range_ / (2.0 * max(cosine, 1e-4)))
    return (Vector3(position.X + axis.X * radius, position.Y + axis.Y * radius,
                    position.Z + axis.Z * radius), radius)


def squared_distance_to_box(minimum: Vector3, maximum: Vector3,
                            point: Vector3) -> float:
    """Zero inside the box, and the squared distance to its nearest point outside."""
    total = 0.0
    for low, high, value in ((minimum.X, maximum.X, point.X),
                             (minimum.Y, maximum.Y, point.Y),
                             (minimum.Z, maximum.Z, point.Z)):
        if value < low:
            total += (low - value) ** 2
        elif value > high:
            total += (value - high) ** 2
    return total


def assign_clusters(projection: Matrix, tiles_x: int, tiles_y: int, slice_count: int,
                    near_plane: float, far_plane: float, view: Matrix,
                    spheres) -> tuple[list[int], list[int]]:
    """Which lights land in which clusters, as ``(offsets, indices)``.

    A whole reimplementation of the sort, because the compressed-row output is
    the family's central claim and checking only its totals would let a
    transposed grid through. A light with a non-positive radius is skipped, one
    wholly behind the camera or wholly beyond the far plane never enters the
    loop, and the rest are tested against every cluster in their own slice range.
    """
    cluster_count = tiles_x * tiles_y * slice_count
    per_cluster: list[list[int]] = [[] for _ in range(cluster_count)]
    for light, sphere in enumerate(spheres):
        centre, radius = sphere
        if not radius > 0.0:
            continue
        view_centre = transform_coordinate((centre.X, centre.Y, centre.Z), view)
        radius_squared = radius * radius
        nearest = -view_centre.Z - radius
        furthest = -view_centre.Z + radius
        if furthest <= 0.0 or nearest >= far_plane:
            continue
        first = slice_for_view_distance(near_plane, far_plane, slice_count, nearest)
        last = slice_for_view_distance(near_plane, far_plane, slice_count, furthest)
        for slice_ in range(first, last + 1):
            for y in range(tiles_y):
                for x in range(tiles_x):
                    minimum, maximum = cluster_bounds(
                        projection, tiles_x, tiles_y, slice_count, near_plane,
                        far_plane, x, y, slice_)
                    if squared_distance_to_box(minimum, maximum,
                                               view_centre) > radius_squared:
                        continue
                    per_cluster[cluster_index(tiles_x, tiles_y, x, y, slice_)].append(light)
    offsets = [0]
    indices: list[int] = []
    for cluster in range(cluster_count):
        indices.extend(per_cluster[cluster])
        offsets.append(len(indices))
    return offsets, indices


def rec709_luminance(color: Vector3) -> float:
    """How much of a colour the eye sees.

    A green light and a blue one of the same numeric intensity do not carry the
    same weight in a picture, and a shadow budget should follow the picture.
    """
    return f32(0.2126 * color.X + 0.7152 * color.Y + 0.0722 * color.Z)


def windowed_falloff(distance: float, range_: float) -> float:
    """Inverse square, windowed so it reaches zero at the light's range.

    ``(1 - (d/r)**4)`` clamped, squared, over ``d**2``: the window takes it
    smoothly to nothing at the range rather than cutting it off, and the
    denominator is floored so a light at the origin is bright rather than
    infinite.
    """
    if distance >= range_:
        return 0.0
    ratio = f32(distance / max(range_, 1e-4))
    window = min(max(f32(1.0 - ratio * ratio * ratio * ratio), 0.0), 1.0)
    return f32(window * window / max(f32(distance * distance), 1e-4))


def shadow_policy_score(color: Vector3, intensity: float, range_: float,
                        position: Vector3, camera: Vector3) -> float:
    """What one shadow-casting light is worth, for ranking inside a budget.

    Luminance times intensity times the falloff at the camera's distance, with
    that distance floored at one unit: at the camera's own position the falloff
    diverges, and a light the camera is standing inside is as important as a
    light can be rather than infinitely more important than every other.
    """
    dx, dy, dz = (position.X - camera.X, position.Y - camera.Y, position.Z - camera.Z)
    distance = f32(math.sqrt(f32(dx * dx + dy * dy + dz * dz)))
    return f32(rec709_luminance(color) * intensity
               * windowed_falloff(max(distance, 1.0), range_))


def volume_attenuation(color: Vector3, attenuation_distance: float,
                       thickness: float) -> Vector3:
    """What survives ``thickness`` of a medium, as a closed form.

    CNA computes ``exp(-(-ln c / d) * t)``. That is ``c ** (t / d)`` exactly, so
    the power is the independent statement of the same physics rather than a
    transcription of the same three calls. The colour is clamped into
    ``1e-4 .. 1`` first, because a zero channel has no logarithm.
    """
    if not attenuation_distance > 0.0 or not thickness > 0.0:
        return Vector3(1.0, 1.0, 1.0)
    exponent = thickness / attenuation_distance
    return Vector3(*(min(max(channel, 1e-4), 1.0) ** exponent
                     for channel in (color.X, color.Y, color.Z)))


def lobe_scale_for(roughness: float) -> float:
    """The width of the specular lobe a roughness implies.

    The GGX alpha -- roughness squared -- floored so that a mirror still has a
    lobe with a width rather than a line.
    """
    clamped = min(max(roughness, 0.0), 1.0)
    return f32(max(f32(clamped * clamped), 0.02))


#: A disc of half-axes a and b encloses ``pi*a*b``; a rectangle of the same
#: half-axes encloses ``4*a*b``. Scaling both by ``sqrt(pi)/2`` makes the two
#: areas equal, so a disc delivers a disc's irradiance even though the outline
#: integrated is a rectangle.
DISC_AXIS_SCALE = math.sqrt(math.pi) / 2.0


def area_light_quad(shape: int, position: Vector3, right_axis: Vector3,
                    up_axis: Vector3) -> tuple[Vector3, ...]:
    """The four corners of a rectangle or disc light, counter-clockwise.

    A tube is not covered: its quad is billboarded toward the surface, so it is
    a different statement and is tested against its own geometric properties
    rather than against a closed form.
    """
    right, up = right_axis, up_axis
    if shape == 1:
        right = Vector3(*(value * DISC_AXIS_SCALE
                          for value in (right.X, right.Y, right.Z)))
        up = Vector3(*(value * DISC_AXIS_SCALE for value in (up.X, up.Y, up.Z)))
    return (Vector3(position.X - right.X - up.X, position.Y - right.Y - up.Y,
                    position.Z - right.Z - up.Z),
            Vector3(position.X + right.X - up.X, position.Y + right.Y - up.Y,
                    position.Z + right.Z - up.Z),
            Vector3(position.X + right.X + up.X, position.Y + right.Y + up.Y,
                    position.Z + right.Z + up.Z),
            Vector3(position.X - right.X + up.X, position.Y - right.Y + up.Y,
                    position.Z - right.Z + up.Z))


# --- light probes -------------------------------------------------------------

#: Ramamoorthi and Hanrahan's constants: the cosine lobe's own spherical-harmonic
#: coefficients, folded together with the basis normalisation. Their result is
#: that irradiance needs only nine terms, because convolving anything with a
#: cosine lobe leaves almost nothing above second order.
SH_C1, SH_C2, SH_C3, SH_C4, SH_C5 = 0.429043, 0.511664, 0.743125, 0.886227, 0.247708


def sh_irradiance(coefficients, normal: Vector3) -> Vector3:
    """Irradiance arriving at a surface facing ``normal``, from nine coefficients.

    The second-order evaluation written out per channel. Floored at zero per
    channel, because a projection can go slightly negative where the environment
    is dark and the fit overshoots, and negative irradiance is light being
    *removed* from a surface.
    """
    unit = normalized(normal)
    if unit.X == 0.0 and unit.Y == 0.0 and unit.Z == 0.0:
        unit = Vector3(0.0, 1.0, 0.0)
    channels = []
    for axis in ("X", "Y", "Z"):
        at = [getattr(value, axis) for value in coefficients]
        value = (SH_C4 * at[0]
                 + 2.0 * SH_C2 * (at[1] * unit.Y + at[2] * unit.Z + at[3] * unit.X)
                 + 2.0 * SH_C1 * (at[4] * unit.X * unit.Y + at[5] * unit.Y * unit.Z
                                  + at[7] * unit.X * unit.Z)
                 + SH_C3 * at[6] * unit.Z * unit.Z - SH_C5 * at[6]
                 + SH_C1 * at[8] * (unit.X * unit.X - unit.Y * unit.Y))
        channels.append(max(value, 0.0))
    return Vector3(*channels)


def probe_visibility_weight(means, mean_squares, direction: Vector3,
                            distance: float) -> float:
    """How much a probe is trusted to be lighting a point that far away.

    Chebyshev's inequality, exactly as a variance shadow map uses it: a flat wall
    has almost no variance and cuts off sharply, a cluttered direction has a lot
    and fades. The six axis moments are blended by the squared component of the
    direction along each axis rather than snapped to the nearest one -- snapping
    makes the weight jump as a surface turns, and a discontinuity in an ambient
    term is more visible than the leak it was fixing.

    A probe with nothing recorded is trusted rather than discarded, and so is a
    point closer than the mean: there is nothing between it and the probe.
    """
    if not any(mean > 0.0 for mean in means):
        return 1.0
    if not distance > 0.0:
        return 1.0
    unit = normalized(direction)
    if unit.X == 0.0 and unit.Y == 0.0 and unit.Z == 0.0:
        unit = Vector3(0.0, 1.0, 0.0)
    components = (max(unit.X, 0.0), max(-unit.X, 0.0), max(unit.Y, 0.0),
                  max(-unit.Y, 0.0), max(unit.Z, 0.0), max(-unit.Z, 0.0))
    total = mean = mean_squared = 0.0
    for index, component in enumerate(components):
        if means[index] <= 0.0:
            continue
        weight = component * component
        if weight <= 0.0:
            continue
        total += weight
        mean += means[index] * weight
        mean_squared += mean_squares[index] * weight
    if not total > 0.0:
        return 1.0
    mean /= total
    mean_squared /= total
    if distance <= mean:
        return 1.0
    variance = max(mean_squared - mean * mean, 0.0)
    gap = distance - mean
    return min(max(variance / (variance + gap * gap), 0.0), 1.0)


def probe_volume_index(count_x: int, count_y: int, x: int, y: int, z: int) -> int:
    """Where one probe sits in the volume's flat array. X fastest, then Y, then Z."""
    return (z * count_y + y) * count_x + x


def probe_volume_position(minimum: Vector3, maximum: Vector3, counts, index) -> Vector3:
    """The world position the grid gives one probe.

    Evenly spaced from the box's minimum to its maximum *inclusive*, so a grid
    of one probe on an axis sits at that axis's minimum rather than at its
    centre -- there is no interval to be in the middle of.
    """
    def along(step: int, count: int, low: float, high: float) -> float:
        if count <= 1:
            return low
        return low + (high - low) * step / (count - 1)

    return Vector3(along(index[0], counts[0], minimum.X, maximum.X),
                   along(index[1], counts[1], minimum.Y, maximum.Y),
                   along(index[2], counts[2], minimum.Z, maximum.Z))


def hammersley(index: int, count: int) -> tuple[float, float]:
    """The i-th point of the Hammersley sequence over ``count`` points.

    The first coordinate walks the interval at the centre of each cell; the
    second is the van der Corput radical inverse in base two -- the bits of the
    index reflected about the binary point. Written here as an actual bit
    reversal of the low 32 bits rather than as the same five-line shift-and-mask
    idiom, so a wrong mask in either place cannot agree with the other.
    """
    first = (index + 0.5) / count if count > 0 else 0.0
    bits = index & 0xFFFFFFFF
    reversed_bits = int(f"{bits:032b}"[::-1], 2)
    return f32(first), f32(reversed_bits * 2.3283064365386963e-10)


def build_basis(normal: Vector3) -> tuple[Vector3, Vector3]:
    """A tangent and bitangent for a normal, the way CNA chooses them."""
    up = (Vector3(0.0, 0.0, 1.0) if abs(normal.Z) < 0.999
          else Vector3(1.0, 0.0, 0.0))
    tangent = normalized(_cross(up, normal))
    return tangent, _cross(normal, tangent)


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return Vector3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X)


def importance_sample_ggx(x: float, y: float, normal: Vector3,
                          roughness: float) -> Vector3:
    """A half-vector drawn from the GGX distribution around ``normal``.

    Every step is rounded to single precision, because the mapping is
    ill-conditioned where the distribution is narrow: at roughness 0.05 the
    denominator ``1 + (alpha**2 - 1) * y`` is a difference of numbers close to
    one, and a double-precision oracle disagrees with a correct single-precision
    implementation in the fourth decimal for that reason alone.
    """
    alpha = f32(max(f32(roughness * roughness), 1e-4))
    phi = f32(2.0 * math.pi * x)
    cos_theta = f32(math.sqrt(f32(f32(1.0 - y)
                                  / f32(1.0 + f32(f32(alpha * alpha) - 1.0) * y))))
    sin_theta = f32(math.sqrt(max(0.0, f32(1.0 - f32(cos_theta * cos_theta)))))
    local = (f32(math.cos(phi) * sin_theta), f32(math.sin(phi) * sin_theta), cos_theta)
    tangent, bitangent = build_basis(normal)
    return normalized(Vector3(
        tangent.X * local[0] + bitangent.X * local[1] + normal.X * local[2],
        tangent.Y * local[0] + bitangent.Y * local[1] + normal.Y * local[2],
        tangent.Z * local[0] + bitangent.Z * local[1] + normal.Z * local[2]))


def mip_for_roughness(roughness: float, mip_count: int) -> float:
    """Which mip level of a prefiltered specular cube a roughness reads from."""
    if mip_count <= 1:
        return 0.0
    return min(max(roughness, 0.0), 1.0) * (mip_count - 1)


def roughness_for_mip(mip: float, mip_count: int) -> float:
    """The roughness one mip level was filtered for -- the inverse of the above."""
    if mip_count <= 1:
        return 0.0
    return min(max(mip / (mip_count - 1), 0.0), 1.0)


def cube_face_direction(face: int, u: float, v: float) -> Vector3:
    """The world direction a cube face's texel looks along.

    ``v`` runs *down* the face, which is the cube-map convention and the
    opposite of what a texture coordinate usually means.
    """
    a = u * 2.0 - 1.0
    b = 1.0 - v * 2.0
    direction = {
        0: Vector3(1.0, b, -a),
        1: Vector3(-1.0, b, a),
        2: Vector3(a, 1.0, -b),
        3: Vector3(a, -1.0, b),
        4: Vector3(a, b, 1.0),
    }.get(face, Vector3(-a, b, -1.0))
    return normalized(direction)


def direction_to_equirectangular(direction: Vector3) -> tuple[float, float]:
    """Where a direction lands in a panorama, as texture coordinates.

    ``atan2(x, -z)`` puts -Z at the centre of the image, which is where a
    panorama's front is and where a viewer looking straight ahead expects to be.
    """
    unit = normalized(direction)
    if unit.X == 0.0 and unit.Y == 0.0 and unit.Z == 0.0:
        unit = direction
    longitude = math.atan2(unit.X, -unit.Z)
    latitude = math.asin(min(max(unit.Y, -1.0), 1.0))
    return longitude / (2.0 * math.pi) + 0.5, 0.5 - latitude / math.pi


#: The forward and up axis each cube face of a probe capture looks along.
PROBE_FACE_AXES = (
    (Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0)),
    (Vector3(-1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0)),
    (Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)),
    (Vector3(0.0, -1.0, 0.0), Vector3(0.0, 0.0, 1.0)),
    (Vector3(0.0, 0.0, 1.0), Vector3(0.0, 1.0, 0.0)),
    (Vector3(0.0, 0.0, -1.0), Vector3(0.0, 1.0, 0.0)),
)


def probe_face_view(face: int, position: Vector3) -> Matrix:
    """The view matrix a probe capture uses for one cube face."""
    forward, up = PROBE_FACE_AXES[face]
    target = Vector3(position.X + forward.X, position.Y + forward.Y,
                     position.Z + forward.Z)
    return Matrix.CreateLookAt(position, target, up)


# --- culling, level of detail and instancing -----------------------------------


def frustum_planes(view_projection: Matrix):
    """The six inward-facing planes of a view-projection, as ``(a, b, c, d)``.

    Extracted by adding and subtracting rows of the matrix, which is where the
    planes come from: a clip-space coordinate is inside when ``-w <= x <= w``,
    and each of those six inequalities is one row combination. Normalised so the
    signed distance a plane reports is a real distance rather than a scaled one.

    Row-vector convention, matching XNA: near is the third row, far is the
    fourth minus the third, and left/right/bottom/top are the fourth plus or
    minus the first and second.
    """
    m = list(view_projection)

    def row(index: int):
        return m[index], m[index + 4], m[index + 8], m[index + 12]

    x, y, z, w = row(0), row(1), row(2), row(3)
    raw = [
        z,                                       # near
        tuple(a - b for a, b in zip(w, z)),      # far
        tuple(a + b for a, b in zip(w, x)),      # left
        tuple(a - b for a, b in zip(w, x)),      # right
        tuple(a + b for a, b in zip(w, y)),      # bottom
        tuple(a - b for a, b in zip(w, y)),      # top
    ]
    planes = []
    for a, b, c, d in raw:
        length = math.sqrt(a * a + b * b + c * c)
        if length == 0.0:
            planes.append((a, b, c, d))
        else:
            planes.append((a / length, b / length, c / length, d / length))
    return planes


def box_is_visible(planes, minimum: Vector3, maximum: Vector3) -> bool:
    """Whether an axis-aligned box is on the inside of every plane.

    The positive-vertex test: for each plane, the corner furthest along its
    normal is the last one to leave, so if that corner is outside the box is
    entirely outside. Conservative at the corners of the frustum, which is what
    every renderer does and what CNA does.
    """
    for a, b, c, d in planes:
        x = maximum.X if a >= 0.0 else minimum.X
        y = maximum.Y if b >= 0.0 else minimum.Y
        z = maximum.Z if c >= 0.0 else minimum.Z
        if a * x + b * y + c * z + d < 0.0:
            return False
    return True


def sphere_is_visible(planes, centre: Vector3, radius: float) -> bool:
    """Whether a sphere is on the inside of every plane, to within its radius."""
    for a, b, c, d in planes:
        if a * centre.X + b * centre.Y + c * centre.Z + d < -radius:
            return False
    return True


def lod_projected_radius_pixels(radius: float, vertical_fov: float,
                                viewport_height: float, distance: float) -> float:
    """How many pixels an object of that radius covers at that distance.

    The view's half-extent at the distance is ``2 * tan(fov / 2) * distance``,
    and the radius is that fraction of the viewport. At or behind the eye the
    projection is meaningless, and the honest answer is "as large as it gets",
    which selects the finest level rather than none.
    """
    if distance <= 0.0:
        return float(ctypes.c_float(3.4028234663852886e38).value)
    return f32(radius * viewport_height / f32(2.0 * math.tan(vertical_fov * 0.5)
                                              * distance))


def lod_select_by_distance(thresholds, distance: float) -> int:
    """The first level whose threshold the distance has not yet passed.

    Upper bound, not lower: a distance exactly at a level's threshold has left
    that level, so the boundary belongs to the next one. ``-1`` when the
    distance is past every threshold and no level covers it.
    """
    for index, threshold in enumerate(thresholds):
        if distance < threshold:
            return index
    return -1


def lod_select_by_screen_space(thresholds, pixels: float) -> int:
    """The first level whose pixel threshold the projected size still clears.

    The comparison turns around because projected size falls as distance rises,
    while the list order does not: index zero is the finest level in both modes,
    which is what lets hysteresis and the returned index be mode-independent.
    """
    for index, threshold in enumerate(thresholds):
        if pixels >= threshold:
            return index
    return -1


def lod_apply_hysteresis(thresholds, candidate: int, last: int, value: float,
                         margin: float) -> int:
    """Holds the previous level when the new one is only just better.

    Only the boundary between the remembered level and its immediate neighbour
    is sticky, and only inside the margin: a value that has moved several levels
    is a real change rather than a wobble, and holding it back would be worse
    than the flicker this prevents.
    """
    if margin <= 0.0 or last < 0 or candidate == last:
        return candidate
    if last >= len(thresholds):
        return candidate
    step = 1 if candidate > last else -1
    if candidate != last + step:
        return candidate
    boundary_index = last if step > 0 else candidate
    if boundary_index >= len(thresholds):
        return candidate
    return last if abs(value - thresholds[boundary_index]) < margin else candidate
