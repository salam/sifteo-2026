define(['./app',
        'events',
        'class'],
function(App, Emitter, clazz) {
  
  function Apps() {
    Apps.super_.call(this);
    this._a = [];
    this.init();
  }
  clazz.inherits(Apps, Emitter);
  
  Apps.prototype.init = function() {
    var self = this;
    
    this.__defineGetter__('length', function() {
      return self._a.length;
    });
    
    if (!window.siftSystem) return;
    
    for (var i = 0, len = siftSystem.apps.length; i < len; i++) {
      var qtapp = siftSystem.apps.at(i);
      this._a.push(new App(qtapp));
    }
    
    this._onadded = onAdded.bind(this);
    this._onremoved = onRemoved.bind(this);
    siftSystem.apps.onadded.connect(this._onadded);
    siftSystem.apps.onremoved.connect(this._onremoved);
  }
  
  Apps.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._onadded) { siftSystem.apps.onadded.disconnect(this._onadded); this._onadded = null; }
    if (this._onremoved) { siftSystem.apps.onremoved.disconnect(this._onremoved); this._onremoved = null; }
  }
  
  Apps.prototype.at = function(i) {
    return this._a[i];
  }
  
  
  function onAdded(qtapp) {
    var app = new App(qtapp);
    this._a.push(app);
    this.emit('added', app);
  }
  
  function onRemoved(qtapp) {
    var pos = -1
      , app;
    for (var i = 0, len = this._a.length; i < len; i++) {
      if (this._a[i]._qtApp === qtapp) {
        pos = i;
        app = this._a[i];
        break;
      }
    }
    if (pos !== -1) {
      this._a.splice(pos, 1);
      this.emit('removed', app);
    }
  }
  
  return new Apps();
});
