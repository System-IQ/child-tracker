"""خريطة حرارية HTML تفاعلية تُظهر أكثر الأماكن زيارة"""
from datetime import datetime, timezone
from typing import List, Dict
from analytics import heatmap_grid


HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Heatmap - {name}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>html,body{{margin:0;height:100%}}#map{{height:100%}}</style>
</head><body><div id="map"></div>
<script>
var heat = {heat_json};
var track = {track_json};
var map = L.map('map').setView([track[0][0], track[0][1]], 14);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{
  maxZoom:19, attribution:'&copy; OpenStreetMap'
}}).addTo(map);
L.polyline(track, {{color:'#3498db', weight:3, opacity:0.6}}).addTo(map);
L.heatLayer(heat, {{radius:25, blur:15, maxZoom:17,
  gradient:{{0.2:'blue',0.4:'lime',0.6:'yellow',0.8:'orange',1:'red'}}}}).addTo(map);
</script></body></html>"""


def build_heatmap_html(points: List[Dict], name: str) -> bytes:
    track = [[p["latitude"], p["longitude"]] for p in points
             if p.get("latitude") is not None]
    if not track:
        track = [[0, 0]]
    grid = heatmap_grid(points, cell_deg=0.0005)
    heat = [[lat, lon, min(cnt / 20.0, 1.0)] for lat, lon, cnt in grid]
    html = HTML.format(name=name,
                       heat_json=str(heat),
                       track_json=str(track))
    return html.encode("utf-8")
