"""Constants for Roborock Map Design integration."""

DOMAIN = "roborock_map_design"

CONF_MAP_ROTATION = "map_rotation"
DEFAULT_MAP_ROTATION = 0
MAP_ROTATION_OPTIONS = (0, 90, 180, 270)

CONF_PALETTE = "palette"
RENDER_STATE = "render_state"

SIGNAL_ROTATION_CHANGED = "roborock_map_design_rotation_changed"
SIGNAL_PALETTE_CHANGED = "roborock_map_design_palette_changed"
SIGNAL_RENDER_STATE = "roborock_map_design_render_state"

# Render modes reported by the image entity and the status binary sensor.
MODE_PENDING = "pending"
MODE_CUSTOM = "custom"  # our palette, our calibration
MODE_ORIGINAL = "original"  # user chose the core image on purpose
MODE_FALLBACK = "fallback"  # custom render failed, core image served

# Used only if the core integration's constants can't be imported.
FALLBACK_MAP_SCALE = 4

SERVICE_DUMP_RAW_MAP = "dump_raw_map"

# Live map: while the vacuum is moving, fetch only the map (one GET_MAP_V1
# request) more often than the core integration does (~30-45 s), so the path
# and robot position on the design map follow the vacuum closely.
LIVE_MAP_INTERVAL_SECONDS = 10
# After a failed/timed-out live fetch, wait this long before trying again.
LIVE_MAP_BACKOFF_SECONDS = 30
# Roborock state codes during which the robot moves and draws a new path:
# remote control, cleaning, returning home, manual, spot, docking,
# going to target, zoned, segment, mapping and the mop variants (6301-6310).
LIVE_MAP_STATES = frozenset(
    {4, 5, 6, 7, 11, 15, 16, 17, 18, 29, *range(6301, 6311)}
)
