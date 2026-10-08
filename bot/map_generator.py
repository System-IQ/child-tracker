"""خريطة HTML تعمل أوفلاين (Canvas) - بدون CDN"""
from datetime import datetime, timezone
from typing import List, Dict


HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>{name}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  html,body{{margin:0;height:100%;background:#0a0a14;color:#eee;font-family:sans-serif}}
  #wrap{{position:relative;width:100vw;height:100vh}}
  canvas{{position:absolute;top:0;left:0}}
  #info{{position:absolute;top:15px;left:15px;background:rgba(0,0,0,0.75);
        padding:12px 16px;border-radius:8px;font-size:13px;max-width:280px}}
  #info h3{{margin:0 0 8px;color:#4dd}}
  #info div{{margin:3px 0}}
</style></head><body>
<div id="wrap">
  <canvas id="c"></canvas>
  <div id="info">
    <h3>📍 {name}</h3>
    <div>📅 {date}</div>
    <div>🔢 النقاط: <b>{points}</b></div>
    <div>📏 المسافة: <b>{distance_km} km</b></div>
    <div>⏱️ الحركة: <b>{moving_time_min} د</b></div>
    <div>⚡ أقصى سرعة: <b>{max_speed_kmh} km/h</b></div>
  </div>
</div>
<script>
const TRACK = {track_json};

function fit() {{
  const c = document.getElementById('c');
  c.width = window.innerWidth; c.height = window.innerHeight;
  draw();
}}

function bounds(pts) {{
  let mnLa=90,mxLa=-90,mnLo=180,mxLo=-180;
  for (const p of pts) {{
    if (p[0]<mnLa) mnLa=p[0]; if (p[0]>mxLa) mxLa=p[0];
    if (p[1]<mnLo) mnLo=p[1]; if (p[1]>mxLo) mxLo=p[1];
  }}
  const pad=0.12, dLa=(mxLa-mnLa)||0.001, dLo=(mxLo-mnLo)||0.001;
  return {{mnLa:mnLa-pad*dLa,mxLa:mxLa+pad*dLa,mnLo:mnLo-pad*dLo,mxLo:mxLo+pad*dLo}};
}}

function proj(lat,lon,b,w,h) {{
  const x=(lon-b.mnLo)/(b.mxLo-b.mnLo)*w;
  const y=(1-(lat-b.mnLa)/(b.mxLa-b.mnLa))*h;
  return [x,y];
}}

function draw() {{
  const c=document.getElementById('c'),ctx=c.getContext('2d');
  const w=c.width,h=c.height;
  ctx.fillStyle='#0a0a14';ctx.fillRect(0,0,w,h);

  if (!TRACK || TRACK.length===0) {{
    ctx.fillStyle='#fff';ctx.font='16px sans-serif';
    ctx.fillText('لا توجد بيانات مسار',20,50);
    return;
  }}

  const b=bounds(TRACK);

  // شبكة
  ctx.strokeStyle='rgba(255,255,255,0.06)';ctx.lineWidth=1;
  for (let i=1;i<8;i++) {{
    const x=w*i/8,y=h*i/8;
    ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();
    ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
  }}

  // خط المسار
  ctx.strokeStyle='#4dd0e1';ctx.lineWidth=4;ctx.lineCap='round';ctx.lineJoin='round';
  ctx.beginPath();
  for (let i=0;i<TRACK.length;i++) {{
    const [x,y]=proj(TRACK[i][0],TRACK[i][1],b,w,h);
    if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  }}
  ctx.stroke();

  // نقاط صغيرة
  ctx.fillStyle='rgba(77,208,225,0.5)';
  for (const p of TRACK) {{
    const [x,y]=proj(p[0],p[1],b,w,h);
    ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);ctx.fill();
  }}

  // بداية ونهاية
  const [sx,sy]=proj(TRACK[0][0],TRACK[0][1],b,w,h);
  const [ex,ey]=proj(TRACK[TRACK.length-1][0],TRACK[TRACK.length-1][1],b,w,h);
  ctx.fillStyle='#00ff88';
  ctx.beginPath();ctx.arc(sx,sy,10,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#ff3355';
  ctx.beginPath();ctx.arc(ex,ey,10,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#fff';ctx.font='bold 13px sans-serif';
  ctx.fillText('بداية',sx+14,sy-10);
  ctx.fillText('نهاية',ex+14,ey-10);
}}

window.addEventListener('resize',fit);
fit();
</script></body></html>"""


def build_map_html(points: List[Dict], name: str, stats: Dict) -> bytes:
    track = [[p["latitude"], p["longitude"]] for p in points
             if p.get("latitude") is not None]
    if not track:
        track = []
    html = HTML_TEMPLATE.format(
        name=name,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        points=stats.get("points", 0),
        distance_km=stats.get("distance_km", 0),
        moving_time_min=stats.get("moving_time_min", 0),
        max_speed_kmh=stats.get("max_speed_kmh", 0),
        track_json=str(track),
    )
    return html.encode("utf-8")
