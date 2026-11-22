# Metrics

**Incidents:** distinct reconciled identifiers. Repeated source rows do not increase the count; an unresolved conflict contributes no canonical incident.

**Unit responses:** distinct incident–apparatus pairs from reported participation lists. One incident can have several responses. First-arriving apparatus is a separate source label, not a response-time measure.

All views and exports apply the same filters. Different filter dimensions use AND; multiple selections within one dimension use OR. Date ranges include both selected local dates. Hour ranges include the start and exclude the end, including overnight ranges.

Category shares divide by the displayed selected population. Unit-response shares use selected unit responses; incident-category shares use all selected incidents, with missing values shown as `Unknown`. Small groups are flagged.

The heatmap weights each validated location by distinct incidents, capped at ten per location for display. Its 10 pixel radius blends nearby points at the current zoom; it does not represent a fixed geographic area. Unlocated incidents stay in non-map totals. No response-duration or target-attainment metric is calculated.
