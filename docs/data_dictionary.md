# Data dictionary

The synthetic CSV uses the detailed import format. A second, shorter format is also supported for local development. Only a nonblank incident identifier is required as a row value; missing optional fields remain unknown.

| CSV field | Dashboard use |
| --- | --- |
| `INCIDENT NUMBER` | Reconciliation identity; synthetic rows use `DEMO-` IDs |
| `INCIDENT DATE/TIME` | Source-reported local date and time filters |
| `STATUS` | Report workflow status |
| `DISPATCH TYPE` | Initial classification, separate from incident type |
| `1ST ARRIVING` | Source-reported first unit, not a time measurement |
| `INCIDENT LOCATION` | Location label and exact coordinate-cache match |
| `SHIFT` | Source-reported shift |
| `INCIDENT TYPE` | Reported incident classification |
| `PROPERTY TYPE` | Reported property classification |
| `APPARATUS` | Comma-separated participating units |
| `STATION` | Source station label |

The shorter format uses `INCIDENT` as the identifier and omits incident type, property type, apparatus, and station. Those values stay unknown unless a compatible detailed row supplies them. A first-arriving unit does not imply a complete participation list.

Timestamp meaning and timezone are not guaranteed by the source format. Naive timestamps are treated as local wall-clock values for exploratory calendar views. Missing or unusable times remain in unfiltered incident totals and drop out only when a time filter is active. The map uses exact normalized location labels and withholds inconsistent coordinates; it does not geocode in a callback.
