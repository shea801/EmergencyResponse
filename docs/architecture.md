# Architecture

`dfd_dashboard.cli` is the only supported entry point. 
`ingestion` validates and normalizes exports, 
`storage` owns SQLite schema and transactions, 
`analytics` owns shared filtering and counts, 
`dashboard` renders the Dash views,
`config` supplies project-relative paths and versioned mappings. 

Presentation callbacks do not import, geocode, or change analytical records. Each callback loads a reconciled snapshot and applies one `Filters` value; exports use the same functions.

The summary map uses a Plotly weighted density trace over OpenStreetMap road tiles. 
The density input is the filtered, distinct incident count at each validated normalized address. 
The browser requests tiles for its viewport and zoom; those requests do not contain incident rows or address text.
Roads depend on tile access, while the incident data and other views remain local.

SQLite lives at `data/incidents.sqlite3` by default. 
Migration `dfd_dashboard/migrations/001_initial.sql` creates `metadata`, `import_batches`, immutable `source_rows`, `resolutions`, `locations`, `incidents`, `apparatus`, and `participations`; 
migration `002_import_versions.sql` adds importer/schema/config versions to import attempts; 
migration `003_resolution_watermark.sql` records which source versions a resolution reviewed. 

Foreign keys and uniqueness constraints enforce one canonical incident per provisional source incident number and one participation per incident–apparatus pair. 
Source rows retain raw and normalized JSON, file hash/name, CSV row number, validation status, and issues. 
`PRAGMA user_version` is not used; 
`metadata.schema_version` is 3. 

New schema changes need numbered migrations, a backup, and restore verification. WAL mode and `BEGIN IMMEDIATE` serialize imports; SQLite backup uses the live connection's backup API.

The current identity key is the exact trimmed `INCIDENT NUMBER`. This is provisional pending confirmation of department/source/year scope. 
`source_formats` validates detailed and summary layouts, aliases the summary `INCIDENT` header, and compares only fields supplied by each source. Dates compare by parsed values and apparatus by canonical unit sets. Compatible reduced exports retain the richer detailed record; differences in formatting, omitted columns, or personnel/editor metadata do not create conflicts. If supplied analytical values conflict for the same identity, no version becomes canonical unless a reviewer adds a resolution decision. A reduced record matching two incompatible detailed records cannot resolve that conflict. 
Repeated rows are retained as source lineage. 
Reimporting an unchanged file records an attempt but does not add source rows or change canonical totals. 
A later export omitting an incident leaves existing rows intact. 
A corrected record creates a conflicting candidate; 

the `resolve` command records the selected source row, reviewed-source watermark, and reason before analytical totals change. 
A genuinely new conflicting observation arriving after a resolution invalidates that choice and excludes the identity again; repeated or compatible reduced versions do not. Compatible new detailed observations can enrich a selected summary record. Resolutions retain the exact selected source-row ID even when it duplicates an earlier source row. 

Report status is retained separately from operational classification; no dispatch or arrival duration schema exists.

`config/dashboard.json` is the versioned configuration: timezone label, known apparatus aliases, optional approved company and broad-category mappings, seasons, and display thresholds. 
Aliases are exact complete tokens after splitting `APPARATUS` on commas. Company mappings start empty because no effective-dated operational mapping has been approved; 
apparatus identity remains separate. Changing alias/company mappings for existing imported rows requires a reviewed data rebuild or a future reprocessing migration, rather than silently changing historical results.
Data and configuration versions accompany every export.

Location identity is normalized uppercase address text with punctuation and whitespace folded. The existing JSON coordinate cache is indexed by that identity only. 
Cache entries for the same address must agree within about 200 feet; larger disagreements are withheld. 
Geographic plausibility is flagged, not used to infer first-due district. 
No timestamp join or callback geocoding occurs. 
`refresh-coordinates` reapplies the cache without changing incident identity.

The dashboard has no shared mutable global dataset or cross-request cache.

At the reviewed size, loading a snapshot takes about 0.08 seconds; each view callback including aggregation and serialization takes about 1.2–1.4 seconds on the tested machine.

Multiple users or concurrent importers would require a reassessment of SQLite and hosting before shared deployment.
