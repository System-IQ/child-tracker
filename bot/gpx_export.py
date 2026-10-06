"""تصدير المسارات إلى GPX/KML/CSV مع إحصائيات"""
import math
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import List, Dict, Tuple


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_stats(points: List[Dict]) -> Dict:
    total_dist = 0.0
    max_speed = 0.0
    speeds = []
    prev = None
    moving_time_s = 0.0
    prev_ts = None
    for p in points:
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat is None or lon is None:
            continue
        spd = float(p.get("speed") or 0)
        if spd > max_speed:
            max_speed = spd
        if spd > 0.5:
            speeds.append(spd)
        ts = p.get("timestamp")
        if prev and ts and prev_ts:
            total_dist += haversine_m(prev[0], prev[1], lat, lon)
            try:
                dt = (datetime.fromisoformat(ts.replace("Z", "+00:00"))
                      - datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))).total_seconds()
                if spd > 0.5:
                    moving_time_s += max(dt, 0)
            except Exception:
                pass
        prev = (lat, lon)
        prev_ts = ts
    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    return {
        "points": len(points),
        "distance_km": round(total_dist / 1000, 3),
        "max_speed_kmh": round(max_speed * 3.6, 1),
        "avg_speed_kmh": round(avg_speed * 3.6, 1),
        "moving_time_min": round(moving_time_s / 60, 1),
    }


def to_gpx_bytes(points: List[Dict], device_name: str) -> bytes:
    now = datetime.now(timezone.utc).isoformat()
    buf = StringIO()
    buf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    buf.write('<gpx version="1.1" creator="ChildTracker" xmlns="http://www.topografix.com/GPX/1/1">\n')
    buf.write(f'  <metadata><name>{device_name}</name><time>{now}</time></metadata>\n')
    buf.write(f'  <trk><name>{device_name}</name><trkseg>\n')
    for p in points:
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat is None or lon is None:
            continue
        ts = p.get("timestamp", now)
        ele = p.get("altitude") or 0
        spd = p.get("speed") or 0
        buf.write(f'    <trkpt lat="{lat}" lon="{lon}">\n')
        buf.write(f'      <ele>{ele}</ele>\n<time>{ts}</time>\n')
        if spd:
            buf.write(f'      <speed>{spd}</speed>\n')
        buf.write('    </trkpt>\n')
    buf.write('  </trkseg></trk>\n</gpx>\n')
    return buf.getvalue().encode("utf-8")


def to_kml_bytes(points: List[Dict], device_name: str) -> bytes:
    buf = StringIO()
    buf.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n')
    buf.write('<Document>\n')
    buf.write(f'<name>{device_name}</name>\n')
    buf.write('<Style id="line"><LineStyle><color>ff00a5ff</color><width>4</width></LineStyle></Style>\n')
    buf.write('<Placemark><name>Track</name><styleUrl>#line</styleUrl><LineString><coordinates>\n')
    for p in points:
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat is None or lon is None:
            continue
        ele = p.get("altitude") or 0
        buf.write(f'{lon},{lat},{ele}\n')
    buf.write('</coordinates></LineString></Placemark>\n</Document></kml>\n')
    return buf.getvalue().encode("utf-8")


def to_csv_bytes(points: List[Dict]) -> bytes:
    buf = StringIO()
    buf.write("timestamp,latitude,longitude,altitude,speed,accuracy,heading,battery\n")
    for p in points:
        buf.write(",".join(str(p.get(k, "")) for k in
                ("timestamp", "latitude", "longitude", "altitude", "speed", "accuracy", "heading", "battery")))
        buf.write("\n")
    return buf.getvalue().encode("utf-8")
