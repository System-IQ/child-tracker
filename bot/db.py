"""طبقة التعامل مع Supabase - مركزية لكل الاستعلامات"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from supabase import create_client, Client

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL/KEY غير معرّفة")
        _client = create_client(url, key)
    return _client


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_devices() -> list[dict]:
    """جلب كل الأجهزة المسجّلة"""
    res = get_client().table("devices").select("*").execute()
    return res.data or []


def get_device(device_id: str) -> Optional[dict]:
    res = get_client().table("devices").select("*").eq("id", device_id).limit(1).execute()
    return (res.data or [None])[0]


def get_latest(device_id: str) -> Optional[dict]:
    res = (
        get_client().table("locations")
        .select("*")
        .eq("device_id", device_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def get_track(device_id: str, hours: int = 6, limit: int = 10000) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    res = (
        get_client().table("locations")
        .select("*")
        .eq("device_id", device_id)
        .gte("timestamp", since)
        .order("timestamp", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_sos_events(device_id: Optional[str] = None, hours: int = 24) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q = get_client().table("sos_events").select("*").gte("timestamp", since).order("timestamp", desc=True)
    if device_id:
        q = q.eq("device_id", device_id)
    return (q.execute().data) or []


def get_geofences(device_id: str) -> list[dict]:
    res = get_client().table("geofences").select("*").eq("device_id", device_id).execute()
    return res.data or []


def add_geofence(device_id: str, name: str, lat: float, lon: float, radius_m: float) -> dict:
    res = get_client().table("geofences").insert({
        "device_id": device_id,
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "radius_m": radius_m,
    }).execute()
    return (res.data or [{}])[0]


def delete_geofence(geofence_id: str) -> bool:
    res = get_client().table("geofences").delete().eq("id", geofence_id).execute()
    return bool(res.data)


def queue_command(device_id: str, command: str, payload: dict | None = None) -> dict:
    """يضع أمراً في الطابور ليُنفّذ على جهاز الطفل عند عودة الاتصال"""
    res = get_client().table("commands").insert({
        "device_id": device_id,
        "command": command,
        "payload": payload or {},
        "status": "pending",
    }).execute()
    return (res.data or [{}])[0]


def pending_commands(device_id: str) -> list[dict]:
    res = (
        get_client().table("commands").select("*")
        .eq("device_id", device_id).eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


def update_device_status(device_id: str, **kwargs) -> None:
    get_client().table("devices").update(kwargs).eq("id", device_id).execute()
