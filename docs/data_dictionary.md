# Data dictionary and source assumptions

Two export layouts are supported. Detailed `Incident Report*.csv` files require all eleven headers below. Summary `incident_reports*.csv` files require `INCIDENT`, `INCIDENT DATE/TIME`, `STATUS`, `DISPATCH TYPE`, `1ST ARRIVING`, `INCIDENT LOCATION`, and `SHIFT`. Surrounding header whitespace and capitalization are normalized; `INCIDENT` aliases `INCIDENT NUMBER`. Duplicate headers after normalization are rejected, including a file supplying both identity aliases. Layout validation uses headers rather than filenames; filenames control directory discovery only.

Only a non-placeholder incident identifier is a required **row value**. A row with a missing classification, location, apparatus, station, first-arriving unit, or usable date remains eligible if its identity is resolved. Extra columns remain in `source_rows.raw_json` and appear in the import report. Summary personnel/editor fields (`OFFICER IN CHARGE`, `LAST OPENED BY`) are not shown or exported and do not affect analytical identity. UTF-8 and UTF-8-SIG are accepted.

| First Due column | Stored field / use | Current assumption |
| --- | --- | --- |
| `INCIDENT NUMBER` | `identity_key`, raw source JSON | Provisional unique incident identifier, exact trimmed text |
| `INCIDENT DATE/TIME` | `source_timestamp`, parsed `local_timestamp` | Meaning and timezone are unconfirmed; label source-reported |
| `STATUS` | `status` | Report workflow status, not operational disposition |
| `DISPATCH TYPE` | `dispatch_type` | Initial classification, separate from incident type |
| `1ST ARRIVING` | `first_unit` | Source-reported apparatus label, never a time |
| `INCIDENT LOCATION` | `location_raw`, `location_key` | Address text; no inferred district |
| `SHIFT` | `shift` | Source-reported A–D, no derived rotation |
| `INCIDENT TYPE` | `incident_type` | Original reported classification |
| `PROPERTY TYPE` | `property_type` | Original property classification |
| `APPARATUS` | `apparatus_raw`, `participations` | Comma-separated complete unit tokens, deduplicated within incident |
| `STATION` | `station` | Source value only; meaning unconfirmed |

Summary exports omit `INCIDENT TYPE`, `PROPERTY TYPE`, `APPARATUS`, and `STATION`. Absence of a column means it supplies no observation for reconciliation. Compatible overlaps retain the detailed source's values regardless of import order. A differing supplied value remains a conflict, including a supplied blank compared with a known value. Date strings such as `Apr 28, 2026 19:51:03` and `2026-04-28 19:51:03` compare by parsed local time rather than text.

For summary-only incidents, final incident type/property type/station remain unknown and no apparatus participation is invented. `DISPATCH TYPE` remains a separate usable classification, and `1ST ARRIVING` supports first-arrival filtering even without a participation list. Participation filters and totals cover reported unit lists only. The dashboard context and export metadata disclose missing participation, final incident type, and property type within the selected incidents.

Whitespace is collapsed and `--`, empty, `N/A`, and `NULL` become missing. Original values remain in source-row JSON. Known exact aliases such as `E22` and `Engine 22` map to the same apparatus label. Unknown labels remain named and are marked unmapped; volunteer, reserve, and mutual-aid units are not discarded. No company is inferred from a station or apparatus label. `config/dashboard.json` holds optional approved mappings with a config version; broad categories remain unavailable until one is approved.

Naive source timestamps are treated as local wall-clock text for calendar analysis, under an explicit `America/New_York` display assumption. Because the export does not state its timezone or event meaning, no UTC instant is asserted for those rows. Explicit offset timestamps can produce UTC instants. Ambiguous and nonexistent daylight-saving wall times are flagged with no UTC instant. Missing or malformed times remain in overall unfiltered incident counts and are excluded whenever a temporal filter is active. Calendar comparisons should not be described as dispatch or call-received trends until the field meaning is confirmed.

Winter spans December through February and is assigned to the year containing January/February; spring, summer, and fall follow calendar quarters in `config/dashboard.json`. Seasonal panels can include partial seasons because export coverage is unverified. Date filters are inclusive local dates. Hour ranges are start-inclusive/end-exclusive and may wrap midnight.

Coordinate cache entries carry address, latitude, longitude, and a date. That date is **not** used as an incident join key. The cache provenance and original geocoding quality are unknown. Matching uses exact normalized address text; points with inconsistent cache coordinates are withheld. Coordinates outside the configured Danbury plausibility box are labeled `out_of_area` because mutual aid may be legitimate. Missing coordinates remain null, never `(0, 0)`.

