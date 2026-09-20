#!/usr/bin/env python3
"""
GDACS events mapped to Azure regions.

Fetches recent GDACS events (default back to 2021-01-01) from the official
GDACS API (https://www.gdacs.org/gdacsapi/swagger/index.html), resolves the
real event geometry via /api/Polygons/getgeometry whenever the search
endpoint only returns a centroid (Class == "Point_Centroid" or a bare Point
geometry), and assigns each event to every Azure region whose radius circle
(default 100 km) around the region coordinates overlaps the event geometry.

Output: a JSON file keyed by the programmatic Azure region name, where the
value is the list of all matching GDACS events for that region.

API usage (per the official swagger / gdac-swagger.json):
  - GET /api/Events/geteventlist/search
      params: eventlist (e.g. "EQ;FL;DR;VO;TC;WF"), alertlevel (e.g.
      "green;orange;red"), fromDate, toDate (date-time), pageSize (max 100),
      pageNumber. Returns a GeoJSON FeatureCollection; empty result sets are
      served as HTTP 204 with an empty body, which is handled and logged.
  - GET /api/Polygons/getgeometry
      params: eventtype, eventid, episodeid. Returns the true polygonal
      geometry of the event (centroid, affected area, intensity zones, ...).
  - GET /api/Events/geteventdata
      params: eventtype, eventid. Fallback source of the url.geometry link.
"""

import argparse
import json
import logging
import math
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

DEFAULT_BASE_URL = "https://www.gdacs.org/gdacsapi/api"
DEFAULT_START_DATE = "2021-01-01"
DEFAULT_RADIUS_KM = 100.0
DEFAULT_ALERT_LEVELS = ["yellow", "red"]
DEFAULT_EVENT_TYPES = ["EQ", "TC", "FL", "VO", "DR", "WF"]

# Friendly event type names accepted by the client / CLI.
EVENT_TYPE_NAMES = {
    "earthquake": "EQ", "earthquakes": "EQ", "eq": "EQ",
    "cyclone": "TC", "cyclones": "TC", "tropicalcyclone": "TC",
    "storm": "TC", "storms": "TC", "tc": "TC",
    "flood": "FL", "floods": "FL", "fl": "FL",
    "volcano": "VO", "volcanoes": "VO", "volcanic": "VO", "vo": "VO",
    "drought": "DR", "droughts": "DR", "dr": "DR",
    "wildfire": "WF", "wildfires": "WF", "fire": "WF", "fires": "WF",
    "forestfire": "WF", "forestfires": "WF", "wf": "WF",
}

# GDACS only knows Green / Orange / Red alert levels.
ALERT_LEVEL_ALIASES = {
    "green": ["green"],
    "yellow": ["orange"],
    "orange": ["orange"],
    "red": ["red"],
}

EARTH_RADIUS_KM = 6371.0088

logger = logging.getLogger("gdacs_az")


# ---------------------------------------------------------------------------
# GDACS API client
# ---------------------------------------------------------------------------

