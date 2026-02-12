define(['./errors/openerror',
        'events',
        'class'],
function(OpenError, Emitter, clazz) {
  
  function Opener(obj) {
    Opener.super_.call(this);
    this._qtOpener = obj;
    this.init();
  }
  clazz.inherits(Opener, Emitter);
  
  Opener.prototype.init = function() {
    this._onsuccess = onSuccess.bind(this);
    this._onerror = onError.bind(this);
    this._qtOpener.onsuccess.connect(this._onsuccess);
    this._qtOpener.onerror.connect(this._onerror);
  }
  
  Opener.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._onsuccess) { this._qtOpener.onsuccess.disconnect(this._onsuccess); this._onsuccess = null; }
    if (this._onerror) { this._qtOpener.onerror.disconnect(this._onerror); this._onerror = null; }
    
    this._qtOpener = null;
  }
  
  Opener.prototype.start = function() {
    this._qtOpener.open();
  }
  
  
  function onSuccess() {
    this.emit('end');
  }
  
  function onError(code, message) {
    this.emit('error', new OpenError(message, code));
  }
  
  return Opener;
});
