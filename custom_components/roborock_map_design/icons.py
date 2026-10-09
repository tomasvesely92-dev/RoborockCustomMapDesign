"""Vacuum icons drawn on the map.

Icons are drawn on a supersampled layer and scaled down, so edges are
smooth (the parser's own drawing has no anti-aliasing). The vacuum's
heading (``Point.a``, degrees, counter-clockwise, 0 = image right) is
kept.
"""

from __future__ import annotations

from collections.abc import Callable
import math

from PIL import Image, ImageDraw
from vacuum_map_parser_base.config.color import Color
from vacuum_map_parser_base.map_data import ImageData, Point

SUPERSAMPLE = 4

# (draw, cx, cy, r, heading_rad, fill, outline) -> None, all in supersampled px
IconDrawer = Callable[[ImageDraw.ImageDraw, float, float, float, float, Color, Color], None]


def _heading_point(cx: float, cy: float, dist: float, a: float) -> tuple[float, float]:
    return cx + dist * math.cos(a), cy - dist * math.sin(a)


def _draw_m3_arrow(draw, cx, cy, r, a, fill, outline) -> None:
    """Filled circle with a navigation-style arrow pointing the heading."""
    ring = r * 0.14
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=outline)
    draw.ellipse(
        [cx - r + ring, cy - r + ring, cx + r - ring, cy + r - ring], fill=fill
    )
    tip = _heading_point(cx, cy, r * 0.55, a)
    left = _heading_point(cx, cy, r * 0.5, a + math.radians(140))
    notch = _heading_point(cx, cy, r * 0.18, a + math.pi)
    right = _heading_point(cx, cy, r * 0.5, a - math.radians(140))
    draw.polygon([tip, left, notch, right], fill=outline)


def _draw_m3_dot(draw, cx, cy, r, a, fill, outline) -> None:
    """Filled circle with a halo and a small dot toward the heading."""
    halo = (*fill[:3], 70)
    draw.ellipse([cx - r * 1.45, cy - r * 1.45, cx + r * 1.45, cy + r * 1.45], fill=halo)
    ring = r * 0.14
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=outline)
    draw.ellipse(
        [cx - r + ring, cy - r + ring, cx + r - ring, cy + r - ring], fill=fill
    )
    dx, dy = _heading_point(cx, cy, r * 0.5, a)
    d = r * 0.22
    draw.ellipse([dx - d, dy - d, dx + d, dy + d], fill=outline)


ICONS: dict[str, IconDrawer] = {
    "m3_arrow": _draw_m3_arrow,
    "m3_dot": _draw_m3_dot,
}


def draw_icon(
    image: ImageData,
    position: Point,
    radius: float,
    icon: str,
    fill: Color,
    outline: Color,
) -> None:
    """Draw ``icon`` at ``position`` onto the map image (in place)."""
    drawer = ICONS[icon]
    point = position.to_img(image.dimensions)
    heading = math.radians(position.a or 0)

    # Draw only a small supersampled tile around the vacuum, then paste it.
    pad = math.ceil(radius * 1.6) + 2
    size = 2 * pad
    tile = Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile, "RGBA")
    c = pad * SUPERSAMPLE
    drawer(draw, c, c, radius * SUPERSAMPLE, heading, _rgba(fill), _rgba(outline))
    tile = tile.resize((size, size), Image.Resampling.LANCZOS)

    layer = Image.new("RGBA", image.data.size, (0, 0, 0, 0))
    layer.paste(tile, (round(point.x) - pad, round(point.y) - pad))
    image.data = Image.alpha_composite(image.data.convert("RGBA"), layer)


def _rgba(color: Color) -> tuple[int, int, int, int]:
    return color if len(color) == 4 else (*color, 255)  # type: ignore[return-value]
