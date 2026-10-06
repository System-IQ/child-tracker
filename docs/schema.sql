CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  owner_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_seen TIMESTAMPTZ,
  battery INT,
  app_version TEXT
);

CREATE TABLE IF NOT EXISTS locations (
  id BIGSERIAL PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  altitude DOUBLE PRECISION,
  speed DOUBLE PRECISION,
  accuracy DOUBLE PRECISION,
  heading DOUBLE PRECISION,
  battery INT,
  source TEXT DEFAULT 'gps',
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_loc_dev_time ON locations(device_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS geofences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  radius_m DOUBLE PRECISION NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sos_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  message TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS commands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  command TEXT NOT NULL,
  payload JSONB DEFAULT '{}'::jsonb,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  executed_at TIMESTAMPTZ
);

ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE geofences ENABLE ROW LEVEL SECURITY;
ALTER TABLE sos_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE commands ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_all_devices ON devices;
DROP POLICY IF EXISTS anon_all_locations ON locations;
DROP POLICY IF EXISTS anon_all_geofences ON geofences;
DROP POLICY IF EXISTS anon_all_sos ON sos_events;
DROP POLICY IF EXISTS anon_all_commands ON commands;

CREATE POLICY anon_all_devices ON devices FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY anon_all_locations ON locations FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY anon_all_geofences ON geofences FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY anon_all_sos ON sos_events FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY anon_all_commands ON commands FOR ALL TO anon USING (true) WITH CHECK (true);

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated;

INSERT INTO devices (id, name) VALUES ('child_phone_01', 'Child One')
ON CONFLICT (id) DO NOTHING;

SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('devices','locations','geofences','sos_events','commands')
ORDER BY table_name;
