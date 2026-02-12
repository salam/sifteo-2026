define(['./errors/fetcherror',
        'events',
        'class'],
function(FetchError, Emitter, clazz) {
  
  function Fetcher(obj) {
    Fetcher.super_.call(this);
    this._qtFetcher = obj;
    this.init();
  }
  clazz.inherits(Fetcher, Emitter);
  
  Fetcher.prototype.init = function() {
    this._onprogress = onProgress.bind(this);
    this._onsuccess = onSuccess.bind(this);
    this._onerror = onError.bind(this);
    this._qtFetcher.onprogress.connect(this._onprogress);
    this._qtFetcher.onsuccess.connect(this._onsuccess);
    this._qtFetcher.onerror.connect(this._onerror);
  }
  
  Fetcher.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._onprogress) { this._qtFetcher.onprogress.disconnect(this._onprogress); this._onprogress = null; }
    if (this._onsuccess) { this._qtFetcher.onsuccess.disconnect(this._onsuccess); this._onsuccess = null; }
    if (this._onerror) { this._qtFetcher.onerror.disconnect(this._onerror); this._onerror = null; }
    
    this._qtFetcher = null;
  }
  
  Fetcher.prototype.start = function() {
    this._qtFetcher.fetch();
  }
  
  
  function onProgress(partial, total) {
    this.emit('progress', partial, total);
  }
  
  function onSuccess() {
    this.emit('end');
  }
  
  function onError(code, message) {
    this.emit('error', new FetchError(message, code));
  }
  
  return Fetcher;
});
