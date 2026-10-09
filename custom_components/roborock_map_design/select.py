"""Select entities: map rotation and color palette (one of each per map)."""

from __future__ import annotations

from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.components.roborock.entity import RoborockCoordinatedEntityV1
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_MAP_ROTATION,
    CONF_PALETTE,
    DEFAULT_MAP_ROTATION,
    DOMAIN,
    MAP_ROTATION_OPTIONS,
    SIGNAL_PALETTE_CHANGED,
    SIGNAL_ROTATION_CHANGED,
)
from .palettes import DEFAULT_PALETTE, PALETTE_OPTIONS

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rotation and palette selects (one of each per map)."""
    entities: list[SelectEntity] = []
    for coord in config_entry.runtime_data:
        if coord.properties_api.home is None:
            continue
        for map_info in (coord.properties_api.home.home_map_info or {}).values():
            for cls in (RoborockMapRotationSelect, RoborockMapPaletteSelect):
                entities.append(
                    cls(config_entry, coord, map_info.map_flag, map_info.name)
                )
    async_add_entities(entities)


class _MapOptionSelect(RoborockCoordinatedEntityV1, RestoreEntity, SelectEntity):
    """Per-map option stored in hass.data and announced by a signal."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    data_key: str
    signal: str
    unique_suffix: str
    name_suffix: str
    default: str

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: RoborockDataUpdateCoordinator,
        map_flag: int,
        map_name: str,
    ) -> None:
        """Initialize the select."""
        RoborockCoordinatedEntityV1.__init__(
            self,
            f"{coordinator.duid_slug}_map_design_{self.unique_suffix}_{map_flag}",
            coordinator,
        )
        self.config_entry = config_entry
        self.map_key = f"{coordinator.duid_slug}_{map_flag}"
        self._attr_name = f"{map_name or f'Map {map_flag}'} {self.name_suffix}"
        self._attr_current_option = self.default

    def _store(self, option: str) -> None:
        self.hass.data[DOMAIN][self.config_entry.entry_id][self.data_key][
            self.map_key
        ] = self._to_stored(option)

    def _to_stored(self, option: str):
        return option

    async def async_added_to_hass(self) -> None:
        """Restore the previous choice."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in self._attr_options:
                self._attr_current_option = last.state
        self._store(self._attr_current_option)
        async_dispatcher_send(
            self.hass,
            f"{self.signal}_{self.config_entry.entry_id}_{self.map_key}",
        )
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Store the new choice and notify the image entity."""
        if option not in self._attr_options:
            return
        self._attr_current_option = option
        self._store(option)
        async_dispatcher_send(
            self.hass,
            f"{self.signal}_{self.config_entry.entry_id}_{self.map_key}",
        )
        self.async_write_ha_state()


class RoborockMapRotationSelect(_MapOptionSelect):
    """Rotate the map image together with its calibration."""

    _attr_translation_key = "rotation"
    _attr_options = [str(v) for v in MAP_ROTATION_OPTIONS]
    data_key = CONF_MAP_ROTATION
    signal = SIGNAL_ROTATION_CHANGED
    unique_suffix = "rotation"
    name_suffix = "rotation"
    default = str(DEFAULT_MAP_ROTATION)

    def _to_stored(self, option: str) -> int:
        return int(option)


class RoborockMapPaletteSelect(_MapOptionSelect):
    """Choose the color palette, or the core integration's original image."""

    _attr_translation_key = "palette"
    _attr_options = list(PALETTE_OPTIONS)
    data_key = CONF_PALETTE
    signal = SIGNAL_PALETTE_CHANGED
    unique_suffix = "palette"
    name_suffix = "palette"
    default = DEFAULT_PALETTE
