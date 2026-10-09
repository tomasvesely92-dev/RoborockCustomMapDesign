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


def _draw_radar(draw, cx, cy, r, a, fill, outline) -> None:
    """Sonar scope: rings, crosshair and a sweep pointing the heading."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=outline)
    w = max(1, round(r * 0.08))
    for k in (0.92, 0.62, 0.32):
        rr = r * k
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=fill, width=w)
    draw.line([cx - r * 0.92, cy, cx + r * 0.92, cy], fill=(*fill[:3], 110), width=w)
    draw.line([cx, cy - r * 0.92, cx, cy + r * 0.92], fill=(*fill[:3], 110), width=w)
    deg = math.degrees(a)
    # PIL angles are clockwise from +x; heading is counter-clockwise.
    draw.pieslice(
        [cx - r * 0.92, cy - r * 0.92, cx + r * 0.92, cy + r * 0.92],
        -deg - 35, -deg + 35, fill=(*fill[:3], 120),
    )
    bx, by = _heading_point(cx, cy, r * 0.62, a)
    d = r * 0.13
    draw.ellipse([bx - d, by - d, bx + d, by + d], fill=fill)


def _draw_saucer(draw, cx, cy, r, a, fill, outline) -> None:
    """Flying saucer from above: hull, dome and a ring of lights."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=outline)
    hull = r * 0.86
    draw.ellipse([cx - hull, cy - hull, cx + hull, cy + hull], fill=fill)
    rim = r * 0.62
    draw.ellipse([cx - rim, cy - rim, cx + rim, cy + rim], fill=outline)
    dome = r * 0.48
    draw.ellipse([cx - dome, cy - dome, cx + dome, cy + dome], fill=(*fill[:3], 200))
    hl = r * 0.16
    hx, hy = cx - dome * 0.35, cy - dome * 0.35
    draw.ellipse([hx - hl, hy - hl, hx + hl, hy + hl], fill=(255, 255, 255, 170))
    lamp = r * 0.07
    for k in range(8):
        lx, ly = _heading_point(cx, cy, r * 0.74, a + k * math.pi / 4)
        color = (255, 214, 120, 255) if k == 0 else outline
        size = lamp * (1.8 if k == 0 else 1)
        draw.ellipse([lx - size, ly - size, lx + size, ly + size], fill=color)


def _draw_rocket(draw, cx, cy, r, a, fill, outline) -> None:
    """Small rocket flying toward the heading."""
    def side(along, across):
        x = cx + along * math.cos(a) + across * math.sin(a)
        y = cy - along * math.sin(a) + across * math.cos(a)
        return x, y

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*outline[:3], 150))
    flame = [side(-r * 0.55, -r * 0.16), side(-r * 0.95, 0), side(-r * 0.55, r * 0.16)]
    draw.polygon(flame, fill=(255, 168, 80, 255))
    fins_l = [side(-r * 0.2, -r * 0.2), side(-r * 0.62, -r * 0.48), side(-r * 0.58, -r * 0.18)]
    fins_r = [side(-r * 0.2, r * 0.2), side(-r * 0.62, r * 0.48), side(-r * 0.58, r * 0.18)]
    draw.polygon(fins_l, fill=outline)
    draw.polygon(fins_r, fill=outline)
    body = [
        side(r * 0.8, 0), side(r * 0.42, -r * 0.24), side(-r * 0.58, -r * 0.2),
        side(-r * 0.58, r * 0.2), side(r * 0.42, r * 0.24),
    ]
    draw.polygon(body, fill=fill, outline=outline)
    wx, wy = side(r * 0.2, 0)
    w = r * 0.13
    draw.ellipse([wx - w, wy - w, wx + w, wy + w], fill=outline)


ICONS: dict[str, IconDrawer] = {
    "m3_arrow": _draw_m3_arrow,
    "m3_dot": _draw_m3_dot,
    "radar": _draw_radar,
    "saucer": _draw_saucer,
    "rocket": _draw_rocket,
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
