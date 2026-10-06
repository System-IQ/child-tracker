-- ============================================
-- Child Tracker - Supabase Schema الكامل
-- شغّل هذا في SQL Editor في Supabase
-- ============================================

-- جدول الأجهزة (الأطفال)
CREATE TABLE IF NOT EXISTS devices (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  owner_id    BIGINT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  last_seen   TIMESTAMPTZ,
  battery     INT,
  app_version TEXT
);

-- جدول المواقع
CREATE TABLE IF NOT EXISTS locations (
  id         BIGSERIAL PRIMARY KEY,
  device_id  TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  latitude   DOUBLE PRECISION NOT NULL,
  longitude  DOUBLE PRECISION NOT NULL,
  altitude   DOUBLE PRECISION,
  speed      DOUBLE PRECISION,
  accuracy   DOUBLE PRECISION,
  heading    DOUBLE PRECISION,
  battery    INT,
  source     TEXT DEFAULT 'gps',
  timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_loc_dev_time ON locations(device_id, timestamp DESC);

-- جدول السياج الجغرافي
CREATE TABLE IF NOT EXISTS geofences (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id  TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  latitude   DOUBLE PRECISION NOT NULL,
  longitude  DOUBLE PRECISION NOT NULL,
  radius_m   DOUBLE PRECISION NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- جدول أحداث SOS
CREATE TABLE IF NOT EXISTS sos_events (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id  TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  latitude   DOUBLE PRECISION NOT NULL,
  longitude  DOUBLE PRECISION NOT NULL,
  message    TEXT,
  timestamp  TIMESTAMPTZ DEFAULT NOW()
);

-- جدول الأوامر عن بعد
CREATE TABLE IF NOT EXISTS commands (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id  TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  command    TEXT NOT NULL,
  payload    JSONB DEFAULT '{}'::jsonb,
  status     TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  executed_at TIMESTAMPTZ
);

-- ============================================
-- Row Level Security (حماية البيانات)
-- ============================================
ALTER TABLE devices     ENABLE ROW LEVEL SECURITY;
ALTER TABLE locations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE geofences   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sos_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE commands    ENABLE ROW LEVEL SECURITY;

-- سياسة مفتوحة للـ anon (استخدم فقط في التطوير)
-- في الإنتاج: استخدم service_role للبوت، ولا تفتح anon
CREATE POLICY "anon_all_devices"   ON devices    FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_locations" ON locations  FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_geofences" ON geofences  FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_sos"       ON sos_events FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_commands"  ON commands   FOR ALL TO anon USING (true) WITH CHECK (true);

-- ============================================
-- تسجيل جهاز افتراضي (للتجربة)
-- ============================================
INSERT INTO devices (id, name) VALUES ('child_phone_01', 'الطفل الأول')
ON CONFLICT (id) DO NOTHING;
