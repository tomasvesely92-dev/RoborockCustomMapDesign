"""Re-render Roborock maps with a custom style.

This module has no Home Assistant imports so it can be tested on its own.
It re-parses the raw map bytes that the core Roborock integration keeps
(``MapContent.raw_api_response``) with our own palette. The returned map
data (rooms, zones, calibration) comes from the same parse as the image,
so image and calibration always match.
"""

from __future__ import annotations

from dataclasses import dataclass
import io

from vacuum_map_parser_base.config.color import Color, ColorsPalette, SupportedColor
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Size, Sizes
from vacuum_map_parser_base.map_data import MapData
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

from .icons import ICONS, draw_icon
from .palettes import PALETTES, Palette
from .room_colors import assign_tones, find_neighbors, probe_room_colors


class RenderError(Exception):
    """Raised when the custom render fails for any reason."""


@dataclass
class RenderResult:
    """A rendered map image and the map data parsed together with it."""

    image: bytes
    map_data: MapData


def _sizes(palette: Palette, map_scale: int) -> Sizes:
    base = {k: v for k, v in Sizes.SIZES.items() if k != Size.MOP_PATH_WIDTH}
    base.update({k: v for k, v in palette.sizes.items() if k != Size.MOP_PATH_WIDTH})
    return Sizes({k: v * map_scale for k, v in base.items()})


_PROBE = Palette(colors={color: (0, 0, 0, 0) for color in SupportedColor})


def _contrasting_room_colors(palette: Palette, raw: bytes) -> dict[str, Color]:
    """Neighboring rooms get clearly different tones; pinned colors win.

    Two cheap probe parses at scale 1: one to learn the room ids, one with
    colors that encode them, to see which rooms touch. Maps change rarely.
    """
    rooms = _make_parser(_PROBE, {}, [], 1).parse(raw).rooms or {}
    room_ids = list(rooms)
    probe = _make_parser(_PROBE, probe_room_colors(room_ids), [], 1).parse(raw)
    neighbors = find_neighbors(probe.image.data, room_ids)
    colors = assign_tones(list(palette.room_tones), neighbors)
    colors.update(palette.room_colors)
    return colors


def _make_parser(
    palette: Palette,
    room_colors: dict[str, Color],
    drawables: list[Drawable],
    map_scale: int,
) -> RoborockMapDataParser:
    parser = RoborockMapDataParser(
        ColorsPalette(dict(palette.colors), room_colors),
        _sizes(palette, map_scale),
        drawables,
        ImageConfig(scale=map_scale),
        [],
    )
    if palette.vacuum_icon in ICONS:
        generator = parser._image_generator  # noqa: SLF001
        icon = palette.vacuum_icon
        colors = ColorsPalette(dict(palette.colors), room_colors)
        radius = generator._sizes.get_size(Size.VACUUM_RADIUS)  # noqa: SLF001

        def _draw_vacuum_position(map_data: MapData) -> None:
            if map_data.vacuum_position is None or map_data.image is None:
                return
            draw_icon(
                map_data.image,
                map_data.vacuum_position,
                radius,
                icon,
                colors.get_color(SupportedColor.ROBO),
                colors.get_color(SupportedColor.ROBO_OUTLINE),
            )

        generator._draw_vacuum_position = _draw_vacuum_position  # noqa: SLF001
    return parser


def render_map(
    raw: bytes,
    palette_name: str,
    drawables: list[Drawable],
    map_scale: int,
) -> RenderResult:
    """Parse raw map bytes and render them with the named palette.

    Blocking: call it from an executor thread.
    """
    if not raw:
        raise RenderError("No raw map data available")
    palette = PALETTES.get(palette_name)
    if palette is None:
        raise RenderError(f"Unknown palette: {palette_name}")

    try:
        room_colors = dict(palette.room_colors)
        if palette.room_tones:
            room_colors = _contrasting_room_colors(palette, raw)
        map_data = _make_parser(palette, room_colors, drawables, map_scale).parse(raw)
    except Exception as err:  # noqa: BLE001 - any parser failure means fallback
        raise RenderError(f"Failed to parse map data: {err}") from err

    if map_data is None or map_data.image is None:
        raise RenderError("Parser returned no image")

    out = io.BytesIO()
    map_data.image.data.save(out, format="PNG")
    return RenderResult(image=out.getvalue(), map_data=map_data)
