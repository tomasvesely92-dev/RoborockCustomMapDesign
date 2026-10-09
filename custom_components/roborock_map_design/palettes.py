"""Color palettes for the map.

Colors are (R, G, B) or (R, G, B, A). Any color not listed keeps the
parser's default. Room colors are keyed by Roborock segment id as a
string; ids we don't list fall back to the parser's default room colors.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vacuum_map_parser_base.config.color import Color, SupportedColor
from vacuum_map_parser_base.config.size import Size

TRANSPARENT: Color = (0, 0, 0, 0)


@dataclass(frozen=True)
class Palette:
    """A named map style: colors, sizes and vacuum icon.

    ``room_tones`` are given to the map's rooms in order of segment id, so
    every room gets a different tone as long as there are enough tones.
    ``room_colors`` pins a color to a specific segment id and wins over the
    tones. ``sizes`` override the parser's sizes (in unscaled units, e.g.
    ``Size.PATH_WIDTH: 0.5``). ``vacuum_icon`` is a key of ``icons.ICONS``
    or ``None`` for the parser's own icon.
    """

    colors: dict[SupportedColor, Color]
    room_tones: list[Color] = field(default_factory=list)
    room_colors: dict[str, Color] = field(default_factory=dict)
    sizes: dict[Size, float] = field(default_factory=dict)
    vacuum_icon: str | None = None
    # Optional darker band under the cleaning path, so a light path stays
    # readable on light rooms too. Width in unscaled units.
    path_halo: Color | None = None
    path_halo_width: float = 0


# Material 3 dark: muted tonal containers on a transparent background,
# so the map sits on the card's own surface color.
M3_DARK_ROOMS: list[Color] = [
    (86, 130, 206),   # blue
    (214, 160, 64),   # amber
    (52, 120, 86),    # green
    (204, 104, 150),  # pink
    (58, 156, 168),   # teal
    (116, 88, 172),   # purple
    (160, 150, 64),   # olive
    (176, 98, 74),    # clay
]

M3_DARK = Palette(
    colors={
        SupportedColor.MAP_OUTSIDE: TRANSPARENT,
        # Floor not assigned to a room.
        SupportedColor.MAP_INSIDE: (40, 43, 49),
        SupportedColor.NEW_DISCOVERED_AREA: (40, 43, 49),
        # What the lidar saw outside the home, and its edge: hidden.
        SupportedColor.SCAN: TRANSPARENT,
        SupportedColor.MAP_WALL: TRANSPARENT,
        # Walls and furniture outlines: near-black "gaps" between rooms.
        SupportedColor.MAP_WALL_V2: (20, 21, 25),
        # Obstacles outside rooms: dark and quiet.
        SupportedColor.GREY_WALL: (38, 40, 46),
        SupportedColor.PATH: (255, 255, 255, 150),
        SupportedColor.GOTO_PATH: (168, 199, 250),
        SupportedColor.PREDICTED_PATH: (168, 199, 250, 150),
        SupportedColor.MOP_PATH: (255, 255, 255, 40),
        SupportedColor.CLEANED_AREA: (168, 199, 250, 50),
        SupportedColor.ROBO: (168, 199, 250),
        SupportedColor.ROBO_OUTLINE: (18, 19, 22),
        SupportedColor.CHARGER: (159, 216, 155),
        SupportedColor.CHARGER_OUTLINE: (18, 19, 22),
        SupportedColor.ZONES: (168, 199, 250, 60),
        SupportedColor.ZONES_OUTLINE: (168, 199, 250),
        SupportedColor.VIRTUAL_WALLS: (255, 138, 128),
        SupportedColor.NO_GO_ZONES: (255, 138, 128, 50),
        SupportedColor.NO_GO_ZONES_OUTLINE: (255, 138, 128),
        SupportedColor.NO_MOPPING_ZONES: (208, 188, 255, 60),
        SupportedColor.NO_MOPPING_ZONES_OUTLINE: (208, 188, 255),
        SupportedColor.NO_CARPET_ZONES: (255, 184, 112, 60),
        SupportedColor.NO_CARPET_ZONES_OUTLINE: (255, 184, 112),
        SupportedColor.CARPETS: (120, 124, 134, 120),
        SupportedColor.ROOM_NAMES: (227, 227, 233),
        SupportedColor.OBSTACLE: (255, 184, 112, 200),
        SupportedColor.IGNORED_OBSTACLE: (160, 160, 168, 160),
        SupportedColor.OBSTACLE_WITH_PHOTO: (255, 184, 112, 200),
        SupportedColor.IGNORED_OBSTACLE_WITH_PHOTO: (160, 160, 168, 160),
    },
    room_tones=M3_DARK_ROOMS,
    sizes={Size.PATH_WIDTH: 0.5, Size.VACUUM_RADIUS: 4, Size.CHARGER_RADIUS: 4},
    vacuum_icon="saucer",
    path_halo=(0, 0, 0, 70),
    path_halo_width=1.25,
)

# Material 3 light: pastel containers, dark walls.
M3_LIGHT_ROOMS: list[Color] = [
    (216, 226, 255),
    (234, 221, 255),
    (200, 236, 208),
    (255, 220, 190),
    (255, 216, 228),
    (190, 234, 240),
    (238, 232, 180),
    (240, 222, 214),
]

M3_LIGHT = Palette(
    colors={
        SupportedColor.MAP_OUTSIDE: TRANSPARENT,
        SupportedColor.MAP_INSIDE: (230, 232, 238),
        SupportedColor.SCAN: (230, 232, 238),
        SupportedColor.NEW_DISCOVERED_AREA: (230, 232, 238),
        SupportedColor.MAP_WALL: (68, 71, 79),
        SupportedColor.MAP_WALL_V2: (68, 71, 79),
        SupportedColor.GREY_WALL: (68, 71, 79),
        SupportedColor.PATH: (68, 71, 79, 140),
        SupportedColor.GOTO_PATH: (65, 95, 145),
        SupportedColor.PREDICTED_PATH: (65, 95, 145, 140),
        SupportedColor.ROBO: (65, 95, 145),
        SupportedColor.ROBO_OUTLINE: (255, 255, 255),
        SupportedColor.CHARGER: (56, 106, 32),
        SupportedColor.CHARGER_OUTLINE: (255, 255, 255),
        SupportedColor.VIRTUAL_WALLS: (186, 26, 26),
        SupportedColor.NO_GO_ZONES: (186, 26, 26, 50),
        SupportedColor.NO_GO_ZONES_OUTLINE: (186, 26, 26),
        SupportedColor.ROOM_NAMES: (26, 28, 30),
    },
    room_tones=M3_LIGHT_ROOMS,
    sizes={Size.PATH_WIDTH: 0.5, Size.VACUUM_RADIUS: 4, Size.CHARGER_RADIUS: 4},
    vacuum_icon="saucer",
)

# Special option: serve the core integration's own image unchanged.
PALETTE_ORIGINAL = "original"

PALETTES: dict[str, Palette] = {
    "m3_dark": M3_DARK,
    "m3_light": M3_LIGHT,
}

DEFAULT_PALETTE = "m3_dark"
PALETTE_OPTIONS = [*PALETTES, PALETTE_ORIGINAL]
