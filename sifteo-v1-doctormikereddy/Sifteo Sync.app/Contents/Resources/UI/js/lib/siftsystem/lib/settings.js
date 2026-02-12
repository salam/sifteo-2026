define(function() {
  
  function Settings() {
  }
  
  Settings.prototype.get = function(key, def) {
    if (!window.siftSystem) return;
  
    var v = siftSystem.settings.get(key);
    if (v === null || v === undefined) {
      v = def;
    }
    return v;
  }
  
  Settings.prototype.set = function(key, val) {
    siftSystem.settings.set(key, val);
  }
  
  return new Settings();
});
