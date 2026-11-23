# Validation

On November 22, 2026, a fresh Python 3.14.3 environment installed the constrained editable package and passed `pip check`. The suite passed **18 tests**, covering import reconciliation, filters, exports, map configuration, and demo isolation. Dash emitted 25 deprecation warnings for its built-in DataTable.

The synthetic fixture imported **240 invented incidents** at **24 invented location labels**; every incident mapped. The demo database carried the synthetic marker, and the demo command rejected an unmarked database. The operational `serve` command rejected a non-local bind.

A headless Chrome capture with software WebGL showed the synthetic banner, road tiles, and navy heat spots: [demo screenshot](screenshots/portfolio-demo-2026-11-22.png). A capture without software WebGL did not show the density layer. Browser review on the intended machine remains open.

`git diff --check`, Ruff lint, and Ruff format checks pass. Python 3.11 execution has not been verified.
