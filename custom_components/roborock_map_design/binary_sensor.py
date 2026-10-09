"""Status sensor: on while the custom map render is working.

Use it in a conditional card: show the custom map while it is ``on`` and
your current, unchanged map card otherwise (``state_not: "on"`` also
covers ``off``, ``unavailable`` and a missing entity).
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.components.roborock.entity import RoborockCoordinatedEntityV1
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    MODE_CUSTOM,
    MODE_ORIGINAL,
    MODE_PENDING,
    RENDER_STATE,
    SIGNAL_RENDER_STATE,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one status sensor per map."""
    async_add_entities(
        RoborockMapRenderOk(
            config_entry,
            f"{coord.duid_slug}_map_design_ok_{map_info.map_flag}",
            coord,
            map_info.map_flag,
            map_info.name,
        )
        for coord in config_entry.runtime_data
        if coord.properties_api.home is not None
        for map_info in (coord.properties_api.home.home_map_info or {}).values()
    )


class RoborockMapRenderOk(RoborockCoordinatedEntityV1, BinarySensorEntity):
    """On when the custom map is served (or the original was chosen)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        map_flag: int,
        map_name: str,
    ) -> None:
        """Initialize the sensor."""
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        self.config_entry = config_entry
        self.map_key = f"{coordinator.duid_slug}_{map_flag}"
        self._attr_name = f"{map_name or f'Map {map_flag}'} design OK"

    def _state(self) -> dict:
        return (
            self.hass.data.get(DOMAIN, {})
            .get(self.config_entry.entry_id, {})
            .get(RENDER_STATE, {})
            .get(self.map_key, {"mode": MODE_PENDING, "error": None})
        )

    @property
    def is_on(self) -> bool | None:
        mode = self._state()["mode"]
        if mode == MODE_PENDING:
            return None
        return mode in (MODE_CUSTOM, MODE_ORIGINAL)

    @property
    def extra_state_attributes(self) -> dict:
        state = self._state()
        return {"render_mode": state["mode"], "last_error": state["error"]}

    async def async_added_to_hass(self) -> None:
        """Follow render state changes from the image entity."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_RENDER_STATE}_{self.config_entry.entry_id}_{self.map_key}",
                self._handle_render_state,
            )
        )

    @callback
    def _handle_render_state(self) -> None:
        self.async_write_ha_state()
