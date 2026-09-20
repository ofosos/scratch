# GDACS events → Azure regions

Fetches recent GDACS events (default back to 2021-01-01) from the official
GDACS API and assigns each event to every Azure region whose radius circle
(default 100 km) around the region coordinates overlaps the event geometry.
Events that overlap multiple region circles are assigned to all of them.

## Usage

```bash
python3 gdacs_az_regions.py                       # defaults: since 2021-01-01,
                                                   # all event types, yellow+red
python3 gdacs_az_regions.py --event-types floods droughts \
                            --start-date 2025-01-01 --end-date 2026-09-20 \
                            --radius-km 150 \
                            --output my_regions.json
```

CLI options:

- `--regions-file` — Azure regions JSON (default `az_regions_annotated.json`,
  keyed by programmatic region name with `latitude`/`longitude`)
- `--output` — output JSON (default `gdacs_events_by_region.json`)
- `--error-log` — error log (default `<output>.error.log`)
- `--start-date` / `--end-date` — time window (default 2021-01-01 / now)
- `--event-types` — friendly names (`earthquakes`, `cyclones`, `floods`,
  `volcanoes`, `droughts`, `wildfires`) or GDACS codes (`EQ`, `TC`, `FL`,
  `VO`, `DR`, `WF`); default: all
- `--alert-levels` — `green`, `yellow` (GDACS "orange"), `red`, `orange`;
  default: `yellow red`
- `--radius-km` — region circle radius (default 100)
- `--max-events` — cap number of events (testing)
- `-v` — verbose logging

## GDACSClient options

```python
from gdacs_az_regions import GDACSClient

client = GDACSClient(
    start_date="2021-01-01",          # or a datetime
    end_date=None,                   # default: now
    event_types=["floods", "volcanoes"],  # or ["FL", "VO"], default: all
    alert_levels=["yellow", "red"],   # GDACS: green/orange/red; "yellow" == orange
)
events = client.search_events()       # /api/Events/geteventlist/search, paged
```

## API implementation notes (per gdac-swagger.json)

- `GET /api/Events/geteventlist/search` with `eventlist`, `alertlevel`,
  `fromDate`, `toDate`, `pageSize` (max 100), `pageNumber`; paged until
  exhausted (a short page, an empty FeatureCollection, or HTTP 204 ends it).
- `GET /api/Polygons/getgeometry` with `eventtype`, `eventid`, `episodeid`:
  the search endpoint returns only a centroid (`Class == "Point_Centroid"`
  or a bare Point geometry), so the script follows the event's `url.geometry`
  link and runs the circle-overlap test against the real polygon.
  `GET /api/Events/geteventdata` is used as fallback source of the link.
- Any response that should be JSON but isn't (e.g. GDACS returns HTTP 204
  with an empty body for "no results") is logged, and the raw non-conforming
  text is dumped into the error log.

## Output

`gdacs_events_by_region.json` is keyed by the programmatic Azure region
name; each value is a list of the GDACS events matching that region
(type, ids, name, alert level, dates, countries, severity, geometry source,
urls, and the full list of matched regions).

## Live-test status (2026-09-20)

- Full run: 453 events (11 DR, 135 EQ, 106 FL, 121 TC, 22 VO, 58 WF) across
  5 search pages, 35 event→region assignments over 46 regions.
- The summer 2026 drought in central Europe (DR/1018332, Orange,
  2025-12-21 → 2026-09-18) is assigned to **10 regions**: westeurope,
  northeurope, germanywestcentral, francecentral, switzerlandnorth,
  switzerlandwest, uksouth, ukwest, swedensouth, italynorth.

## Dependencies

`python3 -m pip install numpy pandas requests`
