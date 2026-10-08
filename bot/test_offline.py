"""اختبار المكونات الأساسية بدون الحاجة لاتصال"""
import sys
from datetime import datetime, timezone
from gpx_export import compute_stats, to_gpx_bytes, to_kml_bytes, to_csv_bytes
from map_generator import build_map_html
from security import valid_coords, valid_device_id, sanitize_text


def make_fake_track(n=100):
    pts = []
    base_lat, base_lon = 33.3152, 44.3661
    for i in range(n):
        pts.append({
            "latitude": base_lat + i * 0.0001,
            "longitude": base_lon + i * 0.0001,
            "altitude": 34 + i * 0.1,
            "speed": 1.5 + (i % 5) * 0.5,
            "accuracy": 5.0,
            "heading": 45.0,
            "battery": max(10, 100 - i // 10),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return pts


def main():
    print("🧪 اختبار المكونات...")
    pts = make_fake_track(100)

    s = compute_stats(pts)
    print(f"✅ الإحصائيات: {s}")
    assert s["points"] == 100
    assert s["distance_km"] > 0

    gpx = to_gpx_bytes(pts, "test_device")
    assert gpx.startswith(b"<?xml")
    assert b"<trkpt" in gpx
    print(f"✅ GPX: {len(gpx)} bytes")

    kml = to_kml_bytes(pts, "test_device")
    assert b"<kml" in kml
    print(f"✅ KML: {len(kml)} bytes")

    csv = to_csv_bytes(pts)
    assert csv.startswith(b"timestamp")
    print(f"✅ CSV: {len(csv)} bytes")

    html = build_map_html(pts, "test_device", s)
    assert b"<!DOCTYPE html>" in html or b"<canvas" in html
    print(f"✅ HTML: {len(html)} bytes")

    assert valid_coords(33.3, 44.4)
    assert not valid_coords(200, 44.4)
    assert valid_device_id("child_phone_01")
    assert not valid_device_id("../../etc")
    print("✅ Security checks passed")

    print("\n🎉 جميع الاختبارات نجحت!")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"❌ فشل اختبار: {e}")
        sys.exit(1)


def test_simplify_and_analytics():
    from track_simplify import clean_track, douglas_peucker
    from analytics import cluster_points, heatmap_grid, detect_home_school
    from heatmap_generator import build_heatmap_html

    pts = make_fake_track(200)
    simple = douglas_peucker(pts, epsilon_m=5.0)
    assert len(simple) < len(pts), "Douglas-Peucker لم يقلل النقاط"
    print(f"✅ Douglas-Peucker: {len(pts)} → {len(simple)}")

    cleaned = clean_track(pts)
    print(f"✅ clean_track: {len(cleaned)} نقطة")

    clusters = cluster_points(pts, radius_m=50, min_visits=3)
    print(f"✅ cluster_points: {len(clusters)} كتلة")

    grid = heatmap_grid(pts)
    print(f"✅ heatmap_grid: {len(grid)} خلية")

    html = build_heatmap_html(pts, "test")
    assert b"<!DOCTYPE html>" in html or b"<canvas" in html
    print(f"✅ heatmap HTML: {len(html)} byte")

    home_school = detect_home_school(pts)
    print(f"✅ detect_home_school: home={bool(home_school['home'])} school={bool(home_school['school'])}")


if __name__ == "__main__":
    test_simplify_and_analytics()
