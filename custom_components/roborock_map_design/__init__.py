"""Roborock Map Design integration.

A fork of Roborock Custom Map that re-renders the core Roborock
integration's maps with a custom color palette, falling back to the core
image and calibration whenever the custom render fails.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_MAP_ROTATION,
    CONF_PALETTE,
    DOMAIN,
    RENDER_STATE,
    SERVICE_DUMP_RAW_MAP,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.IMAGE, Platform.SELECT, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roborock Map Design from a config entry."""
    roborock_entries = hass.config_entries.async_entries("roborock")
    coordinators = []

    @callback
    def unload_this_entry() -> None:
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    for r_entry in roborock_entries:
        if r_entry.state == ConfigEntryState.LOADED:
            coordinators.extend(r_entry.runtime_data.v1)
            r_entry.async_on_unload(unload_this_entry)

    if not coordinators:
        raise ConfigEntryNotReady("No Roborock entries loaded. Cannot start.")

    entry.runtime_data = coordinators

    data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    data.setdefault(CONF_MAP_ROTATION, {})
    data.setdefault(CONF_PALETTE, {})
    data.setdefault(RENDER_STATE, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_DUMP_RAW_MAP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DUMP_RAW_MAP,
            _make_dump_handler(hass),
            supports_response=SupportsResponse.OPTIONAL,
        )

    return True


def _make_dump_handler(hass: HomeAssistant):
    """Build the service handler that saves raw map bytes for offline tuning."""

    async def _dump(call: ServiceCall) -> ServiceResponse:
        out_dir = Path(hass.config.path(DOMAIN))
        to_write: dict[Path, bytes] = {}
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state != ConfigEntryState.LOADED:
                continue
            for coord in entry.runtime_data:
                home = coord.properties_api.home
                if home is None:
                    continue
                for map_flag, content in (home.home_map_content or {}).items():
                    if content.raw_api_response:
                        name = f"{coord.duid_slug}_map{map_flag}.bin"
                        to_write[out_dir / name] = content.raw_api_response

        def _write() -> list[str]:
            out_dir.mkdir(parents=True, exist_ok=True)
            for path, raw in to_write.items():
                path.write_bytes(raw)
            return [str(p) for p in to_write]

        files = await hass.async_add_executor_job(_write)
        _LOGGER.info("Saved %d raw map file(s) to %s", len(files), out_dir)
        return {"files": files}

    return _dump


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_DUMP_RAW_MAP)
    return unloaded
