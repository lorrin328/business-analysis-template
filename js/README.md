# JS runtime boundary

Current production runtime:

- `../经营分析模板.html`
- `constants.js`
- `format-utils.js`
- `api-client.js`
- `export-excel.js` (dashboard workbook download)
- `dashboard-config.js`
- `upload.js`
- `target-modal.js`
- `dashboard-actions.js` (header toolbar action binding)
- `kpi-cards.js`
- `platform-trend.js` (shared helpers only)
- `product-config-modal.js`
- `kpi-modal-content.js`
- `org-analysis.js`
- `seed-data.js`
- `platform-seed-data.js` (local fallback platform trend data only)
- `data-integration.js` (API loading, fallback conversion, and dashboard refresh)
- `platform-trend-main.js` (platform trend chart state and rendering)
- `product-analysis.js` (loaded in-page before payment-period controls)
- `payperiod-chart.js` (loaded in-page before team chart)
- `team-analysis.js` (loaded in-page before resize/init)

Earlier module-migration reference files that are not loaded by `经营分析模板.html` have been archived under `bak/20260524_stability_archive/js_unused/`.

When fixing a production behavior, update `经营分析模板.html` first unless the script is already loaded by the page.
