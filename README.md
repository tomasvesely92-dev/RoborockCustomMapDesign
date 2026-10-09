# Roborock Map Design

Fork of [Roborock Custom Map](https://github.com/Python-roborock/RoborockCustomMap) that re-renders the core Roborock integration's map with a custom color palette (Material You dark/light). If the custom render fails, it falls back to the core image and calibration, which is exactly what upstream serves.

Česky níže.

---

## Co to dělá

- Vezme surová data mapy, která si drží **core Roborock integrace**, a vykreslí je znovu s vlastní paletou. Na cloud ani na vysavač se neposílají žádné dotazy navíc.
- Obrázek i kalibrace vždy pocházejí **ze stejného zdroje**, takže zóny a „jeď sem“ v kartě sedí.
- Když vlastní vykreslení selže (např. po aktualizaci HA), komponenta **automaticky vrátí původní obrázek a kalibraci z core**, tak jak je servíruje původní RoborockCustomMap.
- Doména je `roborock_map_design`, takže může běžet **vedle originálního RoborockCustomMap**.

## Entity (pro každou mapu)

| Entita | Popis |
| - | - |
| `image.<mapa>_design` | Mapa pro xiaomi-vacuum-map-card, včetně atributů `calibration_points`, `rooms`, `zones` a `render_mode` |
| `binary_sensor.<mapa>_design_ok` | `on`, dokud vlastní vykreslení funguje (nebo je zvolená paleta „Původní“). Atributy `render_mode` a `last_error` |
| `select.<mapa>_palette` | Material You – tmavá / světlá / Původní (core) |
| `select.<mapa>_rotation` | Otočení mapy po 90° (otáčí obrázek i kalibraci) |

Služba `roborock_map_design.dump_raw_map` uloží surová data map do `/config/roborock_map_design/*.bin`, pro ladění palety mimo HA.

## Instalace

1. Core Roborock integrace musí být nastavená a načtená.
2. **`image` entity core integrace nevypínej**, pokud je používá tvoje současná karta (slouží jako záloha).
3. HACS → ⋮ → Custom repositories → `https://github.com/tomasvesely92-dev/RoborockCustomMapDesign`, typ *Integration*.
4. Stáhnout **Roborock Map Design**, restartovat HA.
5. Nastavení → Zařízení a služby → Přidat integraci → **Roborock Map Design**.

## Karta s bezpečným fallbackem

Současnou kartu nech beze změny a zkopíruj ji. V kopii změň jen `map_source` a `calibration_source`:

```yaml
type: vertical-stack
cards:
  - type: conditional
    conditions:
      - condition: state
        entity: binary_sensor.<mapa>_design_ok
        state: "on"
    card:
      # kopie současné karty, jen tyto dvě položky:
      type: custom:xiaomi-vacuum-map-card
      map_source:
        camera: image.<mapa>_design
      calibration_source:
        camera: true
      # ... zbytek beze změny
  - type: conditional
    conditions:
      - condition: state
        entity: binary_sensor.<mapa>_design_ok
        state_not: "on"
    card:
      # současná karta, beze změny
```

`state_not: "on"` pokryje `off`, `unavailable` i stav, kdy se integrace vůbec nenačte.

## Notifikace při výpadku

```yaml
alias: Mapa vysavače – fallback
triggers:
  - trigger: state
    entity_id: binary_sensor.<mapa>_design_ok
    from: "on"
    for: "00:05:00"
actions:
  - action: notify.mobile_app_<telefon>
    data:
      title: Mapa vysavače
      message: >
        Vlastní vykreslení mapy nefunguje ({{ state_attr(trigger.entity_id, 'last_error') }}).
        Karta ukazuje původní mapu.
```

## Úprava barev

Palety jsou v `custom_components/roborock_map_design/palettes.py`. Barvy jsou `(R, G, B)` nebo `(R, G, B, A)`, místnosti se klíčují podle ID segmentu.

## Credits

Based on [Roborock Custom Map](https://github.com/Python-roborock/RoborockCustomMap) by @Lash-L and the [python-roborock](https://github.com/Python-roborock/python-roborock) / [vacuum-map-parser](https://github.com/PiotrMachowski/Python-package-vacuum-map-parser-roborock) projects.
