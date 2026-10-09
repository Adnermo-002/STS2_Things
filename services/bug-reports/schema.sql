CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  client_report_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  source TEXT NOT NULL,
  description TEXT NOT NULL,
  game_version TEXT,
  mod_version TEXT,
  seed TEXT,
  ascension INTEGER,
  act_index INTEGER,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  developer_note TEXT NOT NULL DEFAULT '',
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_version ON reports(game_version,mod_version);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status,created_at DESC);
CREATE TABLE IF NOT EXISTS intake_rate (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_intake_rate_date ON intake_rate(updated_at);