class GDACSClient:
    """Client for the official GDACS API.

    Options:
      - start_date / end_date: restrict the event time window (datetime or
        ISO date strings). end_date defaults to "now".
      - event_types: restrict to GDACS event type codes, e.g.
        ["EQ", "TC", "FL", "VO", "DR", "WF"] (earthquakes, tropical
        cyclones, floods, volcanoes, droughts, wildfires).
      - alert_levels: restrict to GDACS alert levels; accepts the common
        alias "yellow" which GDACS calls "orange". Default ["yellow", "red"].
    """

    EVENT_TYPES = DEFAULT_EVENT_TYPES
    PAGE_SIZE = 100  # swagger: "Max 100"

    def __init__(self, base_url=DEFAULT_BASE_URL, timeout=60, max_retries=3,
                 start_date=DEFAULT_START_DATE, end_date=None,
                 event_types=None, alert_levels=None, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.start_date = self._parse_date(start_date)
        self.end_date = self._parse_date(end_date)
        self.event_types = self._normalize_event_types(event_types)
        self.alert_levels = self._normalize_alert_levels(alert_levels)

    # -- option normalization ---------------------------------------------

    @staticmethod
    def _parse_date(value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(value)[:len(fmt) + 2], fmt)
            except ValueError:
                continue
        raise ValueError(f"Unparseable date: {value!r}")

    @staticmethod
    def _normalize_event_types(event_types):
        if not event_types:
            return list(GDACSClient.EVENT_TYPES)
        codes = []
        for item in event_types:
            for code in str(item).replace(",", ";").split(";"):
                code = code.strip()
                if not code:
                    continue
                mapped = EVENT_TYPE_NAMES.get(code.lower(), code.upper())
                if mapped not in codes:
                    codes.append(mapped)
        return codes

    @staticmethod
    def _normalize_alert_levels(alert_levels):
        if not alert_levels:
            alert_levels = DEFAULT_ALERT_LEVELS
        levels = []
        for item in alert_levels:
            for level in str(item).replace(",", ";").split(";"):
                level = level.strip().lower()
                if not level:
                    continue
                for mapped in ALERT_LEVEL_ALIASES.get(level, [level]):
                    if mapped not in levels:
                        levels.append(mapped)
        return levels

    # -- low-level helpers --------------------------------------------------

    def _get(self, url, params=None, expect_json=True, description="request"):
        """GET with retries. Any response that is expected to be JSON but is
        not parseable JSON (e.g. empty 204 bodies or HTML error pages) is
        dumped verbatim into the error log."""
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_exc = requests.HTTPError(
                        f"{description}: HTTP {resp.status_code}")
                    logger.warning("%s: HTTP %s (attempt %d/%d)",
                                   description, resp.status_code, attempt,
                                   self.max_retries)
                    continue
                if expect_json:
                    return self._decode_json(resp, description)
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning("%s: %s (attempt %d/%d)", description, exc,
                               attempt, self.max_retries)
        raise last_exc or requests.RequestException(
            f"{description}: retries exhausted")

    def _decode_json(self, resp, description):
        content_type = (resp.headers.get("content-type") or "").lower()
        body = resp.text or ""
        if resp.status_code == 204 or not body.strip():
            # GDACS signals "no results" with 204 + empty body: not an error,
            # but it is a non-JSON response where JSON is expected, so log it.
            logger.debug("%s: empty non-JSON response (HTTP %d, %d bytes)",
                         description, resp.status_code, len(body))
            return None
        try:
            return resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            logger.error(
                "%s: expected JSON but got non-JSON response "
                "(HTTP %d, content-type=%s). Raw body follows:\n%s",
                description, resp.status_code, content_type, body[:5000])
            return None

    # -- API operations ------------------------------------------------------

    def search_events(self):
        """GET /api/Events/geteventlist/search with paging until exhausted.

        Returns a list of event property dicts, one per GDACS event."""
        params = {
            "eventlist": ";".join(self.event_types),
            "alertlevel": ";".join(self.alert_levels),
            "pageSize": self.PAGE_SIZE,
            "pageNumber": 1,
        }
        if self.start_date:
            params["fromDate"] = self.start_date.strftime("%Y-%m-%dT%H:%M:%S")
        if self.end_date:
            params["toDate"] = self.end_date.strftime("%Y-%m-%dT%H:%M:%S")

        events = []
        page = 1
        while True:
            params["pageNumber"] = page
            data = self._get(
                f"{self.base_url}/Events/geteventlist/search",
                params=params,
                description=f"event search page {page}",
            )
            if data is None:
                logger.info("Search exhausted (no JSON) at page %d", page)
                break
            features = data.get("features", []) if isinstance(data, dict) else []
            if not features:
                logger.info("Search exhausted at page %d (0 features)", page)
                break
            for feature in features:
                props = feature.get("properties", {})
                props["_search_geometry"] = feature.get("geometry")
                events.append(props)
            logger.info("Search page %d: %d events", page, len(features))
            if len(features) < self.PAGE_SIZE:
                break
            page += 1
        return events

    def get_event_data(self, eventtype, eventid):
        """GET /api/Events/geteventdata — fallback source for url.geometry."""
        data = self._get(
            f"{self.base_url}/Events/geteventdata",
            params={"eventtype": eventtype, "eventid": eventid},
            description=f"event data {eventtype}/{eventid}",
        )
        if isinstance(data, dict):
            return data.get("properties", data)
        return None

    def get_geometry(self, eventtype, eventid, episodeid):
        """GET /api/Polygons/getgeometry — the true event geometry.

        Returns a list of GeoJSON features (centroid, affected area,
        intensity polygons, ...)."""
        data = self._get(
            f"{self.base_url}/Polygons/getgeometry",
            params={"eventtype": eventtype, "eventid": eventid,
                    "episodeid": episodeid},
            description=f"geometry {eventtype}/{eventid}/{episodeid}",
        )
        if isinstance(data, dict):
            return data.get("features", [])
        return []


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def rings_from_geometry(geometry):
    """Return a list of (Ni, 2) numpy arrays, one per linear ring of a
    GeoJSON Polygon/MultiPolygon. Point geometries yield a single 1-vertex
    ring. Ring structure is preserved (not flattened across rings) so that
    even-odd containment and segment-distance tests stay correct for
    MultiPolygons made of many parts."""
    if not isinstance(geometry, dict):
        return []
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")

    def is_point(node):
        return (len(node) >= 2 and isinstance(node[0], (int, float))
                and isinstance(node[1], (int, float))
                and not isinstance(node[0], bool))

    def walk(node, rings):
        if not isinstance(node, (list, tuple)):
            return
        if is_point(node):
            rings.append(np.array([[float(node[0]), float(node[1])]],
                                  dtype=float))
            return
        for child in node:
            walk(child, rings)

    if gtype == "Point":
        return [np.array([[float(coords[0]), float(coords[1])]],
                         dtype=float)]
    if gtype == "LineString":
        return [np.array(coords, dtype=float)]
    if gtype not in ("Polygon", "MultiPolygon"):
        return []
    polys = coords if gtype == "MultiPolygon" else [coords]
    rings = []
    for poly in polys:
        for ring in poly:
            arr = np.array(ring, dtype=float)
            if arr.ndim == 2 and arr.shape[1] == 2 and len(arr) >= 3:
                rings.append(arr)
    return rings


def is_bare_point(feature_geometry, props):
    """True when the search/geteventdata result only carries a centroid:
    properties Class == 'Point_Centroid' or the geometry is a bare Point."""
    if isinstance(props, dict) and str(props.get("Class", "")).strip().lower() \
            == "point_centroid":
        return True
    if isinstance(feature_geometry, dict) \
            and feature_geometry.get("type") == "Point":
        return True
    return False


def haversine_matrix(lons1, lats1, lon2, lat2):
    """Great-circle distance (km) from a single point to many points,
    using a vectorized haversine formula."""
    lon1 = np.radians(lons1)
    lat1 = np.radians(lats1)
    lon2_r = math.radians(lon2)
    lat2_r = math.radians(lat2)
    dlon = lon1 - lon2_r
    dlat = lat1 - lat2_r
    a = np.sin(dlat / 2.0) ** 2 + \
        np.cos(lat1) * np.cos(lat2_r) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def ring_bboxes(rings):
    """Per-ring (min_lon, min_lat, max_lon, max_lat) bboxes as an (R, 4)
    numpy array, plus a total bbox over all rings."""
    boxes = np.empty((len(rings), 4), dtype=float)
    for i, ring in enumerate(rings):
        if len(ring):
            boxes[i] = (ring[:, 0].min(), ring[:, 1].min(),
                        ring[:, 0].max(), ring[:, 1].max())
        else:
            boxes[i] = (np.nan, np.nan, np.nan, np.nan)
    return boxes


def circle_polygon_overlap(rings, center_lon, center_lat, radius_km,
                           bboxes=None):
    """Circle-polygon overlap test against a list of closed rings:
    vertex-in-circle OR circle-center-inside (even-odd over all rings, so
    holes are handled) OR minimum segment distance <= radius.

    bboxes: optional per-ring bbox array from ring_bboxes() to speed up
    repeated tests of the same event against many region circles.
    """
    if not rings:
        return False, float("inf")
    if bboxes is None:
        bboxes = ring_bboxes(rings)

    # Radius expressed in degrees for a cheap bbox pre-filter.
    lat_span = radius_km / 111.32
    coslat = max(math.cos(math.radians(min(abs(center_lat) + lat_span, 90.0))),
                 0.01)
    lon_span = radius_km / (111.32 * coslat)
    lo_lon = center_lon - lon_span
    hi_lon = center_lon + lon_span
    lo_lat = center_lat - lat_span
    hi_lat = center_lat + lat_span

    min_seen = float("inf")
    candidates = []
    for i, ring in enumerate(rings):
        if len(ring) == 0:
            continue
        b0, b1, b2, b3 = bboxes[i]
        near = not (b2 < lo_lon or b0 > hi_lon or b3 < lo_lat or b1 > hi_lat)
        # bbox of the circle vs ring bbox with margin: farther than radius?
        if not near:
            continue
        candidates.append(ring)
        # 1. any vertex within the circle
        dists = haversine_matrix(ring[:, 0], ring[:, 1],
                                 center_lon, center_lat)
        dmin = float(dists.min())
        if dmin < min_seen:
            min_seen = dmin
        if dmin <= radius_km:
            return True, dmin

    # 2. circle center inside the (multi)polygon, even-odd over all rings
    if point_in_polygon(center_lon, center_lat, candidates):
        return True, 0.0
    # 3. minimum distance from the center to any closed-ring segment
    for ring in candidates:
        d = point_segment_min_distance(center_lon, center_lat, ring)
        if d < min_seen:
            min_seen = d
        if d <= radius_km:
            return True, d
    return False, min_seen


def point_in_polygon(lon, lat, rings):
    """Vectorized ray-casting point-in-polygon with the even-odd rule over a
    list of rings (outer boundaries and holes alike)."""
    x = float(lon)
    y = float(lat)
    inside = False
    for ring in rings:
        n = len(ring)
        if n < 3:
            continue
        xs = ring[:, 0]
        ys = ring[:, 1]
        x1 = xs
        y1 = ys
        x2 = np.roll(xs, -1)
        y2 = np.roll(ys, -1)
        crosses = (y1 > y) != (y2 > y)
        if not np.any(crosses):
            continue
        # x coordinate of the edge/scanline intersection
        with np.errstate(divide="ignore", invalid="ignore"):
            x_int = (x2[crosses] - x1[crosses]) * \
                (y - y1[crosses]) / (y2[crosses] - y1[crosses]) + x1[crosses]
        # even-odd: count edges crossing the scanline to the right of x
        if int(np.count_nonzero(x < x_int)) % 2 == 1:
            inside = not inside
    return inside


def point_segment_min_distance(lon, lat, ring):
    """Approximate minimum geodesic distance (km) from a point to the
    segments of one closed ring, computed on a local equirectangular
    projection centered at the point (accurate at ~100 km scales)."""
    pts = np.vstack([ring, ring[0]]) if len(ring) else ring
    x0 = math.radians(lon)
    y0 = math.radians(lat)
    coslat0 = max(math.cos(y0), 0.01)
    xs = np.radians(pts[:, 0])
    ys = np.radians(pts[:, 1])
    x1, x2 = xs[:-1], xs[1:]
    y1, y2 = ys[:-1], ys[1:]
    dx = (x2 - x1) * coslat0
    dy = y2 - y1
    px = (x0 - x1) * coslat0
    py = y0 - y1
    denom = dx * dx + dy * dy
    t = np.where(denom > 1e-18,
                 (px * dx + py * dy) / np.where(denom > 1e-18, denom, 1.0),
                 0.0)
    t = np.clip(t, 0.0, 1.0)
    ex = px - t * dx
    ey = py - t * dy
    planar = np.sqrt(ex * ex + ey * ey)
    return float(np.min(planar) * EARTH_RADIUS_KM)


def resolve_event_geometry(client, props):
    """Resolve the true geometry of an event.

    If /search (or geteventdata) returned a real polygon, use it directly.
    If it only returned a centroid (Class == "Point_Centroid" or a bare
    Point geometry), follow the event's url.geometry link
    (/api/Polygons/getgeometry) to fetch the actual polygon, and test the
    circle overlap against that.

    Returns (rings, source) where rings is a list of (N, 2) numpy arrays of
    closed linear rings (lon, lat)."""
    eventtype = props.get("eventtype")
    eventid = props.get("eventid")
    episodeid = props.get("episodeid")
    search_geom = props.get("_search_geometry")

    if not is_bare_point(search_geom, props):
        rings = rings_from_geometry(search_geom)
        if any(len(r) > 1 for r in rings):
            return rings, "search-polygon"

    # Only a centroid: follow url.geometry (fall back to geteventdata).
    geom_url = None
    urls = props.get("url")
    if isinstance(urls, dict):
        geom_url = urls.get("geometry")
    if not geom_url and episodeid is not None:
        detail = client.get_event_data(eventtype, eventid)
        if isinstance(detail, dict):
            urls = detail.get("url")
            if isinstance(urls, dict):
                geom_url = urls.get("geometry")
    if not geom_url:
        geom_url = (f"{client.base_url}/Polygons/getgeometry"
                    f"?eventtype={eventtype}&eventid={eventid}"
                    f"&episodeid={episodeid}")

    features = client.get_geometry(eventtype, eventid, episodeid)
    if not features and geom_url:
        resp = client._get(geom_url, expect_json=True,
                           description=f"geometry link {eventtype}/{eventid}")
        features = resp.get("features", []) if isinstance(resp, dict) else []

    # Prefer the actual area polygons, skip the centroid and global layers.
    best = None
    for feat in features or []:
        fprops = feat.get("properties", {})
        fclass = str(fprops.get("Class", ""))
        geom = feat.get("geometry", {})
        if geom.get("type") == "Point":
            continue
        if fclass.startswith("Poly_Global"):
            continue
        rings = rings_from_geometry(geom)
        if not rings or not any(len(r) >= 3 for r in rings):
            continue
        if fclass in ("Poly_area", "Poly_Affected"):
            best = rings
            break
        if fclass.startswith("Poly_Circle"):
            best = best or rings
        elif "SMPInt" in fclass:
            best = best or rings
        elif best is None:
            best = rings
    if best is None:
        for feat in features or []:
            geom = feat.get("geometry", {})
            if geom.get("type") != "Point":
                rings = rings_from_geometry(geom)
                if rings and any(len(r) >= 3 for r in rings):
                    best = rings
                    break
    if best is None:
        # Fall back to the centroid itself as a zero-area geometry.
        rings = rings_from_geometry(search_geom) if search_geom else []
        if rings:
            return rings, "centroid-only"
        return None, "no-geometry"
    return best, "getgeometry-polygon"


# ---------------------------------------------------------------------------
# Region matching
# ---------------------------------------------------------------------------

def match_events_to_regions(client, regions, radius_km, events=None,
                            verbose=True):
    """Assign each GDACS event to every region whose radius circle overlaps
    the event geometry. Returns (output dict, per-event summary DataFrame)."""
    if events is None:
        events = client.search_events()
    logger.info("Fetched %d GDACS events", len(events))

    region_names = list(regions.keys())
    region_lons = np.array([regions[r]["longitude"] for r in region_names],
                           dtype=float)
    region_lats = np.array([regions[r]["latitude"] for r in region_names],
                           dtype=float)

    output = {name: [] for name in region_names}
    rows = []

    for idx, props in enumerate(events, 1):
        eventtype = props.get("eventtype")
        eventid = props.get("eventid")
        label = f"{eventtype}/{eventid}"
        rings, source = resolve_event_geometry(client, props)
        if not rings or not any(len(r) > 0 for r in rings):
            logger.warning("%s: no usable geometry; skipping", label)
            rows.append({"eventtype": eventtype, "eventid": eventid,
                         "name": props.get("name", ""),
                         "matched_regions": 0, "geometry_source": source,
                         "min_distance_km": None})
            continue

        matched = []
        min_dist = float("inf")
        bboxes = ring_bboxes(rings)
        for i, rname in enumerate(region_names):
            rlon = region_lons[i]
            rlat = region_lats[i]
            overlaps, dist = circle_polygon_overlap(
                rings, rlon, rlat, radius_km, bboxes=bboxes)
            if overlaps:
                matched.append(rname)
                if dist < min_dist:
                    min_dist = dist

        event_summary = {
            "eventtype": eventtype,
            "eventid": eventid,
            "episodeid": props.get("episodeid"),
            "eventname": props.get("eventname"),
            "name": props.get("name"),
            "description": props.get("description"),
            "alertlevel": props.get("alertlevel"),
            "alertscore": props.get("alertscore"),
            "fromdate": props.get("fromdate"),
            "todate": props.get("todate"),
            "country": props.get("country"),
            "iso3": props.get("iso3"),
            "severitydata": props.get("severitydata"),
            "glide": props.get("glide"),
            "geometry_source": source,
            "url_geometry": (props.get("url") or {}).get("geometry"),
            "url_report": (props.get("url") or {}).get("report"),
            "matched_azure_regions": matched,
        }
        for rname in matched:
            output[rname].append(event_summary)

        rows.append({"eventtype": eventtype, "eventid": eventid,
                     "name": props.get("name", ""),
                     "matched_regions": len(matched),
                     "geometry_source": source,
                     "min_distance_km": None if min_dist == float("inf")
                     else round(min_dist, 1)})
        if verbose:
            logger.info("%s (%s): matched %d region(s)%s", label, source,
                        len(matched),
                        f" {matched}" if len(matched) <= 8 else "")

    df = pd.DataFrame(rows)
    return output, df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_regions(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Map GDACS events to Azure regions by circle overlap.")
    parser.add_argument("--regions-file", default="az_regions_annotated.json",
                        help="JSON file with Azure regions (default: "
                             "az_regions_annotated.json)")
    parser.add_argument("--output", default="gdacs_events_by_region.json",
                        help="Output JSON file")
    parser.add_argument("--error-log", default=None,
                        help="Error log file (default: <output>.error.log)")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE,
                        help="Start date, default 2021-01-01")
    parser.add_argument("--end-date", default=None,
                        help="End date, default: now")
    parser.add_argument("--event-types", nargs="*", default=None,
                        help="GDACS event types: friendly names (earthquakes, "
                             "cyclones, floods, volcanoes, droughts, "
                             "wildfires) or codes (EQ TC FL VO DR WF); "
                             "default: all")
    parser.add_argument("--alert-levels", nargs="*", default=None,
                        help="Alert levels, e.g. yellow red green orange "
                             "(default: yellow red)")
    parser.add_argument("--radius-km", type=float, default=DEFAULT_RADIUS_KM,
                        help="Region circle radius in km (default: 100)")
    parser.add_argument("--max-events", type=int, default=None,
                        help="Limit number of events (for testing)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging")
    args = parser.parse_args(argv)

    log_file = args.error_log or (args.output + ".error.log")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, mode="w", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)])

    regions = load_regions(args.regions_file)
    logger.info("Loaded %d Azure regions from %s", len(regions),
                args.regions_file)

    client = GDACSClient(
        start_date=args.start_date,
        end_date=args.end_date,
        event_types=args.event_types,
        alert_levels=args.alert_levels,
    )
    logger.info("Client config: types=%s levels=%s window=%s..%s",
                client.event_types, client.alert_levels, client.start_date,
                client.end_date)

    events = client.search_events()
    if args.max_events:
        events = events[:args.max_events]

    output, df = match_events_to_regions(client, regions, args.radius_km,
                                         events=events)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d regions, %d with events, %d event slots)",
                args.output, len(output),
                sum(1 for v in output.values() if v),
                sum(len(v) for v in output.values()))

    print("\n=== Summary ===")
    if not df.empty:
        print(df.groupby("eventtype").agg(
            events=("eventid", "count"),
            with_matches=("matched_regions", lambda s: int((s > 0).sum())),
            avg_matches=("matched_regions", "mean"),
        ).round(2).to_string())
        multi = df[df["matched_regions"] > 1]
        print(f"\nEvents assigned to multiple regions: {len(multi)}")
        if len(multi):
            print(multi[["eventtype", "eventid", "name",
                         "matched_regions"]].head(20).to_string(index=False))
    else:
        print("No events fetched.")
    print(f"\nOutput: {args.output}\nError log: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
