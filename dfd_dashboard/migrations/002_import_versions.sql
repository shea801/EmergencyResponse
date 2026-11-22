ALTER TABLE import_batches ADD COLUMN importer_version TEXT;
ALTER TABLE import_batches ADD COLUMN schema_version INTEGER;
ALTER TABLE import_batches ADD COLUMN config_version TEXT;
UPDATE metadata SET value='2' WHERE key='schema_version';
