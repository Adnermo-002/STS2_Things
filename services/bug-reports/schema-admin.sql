ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'new';
ALTER TABLE reports ADD COLUMN developer_note TEXT NOT NULL DEFAULT '';
ALTER TABLE reports ADD COLUMN updated_at TEXT;
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at DESC);
