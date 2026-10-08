"""خريطة حرارية HTML تعمل أوفلاين 100% - بدون CDN"""
from datetime import datetime, timezone
from typing import List, Dict
from analytics import heatmap_grid


HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Heatmap - {name}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  html,body{{margin:0;height:100%;background:#111;color:#eee;font-family:sans-serif}}
  #wrap{{position:relative;width:100vw;height:100vh;overflow:hidden}}
  canvas{{display:block;position:absolute;top:0;left:0}}
  #overlay{{position:absolute;top:0;left:0;width:100%;height:100%}}
  #legend{{position:absolute;bottom:20px;right:20px;background:rgba(0,0,0,0.7);
          padding:10px 14px;border-radius:8px;font-size:12px}}
  #legend .bar{{width:200px;height:12px;margin:4px 0;border-radius:6px;
              background:linear-gradient(to right,#0000ff,#00ffff,#00ff00,#ffff00,#ff0000)}}
  #info{{position:absolute;top:15px;left:15px;background:rgba(0,0,0,0.7);
        padding:10px 14px;border-radius:8px;font-size:13px}}
  #info h3{{margin:0 0 6px;color:#4dd}}
</style></head><body>
<div id="wrap">
  <canvas id="c"></canvas>
  <canvas id="overlay"></canvas>
  <div id="info">
    <h3>🔥 {name}</h3>
    <div>النقاط: <b>{total}</b></div>
    <div>المصدر: <b>آخر {hours} ساعة</b></div>
    <div>التاريخ: <b>{date}</b></div>
  </div>
  <div id="legend">
    <div>كثافة الزيارات:</div>
    <div class="bar"></div>
    <div style="display:flex;justify-content:space-between"><span>قليل</span><span>كثير</span></div>
  </div>
</div>
<script>
const POINTS = {points_json};
const TRACK = {track_json};

function fitCanvas() {{
  const w = window.innerWidth, h = window.innerHeight;
  document.getElementById('c').width = w;
  document.getElementById('c').height = h;
  document.getElementById('overlay').width = w;
  document.getElementById('overlay').height = h;
  draw();
}}

function bounds(pts) {{
  let minLat=90, maxLat=-90, minLon=180, maxLon=-180;
  for (const p of pts) {{
    if (p[0]<minLat) minLat=p[0];
    if (p[0]>maxLat) maxLat=p[0];
    if (p[1]<minLon) minLon=p[1];
    if (p[1]>maxLon) maxLon=p[1];
  }}
  const pad = 0.15;
  const dLat = (maxLat-minLat)||0.001, dLon = (maxLon-minLon)||0.001;
  return {{minLat:minLat-pad*dLat, maxLat:maxLat+pad*dLat,
          minLon:minLon-pad*dLon, maxLon:maxLon+pad*dLon}};
}}

function project(lat, lon, b, w, h) {{
  const x = (lon - b.minLon) / (b.maxLon - b.minLon) * w;
  const y = (1 - (lat - b.minLat) / (b.maxLat - b.minLat)) * h;
  return [x, y];
}}

function draw() {{
  const c = document.getElementById('c');
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#0a0a14';
  ctx.fillRect(0, 0, w, h);

  if (POINTS.length === 0) {{
    ctx.fillStyle = '#fff';
    ctx.font = '16px sans-serif';
    ctx.fillText('لا توجد بيانات', 20, 40);
    return;
  }}

  const allPts = POINTS.map(p => [p[0], p[1]]).concat(TRACK);
  const b = bounds(allPts);

  // 1. رسم المسار
  if (TRACK.length > 1) {{
    ctx.strokeStyle = 'rgba(80,180,255,0.5)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i=0; i<TRACK.length; i++) {{
      const [x,y] = project(TRACK[i][0], TRACK[i][1], b, w, h);
      if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }}
    ctx.stroke();
  }}

  // 2. رسم نقاط الكثافة بتدرج شعاعي
  const maxW = Math.max(...POINTS.map(p => p[2]));
  for (const [lat, lon, weight] of POINTS) {{
    const [x, y] = project(lat, lon, b, w, h);
    const ratio = weight / maxW;
    const radius = 15 + ratio * 45;
    const grad = ctx.createRadialGradient(x, y, 0, x, y, radius);
    // Red core -> yellow -> green -> transparent
    if (ratio > 0.75) {{
      grad.addColorStop(0, 'rgba(255,0,0,0.9)');
      grad.addColorStop(0.3, 'rgba(255,165,0,0.6)');
      grad.addColorStop(0.6, 'rgba(255,255,0,0.3)');
    }} else if (ratio > 0.4) {{
      grad.addColorStop(0, 'rgba(255,165,0,0.8)');
      grad.addColorStop(0.4, 'rgba(255,255,0,0.5)');
      grad.addColorStop(0.7, 'rgba(0,255,0,0.2)');
    }} else {{
      grad.addColorStop(0, 'rgba(0,255,0,0.7)');
      grad.addColorStop(0.5, 'rgba(0,128,255,0.3)');
    }}
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI*2);
    ctx.fill();
  }}

  // 3. علامة البداية والنهاية
  if (TRACK.length > 0) {{
    const [sx,sy] = project(TRACK[0][0], TRACK[0][1], b, w, h);
    const [ex,ey] = project(TRACK[TRACK.length-1][0], TRACK[TRACK.length-1][1], b, w, h);
    ctx.fillStyle = '#00ff88';
    ctx.beginPath(); ctx.arc(sx, sy, 8, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = '#ff3355';
    ctx.beginPath(); ctx.arc(ex, ey, 8, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 12px sans-serif';
    ctx.fillText('بداية', sx+10, sy-8);
    ctx.fillText('نهاية', ex+10, ey-8);
  }}

  // 4. شبكة إحداثيات
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 1;
  for (let i=1; i<6; i++) {{
    const x = w*i/6, y = h*i/6;
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke();
  }}
}}

window.addEventListener('resize', fitCanvas);
fitCanvas();
</script></body></html>"""


def build_heatmap_html(points: List[Dict], name: str) -> bytes:
    # بناء قائمة النقاط
    grid = heatmap_grid(points, cell_deg=0.0003)  # دقة أعلى
    heat = [[lat, lon, cnt] for lat, lon, cnt in grid]
    track = [[p["latitude"], p["longitude"]] for p in points
             if p.get("latitude") is not None]
    if not track:
        track = [[0, 0]]

    # تقدير الساعات
    hours = 24
    if len(points) >= 2:
        try:
            t1 = datetime.fromisoformat(points[0]["timestamp"].replace("Z","+00:00"))
            t2 = datetime.fromisoformat(points[-1]["timestamp"].replace("Z","+00:00"))
            hours = max(1, int((t2-t1).total_seconds() / 3600))
        except Exception:
            pass

    html = HTML_TEMPLATE.format(
        name=name,
        total=len(points),
        hours=hours,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        points_json=str(heat),
        track_json=str(track),
    )
    return html.encode("utf-8")
