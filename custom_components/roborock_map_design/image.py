"""Roborock map image re-rendered with a custom palette.

Image and calibration always come from the same source:
- custom mode: our own parse of the raw map bytes (our palette)
- original/fallback mode: the core integration's image and map data,
  exactly as upstream Roborock Custom Map serves them
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import io
import logging

from PIL import Image, UnidentifiedImageError
from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.map_data import MapData

from homeassistant.components.image import ImageEntity
from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.components.roborock.entity import RoborockCoordinatedEntityV1
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MAP_ROTATION,
    CONF_PALETTE,
    DEFAULT_MAP_ROTATION,
    DOMAIN,
    FALLBACK_MAP_SCALE,
    LIVE_MAP_BACKOFF_SECONDS,
    LIVE_MAP_INTERVAL_SECONDS,
    LIVE_MAP_STATES,
    MAP_ROTATION_OPTIONS,
    MODE_CUSTOM,
    MODE_FALLBACK,
    MODE_ORIGINAL,
    MODE_PENDING,
    RENDER_STATE,
    SIGNAL_PALETTE_CHANGED,
    SIGNAL_RENDER_STATE,
    SIGNAL_ROTATION_CHANGED,
)
from .palettes import DEFAULT_PALETTE, PALETTE_ORIGINAL
from .renderer import RenderResult, render_map

try:  # Mirror the core integration's drawables option and scale.
    from homeassistant.components.roborock.const import (
        DEFAULT_DRAWABLES as CORE_DEFAULT_DRAWABLES,
        DRAWABLES as CORE_DRAWABLES,
        MAP_SCALE as CORE_MAP_SCALE,
    )
except ImportError:  # pragma: no cover - only if core renames them
    CORE_DEFAULT_DRAWABLES = {
        Drawable.CHARGER: True,
        Drawable.PATH: True,
        Drawable.VACUUM_POSITION: True,
    }
    CORE_DRAWABLES = "drawables"
    CORE_MAP_SCALE = FALLBACK_MAP_SCALE

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return PNG (width, height) from raw bytes, or None if not a PNG."""
    if len(data) < 24:
        return None
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def _rotate_point_map_xy(
    x: float, y: float, w: int, h: int, rotation: int
) -> tuple[float, float]:
    """Rotate a point in map pixel space around the image bounds.

    rotation is counter-clockwise (PIL Image.rotate does CCW).
    Uses continuous coordinates (w - x / h - y) to avoid off-by-one issues.
    """
    if rotation == 0:
        return (x, y)
    if rotation == 90:
        return (y, w - x)
    if rotation == 180:
        return (w - x, h - y)
    if rotation == 270:
        return (h - y, x)
    return (x, y)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock Map Design image platform."""
    async_add_entities(
        RoborockDesignMap(
            config_entry,
            f"{coord.duid_slug}_map_design_{map_info.map_flag}",
            coord,
            coord.properties_api.home,
            map_info.map_flag,
            map_info.name,
        )
        for coord in config_entry.runtime_data
        if coord.properties_api.home is not None
        for map_info in (coord.properties_api.home.home_map_info or {}).values()
    )


class RoborockDesignMap(RoborockCoordinatedEntityV1, ImageEntity):
    """Roborock map image with a custom palette and a safe fallback."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    image_last_updated: datetime
    _attr_name: str

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        home_trait: HomeTrait,
        map_flag: int,
        map_name: str,
    ) -> None:
        """Initialize the map."""
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)

        self.config_entry = config_entry
        self.map_flag = map_flag
        self.map_key = f"{coordinator.duid_slug}_{map_flag}"
        self._home_trait = home_trait
        self._attr_name = f"{map_name or f'Map {map_flag}'} design"

        self._render: RenderResult | None = None
        self._render_mode = MODE_PENDING
        self._last_error: str | None = None
        self._rendered_raw: bytes | None = None
        self._rendered_palette: str | None = None
        self._render_lock = asyncio.Lock()

        # Live map state (see _async_live_tick).
        self._live_content: MapContent | None = None
        self._core_raw_seen: bytes | None = None
        self._live_busy = False
        self._live_retry_after: datetime | None = None
        self._live_failures = 0

    # ----- source data -------------------------------------------------

    @property
    def _core_map_content(self) -> MapContent | None:
        """The map content as last fetched by the core integration."""
        if self._home_trait.home_map_content and (
            map_content := self._home_trait.home_map_content.get(self.map_flag)
        ):
            return map_content
        return None

    @property
    def _map_content(self) -> MapContent | None:
        """Newest map content: our live fetch if fresher than the core's."""
        if self._live_content is not None:
            return self._live_content
        return self._core_map_content

    def _current(self) -> tuple[bytes, MapData | None]:
        """Return image and map data from ONE source (never mixed)."""
        if self._render is not None:
            return self._render.image, self._render.map_data
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")
        return map_content.image_content or b"", map_content.map_data

    def _entry_data(self) -> dict:
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})

    def _get_rotation(self) -> int:
        rotation = self._entry_data().get(CONF_MAP_ROTATION, {}).get(
            self.map_key, DEFAULT_MAP_ROTATION
        )
        return rotation if rotation in MAP_ROTATION_OPTIONS else DEFAULT_MAP_ROTATION

    def _get_palette(self) -> str:
        return self._entry_data().get(CONF_PALETTE, {}).get(
            self.map_key, DEFAULT_PALETTE
        )

    def _drawables(self) -> list[Drawable]:
        """Use the same drawables the user picked in the core integration."""
        try:
            options = self.coordinator.config_entry.options.get(CORE_DRAWABLES, {})
        except AttributeError:
            options = {}
        return [
            drawable
            for drawable, default in CORE_DEFAULT_DRAWABLES.items()
            if options.get(drawable, default)
        ]

    # ----- lifecycle ---------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Hook up signals and do the first render."""
        await super().async_added_to_hass()
        self._attr_image_last_updated = self.coordinator.last_home_update

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_ROTATION_CHANGED}_{self.config_entry.entry_id}_{self.map_key}",
                self._handle_rotation_changed,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_PALETTE_CHANGED}_{self.config_entry.entry_id}_{self.map_key}",
                self._handle_palette_changed,
            )
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_live_tick,
                timedelta(seconds=LIVE_MAP_INTERVAL_SECONDS),
                name=f"{DOMAIN} live map {self.map_key}",
            )
        )
        self.async_write_ha_state()
        self.hass.async_create_task(self._async_refresh_render())

    @callback
    def _handle_rotation_changed(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @callback
    def _handle_palette_changed(self) -> None:
        # Non-forced: re-renders only if the palette actually differs.
        self.hass.async_create_task(self._async_refresh_render())

    @callback
    def _handle_coordinator_update(self) -> None:
        """Re-render when the core integration has a new map."""
        core = self._core_map_content
        if core is not None and core.raw_api_response != self._core_raw_seen:
            # The core just fetched a map; it is at least as new as ours.
            self._core_raw_seen = core.raw_api_response
            self._live_content = None
        if (map_content := self._map_content) is not None and (
            map_content.raw_api_response != self._rendered_raw
        ):
            self.hass.async_create_task(self._async_refresh_render())
        super()._handle_coordinator_update()

    # ----- live map ----------------------------------------------------

    def _live_map_wanted(self) -> bool:
        """True while the robot moves on this map (path/position change)."""
        try:
            status = self.coordinator.properties_api.status
            state = getattr(status.state, "value", status.state)
            if state not in LIVE_MAP_STATES:
                return False
            current_map = self._home_trait._maps_trait.current_map  # noqa: SLF001
        except AttributeError:
            return False
        return current_map is None or current_map == self.map_flag

    async def _async_live_tick(self, _now: datetime) -> None:
        """Fetch just the map (one GET_MAP_V1) while the vacuum is moving.

        The core integration refreshes the map at most every ~30-45 s and
        sends three cloud commands each time. Here we send only the map
        command, every LIVE_MAP_INTERVAL_SECONDS, and only while cleaning,
        returning or docking. On failure we back off and simply keep serving
        the last map, so nothing gets worse than the core behaviour.
        """
        if self._live_busy or not self.enabled or not self._live_map_wanted():
            return
        now = dt_util.utcnow()
        if self._live_retry_after is not None and now < self._live_retry_after:
            return
        try:
            trait = self._home_trait._map_content  # noqa: SLF001
        except AttributeError:
            return

        self._live_busy = True
        try:
            await trait.refresh()
        except Exception as err:  # noqa: BLE001 - never break the entity
            self._live_failures += 1
            self._live_retry_after = now + timedelta(seconds=LIVE_MAP_BACKOFF_SECONDS)
            _LOGGER.debug(
                "Live map fetch for %s failed (%d in a row), retrying in %ss: %s",
                self.entity_id,
                self._live_failures,
                LIVE_MAP_BACKOFF_SECONDS,
                err,
            )
            return
        finally:
            self._live_busy = False

        self._live_failures = 0
        self._live_retry_after = None
        raw = trait.raw_api_response
        if not raw or raw == self._rendered_raw:
            return
        self._live_content = MapContent(
            image_content=trait.image_content,
            map_data=trait.map_data,
            raw_api_response=raw,
        )
        await self._async_refresh_render()

    # ----- rendering ---------------------------------------------------

    async def _async_refresh_render(self, force: bool = False) -> None:
        """Render with our palette, or fall back to the core image."""
        async with self._render_lock:
            map_content = self._map_content
            if map_content is None:
                return
            raw = map_content.raw_api_response
            palette = self._get_palette()
            if (
                not force
                and raw == self._rendered_raw
                and palette == self._rendered_palette
            ):
                return

            if palette == PALETTE_ORIGINAL:
                self._render = None
                self._render_mode = MODE_ORIGINAL
                self._last_error = None
            else:
                try:
                    self._render = await self.hass.async_add_executor_job(
                        render_map, raw, palette, self._drawables(), CORE_MAP_SCALE
                    )
                    self._render_mode = MODE_CUSTOM
                    self._last_error = None
                except Exception as err:  # noqa: BLE001 - always fall back
                    if self._render_mode != MODE_FALLBACK:
                        _LOGGER.warning(
                            "Custom map render failed for %s, serving the core "
                            "Roborock map instead: %s",
                            self.entity_id,
                            err,
                            exc_info=True,
                        )
                    self._render = None
                    self._render_mode = MODE_FALLBACK
                    self._last_error = str(err)

            self._rendered_raw = raw
            self._rendered_palette = palette
            self._attr_image_last_updated = dt_util.utcnow()
            self._publish_render_state()
            self.async_write_ha_state()

    @callback
    def _publish_render_state(self) -> None:
        state = {"mode": self._render_mode, "error": self._last_error}
        self._entry_data().setdefault(RENDER_STATE, {})[self.map_key] = state
        async_dispatcher_send(
            self.hass,
            f"{SIGNAL_RENDER_STATE}_{self.config_entry.entry_id}_{self.map_key}",
        )

    def _rotate_image(self, raw: bytes, rotation: int) -> bytes:
        img = Image.open(io.BytesIO(raw))
        img = img.rotate(rotation, expand=True)
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    async def async_image(self) -> bytes | None:
        """Return the current image, rotated if configured."""
        image, _ = self._current()
        rotation = self._get_rotation()
        if rotation == DEFAULT_MAP_ROTATION:
            return image
        try:
            return await self.hass.async_add_executor_job(
                self._rotate_image, image, rotation
            )
        except (OSError, UnidentifiedImageError) as err:
            _LOGGER.debug("Failed to rotate map image: %s, returning original", err)
            return image

    @property
    def extra_state_attributes(self):
        """Calibration, rooms and zones for the map card (same source as image)."""
        try:
            image, map_data = self._current()
        except HomeAssistantError:
            return {"render_mode": self._render_mode}
        attrs: dict = {"render_mode": self._render_mode}
        if map_data is None:
            return attrs

        if map_data.rooms is not None:
            room_map = self._home_trait._rooms_trait.room_map  # noqa: SLF001
            for room in map_data.rooms.values():
                name = room_map.get(room.number)
                room.name = name.name if name else "Unknown"

        calibration = map_data.calibration()
        rotation = self._get_rotation()
        size = _png_dimensions(image)
        if rotation != DEFAULT_MAP_ROTATION and size is not None:
            w, h = size
            rotated = []
            for pt in calibration:
                mp = pt.get("map") or {}
                x, y = mp.get("x"), mp.get("y")
                if x is None or y is None:
                    rotated.append(pt)
                    continue
                nx, ny = _rotate_point_map_xy(float(x), float(y), w, h, rotation)
                rotated.append({**pt, "map": {**mp, "x": nx, "y": ny}})
            calibration = rotated

        attrs.update(
            {
                "calibration_points": calibration,
                "rooms": map_data.rooms,
                "zones": map_data.zones,
            }
        )
        return attrs
