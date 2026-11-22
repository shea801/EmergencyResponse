PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', '1'), ('data_version', '0');
CREATE TABLE IF NOT EXISTS import_batches (
  id INTEGER PRIMARY KEY, filename TEXT NOT NULL, file_hash TEXT NOT NULL,
  imported_at TEXT NOT NULL, status TEXT NOT NULL, report_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_import_hash ON import_batches(file_hash);
CREATE TABLE IF NOT EXISTS source_rows (
  id INTEGER PRIMARY KEY, file_hash TEXT NOT NULL, filename TEXT NOT NULL,
  row_number INTEGER NOT NULL, identity_key TEXT, fingerprint TEXT,
  raw_json TEXT NOT NULL, normalized_json TEXT,
  validation_status TEXT NOT NULL, issues_json TEXT NOT NULL,
  UNIQUE(filename, file_hash, row_number)
);
CREATE INDEX IF NOT EXISTS idx_source_identity ON source_rows(identity_key);
CREATE TABLE IF NOT EXISTS resolutions (
  id INTEGER PRIMARY KEY, identity_key TEXT NOT NULL, source_row_id INTEGER NOT NULL,
  decided_at TEXT NOT NULL, reason TEXT NOT NULL,
  FOREIGN KEY(source_row_id) REFERENCES source_rows(id)
);
CREATE INDEX IF NOT EXISTS idx_resolution_identity ON resolutions(identity_key);
CREATE TABLE IF NOT EXISTS locations (
  location_key TEXT PRIMARY KEY, display_name TEXT NOT NULL,
  latitude REAL, longitude REAL, coordinate_source TEXT,
  matching_method TEXT, validation_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
  identity_key TEXT PRIMARY KEY, source_row_id INTEGER NOT NULL,
  source_timestamp TEXT, local_timestamp TEXT, utc_timestamp TEXT,
  timestamp_issue TEXT, status TEXT, dispatch_type TEXT, first_unit TEXT,
  first_unit_mapped INTEGER NOT NULL DEFAULT 0, location_raw TEXT,
  location_key TEXT, shift TEXT, incident_type TEXT, property_type TEXT,
  apparatus_raw TEXT, station TEXT,
  FOREIGN KEY(source_row_id) REFERENCES source_rows(id),
  FOREIGN KEY(location_key) REFERENCES locations(location_key)
);
CREATE INDEX IF NOT EXISTS idx_incident_local ON incidents(local_timestamp);
CREATE INDEX IF NOT EXISTS idx_incident_shift ON incidents(shift);
CREATE INDEX IF NOT EXISTS idx_incident_type ON incidents(incident_type);
CREATE INDEX IF NOT EXISTS idx_incident_location ON incidents(location_key);
CREATE TABLE IF NOT EXISTS apparatus (
  label TEXT PRIMARY KEY, mapped INTEGER NOT NULL, company TEXT
);
CREATE TABLE IF NOT EXISTS participations (
  identity_key TEXT NOT NULL, apparatus_label TEXT NOT NULL,
  PRIMARY KEY(identity_key, apparatus_label),
  FOREIGN KEY(identity_key) REFERENCES incidents(identity_key) ON DELETE CASCADE,
  FOREIGN KEY(apparatus_label) REFERENCES apparatus(label)
);
CREATE INDEX IF NOT EXISTS idx_participation_unit ON participations(apparatus_label);
