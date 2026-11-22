# Known limitations and department decisions

- Required response timing reports are outside the project owner's current First Due access. Durations, target attainment, and response-mode or cancellation exclusions are unavailable; this does not block the incident-analysis MVP.
- Incident-number uniqueness across source, department, and year is provisional. Following the October 26 upload, 17 supplied identifiers have conflicting source values and remain excluded pending review; some conflicts concern report status rather than a different event.
- The new summary exports omit final incident type, property type, full apparatus participation, and station. Compatible detailed overlaps retain those fields; summary-only incidents remain included with unknowns. Unit-response totals and participation filters do not cover incidents without a reported unit list. First-arriving apparatus is available independently and is not a complete response assignment.
- Apparatus parsing assumes comma-separated complete tokens. Company mappings and historical effective dates need department approval. Unknown units remain visible.
- Coordinate-cache provenance, address matching, and out-of-area points need review. Mapping coverage is disclosed; no geocoding or district boundaries are supplied.
- Export coverage and refresh frequency are unknown. Observed event-date bounds do not establish complete reporting; seasonal and year comparisons may cover partial periods.
- Repeat locations identify candidates only. Official target-hazard designation requires approved criteria and other risk sources.
- Localhost access assumes an authorized local user. Shared hosting, accounts, and concurrent importing are deferred.
- The road basemap needs browser access to OpenStreetMap tiles. If unavailable, the heat layer and non-map analysis still work, but roads may be blank.
- Python 3.11 execution and visual browser review still need release sign-off on the intended machine. Final headless Chrome screenshots are recorded in `docs/screenshots/`; a legacy reference screenshot was unavailable because the native computer-use service failed.
