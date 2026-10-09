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
