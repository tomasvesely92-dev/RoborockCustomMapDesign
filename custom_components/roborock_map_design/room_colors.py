"""Give neighboring rooms clearly different colors.

From a probe render we find which rooms touch (walls between rooms are a
few pixels thick, so rooms closer than ``GAP`` px count as neighbors).
Then each room gets the tone that differs most, in perceived color and
lightness, from the tones its neighbors already have.
"""

from __future__ import annotations

from PIL import Image, ImageChops
from vacuum_map_parser_base.config.color import Color

# Marks room pixels in the probe image: R = room id, G/B = this marker.
MARK_G, MARK_B = 7, 13
GAP = 3
# Neighbor contrast that counts as "clearly different" (weighted Lab).
MIN_CONTRAST = 45


def probe_room_colors(room_ids: list[int]) -> dict[str, Color]:
    """Colors that encode the room id, for the probe render."""
    return {str(i): (i, MARK_G, MARK_B) for i in room_ids if 0 < i < 256}


def find_neighbors(probe: Image.Image, room_ids: list[int]) -> dict[int, set[int]]:
    """Room id -> ids of rooms within GAP pixels of it (pure PIL, no numpy)."""
    neighbors: dict[int, set[int]] = {i: set() for i in room_ids}
    r, g, b, a = probe.convert("RGBA").split()
    mask = ImageChops.logical_and(
        ImageChops.logical_and(
            g.point(lambda v: 255 if v == MARK_G else 0, "1"),
            b.point(lambda v: 255 if v == MARK_B else 0, "1"),
        ),
        a.point(lambda v: 255 if v == 255 else 0, "1"),
    )
    ids = Image.composite(r, Image.new("L", r.size, 0), mask)
    width, height = ids.size
    data = ids.tobytes()
    rows = [data[y * width:(y + 1) * width] for y in range(height)]
    pairs: set[tuple[int, int]] = set()
    for d in range(1, GAP + 1):
        for row in rows:  # horizontal
            pairs.update(zip(row[:-d], row[d:]))
        for y in range(height - d):  # vertical
            pairs.update(zip(rows[y], rows[y + d]))
    for x, y in pairs:
        if x and y and x != y and x in neighbors and y in neighbors:
            neighbors[x].add(y)
            neighbors[y].add(x)
    return neighbors


def _lab(color: Color) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in color[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _distance(c1: Color, c2: Color) -> float:
    l1, a1, b1 = _lab(c1)
    l2, a2, b2 = _lab(c2)
    # Weight lightness up: it is what separates colors on small screens
    # and for people with red-green color vision deficiency.
    return ((2 * (l1 - l2)) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2) ** 0.5


def assign_tones(
    tones: list[Color], neighbors: dict[int, set[int]]
) -> dict[str, Color]:
    """Greedy coloring, most-connected rooms first.

    Prefer a tone that is clearly different from every neighbor, then one
    no other room uses yet, then the highest contrast.
    """
    assigned: dict[int, Color] = {}
    used: dict[Color, int] = {}
    order = sorted(neighbors, key=lambda i: (-len(neighbors[i]), i))
    for room in order:
        taken = [assigned[n] for n in neighbors[room] if n in assigned]

        def score(tone: Color) -> tuple[bool, int, float, int]:
            contrast = min((_distance(tone, t) for t in taken), default=1000.0)
            return (
                contrast >= MIN_CONTRAST,
                -used.get(tone, 0),
                contrast,
                -tones.index(tone),
            )

        best = max(tones, key=score)
        assigned[room] = best
        used[best] = used.get(best, 0) + 1
    return {str(room): color for room, color in assigned.items()}
