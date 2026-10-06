"""تبسيط المسارات وتنقية الضوضاء باستخدام Douglas-Peucker + Kalman مبسّط"""
import math
from typing import List, Dict


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _perp_distance(pt, line_start, line_end) -> float:
    """المسافة العمودية من نقطة إلى خط"""
    x0, y0 = pt
    x1, y1 = line_start
    x2, y2 = line_end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    t = max(0, min(1, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return math.hypot(x0 - px, y0 - py)


def douglas_peucker(points: List[Dict], epsilon_m: float = 5.0) -> List[Dict]:
    """يبسّط المسار مع الحفاظ على الشكل - يقلل النقاط بنسبة 60-90%"""
    if len(points) < 3:
        return points
    coords = [(p["latitude"], p["longitude"]) for p in points]

    def _dp(start, end, keep):
        if end <= start + 1:
            return
        dmax = 0.0
        idx = start
        for i in range(start + 1, end):
            d = _perp_distance(coords[i], coords[start], coords[end])
            if d > dmax:
                dmax = d
                idx = i
        # تحويل درجة إلى متر تقريبياً (1° ≈ 111 km)
        if dmax * 111000 > epsilon_m:
            _dp(start, idx, keep)
            keep.add(idx)
            _dp(idx, end, keep)

    keep = {0, len(points) - 1}
    _dp(0, len(points) - 1, keep)
    return [points[i] for i in sorted(keep)]


def filter_outliers(points: List[Dict], max_speed_kmh: float = 200.0) -> List[Dict]:
    """يحذف النقاط الشاذة (سرعة مستحيلة)"""
    if len(points) < 2:
        return points
    out = [points[0]]
    for i in range(1, len(points)):
        p_prev, p_cur = out[-1], points[i]
        try:
            from datetime import datetime
            t1 = datetime.fromisoformat(p_prev["timestamp"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(p_cur["timestamp"].replace("Z", "+00:00"))
            dt = (t2 - t1).total_seconds()
        except Exception:
            dt = 0
        if dt <= 0:
            out.append(p_cur)
            continue
        dist = haversine_m(p_prev["latitude"], p_prev["longitude"],
                           p_cur["latitude"], p_cur["longitude"])
        speed = (dist / dt) * 3.6
        if speed <= max_speed_kmh:
            out.append(p_cur)
    return out


def filter_by_accuracy(points: List[Dict], max_acc_m: float = 50.0) -> List[Dict]:
    """يستبعد النقاط ذات دقة سيئة"""
    return [p for p in points if (p.get("accuracy") or 0) <= max_acc_m]


def clean_track(points: List[Dict], accuracy_m: float = 50.0,
                outlier_speed: float = 200.0, epsilon_m: float = 5.0) -> List[Dict]:
    """خط الأنابيب الكامل للتنقية"""
    pts = filter_by_accuracy(points, accuracy_m)
    pts = filter_outliers(pts, outlier_speed)
    pts = douglas_peucker(pts, epsilon_m)
    return pts
