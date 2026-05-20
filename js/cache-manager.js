// cache-manager.js — 统一缓存管理
(function (window) {
  const _cache = {};

  const Cache = {
    get(key) {
      const entry = _cache[key];
      if (!entry) return null;
      if (entry.expires && Date.now() > entry.expires) {
        delete _cache[key];
        return null;
      }
      return entry.value;
    },

    set(key, value, ttlMs) {
      _cache[key] = {
        value,
        expires: ttlMs ? Date.now() + ttlMs : null,
      };
    },

    has(key) {
      return Cache.get(key) !== null;
    },

    invalidate(pattern) {
      const keys = Object.keys(_cache).filter(k => k.includes(pattern));
      keys.forEach(k => delete _cache[k]);
    },

    clear() {
      Object.keys(_cache).forEach(k => delete _cache[k]);
    },
  };

  window.Cache = Cache;
})(window);
