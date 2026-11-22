ALTER TABLE resolutions ADD COLUMN source_row_watermark INTEGER;
UPDATE resolutions SET source_row_watermark=source_row_id WHERE source_row_watermark IS NULL;
UPDATE metadata SET value='3' WHERE key='schema_version';
