# Roborock Map Design

Fork of [Roborock Custom Map](https://github.com/Python-roborock/RoborockCustomMap) that re-renders the core Roborock integration's map with a custom color palette (Material You dark/light). If the custom render fails, it falls back to the core image and calibration, which is exactly what upstream serves.

## What it does

- Takes the raw map data the **core Roborock integration** already keeps and renders it again with a custom palette. It makes no extra requests to the cloud or the vacuum.
- The image and the calibration always come **from the same source**, so zones and "go to" targets in the map card stay aligned.
- If the custom render fails (for example after a Home Assistant update), it **automatically serves the core image and calibration**, the same way upstream Roborock Custom Map does.
- **Neighboring rooms get clearly different colors.** The integration works out which rooms touch and picks tones that differ in both hue and lightness, so it adapts when you split or merge rooms.
- A smooth, anti-aliased **flying saucer** vacuum icon that turns with the vacuum's heading, a thinner cleaning path, and hidden lidar noise outside the home.
- The domain is `roborock_map_design`, so it can run **alongside upstream Roborock Custom Map**.

## Entities (per map)

| Entity | Description |
| - | - |
| `image.<map>_design` | Map for the xiaomi-vacuum-map-card, with `calibration_points`, `rooms`, `zones` and `render_mode` attributes |
| `binary_sensor.<map>_design_ok` | `on` while the custom render works (or the "Original" palette is selected). Attributes `render_mode` and `last_error` |
| `select.<map>_palette` | Material You dark / Material You light / Original (core) |
| `select.<map>_rotation` | Rotates the map in 90° steps (image and calibration together) |

The `roborock_map_design.dump_raw_map` action saves the raw map data to `/config/roborock_map_design/*.bin` for tuning palettes outside Home Assistant.

## Installation

1. The core Roborock integration must be set up and loaded.
2. **Don't disable the core integration's `image` entities** if your current map card uses them. They serve as the fallback.
3. HACS → ⋮ → Custom repositories → `https://github.com/tomasvesely92-dev/RoborockCustomMapDesign`, type *Integration*.
4. Download **Roborock Map Design**, then restart Home Assistant.
5. Settings → Devices & services → Add integration → **Roborock Map Design**.

## Map card with a safe fallback

Leave your current card unchanged and make a copy of it. In the copy, change only `map_source` and `calibration_source`:

```yaml
type: vertical-stack
cards:
  - type: conditional
    conditions:
      - condition: state
        entity: binary_sensor.<map>_design_ok
        state: "on"
    card:
      # copy of your current card, with only these two keys changed:
      type: custom:xiaomi-vacuum-map-card
      map_source:
        camera: image.<map>_design
      calibration_source:
        camera: true
      # ... everything else unchanged
  - type: conditional
    conditions:
      - condition: state
        entity: binary_sensor.<map>_design_ok
        state_not: "on"
    card:
      # your current card, unchanged
```

`state_not: "on"` covers `off`, `unavailable`, and the case where the integration doesn't load at all.

## Notification on fallback

```yaml
alias: Vacuum map – fallback
triggers:
  - trigger: state
    entity_id: binary_sensor.<map>_design_ok
    from: "on"
    for: "00:05:00"
actions:
  - action: notify.mobile_app_<phone>
    data:
      title: Vacuum map
      message: >
        The custom map render is not working ({{ state_attr(trigger.entity_id, 'last_error') }}).
        The card is showing the original map.
```

## Changing colors

Palettes live in `custom_components/roborock_map_design/palettes.py`. Colors are `(R, G, B)` or `(R, G, B, A)`.

- `room_tones`: the set of room colors; neighbors automatically get contrasting ones.
- `room_colors`: pin a color to a room by its segment ID (wins over `room_tones`).
- `sizes`: override the parser's sizes, e.g. `Size.PATH_WIDTH` or `Size.VACUUM_RADIUS`.
- `vacuum_icon`: `saucer`, `radar`, `rocket`, `m3_arrow`, `m3_dot`, or `None` for the parser's own icon (see `icons.py`).

## Credits

Based on [Roborock Custom Map](https://github.com/Python-roborock/RoborockCustomMap) by @Lash-L and the [python-roborock](https://github.com/Python-roborock/python-roborock) / [vacuum-map-parser](https://github.com/PiotrMachowski/Python-package-vacuum-map-parser-roborock) projects.
