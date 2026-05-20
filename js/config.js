// config.js — 运行时配置（从后端动态加载业务线）
(function (window) {
  const Config = {
    _businessLines: null,
    _loaded: false,

    async loadBusinessLines() {
      if (this._loaded && this._businessLines) return this._businessLines;
      try {
        const resp = await window.fetchJson('/api/config/business-lines');
        this._businessLines = window.unwrapApiResponse(resp) || [];
        this._loaded = true;
        window.AppState.set('businessLines', this._businessLines);
        return this._businessLines;
      } catch (e) {
        console.warn('Failed to load business lines from API, using defaults');
        this._businessLines = this._defaults();
        this._loaded = true;
        return this._businessLines;
      }
    },

    getBusinessLines() {
      return this._businessLines || this._defaults();
    },

    getLine(name) {
      const lines = this.getBusinessLines();
      return lines.find(l => l.name === name || (l.aliases && l.aliases.includes(name)));
    },

    getLineNames() {
      return this.getBusinessLines().map(l => l.name);
    },

    getChannelColors() {
      const lines = this.getBusinessLines().filter(l => l.isIncludedInTotal && l.code !== 'total' && l.code !== 'transform');
      const colors = {};
      lines.forEach(l => { colors[l.name] = l.color; });
      return colors;
    },

    lineSupportsOrg(name) {
      const line = this.getLine(name);
      return line ? line.supportOrgDimension : true;
    },

    _defaults() {
      return [
        { "code": "jingdai", "name": "经代", "displayName": "经代", "color": "#8b5cf6", "order": 10, "isIncludedInTotal": true, "supportOrgDimension": false, "supportTeamDimension": false, "supportDailyTrend": true, "aliases": ["经代"] },
        { "code": "oto", "name": "OTO", "displayName": "OTO", "color": "#3b82f6", "order": 20, "isIncludedInTotal": true, "supportOrgDimension": true, "supportTeamDimension": true, "supportDailyTrend": true, "aliases": ["OTO"] },
        { "code": "zhengbao", "name": "证保", "displayName": "证保", "color": "#10b981", "order": 30, "isIncludedInTotal": true, "supportOrgDimension": true, "supportTeamDimension": true, "supportDailyTrend": true, "aliases": ["证保", "证券"] },
        { "code": "yiqiao", "name": "蚁桥", "displayName": "蚁桥", "color": "#f59e0b", "order": 40, "isIncludedInTotal": true, "supportOrgDimension": true, "supportTeamDimension": true, "supportDailyTrend": true, "aliases": ["蚁桥", "网服"] },
        { "code": "transform", "name": "转型业务", "displayName": "转型业务", "color": "#14b8a6", "order": 50, "isIncludedInTotal": true, "supportOrgDimension": true, "supportTeamDimension": true, "supportDailyTrend": true, "aliases": ["转型业务"] },
        { "code": "total", "name": "整体业务", "displayName": "整体业务", "color": "#e2e8f0", "order": 60, "isIncludedInTotal": false, "supportOrgDimension": false, "supportTeamDimension": false, "supportDailyTrend": true, "aliases": ["整体", "整体业务"] },
      ];
    },
  };

  window.Config = Config;
})(window);
