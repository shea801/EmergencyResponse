# Known limitations

- All portfolio incidents and locations are synthetic. The demo demonstrates the software, not actual emergency demand or performance.
- The source format has no verified dispatch, arrival, or clearance intervals; response times and target attainment are unavailable.
- Source timestamps, station labels, and apparatus mappings need review before operational interpretation. Missing participation lists do not become inferred unit responses.
- The heatmap depends on browser WebGL. OpenStreetMap road tiles require internet access; the other views remain available without tiles.
- The local SQLite design has no user accounts or shared-hosting controls. Public hosting must use the synthetic database.
- Python 3.14.3 and the synthetic browser view were exercised; Python 3.11 and the intended deployment environment still need verification.
