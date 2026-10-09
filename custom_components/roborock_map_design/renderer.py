"""Re-render Roborock maps with a custom color palette.

This module has no Home Assistant imports so it can be tested on its own.
It re-parses the raw map bytes that the core Roborock integration keeps
(``MapContent.raw_api_response``) with our own palette. The returned map
data (rooms, zones, calibration) comes from the same parse as the image,
so image and calibration always match.
"""

from __future__ import annotations

from dataclasses import dataclass
import io

from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Size, Sizes
from vacuum_map_parser_base.map_data import MapData
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

from .palettes import PALETTES


class RenderError(Exception):
    """Raised when the custom render fails for any reason."""


@dataclass
class RenderResult:
    """A rendered map image and the map data parsed together with it."""

    image: bytes
    map_data: MapData


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

    parser = RoborockMapDataParser(
        ColorsPalette(dict(palette.colors), dict(palette.room_colors)),
        Sizes(
            {
                k: v * map_scale
                for k, v in Sizes.SIZES.items()
                if k != Size.MOP_PATH_WIDTH
            }
        ),
        drawables,
        ImageConfig(scale=map_scale),
        [],
    )
    try:
        map_data = parser.parse(raw)
    except Exception as err:  # noqa: BLE001 - any parser failure means fallback
        raise RenderError(f"Failed to parse map data: {err}") from err

    if map_data is None or map_data.image is None:
        raise RenderError("Parser returned no image")

    out = io.BytesIO()
    map_data.image.data.save(out, format="PNG")
    return RenderResult(image=out.getvalue(), map_data=map_data)
