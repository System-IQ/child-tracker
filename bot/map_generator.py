"""توليد خريطة HTML تفاعلية بدون الحاجة لمكتبات ثقيلة (Leaflet + OpenStreetMap)"""
from datetime import datetime, timezone
from typing import List, Dict


HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>مسار {name}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  html,body{{margin:0;height:100%;font-family:sans-serif}}
  #map{{height:100%}}
  #info{{position:absolute;top:10px;right:10px;background:#fff;padding:12px 16px;
        border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.2);z-index:1000;font-size:13px;max-width:260px}}
  #info h3{{margin:0 0 8px;color:#c0392b}}
  #info div{{margin:3px 0}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:10px;background:#ecf0f1;margin-right:4px}}
</style></head><body>
<div id="map"></div>
<div id="info">
  <h3>📍 {name}</h3>
  <div>📅 {generated_at}</div>
  <div>🔢 النقاط: <b>{points}</b></div>
  <div>📏 المسافة: <b>{distance_km} km</b></div>
  <div>⏱️ زمن الحركة: <b>{moving_time_min} د</b></div>
  <div>⚡ أقصى سرعة: <b>{max_speed_kmh} km/h</b></div>
  <div>📊 متوسط السرعة: <b>{avg_speed_kmh} km/h</b></div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var track = {track_json};
var map = L.map('map').setView([track[0][0], track[0][1]], 15);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19, attribution: '&copy; OpenStreetMap'
}}).addTo(map);
var line = L.polyline(track, {{color:'#c0392b', weight:5, opacity:0.85}}).addTo(map);
L.circleMarker(track[0], {{radius:8, color:'#27ae60', fillOpacity:1}})
  .bindPopup('🚩 البداية').addTo(map);
L.circleMarker(track[track.length-1], {{radius:8, color:'#c0392b', fillOpacity:1}})
  .bindPopup('🏁 آخر موقع').addTo(map);
map.fitBounds(line.getBounds(), {{padding:[40,40]}});
</script></body></html>"""


def build_map_html(points: List[Dict], name: str, stats: Dict) -> bytes:
    track = []
    for p in points:
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat is None or lon is None:
            continue
        track.append([lat, lon])
    if not track:
        track = [[0, 0]]
    html = HTML_TEMPLATE.format(
        name=name,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        points=stats["points"],
        distance_km=stats["distance_km"],
        moving_time_min=stats["moving_time_min"],
        max_speed_kmh=stats["max_speed_kmh"],
        avg_speed_kmh=stats["avg_speed_kmh"],
        track_json=str(track),
    )
    return html.encode("utf-8")
