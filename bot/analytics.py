"""تحليلات ذكية: اكتشاف الأماكن المتكررة (البيت/المدرسة) + Heatmap"""
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from gpx_export import haversine_m


def cluster_points(points: List[Dict], radius_m: float = 100.0,
                   min_visits: int = 3) -> List[Dict]:
    """
    يكتشف الأماكن التي يتوقف فيها الطفل كثيراً (يعني بيت/مدرسة/بيت الجد).
    يعمل بخوارزمية DBSCAN مبسّطة.
    """
    clusters: List[Dict] = []
    for p in points:
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat is None or lon is None:
            continue
        placed = False
        for c in clusters:
            if haversine_m(lat, lon, c["lat"], c["lon"]) <= radius_m:
                c["points"].append(p)
                # تحديث مركز الكتلة (المتوسط)
                c["lat"] = sum(q["latitude"] for q in c["points"]) / len(c["points"])
                c["lon"] = sum(q["longitude"] for q in c["points"]) / len(c["points"])
                placed = True
                break
        if not placed:
            clusters.append({"lat": lat, "lon": lon, "points": [p]})

    result = []
    for c in clusters:
        if len(c["points"]) < min_visits:
            continue
        # حساب الوقت المستغرق
        times = []
        for p in c["points"]:
            try:
                times.append(datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")))
            except Exception:
                pass
        total_min = 0
        if len(times) >= 2:
            total_min = (max(times) - min(times)).total_seconds() / 60
        result.append({
            "lat": round(c["lat"], 6),
            "lon": round(c["lon"], 6),
            "visits": len(c["points"]),
            "total_minutes": round(total_min, 1),
            "first": min(times).isoformat() if times else "",
            "last": max(times).isoformat() if times else "",
        })
    result.sort(key=lambda x: x["total_minutes"], reverse=True)
    return result


def detect_home_school(points: List[Dict]) -> Dict[str, Dict]:
    """يخمّن البيت والمدرسة بناءً على أوقات الزيارة"""
    clusters = cluster_points(points, radius_m=100, min_visits=5)
    home, school = None, None
    for c in clusters:
        try:
            t = datetime.fromisoformat(c["first"].replace("Z", "+00:00")).hour
        except Exception:
            continue
        # 6-9 صباحاً → مدرسة
        if 6 <= t <= 9 and not school:
            school = c
        # 14-22 مساءً/ليل → بيت
        if 14 <= t <= 22 and not home:
            home = c
    return {"home": home or {}, "school": school or {}}


def heatmap_grid(points: List[Dict], cell_deg: float = 0.0005) -> List[Tuple[float, float, int]]:
    """يبني شبكة كثافة لرسم Heatmap"""
    grid: Dict[Tuple[float, float], int] = defaultdict(int)
    for p in points:
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat is None or lon is None:
            continue
        key = (round(lat / cell_deg) * cell_deg, round(lon / cell_deg) * cell_deg)
        grid[key] += 1
    return [(lat, lon, cnt) for (lat, lon), cnt in grid.items() if cnt >= 3]


def daily_summary(points: List[Dict]) -> Dict:
    """ملخص يومي: أول حركة، آخر حركة، عدد التوقفات"""
    if not points:
        return {}
    by_hour: Dict[int, int] = defaultdict(int)
    for p in points:
        try:
            h = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")).hour
            by_hour[h] += 1
        except Exception:
            pass
    stops = cluster_points(points, radius_m=80, min_visits=10)
    return {
        "active_hours": sorted(by_hour.keys()),
        "first_point": points[0].get("timestamp", ""),
        "last_point": points[-1].get("timestamp", ""),
        "n_stops": len(stops),
        "top_stops": stops[:3],
    }
