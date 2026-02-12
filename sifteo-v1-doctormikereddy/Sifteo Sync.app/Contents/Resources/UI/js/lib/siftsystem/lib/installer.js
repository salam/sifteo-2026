define(['./errors/installerror',
        'events',
        'class'],
function(InstallError, Emitter, clazz) {
  
  function Installer(obj) {
    Installer.super_.call(this);
    this._qtInstaller = obj;
    this.init();
  }
  clazz.inherits(Installer, Emitter);
  
  Installer.prototype.init = function() {
    this._onprogress = onProgress.bind(this);
    this._onsuccess = onSuccess.bind(this);
    this._onerror = onError.bind(this);
    this._qtInstaller.onprogress.connect(this._onprogress);
    this._qtInstaller.onsuccess.connect(this._onsuccess);
    this._qtInstaller.onerror.connect(this._onerror);
  }
  
  Installer.prototype.destroy = function() {
    // TODO: Remove all listeners.
    if (this._onprogress) { this._qtInstaller.onprogress.disconnect(this._onprogress); this._onprogress = null; }
    if (this._onsuccess) { this._qtInstaller.onsuccess.disconnect(this._onsuccess); this._onsuccess = null; }
    if (this._onerror) { this._qtInstaller.onerror.disconnect(this._onerror); this._onerror = null; }
    
    this._qtInstaller = null;
  }
  
  Installer.prototype.start = function() {
    this._qtInstaller.install();
  }
  
  
  function onProgress(partial, total) {
    this.emit('progress', partial, total);
  }
  
  function onSuccess() {
    this.emit('end');
  }
  
  function onError(code, message) {
    this.emit('error', new InstallError(message, code));
  }
  
  return Installer;
});
