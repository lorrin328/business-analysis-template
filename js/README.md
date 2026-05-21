# JS runtime boundary

Current production runtime:

- `../经营分析模板.html`
- `api-client.js`

The other files in this directory are retained as module-migration references from earlier refactor attempts. They are not active runtime code until `经营分析模板.html` explicitly loads them with `<script src="js/...">` and the related static/browser checks pass.

When fixing a production behavior, update `经营分析模板.html` first unless the script is already loaded by the page.
